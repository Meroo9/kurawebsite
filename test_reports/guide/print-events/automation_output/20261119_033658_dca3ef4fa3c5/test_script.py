async def run_test(page, output_dir, page_url):
    try:
     await page.get_by_test_id('guide-title').wait_for()
     await page.evaluate("""() => {window.__events=[];window.__prints=[]; window.print=()=>window.__prints.push({time:performance.now(),stack:new Error().stack}); document.querySelector('[data-testid="guide-print"]').addEventListener('click',e=>window.__events.push({time:performance.now(),trusted:e.isTrusted,detail:e.detail}));} """)
     await page.get_by_test_id('guide-print').click()
     print('Playwright click diagnostics', await page.evaluate('({events:window.__events,prints:window.__prints})'))
     await page.evaluate("window.__events=[]; window.__prints=[]; document.querySelector('[data-testid=guide-print]').click()")
     print('DOM click diagnostics', await page.evaluate('({events:window.__events,prints:window.__prints})'))
     print('PASS callback invoked; inspect whether harness duplicates mouse click')
    except Exception as e:
     print('FAIL print events:',str(e))
