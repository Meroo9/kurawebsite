async def run_test(page, output_dir, page_url):
    try:
        import json
        from pathlib import Path
        from dotenv import dotenv_values
        s=json.loads(Path('/app/test_reports/research_test_state.json').read_text());base=dotenv_values('/app/frontend/.env')['REACT_APP_BACKEND_URL'].rstrip('/')
        await page.set_viewport_size({'width':1920,'height':1080})
        await page.get_by_test_id('auth-email').fill(s['accounts']['admin']['email']);await page.get_by_test_id('auth-password').fill(s['password']);await page.get_by_test_id('auth-submit').click()
        await page.wait_for_url('**/admin')
        await page.goto(base+'/admin/posts')
        response=await page.request.get(base+'/api/admin/posts?q='+s['tag']+' UI')
        posts=(await response.json())['items'];p=next(p for p in posts if p['title'].endswith('UI عنوان معدل'));pid=p['id']
        await page.get_by_test_id('edit-post-'+pid).click()
        await page.get_by_test_id('remove-post-image').wait_for()
        hit=await page.get_by_test_id('remove-post-image').evaluate("""e=>{let r=e.getBoundingClientRect();let t=document.elementFromPoint(r.x+r.width/2,r.y+r.height/2);return {button:r.toJSON(),hit:t.outerHTML.slice(0,400)}}""")
        print('Image removal hit test:',hit)
        await page.screenshot(path='/app/test_reports/browser_image_diagnostic/automation_output/20261101_121939_6e6940d0f28d/kura-image-button-overlay.jpeg', type="jpeg", quality=40, full_page=False)
        try:
            await page.get_by_test_id('remove-post-image').click(timeout=3000)
            print('Image removal normal click succeeded')
        except Exception as e:
            print('FAIL normal image removal click:',str(e)[:900])
            await page.get_by_test_id('remove-post-image').click(force=True)
        print('After click remove button count:',await page.get_by_test_id('remove-post-image').count())
        async with page.expect_request(lambda r:r.url.endswith('/api/admin/posts/'+pid) and r.method=='PUT') as save:
            await page.get_by_test_id('save-post').click()
        print('Saved image_id:',(await save.value).post_data_json.get('image_id'))
        await page.get_by_test_id('post-editor').wait_for(state='hidden')
        fetched=await page.request.get(base+'/api/posts/'+pid);print('Persisted image_id:',(await fetched.json())['image_id'])
        error_text=await page.evaluate("""() => {const errorElements=Array.from(document.querySelectorAll('.error, [class*="error"], [id*="error"]'));return errorElements.map(el=>el.textContent).join(', ');} """)
        print('Found error message: '+error_text if error_text else 'No error messages found on the page')
    except Exception as e:
        print('FAIL diagnostic:',repr(e))
