# Deduplicated current-run evidence/report; prior broad iteration remains historical only.
import json
from pathlib import Path
ROOT=Path('/app/test_reports/full_site_roles/fixes')
files=['layout_profile_browser','pending_signup_browser','employee_video_browser','avatar_verified_browser']
checks={};shots=[]
for name in files:
    d=json.loads((ROOT/(name+'.json')).read_text())
    for row in d['checks']:checks[row['check']]=row
    shots.extend(d['screenshots'])
unique=sorted(set(shots))
manifest=[{'path':p,'role':('public' if Path(p).name.startswith('public') else 'admin' if Path(p).name.startswith('admin') else 'employee' if 'employee' in Path(p).name else 'blocked' if Path(p).name.startswith('blocked') else 'student' if Path(p).name.startswith(('student','approved','ui_pending')) else 'pending_visitor' if Path(p).name.startswith('pending') else 'visitor'),'viewport_width':int(Path(p).stem.rsplit('-',1)[1])} for p in unique]
(ROOT/'screenshot_manifest.json').write_text(json.dumps(manifest,indent=2))
(ROOT/'executed_browser_checks.json').write_text(json.dumps(list(checks.values()),ensure_ascii=False,indent=2))
cleanup=json.loads((ROOT/'cleanup.json').read_text())
assert all(cleanup['checks'].values())
passed=sum(x['passed'] for x in checks.values());assert passed==len(checks)==46
report={
 'summary':'Targeted iteration 6 WITHOUT deployment: 8/8 pytest API cases and 46/46 current browser checkpoints passed. All reported fixes verified; pending-KRC real browser signup, employee UI lifecycle and small real MP4 playback gaps closed. Historical iteration 5 broad counts were not rerun. All temporary data cleaned; original settings/courses/owner invitations exactly preserved. No APIs mocked.',
 'backend_issues':{'critical':[],'minor':[]},
 'frontend_issues':{'ui_bugs':[],'integration_issues':[],'design_issues':[]},
 'test_report_links':['/app/backend/tests/full_fix_support.py','/app/backend/tests/test_full_site_fixes.py','/app/tests/full_site_fixes_browser.py','/app/tests/full_site_fixes_report.py','/app/test_reports/pytest/full_site_fixes.xml',str(ROOT/'executed_browser_checks.json'),str(ROOT/'layout_profile_browser.json'),str(ROOT/'pending_signup_browser.json'),str(ROOT/'employee_video_browser.json'),str(ROOT/'avatar_verified_browser.json'),str(ROOT/'cleanup.json')],
 'action_items':[],
 'critical_code_review_comments':[],
 'updated_files':['/app/backend/tests/full_fix_support.py','/app/backend/tests/test_full_site_fixes.py','/app/tests/full_site_fixes_browser.py','/app/tests/full_site_fixes_report.py','/app/memory/test_credentials.md','/app/test_reports/iteration_6.json'],
 'success_rate':{'backend':'100% (8/8 current targeted pytest cases)','frontend':'100% (46/46 current deduplicated functional checkpoints; two additional stale-cookie harness attempts failed then corrected; initial load separately passed)'},
 'test_credentials':'No pre-existing active test credentials. Generated eight isolated accounts; no owner credentials/invitation used. Private credential manifest and all temporary users/sessions removed after tests.',
 'seed_data_creation':{'seed_scripts_run':False,'temporary_only':True,'cleanup':cleanup},
 'retest_needed':False,'should_main_agent_self_test':False,
 'context_for_next_testing_agent':'Fresh minimal fixture setup required: full_fix_support.py, then test_full_site_fixes.py, then browser functions with importlib.reload between calls, then full_fix_support.py --cleanup. Archive tests mutate run-owned IDs once; do not rerun them against already archived fixtures. No fixture state remains. Pending signup uses ordinary stable clicks, custom calendar hidden wait, validity diagnostics and captures actual register POST; both typed/calendar workflows fully passed.',
 'rca of the issue':{'long_title':'Verified minmax(0,1fr), child min-width:0 and wrapping fix prior automatic min-content expansion. Tested 143-character uninterrupted Arabic segment (161-character full valid title), public and logged-in detail/purchase panel at 390/1000/1920; full heading/breadcrumb/card text, no clipping or horizontal document overflow.', 'archive':'Mongo matched_count is checked before success/audit. Missing and repeated course/lecture DELETE return Arabic 404, first archive succeeds once and emits exactly one audit. Approved purchase and student private-file access remained valid.', 'signup':'Previous no-POST interruption was not reproduced. Typed date 2025-01-10 and calendar-selected 2025-01-15 passed native validity with zero invalid fields, ordinary submit, actual POST 200, avatar persistence, visitor/pending state, flagged-course denial before UI approval, logout/re-login and student access. No Auth source changes; exact cause of historical interruption cannot be proven.', 'harness_only':'Browser tool retained imported module, requiring importlib.reload after adding employee runner. Supplemental avatar check reused cookies saved before deliberate logout and correctly got redirected; actual login verified both persisted images. Harness now saves new cookies after re-login. No application error inferred.'},
 'resolved_original_failures':['Long-title course overflow at 390/1000/1920; public/logged-in purchase panels and catalog/library cards verified.','Nonexistent course and lecture DELETE false-success/audit; repeat archives also verified.','Duplicate workspace-profile selector; sidebar/header each unique and both navigate/save at mobile/desktop.'],
 'closed_coverage_gaps':['Actual pending-KRC browser signup including avatar and custom calendar, typed-date variant, real approval/logout/login and permission transition.','Admin employee create/edit/disable via actual browser; employee actual login before inactivity, revocation of existing sessions and denied fresh login afterwards.','Blocked and inactive Arabic login notices at 390/1920 with password fields cleared before screenshots.','Real managed-storage upload of eight-second H264 MP4, metadata/range checks, unauthorized anonymous/unrelated denial and student browser play/seek at 390/1920.'],
 'coverage_gaps':['This is a targeted regression, not a new whole-site rerun; iteration 5 broad results remain historical.','MP4 upload performed via public API; actual UI preview/playback exercised. No 100MB load test, real devices, audio playback, network stress, or formal security audit. Mobile coverage uses browser viewport emulation.','Remaining historical limits unchanged: inbox recovery-link delivery/click and global currency mutation intentionally not exercised; owner invitation activation/reset not exercised.','Managed storage has no physical object-delete API; exact metadata deletion revokes access, provider objects remain.'],
 'screenshot_manifest':str(ROOT/'screenshot_manifest.json'),
 'deployment':'Not performed','application_changes':[],'mocked_apis':False,
 'video_metrics':{'duration_seconds':8,'resolution':'320x180','desktop_current_time_before_seek':1.2093,'desktop_current_time_after_seek':5.7064,'mobile_current_time_before_seek':1.2084,'mobile_current_time_after_seek':5.7128,'fixture_size_bytes':(ROOT/'TEST_fixture.mp4').stat().st_size}
}
Path('/app/test_reports/iteration_6.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print('Final report saved: 8 API cases,',len(checks),'browser checkpoints,',len(unique),'role-specific screenshots')