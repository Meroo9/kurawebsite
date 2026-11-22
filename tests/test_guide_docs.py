"""Static Arabic guide generation and public Markdown regression; no application mutations."""
import json
import os
from pathlib import Path
import shutil
import subprocess

import requests

ROOT = Path('/app')
GUIDE = json.loads((ROOT / 'frontend/src/content/user-guide.ar.json').read_text())


def public_origin():
    values = dict(line.split('=', 1) for line in (ROOT / 'frontend/.env').read_text().splitlines() if '=' in line)
    return os.environ.get('REACT_APP_BACKEND_URL', values['REACT_APP_BACKEND_URL']).rstrip('/')


def test_generated_copies_match_source(tmp_path):
    for relative in ['scripts/build_user_guide.cjs', 'frontend/src/content/user-guide.ar.json']:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, target)
    subprocess.run(['node', str(tmp_path / 'scripts/build_user_guide.cjs')], check=True, capture_output=True)
    expected = (tmp_path / 'docs/USER_GUIDE_AR.md').read_bytes()
    assert expected == (ROOT / 'docs/USER_GUIDE_AR.md').read_bytes()
    assert expected == (ROOT / 'frontend/public/docs/kura-user-guide-ar.md').read_bytes()


def test_public_markdown_response():
    response = requests.get(public_origin() + '/docs/kura-user-guide-ar.md', timeout=30)
    assert response.status_code == 200
    assert 'html' not in response.headers.get('Content-Type', '')
    assert response.content == (ROOT / 'docs/USER_GUIDE_AR.md').read_bytes()


def test_chapters_faq_and_limits():
    markdown = (ROOT / 'docs/USER_GUIDE_AR.md').read_text()
    assert len(GUIDE['sections']) == 12
    assert len(GUIDE['sections'][-1]['questions']) == 8
    for i, section in enumerate(GUIDE['sections'], 1):
        assert f'## {i}. {section["title"]}' in markdown
        for question in section.get('questions', []):
            assert question['answer'] in markdown
    for limit in ['5 ميجابايت', '10 ميجابايت', '25 ميجابايت', '100 ميجابايت', '10 ملفات في الدفعة']:
        assert limit in markdown
    files = next(section for section in GUIDE['sections'] if section['id'] == 'files')
    aggregate = files['notes'][0]
    for limit in ['30 ملفًا لمرفقات الطلب', '30 ملفًا للنتائج عبر جميع جولات التعديل', '10 ملفات']:
        assert limit in aggregate
    assert aggregate in markdown
    assert 'TEST_' not in markdown
    assert 'token=' not in markdown
    assert 'https://' not in markdown


def test_readme_paths_and_command():
    readme = (ROOT / 'README.md').read_text()
    assert 'docs/USER_GUIDE_AR.md' in readme
    assert 'node scripts/build_user_guide.cjs' in readme
    assert 'عدم نشر الموقع' in readme