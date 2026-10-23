import json
from datetime import datetime,timezone,timedelta
import pytest
from pydantic import ValidationError
from app.catalog import Catalog
from app.models import Intent,normalize,Feedback,CallRequest,CallResult


def test_normalization():
    assert normalize('  كالا، يک\u200cمدل ۱۲٣! ')==normalize('کالا یک مدل 123')


def test_determinism(catalog):
    a=catalog.search(Intent(query='سونی'))
    assert a==catalog.search(Intent(query='سوني'))
    assert [p['id'] for p in a['items']]==['p0','p1','p2']
    assert all(p['reviews'] is None for p in a['items'])


def test_installments_unknown_no(catalog):
    assert [p['id'] for p in catalog.search(Intent(installments_only=True))['items']]==['p0']
    assert [p['id'] for p in catalog.search(Intent(in_stock_only=True))['items']]==['p0']


def test_no_relaxation(catalog):
    assert not catalog.search(Intent(query='سونی',max_price=99,currency='TOMAN'))['items']
    assert not catalog.search(Intent(attributes={'وزن':'1 کیلوگرم'}))['items']
    assert catalog.search(Intent(query='مانتو'))['state']=='unsupported'
    assert catalog.search(Intent(category='پوشاک'))['state']=='unsupported'
    assert catalog.search(Intent(query='نظرات'))['state']=='unsupported'
    assert catalog.search(Intent(query='گوشی زیر 100 تومان'))['state']=='clarification'


@pytest.mark.parametrize('body',[{'max_price':1},{'query':'x'*501},{'limit':100},{'currency':'USD'},{'attributes':{'x':'a'*201}},{'query':{},'sql':'DELETE'}])
def test_intent_validation(body):
    with pytest.raises(ValidationError):Intent(**body)


def test_stale_invalid_and_orphan(dataset):
    path,data=dataset
    data['products'][0].update(price=-3,currency='USD',installments='maybe',updated_at=None,store_id='missing')
    data['products'][1]['updated_at']=(datetime.now(timezone.utc)-timedelta(days=31)).isoformat()
    data['products'].append({'name':'bad'})
    path.write_text(json.dumps(data),encoding='utf-8')
    c=Catalog(str(path));p=c.effective(c.products['p0'])
    assert p['price'] is None and p['currency'] is None and p['installments']=='unknown' and not p['call_eligible']
    assert c.effective(c.products['p1'])['price'] is None
    assert len(c.products)==3 and c.issues


def test_duplicate_quarantine(dataset):
    path,data=dataset;data['products'] += [data['products'][0],data['products'][0]]
    path.write_text(json.dumps(data),encoding='utf-8');assert 'p0' not in Catalog(str(path)).products


def test_broken_data(tmp_path):
    p=tmp_path/'bad';p.write_text('not json');assert Catalog(str(p)).issues==['dataset_invalid']
    assert Catalog(str(tmp_path/'missing')).issues==['dataset_missing']


def test_compare(catalog):
    r=catalog.compare(['p1','p2']);assert r['price_comparable']
    assert [p['installments'] for p in r['items']]==['no','unknown']
    catalog.products['p2'].currency='IRR';assert not catalog.compare(['p1','p2'])['price_comparable']


def test_consent_and_sanitize():
    with pytest.raises(ValidationError):Feedback(product_id='p',consent=False,text='hello')
    assert Feedback(product_id='p',consent=True,text='<b>hello</b>\x00').text=='hello'


def test_request_validation():
    with pytest.raises(ValidationError):CallRequest(request_id='r',store={'id':'s','name':'s'},product={'id':'p','name':'p'},questions=['price','price'])


@pytest.mark.parametrize('location',[
    None,'null',[],{}, {'latitude':35.7},{'longitude':51.4},
    {'latitude':'bad','longitude':51.4},{'latitude':float('nan'),'longitude':51.4},
    {'latitude':35.7,'longitude':float('inf')},{'latitude':-91,'longitude':51.4},
    {'latitude':35.7,'longitude':181},{'latitude':True,'longitude':51.4},
    {'lat':35.7,'lon':51.4},
])
def test_invalid_optional_store_facts_preserve_json_identity(dataset,location):
    path,data=dataset
    data['stores'][0].update(location=location,address={'invalid':'object'},location_label='x'*201)
    path.write_text(json.dumps(data),encoding='utf-8')
    before=path.read_bytes()
    c=Catalog(str(path))
    assert len(c.stores)==1
    product=c.search(Intent(query='سونی'))['items'][0]
    assert product['store']['id']=='s1' and product['call_eligible']
    assert product['store']['location'] is None and product['store']['address'] is None
    assert product['store']['location_label'] is None
    assert path.read_bytes()==before


def test_valid_json_store_location_and_optional_text(dataset):
    path,data=dataset
    data['stores'][0].update(location={'latitude':'35.71','longitude':'51.42'},
        address='  خیابان\x00 اول\n پلاک ۲  ',location_label='مرکز\u200cشهر')
    path.write_text(json.dumps(data),encoding='utf-8')
    c=Catalog(str(path))
    store=c.search(Intent(query='سونی'))['items'][0]['store']
    assert store['location']=={'latitude':35.71,'longitude':51.42}
    assert store['address']=='خیابان اول پلاک ۲'
    assert store['location_label']=='مرکز\u200cشهر'
    assert all(p['store']==store for p in c.compare(['p0','p1'])['items'])


@pytest.mark.parametrize('address',[None,'','   ','null',' NULL ','x'*1001,True,34])
def test_unknown_optional_store_address(dataset,address):
    path,data=dataset
    data['stores'][0]['address']=address
    path.write_text(json.dumps(data),encoding='utf-8')
    c=Catalog(str(path))
    assert c.stores['s1'].address is None
    assert len(c.products)==3
