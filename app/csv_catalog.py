from __future__ import annotations
import csv, json, sqlite3, re
from collections import Counter
from collections.abc import Mapping
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from .catalog import Catalog, rephrase
from .models import Product, Store, normalize, safe_product_image


def value(v): return v if isinstance(v,str) and v.strip() and v.strip()!='null' else None


def product_image(row):
    try: urls=json.loads(row.get('image_urls','null'))
    except (ValueError,TypeError): return None
    if not isinstance(urls,list): return None
    return next((safe for url in urls[:20] if (safe:=safe_product_image(url))),None)


def attributes(row):
    result={}
    for column,label in [('brand_name','برند'),('model','مدل')]:
        v=value(row.get(column))
        if v and len(v)<=200: result[label]=v
    try: specs=json.loads(row.get('specs','null'))
    except ValueError: specs=None
    conflicts=set()
    if isinstance(specs,list):
        for spec in specs:
            if not isinstance(spec,dict): continue
            k,v=value(spec.get('key')),value(spec.get('value'))
            if not k or not v or len(k)>80 or len(v)>200 or k in conflicts: continue
            if k in result and result[k]!=v:
                result.pop(k);conflicts.add(k)
            elif len(result)<20: result[k]=v
    return result


class ListingMap(Mapping):
    def __init__(self,catalog): self.catalog=catalog
    def __len__(self): return self.catalog.count
    def __iter__(self):
        return (r[0] for r in self.catalog.db.execute('SELECT id FROM offers ORDER BY id'))
    def __getitem__(self,key):
        row=self.catalog.db.execute('SELECT o.*,p.name,p.category,p.attributes,p.image_url FROM offers o JOIN products p ON p.id=o.pid WHERE o.id=?',(key,)).fetchone()
        if not row: raise KeyError(key)
        return Product(id=row['id'],product_id=row['pid'],name=row['name'],category=row['category'],source='dataset/offers.csv:'+row['id'],
            store_id=row['sid'],attributes=json.loads(row['attributes']),price=row['price'],currency='TOMAN' if row['price'] else None,updated_at=row['changed'],image_url=row['image_url'])
    def __contains__(self,key): return self.catalog.db.execute('SELECT 1 FROM offers WHERE id=?',(key,)).fetchone() is not None


class CsvCatalog(Catalog):
    """Read CSV once into SQLite :memory:. No durable database or raw data writes."""
    def __init__(self,path,stale_days=30):
        self.stale_days=stale_days;self.issues=[];self.stores={};self.count=0
        self.db=sqlite3.connect(':memory:',check_same_thread=False)
        self.db.row_factory=sqlite3.Row
        self.db.executescript('CREATE TABLE products(id TEXT PRIMARY KEY,name TEXT,category TEXT,attributes TEXT,nname TEXT,ncat TEXT,search TEXT,image_url TEXT); CREATE TABLE offers(id TEXT PRIMARY KEY,pid TEXT,sid TEXT,price TEXT,changed TEXT);')
        directory=Path(path);stats=Counter();brands=Counter()
        def rows(name,required):
            f=(directory/name).open(encoding='utf-8-sig',newline='')
            reader=csv.DictReader(f)
            if not required.issubset(set(reader.fieldnames or [])):
                f.close();raise ValueError(f'invalid columns in {name}')
            try: yield from reader
            finally: f.close()
        try:
            seen_stores=set()
            for row in rows('shops.csv',{'shop_id','name'}):
                try:
                    s=Store(id=row['shop_id'],name=row['name'],source='dataset/shops.csv:'+row['shop_id'],
                        address=row.get('address'),location_label=row.get('location_label'),
                        location={'latitude':row.get('lat'),'longitude':row.get('lon')})
                    if s.id in seen_stores:
                        stats['duplicate_store']+=1;self.stores.pop(s.id,None);continue
                    seen_stores.add(s.id)
                    self.stores[s.id]=s
                except ValueError: stats['invalid_store']+=1
            batch=[]
            for row in rows('products.csv',{'product_id','persian_title','category_name','specs'}):
                pid,name,cat=value(row.get('product_id')),value(row.get('persian_title')),value(row.get('category_name'))
                if not pid or len(pid)>100 or not name or len(name)>200 or not cat or len(cat)>100:
                    stats['invalid_product']+=1;continue
                attrs=attributes(row)
                if 'برند' in attrs: brands[attrs['برند']]+=1
                batch.append((pid,name,cat,json.dumps(attrs,ensure_ascii=False),normalize(name),normalize(cat),normalize(' '.join([name,cat,*attrs.values()])),product_image(row)))
                if len(batch)>=1000:
                    self.db.executemany('INSERT INTO products VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET name=NULL',batch);batch=[]
            self.db.executemany('INSERT INTO products VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET name=NULL',batch)
            stats['conflicting_product_ids']=self.db.execute('SELECT COUNT(*) FROM products WHERE name IS NULL').fetchone()[0]
            self.db.execute('DELETE FROM products WHERE name IS NULL')
            product_ids={r[0] for r in self.db.execute('SELECT id FROM products')}
            batch=[]
            for row in rows('offers.csv',{'offer_id','shop_id','product_id','price_toman','last_price_changed_at'}):
                oid,pid,sid=value(row.get('offer_id')),value(row.get('product_id')),value(row.get('shop_id'))
                if not oid or len(oid)>100 or pid not in product_ids or sid not in self.stores:
                    stats['invalid_or_orphan_offer']+=1;continue
                price=changed=None
                try:
                    raw=value(row.get('price_toman'))
                    if raw is not None:
                        p=Decimal(raw)
                        if not p.is_finite() or p<0 or p>10**15: raise ValueError()
                        price=str(p)
                except (ValueError,InvalidOperation): stats['invalid_price']+=1
                try:
                    raw=value(row.get('last_price_changed_at'))
                    if raw:
                        dt=datetime.fromisoformat(raw)
                        if dt.tzinfo is None or dt>datetime.now(timezone.utc): raise ValueError()
                        changed=dt.isoformat()
                except ValueError: stats['invalid_date']+=1
                batch.append((oid,pid,sid,price,changed))
                if len(batch)>=2000:
                    self.db.executemany('INSERT INTO offers VALUES(?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET pid=NULL',batch);batch=[]
            self.db.executemany('INSERT INTO offers VALUES(?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET pid=NULL',batch)
            stats['conflicting_offer_ids']=self.db.execute('SELECT COUNT(*) FROM offers WHERE pid IS NULL').fetchone()[0]
            self.db.execute('DELETE FROM offers WHERE pid IS NULL')
            self.db.executescript('CREATE INDEX offer_pid ON offers(pid); CREATE INDEX product_category ON products(ncat);')
            self.count=self.db.execute('SELECT COUNT(*) FROM offers').fetchone()[0]
            self.raw_products=self.db.execute('SELECT COUNT(*) FROM products').fetchone()[0]
            self.db.commit()
        except (OSError,ValueError,csv.Error):
            self.issues.append('csv_load_failed');self.db.execute('DELETE FROM offers');self.count=0
        self.issues.extend(f'{k}:{v}' for k,v in sorted(stats.items()) if v)
        self.products=ListingMap(self)
        cats=[r[0] for r in self.db.execute('SELECT DISTINCT p.category FROM products p JOIN offers o ON o.pid=p.id ORDER BY p.category')]
        self._filters={'categories':cats,'attributes':{'برند':sorted(brands,key=lambda b:(-brands[b],b))[:100]},
            'currencies':['TOMAN'] if self.count else [],'installments':False,'stock':False,
            'products':getattr(self,'raw_products',0),'offers':self.count,'stores':len(self.stores),'issues':self.issues,
            'demo_records':0,'note':'پرداخت‌های فروشگاه تأیید اقساط کالا نیست؛ موجودی و نقد کاربران موجود نیست. تاریخ فقط زمان تغییر قیمت است.'}

    def filters(self): return self._filters

    def effective(self,p):
        row=super().effective(p)
        row['recorded_price']=str(p.price) if p.price is not None else None
        row['price_timestamp_kind']='last_price_changed_at'
        return row

    def search(self,intent):
        cats={normalize(c) for c in self._filters['categories']}
        if intent.category and normalize(intent.category) not in cats:
            return {'state':'unsupported','message':'این دسته در داده‌های موجود پوشش ندارد.','items':[]}
        q=normalize(intent.query)
        if any(w in q for w in ('نظر کاربران','نظرات','امتیاز','reviews')):
            return {'state':'unsupported','message':'دادهٔ نقد و نظر کاربران در دسترس نیست.','items':[]}
        if intent.installments_only or 'اقساط' in q or 'قسطی' in q or intent.in_stock_only or 'فقط موجود' in q:
            return {'state':'empty','message':'دادهٔ تأییدشدهٔ اقساط یا موجودی کالا نداریم؛ محدودیت شما حفظ شده است.','items':[]}
        q=rephrase(q)
        if any(term in q for term in ('زیر ','بالای ','ارزان تر از','حداکثر ','حداقل ')):
            return {'state':'clarification','message':'محدودیت قیمت را از فیلتر مبلغ و واحد وارد کنید؛ جست‌وجو هنوز اجرا نشده است.','items':[]}
        if intent.max_price is not None and intent.currency!='TOMAN':
            return {'state':'empty','message':'قیمت با واحد انتخاب‌شده نداریم؛ تبدیل ضمنی انجام نشد.','items':[]}
        clauses=[];params=[]
        for t in q.split(): clauses.append('instr(p.search,?)>0');params.append(t)
        if intent.category: clauses.append('p.ncat=?');params.append(normalize(intent.category))
        for k,v in intent.attributes.items():
            # Keys and values are data parameters, never SQL identifiers or paths.
            clauses.append('EXISTS(SELECT 1 FROM json_each(p.attributes) a WHERE a.key=? AND a.value=?)');params.extend([k,v])
        if intent.max_price is not None:
            from datetime import timedelta
            cutoff=(datetime.now(timezone.utc)-timedelta(days=self.stale_days)).isoformat()
            clauses.extend(['o.price IS NOT NULL','CAST(o.price AS REAL)<=?','o.changed>=?']);params.extend([float(intent.max_price),cutoff])
        where=' AND '.join(clauses) or '1'
        # Fixed scoring and stable offer ID tie-break. q is bound, including metacharacters.
        score='(CASE WHEN p.nname=? AND ?<>\'\' THEN 100 ELSE 0 END + CASE WHEN instr(p.nname,?)>0 AND ?<>\'\' THEN 40 ELSE 0 END + CASE WHEN p.ncat=? AND ?<>\'\' THEN 20 ELSE 0 END)'
        score_params=[q,q,q,q,q,q]
        for t in q.split(): score+=' + CASE WHEN instr(p.nname,?)>0 THEN 5 ELSE 0 END';score_params.append(t)
        sql=f'SELECT o.id,({score}) AS score FROM products p JOIN offers o ON o.pid=p.id WHERE {where} ORDER BY score DESC,o.id LIMIT ?'
        items=[]
        for hit in self.db.execute(sql,score_params+params+[intent.limit]).fetchall():
            row=self.effective(self.products[hit['id']]);row['score']=hit['score']+10*len(intent.attributes)
            row['why']='مطابق جست‌وجو و ویژگی‌های انتخابی شما.'
            items.append(row)
        return {'state':'results' if items else 'empty','message':'محصولات پیشنهادی را ببینید و گزینهٔ موردنظرتان را انتخاب کنید.' if items else 'محصولی با این مشخصات پیدا نشد. می‌توانید ویژگی‌ها یا محدودیت‌های جست‌وجو را تغییر دهید.','items':items}
