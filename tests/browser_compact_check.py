"""Compact UI measurements and screenshots; all external requests are mocked."""
from pathlib import Path
from playwright.sync_api import expect, sync_playwright
from browser_chat_fixtures import OfflinePage

ROOT = Path(__file__).resolve().parent.parent


def check(browser, width, dark=False):
    test = OfflinePage(browser, mobile=width < 761)
    page = test.page
    page.set_viewport_size({'width': width, 'height': 960 if width > 760 else 844})
    try:
        test.open_products()
        if dark:
            page.get_by_role('button', name='فعال‌کردن حالت تاریک', exact=True).click()
        product = page.locator('[data-testid="product-choice"]')
        image = product.locator('.chat-product-placeholder')
        expected_image = 96 if width > 760 else 80
        assert image.bounding_box()['width'] == expected_image
        assert image.bounding_box()['height'] == expected_image
        assert page.locator('.chat-main').bounding_box()['width'] <= 760
        assert product.bounding_box()['width'] <= 340
        product.locator('.compact-details > summary').click()
        expect(product.locator('.compact-details-body')).to_be_visible()
        product.locator('.compact-details > summary').press('Enter')
        expect(product.locator('.compact-details-body')).to_be_hidden()

        # Uses only UI fixtures; no location, routing or chat model request.
        page.get_by_role('button', name='انتخاب این محصول', exact=True).click()
        test.append('assistant', 'فروشگاه‌های آزمایشی', [{'type':'stores', 'items':__import__('browser_chat_fixtures').OFFERS}])
        page.locator('#query').fill('نمایش فروشگاه‌ها')
        page.locator('#send-message').click()
        cards = page.locator('[data-testid="store-offer"]')
        expect(cards).to_have_count(3)
        card = cards.first
        assert card.bounding_box()['width'] <= 640
        assert card.locator('.chat-offer-card').bounding_box()['height'] < (660 if width < 761 else 420)
        expect(card.locator('.chat-offer-card > .store-location-embedded')).to_have_count(1)
        expected_map = 160 if width > 760 else 140
        assert card.locator('.compact-map-preview').bounding_box()['height'] == expected_map
        card.get_by_role('button', name='مسیریابی', exact=True).click()
        expect(card.locator('.store-map')).to_have_attribute('aria-busy', 'false')
        assert card.locator('.store-map').bounding_box()['height'] == expected_map
        maps_before = len(test.probe()['maps'])
        card.get_by_role('button', name='نقشه کامل', exact=True).click()
        assert card.locator('.store-map').bounding_box()['height'] > expected_map
        assert len(test.probe()['maps']) == maps_before, 'Expanding must preserve the map instance.'
        card.get_by_role('button', name='نقشه کوچک', exact=True).click()
        assert card.locator('.store-map').bounding_box()['height'] == expected_map
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        assert page.locator('.chat-topbar').bounding_box()['height'] <= (66 if width > 760 else 58)
        assert page.locator('.chat-composer').bounding_box()['height'] >= 48
        assert page.locator('.chat-composer').bounding_box()['y'] < page.viewport_size['height']
        if width in (390, 1440):
            card.scroll_into_view_if_needed()
            page.screenshot(path=str(ROOT / f'docs/compact-{width}{"-dark" if dark else ""}.png'), full_page=True)
        test.assert_safe()
        print(f'Compact layout passed: {width}px, dark={dark}, card height={card.locator(".chat-offer-card").bounding_box()["height"]}')
    finally:
        test.close()


if __name__ == '__main__':
    with sync_playwright() as p:
        browser = p.chromium.launch(channel='chrome', headless=True)
        try:
            for width in (320, 390, 768, 1440):
                check(browser, width)
            check(browser, 390, dark=True)
            check(browser, 1440, dark=True)
        finally:
            browser.close()
