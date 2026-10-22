"""Local shadcn UI checks. Never starts a provider call or captures audio."""
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

ROOT=Path(__file__).resolve().parent.parent
with sync_playwright() as p:
    browser=p.chromium.launch(channel='chrome',headless=True)
    page=browser.new_page(viewport={'width':1440,'height':1050},locale='fa-IR')
    errors=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.on('console',lambda m:errors.append(m.text) if m.type=='error' else None)
    page.route('**/api/calls',lambda route:route.abort()) # No live-call creation is permitted in this test.
    page.goto('http://127.0.0.1:8000',wait_until='networkidle')
    expect(page.locator('#coverage')).to_contain_text('محصول')
    expect(page.locator('#hero-title')).to_be_visible()
    assert page.locator('html').get_attribute('dir')=='rtl'
    page.screenshot(path=str(ROOT/'docs/ui-home.png'),full_page=True)
    page.get_by_role('button',name='حالت تاریک',exact=True).click()
    expect(page.locator('html')).to_have_class('dark')
    page.screenshot(path=str(ROOT/'docs/ui-dark.png'),full_page=True)
    page.get_by_role('button',name='حالت روشن',exact=True).click()
    page.locator('#category').click()
    page.locator('[cmdk-input]').fill('لنز')
    page.get_by_role('option',name='لنز دوربین',exact=True).click()
    page.locator('#query').fill('لنز سونی');page.locator('#search-button').click()
    expect(page.locator('.product-card').first).to_be_visible()
    assert page.locator('.product-card').count()>1
    page.locator('.product-card').nth(0).get_by_role('checkbox').click()
    page.locator('.product-card').nth(1).get_by_role('checkbox').click()
    page.locator('#compare').click()
    expect(page.locator('#comparison')).to_be_visible()
    assert page.locator('#compare-content table tr').count()>3
    page.locator('#comparison').get_by_role('button',name='بستن',exact=True).click()
    page.locator('.product-card').first.get_by_role('button',name='استعلام از فروشگاه').click()
    expect(page.locator('#call .notice')).to_have_text('دموی تماس مرورگری است؛ تماس تلفنی واقعی برقرار نمی‌شود و شما نقش فروشنده را دارید.')
    assert page.locator('#call input[type=password]').count()==0
    page.locator('#close-call').click()
    page.locator('.product-card').first.get_by_role('button',name='ثبت تجربهٔ بازدید یا خرید').click()
    page.locator('#feedback-kind').get_by_role('radio',name='پس از خرید').click()
    page.locator('#feedback-text').fill('بازخورد آزمایشی مرورگر')
    page.locator('#consent').click()
    page.locator('#feedback-form').get_by_role('button',name='ثبت بازخورد',exact=True).click()
    expect(page.locator('#feedback-status')).to_contain_text('خرید')
    page.locator('#purchased').click()
    page.locator('#feedback-form').get_by_role('button',name='ثبت بازخورد',exact=True).click()
    expect(page.locator('#delete-feedback')).to_be_visible()
    page.locator('#delete-feedback').click()
    expect(page.locator('#feedback-status')).to_contain_text('حذف')
    page.locator('#feedback').get_by_role('button',name='بستن',exact=True).click()
    page.screenshot(path=str(ROOT/'docs/desktop.png'),full_page=True)
    page.locator('#installments').click()
    page.locator('#filters').get_by_role('button',name='اعمال فیلترها').click()
    expect(page.locator('#status')).to_contain_text('تأییدشده')
    assert page.locator('.product-card').count()==0
    page.set_viewport_size({'width':390,'height':844})
    page.goto('http://127.0.0.1:8000',wait_until='networkidle')
    page.screenshot(path=str(ROOT/'docs/mobile.png'),full_page=True)
    assert page.evaluate('() => document.documentElement.scrollWidth<=window.innerWidth')
    page.locator('.mobile-filter-button button').click()
    expect(page.locator('[data-slot=sheet-content]')).to_be_visible()
    page.locator('#mobile-installments').click()
    page.locator('#mobile-filters').get_by_role('button',name='اعمال فیلترها').click()
    expect(page.locator('#status')).to_contain_text('تأییدشده')
    page.screenshot(path=str(ROOT/'docs/ui-mobile-filtered.png'),full_page=True)
    page.locator('.mobile-filter-button button').click()
    page.locator('#mobile-installments').click()
    page.locator('#mobile-filters').get_by_role('button',name='اعمال فیلترها').click()
    expect(page.locator('.product-card').first).to_be_visible()
    assert page.evaluate('() => document.documentElement.scrollWidth<=window.innerWidth')
    page.locator('#query').fill('نظرات');page.locator('#search-button').click()
    expect(page.locator('#status')).to_contain_text('نقد')
    assert not errors,errors
    browser.close()
    print('Browser checks passed: shadcn RTL, local font/theme, searchable categories, real search, comparison, call disclaimer/no password, feedback consent/purchase/deletion, unknown installment exclusion, mobile filters, reviews, no overflow/console errors. No provider requests.')
