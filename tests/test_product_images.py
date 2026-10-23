import csv
import json
import pytest
from app.csv_catalog import CsvCatalog
from app.models import safe_product_image, Intent


@pytest.mark.parametrize('url',[
    'javascript:alert(1)', 'data:image/svg+xml,test',
    'https://image.torob.com.evil.example/base/images/x.jpg',
    'https://user:secret@image.torob.com/base/images/x.jpg',
    'http://image.torob.com/base/images/x.jpg',
    'https://image.torob.com:444/base/images/x.jpg', None,
])
def test_untrusted_image_urls_not_sent_to_client(url):
    assert safe_product_image(url) is None


def test_csv_image_belongs_to_selected_product_and_raw_data_is_unchanged(tmp_path):
    image='https://image.torob.com/base/images/test-product.jpg'
    files={
        'shops.csv':[{'shop_id':'shop','name':'shop'}],
        'products.csv':[
            {'product_id':'p1','persian_title':'first','category_name':'phone','specs':'null','image_urls':json.dumps(['https://evil.example/track',image])},
            {'product_id':'p2','persian_title':'second','category_name':'phone','specs':'null','image_urls':'null'},
        ],
        'offers.csv':[
            {'offer_id':'o1','product_id':'p1','shop_id':'shop','price_toman':'null','last_price_changed_at':'null'},
            {'offer_id':'o2','product_id':'p2','shop_id':'shop','price_toman':'null','last_price_changed_at':'null'},
        ],
    }
    for name,rows in files.items():
        with (tmp_path/name).open('w',encoding='utf-8',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=rows[0].keys());writer.writeheader();writer.writerows(rows)
    before={name:(tmp_path/name).read_bytes() for name in files}
    catalog=CsvCatalog(tmp_path)
    assert catalog.search(Intent(query='first'))['items'][0]['image_url']==image
    assert catalog.search(Intent(query='second'))['items'][0]['image_url'] is None
    assert catalog.compare(['o1','o2'])['items'][0]['image_url']==image
    assert before=={name:(tmp_path/name).read_bytes() for name in files}
