import csv,json
from pathlib import Path
import pytest
from app.csv_catalog import CsvCatalog
from app.models import Intent

@pytest.fixture(scope='module')
def real():
    return CsvCatalog('dataset')


def test_actual_coverage(real):
    f=real.filters()
    assert f['products']>200000 and f['offers']>300000 and f['stores']==6476
    assert len(f['categories'])>3000 and not f['demo_records']
    assert f['stock'] is False and f['installments'] is False


def test_real_search_and_ids(real):
    a=real.search(Intent(query='لنز سونی',limit=3))
    assert a['state']=='results' and a==real.search(Intent(query='لنز سونی',limit=3))
    for p in a['items']:
        assert p['product_id'].startswith('product_') and p['id'].startswith('offer_') and p['store']['id'].startswith('shop_')
        assert p['stock']=='unknown' and p['installments']=='unknown' and p['reviews'] is None
        assert 'لنز' in p['name'] and p['call_eligible']


def test_real_store_locations_follow_offer_shop_id(real):
    result=real.search(Intent(query='لنز سونی',limit=3))['items']
    with Path('dataset/shops.csv').open(encoding='utf-8-sig',newline='') as f:
        stores={row['shop_id']:row for row in csv.DictReader(f)
                if row['shop_id'] in {p['store_id'] for p in result}}
    for p in result:
        source=stores[p['store_id']]
        assert p['store']['id']==p['store_id']
        assert p['store']['location']=={'latitude':float(source['lat']),'longitude':float(source['lon'])}
        assert p['store']['address']==source['address'].strip()
        assert p['store']['location_label']==source['location_label'].strip()
    assert [p['store'] for p in real.compare([p['id'] for p in result])['items']]==[p['store'] for p in result]


def test_real_constraints_and_injection(real):
    assert real.search(Intent(query='لنز سونی',installments_only=True))['items']==[]
    assert real.search(Intent(query="' OR 1=1 --"))['items']==[]
    assert real.search(Intent(category='دسته‌ای که وجود ندارد'))['state']=='unsupported'


def test_real_s24_ultra_product_and_store_associations(real):
    from app.shop_search import ShopRepository
    repository=ShopRepository(real)
    products=repository.search_products(Intent(query='s24 ultra',category='گوشی موبایل'))
    assert products and len({p['product_id'] for p in products})==len(products)
    assert all(p['category']=='گوشی موبایل' for p in products)
    for product in products:
        assert real.products[product['id']].product_id==product['product_id']
        offers=repository.offers_for_product(product['product_id'])
        assert offers and len({p['store']['id'] for p in offers})==len(offers)
        assert all(real.products[p['id']].product_id==product['product_id'] for p in offers)


def test_csv_malformed_optional_and_duplicates(tmp_path):
    files={'shops.csv':[{'shop_id':'s','name':'test'}],
    'products.csv':[{'product_id':'p','persian_title':'test','category_name':'c','specs':'[{"key":"k","value":"a"},{"key":"k","value":"b"}]'}],
    'offers.csv':[{'offer_id':'o','shop_id':'s','product_id':'p','price_toman':'NaN','last_price_changed_at':'bad'}]}
    for name,rows in files.items():
        with (tmp_path/name).open('w',encoding='utf-8',newline='') as f:
            w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
    c=CsvCatalog(tmp_path);p=c.effective(c.products['o'])
    assert p['price'] is None and p['updated_at'] is None and p['attributes']=={} and c.issues
    with (tmp_path/'offers.csv').open('a',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=files['offers.csv'][0].keys());w.writerows(files['offers.csv'])
    assert len(CsvCatalog(tmp_path).products)==0


def test_csv_location_linkage_and_raw_files_unchanged(tmp_path):
    files={'shops.csv':[
        {'shop_id':'s1','name':'اول','address':'  نشانی اول\x00  ','location_label':'تهران','lat':'35.71','lon':'51.42'},
        {'shop_id':'s2','name':'دوم','address':'نشانی دوم','location_label':'شیراز','lat':'29.61','lon':'52.53'}],
        'products.csv':[{'product_id':'p','persian_title':'کالا','category_name':'دسته','specs':'null'}],
        'offers.csv':[
            {'offer_id':'o1','shop_id':'s1','product_id':'p','price_toman':'null','last_price_changed_at':'null'},
            {'offer_id':'o2','shop_id':'s2','product_id':'p','price_toman':'null','last_price_changed_at':'null'}]}
    for name,rows in files.items():
        with (tmp_path/name).open('w',encoding='utf-8',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=rows[0].keys());writer.writeheader();writer.writerows(rows)
    before={name:(tmp_path/name).read_bytes() for name in files}
    c=CsvCatalog(tmp_path)
    items=c.search(Intent(query='کالا'))['items']
    assert [p['store']['location'] for p in items]==[
        {'latitude':35.71,'longitude':51.42},{'latitude':29.61,'longitude':52.53}]
    assert [p['store']['address'] for p in items]==['نشانی اول','نشانی دوم']
    assert [p['store'] for p in c.compare(['o2','o1'])['items']]==[items[1]['store'],items[0]['store']]
    assert {name:(tmp_path/name).read_bytes() for name in files}==before


@pytest.mark.parametrize('coordinates,expected',[
    ({},None),({'lat':'','lon':''},None),({'lat':'null','lon':'51'},None),
    ({'lat':'35.7'},None),({'lon':'51.4'},None),({'lat':'garbage','lon':'51'},None),
    ({'lat':'NaN','lon':'51'},None),({'lat':'35','lon':'Infinity'},None),
    ({'lat':'91','lon':'51'},None),({'lat':'35','lon':'-181'},None),
    ({'lat':'0','lon':'0'},{'latitude':0.0,'longitude':0.0}),
    ({'lat':'-90','lon':'180'},{'latitude':-90.0,'longitude':180.0}),
])
def test_csv_optional_location_does_not_drop_valid_store(tmp_path,coordinates,expected):
    files={'shops.csv':[{'shop_id':'s','name':'فروشگاه','address':'null','location_label':'null',**coordinates}],
        'products.csv':[{'product_id':'p','persian_title':'کالا','category_name':'دسته','specs':'null'}],
        'offers.csv':[{'offer_id':'o','shop_id':'s','product_id':'p','price_toman':'null','last_price_changed_at':'null'}]}
    for name,rows in files.items():
        with (tmp_path/name).open('w',encoding='utf-8',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=rows[0].keys());writer.writeheader();writer.writerows(rows)
    c=CsvCatalog(tmp_path)
    product=c.search(Intent())['items'][0]
    assert len(c.stores)==1 and product['call_eligible']
    assert product['store']['location']==expected
    assert product['store']['address'] is None and product['store']['location_label'] is None
