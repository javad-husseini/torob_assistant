import asyncio,json
from decimal import Decimal
import pytest
from app.models import CallRequest,Segment
from app.calls import Call,GisooAdapter,extract,configuration,session_update


@pytest.fixture(autouse=True)
def default_turn_taking(monkeypatch):
    monkeypatch.setenv('GISOO_TURN_TAKING','full_duplex')


def test_half_duplex_waits_for_audio_completion_and_playback(monkeypatch):
    monkeypatch.setenv('GISOO_TURN_TAKING','half_duplex')
    async def scenario():
        c=Call(request());b=Browser();a=GisooAdapter(c,b);a.provider=Provider()
        a.ready=True;a.pending_response=True;c.generation_count=1
        await a.event({'type':'response.output_item.added','response_id':'r','item':{'id':'a','role':'assistant'}})
        await a.event({'type':'response.output_audio.delta','response_id':'r','delta':'AAAAAA=='})
        await a.barge_in()
        assert not c.interrupted and not c.stop.is_set()
        await a.event({'type':'response.done','response':{'status':'completed','id':'r'}})
        assert not a.listening
        await a.event({'type':'response.output_audio.done','response_id':'r'})
        assert not a.listening  # Generation is complete, but playback isn't.
        class Input(Browser):
            async def iter_text(self):
                yield json.dumps({'type':'audio','audio':'AAAAAA=='})
                assert not any(e['type']=='input_audio_buffer.append' for e in a.provider.sent)
                yield json.dumps({'type':'played','seq':1,'epoch':0})
                assert a.listening
                yield json.dumps({'type':'audio','audio':'AAAAAA=='})
                yield json.dumps({'type':'end'})
        a.browser=Input()
        await a.browser_loop()
        assert sum(e['type']=='input_audio_buffer.append' for e in a.provider.sent)==1
        assert {'type':'listening','enabled':True} in a.browser.sent
    asyncio.run(scenario())


def request(): return CallRequest(request_id='r',store={'id':'s','name':'store'},product={'id':'p','name':'product'})


def complete_call():
    c=Call(request());c.generation_count=1
    seller=c.segment('b','seller');seller.text='موجود است قیمت ۱۲۰۰ تومان';seller.complete=True;seller.previous_item_id='a'
    agent=c.segment('a','agent');agent.text='دستیار هوش مصنوعی ترب هستم';agent.complete=True;agent.response_id='r1'
    c.order_known.update(['a','b']);c.chunks[1]={'response_id':'r1','epoch':0};c.audio_done.add('r1');c.ack(1,0)
    return c


def test_startup_command_is_an_order_anchor_not_seller_transcript():
    c=complete_call()
    c.context_items.add('server-setup')
    c.segments['a'].previous_item_id='server-setup'
    result=c.finalize('manual_end')
    assert result.transcript_complete
    assert {s.item_id for s in result.transcript}=={'a','b'}


def test_order_not_arrival(monkeypatch):
    monkeypatch.setenv('CALL_EXTRACTION_MODE','post_call_rules')
    c=complete_call();r=c.finalize('manual_end')
    assert r.transcript_complete and [s.item_id for s in r.transcript]==['a','b']
    assert r.price_amount is None and r.currency is None and r.availability=='unknown'
    assert r.raw_text=='موجود است قیمت ۱۲۰۰ تومان' # No primary local extraction.
    assert c.finalize('error') is r


@pytest.mark.parametrize('issue',['link','missing_text','unplayed','interrupted','missing_audio_done'])
def test_incomplete(issue,monkeypatch):
    monkeypatch.setenv('CALL_EXTRACTION_MODE','post_call_rules');c=complete_call()
    if issue=='link':c.order_known.clear()
    elif issue=='missing_text':c.segments['b'].complete=False
    elif issue=='unplayed':c.played.clear()
    elif issue=='interrupted':c.interrupted.add('r1')
    else:c.audio_done.clear()
    r=c.finalize('manual_end');assert not r.transcript_complete and r.price_amount is None
    if issue in ('unplayed','interrupted','missing_audio_done'):assert r.transcript[0].text is None


def test_barge_in_stale_ack():
    c=complete_call();c.played.clear();c.interrupt();c.ack(1,0)
    assert not c.played and not c.audible('r1') and c.epoch==1


@pytest.mark.parametrize('reason',['error','timeout','disconnected'])
def test_abnormal_preserves_unknown(reason,monkeypatch):
    monkeypatch.setenv('CALL_EXTRACTION_MODE','post_call_rules')
    r=complete_call().finalize(reason);assert r.reason==reason and r.price_amount is None


@pytest.mark.parametrize('texts,expected',[
    (['موجود است قیمت ۱۰۰ تومان'],('in_stock',Decimal(100),'TOMAN')),
    (['موجود نیست قیمت ۲۰۰ ریال'],('out_of_stock',Decimal(200),'IRR')),
    (['قیمت ۱۰۰ تومان','ببخشید قیمت ۲۰۰ ریال'],('unknown',Decimal(200),'IRR')),
    (['قیمت ۱۰۰ تومان','اصلاح قیمت ۲۰۰'],('unknown',None,None)),
    (['قیمت ۲ میلیون تومان'],('unknown',Decimal(2000000),'TOMAN')),
    (['قیمت ۲۰۰'],('unknown',None,None)),
    (['هزینه ارسال ۱۰۰ تومان'],('unknown',None,None)),
    (['قیمت ۱۰۰ تا ۲۰۰ تومان'],('unknown',None,None)),
    (['موجود است','ببخشید موجود نیست'],('out_of_stock',None,None)),
])
def test_conservative_extraction(texts,expected):
    rows=[Segment(item_id=str(i),speaker='seller',text=t,complete=True) for i,t in enumerate(texts)]
    assert extract(rows)[:3]==expected


class Browser:
    def __init__(self,events=()):self.sent=[];self.events=events
    async def send_json(self,e):self.sent.append(e)
    async def iter_text(self):
        for e in self.events:yield json.dumps(e)
class Provider:
    def __init__(self):self.sent=[]
    async def send(self,e):self.sent.append(json.loads(e))


def test_ready_first_and_question_cap(monkeypatch):
    monkeypatch.setenv('GISOO_TRANSCRIPTION_CONFIG','{"input_audio_transcription":{"model":"provider-confirmed-placeholder"}}')
    async def run():
        c=Call(request());b=Browser();a=GisooAdapter(c,b);a.provider=Provider()
        await a.event({'type':'session.created'})
        assert c.generation_count==0 and a.provider.sent[0]['type']=='session.update'
        await a.event({'type':'session.updated'})
        assert c.generation_count==0 and not b.sent
        setup=a.provider.sent[-1]['item']
        assert setup['role']=='user' and setup['content'][0]['type']=='input_text'
        await a.event({'type':'conversation.item.added','previous_item_id':None,'item':{'id':'provider-assigned-setup','role':'user'}})
        assert not c.segments and 'provider-assigned-setup' in c.context_items
        assert c.generation_count==1 and b.sent[0]['type']=='ready'
        for i in range(6):
            await a.event({'type':'response.done','response':{'status':'completed','id':str(i)}})
            await a.event({'type':'conversation.item.input_audio_transcription.completed','item_id':str(i),'transcript':'قیمت نامشخص'})
        assert c.generation_count==3 and c.stop.is_set()
    asyncio.run(run())


def test_provider_audio_and_cancellation():
    async def run():
        c=Call(request());b=Browser();a=GisooAdapter(c,b);a.provider=Provider();a.pending_response=True
        await a.event({'type':'response.output_item.added','response_id':'r','item':{'id':'a','role':'assistant'}})
        await a.event({'type':'response.output_audio.delta','response_id':'r','delta':'AAAAAA=='})
        assert b.sent[-1]['type']=='audio'
        await a.event({'type':'input_audio_buffer.speech_started'})
        assert a.provider.sent[-1]['type']=='response.cancel'
        n=len(b.sent)
        await a.event({'type':'response.output_audio.delta','response_id':'r','delta':'AAAAAA=='})
        assert len(b.sent)==n
    asyncio.run(run())


def test_transcription_failure():
    async def run():
        c=Call(request());a=GisooAdapter(c,Browser())
        await a.event({'type':'conversation.item.input_audio_transcription.failed'})
        assert c.stop.is_set() and c.reason=='error'
    asyncio.run(run())


def test_audio_not_retained():
    async def run():
        c=Call(request());a=GisooAdapter(c,Browser());a.provider=Provider()
        await a.event({'type':'response.output_audio.delta','response_id':'r','delta':'UNIQUE_AUDIO_SENTINEL'})
        assert 'UNIQUE_AUDIO_SENTINEL' not in repr(c)
        assert 'audio' not in c.finalize('error').model_dump_json()
    asyncio.run(run())


def test_unconfigured(monkeypatch):
    for key in ['GISOO_API_KEY','GISOO_REALTIME_MODEL','CALL_EXTRACTION_MODE','GISOO_TRANSCRIPTION_CONFIG','GISOO_PROTOCOL_VERIFIED','BOXAPI_API_KEY','BOXAPI_MODEL']:monkeypatch.delenv(key,raising=False)
    assert len(configuration())==7
    monkeypatch.setenv('GISOO_REALTIME_MODEL','not-a-model');assert 'GISOO_REALTIME_MODEL' in configuration()

def test_duplicate_seller_event_does_not_generate_twice():
    async def run():
        c=Call(request());a=GisooAdapter(c,Browser());a.provider=Provider()
        event={'type':'conversation.item.input_audio_transcription.completed','item_id':'u','transcript':'موجود است'}
        await a.event(event);assert c.generation_count==1
        a.pending_response=False
        await a.event(event);assert c.generation_count==1
    asyncio.run(run())


def test_late_events_before_and_after_finalization(monkeypatch):
    monkeypatch.setenv('CALL_EXTRACTION_MODE','post_call_rules')
    async def run():
        c=complete_call();c.segments['b'].complete=False;c.segments['b'].text=None;c.stop.set()
        a=GisooAdapter(c,Browser());a.provider=Provider()
        await a.event({'type':'conversation.item.input_audio_transcription.completed','item_id':'b','transcript':'قیمت ۳۰۰ تومان'})
        result=c.finalize('manual_end');assert result.price_amount is None and result.raw_text=='قیمت ۳۰۰ تومان'
        await a.event({'type':'conversation.item.input_audio_transcription.completed','item_id':'b','transcript':'قیمت ۹۰۰ تومان'})
        assert result.price_amount is None and result.transcript[-1].text=='قیمت ۳۰۰ تومان'
    asyncio.run(run())


def test_question_cap_violation_is_not_success():
    async def run():
        c=complete_call();c.generation_count=2;a=GisooAdapter(c,Browser())
        await a.event({'type':'response.output_audio_transcript.done','item_id':'c','response_id':'r2','transcript':'رنگ؟ ضمانت؟ نقد؟'})
        assert c.reason=='error' and c.stop.is_set()
        assert c.finalize('error').status=='incomplete'
    asyncio.run(run())


def test_relay_failure_cleanup_without_audio_persistence(monkeypatch,tmp_path):
    from app import calls as module
    monkeypatch.setenv('GISOO_API_KEY','mock')
    monkeypatch.setenv('GISOO_REALTIME_MODEL','gemini-3.8-live')
    class Failure:
        async def __aenter__(self):raise ConnectionError('do not log this')
        async def __aexit__(self,*args):pass
    monkeypatch.setattr(module.websockets,'connect',lambda *a,**k:Failure())
    async def run():
        c=Call(request());b=Browser();a=GisooAdapter(c,b)
        await a.run()
        assert c.result.reason=='error' and b.sent[-1]['type']=='finalized'
        assert c.diagnostics==['relay_failed','failure_type:ConnectionError']
    asyncio.run(run())
    assert list(tmp_path.iterdir())==[]


def test_mock_end_to_end_pcm_relay(monkeypatch):
    from app import calls as module
    monkeypatch.setenv('GISOO_API_KEY','mock-secret-never-exposed')
    monkeypatch.setenv('GISOO_REALTIME_MODEL','gemini-3.8-live')
    monkeypatch.setenv('GISOO_TRANSCRIPTION_CONFIG','{"input_audio_transcription":{"model":"mock"}}')
    async def run():
        c=Call(request());server_queue=asyncio.Queue();browser_queue=asyncio.Queue();received=[]
        class FakeProvider:
            async def send(self,raw):
                e=json.loads(raw);received.append(e)
                if e['type']=='session.update':await server_queue.put({'type':'session.updated'})
                elif e['type']=='conversation.item.create':await server_queue.put({'type':'conversation.item.added','previous_item_id':None,'item':e['item']})
                elif e['type']=='response.create':
                    for event in [
                        {'type':'conversation.item.added','previous_item_id':None,'item':{'id':'a','role':'assistant'}},
                        {'type':'response.output_item.added','response_id':'r1','item':{'id':'a','role':'assistant'}},
                        {'type':'response.output_audio.delta','response_id':'r1','delta':'AAAAAA=='},
                        {'type':'response.output_audio.done','response_id':'r1'},
                        {'type':'response.output_audio_transcript.done','item_id':'a','response_id':'r1','transcript':'دستیار هوش مصنوعی ترب هستم'},
                        {'type':'response.done','response':{'id':'r1','status':'completed'}},
                    ]:await server_queue.put(event)
                elif e['type']=='input_audio_buffer.append':
                    await browser_queue.put({'type':'end'})
            def __aiter__(self):return self
            async def __anext__(self):return json.dumps(await server_queue.get())
        provider=FakeProvider()
        class Context:
            async def __aenter__(self):await server_queue.put({'type':'session.created'});return provider
            async def __aexit__(self,*a):pass
        class FakeBrowser(Browser):
            async def send_json(self,e):
                self.sent.append(e)
                if e['type']=='ready':await browser_queue.put({'type':'audio','audio':'AAAAAA=='})
                if e['type']=='audio':await browser_queue.put({'type':'played','seq':e['seq'],'epoch':e['epoch']})
            async def iter_text(self):
                while True:yield json.dumps(await browser_queue.get())
        monkeypatch.setattr(module.websockets,'connect',lambda *args,**kw:Context())
        b=FakeBrowser();a=GisooAdapter(c,b);await a.run()
        assert c.result.reason=='manual_end' and c.state=='finalized', (c.diagnostics,received,b.sent)
        assert any(e['type']=='input_audio_buffer.append' for e in received)
        assert any(e['type']=='audio' for e in b.sent)
        assert c.result.transcript_complete is False # Seller transcription was deliberately absent.
        assert 'mock-secret' not in repr(b.sent) and 'AAAA' not in repr(c)
    asyncio.run(run())



def test_uncommitted_seller_speech_is_incomplete():
    c=complete_call();c.uncommitted_speech=1
    assert not c.finalize('manual_end').transcript_complete


def test_qwen_interruption_stops_on_unsupported_context(monkeypatch):
    monkeypatch.setenv('GISOO_REALTIME_MODEL','qwen3.8-omni-flash-realtime')
    async def run():
        c=complete_call();c.played.clear();a=GisooAdapter(c,Browser());a.provider=Provider()
        await a.barge_in()
        assert c.stop.is_set() and c.reason=='error' and 'qwen_context_truncation_unsupported' in c.diagnostics
    asyncio.run(run())

@pytest.mark.parametrize('ending',['timeout','disconnected'])
def test_relay_timeout_and_disconnect_cleanup(monkeypatch,ending):
    from app import calls as module
    monkeypatch.setenv('GISOO_API_KEY','mock')
    monkeypatch.setenv('GISOO_REALTIME_MODEL','gemini-3.8-live')
    class EmptyProvider(Provider):
        def __aiter__(self):return self
        async def __anext__(self):
            if ending=='disconnected':raise StopAsyncIteration
            await asyncio.Future()
    class Context:
        async def __aenter__(self):return EmptyProvider()
        async def __aexit__(self,*args):pass
    class WaitingBrowser(Browser):
        async def iter_text(self):
            await asyncio.Future()
            yield ''
    monkeypatch.setattr(module.websockets,'connect',lambda *a,**k:Context())
    original_wait=asyncio.wait
    async def short_wait(tasks,**kwargs):return await original_wait(tasks,timeout=.01,return_when=kwargs['return_when'])
    monkeypatch.setattr(module.asyncio,'wait',short_wait)
    async def run():
        c=Call(request());b=WaitingBrowser();await GisooAdapter(c,b).run()
        assert c.result.reason==ending and c.state=='finalized' and c.stop.is_set()
        assert c.result.extraction_status=='skipped_incomplete' and b.sent[-1]['type']=='finalized'
    asyncio.run(run())
