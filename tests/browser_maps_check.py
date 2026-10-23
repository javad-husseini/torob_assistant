"""Offline lazy Neshan Leaflet regressions for maps inside the shopping chat.

TOROB_TEST_BASE_URL defaults to http://127.0.0.1:8000. The SDK and conversation
service are doubles; no credentials, provider requests, or real tiles are used.
"""
import re
from playwright.sync_api import expect, sync_playwright
from browser_chat_fixtures import OFFERS, PUBLIC_TEST_KEY, OfflinePage

MAP_BUTTON = re.compile(r"^نمایش (?:نقشه|موقعیت)$")


def desktop_checks(browser):
    test = OfflinePage(browser)
    try:
        test.open_stores()
        cards = test.page.locator(".store-location-card")
        pairs = test.page.locator('[data-testid="store-offer"]')
        expect(pairs).to_have_count(3)
        offer_box = pairs.first.locator(".chat-offer-card").bounding_box()
        location_box = cards.first.bounding_box()
        assert offer_box and location_box
        assert offer_box["y"] <= location_box["y"]
        assert location_box["y"] + location_box["height"] <= offer_box["y"] + offer_box["height"] + 2
        expect(pairs.first.locator('.chat-offer-card .store-location-embedded')).to_have_count(1)
        expect(cards.nth(0)).to_contain_text(OFFERS[0]["store"]["address"])
        expect(cards.nth(1)).to_contain_text(OFFERS[1]["store"]["address"])
        assert test.map_config_requests == test.sdk_requests == 0
        cards.first.get_by_role("button", name="نمایش نقشه", exact=True).click()
        expect(cards.first.locator(".store-map")).to_have_attribute("aria-busy", "false")
        probe = test.probe()
        assert probe["maps"][0]["center"] == [35.7123, 51.4123]
        assert probe["maps"][0]["key"] == PUBLIC_TEST_KEY
        assert probe["markers"][0] == [35.7123, 51.4123]
        assert test.map_config_requests == test.sdk_requests == 1
        cards.nth(1).get_by_role("button", name="نمایش نقشه", exact=True).click()
        test.page.wait_for_function("window.__mapProbe.markers.length === 2")
        assert test.probe()["markers"][1] == [32.6543, 51.6789]
        assert test.map_config_requests == test.sdk_requests == 1
        expect(cards.nth(2).get_by_role("button", name=MAP_BUTTON)).to_be_disabled()
        test.page.get_by_role("button", name="گفت‌وگوی تازه", exact=True).click()
        expect(test.page.locator(".store-map")).to_have_count(0)
        test.page.wait_for_function("window.__mapProbe.removedMaps === 2")
        assert test.probe()["removedMarkers"] == 2
        test.assert_safe()
    finally:
        test.close()


def mobile_checks(browser):
    test = OfflinePage(browser, mobile=True)
    try:
        test.open_stores()
        card = test.page.locator(".store-location-card").first
        assert test.map_config_requests == test.sdk_requests == 0
        card.get_by_role("button", name="نمایش موقعیت", exact=True).click()
        expect(card.locator(".store-map")).to_have_attribute("aria-busy", "false")
        assert test.probe()["markers"][0] == [35.7123, 51.4123]
        card.get_by_role("button", name="بستن موقعیت", exact=True).click()
        expect(card.locator(".store-map")).to_have_count(0)
        test.page.wait_for_function("window.__mapProbe.removedMaps === 1")
        card.get_by_role("button", name="نمایش موقعیت", exact=True).click()
        test.page.wait_for_function("window.__mapProbe.markers.length === 2")
        assert test.map_config_requests == test.sdk_requests == 1
        test.assert_safe()
    finally:
        test.close()


def unconfigured_checks(browser):
    test = OfflinePage(browser, configured=False)
    try:
        test.open_stores()
        cards = test.page.locator(".store-location-card")
        expect(cards.first).to_contain_text(OFFERS[0]["store"]["address"])
        for index in range(cards.count()):
            expect(cards.nth(index).get_by_role("button", name=MAP_BUTTON)).to_be_disabled()
        assert test.map_config_requests == test.sdk_requests == 0
        test.assert_safe()
    finally:
        test.close()


def tile_failure_checks(browser):
    test = OfflinePage(browser, tile_failure=True)
    try:
        test.open_stores()
        card = test.page.locator(".store-location-card").first
        card.get_by_role("button", name="نمایش نقشه", exact=True).click()
        expect(card).to_contain_text("نقشه بارگذاری نشد. دوباره تلاش کنید.")
        expect(card.locator(".store-map")).to_be_hidden()
        assert PUBLIC_TEST_KEY not in card.inner_text()
        test.page.wait_for_function("window.__mapProbe.removedMaps === 1")
        test.page.evaluate("window.__mapProbe.failTiles = false")
        card.get_by_role("button", name="تلاش دوباره", exact=True).click()
        test.page.wait_for_function("window.__mapProbe.markers.length === 2")
        expect(card.locator(".store-map")).to_have_attribute("aria-busy", "false")
        assert test.map_config_requests == test.sdk_requests == 1
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
            tile_failure_checks(browser)
        finally:
            browser.close()
    print("Offline chat map checks passed: addresses/offer association, click-only SDK/key, coordinate order, independent markers, cleanup, mobile, missing map config/coordinates, tile failure/retry. All provider traffic blocked; real Neshan tiles not tested.")
