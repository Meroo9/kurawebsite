"""Targeted public guide browser regression; no mocked APIs or data writes."""
import json
from pathlib import Path
from urllib.parse import urlsplit

from playwright.async_api import expect

ROOT = Path('/app')
OUT = ROOT / 'test_reports/guide'


async def run(page):
    OUT.mkdir(parents=True, exist_ok=True)
    guide = json.loads((ROOT / 'frontend/src/content/user-guide.ar.json').read_text())
    origin = '{0.scheme}://{0.netloc}'.format(urlsplit(page.url))
    results = []

    async def check(name, task):
        try:
            await task()
            results.append({'name': name, 'passed': True})
            print('PASS', name)
        except Exception as exc:
            results.append({'name': name, 'passed': False, 'error': str(exc)})
            print('FAIL', name, str(exc))

    async def public_load():
        await page.set_viewport_size({'width': 1920, 'height': 1080})
        await page.goto(origin + '/guide')
        await expect(page.get_by_test_id('guide-title')).to_be_visible()
        assert await page.locator('.guide-screen-content section.guide-chapter').count() == 12
        assert await page.locator('html').get_attribute('dir') == 'rtl'
        for section in guide['sections']:
            await expect(page.get_by_test_id('guide-screen-' + section['id'] + '-title')).to_have_text(section['title'])
        duplicates = await page.evaluate("""() => {const ids=[...document.querySelectorAll('[data-testid]')].map(e=>e.dataset.testid); return ids.filter((id,i)=>ids.indexOf(id)!==i)}""")
        assert duplicates == [], duplicates
        assert await page.get_by_test_id('guide-print-document').is_hidden()

    await check('Public RTL, 12 titles, unique test IDs, hidden print copy', public_load)

    for role in ['visitor', 'student', 'employee', 'admin', 'all']:
        async def role_flow(role=role):
            await page.get_by_test_id('guide-role-' + role).click()
            expected = [s['id'] for s in guide['sections'] if role == 'all' or role in s['roles']]
            await expect(page.get_by_test_id('guide-section-count')).to_have_text(f'{len(expected)} فصلًا')
            actual = await page.locator('.guide-screen-content section.guide-chapter').evaluate_all('(els)=>els.map(e=>e.id.replace("guide-",""))')
            assert actual == expected, actual
            if role != 'all':
                assert 'role=' + role in page.url
            await page.reload()
            await expect(page.get_by_test_id('guide-role-' + role)).to_have_attribute('aria-pressed', 'true')
        await check('Role filter and reload persistence: ' + role, role_flow)

    async def search():
        await page.goto(origin + '/guide?role=invalid')
        await expect(page.get_by_test_id('guide-role-all')).to_have_attribute('aria-pressed', 'true')
        await expect(page.get_by_test_id('guide-section-count')).to_have_text('12 فصلًا')
        await page.get_by_test_id('guide-role-employee').click()
        await page.get_by_test_id('guide-search').fill('اسْتِلام')
        await expect(page.get_by_test_id('guide-section-count')).to_have_text('1 فصلًا')
        await expect(page.get_by_test_id('guide-screen-employee-title')).to_be_visible()
        assert 'role=employee' in page.url and 'q=' in page.url
        await page.reload()
        await expect(page.get_by_test_id('guide-search')).to_have_value('اسْتِلام')
        await page.get_by_test_id('guide-clear-search').click()
        await expect(page.get_by_test_id('guide-section-count')).to_have_text('5 فصلًا')
        await page.get_by_test_id('guide-search').fill('zzzz_no_matching_guide')
        await expect(page.get_by_test_id('guide-section-count')).to_have_text('0 فصلًا')
        await page.get_by_test_id('guide-reset-filters').click()
        await expect(page.get_by_test_id('guide-section-count')).to_have_text('12 فصلًا')
        assert '?' not in page.url
    await check('Invalid role, Arabic diacritics, combined search, clear and empty reset', search)

    async def faq():
        for i, question in enumerate(guide['sections'][-1]['questions']):
            trigger = page.get_by_test_id(f'guide-screen-help-question-{i}')
            await trigger.click()
            await expect(trigger).to_have_attribute('data-state', 'open')
            await expect(page.get_by_test_id(f'guide-screen-help-answer-{i}')).to_contain_text(question['answer'])
            await trigger.click()
            await expect(trigger).to_have_attribute('data-state', 'closed')
        await page.get_by_test_id('guide-search').fill('الدفعات الجزئية')
        await expect(page.get_by_test_id('guide-screen-help-answer-2')).to_be_visible()
        await page.get_by_test_id('guide-clear-search').click()
    await check('All 8 FAQ expand/collapse and answer text searchable', faq)

    async def anchors():
        await page.get_by_test_id('guide-toc-files').click()
        await page.wait_for_timeout(400)
        assert page.url.endswith('#guide-files')
        assert abs(await page.get_by_test_id('guide-screen-files').evaluate('(e)=>e.getBoundingClientRect().top')) < 100
        await page.get_by_test_id('guide-back-to-top').click()
        await page.wait_for_timeout(400)
        assert page.url.endswith('#guide-top')
        assert await page.evaluate('window.scrollY') < 150
    await check('TOC anchors and back to top', anchors)

    async def download():
        async with page.expect_download() as event:
            await page.get_by_test_id('guide-download').click()
        attachment = await event.value
        assert attachment.suggested_filename == 'kura-user-guide-ar.md'
        await attachment.save_as(str(OUT / 'downloaded-guide.md'))
        assert (OUT / 'downloaded-guide.md').read_bytes() == (ROOT / 'docs/USER_GUIDE_AR.md').read_bytes()
    await check('Real Markdown download byte-for-byte match', download)

    async def printing():
        await page.get_by_test_id('guide-role-employee').click()
        await page.get_by_test_id('guide-search').fill('استلام')
        await page.evaluate('window.__printCalls=0; window.print=()=>window.__printCalls++')
        await page.get_by_test_id('guide-print').click()
        assert await page.evaluate('window.__printCalls') == 1
        await page.emulate_media(media='print')
        await expect(page.get_by_test_id('guide-print-document')).to_be_visible()
        assert await page.locator('.guide-print-content section.guide-chapter:visible').count() == 12
        assert await page.locator('.guide-print-content [data-testid*="-answer-"]:visible').count() == 8
        assert await page.locator('.site-header').is_hidden()
        assert await page.locator('.footer').is_hidden()
        assert await page.get_by_test_id('guide-search').is_hidden()
        await page.screenshot(path=str(OUT / 'print-emulation.jpg'), quality=40, full_page=False)
        await page.pdf(path=str(OUT / 'guide-filtered-all-chapters.pdf'), format='A4', print_background=True, prefer_css_page_size=True)
        await page.emulate_media(media='screen')
        await expect(page.get_by_test_id('guide-section-count')).to_have_text('1 فصلًا')
    await check('Print callback, all chapters/answers despite filters, hidden chrome, actual PDF', printing)

    for width, height in [(390, 844), (768, 1024), (1000, 1024), (1920, 1080)]:
        async def responsive(width=width, height=height):
            await page.set_viewport_size({'width': width, 'height': height})
            await page.goto(origin + '/guide')
            await expect(page.get_by_test_id('guide-title')).to_be_visible()
            await page.evaluate('document.fonts.ready')
            assert await page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Horizontal document overflow'
            for target in ['guide-role-all', 'guide-role-admin', 'guide-download', 'guide-print']:
                box = await page.get_by_test_id(target).bounding_box()
                assert box['x'] >= 0 and box['x'] + box['width'] <= width + 1
            await page.screenshot(path=str(OUT / f'guide-{width}.jpg'), quality=40, full_page=False)
            await page.get_by_test_id('guide-toc-files').click()
            await page.wait_for_timeout(400)
            await expect(page.get_by_test_id('guide-screen-files-table')).to_be_visible()
            assert await page.get_by_test_id('guide-screen-files-table').evaluate('(e)=>e.scrollWidth<=e.clientWidth')
            if width == 390:
                await page.screenshot(path=str(OUT / 'files-mobile.jpg'), quality=40, full_page=False)
        await check(f'Responsive guide/table {width}', responsive)

    async def navigation():
        await page.set_viewport_size({'width': 390, 'height': 844})
        await page.goto(origin + '/')
        await page.get_by_test_id('mobile-menu').click()
        await expect(page.get_by_test_id('nav-about')).to_be_visible()
        await page.get_by_test_id('nav-about').click()
        await page.wait_for_url('**/about')
        assert not await page.locator('.main-nav').evaluate('(e)=>e.classList.contains("open")')
        await page.get_by_test_id('footer-guide').click()
        await page.wait_for_url('**/guide')
        await expect(page.get_by_test_id('guide-title')).to_be_visible()
        for target in ['guide-screen-account-link-1', 'guide-screen-admin-start-link-0']:
            await page.get_by_test_id(target).click()
            await page.wait_for_url('**/login')
            await page.goto(origin + '/guide')
        await page.goto(origin + '/')
        assert await page.locator('.site-header').is_visible()
        assert await page.locator('.footer').is_visible()
        assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    await check('Home/mobile menu/footer guide and protected links still require login', navigation)

    error_text = await page.evaluate("""() => {const errorElements = Array.from(document.querySelectorAll('.error, [class*="error"], [id*="error"]'));return errorElements.map(el => el.textContent).join(', ');} """)
    print(f'Found error message: {error_text}' if error_text else 'No error messages found on the page')
    (OUT / 'browser-results.json').write_text(json.dumps(results, ensure_ascii=False, indent=2))
    print('BROWSER SUMMARY', sum(r['passed'] for r in results), '/', len(results))