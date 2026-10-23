"""Functional four-stage shopping flow with real catalog data and fake providers."""
import asyncio
import copy
import json
from datetime import datetime, timedelta, timezone

import pytest

from app import assistant
from app.assistant import AssistantError, AssistantService, TurnRequest
from app.catalog import Catalog
from app.chat_model import ChatModelError, ChatPlan, GroundedReply, plan_turn
from app.models import ExtractionUsage


@pytest.fixture
def offer_catalog(tmp_path):
    now = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    stores = [
        {"id": f"store-{i}", "name": f"فروشگاه {i}", "source": "offline-test", "demo": True,
         "address": f"نشانی ثبت‌شده {i}", "location": {"latitude": 35.6 + i * 0.01, "longitude": 51.3 + i * 0.01}}
        for i in range(1, 5)
    ]
    products = []
    for offer_id, product_id, store_id, capacity, price in [
        ("offer-a", "s24-256", "store-1", "256", 800),
        ("offer-b", "s24-256", "store-2", "256", 900),
        ("offer-expensive", "s24-256", "store-3", "256", 1600),
        ("offer-other", "s24-512", "store-4", "512", 1400),
    ]:
        products.append({"id": offer_id, "product_id": product_id, "name": f"Samsung S24 Ultra {capacity}",
                         "category": "گوشی موبایل", "store_id": store_id, "source": "offline-test", "demo": True,
                         "price": price, "currency": "TOMAN", "stock": "unknown", "installments": "unknown",
                         "updated_at": now, "attributes": {"capacity": capacity}})
    path = tmp_path / "multiple-offers.json"
    path.write_text(json.dumps({"stores": stores, "products": products}, ensure_ascii=False), encoding="utf-8")
    catalog = Catalog(str(path))
    assert not catalog.issues
    return catalog


def search_plan(**filters):
    search = {"query": "s24 ultra", "category": "گوشی موبایل", "brand": None, "max_price": None,
              "currency": None, "installments_only": False, "in_stock_only": False, "attributes": []}
    search.update(filters)
    return ChatPlan(action="search", reply="مدل موردنظر را جستجو می‌کنم.", search=search,
                    product_id=None, offer_ids=[], suggestions=[])


def clarify_plan():
    return ChatPlan(action="clarify", reply="چه ظرفیتی نیاز داری؟", search=None,
                    product_id=None, offer_ids=[], suggestions=["۲۵۶ گیگابایت"])


class Providers:
    def __init__(self):
        self.plans = []
        self.plan_contexts = []
        self.explain_contexts = []
        self.route_calls = []
        self.explain_error = None

    async def planner(self, context):
        self.plan_contexts.append(copy.deepcopy(context))
        result = self.plans.pop(0) if self.plans else search_plan()
        if isinstance(result, Exception):
            raise result
        return result, ExtractionUsage(total_tokens=11)

    async def explainer(self, context, products):
        self.explain_contexts.append(copy.deepcopy(context))
        if self.explain_error:
            raise self.explain_error
        return GroundedReply(reply="نسخه‌های ثبت‌شده را ببین و یکی را انتخاب کن.", recommendations=[
            {"product_id": product["product_id"], "rationale": "با مدل خواسته‌شده تطبیق دارد."} for product in products
        ]), ExtractionUsage(total_tokens=7)

    async def router(self, origin, offers, mode):
        self.route_calls.append({"origin": origin.model_dump(), "ids": [offer["id"] for offer in offers], "mode": mode})
        times = {"offer-a": 900, "offer-b": 120, "offer-expensive": 60, "offer-other": 240}
        return [{**offer, "route": {"status": "ready", "mode": mode, "source": "neshan",
                                    "duration_seconds": times[offer["id"]], "distance_meters": times[offer["id"]] * 5,
                                    "fetched_at": "2026-01-01T00:00:00+00:00"}} for offer in offers]

    def service(self, catalog):
        return AssistantService(catalog, planner=self.planner, explainer=self.explainer,
                                router=self.router, modes=("car",))


async def turn(service, conversation_id, request_id, **body):
    return await service.turn(conversation_id, "owner", TurnRequest(request_id=request_id, **body))


def component(view, kind):
    return next(value for value in view["messages"][-1]["components"] if value["type"] == kind)


def stable_state(view):
    return {key: value for key, value in view.items() if key != "expires_in_seconds"}


async def ready_stores(service, conversation_id):
    await turn(service, conversation_id, "search", message="گوشی موبایل s24 ultra میخوام")
    await turn(service, conversation_id, "select", action="select_product", product_id="s24-256")
    return await turn(service, conversation_id, "pin", action="set_location",
                      location={"latitude": 35.812345, "longitude": 51.912345}, travel_mode="car")


def test_four_stages_same_product_stores_routes_compare_and_browser_inquiry(offer_catalog):
    providers = Providers()
    service = providers.service(offer_catalog)
    conversation_id = service.create("owner")["id"]

    async def scenario():
        products = await turn(service, conversation_id, "search", message="گوشی موبایل s24 ultra میخوام")
        cards = component(products, "products")["items"]
        assert products["stage"] == 1 and {row["product_id"] for row in cards} == {"s24-256", "s24-512"}
        assert len(cards) == 2 and next(row for row in cards if row["product_id"] == "s24-256")["offer_count"] == 3
        assert all(row["recommendation_reason"] for row in cards)
        assert len(providers.plan_contexts) == len(providers.explain_contexts) == 1
        assert providers.route_calls == []

        pin_prompt = await turn(service, conversation_id, "select", action="select_product", product_id="s24-256")
        assert pin_prompt["stage"] == 2 and component(pin_prompt, "location")["center"] is not None
        assert providers.route_calls == []
        stores = await turn(service, conversation_id, "pin", action="set_location",
                            location={"latitude": 35.812345, "longitude": 51.912345}, travel_mode="car")
        offers = component(stores, "stores")["items"]
        assert [row["id"] for row in offers] == ["offer-expensive", "offer-b", "offer-a"]
        assert {row["product_id"] for row in offers} == {"s24-256"}
        assert providers.route_calls[0]["mode"] == "car"
        assert providers.route_calls[0]["origin"] == {"latitude": 35.812345, "longitude": 51.912345}

        comparison = await turn(service, conversation_id, "compare", action="compare", offer_ids=["offer-a", "offer-b"])
        table = component(comparison, "comparison")
        assert comparison["stage"] == 3 and [row["id"] for row in table["items"]] == ["offer-a", "offer-b"]
        assert table["price_comparable"] is True and all("route" in row for row in table["items"])
        inquiry = await turn(service, conversation_id, "inquire", action="inquiry", offer_ids=["offer-b"])
        assert inquiry["stage"] == 4 and component(inquiry, "inquiry")["items"][0]["id"] == "offer-b"
        assert "دموی مرورگری" in inquiry["messages"][-1]["text"]
        assert "تماس تلفنی واقعی برقرار نمی‌شود" in inquiry["messages"][-1]["text"]
        # Native clicks route once and never consume chat-model tokens or start a call.
        assert len(providers.plan_contexts) == len(providers.explain_contexts) == 1
        assert len(providers.route_calls) == 1 and len(inquiry["usage"]) == 2

    asyncio.run(scenario())


def test_budget_remains_mandatory_after_product_selection(offer_catalog):
    providers = Providers()
    providers.plans = [search_plan(max_price=1000, currency="TOMAN")]
    service = providers.service(offer_catalog)
    conversation_id = service.create("owner")["id"]
    view = asyncio.run(ready_stores(service, conversation_id))
    assert [row["id"] for row in component(view, "stores")["items"]] == ["offer-b", "offer-a"]
    assert set(providers.route_calls[0]["ids"]) == {"offer-a", "offer-b"}
    assert "offer-expensive" not in json.dumps(providers.route_calls)


def test_repeated_product_selection_keeps_one_picker_and_does_not_repeat_routes(offer_catalog):
    providers = Providers()
    service = providers.service(offer_catalog)
    conversation_id = service.create("owner")["id"]

    async def scenario():
        await turn(service, conversation_id, "search", message="s24 ultra")
        selected = await turn(service, conversation_id, "select", action="select_product", product_id="s24-256")
        repeats = await asyncio.gather(*[
            turn(service, conversation_id, f"repeat-{index}", action="select_product", product_id="s24-256")
            for index in range(3)
        ])
        assert all(stable_state(view) == stable_state(selected) for view in repeats)
        assert sum(c["type"] == "location" for m in repeats[-1]["messages"] for c in m["components"]) == 1
        stores = await turn(service, conversation_id, "pin", action="set_location",
            location={"latitude": 35.812345, "longitude": 51.912345}, travel_mode="car")
        duplicate = await turn(service, conversation_id, "repeat-after-pin", action="select_product", product_id="s24-256")
        assert stable_state(duplicate) == stable_state(stores)
        assert len(providers.route_calls) == 1
        comparison = await turn(service, conversation_id, "compare", action="compare", offer_ids=["offer-a", "offer-b"])
        duplicate = await turn(service, conversation_id, "repeat-after-compare", action="select_product", product_id="s24-256")
        assert stable_state(duplicate) == stable_state(comparison)
        assert len(providers.plan_contexts) == len(providers.explain_contexts) == 1

    asyncio.run(scenario())


def test_product_change_invalidates_old_store_actions(offer_catalog):
    providers = Providers()
    service = providers.service(offer_catalog)
    conversation_id = service.create("owner")["id"]

    async def scenario():
        await ready_stores(service, conversation_id)
        changed = await turn(service, conversation_id, "other", action="select_product", product_id="s24-512")
        assert changed["selected_product_id"] == "s24-512"
        assert [row["id"] for row in component(changed, "stores")["items"]] == ["offer-other"]
        with pytest.raises(AssistantError) as error:
            await turn(service, conversation_id, "stale-inquiry", action="inquiry", offer_ids=["offer-a"])
        assert error.value.status == 422
    asyncio.run(scenario())


def test_unseen_product_and_offer_ids_rejected_without_cost(offer_catalog):
    providers = Providers()
    service = providers.service(offer_catalog)
    conversation_id = service.create("owner")["id"]

    async def scenario():
        for payload in [
            {"action": "select_product", "product_id": "s24-256"},
            {"action": "inquiry", "offer_ids": ["offer-a"]},
            {"action": "compare", "offer_ids": ["offer-a", "offer-b"]},
        ]:
            with pytest.raises(AssistantError) as error:
                await turn(service, conversation_id, "forged", **payload)
            assert error.value.status == 422
        assert providers.plan_contexts == providers.route_calls == []
        assert service.sessions[conversation_id].requests == {}
    asyncio.run(scenario())


def test_location_reaches_only_router_and_not_later_model_context(offer_catalog):
    providers = Providers()
    providers.plans = [search_plan(), clarify_plan(), search_plan()]
    service = providers.service(offer_catalog)
    conversation_id = service.create("owner")["id"]

    async def scenario():
        await ready_stores(service, conversation_id)
        await turn(service, conversation_id, "question", message="تفاوت این ظرفیت‌ها چیست؟")
        await turn(service, conversation_id, "newsearch", message="همین مدل را دوباره نشان بده")
    asyncio.run(scenario())
    contexts = json.dumps([providers.plan_contexts, providers.explain_contexts], ensure_ascii=False)
    assert "35.812345" not in contexts and "51.912345" not in contexts
    assert "latitude" not in contexts and "longitude" not in contexts
    assert providers.plan_contexts[1]["has_confirmed_location"] is True
    assert len(providers.route_calls) == 1


def test_duplicate_request_and_reused_id_do_not_repeat_cost(offer_catalog):
    providers = Providers()
    service = providers.service(offer_catalog)
    conversation_id = service.create("owner")["id"]

    async def scenario():
        first = await turn(service, conversation_id, "search", message="گوشی موبایل s24 ultra میخوام")
        second = await turn(service, conversation_id, "search", message="گوشی موبایل s24 ultra میخوام")
        assert stable_state(first) == stable_state(second) and len(providers.plan_contexts) == len(providers.explain_contexts) == 1
        await turn(service, conversation_id, "select", action="select_product", product_id="s24-256")
        pin = {"action": "set_location", "location": {"latitude": 35.812345, "longitude": 51.912345}, "travel_mode": "car"}
        first_pin = await turn(service, conversation_id, "pin", **pin)
        second_pin = await turn(service, conversation_id, "pin", **pin)
        assert stable_state(first_pin) == stable_state(second_pin) and len(providers.route_calls) == 1
        with pytest.raises(AssistantError) as error:
            await turn(service, conversation_id, "search", message="پیام متفاوت")
        assert error.value.status == 409 and len(providers.plan_contexts) == 1
    asyncio.run(scenario())


def test_concurrent_duplicate_waits_and_uses_one_model_attempt(offer_catalog):
    providers = Providers()

    async def scenario():
        started, release = asyncio.Event(), asyncio.Event()
        attempts = []
        async def slow_planner(context):
            attempts.append(context)
            started.set()
            await release.wait()
            return clarify_plan(), ExtractionUsage(total_tokens=3)
        service = AssistantService(offer_catalog, planner=slow_planner, explainer=providers.explainer,
                                   router=providers.router, modes=("car",))
        conversation_id = service.create("owner")["id"]
        one = asyncio.create_task(turn(service, conversation_id, "same", message="سلام"))
        await started.wait()
        two = asyncio.create_task(turn(service, conversation_id, "same", message="سلام"))
        await asyncio.sleep(0)
        release.set()
        first, second = await asyncio.gather(one, two)
        assert stable_state(first) == stable_state(second) and len(attempts) == 1 and len(first["usage"]) == 1
        assert len(first["messages"]) == 3
    asyncio.run(scenario())


@pytest.mark.parametrize("phase", ["plan", "explain"])
@pytest.mark.parametrize("code", ["invalid", "request_failed"])
def test_provider_failure_preserves_usage_and_has_no_fake_fallback(offer_catalog, phase, code):
    providers = Providers()
    failure = ChatModelError(code, ExtractionUsage(total_tokens=23, reported_cost="0.0002"))
    if phase == "plan":
        providers.plans = [failure]
    else:
        providers.explain_error = failure
    service = providers.service(offer_catalog)
    conversation_id = service.create("owner")["id"]
    view = asyncio.run(turn(service, conversation_id, "bad", message="گوشی s24 ultra میخوام"))
    assert view["messages"][-1]["role"] == "assistant" and view["messages"][-1]["components"] == []
    assert "دریافت پاسخ انجام نشد" in view["messages"][-1]["text"]
    assert view["usage"][-1]["kind"] == "error" and view["usage"][-1]["total_tokens"] == 23
    assert view["usage"][-1]["reported_cost"] == "0.0002"
    assert providers.route_calls == []
    duplicate = asyncio.run(turn(service, conversation_id, "bad", message="گوشی s24 ultra میخوام"))
    assert stable_state(duplicate) == stable_state(view) and len(providers.plan_contexts) == 1


def test_missing_chat_model_is_honest_and_does_not_run_deterministic_search(offer_catalog, monkeypatch):
    monkeypatch.delenv("BOXAPI_CHAT_MODEL", raising=False)
    providers = Providers()
    service = AssistantService(offer_catalog, planner=plan_turn, explainer=providers.explainer,
                               router=providers.router, modes=("car",))
    conversation_id = service.create("owner")["id"]
    view = asyncio.run(turn(service, conversation_id, "missing", message="گوشی s24 ultra میخوام"))
    assert "دستیار خرید فعلاً در دسترس نیست" in view["messages"][-1]["text"]
    assert view["messages"][-1]["components"] == [] and not service.sessions[conversation_id].products
    assert providers.explain_contexts == providers.route_calls == []


def test_invalid_planner_filter_does_not_escape_as_server_exception(offer_catalog):
    providers = Providers()
    providers.plans = [search_plan(category="x" * 101)]
    service = providers.service(offer_catalog)
    conversation_id = service.create("owner")["id"]
    view = asyncio.run(turn(service, conversation_id, "longcategory", message="مدل خاص می‌خواهم"))
    assert view["messages"][-1]["components"] == [] and "مشخصات جست‌وجو روشن نیست" in view["messages"][-1]["text"]
    assert providers.explain_contexts == providers.route_calls == []


def test_turn_limit_ownership_expiry_and_deletion(offer_catalog, monkeypatch):
    providers = Providers()
    providers.plans = [clarify_plan(), clarify_plan()]
    service = providers.service(offer_catalog)
    conversation_id = service.create("owner")["id"]
    with pytest.raises(AssistantError) as error:
        service.owned(conversation_id, "other-owner")
    assert error.value.status == 404
    monkeypatch.setattr(assistant, "MAX_TURNS", 2)

    async def scenario():
        await turn(service, conversation_id, "1", message="سلام")
        await turn(service, conversation_id, "2", message="گوشی")
        with pytest.raises(AssistantError) as error:
            await turn(service, conversation_id, "3", message="ظرفیت")
        assert error.value.status == 429
    asyncio.run(scenario())
    assert len(providers.plan_contexts) == 2
    service.sessions[conversation_id].created -= assistant.TTL + 1
    with pytest.raises(AssistantError) as error:
        service.owned(conversation_id, "owner")
    assert error.value.status == 404 and conversation_id not in service.sessions
    next_id = service.create("owner")["id"]
    assert service.delete(next_id, "owner") == {"deleted": True}
    with pytest.raises(AssistantError):
        service.owned(next_id, "owner")


def test_followup_cannot_silently_drop_filters_after_old_messages_leave_context(offer_catalog):
    providers = Providers()
    providers.plans = [
        search_plan(max_price=1000, currency="TOMAN", attributes=[{"key": "capacity", "value": "256"}]),
        search_plan(query="s24", category=None),
    ]
    service = providers.service(offer_catalog)
    conversation_id = service.create("owner")["id"]

    async def scenario():
        initial = await turn(service, conversation_id, "budget", message="گوشی s24 ultra ظرفیت 256 تا 1000 تومان می‌خواهم")
        assert {row["product_id"] for row in component(initial, "products")["items"]} == {"s24-256"}
        session = service.sessions[conversation_id]
        # Simulate a long existing conversation whose original constraints are no
        # longer included in the bounded message-history window.
        for _ in range(14):
            service._append(session, "assistant", "هنوز در حال انتخاب هستیم.")
        pending = await turn(service, conversation_id, "relax", message="گزینه‌های دیگری هم هست؟")
        context = providers.plan_contexts[-1]
        assert not any("1000" in message["text"] for message in context["history"])
        assert str(context["current_search"]["max_price"]) == "1000"
        assert context["current_search"]["category"] == "گوشی موبایل"
        assert context["current_search"]["attributes"] == {"capacity": "256"}
        assert component(pending, "suggestions")["items"] == ["بله، شرایط جدید را تأیید می‌کنم", "شرایط قبلی حفظ شود"]
        assert len(providers.explain_contexts) == 1 and session.search_intent.max_price == 1000
        assert session.search_intent.attributes == {"capacity": "256"}

        confirmed = await turn(service, conversation_id, "confirm", message="بله، شرایط جدید را تأیید می‌کنم")
        assert {row["product_id"] for row in component(confirmed, "products")["items"]} == {"s24-256", "s24-512"}
        assert len(providers.plan_contexts) == 2 and len(providers.explain_contexts) == 2
        assert session.search_intent.max_price is None and session.pending_search is None
    asyncio.run(scenario())


def test_tighter_budget_is_applied_without_relaxation_confirmation(offer_catalog):
    providers = Providers()
    providers.plans = [search_plan(max_price=1000, currency="TOMAN"), search_plan(max_price=850, currency="TOMAN")]
    service = providers.service(offer_catalog)
    conversation_id = service.create("owner")["id"]

    async def scenario():
        await turn(service, conversation_id, "original", message="s24 ultra زیر 1000 تومان")
        tighter = await turn(service, conversation_id, "tighter", message="بودجه‌ام 850 تومان است")
        assert component(tighter, "products")["items"][0]["product_id"] == "s24-256"
        assert len(providers.explain_contexts) == 2
        assert service.sessions[conversation_id].search_intent.max_price == 850
        assert service.sessions[conversation_id].pending_search is None
    asyncio.run(scenario())
