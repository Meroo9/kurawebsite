"""Authenticated workspace guide links with isolated run-owned roles and real sessions."""
import json
from pathlib import Path
from urllib.parse import urlsplit

from playwright.async_api import expect


async def run(page):
    out = Path('/app/test_reports/guide')
    state = json.loads((out / 'private_state.json').read_text())
    parsed = urlsplit(page.url)
    base = f'{parsed.scheme}://{parsed.netloc}'
    results = []
    for role in ['visitor', 'student', 'employee', 'admin']:
        context = await page.context.browser.new_context(viewport={'width': 390, 'height': 844})
        try:
            await context.add_cookies([{'name': 'kura_session', 'value': state['cookies'][role]['kura_session'], 'domain': parsed.hostname, 'path': '/api', 'secure': True, 'httpOnly': True, 'sameSite': 'Lax'}])
            tab = await context.new_page()
            await tab.goto(base + ('/admin' if role == 'admin' else '/dashboard'))
            link = tab.get_by_test_id('workspace-guide')
            await expect(link).to_be_visible()
            await expect(link).to_have_attribute('href', '/guide?role=' + role)
            await tab.screenshot(path=str(out / f'workspace-guide-{role}-390.jpg'), quality=40, full_page=False)
            await link.click()
            await tab.wait_for_url('**/guide?role=' + role)
            await expect(tab.get_by_test_id('guide-role-' + role)).to_have_attribute('aria-pressed', 'true')
            await expect(tab.get_by_test_id('open-workspace')).to_be_visible()
            await tab.get_by_test_id('open-workspace').click()
            await tab.wait_for_url('**/admin' if role == 'admin' else '**/dashboard')
            await expect(tab.get_by_test_id('workspace-guide')).to_be_visible()
            results.append({'name': role + ' workspace guide query/navigation/mobile', 'passed': True})
            print('PASS workspace guide role:', role)
        except Exception as exc:
            results.append({'name': role + ' workspace guide query/navigation/mobile', 'passed': False, 'error': str(exc)})
            print('FAIL workspace guide role:', role, str(exc))
        finally:
            await context.close()
    (out / 'roles-browser-results.json').write_text(json.dumps(results, indent=2))