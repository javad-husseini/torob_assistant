"""Actual pinned Leaflet SDK, fake key and locally fulfilled map responses.

No provider request leaves the browser. Covers SDK access failure separately
from tile errors; a successful placeholder tile must not hide access failure.
"""
import base64
from urllib.parse import parse_qs, urlsplit

from playwright.sync_api import expect, sync_playwright

from browser_chat_fixtures import BASE_PARTS, OfflinePage, PUBLIC_TEST_KEY, SDK_URL

PNG = base64.b64decode(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/lZkAAAAASUVORK5CYII='
)
BASE_TILE_HOSTS = {f'tile{number}.neshan.org' for number in range(1, 5)}
LABEL_TILE_HOSTS = {f'tile{number}.neshan.org' for number in range(5, 9)}


class RealSDKPage(OfflinePage):
    def __init__(self, browser, *, access_status=204, tile_scenario='all_png'):
        self.access_status = access_status
        self.tile_scenario = tile_scenario
        self.base_tile_requests = 0
        self.empty_tile_roles = []
        self.successful_tile_roles = []
        self.mocked_provider_requests = []
        self.quota_contract_errors = []
        super().__init__(browser)

    def route(self, route):
        url = urlsplit(route.request.url)
        local = (url.scheme, url.hostname, url.port) == (
            BASE_PARTS.scheme, BASE_PARTS.hostname, BASE_PARTS.port)
        if local and SDK_URL.search(route.request.url):
            self.sdk_requests += 1
            route.continue_()  # Real SDK chunk served locally by our own app.
            return
        if url.scheme == 'https' and url.hostname and url.hostname.endswith('.neshan.org'):
            # Keep credentials/query values out of captured request metadata.
            self.mocked_provider_requests.append((route.request.method, url.hostname, url.path))
            if url.hostname == 'api.neshan.org' and url.path == '/v1/quota':
                query = parse_qs(url.query, keep_blank_values=True)
                if route.request.method != 'PUT':
                    self.quota_contract_errors.append('Access check must use PUT, not GET.')
                if set(query) != {'t'} or len(query['t']) != 1 or not query['t'][0].isdigit():
                    self.quota_contract_errors.append('Access check must include only its timestamp query.')
                if route.request.headers.get('api-key') != PUBLIC_TEST_KEY:
                    self.quota_contract_errors.append('Access check must use the public fixture key.')
                if route.request.post_data not in (None, ''):
                    self.quota_contract_errors.append('Access check must have an empty body.')
                route.fulfill(
                    status=self.access_status, content_type='application/json',
                    headers={'Access-Control-Allow-Origin': '*'},
                    body='' if self.access_status == 204 else
                    '{"status":404,"error":"Not Found","path":"/v1/quota"}')
            elif route.request.resource_type == 'image':
                role = ('base' if url.hostname in BASE_TILE_HOSTS else
                        'label' if url.hostname in LABEL_TILE_HOSTS else None)
                if role == 'base':
                    self.base_tile_requests += 1
                empty = (
                    self.tile_scenario == 'empty_labels' and role == 'label' or
                    self.tile_scenario == 'empty_base' and role == 'base' or
                    self.tile_scenario == 'mixed_base' and role == 'base' and self.base_tile_requests == 1
                )
                if empty:
                    self.empty_tile_roles.append(role)
                    # An empty HTTP 204 is not a decodable map image. Leaflet
                    # emits tileerror, then layer load even if every tile failed.
                    route.fulfill(status=204, body='')
                else:
                    if role:
                        self.successful_tile_roles.append(role)
                    route.fulfill(status=200, content_type='image/png', body=PNG)
            else:
                self.external_requests.append(url.hostname + url.path)
                route.abort()
            return
        super().route(route)

    def assert_safe(self):
        # The SDK's simulated HTTP failure is expected; JS/CSP errors are not.
        unexpected = [e for e in self.errors if not (
            self.access_status == 404 and '404 (Not Found)' in e)]
        assert not unexpected, unexpected
        assert not self.quota_contract_errors, self.quota_contract_errors
        assert ('PUT', 'api.neshan.org', '/v1/quota') in self.mocked_provider_requests
        assert not self.external_requests, self.external_requests
        assert not self.call_requests, self.call_requests
        if self.tile_scenario == 'empty_labels':
            assert 'label' in self.empty_tile_roles
            assert 'base' in self.successful_tile_roles
        elif self.tile_scenario == 'empty_base':
            assert 'base' in self.empty_tile_roles
            assert 'base' not in self.successful_tile_roles
            assert 'label' in self.successful_tile_roles
        elif self.tile_scenario == 'mixed_base':
            assert self.empty_tile_roles.count('base') == 1
            assert 'base' in self.successful_tile_roles


def check_pin_map(browser, access_status, tile_scenario='all_png'):
    test = RealSDKPage(browser, access_status=access_status, tile_scenario=tile_scenario)
    try:
        test.open_location()
        assert not test.mocked_provider_requests
        picker = test.page.locator('[data-testid="location-picker"]')
        picker.get_by_role('button', name='نمایش نقشه', exact=True).click()
        surface = picker.locator('.store-map')
        if access_status == 204 and tile_scenario != 'empty_base':
            expect(surface).to_have_attribute('aria-busy', 'false')
            expect(picker.locator('.leaflet-tile-loaded').first).to_be_visible()
            surface.click(position={'x': 140, 'y': 110})
            expect(picker.locator('[data-testid="chosen-location"]')).to_be_visible()
            expect(picker.locator('.store-map-marker')).to_have_count(1)
            picker.get_by_role('radio', name='با خودرو', exact=True).click()
            expect(picker.get_by_role('button', name='تأیید موقعیت و یافتن فروشگاه‌ها', exact=True)).to_be_enabled()
        else:
            expect(picker.locator('.store-map-message')).to_contain_text('نقشه بارگذاری نشد')
            expect(surface).to_be_hidden()
            expect(picker.locator('[data-testid="chosen-location"]')).to_have_count(0)
            expect(picker.locator('.leaflet-pane')).to_have_count(0)
        test.assert_safe()
    finally:
        test.close()


def check_store_map(browser, access_status, tile_scenario='all_png'):
    test = RealSDKPage(browser, access_status=access_status, tile_scenario=tile_scenario)
    try:
        test.open_stores()
        card = test.page.locator('[data-testid="store-location-card"]').first
        card.get_by_role('button', name='نمایش نقشه', exact=True).click()
        if access_status == 204 and tile_scenario != 'empty_base':
            expect(card.locator('.store-map')).to_have_attribute('aria-busy', 'false')
            expect(card.locator('.store-map-marker')).to_have_count(1)
        else:
            expect(card.locator('.store-map-message')).to_contain_text('نقشه بارگذاری نشد')
            expect(card.locator('.store-map')).to_be_hidden()
            expect(card.locator('.leaflet-pane')).to_have_count(0)
        test.assert_safe()
    finally:
        test.close()


if __name__ == '__main__':
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel='chrome', headless=True)
        try:
            for status in (204, 404):
                check_pin_map(browser, status)
                check_store_map(browser, status)
            for scenario in ('empty_labels', 'empty_base', 'mixed_base'):
                check_pin_map(browser, 204, scenario)
                check_store_map(browser, 204, scenario)
        finally:
            browser.close()
    print('Real Leaflet SDK checks passed: PUT access contract, pin/store maps, pin selection, '
          'empty optional labels, failed base tiles, mixed base tiles, access-failure cleanup. '
          'Fake key and local responses only; no live provider traffic.')
