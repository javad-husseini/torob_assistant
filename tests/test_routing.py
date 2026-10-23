"""Neshan is always mocked here; routing tests never consume API quota."""
import asyncio
import json

import httpx
import pytest

from app import routing
from app.models import StoreLocation


ORIGIN = StoreLocation(latitude=35.7, longitude=51.4)


def offer(index=0, location=True):
    return {'id': f'o{index}', 'store_id': f's{index}', 'store': {'id': f's{index}',
            'location': {'latitude': 35.71 + index / 1000, 'longitude': 51.41} if location else None}}


@pytest.fixture(autouse=True)
def configured(monkeypatch):
    monkeypatch.setenv('NESHAN_ROUTING_API_KEY', 'private-test-key')
    routing._cache.clear()


def response(distance=1820.0, duration=487.0):
    return {'routes': [{'legs': [{'distance': {'value': distance}, 'duration': {'value': duration}}]}]}


def run(handler, offers=None, mode='car'):
    requests = []
    def handle(request):
        requests.append(request)
        return handler(request)
    async def execute():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            return await routing.route_offers(ORIGIN, offers or [offer()], mode, client)
    return asyncio.run(execute()), requests


@pytest.mark.parametrize('mode,path', [('car', '/v4/direction'), ('pedestrian', '/v4/direction')])
def test_uses_private_header_fixed_endpoint_correct_coordinate_order(mode, path):
    rows, requests = run(lambda request: httpx.Response(200, json=response()), mode=mode)
    assert len(requests) == 1
    request = requests[0]
    assert request.url.host == 'api.neshan.org' and request.url.path == path
    assert request.headers['Api-Key'] == 'private-test-key'
    assert request.url.params['origin'] == '35.7,51.4'
    assert request.url.params['destination'] == '35.71,51.41'
    assert request.url.params['type'] == mode
    assert 'private-test-key' not in str(request.url)
    route = rows[0]['route']
    assert route['status'] == 'ready' and route['distance_meters'] == 1820 and route['duration_seconds'] == 487
    assert route['source'] == 'neshan' and route['mode'] == mode and route['fetched_at']


def test_missing_service_key_never_uses_public_map_key(monkeypatch):
    monkeypatch.delenv('NESHAN_ROUTING_API_KEY')
    monkeypatch.setenv('NESHAN_MAP_API_KEY', 'public-web-key')
    rows, requests = run(lambda request: pytest.fail('network forbidden'))
    assert requests == [] and rows[0]['route']['status'] == 'unconfigured'


def test_cache_avoids_repeated_route_requests_and_key_changes_isolate_cache(monkeypatch):
    handler = lambda request: httpx.Response(200, json=response())
    first, requests = run(handler)
    second, repeat_requests = run(lambda request: pytest.fail('cached destination must not request again'))
    assert len(requests) == 1 and repeat_requests == [] and first == second
    monkeypatch.setenv('NESHAN_ROUTING_API_KEY', 'different-private-key')
    _, other_requests = run(handler)
    assert len(other_requests) == 1


def test_cache_expires(monkeypatch):
    _, requests = run(lambda request: httpx.Response(200, json=response()))
    assert requests
    for key, entry in list(routing._cache.items()):
        routing._cache[key] = (0, entry[1])
    _, requests = run(lambda request: httpx.Response(200, json=response(duration=900)))
    assert len(requests) == 1


@pytest.mark.parametrize('status,data,expected', [
    (200, {'routes': []}, 'no_route'),
    (404, {'status': 'NoRouteFound'}, 'no_route'),
    (200, {'code': 'NoRouteFound'}, 'no_route'),
    (481, {'status': 'LimitExceeded'}, 'unavailable'),
    (500, {}, 'unavailable'),
    (302, {}, 'unavailable'),
    (200, {}, 'unavailable'),
    (200, response(distance=-1), 'unavailable'),
    (200, response(distance=True), 'unavailable'),
    (200, response(duration='487'), 'unavailable'),
    (200, response(duration=float('inf')), 'unavailable'),
])
def test_route_failures_remain_unknown_no_straight_line_estimate(status, data, expected):
    rows, requests = run(lambda request: httpx.Response(status, content=json.dumps(data)))
    route = rows[0]['route']
    assert len(requests) == 1 and route['status'] == expected
    assert route['distance_meters'] is None and route['duration_seconds'] is None
    assert routing._cache == {}


def test_malformed_response_oversize_and_timeout_are_bounded(monkeypatch):
    for handler in [lambda request: httpx.Response(200, content='not-json'),
                    lambda request: httpx.Response(200, content=' ' * (routing.MAX_BODY_BYTES + 1))]:
        rows, requests = run(handler)
        assert len(requests) == 1 and rows[0]['route']['status'] == 'unavailable'
    def timeout(request):
        raise httpx.ReadTimeout('mock timeout')
    rows, requests = run(timeout)
    assert len(requests) == 1 and rows[0]['route']['status'] == 'unavailable'


def test_destinations_deduplicated_and_maximum_six_requests():
    offers = [offer(i) for i in range(10)] + [offer(0), offer(11, location=False)]
    rows, requests = run(lambda request: httpx.Response(200, json=response()), offers)
    assert len(requests) == 6 and len(rows) == 12
    assert all(row['route']['status'] == 'ready' for row in rows[:6])
    assert rows[10]['route']['status'] == 'ready'
    assert all(row['route']['status'] == 'unavailable' for row in rows[6:10] + rows[11:])
    assert all('route' not in original for original in offers)


def test_at_most_two_requests_in_flight():
    active = maximum = 0
    async def handler(request):
        nonlocal active, maximum
        active += 1
        maximum = max(maximum, active)
        await asyncio.sleep(0.01)
        active -= 1
        return httpx.Response(200, json=response())
    async def execute():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await routing.route_offers(ORIGIN, [offer(i) for i in range(6)], 'car', client)
    rows = asyncio.run(execute())
    assert maximum == 2 and all(row['route']['status'] == 'ready' for row in rows)


def test_travel_mode_requires_explicit_supported_value():
    with pytest.raises(ValueError):
        asyncio.run(routing.route_offers(ORIGIN, [offer()], 'motorcycle'))
