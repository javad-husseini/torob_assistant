import os
os.environ['DATASET_PATH']='data/catalog.json'
import json
import pytest
from datetime import datetime,timezone
from app.catalog import Catalog

@pytest.fixture
def dataset(tmp_path):
    now=datetime.now(timezone.utc).isoformat()
    data={'stores':[{'id':'s1','name':'فروشگاه آزمایشی','source':'test','demo':True}], 'products':[]}
    for i,status in enumerate(['yes','no','unknown']):
        data['products'].append({'id':f'p{i}','name':f'گوشی سونی مدل {i}','category':'گوشی','store_id':'s1','source':'test','demo':True,'price':100+i,'currency':'TOMAN','installments':status,'stock':'in_stock' if i==0 else 'unknown','updated_at':now,'attributes':{'وزن':'100 گرم'}})
    path=tmp_path/'data.json';path.write_text(json.dumps(data),encoding='utf-8')
    return path,data

@pytest.fixture
def catalog(dataset):return Catalog(str(dataset[0]))
