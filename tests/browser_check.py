"""Offline four-stage chat UI checks. No live model, route, map tile or audio requests.

Start the built app first. TOROB_TEST_BASE_URL defaults to http://127.0.0.1:8000.
The conversation service is a deterministic UI fixture here; backend model and
catalog integration have separate pytest coverage. Screenshots show test data.
"""
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

from browser_chat_fixtures import OfflinePage

ROOT = Path(__file__).resolve().parent.parent


def desktop_checks(browser):
    test = OfflinePage(browser)
    page = test.page
    try:
        test.open_location()
        product = page.locator('[data-testid="product-choice"]').first
        expect(product.locator('img')).to_be_visible()
        expect(product.locator('img')).to_have_js_property('naturalWidth', 1)
        choose = product.get_by_role('button', name='انتخاب این محصول', exact=True)
        expect(choose).to_be_disabled()
        # Even scripted repeated activation must not submit another selection.
        choose.evaluate('button => { button.click(); button.click(); button.click(); }')
        expect(page.locator('[data-testid="location-picker"]')).to_have_count(1)
        assert sum(turn['action'] == 'select_product' for turn in test.turns) == 1
        assert page.locator("html").get_attribute("dir") == "rtl"
        expect(page.locator(".chat-stage-nav li")).to_have_count(4)
        expect(page.locator('.chat-stage-nav [aria-current="step"]')).to_contain_text("فروشگاه")
        assert test.map_config_requests == test.sdk_requests == 0
        picker = page.locator('[data-testid="location-picker"]')
        confirm = picker.get_by_role("button", name="تأیید موقعیت و یافتن فروشگاه‌ها", exact=True)
        expect(confirm).to_be_disabled()
        picker.get_by_role("button", name="نمایش نقشه", exact=True).click()
        expect(picker.locator(".store-map")).to_have_attribute("aria-busy", "false")
        assert test.probe()["markers"] == [], "A viewport must never be treated as the user's pin."
        expect(confirm).to_be_disabled()
        picker.locator("canvas").click(position={"x": 80, "y": 80})
        expect(picker.locator('[data-testid="chosen-location"]')).to_contain_text("35.73333")
        expect(confirm).to_be_disabled()  # Explicit travel mode is still required.
        picker.get_by_role("radio", name="با خودرو", exact=True).click()
        expect(picker.get_by_role("radio", name="با خودرو", exact=True)).to_be_checked()
        confirm.click()
        expect(page.locator('[data-testid="store-offer"]')).to_have_count(3)
        assert test.turns[-1]["location"] == {"latitude": 35.73333, "longitude": 51.43333}
        assert test.turns[-1]["travel_mode"] == "car"
        assert all("location" not in turn for turn in test.turns[:-1])
        cards = page.locator('[data-testid="store-offer"]')
        expect(cards.first).to_contain_text("۳٫۲ کیلومتر")
        expect(cards.first).to_contain_text("۱۰ دقیقه")
        cards.nth(0).get_by_role("checkbox").click()
        cards.nth(1).get_by_role("checkbox").click()
        page.get_by_role("button", name="مقایسهٔ فروشگاه‌های انتخاب‌شده", exact=True).click()
        expect(page.locator('[data-testid="inline-comparison"]')).to_be_visible()
        assert page.locator('[data-testid="inline-comparison"] table tr').count() >= 7
        assert page.locator('[data-slot="dialog-content"]').count() == 0
        page.screenshot(path=str(ROOT / "docs/chat-desktop.png"), full_page=True)

        page.get_by_role("button", name="فعال‌کردن حالت تاریک", exact=True).click()
        expect(page.locator("html")).to_have_class("dark")
        page.get_by_role("button", name="فعال‌کردن حالت روشن", exact=True).click()
        page.locator('[data-testid="inline-comparison"]').get_by_role("button", name="دموی استعلام", exact=True).first.click()
        inquiry = page.locator('[data-testid="inline-inquiry"]')
        expect(inquiry).to_be_visible()
        expect(inquiry).to_contain_text("شما نقش فروشنده")
        expect(inquiry.get_by_role("button", name="شروع دمو با میکروفون", exact=True)).to_be_disabled()
        assert inquiry.locator('input[type="password"]').count() == 0
        assert page.locator('[data-slot="dialog-content"]').count() == 0
        expect(page.locator('.chat-stage-nav [aria-current="step"]')).to_contain_text("استعلام")

        # Existing consent/purchase/deletion behavior is preserved.
        cards.first.locator('.compact-details > summary').click()
        cards.first.get_by_role("button", name="ثبت تجربهٔ بازدید یا خرید", exact=True).click()
        page.locator("#feedback-kind").get_by_role("radio", name="پس از خرید").click()
        page.locator("#feedback-text").fill("بازخورد آفلاین مرورگر")
        page.locator("#consent").click()
        page.locator("#feedback-form").get_by_role("button", name="ثبت بازخورد", exact=True).click()
        expect(page.locator("#feedback-status")).to_contain_text("خرید")
        page.locator("#purchased").click()
        page.locator("#feedback-form").get_by_role("button", name="ثبت بازخورد", exact=True).click()
        expect(page.locator("#delete-feedback")).to_be_visible()
        page.locator("#delete-feedback").click()
        expect(page.locator("#feedback-status")).to_contain_text("حذف")
        page.locator("#feedback").get_by_role("button", name="بستن", exact=True).click()

        # A failed HTTP response retries the exact payload and ID once requested.
        test.fail_once = True
        page.locator("#query").fill("مدل مشابه هم پیشنهاد بده")
        page.locator("#send-message").click()
        expect(page.locator(".chat-error")).to_contain_text("خطای موقت")
        first_attempt = test.turns[-1]
        page.locator(".chat-error").get_by_role("button", name="تلاش دوباره", exact=True).click()
        expect(page.locator(".chat-error")).to_have_count(0)
        assert test.turns[-1] == first_attempt
        page.get_by_role("button", name="گفت‌وگوی تازه", exact=True).click()
        expect(page.locator('[data-testid="store-offer"]')).to_have_count(0)
        expect(page.locator('[data-testid="inline-comparison"]')).to_have_count(0)
        test.assert_safe()
    finally:
        test.close()


def mobile_checks(browser):
    test = OfflinePage(browser, mobile=True)
    try:
        test.open_products()
        page = test.page
        expect(page.locator('[data-testid="product-choice"]')).to_be_visible()
        carousel = page.locator('.chat-carousel[aria-label="محصولات پیشنهادی"]')
        assert carousel.evaluate("element => getComputedStyle(element).overflowX") == "auto"
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.screenshot(path=str(ROOT / "docs/chat-mobile.png"), full_page=True)
        test.assert_safe()
    finally:
        test.close()


def unconfigured_checks(browser):
    test = OfflinePage(browser, chat_configured=False)
    try:
        test.open()
        expect(test.page.locator("#query")).to_be_disabled()
        expect(test.page.get_by_text("دستیار فعلاً در دسترس نیست", exact=True)).to_be_visible()
        assert test.turns == []
        test.assert_safe()
    finally:
        test.close()


def transport_without_maps_checks(browser):
    for mobile in (False, True):
        test = OfflinePage(browser, mobile=mobile, configured=False, routing_configured=False)
        try:
            test.open_location()
            picker = test.page.locator('[data-testid="location-picker"]')
            car = picker.get_by_role('radio', name='با خودرو', exact=True)
            walking = picker.get_by_role('radio', name='پیاده', exact=True)
            expect(car).to_be_enabled()
            expect(walking).to_be_enabled()
            expect(car).not_to_be_checked()
            expect(walking).not_to_be_checked()
            car.click()
            expect(car).to_be_checked()
            expect(car.locator('svg')).not_to_have_class('invisible size-3.5')
            car.click()
            expect(car).to_be_checked()
            walking.click()
            expect(walking).to_be_checked()
            expect(car).not_to_be_checked()
            car.focus()
            car.press('Space')
            expect(car).to_be_checked()
            expect(walking).not_to_be_checked()
            expect(picker.get_by_role('button', name='تأیید موقعیت و یافتن فروشگاه‌ها', exact=True)).to_be_disabled()
            assert test.map_config_requests == test.sdk_requests == 0
            assert len(test.turns) == 2  # Mode selection remains local; no paid/chat requests.
            test.assert_safe()
        finally:
            test.close()


if __name__ == "__main__":
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="chrome", headless=True)
        try:
            desktop_checks(browser)
            mobile_checks(browser)
            unconfigured_checks(browser)
            transport_without_maps_checks(browser)
        finally:
            browser.close()
    print("Offline chat browser checks passed: four stages, product/store carousels, explicit pin/mode, route metrics, inline comparison/inquiry, theme, consent feedback/deletion, exact-ID retry, new conversation, missing model, mobile/no overflow. All provider traffic blocked; live service integration not tested.")
