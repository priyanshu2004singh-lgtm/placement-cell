"""
Student Counselling & Placement Cell - Flask REST API
Backend: Python + Flask + MySQL (PyMySQL)
Frontend: served as static HTML/CSS/JS, talks to /api/*
"""

from functools import wraps
from datetime import datetime

from flask import Flask, session, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import pymysql

from config import SECRET_KEY
from db import get_conn

app = Flask(__name__, static_folder='static')
app.secret_key = SECRET_KEY


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------
def api_error(msg, status=400):
    return jsonify(error=msg), status


def extract_err(e):
    """Return a friendly message from a MySQL exception."""
    err = getattr(e, 'args', (0, str(e)))
    code = err[0] if err else 0
    msg = err[1] if len(err) > 1 else str(e)
    return code, str(msg)


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'uid' not in session:
            return api_error('Login required', 401)
        return f(*args, **kwargs)
    return wrapper


def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if 'uid' not in session:
                return api_error('Login required', 401)
            if session.get('role') not in roles:
                return api_error('Forbidden - role not allowed', 403)
            return f(*args, **kwargs)
        return wrapper
    return decorator


def current_user():
    return {'uid': session['uid'], 'role': session['role'], 'name': session['name']}


# ---------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------
@app.post('/api/register')
def register():
    data = request.get_json() or {}
    name, email, password = data.get('name'), data.get('email'), data.get('password')
    rollno = data.get('rollno')
    branch = data.get('branch')
    year = data.get('academic_year')
    cgpa = data.get('cgpa')
    if not all([name, email, password, rollno, branch, year, cgpa]):
        return api_error('All fields are required')

    try:
        cgpa = float(cgpa)
        backlogs = int(data.get('backlogs') or 0)
        if cgpa < 0 or cgpa > 10 or backlogs < 0:
            return api_error('Invalid CGPA or backlogs')
    except (TypeError, ValueError):
        return api_error('CGPA / backlogs must be numeric')

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users (email, password_hash, name, role) VALUES (%s,%s,%s,'student')",
                (email, generate_password_hash(password), name))
            uid = cur.lastrowid
            cur.execute(
                """INSERT INTO students
                   (user_id, rollno, branch, academic_year, cgpa, backlogs, skills, phone)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                (uid, rollno, branch, year, cgpa, backlogs,
                 data.get('skills'), data.get('phone')))
        conn.commit()
        return jsonify(id=uid, email=email, name=name, role='student'), 201
    except pymysql.err.IntegrityError as e:
        conn.rollback()
        code, msg = extract_err(e)
        if code == 1062:
            return api_error('Email or roll number already registered')
        return api_error(msg)
    finally:
        conn.close()


@app.post('/api/login')
def login():
    data = request.get_json() or {}
    email, password = data.get('email'), data.get('password')
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, email, name, role, password_hash FROM users WHERE email=%s", (email,))
            user = cur.fetchone()
            if not user or not check_password_hash(user['password_hash'], password or ''):
                return api_error('Invalid email or password', 401)
            session['uid'] = user['id']
            session['role'] = user['role']
            session['name'] = user['name']
            return jsonify(id=user['id'], email=user['email'], name=user['name'], role=user['role'])
    finally:
        conn.close()


@app.post('/api/logout')
def logout():
    session.clear()
    return jsonify(ok=True)


@app.get('/api/me')
@login_required
def me():
    me = current_user()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if me['role'] == 'student':
                cur.execute("SELECT * FROM students WHERE user_id=%s", (me['uid'],))
                profile = cur.fetchone()
            elif me['role'] == 'counselor':
                cur.execute("SELECT * FROM counselors WHERE user_id=%s", (me['uid'],))
                profile = cur.fetchone()
            else:
                profile = None
        return jsonify(user=me, profile=profile)
    finally:
        conn.close()


# ---------------------------------------------------------------------
# Student profile
# ---------------------------------------------------------------------
@app.put('/api/student/profile')
@login_required
@role_required('student')
def update_profile():
    data = request.get_json() or {}
    try:
        cgpa = float(data.get('cgpa', 0)) or None
        backlogs = int(data.get('backlogs', 0)) or 0
        if cgpa is not None and (cgpa < 0 or cgpa > 10):
            return api_error('CGPA must be between 0 and 10')
        if backlogs < 0:
            return api_error('Backlogs cannot be negative')
    except (TypeError, ValueError):
        return api_error('CGPA / backlogs must be numeric')

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE students
                   SET cgpa=%s, backlogs=%s, skills=%s, phone=%s, resume_url=%s
                   WHERE user_id=%s""",
                (cgpa, backlogs, data.get('skills'), data.get('phone'),
                 data.get('resume_url'), session['uid']))
        conn.commit()
        return jsonify(ok=True)
    finally:
        conn.close()


# ---------------------------------------------------------------------
# Companies (admin CRUD, everyone can list)
# ---------------------------------------------------------------------
@app.get('/api/companies')
@login_required
def list_companies():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM companies ORDER BY name")
            rows = cur.fetchall()
        return jsonify(companies=rows)
    finally:
        conn.close()


@app.post('/api/companies')
@login_required
@role_required('admin')
def create_company():
    data = request.get_json() or {}
    name = data.get('name')
    if not name:
        return api_error('Company name is required')
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO companies (name, sector, website, contact_email) VALUES (%s,%s,%s,%s)",
                        (name, data.get('sector'), data.get('website'), data.get('contact_email')))
        conn.commit()
        return jsonify(id=cur.lastrowid, ok=True), 201
    except pymysql.err.IntegrityError:
        return api_error('Company already exists')
    finally:
        conn.close()


@app.put('/api/companies/<int:cid>')
@login_required
@role_required('admin')
def update_company(cid):
    data = request.get_json() or {}
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE companies SET name=%s, sector=%s, website=%s, contact_email=%s WHERE id=%s",
                (data.get('name'), data.get('sector'), data.get('website'),
                 data.get('contact_email'), cid))
        conn.commit()
        return jsonify(ok=True)
    finally:
        conn.close()


@app.delete('/api/companies/<int:cid>')
@login_required
@role_required('admin')
def delete_company(cid):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM companies WHERE id=%s", (cid,))
        conn.commit()
        return jsonify(ok=True)
    finally:
        conn.close()


# ---------------------------------------------------------------------
# Job roles + eligibility
# ---------------------------------------------------------------------
def _role_detail(cur, rid):
    cur.execute(
        """SELECT r.id, r.title, r.package_lpa, r.vacancies, r.description,
                  c.id AS company_id, c.name AS company,
                  e.min_cgpa, e.max_backlogs, e.academic_year,
                  (SELECT COUNT(*) FROM drives d WHERE d.role_id=r.id) AS drive_count
           FROM job_roles r
           JOIN companies c ON c.id=r.company_id
           JOIN eligibility e ON e.role_id=r.id
           WHERE r.id=%s""", (rid,))
    role = cur.fetchone()
    if not role:
        return None
    cur.execute("SELECT branch FROM role_branches WHERE role_id=%s", (rid,))
    role['branches'] = [b['branch'] for b in cur.fetchall()]
    cur.execute("SELECT skill FROM role_skills WHERE role_id=%s", (rid,))
    role['skills'] = [s['skill'] for s in cur.fetchall()]
    return role


@app.get('/api/roles')
@login_required
def list_roles():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT r.id, r.title, r.package_lpa, r.vacancies, c.name AS company,
                          e.min_cgpa, e.max_backlogs, e.academic_year,
                          GROUP_CONCAT(DISTINCT rb.branch ORDER BY rb.branch) AS branches,
                          GROUP_CONCAT(DISTINCT rs.skill ORDER BY rs.skill) AS skills
                   FROM job_roles r
                   JOIN companies c ON c.id=r.company_id
                   JOIN eligibility e ON e.role_id=r.id
                   LEFT JOIN role_branches rb ON rb.role_id=r.id
                   LEFT JOIN role_skills rs ON rs.role_id=r.id
                   GROUP BY r.id ORDER BY r.id""")
            rows = cur.fetchall()
        return jsonify(roles=rows)
    finally:
        conn.close()


@app.get('/api/roles/<int:rid>')
@login_required
def get_role(rid):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            role = _role_detail(cur, rid)
        return jsonify(role=role)
    finally:
        conn.close()


@app.post('/api/roles')
@login_required
@role_required('admin')
def create_role():
    data = request.get_json() or {}
    required = ['company_id', 'title', 'package_lpa', 'min_cgpa', 'max_backlogs', 'academic_year']
    if any(data.get(k) is None for k in required):
        return api_error('Missing role fields')
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO job_roles (company_id, title, package_lpa, vacancies, description)
                   VALUES (%s,%s,%s,%s,%s)""",
                (data['company_id'], data['title'], float(data['package_lpa']),
                 int(data.get('vacancies') or 1), data.get('description')))
            rid = cur.lastrowid
            cur.execute(
                """INSERT INTO eligibility (role_id, min_cgpa, max_backlogs, academic_year)
                   VALUES (%s,%s,%s,%s)""",
                (rid, float(data['min_cgpa']), int(data['max_backlogs']), data['academic_year']))
            for branch in data.get('branches') or []:
                cur.execute("INSERT INTO role_branches (role_id, branch) VALUES (%s,%s)", (rid, branch))
            for skill in data.get('skills') or []:
                cur.execute("INSERT INTO role_skills (role_id, skill) VALUES (%s,%s)", (rid, skill))
        conn.commit()
        return jsonify(id=rid, ok=True), 201
    except pymysql.err.MySQLError as e:
        conn.rollback()
        code, msg = extract_err(e)
        return api_error(msg)
    finally:
        conn.close()


@app.delete('/api/roles/<int:rid>')
@login_required
@role_required('admin')
def delete_role(rid):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM job_roles WHERE id=%s", (rid,))
        conn.commit()
        return jsonify(ok=True)
    finally:
        conn.close()


# ---------------------------------------------------------------------
# Drives
# ---------------------------------------------------------------------
@app.get('/api/drives')
@login_required
def list_drives():
    role = session['role']
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if role == 'student':
                cur.execute("SELECT id FROM students WHERE user_id=%s", (session['uid'],))
                s = cur.fetchone()
                if not s:
                    return api_error('Student profile not found')
                sid = s['id']
                cur.execute(
                    """SELECT v.*, d.role_id,
                              CASE WHEN a.id IS NULL THEN 0 ELSE 1 END AS applied
                       FROM v_open_drives v
                       JOIN drives d ON d.id = v.drive_id
                       JOIN role_branches rb ON rb.role_id = d.role_id AND rb.branch =
                              (SELECT branch FROM students WHERE id=%s)
                       LEFT JOIN applications a
                              ON a.drive_id = v.drive_id AND a.student_id = %s
                       WHERE v.academic_year = (SELECT academic_year FROM students WHERE id=%s)
                         AND v.min_cgpa <= (SELECT cgpa FROM students WHERE id=%s)
                         AND v.max_backlogs >= (SELECT backlogs FROM students WHERE id=%s)
                         AND d.status = 'open'
                       ORDER BY v.apply_deadline""",
                    (sid, sid, sid, sid, sid))
                drives = cur.fetchall()
            else:
                cur.execute(
                    """SELECT d.id, d.apply_deadline, d.drive_date, d.venue, d.status,
                              r.title AS role_title, c.name AS company,
                              (SELECT COUNT(*) FROM applications a
                                WHERE a.drive_id=d.id AND a.status='applied') AS applied_count,
                              (SELECT COUNT(*) FROM applications a
                                WHERE a.drive_id=d.id AND a.status='shortlisted') AS shortlisted_count
                       FROM drives d
                       JOIN job_roles r ON r.id=d.role_id
                       JOIN companies c ON c.id=r.company_id
                       ORDER BY d.drive_id""")
                drives = cur.fetchall()
        return jsonify(drives=drives)
    finally:
        conn.close()


@app.get('/api/drives/<int:did>')
@login_required
def get_drive(did):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT d.id, d.apply_deadline, d.drive_date, d.venue, d.status AS drive_status,
                          r.id AS role_id, r.title, r.package_lpa, r.vacancies, r.description,
                          c.id AS company_id, c.name AS company, c.sector,
                          e.min_cgpa, e.max_backlogs, e.academic_year
                   FROM drives d
                   JOIN job_roles r ON r.id=d.role_id
                   JOIN companies c ON c.id=r.company_id
                   JOIN eligibility e ON e.role_id=r.id
                   WHERE d.id=%s""", (did,))
            d = cur.fetchone()
            if not d:
                return api_error('Drive not found', 404)
            cur.execute("SELECT branch FROM role_branches WHERE role_id=%s", (d['role_id'],))
            d['branches'] = [b['branch'] for b in cur.fetchall()]
            cur.execute("SELECT skill FROM role_skills WHERE role_id=%s", (d['role_id'],))
            d['skills'] = [s['skill'] for s in cur.fetchall()]

            if session['role'] == 'student':
                cur.execute("SELECT id FROM students WHERE user_id=%s", (session['uid'],))
                s = cur.fetchone()
                d['applied'] = False
                if s:
                    cur.execute(
                        "SELECT id, status FROM applications WHERE student_id=%s AND drive_id=%s",
                        (s['id'], did))
                    app_row = cur.fetchone()
                    if app_row:
                        d['applied'] = True
                        d['application_status'] = app_row['status']
        return jsonify(drive=d)
    finally:
        conn.close()


@app.post('/api/drives')
@login_required
@role_required('admin')
def create_drive():
    data = request.get_json() or {}
    if not data.get('role_id') or not data.get('apply_deadline') or not data.get('drive_date'):
        return api_error('role_id, apply_deadline and drive_date are required')
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO drives (role_id, apply_deadline, drive_date, venue, status)
                   VALUES (%s,%s,%s,%s,%s)""",
                (data['role_id'], data['apply_deadline'], data['drive_date'],
                 data.get('venue'), data.get('status', 'open')))
        conn.commit()
        return jsonify(id=cur.lastrowid, ok=True), 201
    finally:
        conn.close()


@app.put('/api/drives/<int:did>')
@login_required
@role_required('admin')
def update_drive(did):
    data = request.get_json() or {}
    allowed = ['role_id', 'apply_deadline', 'drive_date', 'venue', 'status']
    sets = [k for k in allowed if data.get(k) is not None]
    if not sets:
        return api_error('Nothing to update')
    if 'status' in sets and data['status'] not in ('open', 'closed', 'completed'):
        return api_error('Invalid drive status')
    sql = "UPDATE drives SET " + ", ".join(f"{k}=%s" for k in sets) + " WHERE id=%s"
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, tuple(data[k] for k in sets) + (did,))
        conn.commit()
        return jsonify(ok=True)
    finally:
        conn.close()


@app.delete('/api/drives/<int:did>')
@login_required
@role_required('admin')
def delete_drive(did):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM drives WHERE id=%s", (did,))
        conn.commit()
        return jsonify(ok=True)
    finally:
        conn.close()


# ---------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------
@app.post('/api/drives/<int:did>/apply')
@login_required
@role_required('student')
def apply_drive(did):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM students WHERE user_id=%s", (session['uid'],))
            s = cur.fetchone()
            if not s:
                return api_error('Student profile not found')
            sid = s['id']
            # Atomic apply -> stored procedure -> trigger validates eligibility
            cur.execute("CALL sp_apply_drive(%s,%s)", (sid, did))
        conn.commit()
        return jsonify(message='Applied successfully'), 201
    except pymysql.err.MySQLError as e:
        conn.rollback()
        code, msg = extract_err(e)
        if code == 1062:
            return api_error('You have already applied to this drive')
        return api_error(msg or 'Could not apply', 400)
    finally:
        conn.close()


@app.get('/api/student/applications')
@login_required
@role_required('student')
def my_applications():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM students WHERE user_id=%s", (session['uid'],))
            s = cur.fetchone()
            if not s:
                return api_error('Student profile not found')
            cur.execute(
                """SELECT a.id, a.status AS application_status, a.applied_at,
                          d.id AS drive_id, d.apply_deadline, d.drive_date, d.status AS drive_status,
                          c.name AS company, r.title AS role_title, r.package_lpa
                   FROM applications a
                   JOIN drives d ON d.id=a.drive_id
                   JOIN job_roles r ON r.id=d.role_id
                   JOIN companies c ON c.id=r.company_id
                   WHERE a.student_id=%s
                   ORDER BY a.applied_at DESC""", (s['id'],))
            rows = cur.fetchall()
        return jsonify(applications=rows)
    finally:
        conn.close()


@app.get('/api/drives/<int:did>/applications')
@login_required
@role_required('admin', 'counselor')
def drive_applications(did):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT a.id, a.status, a.applied_at, a.student_id,
                          s.rollno, u.name, s.branch, s.academic_year, s.cgpa, s.backlogs, s.skills
                   FROM applications a
                   JOIN students s ON s.id=a.student_id
                   JOIN users u ON u.id=s.user_id
                   WHERE a.drive_id=%s
                   ORDER BY s.cgpa DESC""", (did,))
            rows = cur.fetchall()
        return jsonify(applications=rows)
    finally:
        conn.close()


@app.post('/api/drives/<int:did>/shortlist')
@login_required
@role_required('admin')
def shortlist_drive(did):
    data = request.get_json() or {}
    min_cgpa = float(data.get('min_cgpa') or 0)
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("CALL sp_shortlist(%s,%s)", (did, min_cgpa))
        conn.commit()
        return jsonify(message='Shortlist updated')
    finally:
        conn.close()


@app.post('/api/drives/<int:did>/results')
@login_required
@role_required('admin')
def set_result(did):
    data = request.get_json() or {}
    student_id = data.get('student_id')
    status = data.get('status')
    if not student_id or status not in ('selected', 'rejected'):
        return api_error('student_id and status(selected|rejected) required')
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("CALL sp_set_result(%s,%s,%s)", (did, student_id, status))
        conn.commit()
        return jsonify(message=f'Result recorded: {status}')
    except pymysql.err.MySQLError as e:
        conn.rollback()
        _, msg = extract_err(e)
        return api_error(msg or 'Could not record result', 400)
    finally:
        conn.close()


@app.get('/api/shortlist')
@login_required
@role_required('admin', 'counselor')
def shortlist_view():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT v.company, v.role_title, v.student_name, v.rollno, v.branch,
                          v.cgpa, v.status
                   FROM v_shortlist v
                   ORDER BY v.company, v.role_title""")
            rows = cur.fetchall()
        return jsonify(shortlists=rows)
    finally:
        conn.close()


# ---------------------------------------------------------------------
# Counselling
# ---------------------------------------------------------------------
@app.get('/api/counselors')
@login_required
def list_counselors():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT c.id, u.name, c.specialization FROM counselors c
                   JOIN users u ON u.id=c.user_id ORDER BY u.name""")
            rows = cur.fetchall()
        return jsonify(counselors=rows)
    finally:
        conn.close()


@app.post('/api/sessions/book')
@login_required
@role_required('student')
def book_session():
    data = request.get_json() or {}
    counselor_id = data.get('counselor_id')
    slot_time = data.get('slot_time')
    if not counselor_id or not slot_time:
        return api_error('counselor_id and slot_time are required')
    try:
        slot_dt = datetime.strptime(slot_time, '%Y-%m-%dT%H:%M')
    except ValueError:
        return api_error('Invalid slot_time format (use YYYY-MM-DDTHH:MM)')

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM students WHERE user_id=%s", (session['uid'],))
            s = cur.fetchone()
            if not s:
                return api_error('Student profile not found')
            sid = s['id']
            if slot_dt <= datetime.now():
                return api_error('Cannot book a slot in the past')
            cur.execute(
                "SELECT COUNT(*) AS n FROM counselling_sessions WHERE counselor_id=%s AND slot_time=%s",
                (counselor_id, slot_time))
            if cur.fetchone()['n'] > 0:
                return api_error('Slot already booked')
            cur.execute(
                """INSERT INTO counselling_sessions (student_id, counselor_id, slot_time)
                   VALUES (%s,%s,%s)""", (sid, counselor_id, slot_time))
        conn.commit()
        return jsonify(message='Session booked'), 201
    except pymysql.err.IntegrityError:
        conn.rollback()
        return api_error('Slot unavailable', 400)
    finally:
        conn.close()


@app.get('/api/sessions')
@login_required
def list_sessions():
    role = session['role']
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            base = """SELECT cs.id, cs.slot_time, cs.status, cs.feedback,
                             s.id AS student_id, s.rollno, su.name AS student_name,
                             cu.name AS counselor_name, cs.counselor_id
                      FROM counselling_sessions cs
                      JOIN students s ON s.id=cs.student_id
                      JOIN users su ON su.id=s.user_id
                      JOIN counselors cc ON cc.id=cs.counselor_id
                      JOIN users cu ON cu.id=cc.user_id
                   """
            params = ()
            if role == 'student':
                cur.execute("SELECT id FROM students WHERE user_id=%s", (session['uid'],))
                s = cur.fetchone()
                if not s:
                    return jsonify(sessions=[])
                base += " WHERE cs.student_id=%s ORDER BY cs.slot_time"
                params = (s['id'],)
            elif role == 'counselor':
                cur.execute("SELECT id FROM counselors WHERE user_id=%s", (session['uid'],))
                c = cur.fetchone()
                if not c:
                    return jsonify(sessions=[])
                base += " WHERE cs.counselor_id=%s ORDER BY cs.slot_time"
                params = (c['id'],)
            else:
                base += " ORDER BY cs.slot_time"
            cur.execute(base, params)
            rows = cur.fetchall()
        return jsonify(sessions=rows)
    finally:
        conn.close()


@app.post('/api/sessions/<int:sid>/complete')
@login_required
@role_required('counselor', 'admin')
def complete_session(sid):
    data = request.get_json() or {}
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE counselling_sessions SET status='completed', feedback=%s WHERE id=%s",
                (data.get('feedback'), sid))
        conn.commit()
        return jsonify(ok=True)
    finally:
        conn.close()


@app.post('/api/sessions/<int:sid>/cancel')
@login_required
@role_required('student', 'admin')
def cancel_session(sid):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE counselling_sessions SET status='cancelled' WHERE id=%s", (sid,))
        conn.commit()
        return jsonify(ok=True)
    finally:
        conn.close()


# ---------------------------------------------------------------------
# Dashboard reports
# ---------------------------------------------------------------------
@app.get('/api/dashboard')
@login_required
@role_required('admin')
def dashboard():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM v_dashboard_stats")
            stats = cur.fetchone()
            cur.execute("SELECT * FROM v_placement_report ORDER BY company")
            report = cur.fetchall()
            cur.execute(
                """SELECT a.id, a.status, a.applied_at, u.name AS student, s.branch,
                          c.name AS company, r.title AS role_title
                   FROM applications a
                   JOIN students s ON s.id=a.student_id
                   JOIN users u ON u.id=s.user_id
                   JOIN drives d ON d.id=a.drive_id
                   JOIN job_roles r ON r.id=d.role_id
                   JOIN companies c ON c.id=r.company_id
                   ORDER BY a.applied_at DESC LIMIT 10""")
            recent = cur.fetchall()
        return jsonify(stats=stats, report=report, recent=recent)
    finally:
        conn.close()


# ---------------------------------------------------------------------
# Static pages
# ---------------------------------------------------------------------
@app.route('/')
def index():
    return app.send_static_file('login.html')


@app.route('/<page>.html')
def serve_page(page):
    return app.send_static_file(f'{page}.html')


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=True, threaded=True)