"""Manual, local browser checks. No provider connection or audio capture."""
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parent.parent
with sync_playwright() as p:
    browser=p.chromium.launch(channel='chrome',headless=True)
    page=browser.new_page(viewport={'width':1366,'height':900},locale='fa-IR')
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto('http://127.0.0.1:8000');page.wait_for_function('() => document.querySelector("#coverage").textContent.includes("محصول")')
    assert page.locator('html').get_attribute('dir')=='rtl'
    page.locator('#query').fill('لنز سونی');page.locator('#search-button').click();page.wait_for_selector('.card')
    assert page.locator('.card').count()>1
    page.locator('.card input[type=checkbox]').nth(0).check();page.locator('.card input[type=checkbox]').nth(1).check();page.locator('#compare').click()
    page.wait_for_selector('#comparison[open]');assert page.locator('#compare-content table tr').count()>3
    page.locator('[data-close=comparison]').click()
    page.locator('.card button').filter(has_text='استعلام از فروشگاه').first.click()
    assert page.locator('#call .notice').inner_text()=='دموی تماس مرورگری است؛ تماس تلفنی واقعی برقرار نمی‌شود و شما نقش فروشنده را دارید.'
    assert page.locator('#start-call').is_disabled()
    page.locator('#close-call').click()
    page.locator('.card button').filter(has_text='ثبت تجربه').first.click()
    page.locator('#feedback-kind').select_option('purchase');page.locator('#feedback-text').fill('بازخورد آزمایشی مرورگر');page.locator('#consent').check();page.locator('#feedback-form button').click()
    page.wait_for_function('() => document.querySelector("#feedback-status").textContent.includes("خرید")')
    page.locator('#purchased').check();page.locator('#feedback-form button').click();page.wait_for_selector('#delete-feedback:not([hidden])')
    page.locator('#delete-feedback').click();page.wait_for_function('() => document.querySelector("#feedback-status").textContent.includes("حذف")');page.locator('[data-close=feedback]').click()
    page.screenshot(path=str(ROOT/'docs/desktop.png'),full_page=True)
    page.locator('#installments').check();page.locator('#filters button').click();page.wait_for_function('() => document.querySelector("#status").textContent.includes("تأییدشده")')
    assert page.locator('.card').count()==0
    page.set_viewport_size({'width':390,'height':844});page.screenshot(path=str(ROOT/'docs/mobile.png'),full_page=True)
    assert page.evaluate('document.documentElement.scrollWidth<=window.innerWidth')
    page.locator('#installments').uncheck();page.locator('#query').fill('نظرات');page.locator('#search-button').click();page.wait_for_function('() => document.querySelector("#status").textContent.includes("نقد")')
    assert not errors,errors
    browser.close()
    print('Browser checks passed: RTL, real search, compare, call unconfigured, feedback consent/purchase/deletion, installment unknown exclusion, reviews, mobile width; no provider requests.')

