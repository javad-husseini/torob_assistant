import pytest
from fastapi.testclient import TestClient
from app import main
from app.calls import Call
from app.models import CallRequest

@pytest.fixture
def client(catalog,monkeypatch):
    monkeypatch.setattr(main,'catalog',catalog);main.calls.clear();main.feedback.clear()
    with TestClient(main.app) as c:
        config=c.get('/api/config').json();c.headers['X-App-Token']=config['csrf_token'];yield c


def test_api_health_filters_chat_compare(client):
    assert client.get('/health').json()['status']=='ok'
    assert client.get('/api/catalog/filters').json()['categories']==['گوشی']
    assert len(client.post('/api/chat',json={'query':'سونی'}).json()['items'])==3
    assert client.post('/api/compare',json={'ids':['p1','p2']}).status_code==200
    assert client.post('/api/compare',json={'ids':['p1','missing']}).status_code==404
    assert client.post('/api/chat',json={'max_price':1}).status_code==422
    assert client.post('/api/chat',json={'query':'x'*66000}).status_code==413


def test_write_protection(client):
    assert client.post('/api/chat',json={},headers={'X-App-Token':''}).status_code==403
    assert client.post('/api/chat',json={},headers={'Origin':'https://evil.example'}).status_code==403
    assert 'access-control-allow-origin' not in client.get('/api/config',headers={'Origin':'https://evil.example'}).headers


def test_feedback_separation_ownership_and_deletion(client):
    payload={'product_id':'p0','consent':True,'text':'بازدید کردم'}
    assert client.post('/api/feedback/purchase',json=payload).status_code==422
    visit=client.post('/api/feedback/visit',json=payload).json()
    purchase=client.post('/api/feedback/purchase',json={**payload,'purchased':True}).json()
    assert visit['kind']=='visit' and purchase['kind']=='purchase'
    assert not visit['persistent']
    assert main.feedback[visit['id']]['kind']=='visit'
    assert client.delete('/api/feedback/'+visit['id']).json()=={'deleted':True}
    assert client.delete('/api/feedback/'+visit['id']).status_code==404


def test_call_config_association_and_payload(client,monkeypatch):
    monkeypatch.delenv('GISOO_API_KEY',raising=False)
    payload={'request_id':'r','store':{'id':'s1','name':'فروشگاه آزمایشی'},'product':{'id':'p0','name':'گوشی سونی مدل 0','attributes':{'وزن':'100 گرم'}}}
    assert client.post('/api/calls',json=payload).status_code==503
    payload['store']['name']='invented'
    assert client.post('/api/calls',json=payload).status_code==422


def test_finalization_gate_idempotency_and_ownership(client):
    c=Call(CallRequest(request_id='r',store={'id':'s1','name':'s'},product={'id':'p0','name':'p'}))
    owner=client.cookies.get('torob_session');main.calls[c.id]={'call':c,'owner':owner}
    assert client.get('/api/calls/'+c.id+'/result').status_code==409
    for _ in range(2):assert client.post('/api/calls/'+c.id+'/end',json={}).status_code==200
    assert client.get('/api/calls/'+c.id+'/result').json()['reason']=='manual_end'
    with TestClient(main.app) as other:assert other.get('/api/calls/'+c.id+'/result').status_code==404


def test_websocket_origin_rejected(client):
    from starlette.websockets import WebSocketDisconnect
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect('/ws/calls/unknown',headers={'Origin':'https://evil.example'}):pass


def test_static_safety(client):
    r=client.get('/');assert 'dir="rtl"' in r.text and 'lang="fa"' in r.text
    assert 'تماس تلفنی واقعی برقرار نمی‌شود' in r.text
    assert "script-src 'self'" in r.headers['content-security-policy']
    js=client.get('/static/app.js').text
    assert 'innerHTML' not in js and 'localStorage' not in js and 'MediaRecorder' not in js
