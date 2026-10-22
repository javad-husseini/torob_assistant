from pathlib import Path
import csv,json,hashlib,time
from app.csv_catalog import CsvCatalog
from app.models import Intent
start=time.monotonic();c=CsvCatalog('dataset');f=c.filters()
report={k:v for k,v in f.items() if k not in ('categories','attributes')}
report['categories']=len(f['categories']);report['load_seconds']=round(time.monotonic()-start,2)
report['raw_files']={}
for p in Path('dataset').glob('*.csv'):
    digest=hashlib.sha256()
    with p.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):digest.update(block)
    report['raw_files'][p.name]={'bytes':p.stat().st_size,'sha256':digest.hexdigest()}
report['sample_search']={'query':'لنز سونی','ids':[r['id'] for r in c.search(Intent(query='لنز سونی',limit=3))['items']]}
Path('docs/data-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=True))
