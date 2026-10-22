import asyncio,json
import httpx,pytest
from app.calls import Call
from app.models import CallRequest
from app.extraction import extract_result,Facts,usage_from


def ready_call():
    c=Call(CallRequest(request_id='r',store={'id':'s','name':'s'},product={'id':'p','name':'p'}))
    a=c.segment('a','agent');a.text='قیمت و موجودی؟';a.complete=True;a.response_id='r1'
    b=c.segment('b','seller');b.text='موجود است قیمت ۱۰۰ تومان';b.complete=True;b.previous_item_id='a'
    d=c.segment('c','seller');d.text='ببخشید قیمت ۲۰۰ ریال';d.complete=True;d.previous_item_id='b'
    c.order_known.update(['a','b','c']);c.chunks[1]={'response_id':'r1','epoch':0};c.audio_done.add('r1');c.ack(1,0)
    c.finalize('manual_end');return c


def facts():return {'availability':'in_stock','price_amount':200,'currency':'IRR','availability_evidence':{'item_id':'b','quote':'موجود است'},'price_evidence':{'item_id':'c','quote':'قیمت ۲۰۰ ریال'}}

@pytest.fixture(autouse=True)
def config(monkeypatch):
    monkeypatch.setenv('CALL_EXTRACTION_MODE','boxapi_post_call');monkeypatch.setenv('BOXAPI_API_KEY','mock-secret');monkeypatch.setenv('BOXAPI_MODEL','approved-mock-model')


def response(f=None,**extras):return {'choices':[{'message':{'content':json.dumps(f or facts(),ensure_ascii=False)},'finish_reason':'stop'}],**extras}


def run(c,data=None,status=200,exception=None,inspect=None):
    requests=[]
    async def invoke():
        def handler(req):
            requests.append(req)
            if inspect:inspect(req)
            if exception:raise exception
            return httpx.Response(status,json=data or response())
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            await extract_result(c,client);await extract_result(c,client)
    asyncio.run(invoke());return requests


def test_boxapi_corrected_price_usage_and_no_repeat():
    c=ready_call()
    def inspect(req):
        payload=json.loads(req.content)
        assert str(req.url)=='https://ai.boxapi.ir/ai/v1/chat/completions'
        assert payload['model']=='approved-mock-model' and not payload['stream']
        transcript=json.loads(payload['messages'][1]['content'])
        assert len(transcript)==3 and set(transcript[0])=={'item_id','speaker','text'}
        assert req.headers['Authorization']=='Bearer mock-secret'
    requests=run(c,response(usage={'prompt_tokens':100,'completion_tokens':30,'total_tokens':130},cost=.0001),inspect=inspect)
    assert len(requests)==1 and c.result.price_amount==200 and c.result.currency=='IRR'
    assert c.result.extraction_status=='complete' and c.result.extraction_usage.total_tokens==130
    assert str(c.result.extraction_usage.reported_cost)=='0.0001' and c.result.extraction_usage.reported_cost_currency is None
    assert 'mock-secret' not in c.result.model_dump_json()


def test_skip_incomplete_no_http():
    c=ready_call();c.result.transcript_complete=False
    assert run(c)==[] and c.result.extraction_status=='skipped_incomplete'


def test_skip_abnormal_no_http():
    c=ready_call();c.result.reason='error'
    assert run(c)==[] and c.result.extraction_status=='skipped_abnormal'


def test_missing_model_no_default(monkeypatch):
    monkeypatch.delenv('BOXAPI_MODEL');c=ready_call()
    assert run(c)==[] and c.result.extraction_status=='unconfigured' and c.result.price_amount is None


@pytest.mark.parametrize('alter',[
    lambda f:f.update(price_amount=-1),
    lambda f:f.update(currency=None),
    lambda f:f.update(unapproved='extra'),
    lambda f:f.update(price_evidence={'item_id':'a','quote':'قیمت و موجودی؟'}),
    lambda f:f.update(price_evidence={'item_id':'c','quote':'قیمت ۹۰۰ ریال'}),
    lambda f:f.update(price_amount=100,currency='TOMAN',price_evidence={'item_id':'b','quote':'قیمت ۱۰۰ تومان'}),
])
def test_reject_invalid_or_ungrounded_facts(alter):
    c=ready_call();f=facts();alter(f)
    run(c,response(f,usage={'total_tokens':20}))
    assert c.result.extraction_status=='invalid' and c.result.price_amount is None
    assert c.result.extraction_usage.total_tokens==20


def test_no_local_primary_extraction():
    c=ready_call();assert c.result.availability=='unknown' and c.result.price_amount is None


@pytest.mark.parametrize('status',[401,402,429,500])
def test_http_error_no_retry(status):
    c=ready_call();assert len(run(c,status=status))==1
    assert c.result.extraction_status=='error' and c.result.price_amount is None


def test_timeout_no_retry():
    c=ready_call();assert len(run(c,exception=httpx.ReadTimeout('private diagnostic')))==1
    assert c.result.extraction_status=='error' and 'private diagnostic' not in c.result.model_dump_json()


def test_invalid_json_and_usage_preserved():
    c=ready_call();run(c,{'choices':[{'message':{'content':'not json'},'finish_reason':'stop'}],'usage':{'total_tokens':50}})
    assert c.result.extraction_status=='invalid' and c.result.extraction_usage.total_tokens==50


def test_usage_unknowns():
    u=usage_from({'usage':{'prompt_tokens':-1,'total_tokens':True},'cost':'NaN'})
    assert u.total_tokens is None and u.prompt_tokens is None and u.reported_cost is None

def test_same_turn_correction_supersedes_earlier_quote():
    c=ready_call();c.result.transcript[-1].text='قیمت ۱۰۰ تومان، ببخشید قیمت ۲۰۰ ریال'
    f=facts();f.update(price_amount=100,currency='TOMAN',price_evidence={'item_id':'c','quote':'قیمت ۱۰۰ تومان'})
    run(c,response(f));assert c.result.extraction_status=='invalid'
    c=ready_call();c.result.transcript[-1].text='قیمت ۱۰۰ تومان، ببخشید قیمت ۲۰۰ ریال'
    run(c,response());assert c.result.price_amount==200 and c.result.currency=='IRR'

@pytest.mark.parametrize('data',[[1],{'choices':[1]},{'choices':[{'finish_reason':'stop','message':None}]}])
def test_malformed_response_envelope(data):
    c=ready_call();run(c,data)
    assert c.result.extraction_status=='invalid' and c.state=='finalized'
