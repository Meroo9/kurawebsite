async def run_test(page, output_dir, page_url):
    try:
        import json,traceback
        from pathlib import Path
        from dotenv import dotenv_values
        namespace={}
        exec(Path('/app/tests/research_browser_regression.py').read_text(),namespace)
        base=dotenv_values('/app/frontend/.env')['REACT_APP_BACKEND_URL'].rstrip('/')
        state=json.loads(Path('/app/test_reports/research_test_state.json').read_text())
        await namespace['run'](page,base,state)
        print('PASS: full research browser suite completed')
    except Exception as e:
        print('FAIL: browser execution '+repr(e));print(traceback.format_exc())
