import pytest
from fastapi.testclient import TestClient
from app import main
from app.calls import Call
from app.models import CallRequest


def test_voice_test_mode_requires_opt_in_and_loopback(monkeypatch):
    from starlette.requests import Request
    def request(client_host, host):
        return Request({'type':'http','scheme':'http','path':'/api/config',
            'headers':[(b'host',host.encode())], 'client':(client_host,1234), 'server':('127.0.0.1',8000)})
    monkeypatch.delenv('GISOO_LOCAL_TEST_MODE',raising=False)
    assert not main.local_voice_test(request('127.0.0.1','localhost:8000'))
    monkeypatch.setenv('GISOO_LOCAL_TEST_MODE','true')
    assert main.local_voice_test(request('127.0.0.1','127.0.0.1:8000'))
    assert not main.local_voice_test(request('192.0.2.1','localhost:8000'))
    assert not main.local_voice_test(request('127.0.0.1','public.example'))

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


def test_built_ui_style_nonce_is_per_document(client,tmp_path,monkeypatch):
    import re
    ui=tmp_path/'static'/'ui'
    ui.mkdir(parents=True)
    (ui/'index.html').write_text('<meta name="csp-nonce" content="__CSP_NONCE__">',encoding='utf-8')
    monkeypatch.setattr(main,'ROOT',tmp_path)
    first=client.get('/');second=client.get('/')
    nonce=re.search(r"'nonce-([^']+)'",first.headers['content-security-policy']).group(1)
    assert nonce in first.text and '__CSP_NONCE__' not in first.text
    assert nonce not in second.text
    assert "script-src 'self'" in first.headers['content-security-policy']
    assert 'unsafe-inline' not in first.headers['content-security-policy']


def test_map_config_only_exposes_explicit_public_web_key(client,monkeypatch):
    monkeypatch.setenv('NESHAN_MAP_API_KEY','test-public-domain-restricted-web-key')
    monkeypatch.setenv('GISOO_API_KEY','test-private-gisoo-secret')
    monkeypatch.setenv('BOXAPI_API_KEY','test-private-boxapi-secret')
    general=client.get('/api/config')
    assert general.json()['map_configured'] is True
    assert 'test-public-domain-restricted-web-key' not in general.text
    result=client.get('/api/maps/config')
    assert result.json()=={'api_key':'test-public-domain-restricted-web-key'}
    for response in (general,result):
        assert 'test-private-gisoo-secret' not in response.text
        assert 'test-private-boxapi-secret' not in response.text
        assert response.headers['cache-control']=='no-store'
    csp=result.headers['content-security-policy']
    assert "connect-src 'self' https://*.neshan.org;" in csp
    assert "script-src 'self';" in csp and 'unsafe-inline' not in csp
    assert "style-src-attr 'unsafe-hashes'" in csp
    assert all(f"'{h}'" in csp for h in main.NESHAN_STYLE_HASHES)
    assert result.headers['referrer-policy']=='strict-origin-when-cross-origin'


def test_missing_map_key_does_not_prevent_shopping(client,monkeypatch):
    monkeypatch.delenv('NESHAN_MAP_API_KEY',raising=False)
    assert client.get('/api/config').json()['map_configured'] is False
    result=client.get('/api/maps/config')
    assert result.status_code==503
    assert 'https://*.neshan.org' not in result.headers['content-security-policy']
    assert result.headers['referrer-policy']=='no-referrer'
    assert client.post('/api/chat',json={'query':'سونی'}).json()['items']


def test_private_service_map_key_is_never_exposed(client,monkeypatch):
    key='service.private-test-value'
    monkeypatch.setenv('NESHAN_MAP_API_KEY',key)
    config=client.get('/api/config')
    response=client.get('/api/maps/config')
    assert config.json()['map_configured'] is False
    assert response.status_code==503
    assert key not in config.text and key not in response.text
    assert 'https://*.neshan.org' not in response.headers['content-security-policy']
    assert 'https://image.torob.com' in response.headers['content-security-policy']
