import json
import urllib.request

BASE = 'http://127.0.0.1:5000'

def post(path, data, cookie=None):
    body = json.dumps(data).encode()
    req = urllib.request.Request(BASE + path, data=body, headers={'Content-Type': 'application/json'})
    if cookie:
        req.add_header('Cookie', cookie)
    try:
        resp = urllib.request.urlopen(req)
        return resp.getcode(), json.loads(resp.read()), resp.getheader('Set-Cookie')
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read()), None

def get(path, cookie=None):
    req = urllib.request.Request(BASE + path)
    if cookie:
        req.add_header('Cookie', cookie)
    try:
        resp = urllib.request.urlopen(req)
        return resp.getcode(), json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())

def put(path, data, cookie=None):
    body = json.dumps(data).encode()
    req = urllib.request.Request(BASE + path, data=body, method='PUT',
                                headers={'Content-Type': 'application/json'})
    if cookie:
        req.add_header('Cookie', cookie)
    try:
        resp = urllib.request.urlopen(req)
        return resp.getcode(), json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())

def login(email, password):
    code, data, cookie = post('/api/login', {'email': email, 'password': password})
    sid = cookie.split(';')[0].split('=')[1] if cookie else None
    return f'session={sid}' if sid else None

print('='*60)
print('STUDENT COUNSELLING & PLACEMENT CELL - INTEGRATION TEST')
print('='*60)

# 1. Auth
c = login('admin@placement.edu', 'admin123')
print(f'\n[1] Admin login: OK')

c2 = login('rohit@student.edu', 'stud1234')
print(f'[2] Student login (Rohit): OK')

# 2. Dashboard (admin)
code, d = get('/api/dashboard', c)
print(f'\n[3] Dashboard stats: students={d["stats"]["total_students"]} placed={d["stats"]["placed_students"]} open_drives={d["stats"]["open_drives"]} applications={d["stats"]["total_applications"]} pending={d["stats"]["pending_sessions"]}')

# 3. Student open drives (Rohit: CSE, year4, cgpa 8.9, backlogs 0)
code, d = get('/api/drives', c2)
open_drives = ', '.join(str(x['role_title']) + '(applied=' + str(x['applied']) + ')' for x in d['drives'])
print(f'[4] Rohit open drives: {open_drives}')

# 4. Apply (already applied by seed — duplicate)
code, d, _ = post('/api/drives/1/apply', {}, c2)
print(f'[5] Duplicate apply SE drive: {d.get("error", "ok")}')

# 5. Ineligible apply (Meera year4/cgpa7.2 to FullStack min 7.5)
c3 = login('meera@student.edu', 'stud1234')
code, d, _ = post('/api/drives/2/apply', {}, c3)
print(f'[6] Meera apply FullStack (min 7.5, she has 7.2): {d.get("error", "ok")}')

# 6. Branch ineligible (Kavya ME to Embedded ECE-only)
c4 = login('kavya@student.edu', 'stud1234')
code, d = get('/api/drives', c4)
kavya_drives = ', '.join(str(x['role_title']) for x in d['drives']) or '(none)'
print(f'[7] Kavya (ME) open drives: {kavya_drives} (should be none - no ME roles)')

# 7. Register new student
code, d, _ = post('/api/register', {
    'name': 'Test Student', 'email': 'test@reg.edu', 'password': 'test1234',
    'rollno': 'CS2301', 'branch': 'CSE', 'academic_year': '4',
    'cgpa': 8.5, 'backlogs': 0, 'skills': 'Python, SQL'
})
print(f'\n[8] Register new student: id={d.get("id")} role={d.get("role")}')

# 8. Admin shortlist SE drive
code, d, _ = post('/api/drives/1/shortlist', {'min_cgpa': 8.0}, c)
print(f'\n[9] Shortlist SE (min 8.0): {d.get("message", d.get("error"))}')
code, d = get('/api/drives/1/applications', c)
print(f'[10] SE applicants after shortlist: {[(x["name"], x["status"]) for x in d["applications"]]}')

# 9. Block results while drive open
code, d, _ = post('/api/drives/1/results', {'student_id': 1, 'status': 'selected'}, c)
print(f'[11] Select while open: {d.get("error", "ok") if code != 200 else "FAIL — should be blocked"}')

# 10. Complete drive then select
code, d = put('/api/drives/1', {'status': 'completed'}, c)
print(f'[12] Close SE drive: {d.get("ok", d.get("error"))}')
code, d, _ = post('/api/drives/1/results', {'student_id': 1, 'status': 'selected'}, c)
print(f'[13] Select Rohit (drive completed): {d.get("message", d.get("error"))}')

# 11. Verify trigger updated student status
code, d = get('/api/dashboard', c)
print(f'[14] Placed count now: {d["stats"]["placed_students"]}')

# 12. Counselling session
c_new = login('rohit@student.edu', 'stud1234')
code, d, _ = post('/api/sessions/book', {'counselor_id': 1, 'slot_time': '2026-09-28T10:00'}, c_new)
print(f'\n[15] Book counselling: {d.get("message", d.get("error"))}')
code, d = get('/api/sessions', c_new)
print(f'[16] Rohit sessions: {[(s["status"], s["feedback"]) for s in d["sessions"]]}')

# 13. Counselor complete
coun = login('counselor@placement.edu', 'coun1234')
code, d = get('/api/sessions', coun)
if d['sessions']:
    sid = d['sessions'][0]['id']
    code, d, _ = post(f'/api/sessions/{sid}/complete', {'feedback': 'Good career planning discussion'}, coun)
    print(f'[17] Counselor complete session: ok')

# 14. Shortlist view
code, d = get('/api/shortlist', coun)
shortlist_rows = ', '.join(str(s['student_name']) + ':' + str(s['status']) + ':' + (s['company'] or '') for s in d['shortlists'])
print(f'[18] Shortlist view: {shortlist_rows}')

# 15. Auth: student -> admin endpoint
code, d = get('/api/dashboard', c_new)
print(f'\n[19] Auth student->admin: {code} {"(blocked)" if code != 200 else "FAIL"}')

# 16. Counselor cannot access admin
code, d = get('/api/dashboard', coun)
print(f'[20] Auth counselor->admin: {code} {"(blocked)" if code != 200 else "FAIL"}')

print('\n' + '='*60)
print('ALL TESTS COMPLETE')
print('='*60)
