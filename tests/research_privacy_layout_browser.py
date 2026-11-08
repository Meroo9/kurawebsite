# Targeted UI privacy and responsive heading regression; no extra request submissions.
import json, re
from pathlib import Path

async def run(page, base, state):
    results=[]
    contexts=[]
    out=Path('/app/test_reports/browser_privacy_layout')
    out.mkdir(parents=True,exist_ok=True)
    async def check(label, fn):
        try:
            await fn()
            results.append({'check':label,'passed':True});print('PASS '+label)
        except Exception as e:
            results.append({'check':label,'passed':False,'error':str(e)});print('FAIL '+label+': '+str(e))
    async def width(p,label):
        metrics=await p.evaluate('''() => ({doc:document.documentElement.scrollWidth,win:innerWidth,body:document.body.scrollWidth})''')
        assert metrics['doc']<=metrics['win'],(label,metrics)
        print(label+' width '+str(metrics))
    async def heading(p, expected=None):
        h=p.get_by_test_id('page-title')
        await h.wait_for(timeout=15000)
        if expected is not None:assert await h.inner_text()==expected
        m=await h.evaluate('''el=>{const r=el.getBoundingClientRect(),s=getComputedStyle(el);const range=document.createRange();range.selectNodeContents(el);return {left:r.left,right:r.right,width:r.width,height:r.height,scroll:el.scrollWidth,client:el.clientWidth,overflow:s.overflow,whiteSpace:s.whiteSpace,lineClamp:s.webkitLineClamp,textHeight:range.getBoundingClientRect().height,viewport:innerWidth};}''')
        assert m['width']>0 and m['height']>0 and m['left']>=-1 and m['right']<=m['viewport']+1,m
        assert m['scroll']<=m['client']+1 and m['overflow']!='hidden' and m['lineClamp'] in ('none','',None),m
        assert m['height']>=m['textHeight']-2,m
        print('Heading geometry '+str(m))
    async def login(p,role):
        await p.goto(base+'/login')
        await p.get_by_test_id('auth-email').fill(state['accounts'][role]['email'])
        await p.get_by_test_id('auth-password').fill(state['password'])
        await p.get_by_test_id('auth-submit').click(force=True)
        await p.wait_for_url(re.compile('/(admin|dashboard)$'),timeout=20000)
        print('PASS temporary '+role+' login')
    async def errors(p):
        error_text=await p.evaluate("""() => {const errorElements = Array.from(document.querySelectorAll('.error, [class*="error"], [id*="error"]'));return errorElements.map(el => el.textContent).join(', ');} """)
        if error_text:print('Found error message: '+error_text)
        else:print('No error messages found on the page')
        assert not error_text,error_text
    try:
        for role in ('employee','owner','admin'):
            context=await page.context.browser.new_context(viewport={'width':1920,'height':1080})
            contexts.append(context);p=await context.new_page()
            await login(p,role)
            route=('/admin/research/' if role=='admin' else '/dashboard/research/')+state['rid']
            async def privacy():
                await p.goto(base+route)
                await p.get_by_test_id('research-detail-description').wait_for(timeout=15000)
                body=await p.locator('body').inner_text()
                if role=='employee':
                    for marker in state['markers']+[state['currency']]+[state['accounts']['owner'][k] for k in ('id','email','name','phone')]:
                        assert marker not in body,'Private marker rendered '+marker
                    assert await p.get_by_test_id('cancellation-resolution').count()==0
                    assert await p.get_by_test_id('research-owner-info').count()==0
                    assert await p.get_by_test_id('research-payment-status').count()==0
                    assert await p.locator('[data-testid^="research-event-"]').count()>0
                else:
                    assert await p.get_by_test_id('cancellation-resolution').inner_text()==state['note']
                    assert state['note'] in body
                await errors(p)
            await check(role+' rendered event privacy',privacy)
            for w in (390,1000,1920):
                async def detail_layout():
                    await p.set_viewport_size({'width':w,'height':844 if w==390 else 1080})
                    await p.goto(base+route)
                    await p.get_by_test_id('research-detail-description').wait_for(timeout=15000)
                    await heading(p,state['title']);await width(p,role+' detail '+str(w))
                    assert await p.locator('.request-summary').is_visible()
                    style=await p.locator('.request-summary').evaluate('el=>({border:getComputedStyle(el).borderTopWidth,padding:getComputedStyle(el).padding,background:getComputedStyle(el).backgroundColor})')
                    assert style['border']=='1px' and style['padding']!='0px',style
                    assert await p.locator('.research-timeline').is_visible()
                    file=p.get_by_test_id('research-file-view-'+state['input_id'])
                    assert await file.count()==1
                    file_text=await p.locator('.research-file strong').first.inner_text()
                    assert file_text==state['filename']
                    if w in (390,1920):
                        await p.get_by_test_id('page-title').scroll_into_view_if_needed()
                        await p.screenshot(path=str(out/f'{role}-detail-{w}.jpeg'),quality=40,full_page=False)
                await check(role+' long title detail '+str(w),detail_layout)
            if role=='owner':
                for w in (390,1000,1920):
                    async def listing():
                        await p.set_viewport_size({'width':w,'height':844 if w==390 else 1080})
                        await p.goto(base+'/dashboard/research')
                        await p.get_by_test_id('research-row-'+state['rid']).wait_for(timeout=15000)
                        assert await p.get_by_test_id('research-title-'+state['rid']).inner_text()==state['title']
                        await width(p,'owner list '+str(w));await heading(p)
                    await check('long title research list '+str(w),listing)
                    async def payments():
                        await p.goto(base+'/dashboard/payments')
                        await p.get_by_test_id('research-payments-tab').click(force=True)
                        row=p.get_by_test_id('research-payment-row-'+state['rid'])
                        await row.wait_for(timeout=15000)
                        assert await row.locator('h2').inner_text()==state['title']
                        await width(p,'owner payments '+str(w));await heading(p)
                        if w==390:await p.screenshot(path=str(out/'owner-payments-390.jpeg'),quality=40,full_page=False)
                        await row.click(force=True)
                        await p.get_by_test_id('research-detail-description').wait_for(timeout=15000)
                        assert p.url.endswith(state['rid'])
                    await check('long title research payments '+str(w),payments)
                async def form():
                    await p.set_viewport_size({'width':390,'height':844})
                    await p.goto(base+'/dashboard/research/new')
                    await p.get_by_test_id('research-title-input').fill(state['title'])
                    await p.get_by_test_id('research-description-input').fill(state['title']*3)
                    assert await p.get_by_test_id('research-description-input').input_value()==state['title']*3
                    await p.get_by_test_id('research-files-input').set_input_files({'name':state['filename'],'mimeType':'text/plain','buffer':b'TEST selected only'})
                    assert state['filename'] in await p.locator('.selected-files').inner_text()
                    await width(p,'long title form')
                    assert await p.get_by_test_id('research-guidance-title').is_visible()
                    await p.get_by_test_id('remove-selected-file-0').click(force=True)
                    assert await p.locator('.selected-files').count()==0
                    await errors(p)
                await check('mobile intake textarea and long selected filename',form)
        # Unauthenticated pages ensure shared-heading constraints do not regress normal screens.
        for w in (390,1920):
            await page.set_viewport_size({'width':w,'height':844 if w==390 else 1080})
            for route,testid in [('/','hero-title'),('/posts','page-title'),('/courses','page-title'),('/research','page-title')]:
                async def public_layout():
                    await page.goto(base+route)
                    await page.get_by_test_id(testid).wait_for(timeout=15000)
                    assert len(await page.get_by_test_id(testid).inner_text())>3
                    await width(page,'public '+route+' '+str(w))
                    if testid=='page-title':await heading(page)
                    assert await page.locator('body').inner_text()
                    await errors(page)
                await check('normal '+route+' '+str(w),public_layout)
    finally:
        for context in contexts:await context.close()
        Path('/app/test_reports/privacy_layout_browser_results.json').write_text(json.dumps(results,indent=2,ensure_ascii=False))
        print('BROWSER RESULT '+str(sum(r['passed'] for r in results))+'/'+str(len(results)))