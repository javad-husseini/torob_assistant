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


def test_real_constraints_and_injection(real):
    assert real.search(Intent(query='لنز سونی',installments_only=True))['items']==[]
    assert real.search(Intent(query="' OR 1=1 --"))['items']==[]
    assert real.search(Intent(category='دسته‌ای که وجود ندارد'))['state']=='unsupported'


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
