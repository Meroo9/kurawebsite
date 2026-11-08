async def run_test(page, output_dir, page_url):
    from pathlib import Path
    import json, os
    from dotenv import load_dotenv
    load_dotenv('/app/frontend/.env')
    try:
        ns={}
        exec(Path('/app/tests/research_privacy_layout_browser.py').read_text(),ns)
        await ns['run'](page,os.environ['REACT_APP_BACKEND_URL'].rstrip('/'),json.loads(Path('/app/test_reports/privacy_layout_state.json').read_text()))
    except Exception as e:
        print('FAIL browser execution',repr(e))
