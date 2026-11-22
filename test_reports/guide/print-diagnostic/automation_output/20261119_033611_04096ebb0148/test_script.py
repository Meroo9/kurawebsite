async def run_test(page, output_dir, page_url):
    try:
     await page.set_viewport_size({'width':1920,'height':1080})
     await page.get_by_test_id('guide-title').wait_for()
     await page.evaluate('window.__printCalls=0; window.print=()=>window.__printCalls++')
     await page.get_by_test_id('guide-print').click()
     print('Print calls:',await page.evaluate('window.__printCalls'))
     await page.emulate_media(media='print')
     print('Print container visible:',await page.get_by_test_id('guide-print-document').is_visible())
     print('Chapters:',await page.locator('.guide-print-content section.guide-chapter:visible').count())
     print('Answers:',await page.locator('.guide-print-content [data-testid*="-answer-"]:visible').count())
     print('Header hidden:',await page.locator('.site-header').is_hidden())
     print('Footer hidden:',await page.locator('.footer').is_hidden())
     print('Search hidden:',await page.get_by_test_id('guide-search').is_hidden())
     print('Computed:',await page.evaluate("""() => Object.fromEntries(['.site-header','.footer','.guide-screen-content','.guide-print-content'].map(s=>[s,getComputedStyle(document.querySelector(s)).display]))"""))
     await page.screenshot(path='/app/test_reports/guide/print-diagnostic/automation_output/20261119_033611_04096ebb0148/print-emulation.jpeg', type="jpeg", quality=40, full_page=False)
     await page.pdf(path='/app/test_reports/guide/guide-filtered-all-chapters.pdf',format='A4',print_background=True,prefer_css_page_size=True)
     print('PASS PDF generated')
     await page.emulate_media(media='screen')
     print('Restored screen count:',await page.get_by_test_id('guide-section-count').inner_text())
    except Exception as e:
     import traceback
     print('FAIL print diagnosis:',traceback.format_exc())
