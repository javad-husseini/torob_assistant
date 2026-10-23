"""Bounded server-only Neshan route estimates, never straight-line substitutes.

Traffic API: https://platform.neshan.org/docs/api/routing-category/routing/
Walking API: https://platform.neshan.org/docs/api/routing-category/routing_pedestrian/
Walking examples still mention retired v1; the current endpoint heading is v4.
No automatic fallback to another endpoint or travel mode.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import math
import os
import time
from datetime import datetime, timezone

import httpx

from .models import StoreLocation

ENDPOINTS = {'car': 'https://api.neshan.org/v4/direction', 'pedestrian': 'https://api.neshan.org/v4/direction'}
CACHE_TTL = 300
MAX_BODY_BYTES = 1_000_000
MAX_CANDIDATES = 6
_cache: dict[tuple, tuple[float, dict]] = {}


def _result(status, mode):
    return {'status': status, 'distance_meters': None, 'duration_seconds': None,
            'mode': mode, 'source': 'neshan', 'fetched_at': None}


def _metric(leg, name):
    metric = leg.get(name)
    value = metric.get('value') if isinstance(metric, dict) else None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0 or value > 1_000_000_000:
        raise ValueError('invalid route metric')
    return value


def _parse(data, mode):
    if not isinstance(data, dict):
        return _result('unavailable', mode)
    if data.get('status') == 'NoRouteFound' or data.get('code') == 'NoRouteFound':
        return _result('no_route', mode)
    routes = data.get('routes')
    if routes == []:
        return _result('no_route', mode)
    if not isinstance(routes, list) or not routes or not isinstance(routes[0], dict):
        return _result('unavailable', mode)
    legs = routes[0].get('legs')
    if not isinstance(legs, list) or not 1 <= len(legs) <= 32 or any(not isinstance(leg, dict) for leg in legs):
        return _result('unavailable', mode)
    try:
        distance = math.ceil(sum(_metric(leg, 'distance') for leg in legs))
        duration = math.ceil(sum(_metric(leg, 'duration') for leg in legs))
    except (ValueError, OverflowError):
        return _result('unavailable', mode)
    return {**_result('ready', mode), 'distance_meters': distance, 'duration_seconds': duration,
            'fetched_at': datetime.now(timezone.utc).isoformat()}


async def _request(client, origin, destination, mode, key):
    params = {'type': mode, 'origin': f'{origin.latitude},{origin.longitude}',
              'destination': f'{destination.latitude},{destination.longitude}', 'alternative': 'false'}
    try:
        async with asyncio.timeout(10):
            async with client.stream('GET', ENDPOINTS[mode], params=params,
                                     headers={'Api-Key': key, 'Accept': 'application/json'},
                                     timeout=httpx.Timeout(8, connect=3), follow_redirects=False) as response:
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > MAX_BODY_BYTES:
                        return _result('unavailable', mode)
                data = json.loads(body)
                if not response.is_success:
                    if isinstance(data, dict) and (data.get('status') == 'NoRouteFound' or data.get('code') == 'NoRouteFound'):
                        return _result('no_route', mode)
                    return _result('unavailable', mode)
                return _parse(data, mode)
    except (httpx.HTTPError, TimeoutError, ValueError, TypeError, RecursionError):
        return _result('unavailable', mode)


async def route_offers(origin: StoreLocation, offers: list[dict], mode: str, client=None) -> list[dict]:
    """At most six distinct destinations, two in flight, and no automatic retries.

    The caller chooses a candidate shortlist and explicitly supplies travel mode.
    Returned order stays unchanged; the orchestrator ranks actual ready routes.
    Successful estimates are cached in memory for five minutes. Nothing is logged
    or persisted, and a missing private service key never uses the public map key.
    """
    if mode not in ENDPOINTS:
        raise ValueError('unsupported travel mode')
    origin = StoreLocation.model_validate(origin)
    key = os.getenv('NESHAN_ROUTING_API_KEY', '').strip()
    if not key:
        return [{**offer, 'route': _result('unconfigured', mode)} for offer in offers]
    # Limit cache size and expire coordinates with their result rather than retaining them.
    now = time.monotonic()
    for cache_key, entry in list(_cache.items()):
        if entry[0] <= now:
            _cache.pop(cache_key, None)
    key_scope = hashlib.sha256(key.encode()).digest()
    destinations = {}
    for offer in offers:
        try:
            location = StoreLocation.model_validate((offer.get('store') or {}).get('location'))
        except (TypeError, ValueError):
            continue
        coordinates = (location.latitude, location.longitude)
        if coordinates not in destinations and len(destinations) < MAX_CANDIDATES:
            destinations[coordinates] = location
    results = {}
    semaphore = asyncio.Semaphore(2)

    async def resolve(coordinates, destination, http_client):
        cache_key = (key_scope, origin.latitude, origin.longitude, *coordinates, mode)
        cached = _cache.get(cache_key)
        if cached and cached[0] > time.monotonic():
            results[coordinates] = dict(cached[1])
            return
        async with semaphore:
            result = await _request(http_client, origin, destination, mode, key)
        if result['status'] == 'ready':
            if len(_cache) >= 1024:
                _cache.pop(next(iter(_cache)))
            _cache[cache_key] = (time.monotonic() + CACHE_TTL, dict(result))
        results[coordinates] = result

    async def resolve_all(http_client):
        await asyncio.gather(*(resolve(coordinates, destination, http_client) for coordinates, destination in destinations.items()))

    if client is None:
        async with httpx.AsyncClient(follow_redirects=False) as http_client:
            await resolve_all(http_client)
    else:
        await resolve_all(client)
    output = []
    for offer in offers:
        location = (offer.get('store') or {}).get('location') or {}
        coordinate = (location.get('latitude'), location.get('longitude'))
        output.append({**offer, 'route': dict(results.get(coordinate, _result('unavailable', mode)))})
    return output
