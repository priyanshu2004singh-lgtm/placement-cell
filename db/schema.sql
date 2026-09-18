-- ============================================================
-- STUDENT COUNSELLING & PLACEMENT CELL - MySQL Schema
-- Demonstrates DBMS concepts:
--   * Normalization (3NF)
--   * Primary / Foreign keys, UNIQUE, CHECK, ENUM, NOT NULL
--   * Triggers (eligibility validation, placement status update)
--   * Views (aggregated reports)
--   * Stored Procedures (transactions / ACID)
--   * Indexes for query performance
-- ============================================================

DROP DATABASE IF EXISTS placement_db;
CREATE DATABASE placement_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE placement_db;

-- ============================================================
-- 1. TABLES
-- ============================================================

-- Login accounts for every actor (admin / counselor / student)
CREATE TABLE users (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    email         VARCHAR(120) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    name          VARCHAR(120) NOT NULL,
    role          ENUM('admin','counselor','student') NOT NULL,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- Student profile (1:1 with users)
CREATE TABLE students (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    user_id       INT NOT NULL UNIQUE,
    rollno        VARCHAR(20) NOT NULL UNIQUE,
    branch        ENUM('CSE','ECE','ME','CE','IT') NOT NULL,
    academic_year ENUM('1','2','3','4') NOT NULL,
    cgpa          DECIMAL(3,2) NOT NULL CHECK (cgpa BETWEEN 0.00 AND 10.00),
    backlogs      INT NOT NULL DEFAULT 0 CHECK (backlogs >= 0),
    skills        VARCHAR(255),
    phone         VARCHAR(15),
    resume_url    VARCHAR(255),
    status        ENUM('unplaced','seeking','placed') DEFAULT 'unplaced',
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_stud_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- Counselor profile (1:1 with users)
CREATE TABLE counselors (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    user_id         INT NOT NULL UNIQUE,
    specialization  VARCHAR(120),
    CONSTRAINT fk_coun_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- Recruiting companies
CREATE TABLE companies (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    name          VARCHAR(120) NOT NULL UNIQUE,
    sector        VARCHAR(80),
    website       VARCHAR(160),
    contact_email VARCHAR(120),
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- Job roles offered by companies
CREATE TABLE job_roles (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    company_id  INT NOT NULL,
    title       VARCHAR(120) NOT NULL,
    package_lpa DECIMAL(5,2) NOT NULL CHECK (package_lpa >= 0),
    vacancies   INT NOT NULL DEFAULT 1 CHECK (vacancies >= 0),
    description TEXT,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_role_company FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- Eligibility criteria (1:1 with job_roles)
CREATE TABLE eligibility (
    role_id       INT NOT NULL UNIQUE,
    min_cgpa      DECIMAL(3,2) NOT NULL DEFAULT 0.00 CHECK (min_cgpa BETWEEN 0.00 AND 10.00),
    max_backlogs  INT NOT NULL DEFAULT 0 CHECK (max_backlogs >= 0),
    academic_year ENUM('1','2','3','4') NOT NULL,
    CONSTRAINT fk_elig_role FOREIGN KEY (role_id) REFERENCES job_roles(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- Many-to-many: role <-> allowed branches
CREATE TABLE role_branches (
    role_id INT NOT NULL,
    branch  ENUM('CSE','ECE','ME','CE','IT') NOT NULL,
    PRIMARY KEY (role_id, branch),
    CONSTRAINT fk_rb_role FOREIGN KEY (role_id) REFERENCES job_roles(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- Many-to-many: role <-> required skills
CREATE TABLE role_skills (
    role_id INT NOT NULL,
    skill   VARCHAR(60) NOT NULL,
    PRIMARY KEY (role_id, skill),
    CONSTRAINT fk_rs_role FOREIGN KEY (role_id) REFERENCES job_roles(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- Placement drives (one per role)
CREATE TABLE drives (
    id             INT AUTO_INCREMENT PRIMARY KEY,
    role_id        INT NOT NULL,
    apply_deadline DATETIME NOT NULL,
    drive_date     DATE NOT NULL,
    venue          VARCHAR(160),
    status         ENUM('open','closed','completed') DEFAULT 'open',
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_drive_role FOREIGN KEY (role_id) REFERENCES job_roles(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- Student applications to drives
CREATE TABLE applications (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT NOT NULL,
    drive_id   INT NOT NULL,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status     ENUM('applied','shortlisted','selected','rejected','withdrawn') DEFAULT 'applied',
    CONSTRAINT fk_app_stud  FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
    CONSTRAINT fk_app_drive FOREIGN KEY (drive_id) REFERENCES drives(id) ON DELETE CASCADE,
    CONSTRAINT uniq_stud_drive UNIQUE (student_id, drive_id)
) ENGINE=InnoDB;

-- Counselling session bookings
CREATE TABLE counselling_sessions (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    student_id   INT NOT NULL,
    counselor_id INT NOT NULL,
    slot_time    DATETIME NOT NULL,
    status       ENUM('booked','completed','cancelled') DEFAULT 'booked',
    feedback     VARCHAR(500),
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_sess_stud  FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
    CONSTRAINT fk_sess_coun  FOREIGN KEY (counselor_id) REFERENCES counselors(id) ON DELETE CASCADE,
    CONSTRAINT chk_slot_future CHECK (slot_time > '2020-01-01 00:00:00')
) ENGINE=InnoDB;

-- ============================================================
-- 2. INDEXES
-- ============================================================
CREATE INDEX idx_stud_branch ON students(branch);
CREATE INDEX idx_stud_cgpa   ON students(cgpa);
CREATE INDEX idx_app_drive   ON applications(drive_id);
CREATE INDEX idx_app_status  ON applications(status);
CREATE INDEX idx_drive_status   ON drives(status);
CREATE INDEX idx_drive_deadline ON drives(apply_deadline);
CREATE INDEX idx_sess_slot   ON counselling_sessions(slot_time);
CREATE INDEX idx_role_company ON job_roles(company_id);

-- ============================================================
-- 3. TRIGGERS
-- ============================================================

-- Trigger 1: validate eligibility BEFORE an application is inserted.
-- If the student does not meet CGPA / backlogs / branch / year rules,
-- or the drive is not open, MySQL raises an error (45000) and rolls back.
DELIMITER $$
CREATE TRIGGER trg_application_eligibility
BEFORE INSERT ON applications
FOR EACH ROW
BEGIN
    DECLARE v_cgpa  DECIMAL(3,2);
    DECLARE v_branch VARCHAR(10);
    DECLARE v_back  INT;
    DECLARE v_year  VARCHAR(2);
    DECLARE v_drive_status VARCHAR(10);
    DECLARE v_min_cgpa DECIMAL(3,2);
    DECLARE v_max_back  INT;
    DECLARE v_req_year  VARCHAR(2);
    DECLARE v_role_id   INT;
    DECLARE v_ok_branch INT;

    SELECT cgpa, branch, backlogs, academic_year
      INTO v_cgpa, v_branch, v_back, v_year
      FROM students WHERE id = NEW.student_id;

    SELECT status INTO v_drive_status FROM drives WHERE id = NEW.drive_id;
    IF v_drive_status <> 'open' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Drive is not open for applications';
    END IF;

    IF (SELECT apply_deadline < NOW() FROM drives WHERE id = NEW.drive_id) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Application deadline has passed';
    END IF;

    SELECT role_id INTO v_role_id FROM drives WHERE id = NEW.drive_id;

    SELECT e.min_cgpa, e.max_backlogs, e.academic_year
      INTO v_min_cgpa, v_max_back, v_req_year
      FROM eligibility e WHERE e.role_id = v_role_id;

    IF v_cgpa < v_min_cgpa THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'CGPA below minimum requirement';
    END IF;
    IF v_back > v_max_back THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Too many backlogs for this role';
    END IF;
    IF v_year <> v_req_year THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Academic year not eligible for this role';
    END IF;

    SELECT COUNT(*) INTO v_ok_branch
      FROM role_branches WHERE role_id = v_role_id AND branch = v_branch;
    IF v_ok_branch = 0 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Branch not eligible for this role';
    END IF;
END$$
DELIMITER ;

-- Trigger 2: when a student's application becomes 'selected',
-- automatically update their placement status to 'placed'.
DELIMITER $$
CREATE TRIGGER trg_mark_selected
AFTER UPDATE ON applications
FOR EACH ROW
BEGIN
    IF NEW.status = 'selected' AND OLD.status <> 'selected' THEN
        UPDATE students SET status = 'placed' WHERE id = NEW.student_id;
    END IF;
END$$
DELIMITER ;

-- Trigger 3: when an application is deleted (withdrawn/rejected cleanup)
-- keep student status consistent.
DELIMITER $$
CREATE TRIGGER trg_unmark_student
AFTER DELETE ON applications
FOR EACH ROW
BEGIN
    IF OLD.status = 'selected' THEN
        UPDATE students SET status = 'unplaced'
        WHERE id = OLD.student_id
          AND NOT EXISTS (
              SELECT 1 FROM applications
              WHERE student_id = OLD.student_id AND status = 'selected'
          );
    END IF;
END$$
DELIMITER ;

-- ============================================================
-- 4. VIEWS
-- ============================================================

-- Open drives with eligibility summary (for the student dashboard)
CREATE VIEW v_open_drives AS
SELECT d.id          AS drive_id,
       c.name        AS company,
       r.title       AS role_title,
       r.package_lpa AS package,
       d.apply_deadline,
       d.drive_date,
       d.venue,
       e.min_cgpa,
       e.max_backlogs,
       e.academic_year
FROM drives d
JOIN job_roles  r ON r.id = d.role_id
JOIN companies  c ON c.id = r.company_id
JOIN eligibility e ON e.role_id = r.id;

-- Shortlist / selection results for counselors & admins
CREATE VIEW v_shortlist AS
SELECT a.drive_id,
       d.role_id,
       s.id AS student_id,
       s.rollno,
       u.name AS student_name,
       s.branch,
       s.cgpa,
       a.status,
       a.applied_at,
       c.name AS company,
       r.title AS role_title
FROM applications a
JOIN students  s ON s.id = a.student_id
JOIN users     u ON u.id = s.user_id
JOIN drives   d ON d.id = a.drive_id
JOIN job_roles r ON r.id = d.role_id
JOIN companies c ON c.id = r.company_id
WHERE a.status IN ('shortlisted','selected');

-- Placement report: selected counts grouped by company & role
CREATE VIEW v_placement_report AS
SELECT c.name  AS company,
       r.title AS role_title,
       COUNT(CASE WHEN a.status = 'selected' THEN 1 END) AS selected_count,
       COUNT(a.id) AS applied_count
FROM companies c
JOIN job_roles r  ON r.company_id = c.id
LEFT JOIN drives d         ON d.role_id = r.id
LEFT JOIN applications a   ON a.drive_id = d.id
GROUP BY c.id, r.id;

-- Dashboard aggregates
CREATE VIEW v_dashboard_stats AS
SELECT
    (SELECT COUNT(*) FROM students)                        AS total_students,
    (SELECT COUNT(*) FROM students WHERE status='placed')  AS placed_students,
    (SELECT COUNT(*) FROM companies)                       AS total_companies,
    (SELECT COUNT(*) FROM drives WHERE status='open')      AS open_drives,
    (SELECT COUNT(*) FROM applications)                    AS total_applications,
    (SELECT COUNT(*) FROM counselling_sessions WHERE status='booked') AS pending_sessions;

-- ============================================================
-- 5. STORED PROCEDURES  (demonstrate transactions / ACID)
-- ============================================================

-- Apply to a drive as an atomic transaction.
DELIMITER $$
CREATE PROCEDURE sp_apply_drive(IN p_student_id INT, IN p_drive_id INT)
BEGIN
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;
    START TRANSACTION;
    INSERT INTO applications (student_id, drive_id) VALUES (p_student_id, p_drive_id);
    COMMIT;
END$$
DELIMITER ;

-- Shortlist all 'applied' students of a drive whose CGPA >= threshold.
-- A single set-based UPDATE demonstrating relational power.
DELIMITER $$
CREATE PROCEDURE sp_shortlist(IN p_drive_id INT, IN p_min_cgpa DECIMAL(3,2))
BEGIN
    UPDATE applications a
    JOIN students s ON s.id = a.student_id
    SET a.status = 'shortlisted'
    WHERE a.drive_id = p_drive_id
      AND a.status = 'applied'
      AND s.cgpa >= p_min_cgpa;
END$$
DELIMITER ;

-- Record a selection/rejection result atomically (fires trg_mark_selected).
-- Business rule: results can only be published after the drive is 'completed'.
DELIMITER $$
CREATE PROCEDURE sp_set_result(IN p_drive_id INT, IN p_student_id INT, IN p_status VARCHAR(10))
BEGIN
    DECLARE v_drive_status VARCHAR(10);
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;
    IF p_status NOT IN ('selected','rejected') THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Status must be selected or rejected';
    END IF;
    SELECT status INTO v_drive_status FROM drives WHERE id = p_drive_id;
    IF v_drive_status <> 'completed' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Drive must be completed before announcing results';
    END IF;
    START TRANSACTION;
    UPDATE applications
       SET status = p_status
     WHERE drive_id = p_drive_id AND student_id = p_student_id;
    COMMIT;
END$$
DELIMITER ;