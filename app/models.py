from __future__ import annotations
import re, unicodedata
from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal
from urllib.parse import urlsplit
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, field_serializer, model_validator


def normalize(value: str) -> str:
    value = unicodedata.normalize('NFKC', value).translate(str.maketrans('يىك۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩', 'ییک01234567890123456789'))
    value = value.replace('\u200c', ' ')
    value = ''.join(' ' if unicodedata.category(c).startswith('P') else c for c in value)
    return re.sub(r'\s+', ' ', value).strip().casefold()


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True, allow_inf_nan=False)


def safe_product_image(value):
    if not isinstance(value,str) or len(value)>2000:
        return None
    try:
        url=urlsplit(value.strip())
        if (url.scheme!='https' or url.hostname!='image.torob.com' or
                url.port not in (None,443) or url.username or url.password or url.fragment or
                not url.path.startswith('/base/images/')):
            return None
    except ValueError:
        return None
    return value.strip()


class StoreLocation(Strict):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)

    @field_validator('latitude', 'longitude', mode='before')
    @classmethod
    def numeric_coordinate(cls, value):
        if isinstance(value, bool):
            raise ValueError('coordinate must be numeric')
        return value


class Store(Strict):
    id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    source: str = Field(min_length=1, max_length=500)
    demo: bool = False
    address: str | None = Field(default=None, max_length=1000)
    location_label: str | None = Field(default=None, max_length=200)
    location: StoreLocation | None = None

    @field_validator('address', 'location_label', mode='before')
    @classmethod
    def optional_text(cls, value, info):
        # Optional dataset facts must never invalidate an otherwise valid shop.
        if not isinstance(value, str):
            return None
        value = ''.join(c for c in value if c.isspace() or not unicodedata.category(c).startswith('C') or c == '\u200c')
        value = ' '.join(value.split())
        maximum = 1000 if info.field_name == 'address' else 200
        if not value or value.casefold() == 'null' or len(value) > maximum:
            return None
        return value

    @field_validator('location', mode='before')
    @classmethod
    def optional_location(cls, value):
        if value is None:
            return None
        try:
            return StoreLocation.model_validate(value)
        except (ValidationError, TypeError, ValueError):
            return None


class Product(Strict):
    product_id: str | None = Field(default=None, max_length=100)
    id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    category: str = Field(min_length=1, max_length=100)
    source: str = Field(min_length=1, max_length=500)
    store_id: str | None = Field(default=None, max_length=100)
    attributes: dict[str, str] = Field(default_factory=dict, max_length=20)
    price: Decimal | None = Field(default=None, ge=0, le=10**15)
    currency: Literal['TOMAN', 'IRR'] | None = None
    stock: Literal['in_stock', 'out_of_stock', 'unknown'] = 'unknown'
    installments: Literal['yes', 'no', 'unknown'] = 'unknown'
    updated_at: datetime | None = None
    demo: bool = False
    image_url: str | None = None

    @field_validator('image_url',mode='before')
    @classmethod
    def validated_image(cls,value):
        return safe_product_image(value)

    @field_validator('attributes')
    @classmethod
    def attributes_valid(cls, v):
        if any(not k or len(k)>80 or not val or len(val)>200 for k,val in v.items()):
            raise ValueError('invalid attributes')
        return v

    @field_validator('updated_at')
    @classmethod
    def aware(cls, v):
        if v and (v.tzinfo is None or v > datetime.now(timezone.utc)):
            raise ValueError('timestamp must be past and timezone-aware')
        return v


class Intent(Strict):
    query: str = Field(default='', max_length=500)
    category: str | None = Field(default=None, max_length=100)
    max_price: Decimal | None = Field(default=None, ge=0, le=10**15)
    currency: Literal['TOMAN', 'IRR'] | None = None
    installments_only: bool = False
    in_stock_only: bool = False
    attributes: dict[str, str] = Field(default_factory=dict, max_length=20)
    limit: int = Field(default=12, ge=1, le=30)

    @model_validator(mode='after')
    def currency_required(self):
        if self.max_price is not None and self.currency is None:
            raise ValueError('برای سقف قیمت، واحد TOMAN یا IRR را مشخص کنید')
        Product.attributes_valid(self.attributes)
        return self


class Compare(Strict):
    ids: list[str] = Field(min_length=2, max_length=4)
    @field_validator('ids')
    @classmethod
    def distinct(cls, v):
        if len(set(v)) != len(v) or any(len(i)>100 for i in v):
            raise ValueError('distinct valid ids required')
        return v


class Feedback(Strict):
    product_id: str = Field(min_length=1, max_length=100)
    consent: Literal[True]
    text: str = Field(min_length=1, max_length=1000)
    purchased: bool = False
    @field_validator('text')
    @classmethod
    def clean(cls, v):
        v = re.sub(r'<[^>]*>', '', v)
        v = ''.join(c for c in v if c in '\n\t' or not unicodedata.category(c).startswith('C'))
        if not v.strip(): raise ValueError('empty feedback')
        return v.strip()


class Identity(Strict):
    id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)


class CallProduct(Identity):
    attributes: dict[str, str] = Field(default_factory=dict, max_length=20)


class CallRequest(Strict):
    offer_id: str | None = Field(default=None, max_length=100)
    request_id: str = Field(min_length=1, max_length=100)
    store: Identity
    product: CallProduct
    questions: list[Literal['availability', 'price']] = Field(default=['availability','price'], min_length=1, max_length=2)
    language: Literal['fa-IR'] = 'fa-IR'
    @field_validator('questions')
    @classmethod
    def unique(cls,v):
        if len(set(v)) != len(v): raise ValueError('duplicate questions')
        return v


class Segment(Strict):
    item_id: str
    previous_item_id: str | None = None
    response_id: str | None = None
    speaker: Literal['seller','agent']
    text: str | None = None
    complete: bool = False
    audible: bool | None = None
    interrupted: bool = False
    audio_end_ms: int | None = None


class ExtractionUsage(Strict):
    prompt_tokens: int | None = Field(default=None,ge=0,strict=True)
    completion_tokens: int | None = Field(default=None,ge=0,strict=True)
    total_tokens: int | None = Field(default=None,ge=0,strict=True)
    reported_cost: Decimal | None = Field(default=None,ge=0)
    reported_cost_currency: str | None = Field(default=None,max_length=10)


class CallResult(Strict):
    session_id: str
    request_id: str
    store_id: str
    product_id: str
    status: Literal['complete','incomplete','unconfigured']
    reason: Literal['agent_finished','manual_end','timeout','error','disconnected']
    availability: Literal['in_stock','out_of_stock','unknown'] = 'unknown'
    price_amount: Decimal | None = Field(default=None, ge=0, le=10**15)
    currency: Literal['TOMAN','IRR'] | None = None
    raw_text: str | None = None
    clarification_count: int = Field(ge=0, le=2)
    unanswered_questions: list[str]
    transcript: list[Segment]
    transcript_complete: bool
    diagnostics: list[str] = Field(default_factory=list)
    extraction_status: Literal['not_requested','skipped_incomplete','skipped_abnormal','unconfigured','pending','complete','error','invalid'] = 'not_requested'
    extraction_usage: ExtractionUsage = Field(default_factory=ExtractionUsage)
    @field_serializer('price_amount',when_used='json')
    def serialize_amount(self,v):
        return None if v is None else int(v) if v==int(v) else float(v)
    @model_validator(mode='after')
    def coherent(self):
        if (self.price_amount is None) != (self.currency is None):
            raise ValueError('amount and currency must be known together')
        if self.status == 'complete' and not self.transcript_complete:
            raise ValueError('complete requires verified transcript')
        return self
