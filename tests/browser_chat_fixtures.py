"""Deterministic UI fixtures. Every external request and provider API is blocked."""
import copy
import base64
import json
import os
import re
from urllib.parse import urlsplit

from playwright.sync_api import expect

BASE_URL = os.getenv("TOROB_TEST_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
BASE_PARTS = urlsplit(BASE_URL)
SDK_URL = re.compile(r"/static/ui/assets/(?:leaflet|neshan-leaflet)[^/]*\.js(?:\?.*)?$")
PUBLIC_TEST_KEY = "public-browser-test-key-not-a-real-credential"


def offer(identifier, store_name, address, location):
    return {
        "id": identifier, "product_id": "product-s24", "name": "Samsung Galaxy S24 Ultra 256GB (تست آفلاین)",
        "category": "گوشی موبایل", "attributes": {"حافظه": "256GB"}, "price": None,
        "currency": "TOMAN", "stock": "unknown", "installments": "unknown",
        "store": {"id": "store-" + identifier, "name": store_name, "address": address,
                  "location_label": None, "location": location},
        "call_eligible": True, "updated_at": None, "why": "دادهٔ آزمایشی تست آفلاین", "demo": True,
        "offer_count": 3,
        "route": {"status": "ready" if location else "missing_location", "distance_meters": 3200 if location else None,
                  "duration_seconds": 600 if location else None, "mode": "car", "source": "neshan"},
    }


OFFERS = [
    offer("offer-a", "فروشگاه تست تهران", "تهران، خیابان آزمایشی، پلاک ۱", {"latitude": 35.7123, "longitude": 51.4123}),
    offer("offer-b", "فروشگاه تست اصفهان", "اصفهان، خیابان نمونه، پلاک ۲", {"latitude": 32.6543, "longitude": 51.6789}),
    offer("offer-c", "فروشگاه بدون مختصات", None, None),
]
PRODUCTS = [copy.deepcopy(OFFERS[0])]
PRODUCTS[0]['image_url'] = 'https://image.torob.com/base/images/offline-test.png'
SDK_DOUBLE = r"""
const probe = window.__mapProbe;
class Map {
  constructor(container, options) {
    this.container = container; this.listeners = {}; this.removed = false;
    this.canvas = document.createElement('canvas'); this.canvas.style.width = '100%';
    this.canvas.style.height = '100%'; this.canvas.style.background = '#eef1ec';
    this.container.appendChild(this.canvas);
    probe.maps.push({center: options.center, zoom: options.zoom, key: options.key || null});
    this.click = () => (this.listeners.click || []).forEach(fn => fn({latlng: {lat: 35.73333, lng: 51.43333}}));
    this.canvas.addEventListener('click', this.click);
    this.layer = {options: {zIndex: -9999}, getTileUrl() { return ''; }, on(event, listener) {
      if ((event === 'tileload' && !probe.failTiles) || (event === 'tileerror' && probe.failTiles) || event === 'load')
        setTimeout(() => listener(), 0);
      return this;
    }, off() { return this; }};
  }
  on(event, fn) { (this.listeners[event] ||= []).push(fn); return this; }
  off(event, fn) { this.listeners[event] = (this.listeners[event] || []).filter(x => x !== fn); return this; }
  eachLayer(fn) { fn(this.layer); return this; }
  invalidateSize() { return this; }
  remove() { if (!this.removed) { this.removed = true; probe.removedMaps++; } this.canvas.removeEventListener('click', this.click); this.canvas.remove(); }
}
class Marker {
  constructor(coordinates) { this.coordinates = coordinates; }
  addTo(map) { this.index = probe.markers.length; probe.markers.push(this.coordinates); this.element = document.createElement('span'); this.element.className = 'offline-test-store-marker'; map.container.appendChild(this.element); return this; }
  setLatLng(coordinates) { this.coordinates = coordinates; if (this.index != null) probe.markers[this.index] = coordinates; return this; }
  remove() { this.element?.remove(); probe.removedMarkers++; return this; }
}
const marker = coordinates => new Marker(coordinates);
const divIcon = options => options;
export {Map, marker, divIcon};
export default {Map, marker, divIcon};
"""


class OfflinePage:
    def __init__(self, browser, *, mobile=False, configured=True, tile_failure=False, chat_configured=True, routing_configured=True):
        self.context = browser.new_context(viewport={"width": 390 if mobile else 1440, "height": 844 if mobile else 1050}, locale="fa-IR", service_workers="block")
        self.page = self.context.new_page()
        self.errors = []
        self.external_requests = []
        self.call_requests = []
        self.map_config_requests = 0
        self.sdk_requests = 0
        self.turns = []
        self.mode = None
        self.configured = configured
        self.chat_configured = chat_configured
        self.routing_configured = routing_configured
        self.fail_once = False
        self.conversation_number = 0
        self.view = None
        self.page.on("pageerror", lambda error: self.errors.append(str(error)))
        self.page.on("console", lambda message: self.errors.append(message.text) if message.type == "error" and "503" not in message.text else None)
        self.page.add_init_script("window.__mapProbe = {maps: [], markers: [], removedMaps: 0, removedMarkers: 0, failTiles: " + str(tile_failure).lower() + "};")
        self.context.route("**/*", self.route)

    @staticmethod
    def respond(route, data, status=200):
        route.fulfill(status=status, content_type="application/json", body=json.dumps(data))

    def append(self, role, text, components=None):
        self.view["messages"].append({"id": str(len(self.view["messages"])), "role": role, "text": text, "components": components or []})

    def route(self, route):
        url = urlsplit(route.request.url)
        if route.request.url == PRODUCTS[0]['image_url']:
            # A local PNG fixture: no CDN or other external network request.
            route.fulfill(status=200, content_type='image/png', body=base64.b64decode(
                'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/lZkAAAAASUVORK5CYII='))
            return
        if url.scheme not in ("http", "https"):
            route.continue_(); return
        if (url.scheme, url.hostname, url.port) != (BASE_PARTS.scheme, BASE_PARTS.hostname, BASE_PARTS.port):
            self.external_requests.append(route.request.url); route.abort(); return
        if url.path.startswith("/api/calls"):
            self.call_requests.append(route.request.url); route.abort(); return
        if SDK_URL.search(route.request.url):
            self.sdk_requests += 1
            route.fulfill(status=200, content_type="text/javascript", body=SDK_DOUBLE); return
        if url.path == "/api/config":
            self.respond(route, {"csrf_token": "offline-test-csrf", "call_configured": False, "call_missing": ["GISOO_API_KEY"], "map_configured": self.configured, "chat_configured": self.chat_configured, "chat_missing": [] if self.chat_configured else ["BOXAPI_API_KEY"], "routing_configured": self.routing_configured, "travel_modes": ["car", "pedestrian"], "coverage": {"products": 1, "offers": 3, "stores": 3, "categories": ["گوشی موبایل"], "attributes": {}, "currencies": ["TOMAN"], "issues": []}}); return
        if url.path == "/api/conversations":
            self.conversation_number += 1
            self.view = {"id": "offline-" + str(self.conversation_number), "stage": 1, "messages": [], "selected_product_id": None, "travel_mode": None, "expires_in_seconds": 3600}
            self.append("assistant", "سلام، چی می‌خوای بخری؟ این گفت‌وگو از دادهٔ آفلاین تست استفاده می‌کند.")
            self.respond(route, self.view); return
        if url.path.startswith("/api/conversations/"):
            if route.request.method == "DELETE":
                self.respond(route, {"deleted": True}); return
            if url.path.endswith("/turns"):
                turn = route.request.post_data_json
                self.turns.append(turn)
                if self.fail_once:
                    self.fail_once = False
                    self.respond(route, {"detail": "خطای موقت تست؛ با همان شناسه دوباره تلاش کنید."}, 503); return
                action = turn["action"]
                if action == "message":
                    self.append("user", turn["message"])
                    self.append("assistant", "محصول موردنظرت را انتخاب کن.", [{"type": "products", "items": PRODUCTS}])
                elif action == "select_product":
                    self.view["stage"] = 2; self.view["selected_product_id"] = turn["product_id"]
                    self.append("assistant", "برای یافتن فروشگاه نزدیک، یک نقطه روی نقشه انتخاب کن.", [{"type": "location", "center": None}])
                elif action == "set_location":
                    self.mode = turn["travel_mode"]; self.view["travel_mode"] = self.mode
                    self.append("assistant", "فروشگاه‌های این محصول را ببین و مقایسه کن.", [{"type": "stores", "items": OFFERS}])
                elif action == "compare":
                    self.view["stage"] = 3
                    self.append("assistant", "فروشگاه‌ها را با هم مقایسه کن.", [{"type": "comparison", "items": [x for x in OFFERS if x["id"] in turn["offer_ids"]], "note": "اطلاعات آفلاین تست، قیمت فعلی نامشخص است.", "price_comparable": False}])
                elif action == "inquiry":
                    self.view["stage"] = 4
                    self.append("assistant", "برای تمرین استعلام، دموی صوتی را شروع کن.", [{"type": "inquiry", "items": [x for x in OFFERS if x["id"] in turn["offer_ids"]]}])
                elif action == "back_to_products":
                    self.view["stage"] = 1; self.view["selected_product_id"] = None
                    self.append("assistant", "محصول موردنظرت را انتخاب کن.", [{"type": "products", "items": PRODUCTS}])
                self.respond(route, self.view); return
            self.respond(route, self.view); return
        if url.path == "/api/maps/config":
            self.map_config_requests += 1; self.respond(route, {"api_key": PUBLIC_TEST_KEY}); return
        if url.path.startswith("/api/feedback/"):
            self.respond(route, {"deleted": True} if route.request.method == "DELETE" else {"id": "offline-feedback"}); return
        if url.path.startswith("/api/"):
            route.abort(); raise AssertionError("Unexpected API request: " + url.path)
        route.continue_()

    def open(self):
        self.page.goto(BASE_URL, wait_until="networkidle")
        expect(self.page.locator("#query")).to_be_visible()
        expect(self.page.locator("#chat")).to_contain_text("چی می‌خوای بخری")

    def open_products(self):
        self.open()
        self.page.locator("#query").fill("گوشی موبایل s24 ultra میخوام")
        self.page.locator("#send-message").click()
        expect(self.page.locator('[data-testid="product-choice"]')).to_have_count(1)

    def open_location(self):
        self.open_products()
        self.page.get_by_role("button", name="انتخاب این محصول", exact=True).click()
        expect(self.page.locator('[data-testid="location-picker"]')).to_be_visible()

    def open_stores(self):
        self.open_location()
        # A mocked server turn isolates store-map tests from pin-map tests. No provider is called.
        self.view["messages"].append({"id": "stores", "role": "assistant", "text": "فروشگاه‌های تست آفلاین", "components": [{"type": "stores", "items": OFFERS}]})
        self.page.locator("#query").fill("نمایش فروشگاه‌ها")
        self.page.locator("#send-message").click()
        expect(self.page.locator('[data-testid="store-offer"]')).to_have_count(3)

    def probe(self):
        return self.page.evaluate("window.__mapProbe")

    def assert_safe(self):
        assert not self.external_requests, self.external_requests
        assert not self.call_requests, self.call_requests
        assert not self.errors, self.errors
        assert self.page.evaluate("document.documentElement.scrollWidth <= innerWidth")

    def close(self):
        self.context.close()
