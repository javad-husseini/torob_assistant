"""Owned, short-lived shopping conversations with a fixed UI component vocabulary."""
from __future__ import annotations

import asyncio
import copy
import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Literal
from uuid import uuid4

from pydantic import Field, ValidationError, field_validator, model_validator

from . import chat_model, routing
from .models import Strict, StoreLocation, Intent, ExtractionUsage, normalize
from .shop_search import ShopRepository

TTL = 3600
MAX_TURNS = 40
CONFIRM_SEARCH = 'بله، شرایط جدید را تأیید می‌کنم'
KEEP_SEARCH = 'شرایط قبلی حفظ شود'


class TurnRequest(Strict):
    request_id: str = Field(min_length=1, max_length=100)
    action: Literal['message', 'select_product', 'set_location', 'compare', 'inquiry', 'back_to_products'] = 'message'
    message: str = Field(default='', max_length=2000)
    product_id: str | None = Field(default=None, max_length=100)
    offer_ids: list[str] = Field(default_factory=list, max_length=4)
    location: StoreLocation | None = None
    travel_mode: Literal['car', 'pedestrian'] | None = None

    @field_validator('offer_ids')
    @classmethod
    def distinct_offers(cls, value):
        if len(value) != len(set(value)) or any(not x or len(x) > 100 for x in value):
            raise ValueError('distinct offer identifiers required')
        return value

    @model_validator(mode='after')
    def valid_action(self):
        if self.action == 'message' and not self.message:
            raise ValueError('message is required')
        if self.action == 'select_product' and not self.product_id:
            raise ValueError('product_id is required')
        if self.action == 'set_location' and (self.location is None or self.travel_mode is None):
            raise ValueError('a confirmed map pin and travel mode are required')
        if self.action == 'compare' and not 2 <= len(self.offer_ids) <= 4:
            raise ValueError('select two to four store offers')
        if self.action == 'inquiry' and len(self.offer_ids) != 1:
            raise ValueError('select one store offer')
        if self.action != 'set_location' and (self.location is not None or self.travel_mode is not None):
            raise ValueError('location is accepted only from a confirmed pin action')
        return self


class AssistantError(Exception):
    def __init__(self, status: int, detail: str):
        self.status, self.detail = status, detail
        super().__init__(detail)


@dataclass
class Conversation:
    owner: str
    id: str = field(default_factory=lambda: uuid4().hex)
    created: float = field(default_factory=time.monotonic)
    stage: int = 1
    messages: list = field(default_factory=list)
    products: list = field(default_factory=list)
    offers: list = field(default_factory=list)
    selected: dict | None = None
    search_intent: Intent | None = None
    pending_search: Intent | None = None
    origin: StoreLocation | None = None
    travel_mode: str | None = None
    usage: list = field(default_factory=list)
    requests: dict = field(default_factory=dict)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class AssistantService:
    def __init__(self, catalog, *, planner=None, explainer=None, router=None, modes=None):
        self.catalog = catalog
        self.repo = ShopRepository(catalog)
        self.sessions: dict[str, Conversation] = {}
        self.planner = planner or chat_model.plan_turn
        self.explainer = explainer or chat_model.explain_results
        self.router = router or routing.route_offers
        # The caller supplies the user's approved transport choices.
        self.modes = tuple(modes or ())

    def cleanup(self):
        now = time.monotonic()
        for key, value in list(self.sessions.items()):
            if now - value.created >= TTL and not value.lock.locked():
                del self.sessions[key]

    def create(self, owner):
        self.cleanup()
        if len(self.sessions) >= 100:
            raise AssistantError(429, 'ظرفیت گفت‌وگوهای موقت تکمیل است؛ کمی بعد دوباره تلاش کنید.')
        session = Conversation(owner=owner)
        self.sessions[session.id] = session
        self._append(session, 'assistant', 'سلام! برای چه کاری دنبال خرید هستی، یا چه محصولی در نظر داری؟ اگر مدل مشخصی می‌خواهی، نامش را بگو.')
        return self.view(session)

    def owned(self, conversation_id, owner):
        self.cleanup()
        session = self.sessions.get(conversation_id)
        if not session or session.owner != owner or time.monotonic() - session.created >= TTL:
            raise AssistantError(404, 'گفت‌وگو پیدا نشد یا زمان نگهداری موقت آن پایان یافته است.')
        return session

    def delete(self, conversation_id, owner):
        session = self.owned(conversation_id, owner)
        if session.lock.locked():
            raise AssistantError(409, 'ابتدا منتظر پایان پاسخ جاری بمانید.')
        del self.sessions[session.id]
        return {'deleted': True}

    @staticmethod
    def view(session):
        return copy.deepcopy({
            'id': session.id, 'stage': session.stage,
            'messages': session.messages,
            'selected_product_id': (session.selected or {}).get('product_id'),
            'travel_mode': session.travel_mode,
            'expires_in_seconds': max(0, int(TTL - (time.monotonic() - session.created))),
            'usage': session.usage,
        })

    @staticmethod
    def _append(session, role, text, components=None):
        session.messages.append({'id': uuid4().hex, 'role': role, 'text': text, 'components': components or []})

    def _center(self, session):
        for offer in self.repo.offers_for_product(session.selected['product_id']):
            if (offer.get('store') or {}).get('location'):
                return offer['store']['location']
        return None

    def _context(self, session, message):
        categories = self.catalog.filters()['categories']
        terms = [x for x in normalize(message).split() if len(x) > 1]
        ranked = sorted(categories, key=lambda c: (-sum(t in normalize(c) for t in terms), c))
        common = ('گوشی موبایل', 'لپ تاپ', 'هدفون', 'لنز دوربین', 'کنسول بازی')
        preferred = [c for c in categories if any(normalize(c) == x for x in common)]
        def brief(p):
            return {
                'product_id': p.get('product_id') or p['id'], 'offer_id': p['id'],
                'name': p['name'], 'category': p['category'], 'attributes': dict(list(p['attributes'].items())[:10]),
                'price': p['price'], 'currency': p['currency'], 'stock': p['stock'],
                'store': {'id': p['store']['id'], 'name': p['store']['name']} if p.get('store') else None,
            }
        return {
            'stage': session.stage, 'message': message,
            'history': [{'role': m['role'], 'text': m['text'][:1600]} for m in session.messages[-12:]],
            'available_categories': list(dict.fromkeys([*preferred, *ranked[:40]])),
            'available_brands': self.catalog.filters().get('attributes', {}).get('برند', [])[:60],
            'selected_product': brief(session.selected) if session.selected else None,
            'products': [brief(p) for p in session.products],
            'offers': [brief(p) for p in session.offers],
            'has_confirmed_location': session.origin is not None,
            'travel_mode': session.travel_mode,
            'current_search': session.search_intent.model_dump(mode='json') if session.search_intent else None,
            'constraints': 'No current stock/reviews/installments evidence. Every mandatory filter must remain enforced.',
        }

    @staticmethod
    def _usage(session, request_id, kind, usage):
        session.usage.append({'request_id': request_id, 'kind': kind, **usage.model_dump(mode='json')})

    def _select(self, session, product_id):
        selected = next((p for p in session.products if p.get('product_id') == product_id), None)
        if selected is None:
            raise AssistantError(422, 'محصول را از کارت‌های همین گفت‌وگو انتخاب کنید.')
        if session.selected and session.selected['product_id'] == product_id:
            return False
        session.selected, session.offers, session.stage = selected, [], 2
        return True

    def _offers_selected(self, session, ids):
        lookup = {p['id']: p for p in session.offers}
        if not session.selected or any(i not in lookup for i in ids):
            raise AssistantError(422, 'فروشگاه را از پیشنهادهای همین محصول انتخاب کنید.')
        return [lookup[i] for i in ids]

    async def _stores(self, session):
        if session.selected is None:
            self._append(session, 'assistant', 'اول محصول یا نسخهٔ موردنظر را مشخص کنیم.')
            return
        session.stage = 2
        if session.origin is None or session.travel_mode is None:
            self._append(session, 'assistant', 'موقعیت شروع را خودت با پین روی نقشه مشخص کن تا مسیر فروشگاه‌های همین محصول بررسی شود.', [
                {'type': 'location', 'center': self._center(session)},
            ])
            return
        offers = self.repo.offers_for_product(session.selected['product_id'], intent=session.search_intent)
        candidates = self.repo.shortlist(session.origin, offers, limit=6)
        if not candidates:
            self._append(session, 'assistant', 'برای این محصول، فروشگاهی با موقعیت ثبت‌شده در داده‌ها پیدا نشد.')
            return
        session.offers = await self.router(session.origin, candidates, session.travel_mode)
        session.offers.sort(key=lambda p: (
            p.get('route', {}).get('status') != 'ready',
            p.get('route', {}).get('duration_seconds') if p.get('route', {}).get('duration_seconds') is not None else float('inf'),
            p['id'],
        ))
        ready = sum(p.get('route', {}).get('status') == 'ready' for p in session.offers)
        text = f'{len(session.offers)} فروشگاه برای همین نسخهٔ محصول بررسی شد. '
        text += 'ترتیب مسیرهای آماده بر اساس زمان رسیدن، در میان همین فروشگاه‌های بررسی‌شده است.' if ready else 'زمان و فاصلهٔ مسیر فعلاً در دسترس نیست؛ نزدیک‌ترین بودن تأیید نشده است.'
        self._append(session, 'assistant', text, [{'type': 'stores', 'items': session.offers}])

    def _compare(self, session, ids):
        if not 2 <= len(ids) <= 4 or len(ids) != len(set(ids)):
            raise AssistantError(422, 'دو تا چهار پیشنهاد فروش متفاوت را برای مقایسه انتخاب کنید.')
        items = self._offers_selected(session, ids)
        result = self.catalog.compare(ids)
        result['items'] = items
        session.stage = 3
        self._append(session, 'assistant', 'فروشگاه‌های همین محصول را کنار هم ببین. قیمت‌ها و موجودی امروز فقط پس از استعلام قابل تأییدند.', [
            {'type': 'comparison', **result},
        ])

    def _inquiry(self, session, ids):
        if len(ids) != 1:
            raise AssistantError(422, 'یک پیشنهاد فروش را برای استعلام انتخاب کنید.')
        items = self._offers_selected(session, ids)
        session.stage = 4
        self._append(session, 'assistant', 'برای پرسیدن قیمت و موجودی این محصول، دموی مرورگری را از همین‌جا شروع کن. تماس تلفنی واقعی برقرار نمی‌شود؛ خودت نقش فروشنده را داری.', [
            {'type': 'inquiry', 'items': items},
        ])

    def _intent(self, search):
        category = search.category
        if category:
            known = {normalize(c): c for c in self.catalog.filters()['categories']}
            category = known.get(normalize(category), category)
        attributes = {a.key: a.value for a in search.attributes}
        if search.brand:
            attributes['برند'] = search.brand
        return Intent(query=search.query, category=category, max_price=search.max_price,
            currency=search.currency, installments_only=search.installments_only,
            in_stock_only=search.in_stock_only, attributes=attributes, limit=30)

    @staticmethod
    def _changes_constraints(previous, incoming):
        if previous is None:
            return False
        if previous.category and normalize(previous.category) != normalize(incoming.category or ''):
            return True
        if previous.max_price is not None and (incoming.max_price is None or
                incoming.currency != previous.currency or incoming.max_price > previous.max_price):
            return True
        if previous.in_stock_only and not incoming.in_stock_only:
            return True
        if previous.installments_only and not incoming.installments_only:
            return True
        attrs = {normalize(k): normalize(v) for k,v in incoming.attributes.items()}
        if any(attrs.get(normalize(k)) != normalize(v) for k,v in previous.attributes.items()):
            return True
        hay = normalize(' '.join([incoming.query, incoming.category or '', *incoming.attributes.values()]))
        return any(token not in hay for token in normalize(previous.query).split())

    @staticmethod
    def _describe_intent(intent):
        pieces = [intent.query or 'بدون عبارت جست‌وجو', intent.category or 'همهٔ دسته‌ها']
        if intent.max_price is None:
            pieces.append('بدون سقف قیمت')
        else:
            unit = 'تومان' if intent.currency == 'TOMAN' else 'ریال'
            pieces.append(f'سقف {intent.max_price} {unit}')
        pieces.extend(f'{key}: {value}' for key,value in intent.attributes.items())
        if intent.in_stock_only: pieces.append('فقط موجودی تأییدشده')
        if intent.installments_only: pieces.append('فقط اقساط تأییدشده')
        return '؛ '.join(pieces)

    async def _search(self, session, intent, context, request_id):
        session.search_intent = intent
        session.pending_search = None
        session.products = self.repo.search_products(intent, limit=6)
        session.selected, session.offers, session.stage = None, [], 1
        if not session.products:
            self._append(session, 'assistant', 'محصولی با این مشخصات پیدا نکردم. می‌خواهی یکی از ویژگی‌ها یا محدودیت‌ها را تغییر بدهیم؟')
            return
        reply, usage = await self.explainer(context, session.products)
        self._usage(session, request_id, 'explain', usage)
        rationales = {r.product_id: r.rationale for r in reply.recommendations}
        items = [{**p, 'recommendation_reason': rationales.get(p['product_id'])} for p in session.products]
        self._append(session, 'assistant', reply.reply, [{'type': 'products', 'items': items}])

    async def _message(self, session, body):
        context = self._context(session, body.message)
        if session.pending_search and normalize(body.message) == normalize(CONFIRM_SEARCH):
            await self._search(session, session.pending_search, context, body.request_id)
            return
        if session.pending_search and normalize(body.message) == normalize(KEEP_SEARCH):
            session.pending_search = None
            self._append(session, 'assistant', 'شرایط قبلی حفظ شد. کدام ویژگی را می‌خواهی دقیق‌تر مشخص کنیم؟')
            return
        plan, usage = await self.planner(context)
        self._usage(session, body.request_id, 'plan', usage)
        if plan.action == 'search':
            if plan.search is None:
                raise AssistantError(422, 'درخواست جست‌وجو مشخص نشد؛ لطفاً محصول و ویژگی‌های موردنظرت را دقیق‌تر بنویس.')
            try:
                intent = self._intent(plan.search)
            except ValidationError:
                raise AssistantError(422, 'مشخصات جست‌وجو روشن نیست؛ لطفاً ویژگی‌های موردنظرت را دقیق‌تر بنویس.') from None
            if self._changes_constraints(session.search_intent, intent):
                session.pending_search = intent
                text = 'جست‌وجوی تازه بعضی شرایط قبلی را تغییر می‌دهد. آیا این تغییرها را تأیید می‌کنی؟\n'
                text += 'قبلی: ' + self._describe_intent(session.search_intent) + '\n'
                text += 'جدید: ' + self._describe_intent(intent)
                self._append(session, 'assistant', text, [{'type':'suggestions','items':[CONFIRM_SEARCH,KEEP_SEARCH]}])
                return
            await self._search(session, intent, context, body.request_id)
        elif plan.action == 'select_product':
            if self._select(session, plan.product_id):
                await self._stores(session)
        elif plan.action == 'stores':
            await self._stores(session)
        elif plan.action == 'compare':
            self._compare(session, plan.offer_ids)
        elif plan.action == 'inquiry':
            self._inquiry(session, plan.offer_ids)
        else:
            components = [{'type': 'suggestions', 'items': plan.suggestions}] if plan.suggestions else []
            self._append(session, 'assistant', plan.reply, components)

    async def turn(self, conversation_id, owner, body: TurnRequest):
        session = self.owned(conversation_id, owner)
        fingerprint = hashlib.sha256(body.model_dump_json(exclude={'request_id'}).encode()).hexdigest()
        async with session.lock:
            # A queued request may have waited until after expiration/deletion.
            self.owned(conversation_id, owner)
            previous = session.requests.get(body.request_id)
            if previous is not None:
                if previous != fingerprint:
                    raise AssistantError(409, 'شناسهٔ درخواست برای پیام دیگری استفاده شده است.')
                return self.view(session)
            if len(session.requests) >= MAX_TURNS:
                raise AssistantError(429, 'این گفت‌وگو به سقف پیام رسیده؛ گفت‌وگوی تازه‌ای شروع کنید.')
            # Validate native UI actions before recording the request.
            if body.action == 'select_product':
                if not any(p.get('product_id') == body.product_id for p in session.products):
                    raise AssistantError(422, 'کارت محصول معتبر نیست.')
            if body.action in ('compare', 'inquiry'):
                self._offers_selected(session, body.offer_ids)
            if body.action == 'set_location' and (session.selected is None or body.travel_mode not in self.modes):
                raise AssistantError(422, 'ابتدا محصول و نوع رفت‌وآمد مجاز را مشخص کنید.')
            session.requests[body.request_id] = fingerprint
            # Repeated clicks must preserve the existing pin picker/store results,
            # including later stages, and must never repeat routing requests.
            if (body.action == 'select_product' and session.selected
                    and session.selected['product_id'] == body.product_id):
                return self.view(session)
            labels = {
                'select_product': 'این نسخهٔ محصول را انتخاب می‌کنم.',
                'set_location': 'این پین را برای بررسی مسیر فروشگاه‌ها تأیید می‌کنم.',
                'compare': 'این فروشگاه‌ها را مقایسه کن.',
                'inquiry': 'از این فروشگاه دربارهٔ محصول استعلام بگیریم.',
                'back_to_products': 'به انتخاب محصول برگردیم.',
            }
            self._append(session, 'user', body.message if body.action == 'message' else labels[body.action])
            try:
                if body.action == 'message':
                    await self._message(session, body)
                elif body.action == 'select_product':
                    self._select(session, body.product_id)
                    await self._stores(session)
                elif body.action == 'set_location':
                    session.origin, session.travel_mode = body.location, body.travel_mode
                    await self._stores(session)
                elif body.action == 'compare':
                    self._compare(session, body.offer_ids)
                elif body.action == 'inquiry':
                    self._inquiry(session, body.offer_ids)
                else:
                    session.selected, session.offers, session.stage = None, [], 1
                    self._append(session, 'assistant', 'به انتخاب محصول برگشتیم. چه چیزی را تغییر بدهیم؟',
                        [{'type': 'products', 'items': session.products}] if session.products else [])
            except chat_model.ChatModelError as error:
                self._usage(session, body.request_id, 'error', error.usage)
                text = 'دستیار خرید فعلاً در دسترس نیست. لطفاً کمی بعد دوباره تلاش کن.' if error.code == 'unconfigured' else 'دریافت پاسخ انجام نشد. لطفاً دوباره تلاش کن.'
                self._append(session, 'assistant', text)
            except AssistantError as error:
                self._append(session, 'assistant', error.detail)
            return self.view(session)
