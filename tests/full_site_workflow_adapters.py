# Execute existing browser flows against fresh full-site state, recording only actually reached checkpoints.
from pathlib import Path
import full_site_roles_browser as h

async def run_existing(page,which):
    source=Path('/app/tests/'+which+'_browser_regression.py').read_text()
    source=source.replace('/tmp/kura-post-mobile.jpg',str(h.ROOT/'post-workflow-mobile.jpg')).replace('/tmp/kura-research-completed.jpg',str(h.ROOT/'research-workflow-completed-1000.jpg'))
    def log(*args,**kwargs):
        text=' '.join(str(a) for a in args)
        if text.startswith('PASS:'):h.record(text[6:])
        elif text.startswith('FAIL:'):h.record(text[6:],False)
        else:print(*args,**kwargs)
    ns={'print':log};exec(source,ns)
    try:await ns['run'](page,h.BASE,h.load())
    except Exception as e:
        h.record(which+' workflow aborted',False,repr(e));await h.shot(page,which+'-workflow-failure')
    finally:h.report(which+'_workflow_browser')