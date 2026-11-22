"""Minimal role-only fixtures following the existing isolated auth pattern; exact-ID cleanup."""
import hashlib
import json
import os
import secrets
from datetime import datetime, timezone
from pathlib import Path

import bcrypt
from bson import json_util
from dotenv import load_dotenv
from pymongo import MongoClient
import requests

load_dotenv('/app/frontend/.env')
load_dotenv('/app/backend/.env')
OUT = Path('/app/test_reports/guide')
STATE = OUT / 'private_state.json'


def fingerprint(db, collection, query):
    return hashlib.sha256(json_util.dumps(list(db[collection].find(query)), sort_keys=True).encode()).hexdigest()


def save(state):
    STATE.write_text(json.dumps(state))
    STATE.chmod(0o600)


def setup():
    assert not STATE.exists()
    db = MongoClient(os.environ['MONGO_URL'])[os.environ['DB_NAME']]
    tag = 'TEST_GUIDE_' + secrets.token_hex(5)
    state = {'tag': tag, 'ids': [], 'cookies': {}, 'original': {}}
    for collection in ['users', 'settings', 'owner_invites', 'courses']:
        state['original'][collection] = fingerprint(db, collection, {})
    OUT.mkdir(parents=True, exist_ok=True)
    save(state)
    base = os.environ['REACT_APP_BACKEND_URL'].rstrip('/')
    password = secrets.token_urlsafe(24)
    for role in ['visitor', 'student', 'employee', 'admin']:
        row = {'id': secrets.token_hex(12), 'name': tag + ' ' + role, 'email': tag.lower() + role + '@example.com', 'phone': '+1888' + str(secrets.randbelow(90000000) + 10000000), 'role': role, 'status': 'active', 'is_student': role == 'student', 'student_status': 'approved' if role == 'student' else 'none', 'krc': 'KRC' + secrets.token_hex(5).upper() if role == 'student' else None, 'registration_date': '2025-01-01' if role == 'student' else None, 'university': 'TEST university' if role == 'student' else '', 'research_field': 'TEST medicine' if role == 'student' else '', 'avatar_id': None, 'created_at': datetime.now(timezone.utc).isoformat()}
        state['ids'].append(row['id'])
        save(state)
        db.users.insert_one({**row, 'password_hash': bcrypt.hashpw(hashlib.sha256(password.encode()).digest(), bcrypt.gensalt()).decode()})
        with requests.Session() as session:
            session.headers.update({'X-Kura-Request': '1', 'Origin': base})
            response = session.post(base + '/api/auth/login', json={'email': row['email'], 'password': password}, timeout=30)
            assert response.status_code == 200, (role, response.status_code)
            state['cookies'][role] = session.cookies.get_dict()
            save(state)
    print('PASS four isolated role fixtures created; no content/settings/invitations changed')


def cleanup():
    state = json.loads(STATE.read_text())
    db = MongoClient(os.environ['MONGO_URL'])[os.environ['DB_NAME']]
    ids = state['ids']
    counts = {}
    for collection, query in [('sessions', {'user_id': {'$in': ids}}), ('audit', {'user_id': {'$in': ids}}), ('users', {'id': {'$in': ids}, 'name': {'$regex': '^' + state['tag']}})]:
        counts[collection] = db[collection].delete_many(query).deleted_count
    checks = {collection + '_preserved': fingerprint(db, collection, {}) == digest for collection, digest in state['original'].items()}
    checks['temporary_users_removed'] = db.users.count_documents({'id': {'$in': ids}}) == 0
    (OUT / 'role-cleanup.json').write_text(json.dumps({'deleted': counts, 'checks': checks}, indent=2))
    assert all(checks.values()), checks
    STATE.unlink()
    print('PASS cleanup', counts, checks)


if __name__ == '__main__':
    import sys
    cleanup() if '--cleanup' in sys.argv else setup()