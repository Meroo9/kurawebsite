async def run_test(page, output_dir, page_url):
    import sys
    sys.path.insert(0,'/app/tests')
    from full_site_fixes_browser import run_signup
    try:
        await run_signup(page)
        print('Actual pending signup run complete')
    except Exception as e:
        print('FAIL signup harness',repr(e))
