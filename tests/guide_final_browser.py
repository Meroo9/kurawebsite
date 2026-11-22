"""Final guide-only contrast/documentation smoke; no auth, DB writes or API mocks."""
import json
from pathlib import Path
from urllib.parse import urlsplit

from playwright.async_api import expect

ROOT = Path('/app')
OUT = ROOT / 'test_reports/guide-final'

CONTRAST = r"""() => {
 const rgba = value => {const n=value.match(/[\d.]+/g).map(Number);return [...n.slice(0,3),n.length>3?n[3]:1]};
 const blend=(a,b)=>a.slice(0,3).map((v,i)=>v*a[3]+b[i]*(1-a[3])).concat(1);
 const background=e=>{const chain=[];for(let p=e;p;p=p.parentElement)chain.unshift(p);let b=[255,255,255,1];for(const p of chain){const s=getComputedStyle(p);if(s.backgroundImage!=='none')throw Error('Unsupported background image');b=blend(rgba(s.backgroundColor),b)}return b};
 const lum=c=>{const v=c.slice(0,3).map(x=>{x/=255;return x<=.04045?x/12.92:((x+.055)/1.055)**2.4});return .2126*v[0]+.7152*v[1]+.0722*v[2]};
 const sample=(e,pseudo=null)=>{const s=getComputedStyle(e,pseudo);let bg=background(e);if(pseudo)bg=blend(rgba(s.backgroundColor),bg);const fg=blend(rgba(s.color),bg);const a=lum(fg),b=lum(bg);return {id:e.dataset.testid||e.parentElement.dataset.testid||e.className,pseudo,color:s.color,background:bg.slice(0,3),ratio:(Math.max(a,b)+.05)/(Math.min(a,b)+.05),opacity:s.opacity}};
 const selectors=['[data-testid^="guide-toc-"]','[data-testid^="guide-toc-"]>span','[data-testid="guide-section-count"]','[data-testid="guide-scope"]','[data-testid^="guide-role-"]','.guide-screen-content .guide-steps li','.guide-screen-content .guide-chapter-heading small','.guide-screen-content .guide-chapter-number','.guide-screen-content .guide-table th','.guide-screen-content .guide-table td','.guide-screen-content .guide-faq [data-testid*="-answer-"]>div','.guide-screen-content .guide-note p','[data-testid="guide-version"]','[data-testid="guide-back-to-top"]'];
 const result=[];for(const selector of selectors)for(const e of document.querySelectorAll(selector))if(e.getClientRects().length)result.push(sample(e));
 for(const e of document.querySelectorAll('.guide-screen-content .guide-steps li'))result.push(sample(e,'::before'));
 result.push(sample(document.querySelector('[data-testid="guide-search"]'),'::placeholder'));
 return result;
}"""


async def run(page):
    OUT.mkdir(parents=True, exist_ok=True)
    origin = '{0.scheme}://{0.netloc}'.format(urlsplit(page.url))
    results, contrasts = [], {}
    guide = json.loads((ROOT / 'frontend/src/content/user-guide.ar.json').read_text())

    async def check(name, task):
        try:
            await task()
            results.append({'name': name, 'passed': True})
            print('PASS', name)
        except Exception as exc:
            results.append({'name': name, 'passed': False, 'error': str(exc)})
            print('FAIL', name, str(exc))

    for width, height in [(1920, 1080), (390, 844)]:
        async def viewport(width=width, height=height):
            await page.set_viewport_size({'width': width, 'height': height})
            await page.goto(origin + '/guide')
            await expect(page.get_by_test_id('guide-title')).to_be_visible()
            await expect(page.get_by_test_id('guide-section-count')).to_have_text('12 فصلًا')
            await page.evaluate('document.fonts.ready')
            assert await page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            assert await page.get_by_test_id('guide-screen-files-table').evaluate('(e)=>e.scrollWidth<=e.clientWidth')
            await page.screenshot(path=str(OUT / f'guide-{width}.jpg'), quality=40, full_page=False)
            for i in range(8):
                await page.get_by_test_id(f'guide-screen-help-question-{i}').click(force=True)
                await expect(page.get_by_test_id(f'guide-screen-help-answer-{i}')).to_be_visible()
            await page.wait_for_timeout(250)
            samples = await page.evaluate(CONTRAST)
            for target in ['guide-toc-account', 'guide-role-employee', 'guide-role-all']:
                await page.get_by_test_id(target).hover()
                await page.wait_for_timeout(250)
                hovered = await page.evaluate(CONTRAST)
                samples.extend(dict(item, state='hover') for item in hovered if item['id'] == target)
            contrasts[str(width)] = samples
            failed = [s for s in samples if s['ratio'] < 4.5]
            assert not failed, failed
            print('CONTRAST', width, len(samples), 'samples; minimum', min(s['ratio'] for s in samples))
        await check(f'Layout/FAQ/contrast including hover and active at {width}', viewport)

    async def filtered_print():
        await page.get_by_test_id('guide-role-employee').click(force=True)
        await expect(page.get_by_test_id('guide-section-count')).to_have_text('5 فصلًا')
        await page.get_by_test_id('guide-search').fill('استلام')
        await expect(page.get_by_test_id('guide-section-count')).to_have_text('1 فصلًا')
        await expect(page.get_by_test_id('guide-screen-employee-title')).to_have_text(guide['sections'][5]['title'])
        await page.emulate_media(media='print')
        await expect(page.get_by_test_id('guide-print-document')).to_be_visible()
        assert await page.locator('.guide-print-content section.guide-chapter:visible').count() == 12
        assert await page.locator('.guide-print-content [data-testid*="-answer-"]:visible').count() == 8
        await expect(page.get_by_test_id('guide-search')).to_be_hidden()
        await page.emulate_media(media='screen')
        await expect(page.get_by_test_id('guide-section-count')).to_have_text('1 فصلًا')
        await page.get_by_test_id('guide-clear-search').click(force=True)
        await expect(page.get_by_test_id('guide-section-count')).to_have_text('5 فصلًا')
        await page.get_by_test_id('guide-search').fill('الدفعات الجزئية')
        await expect(page.get_by_test_id('guide-screen-help-answer-2')).to_be_visible()
        await expect(page.get_by_test_id('guide-screen-help-answer-2')).to_have_text(guide['sections'][-1]['questions'][2]['answer'])
        await page.get_by_test_id('guide-clear-search').click(force=True)
    await check('Employee filter/search, all 12 print chapters/8 answers, searchable FAQ', filtered_print)

    async def download():
        async with page.expect_download() as event:
            await page.get_by_test_id('guide-download').click(force=True)
        attachment = await event.value
        assert attachment.suggested_filename == 'kura-user-guide-ar.md'
        await attachment.save_as(str(OUT / 'downloaded-guide.md'))
        assert (OUT / 'downloaded-guide.md').read_bytes() == (ROOT / 'docs/USER_GUIDE_AR.md').read_bytes()
    await check('Actual browser Markdown download matches repository bytes', download)
    error_text = await page.evaluate("""() => {const errorElements = Array.from(document.querySelectorAll('.error, [class*="error"], [id*="error"]'));return errorElements.map(el => el.textContent).join(', ');} """)
    print(f'Found error message: {error_text}' if error_text else 'No error messages found on the page')
    (OUT / 'contrast.json').write_text(json.dumps(contrasts, ensure_ascii=False, indent=2))
    (OUT / 'browser-results.json').write_text(json.dumps(results, ensure_ascii=False, indent=2))
    print('FINAL TARGETED SUMMARY', sum(r['passed'] for r in results), '/', len(results))