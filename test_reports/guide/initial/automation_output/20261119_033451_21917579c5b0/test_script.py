async def run_test(page, output_dir, page_url):
    try:
     await page.set_viewport_size({"width":1920,"height":1080})
     await page.get_by_test_id('guide-title').wait_for()
     print('PASS public guide loaded; count:', await page.get_by_test_id('guide-section-count').inner_text())
     await page.screenshot(path='/app/test_reports/guide/initial/automation_output/20261119_033451_21917579c5b0/initial-desktop.jpeg', type="jpeg", quality=40, full_page=False)
     error_text = await page.evaluate("""() => {const errorElements = Array.from(document.querySelectorAll('.error, [class*="error"], [id*="error"]')); return errorElements.map(el => el.textContent).join(', ');} """)
     print(f'Found error message: {error_text}' if error_text else 'No error messages found on the page')
    except Exception as e:
     print('FAIL initial guide:',str(e))
