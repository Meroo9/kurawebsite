async def run_test(page, output_dir, page_url):
    import sys
    sys.path.insert(0,'/app/tests')
    from full_site_fixes_browser import run_employee_video
    try:
        await run_employee_video(page)
        print('Employee and real video verification complete')
    except Exception as e:
        print('FAIL employee/video harness',repr(e))
