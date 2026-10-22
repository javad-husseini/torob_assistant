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
