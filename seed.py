"""Seed the placement_db with sample data (idempotent-ish for a fresh DB).
Default logins:
    admin      -> admin@placement.edu / admin123
    counselor  -> counselor@placement.edu / coun1234
    counselor2 -> dana@placement.edu / coun1234
    students   -> rohit@student.edu / stud1234  (CSE 3.4yr CGPA 8.9)
                  meera@student.edu / stud1234  (CSE 3.4yr CGPA 7.2)
                  arjun@student.edu / stud1234  (ECE 3.4yr CGPA 8.1)
                  kavya@student.edu / stud1234  (MEA 3.4yr CGPA 6.4 -> will fail TCS min 7.0)
"""

from werkzeug.security import generate_password_hash

from db import get_conn

P = lambda x: generate_password_hash(x)


def main():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # Clean slate (idempotent): delete children first, then parents.
            for tbl in ('counselling_sessions', 'applications', 'drives', 'role_skills',
                        'role_branches', 'eligibility', 'job_roles', 'companies',
                        'counselors', 'students', 'users'):
                cur.execute(f'DELETE FROM {tbl}')

            # ---------------- users: admin & counselors ----------------
            cur.execute("INSERT INTO users (email,password_hash,name,role) VALUES (%s,%s,%s,%s)",
                        ('admin@placement.edu', P('admin123'), 'Dr. Sharma', 'admin'))
            admin_id = cur.lastrowid

            cur.execute("INSERT INTO users (email,password_hash,name,role) VALUES (%s,%s,%s,%s)",
                        ('counselor@placement.edu', P('coun1234'), 'Ms. Priya Nair', 'counselor'))
            c2_id = cur.lastrowid
            cur.execute("INSERT INTO counselors (user_id, specialization) VALUES (%s,%s)",
                        (c2_id, 'Career guidance & interviews'))

            cur.execute("INSERT INTO users (email,password_hash,name,role) VALUES (%s,%s,%s,%s)",
                        ('dana@placement.edu', P('coun1234'), 'Mr. D' + 'ana Rao', 'counselor'))
            c3_id = cur.lastrowid
            cur.execute("INSERT INTO counselors (user_id, specialization) VALUES (%s,%s)",
                        (c3_id, 'Resume building & aptitude'))

            # ---------------- students ----------------
            students = [
                ('rohit@student.edu', 'Rohit Verma', 'CS2101', 'CSE', '4', 8.90, 0, 'Python, SQL, Flask', '9876500001'),
                ('meera@student.edu', 'Meera Iyer', 'CS2102', 'CSE', '4', 7.20, 1, 'Java, HTML, CSS', '9876500002'),
                ('arjun@student.edu', 'Arjun Reddy', 'EC2101', 'ECE', '4', 8.10, 0, 'C, MySQL, JavaScript', '9876500003'),
                ('kavya@student.edu', 'Kavya S', 'ME2101', 'ME', '4', 6.40, 2, 'AutoCAD, SolidWorks', '9876500004'),
            ]
            for (email, name, roll, branch, year, cgpa, back, skills, phone) in students:
                cur.execute("INSERT INTO users (email,password_hash,name,role) VALUES (%s,%s,%s,'student')",
                            (email, P('stud1234'), name))
                uid = cur.lastrowid
                cur.execute(
                    """INSERT INTO students (user_id, rollno, branch, academic_year, cgpa, backlogs, skills, phone)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (uid, roll, branch, year, cgpa, back, skills, phone))
                print(f'  + student {name} ({roll}) id={cur.lastrowid}')

            # ---------------- companies ----------------
            cur.execute("INSERT INTO companies (name, sector, website, contact_email) VALUES (%s,%s,%s,%s)",
                        ('TechNova Systems', 'IT Services', 'https://technova.example', 'hr@technova.example'))
            technova_id = cur.lastrowid
            cur.execute("INSERT INTO companies (name, sector, website, contact_email) VALUES (%s,%s,%s,%s)",
                        ('InnoSoft Labs', 'Software Product', 'https://innosoft.example', 'careers@innosoft.example'))
            innosoft_id = cur.lastrowid

            # ---------------- roles + eligibility ----------------
            roles = [
                # (company, title, package, vacancies, desc, min_cgpa, max_back, year, branches, skills)
                (technova_id, 'Software Engineer', 6.50, 10, 'Full-stack developer role',
                 7.00, 1, '4', ['CSE', 'IT'], ['Python', 'SQL']),
                (technova_id, 'Data Analyst', 5.80, 5, 'Analyse datasets, build dashboards',
                 7.00, 1, '4', ['CSE', 'IT', 'ECE'], ['SQL', 'Excel']),
                (innosoft_id, 'Full Stack Developer', 8.00, 8, 'React + Python web apps',
                 7.50, 0, '4', ['CSE', 'IT'], ['Python', 'JavaScript', 'SQL']),
                (innosoft_id, 'Embedded Engineer', 6.00, 4, 'Firmware for IOT devices',
                 7.00, 1, '4', ['ECE'], ['C', 'SQL']),
            ]
            role_ids = []
            for (compid, title, pkg, vac, desc, mincgpa, maxback, year, branches, skills) in roles:
                cur.execute(
                    """INSERT INTO job_roles (company_id, title, package_lpa, vacancies, description)
                       VALUES (%s,%s,%s,%s,%s)""",
                    (compid, title, pkg, vac, desc))
                rid = cur.lastrowid
                role_ids.append(rid)
                cur.execute(
                    """INSERT INTO eligibility (role_id, min_cgpa, max_backlogs, academic_year)
                       VALUES (%s,%s,%s,%s)""",
                    (rid, mincgpa, maxback, year))
                for b in branches:
                    cur.execute("INSERT INTO role_branches (role_id, branch) VALUES (%s,%s)", (rid, b))
                for sk in skills:
                    cur.execute("INSERT INTO role_skills (role_id, skill) VALUES (%s,%s)", (rid, sk))

            # ---------------- drives ----------------
            cur.execute(
                """INSERT INTO drives (role_id, apply_deadline, drive_date, venue, status)
                   VALUES (%s, '2026-10-05 23:59:00', '2026-10-12', 'Online - TechNova Portal', 'open')""",
                (role_ids[0],))
            cur.execute(
                """INSERT INTO drives (role_id, apply_deadline, drive_date, venue, status)
                   VALUES (%s, '2026-09-25 23:59:00', '2026-10-02', 'Main Block Auditorium', 'open')""",
                (role_ids[2],))
            cur.execute(
                """INSERT INTO drives (role_id, apply_deadline, drive_date, venue, status)
                   VALUES (%s, '2026-09-30 23:59:00', '2026-10-08', 'Main Block Auditorium', 'open')""",
                (role_ids[1],))

            # ---------------- applications (drives) ----------------
            # Get student ids
            cur.execute("SELECT u.email, s.id FROM students s JOIN users u ON u.id=s.user_id")
            sid_by_email = {r['email']: r['id'] for r in cur.fetchall()}
            cur.execute("SELECT id, role_id, status FROM drives ORDER BY id")
            drives = cur.fetchall()
            se_drive = drives[0]['id']        # Software Engineer (open)
            fs_drive = drives[1]['id']        # Full Stack Developer (open)
            da_drive = drives[2]['id']        # Data Analyst (becomes completed)

            # Applications to the open drives
            cur.execute("CALL sp_apply_drive(%s,%s)", (sid_by_email['rohit@student.edu'], se_drive))
            cur.execute("CALL sp_apply_drive(%s,%s)", (sid_by_email['meera@student.edu'], se_drive))
            cur.execute("CALL sp_apply_drive(%s,%s)", (sid_by_email['rohit@student.edu'], fs_drive))

            # Data Analyst drive: apply while open, then close it and publish results
            cur.execute("CALL sp_apply_drive(%s,%s)", (sid_by_email['rohit@student.edu'], da_drive))
            cur.execute("CALL sp_apply_drive(%s,%s)", (sid_by_email['arjun@student.edu'], da_drive))
            cur.execute("UPDATE drives SET status='completed' WHERE id=%s", (da_drive,))
            cur.execute("CALL sp_set_result(%s,%s,'selected')", (da_drive, sid_by_email['rohit@student.edu']))
            cur.execute("CALL sp_set_result(%s,%s,'rejected')", (da_drive, sid_by_email['arjun@student.edu']))

            # ---------------- counselling sessions ----------------
            cur.execute("SELECT id FROM counselors ORDER BY id")
            counselor_ids = [r['id'] for r in cur.fetchall()]
            cur.execute(
                """INSERT INTO counselling_sessions (student_id, counselor_id, slot_time, status, feedback)
                   VALUES (%s,%s, '2026-09-25 10:00:00', 'booked', NULL)""",
                (sid_by_email['rohit@student.edu'], counselor_ids[0]))
            cur.execute(
                """INSERT INTO counselling_sessions (student_id, counselor_id, slot_time, status, feedback)
                   VALUES (%s,%s, '2026-09-22 14:30:00', 'completed', 'Solid resume, focus on SQL depth')""",
                (sid_by_email['kavya@student.edu'], counselor_ids[0]))

            conn.commit()
            print(f'Seeded: 1 admin, {len(counselor_ids)} counselor(s), {len(students)} students, '
                  f'{len(roles)} roles, {len(drives)} drives')
            print('Logins -> admin@placement.edu/admin123, counselor@placement.edu/coun1234, '
                  'rohit@student.edu/stud1234')
    except Exception as e:
        conn.rollback()
        print('Seed failed:', e)
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    main()