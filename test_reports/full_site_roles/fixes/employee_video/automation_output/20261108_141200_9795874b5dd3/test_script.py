async def run_test(page, output_dir, page_url):
    import sys,importlib
    sys.path.insert(0,'/app/tests')
    import full_site_fixes_browser
    f=importlib.reload(full_site_fixes_browser)
    try:
        await f.run_employee_video(page)
        print('Employee and real video verification complete')
    except Exception as e:
        print('FAIL employee/video harness',repr(e))
