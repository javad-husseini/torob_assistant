import csv
import json
from datetime import datetime, timedelta, timezone

import pytest

from app.csv_catalog import CsvCatalog
from app.catalog import Catalog
from app.models import Intent, StoreLocation
from app.shop_search import ShopRepository


@pytest.fixture
def shops(tmp_path):
    now = datetime.now(timezone.utc).isoformat()
    stale = (datetime.now(timezone.utc) - timedelta(days=70)).isoformat()
    files = {
        'shops.csv': [
            {'shop_id': 's1', 'name': 'اول', 'lat': '35.7', 'lon': '51.4'},
            {'shop_id': 's2', 'name': 'دوم', 'lat': '35.8', 'lon': '51.5'},
            {'shop_id': 's3', 'name': 'سوم', 'lat': '29.6', 'lon': '52.5'},
        ],
        'products.csv': [
            {'product_id': 'p256', 'persian_title': 'گوشی Samsung S24 Ultra 256', 'category_name': 'گوشی موبایل', 'specs': json.dumps([{'key': 'برند', 'value': 'Samsung'}, {'key': 'ظرفیت', 'value': '256'}])},
            {'product_id': 'p512', 'persian_title': 'گوشی Samsung S24 Ultra 512', 'category_name': 'گوشی موبایل', 'specs': json.dumps([{'key': 'برند', 'value': 'Samsung'}, {'key': 'ظرفیت', 'value': '512'}])},
            {'product_id': 'used', 'persian_title': 'گوشی Samsung S24 Ultra 256 کارکرده', 'category_name': 'گوشی موبایل', 'specs': '[]'},
            {'product_id': 'clone', 'persian_title': 'گوشی S24 Ultra طرح', 'category_name': 'گوشی موبایل', 'specs': json.dumps([{'key': 'برند', 'value': 'Clone'}])},
            {'product_id': 'case', 'persian_title': 'قاب گوشی Samsung S24 Ultra', 'category_name': 'قاب گوشی', 'specs': '[]'},
        ],
        'offers.csv': [
            {'offer_id': 'o11', 'shop_id': 's1', 'product_id': 'p256', 'price_toman': '150', 'last_price_changed_at': now},
            {'offer_id': 'o12', 'shop_id': 's1', 'product_id': 'p256', 'price_toman': '140', 'last_price_changed_at': now},
            {'offer_id': 'o21', 'shop_id': 's2', 'product_id': 'p256', 'price_toman': '20', 'last_price_changed_at': stale},
            {'offer_id': 'o22', 'shop_id': 's2', 'product_id': 'p256', 'price_toman': '160', 'last_price_changed_at': now},
            {'offer_id': 'o31', 'shop_id': 's3', 'product_id': 'p256', 'price_toman': '130', 'last_price_changed_at': now},
            {'offer_id': 'o512', 'shop_id': 's1', 'product_id': 'p512', 'price_toman': '180', 'last_price_changed_at': now},
            {'offer_id': 'oused', 'shop_id': 's1', 'product_id': 'used', 'price_toman': '110', 'last_price_changed_at': now},
            {'offer_id': 'oclone', 'shop_id': 's1', 'product_id': 'clone', 'price_toman': '10', 'last_price_changed_at': now},
            {'offer_id': 'ocase', 'shop_id': 's1', 'product_id': 'case', 'price_toman': '1', 'last_price_changed_at': now},
        ],
    }
    for filename, rows in files.items():
        with (tmp_path / filename).open('w', encoding='utf-8', newline='') as output:
            writer = csv.DictWriter(output, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
    return ShopRepository(CsvCatalog(tmp_path))


def test_product_results_group_only_real_id_not_variants_or_titles(shops):
    items = shops.search_products(Intent(query='S24 Ultra', category='گوشی موبایل'))
    assert {row['product_id'] for row in items} == {'p256', 'p512', 'used', 'clone'}
    assert len(items) == len({row['product_id'] for row in items})
    assert next(row for row in items if row['product_id'] == 'p256')['offer_count'] == 3
    assert all(row['category'] == 'گوشی موبایل' for row in items)
    assert 'کارکرده' in next(row for row in items if row['product_id'] == 'used')['name']
    assert 'طرح' in next(row for row in items if row['product_id'] == 'clone')['name']


def test_brand_capacity_and_price_filters_are_mandatory(shops):
    intent = Intent(query='S24 Ultra', category='گوشی موبایل', attributes={'برند': 'Samsung', 'ظرفیت': '256'}, max_price=145, currency='TOMAN')
    rows = shops.search_products(intent)
    assert [row['product_id'] for row in rows] == ['p256']
    assert int(rows[0]['price']) <= 145
    assert shops.search_products(intent.model_copy(update={'max_price': 100})) == []
    assert shops.search_products(intent.model_copy(update={'currency': 'IRR'})) == []


@pytest.mark.parametrize('filters', [{'installments_only': True}, {'in_stock_only': True}, {'category': 'missing'}, {'query': "' OR 1=1 --"}, {'attributes': {"' OR 1=1 --": '256'}}])
def test_unknown_and_malicious_filters_do_not_broaden_search(shops, filters):
    assert shops.search_products(Intent(**filters)) == []


def test_stores_are_only_for_exact_selected_product_deduped_with_effective_price(shops):
    rows = shops.offers_for_product('p256')
    assert {row['store_id'] for row in rows} == {'s1', 's2', 's3'}
    assert {row['id'] for row in rows} == {'o12', 'o22', 'o31'}
    assert all(row['product_id'] == 'p256' for row in rows)
    assert all(row['stock'] == 'unknown' and row['reviews'] is None for row in rows)
    assert shops.offers_for_product("p256' OR 1=1 --") == []
    assert shops.offers_for_product('does-not-exist') == []


def test_csv_shop_offers_preserve_budget_currency_and_unknown_stock_filters(shops):
    eligible = shops.offers_for_product('p256', Intent(max_price=145, currency='TOMAN'))
    assert {row['id'] for row in eligible} == {'o12', 'o31'}
    assert shops.offers_for_product('p256', Intent(max_price=145, currency='IRR')) == []
    assert shops.offers_for_product('p256', Intent(in_stock_only=True)) == []
    assert shops.offers_for_product('p256', Intent(installments_only=True)) == []


def test_shortlist_uses_coordinates_only_internally_without_fake_route_distance(shops):
    rows = shops.offers_for_product('p256')
    shortlist = shops.shortlist(StoreLocation(latitude=35.8, longitude=51.5), rows, limit=2)
    assert [row['store_id'] for row in shortlist] == ['s2', 's1']
    assert all('distance_meters' not in row and 'route' not in row for row in shortlist)
    assert 'route' not in rows[0]


def test_json_fallback_uses_existing_product_id(catalog):
    repository = ShopRepository(catalog)
    products = repository.search_products(Intent(query='سونی'))
    assert {row['product_id'] for row in products} == {'p0', 'p1', 'p2'}
    assert repository.offers_for_product('p0')[0]['id'] == 'p0'
    assert repository.offers_for_product('unknown') == []


def test_json_source_product_identity_supports_multiple_offers_and_stores(tmp_path):
    now = datetime.now(timezone.utc).isoformat()
    data = {'stores': [{'id': 's1', 'name': 'اول', 'source': 'test'}, {'id': 's2', 'name': 'دوم', 'source': 'test'}], 'products': []}
    for index in range(35):
        data['products'].append({'id': f'offer-{index:02}', 'product_id': 'true-product', 'name': 'Samsung S24 Ultra 256',
                                 'category': 'phone', 'source': 'test', 'store_id': 's1' if index < 34 else 's2',
                                 'price': 200 - index, 'currency': 'TOMAN', 'updated_at': now})
    data['products'].append({'id': 'different-variant', 'product_id': '512-variant', 'name': 'Samsung S24 Ultra 512',
                             'category': 'phone', 'source': 'test', 'store_id': 's1'})
    path = tmp_path / 'data.json'
    path.write_text(json.dumps(data), encoding='utf-8')
    repository = ShopRepository(Catalog(str(path)))
    products = repository.search_products(Intent(query='S24 Ultra', category='phone'))
    assert {row['product_id'] for row in products} == {'true-product', '512-variant'}
    assert next(row for row in products if row['product_id'] == 'true-product')['offer_count'] == 2
    rows = repository.offers_for_product('true-product')
    assert {row['id'] for row in rows} == {'offer-33', 'offer-34'}
    assert repository.offers_for_product('offer-00') == []


def test_json_eligible_offer_is_not_hidden_by_cheaper_offer_from_same_store(tmp_path):
    now = datetime.now(timezone.utc).isoformat()
    stale = (datetime.now(timezone.utc) - timedelta(days=70)).isoformat()
    base = {'product_id': 'true-product', 'name': 'Samsung S24 Ultra', 'category': 'phone',
            'source': 'test', 'store_id': 's1', 'currency': 'TOMAN', 'updated_at': now}
    data = {'stores': [{'id': 's1', 'name': 'فروشگاه', 'source': 'test'}], 'products': [
        {**base, 'id': 'cheap-unknown', 'price': 100, 'stock': 'unknown', 'installments': 'unknown'},
        {**base, 'id': 'cheap-out-of-stock', 'price': 10, 'stock': 'out_of_stock', 'installments': 'no'},
        {**base, 'id': 'eligible', 'price': 150, 'stock': 'in_stock', 'installments': 'yes'},
        {**base, 'id': 'different-currency', 'price': 1, 'currency': 'IRR', 'stock': 'in_stock', 'installments': 'yes'},
        {**base, 'id': 'stale', 'price': 5, 'stock': 'in_stock', 'installments': 'yes', 'updated_at': stale},
    ]}
    path = tmp_path / 'same-store-offers.json'
    path.write_text(json.dumps(data), encoding='utf-8')
    repository = ShopRepository(Catalog(str(path)))
    constraints = Intent(in_stock_only=True, installments_only=True, max_price=160, currency='TOMAN')
    assert [row['id'] for row in repository.offers_for_product('true-product', constraints)] == ['eligible']
    assert repository.offers_for_product('true-product', constraints.model_copy(update={'max_price': 140})) == []
    assert [row['id'] for row in repository.offers_for_product('true-product', constraints.model_copy(update={'max_price': None}))] == ['eligible']
    # Optional filtering preserves the original unfiltered API for other callers.
    assert repository.offers_for_product('true-product')[0]['id'] == 'different-currency'
