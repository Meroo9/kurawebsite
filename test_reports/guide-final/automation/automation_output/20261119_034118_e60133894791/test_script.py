async def run_test(page, output_dir, page_url):
    import importlib.util
    try:
        spec = importlib.util.spec_from_file_location('guide_final_browser', '/app/tests/guide_final_browser.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        await module.run(page)
    except Exception as exc:
        print('FAIL final verification runner:', str(exc))
