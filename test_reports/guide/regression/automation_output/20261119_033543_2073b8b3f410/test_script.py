async def run_test(page, output_dir, page_url):
    import sys
    sys.path.insert(0, '/app/tests')
    import guide_browser
    try:
     await guide_browser.run(page)
    except Exception as e:
     print('FAIL guide regression harness:',str(e))
