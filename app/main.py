from __future__ import annotations
import asyncio, hashlib, hmac, os, secrets, time
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4
from dotenv import load_dotenv
from fastapi import FastAPI, Request, WebSocket, HTTPException, Depends
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from .catalog import Catalog
from .csv_catalog import CsvCatalog
from .models import Intent, Compare, Feedback, CallRequest
from .calls import Call, GisooAdapter, configuration

load_dotenv()
ROOT=Path(__file__).resolve().parent.parent
data_path=os.getenv('DATASET_PATH',str(ROOT/'dataset'))
catalog=(CsvCatalog if Path(data_path).is_dir() else Catalog)(data_path,int(os.getenv('DATA_STALE_DAYS','30')))
@asynccontextmanager
async def lifespan(app):
    async def sweep():
        while True:
            await asyncio.sleep(30)
            cleanup()
    task=asyncio.create_task(sweep())
    try: yield
    finally:
        task.cancel()
        await asyncio.gather(task,return_exceptions=True)

app=FastAPI(title='دستیار خرید حضوری ترب',version='0.1.0',lifespan=lifespan)
app.mount('/static',StaticFiles(directory=ROOT/'static'),name='static')
SECRET=secrets.token_bytes(32)
origins={s.strip().rstrip('/') for s in os.getenv('APP_ORIGINS','http://localhost:8000,http://127.0.0.1:8000').split(',')}
calls={};feedback={}


def token(user): return hmac.new(SECRET,user.encode(),hashlib.sha256).hexdigest()


@app.middleware('http')
async def bounds(request:Request,call_next):
    if request.method in ('POST','PUT','PATCH'):
        try:
            length=int(request.headers.get('content-length','0'))
        except ValueError: return JSONResponse({'detail':'invalid size'},400)
        if length>65536: return JSONResponse({'detail':'request too large'},413)
        chunks=[];size=0
        async for chunk in request.stream():
            size+=len(chunk)
            if size>65536: return JSONResponse({'detail':'request too large'},413)
            chunks.append(chunk)
        request._body=b''.join(chunks)
    user=request.cookies.get('torob_session','')
    if len(user)!=64 or any(c not in '0123456789abcdef' for c in user): user=secrets.token_hex(32)
    request.state.user=user
    request.state.style_nonce=secrets.token_urlsafe(18)
    response=await call_next(request)
    response.set_cookie('torob_session',user,httponly=True,samesite='strict',secure=os.getenv('COOKIE_SECURE')=='true',max_age=3600)
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Content-Security-Policy']=f"default-src 'self'; script-src 'self'; style-src 'self' 'nonce-{request.state.style_nonce}'; connect-src 'self'; media-src 'self' blob:; object-src 'none'; frame-ancestors 'none'"
    response.headers['Referrer-Policy']='no-referrer'
    response.headers['Cache-Control']='no-store'
    return response


def write_access(request:Request):
    origin=request.headers.get('origin')
    if origin and origin.rstrip('/') not in origins: raise HTTPException(403,'origin rejected')
    if not hmac.compare_digest(request.headers.get('x-app-token',''),token(request.state.user)):
        raise HTTPException(403,'برنامه را بازخوانی کنید؛ توکن درخواست نامعتبر است')


def owned(session_id,user):
    cleanup()
    item=calls.get(session_id)
    if not item or item['owner']!=user: raise HTTPException(404,'جلسه یافت نشد')
    return item['call']


def cleanup():
    now=time.monotonic()
    for sid in list(calls):
        c=calls[sid]['call']
        if c.state=='created' and now-c.created>120:
            c.finalize('timeout')
        if now-c.created>3600 and not c.active: del calls[sid]
    for fid in list(feedback):
        if now-feedback[fid]['created']>3600: del feedback[fid]


@app.get('/')
def home(request:Request):
    built_ui=ROOT/'static/ui/index.html'
    if built_ui.is_file():
        return HTMLResponse(built_ui.read_text(encoding='utf-8').replace('__CSP_NONCE__',request.state.style_nonce))
    return FileResponse(ROOT/'static/index.html')


@app.get('/health')
def health(): return {'status':'ok','products':catalog.filters()['products'],'offers':len(catalog.products),'storage':'development_memory'}


@app.get('/api/config')
def config(request:Request):
    return {'csrf_token':token(request.state.user),'call_configured':not configuration(),'call_missing':configuration(),
            'storage':'development_memory','retention_seconds':3600,'coverage':catalog.filters()}


@app.get('/api/catalog/filters')
def filters(): return catalog.filters()


@app.post('/api/chat',dependencies=[Depends(write_access)])
def chat(body:Intent): return catalog.search(body)


@app.post('/api/compare',dependencies=[Depends(write_access)])
def compare(body:Compare):
    if any(i not in catalog.products for i in body.ids): raise HTTPException(404,'محصول یافت نشد')
    return catalog.compare(body.ids)


def save_feedback(kind,body,request):
    cleanup()
    if body.product_id not in catalog.products: raise HTTPException(404,'محصول یافت نشد')
    if kind=='purchase' and not body.purchased: raise HTTPException(422,'ابتدا خرید را تأیید کنید')
    if len(feedback)>=500: raise HTTPException(429,'ظرفیت موقت تکمیل است')
    fid=uuid4().hex
    feedback[fid]={'owner':request.state.user,'kind':kind,'body':body.model_dump(),'created':time.monotonic()}
    return {'id':fid,'kind':kind,'persistent':False,'retention_seconds':3600}


@app.post('/api/feedback/visit',dependencies=[Depends(write_access)])
def visit(body:Feedback,request:Request): return save_feedback('visit',body,request)


@app.post('/api/feedback/purchase',dependencies=[Depends(write_access)])
def purchase(body:Feedback,request:Request): return save_feedback('purchase',body,request)


@app.delete('/api/feedback/{feedback_id}',dependencies=[Depends(write_access)])
def delete_feedback(feedback_id:str,request:Request):
    cleanup()
    if feedback_id not in feedback or feedback[feedback_id]['owner']!=request.state.user: raise HTTPException(404,'یافت نشد')
    del feedback[feedback_id]
    return {'deleted':True}


@app.post('/api/calls',dependencies=[Depends(write_access)])
def create_call(body:CallRequest,request:Request):
    cleanup()
    access=os.getenv('CALL_DEMO_ACCESS_TOKEN','')
    if access and not hmac.compare_digest(request.headers.get('x-call-access',''),access):
        raise HTTPException(403,'رمز دسترسی دمو نامعتبر است')
    p=catalog.products.get(body.offer_id or body.product.id);s=catalog.stores.get(body.store.id)
    if not p or not s or p.store_id!=s.id or (p.product_id or p.id)!=body.product.id: raise HTTPException(422,'ارتباط معتبر محصول و فروشگاه موجود نیست')
    if p.name!=body.product.name or p.attributes!=body.product.attributes or s.name!=body.store.name:
        raise HTTPException(422,'اطلاعات کارت با دادهٔ مرجع تطابق ندارد')
    missing=configuration()
    if missing: raise HTTPException(503,{'state':'unconfigured','missing':missing})
    if len(calls)>=50 or sum(v['call'].state!='finalized' for v in calls.values())>=3 or any(v['owner']==request.state.user and v['call'].state!='finalized' for v in calls.values()):
        raise HTTPException(429,'ظرفیت جلسه تکمیل است؛ جلسهٔ قبلی را پایان دهید')
    c=Call(body);calls[c.id]={'call':c,'owner':request.state.user}
    return {'session_id':c.id,'state':c.state,'ws_path':f'/ws/calls/{c.id}'}


@app.post('/api/calls/{session_id}/end',dependencies=[Depends(write_access)])
def end_call(session_id:str,request:Request):
    c=owned(session_id,request.state.user)
    if c.state!='finalized':
        c.reason='manual_end';c.stop.set()
        if not c.active: c.finalize('manual_end')
    return {'session_id':c.id,'state':c.state}


@app.get('/api/calls/{session_id}/result')
def result(session_id:str,request:Request):
    c=owned(session_id,request.state.user)
    if c.result is None or c.state!='finalized': raise HTTPException(409,'جلسه هنوز نهایی نشده است')
    return c.result


@app.websocket('/ws/calls/{session_id}')
async def call_socket(ws:WebSocket,session_id:str):
    if ws.headers.get('origin','').rstrip('/') not in origins:
        await ws.close(code=1008);return
    try: c=owned(session_id,ws.cookies.get('torob_session',''))
    except HTTPException:
        await ws.close(code=1008);return
    if c.active or c.state!='created' or time.monotonic()-c.created>120:
        await ws.close(code=1008);return
    await ws.accept();c.active=True
    try: await GisooAdapter(c,ws).run()
    finally:
        c.active=False
        try: await ws.close()
        except RuntimeError: pass
