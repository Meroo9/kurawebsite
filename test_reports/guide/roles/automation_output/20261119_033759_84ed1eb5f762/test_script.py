async def run_test(page, output_dir, page_url):
    import sys,json
    from pathlib import Path
    sys.path.insert(0,'/app/tests')
    try:
     import guide_roles_browser
     await guide_roles_browser.run(page)
     await page.set_viewport_size({'width':1920,'height':1080})
     await page.goto(page.url.split('/guide')[0]+'/guide')
     await page.get_by_test_id('guide-title').wait_for()
     contrast = await page.evaluate("""() => {
     const luminance=rgb=>rgb.map(v=>{v/=255;return v<=0.04045?v/12.92:((v+0.055)/1.055)**2.4}).reduce((a,v,i)=>a+v*[0.2126,0.7152,0.0722][i],0);
     return ['guide-toc-account','guide-scope','guide-section-count','guide-screen-account-step-0','guide-role-admin','guide-screen-files-cell-0-2'].map(id=>{const el=document.querySelector(`[data-testid="${id}"]`),style=getComputedStyle(el);let bgEl=el,bg=getComputedStyle(bgEl).backgroundColor;while(bg==='rgba(0, 0, 0, 0)'&&bgEl.parentElement){bgEl=bgEl.parentElement;bg=getComputedStyle(bgEl).backgroundColor;}const fg=style.color.match(/[0-9.]+/g).slice(0,3).map(Number),background=bg.match(/[0-9.]+/g).slice(0,3).map(Number),a=luminance(fg),b=luminance(background);return {id,color:style.color,background:bg,fontSize:style.fontSize,contrast:(Math.max(a,b)+.05)/(Math.min(a,b)+.05)};});
     }""")
     Path('/app/test_reports/guide/contrast.json').write_text(json.dumps(contrast,indent=2))
     print('Measured guide text contrast',contrast)
     error_text = await page.evaluate("""() => {const errorElements = Array.from(document.querySelectorAll('.error, [class*="error"], [id*="error"]')); return errorElements.map(el => el.textContent).join(', ');} """)
     print(f'Found error message: {error_text}' if error_text else 'No error messages found on the page')
    except Exception as e:
     print('FAIL role/contrast harness:',str(e))
