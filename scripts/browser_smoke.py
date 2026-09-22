import json
import re
import argparse
import shutil
from pathlib import Path
from playwright.sync_api import sync_playwright, expect
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description="Optional browser/UI smoke checks; start backend and static frontend first.")
parser.add_argument("--backend-base-url",default="http://127.0.0.1:8080")
parser.add_argument("--frontend-url",default="http://localhost:5500/")
parser.add_argument("--chromium",default=shutil.which("chromium"))
parser.add_argument("--inline-local-render",action="store_true",help="Render supplied local sources in about:blank instead of navigating. HTTP still goes to the backend.")
args=parser.parse_args()
(ROOT/'reports').mkdir(exist_ok=True)
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path=args.chromium,args=['--no-sandbox'])
    context=browser.new_context(viewport={"width":1440,"height":1050},device_scale_factor=1)

    page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    if args.inline_local_render:
        # System Chromium blocks all URL navigation. Render the local sources in
        # about:blank; no browser policy is modified. HTTP integration is tested
        # separately and these DOM tests use the exact source modules concatenated.
        markup=(ROOT/'frontend/index.html').read_text()
        markup=re.sub(r'<script[^>]*>.*?</script>', '', markup, flags=re.S)
        markup=re.sub(r'<link[^>]*>', '', markup)
        page.set_content(markup)
        page.add_style_tag(content=(ROOT/'frontend/styles.css').read_text())
        page.add_script_tag(content='window.VERA_CONFIG='+json.dumps({'API_BASE_URL':args.backend_base_url})+';')
        modules=[]
        for filename in ['utils.js','demo.js','api.js','app.js']:
            code=(ROOT/'frontend/src'/filename).read_text()
            code=re.sub(r'^import .*;\n', '', code, flags=re.M)
            code=re.sub(r'^export ', '', code, flags=re.M)
            modules.append(code)
        page.add_script_tag(content='(() => {"use strict";\n'+'\n'.join(modules)+'\n})();')
    else:
        page.add_init_script("localStorage.setItem('vera-studio.backend-override.v2',"+json.dumps(args.backend_base_url)+");")
        page.goto(args.frontend_url)
    expect(page.locator('#connect-button-text')).to_have_text('Connected',timeout=15000)
    page.screenshot(path=str(ROOT/'reports/desktop-empty.png'),full_page=True)
    page.locator('#start-demo').click()
    expect(page.locator('#chat-status')).to_have_text('Conversation open',timeout=10000)
    assert page.locator('.message.bot').count()==1
    page.locator('[data-reply="Yes, send the checklist"]').click()
    expect(page.locator('.message.bot')).to_have_count(2)
    page.locator('[data-reply="What is the price?"]').click()
    expect(page.locator('.message.bot')).to_have_count(3)
    page.wait_for_timeout(500)
    page.screenshot(path=str(ROOT/'reports/desktop-chat.png'),full_page=True)
    page.locator('[data-reply="STOP"]').click()
    expect(page.locator('#chat-status')).to_have_text('Conversation ended')
    expect(page.locator('#message-input')).to_be_disabled()
    print('Desktop full chat incl STOP passed')
    # Edit custom JSON, unknown URL needs error, API console reads all support.
    page.locator('[data-view="api"]').click()
    page.locator('#send-api').click();expect(page.locator('#response-status')).to_contain_text('200')
    page.locator('#api-endpoint').select_option('metadata');page.locator('#send-api').click()
    expect(page.locator('#api-response')).to_contain_text('deterministic-rule-engine')
    page.locator('[data-view="context"]').click()
    page.locator('#context-json').fill('{ broken')
    page.locator('#apply-context').click();expect(page.locator('#context-error')).to_be_visible()
    print('API console + JSON errors passed')
    page.locator('[data-view="playground"]').click()
    # All business/scenario combinations must actually compose, not just build valid JSON.
    for category in ['restaurants','salons','gyms','dentists','pharmacies']:
        for kind in ['perf_dip','perf_spike','milestone_reached','curious_ask_due']:
            page.locator('#business-select').select_option(category)
            page.locator('#trigger-select').select_option(kind)
            page.locator('#new-session').click()
            expect(page.locator('#chat-status')).to_have_text('Conversation open',timeout=10000)
            assert page.locator('.message.bot').count()==1,(category,kind,page.locator('#chat-timeline').inner_text())
    print('20 live scenario combinations passed')
    # Response lost after server processes: retry sends exactly the original turn.
    captured=[]
    def lose_once(route):
        captured.append(route.request.post_data_json)
        response=route.fetch();assert response.status==200
        route.abort('failed')
    page.route('**/demo/v1/reply',lose_once,times=1)
    page.locator('[data-reply="Yes, send the checklist"]').click()
    expect(page.locator('#pending-retry')).to_be_visible()
    def retry_capture(route):
        captured.append(route.request.post_data_json);route.continue_()
    page.route('**/demo/v1/reply',retry_capture,times=1)
    page.locator('#retry-reply').click()
    expect(page.locator('#pending-retry')).to_be_hidden()
    expect(page.locator('.message.bot')).to_have_count(2)
    assert captured[0]==captured[1]
    assert page.locator('.message.user').count()==1
    print('Lost-response exact-turn safe retry passed')
    # Settings rejects /v1 suffix; old token cleared when host changes.
    page.locator('[data-open-settings]').first.click()
    page.locator('#api-token').fill('do-not-leak')
    page.locator('#backend-url').fill(args.backend_base_url.rstrip('/')+'/v1')
    assert page.locator('#api-token').input_value()==''
    page.locator('#save-settings').click()
    expect(page.locator('#settings-error')).to_be_visible()
    page.locator('#close-settings').click()
    print('Settings bad base URL + token clearing passed')
    # Every major view remains in the mobile viewport.
    page.set_viewport_size({'width':390,'height':844})
    for name in ['playground','context','api','guide']:
        page.locator('[data-view="'+name+'"]').click()
        assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'),name
    page.locator('[data-view="playground"]').click()
    page.locator('#business-select').select_option('restaurants')
    page.locator('#trigger-select').select_option('perf_dip')
    page.locator('#new-session').click()
    expect(page.locator('#chat-status')).to_have_text('Conversation open')
    page.locator('[data-reply="Yes, send the checklist"]').click()
    expect(page.locator('.message.bot')).to_have_count(2)
    page.wait_for_timeout(600)
    page.screenshot(path=str(ROOT/'reports/mobile-chat.png'),full_page=True)
    print('Mobile views no horizontal page overflow passed')
    print('Page errors',errors)
    assert not errors
    browser.close()
