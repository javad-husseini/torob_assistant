"""Read-only product identity search and exact-product store candidates.

The CSV's product ID is the identity: matching titles never merge variants,
used products, or look-alike products into one product.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from .models import Intent, StoreLocation, normalize


def _offer_order(row):
    price = row.get('price')
    # Compare amounts only within a common currency; unit order is merely stable.
    return (price is None, row.get('currency') or '', Decimal(str(price)) if price is not None else Decimal(0), row['id'])


class ShopRepository:
    def __init__(self, catalog):
        self.catalog = catalog

    def search_products(self, intent: Intent, limit: int = 6) -> list[dict]:
        """One representative per real product ID; all supplied filters stay mandatory."""
        limit = max(1, min(int(limit), 12))
        catalog = self.catalog
        if not hasattr(catalog, 'db'):
            query = normalize(intent.query)
            grouped = {}
            for product in catalog.products.values():
                row = catalog.effective(product)
                if intent.category and normalize(product.category) != normalize(intent.category):
                    continue
                if intent.in_stock_only and row['stock'] != 'in_stock':
                    continue
                if intent.installments_only and row['installments'] != 'yes':
                    continue
                if intent.max_price is not None and (row['price'] is None or row['currency'] != intent.currency or Decimal(str(row['price'])) > intent.max_price):
                    continue
                if any(normalize(product.attributes.get(key, '')) != normalize(value) for key, value in intent.attributes.items()):
                    continue
                haystack = normalize(' '.join([product.name, product.category, *product.attributes.values()]))
                if not all(token in haystack for token in query.split()):
                    continue
                identity = product.product_id or product.id
                row['product_id'] = identity
                grouped.setdefault(identity, []).append(row)
            found = []
            for identity, rows in grouped.items():
                representative = min(rows, key=_offer_order)
                representative['offer_count'] = len({row['store_id'] for row in rows if row.get('store_id')})
                found.append(representative)
            found.sort(key=lambda row: (-(2 if query and normalize(row['name']) == query else 1 if query and query in normalize(row['name']) else 0), row['product_id']))
            return found[:limit]
        if intent.installments_only or intent.in_stock_only:
            return []  # These facts do not exist in the CSV dataset.
        if intent.max_price is not None and intent.currency != 'TOMAN':
            return []
        query = normalize(intent.query)
        clauses, params = [], []
        for token in query.split():
            clauses.append('instr(p.search, ?) > 0')
            params.append(token)
        if intent.category:
            clauses.append('p.ncat = ?')
            params.append(normalize(intent.category))
        for key, val in intent.attributes.items():
            clauses.append('EXISTS (SELECT 1 FROM json_each(p.attributes) a WHERE a.key = ? AND a.value = ?)')
            params.extend((key, val))
        if intent.max_price is not None:
            cutoff = (datetime.now(timezone.utc) - timedelta(days=catalog.stale_days)).isoformat()
            clauses.extend(('o.price IS NOT NULL', 'CAST(o.price AS REAL) <= ?', 'o.changed >= ?'))
            params.extend((float(intent.max_price), cutoff))
        where = ' AND '.join(clauses) or '1'
        # Both query and filter values are data parameters, never identifiers.
        sql = f'''SELECT p.id AS product_id, MIN(o.id) AS representative,
                         COUNT(DISTINCT o.sid) AS offer_count,
                         CASE WHEN p.nname = ? AND ? <> '' THEN 2
                              WHEN instr(p.nname, ?) > 0 AND ? <> '' THEN 1 ELSE 0 END AS score
                  FROM products p JOIN offers o ON o.pid = p.id
                  WHERE {where}
                  GROUP BY p.id
                  ORDER BY score DESC, p.id LIMIT ?'''
        hits = catalog.db.execute(sql, [query] * 4 + params + [limit]).fetchall()
        result = []
        for hit in hits:
            row = catalog.effective(catalog.products[hit['representative']])
            # The effective adapter is the authority for freshness and currency.
            if intent.max_price is not None and (row['price'] is None or row['currency'] != intent.currency or Decimal(str(row['price'])) > intent.max_price):
                continue
            row.update(product_id=hit['product_id'], offer_count=hit['offer_count'])
            result.append(row)
        return result

    def offers_for_product(self, product_id: str, intent: Intent | None = None) -> list[dict]:
        """Exact association, then eligible offers, then one offer per store.

        Filtering must precede store deduplication: a cheaper unknown-stock offer
        cannot hide another offer that satisfies a mandatory purchase condition.
        """
        catalog = self.catalog
        if hasattr(catalog, 'db'):
            ids = [r[0] for r in catalog.db.execute('SELECT id FROM offers WHERE pid = ? ORDER BY id', (product_id,))]
        else:
            ids = [product.id for product in catalog.products.values() if (product.product_id or product.id) == product_id]
        stores = {}
        for offer_id in ids:
            row = catalog.effective(catalog.products[offer_id])
            store_id = row.get('store_id')
            if not store_id or not row.get('store'):
                continue
            if intent is not None:
                if intent.in_stock_only and row['stock'] != 'in_stock':
                    continue
                if intent.installments_only and row['installments'] != 'yes':
                    continue
                if intent.currency is not None and row['currency'] != intent.currency:
                    continue
                if intent.max_price is not None and (row['price'] is None or Decimal(str(row['price'])) > intent.max_price):
                    continue
            row['product_id'] = product_id
            previous = stores.get(store_id)
            if previous is None or _offer_order(row) < _offer_order(previous):
                stores[store_id] = row
        return sorted(stores.values(), key=lambda row: (row['store_id'], row['id']))

    @staticmethod
    def shortlist(origin: StoreLocation, offers: list[dict], limit: int = 6) -> list[dict]:
        """Internal geometric shortlist, never presented as travel distance or global nearest.

        Unknown locations sort last and remain available if there is room; routing
        returns unavailable for those rows instead of fabricating an estimate.
        """
        origin = StoreLocation.model_validate(origin)
        limit = max(1, min(int(limit), 6))

        def order(row):
            location = (row.get('store') or {}).get('location')
            try:
                destination = StoreLocation.model_validate(location)
            except (ValueError, TypeError):
                return (True, math.inf, row['store_id'], row['id'])
            lat1, lat2 = math.radians(origin.latitude), math.radians(destination.latitude)
            dlat = lat2 - lat1
            dlon = math.radians(destination.longitude - origin.longitude)
            a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
            # A monotonic score is sufficient: no distance is added to public rows.
            return (False, a, row['store_id'], row['id'])

        return sorted(offers, key=order)[:limit]
