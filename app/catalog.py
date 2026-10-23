from __future__ import annotations
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from pydantic import ValidationError
from .models import Product, Store, Intent, normalize


class Catalog:
    """Read-only JSON adapter. No filesystem mutation, network retrieval or inferred facts."""
    def __init__(self, path: str, stale_days: int = 30):
        self.products = {}
        self.stores = {}
        self.issues = []
        self.stale_days = stale_days
        file = Path(path)
        if not file.exists():
            self.issues.append('dataset_missing')
            return
        if file.stat().st_size > 20_000_000:
            self.issues.append('dataset_too_large')
            return
        try:
            data = json.loads(file.read_text(encoding='utf-8-sig'))
            if not isinstance(data, dict) or set(data)-{'products','stores'}:
                raise ValueError()
            for key in ('products','stores'):
                if not isinstance(data.get(key, []), list): raise ValueError()
        except (OSError,ValueError):
            self.issues.append('dataset_invalid')
            return
        for key, model, target in [('stores',Store,self.stores),('products',Product,self.products)]:
            seen = set()
            for index, row in enumerate(data.get(key, [])):
                if not isinstance(row, dict):
                    self.issues.append(f'{key}:{index}:invalid_row'); continue
                row = dict(row)
                # Invalid optional facts become unknown; malformed identities are quarantined.
                if model is Product:
                    for field in ('price','currency','stock','installments','updated_at','attributes','store_id'):
                        if field not in row: continue
                        try:
                            model.model_validate({**row, **{k:v for k,v in {'price':None,'currency':None,'stock':'unknown','installments':'unknown','updated_at':None,'attributes':{},'store_id':None}.items() if k!=field}})
                        except ValidationError as e:
                            if any(err['loc'] and err['loc'][0] == field for err in e.errors()):
                                row[field] = {'stock':'unknown','installments':'unknown','attributes':{}}.get(field)
                                self.issues.append(f'{key}:{index}:{field}:unknown')
                try:
                    item = model.model_validate(row)
                    if item.id in seen:
                        target.pop(item.id, None)
                        self.issues.append(f'{key}:{index}:duplicate_id')
                        continue
                    seen.add(item.id)
                    target[item.id] = item
                except ValidationError:
                    self.issues.append(f'{key}:{index}:invalid_row')
        for p in self.products.values():
            if p.store_id and p.store_id not in self.stores:
                p.store_id = None
                self.issues.append('orphan_store')
            if p.store_id and self.stores[p.store_id].demo != p.demo:
                p.store_id = None
                self.issues.append('demo_provenance_conflict')

    def effective(self, p):
        result = p.model_dump(mode='json')
        fresh = p.updated_at is not None and datetime.now(timezone.utc)-p.updated_at <= timedelta(days=self.stale_days)
        result['freshness'] = 'dated' if fresh else 'unknown_or_stale'
        if not fresh:
            result.update(price=None,currency=None,stock='unknown',installments='unknown')
        if result['price'] is None or result['currency'] is None:
            result.update(price=None,currency=None)
        result['store'] = self.stores[p.store_id].model_dump() if p.store_id else None
        result['reviews'] = None
        result['call_eligible'] = bool(p.store_id)
        return result

    def filters(self):
        rows = [self.effective(p) for p in self.products.values()]
        return {'categories':sorted({p.category for p in self.products.values()}),
                'attributes':{k:sorted({p.attributes[k] for p in self.products.values() if k in p.attributes}) for k in sorted({k for p in self.products.values() for k in p.attributes})},
                'currencies':sorted({p['currency'] for p in rows if p['currency']}),
                'installments':any(p['installments']=='yes' for p in rows),
                'stock':any(p['stock']!='unknown' for p in rows),
                'products':len(rows),'stores':len(self.stores),'issues':self.issues[:100],
                'demo_records':sum(p.demo for p in self.products.values())}

    def search(self, intent: Intent):
        filters = self.filters()
        cats = {normalize(c) for c in filters['categories']}
        if intent.category and normalize(intent.category) not in cats:
            return {'state':'unsupported','message':'این دسته در داده‌های موجود پوشش ندارد.','items':[]}
        q = normalize(intent.query)
        if any(w in q for w in ('نظر کاربران','نظرات','امتیاز','reviews')):
            return {'state':'unsupported','message':'دادهٔ نقد و نظر کاربران در دسترس نیست.','items':[]}
        apparel = ('لباس','پوشاک','مانتو','شلوار','پیراهن','کفش')
        if any(w in q for w in apparel) and not any(w in c for c in cats for w in apparel):
            return {'state':'unsupported','message':'پوشاک در داده‌های موجود پوشش ندارد؛ اطلاعات مکانی معتبری برای پیشنهاد محدوده نداریم.','items':[]}
        # Interpret only supported deterministic phrases. Keep other terms mandatory.
        only_installments = intent.installments_only or 'اقساط' in q or 'قسطی' in q
        only_stock = intent.in_stock_only or 'فقط موجود' in q
        q = rephrase(q)
        if any(term in q for term in ('زیر ', 'بالای ', 'ارزان تر از', 'حداکثر ', 'حداقل ')):
            return {'state':'clarification','message':'محدودیت قیمت را در فیلتر مبلغ و واحد مشخص کنید؛ هنوز جست‌وجو اجرا نشده است.','items':[]}
        tokens = q.split()
        matches=[]
        for p in self.products.values():
            row=self.effective(p)
            if intent.category and normalize(p.category)!=normalize(intent.category): continue
            if only_installments and row['installments']!='yes': continue
            if only_stock and row['stock']!='in_stock': continue
            if intent.max_price is not None:
                if row['price'] is None or row['currency']!=intent.currency or p.price>intent.max_price: continue
            if any(normalize(p.attributes.get(k,''))!=normalize(v) for k,v in intent.attributes.items()): continue
            name,cat=normalize(p.name),normalize(p.category)
            hay=' '.join([name,cat,*map(normalize,p.attributes.values())])
            if not all(t in hay for t in tokens): continue
            score=(100 if q and q==name else 0)+(40 if q and q in name else 0)+(20 if q and q==cat else 0)+sum(5 for t in tokens if t in name)+10*len(intent.attributes)
            row['score']=score
            row['why']='مطابق جست‌وجو و ویژگی‌های انتخابی شما.'
            matches.append(row)
        matches.sort(key=lambda r:(-r['score'],r['id']))
        return {'state':'results' if matches else 'empty','message':'محصولات پیشنهادی را ببینید و گزینهٔ موردنظرتان را انتخاب کنید.' if matches else 'محصولی با این مشخصات پیدا نشد. می‌توانید ویژگی‌ها یا محدودیت‌های جست‌وجو را تغییر دهید.','items':matches[:intent.limit]}

    def compare(self, ids):
        rows=[self.effective(self.products[i]) for i in ids]
        currencies={r['currency'] for r in rows if r['currency']}
        return {'items':rows,'price_comparable':len(currencies)==1 and all(r['price'] is not None for r in rows),
                'note':'تبدیل واحد انجام نمی‌شود؛ خیر با نامشخص متفاوت است. ویژگی‌ها فقط با کلید و مقدار ثبت‌شده نمایش داده می‌شوند.'}


def rephrase(q):
    for term in ('فقط اقساطی','اقساطی','قسطی','فقط موجود','اقساط'):
        q=q.replace(term,' ')
    for term in ('می خواهم','می خوام','نشان بده','پیدا کن','لطفا'):
        q=q.replace(term,' ')
    return ' '.join(q.split())
