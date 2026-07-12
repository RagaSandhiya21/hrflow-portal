-- ================================================================
--  HRFlow — Zoho People-Style HR Portal
--  PostgreSQL Schema  |  Use Case: S2-C-01
--  Designed as a Zoho People replica for Psiog
-- ================================================================
-- MODULE MAP
--  A.  Org & Identity          (organisations → departments → teams → employees)
--  B.  Authentication & Roles  (sessions, role_permissions)
--  C.  Employee Profile        (personal, emergency, bank/identity, documents)
--  D.  Leave Management        (types, policies, balances, requests, approvals)
--  E.  Attendance              (records, regularisation, shifts, summary)
--  F.  Payroll & Payslips      (salary components, monthly payroll, payslips)
--  G.  HR Requests             (employee → HR Admin tickets)
--  H.  IT / Asset Requests     (employee → IT Admin tickets)
--  I.  Announcements & Feed    (notice board like Zoho's Home tab)
--  J.  Org Chart               (reporting lines, already modelled in employees)
--  K.  AI Chatbot & RAG        (policy docs, chunks, query log, escalations)
--  L.  Notifications           (in-portal + email log)
--  M.  Audit & System          (immutable audit trail, system config)
-- ================================================================
--
-- REVISION NOTES (v1.1 — post-review fixes)
--  1. employee_id FK on historical/financial/audit-relevant tables changed
--     from ON DELETE CASCADE to ON DELETE RESTRICT (leave, attendance,
--     payroll, payslips, HR/IT requests, identity_info, documents,
--     profile_change_requests, chatbot logs/escalations, hr_request_comments).
--     Rationale: employees must never be hard-deleted once they have any
--     transactional history — offboarding should set
--     employees.employment_status = 'resigned'/'terminated' and
--     is_active = FALSE instead. RESTRICT enforces that at the DB layer
--     and protects compliance/audit retention. Tables holding only
--     current-state profile attributes with no compliance/audit value
--     (addresses, emergency_contacts, education, work_experience, shift
--     assignments, session records, notification logs, read receipts)
--     intentionally remain ON DELETE CASCADE.
--  2. Added CHECK (number_of_days > 0) on leave_requests.
--  3. Added a CHECK constraint on chatbot_query_log.query_category so the
--     7 documented categories are enforced in the DB, not just commented.
--  4. Flagged employee_identity_info as containing DPDP-Act-sensitive PII
--     (PAN/Aadhaar/bank) — see comment above that table. Encryption at
--     rest is an application-layer task, not modelled in DDL here.
--  5. Added a BUILD PRIORITY GUIDE (below) classifying all 53 tables into
--     three tiers, since the full schema is larger than what the RFP's
--     minimum coverage requirements or the 12-week/150-hour proposal
--     timeline strictly require. Build Tier 1 first, Tier 2 next; treat
--     Tier 3 as stretch goals only if time remains.
--
-- REVISION NOTES (v1.2 — found by actually running the schema + seed data)
--  1. employees.gender was VARCHAR(15) but its own CHECK constraint allows
--     'prefer_not_to_say' (17 chars) — every insert of that value would
--     have failed. Widened to VARCHAR(20).
--  2. salary_components.component_type was VARCHAR(20) but its own CHECK
--     constraint allows 'employer_contribution' (21 chars). Widened to
--     VARCHAR(25). Neither of these surfaced under v1.1's review because
--     review was read-only; both only showed up once real INSERTs were
--     attempted — worth doing for any hand-written CHECK-constrained
--     schema before trusting it.
--
-- ================================================================
-- BUILD PRIORITY GUIDE
-- ================================================================
-- TIER 1 — CORE (needed for Week 10 mid-term: SSO, 2 workflows, 3 policy
-- docs, basic RAG chatbot, escalation, leave + payslip data integrity)
--   organisations, departments, teams, employees, user_sessions,
--   role_permissions, leave_types, leave_policies, holiday_calendar,
--   employee_leave_balances, leave_requests, leave_approvals,
--   hr_policy_documents, rag_document_chunks, chatbot_sessions,
--   chatbot_query_log, escalation_tickets, salary_components,
--   employee_salary_structure, monthly_payroll, payslips, audit_log
--
-- TIER 2 — REQUIRED FOR FULL SCOPE (needed by Week 17 to cover the 4
-- minimum self-service transaction types + the proposal's attendance and
-- IT-request modules)
--   designations, locations, employee_addresses, emergency_contacts,
--   employee_identity_info, profile_change_requests,
--   hr_request_categories, hr_requests, hr_request_comments,
--   attendance_records, attendance_regularisation, attendance_edit_log,
--   attendance_monthly_summary, work_shifts, employee_shift_assignments,
--   it_requests, it_request_status_history, compensatory_off_log,
--   notifications, email_notification_log, system_config
--
-- TIER 3 — STRETCH (not required by the RFP's minimum coverage table or
-- by the proposal's own 7-module description; defer if Weeks 4-16 are
-- tight — Risk #5 in the proposal already flags scope creep across 7
-- modules as a High-impact risk)
--   employee_education, employee_work_experience, employee_documents,
--   assets, asset_categories, asset_assignments, announcements,
--   announcement_reads, employee_milestone_events, portal_quick_links
-- ================================================================


-- ================================================================
-- A. ORG & IDENTITY
-- ================================================================

CREATE TABLE organisations (
    org_id              SERIAL PRIMARY KEY,
    org_name            VARCHAR(150) NOT NULL,
    org_code            VARCHAR(30)  NOT NULL UNIQUE,
    logo_url            TEXT,
    website             VARCHAR(255),
    industry            VARCHAR(100),
    headquarters        TEXT,
    fiscal_year_start   DATE,                         -- e.g. 2025-04-01
    timezone            VARCHAR(60)  NOT NULL DEFAULT 'Asia/Kolkata',
    date_format         VARCHAR(20)  NOT NULL DEFAULT 'DD-MM-YYYY',
    currency_code       CHAR(3)      NOT NULL DEFAULT 'INR',
    created_at          TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE departments (
    department_id       SERIAL PRIMARY KEY,
    org_id              INT NOT NULL REFERENCES organisations(org_id) ON DELETE CASCADE,
    department_name     VARCHAR(100) NOT NULL,
    department_code     VARCHAR(20)  NOT NULL,
    description         TEXT,
    head_employee_id    INT,                          -- FK set after employees table
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (org_id, department_code)
);

CREATE TABLE locations (
    location_id         SERIAL PRIMARY KEY,
    org_id              INT NOT NULL REFERENCES organisations(org_id) ON DELETE CASCADE,
    location_name       VARCHAR(100) NOT NULL,
    address_line1       TEXT,
    address_line2       TEXT,
    city                VARCHAR(80),
    state               VARCHAR(80),
    country             VARCHAR(80)  NOT NULL DEFAULT 'India',
    pincode             VARCHAR(20),
    timezone            VARCHAR(60)  DEFAULT 'Asia/Kolkata',
    is_active           BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE teams (
    team_id             SERIAL PRIMARY KEY,
    org_id              INT NOT NULL REFERENCES organisations(org_id) ON DELETE CASCADE,
    department_id       INT NOT NULL REFERENCES departments(department_id) ON DELETE RESTRICT,
    team_name           VARCHAR(100) NOT NULL,
    team_code           VARCHAR(20)  NOT NULL UNIQUE,
    lead_employee_id    INT,                          -- FK set after employees table
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE designations (
    designation_id      SERIAL PRIMARY KEY,
    org_id              INT NOT NULL REFERENCES organisations(org_id) ON DELETE CASCADE,
    title               VARCHAR(100) NOT NULL,
    level               VARCHAR(30),                  -- e.g. 'junior','senior','lead','manager'
    is_active           BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE employees (
    employee_id         SERIAL PRIMARY KEY,
    org_id              INT NOT NULL REFERENCES organisations(org_id) ON DELETE CASCADE,
    employee_code       VARCHAR(30)  NOT NULL UNIQUE,  -- e.g. P484
    entra_object_id     VARCHAR(128) UNIQUE,            -- Microsoft Entra ID OID of a
                                                         -- SPECIFIC PERSON. NULL for shared
                                                         -- role accounts (see is_shared_admin
                                                         -- below) since those are accessed by
                                                         -- whichever real person is a member of
                                                         -- the mapped Entra ID security group —
                                                         -- there is no single fixed OID for them.
    email               VARCHAR(255) NOT NULL UNIQUE,
    work_email          VARCHAR(255) UNIQUE,
    full_name           VARCHAR(150) NOT NULL,
    first_name          VARCHAR(75)  NOT NULL,
    last_name           VARCHAR(75)  NOT NULL,
    display_name        VARCHAR(100),
    phone               VARCHAR(20),
    work_phone          VARCHAR(20),
    gender              VARCHAR(20)  CHECK (gender IN ('male','female','non_binary','prefer_not_to_say')),
    date_of_birth       DATE,
    blood_group         VARCHAR(5),
    marital_status      VARCHAR(15)  CHECK (marital_status IN ('single','married','divorced','widowed')),
    nationality         VARCHAR(60)  DEFAULT 'Indian',
    profile_photo_url   TEXT,
    -- org positioning
    designation_id      INT REFERENCES designations(designation_id) ON DELETE SET NULL,
    department_id       INT REFERENCES departments(department_id) ON DELETE SET NULL,
    team_id             INT REFERENCES teams(team_id) ON DELETE SET NULL,
    location_id         INT REFERENCES locations(location_id) ON DELETE SET NULL,
    manager_id          INT REFERENCES employees(employee_id) ON DELETE SET NULL,
    -- employment
    date_of_joining     DATE,
    date_of_confirmation DATE,
    employment_type     VARCHAR(20)  NOT NULL DEFAULT 'full_time'
                            CHECK (employment_type IN ('full_time','part_time','contract','intern')),
    employment_status   VARCHAR(20)  NOT NULL DEFAULT 'active'
                            CHECK (employment_status IN ('active','on_leave','notice_period','resigned','terminated')),
    role                VARCHAR(20)  NOT NULL DEFAULT 'employee'
                            CHECK (role IN ('employee','manager','hr_admin','it_admin','super_admin')),
    last_working_day    DATE,
    -- ── Shared functional-role accounts ──────────────────────────────────
    -- HR Admin and IT Admin are FUNCTIONAL identities, not individual people.
    -- Multiple real staff share the same "HR Admin" / "IT Admin" identity by
    -- being members of an Entra ID security group (entra_group_id below) —
    -- whoever is in that group is authenticated INTO this row, rather than a
    -- single named person owning it. Rows with is_shared_admin = TRUE must
    -- never be populated with personal data (DOB, address, emergency
    -- contact, bank/PAN identity info, leave allocation, payslips,
    -- attendance) — enforced in application code (see backend/app/deps.py
    -- assert_personal_employee) and reviewable via this flag.
    is_shared_admin     BOOLEAN NOT NULL DEFAULT FALSE,
    entra_group_id      VARCHAR(128),   -- Entra ID security group mapped to this shared account
                                         -- (e.g. "HR-Admins" / "IT-Admins" group object ID)
    -- system
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    created_by          INT REFERENCES employees(employee_id) ON DELETE SET NULL,
    created_at          TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMP NOT NULL DEFAULT NOW()
);

-- back-fill deferred FKs
ALTER TABLE departments ADD CONSTRAINT fk_dept_head
    FOREIGN KEY (head_employee_id) REFERENCES employees(employee_id) ON DELETE SET NULL;
ALTER TABLE teams ADD CONSTRAINT fk_team_lead
    FOREIGN KEY (lead_employee_id) REFERENCES employees(employee_id) ON DELETE SET NULL;


-- ================================================================
-- B. AUTHENTICATION & ROLE PERMISSIONS
-- ================================================================

CREATE TABLE user_sessions (
    session_id          BIGSERIAL PRIMARY KEY,
    employee_id         INT NOT NULL REFERENCES employees(employee_id) ON DELETE CASCADE,
    entra_access_token  TEXT,
    jwt_token_hash      VARCHAR(128) NOT NULL,         -- SHA-256 of JWT; never store raw
    issued_at           TIMESTAMP NOT NULL DEFAULT NOW(),
    expires_at          TIMESTAMP NOT NULL,
    ip_address          VARCHAR(45),
    user_agent          TEXT,
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    revoked_at          TIMESTAMP
);

CREATE TABLE role_permissions (
    permission_id       SERIAL PRIMARY KEY,
    role                VARCHAR(20)  NOT NULL
                            CHECK (role IN ('employee','manager','hr_admin','it_admin','super_admin')),
    module              VARCHAR(50)  NOT NULL,         -- e.g. 'leave','payslip','attendance'
    can_view            BOOLEAN NOT NULL DEFAULT FALSE,
    can_create          BOOLEAN NOT NULL DEFAULT FALSE,
    can_edit            BOOLEAN NOT NULL DEFAULT FALSE,
    can_delete          BOOLEAN NOT NULL DEFAULT FALSE,
    can_approve         BOOLEAN NOT NULL DEFAULT FALSE,
    scope               VARCHAR(20)  NOT NULL DEFAULT 'own'
                            CHECK (scope IN ('own','team','department','org')),
    UNIQUE (role, module)
);

-- Accountability trail for shared HR Admin / IT Admin logins.
-- Because those accounts are used by many real people (see
-- employees.is_shared_admin), we can't rely on employee_id alone to know
-- WHO actually performed an action — so every SSO login into a shared
-- account is logged here with the real person's identity as it came off
-- their own Entra ID token, independent of any employees row for them.
CREATE TABLE admin_account_access_log (
    access_log_id       BIGSERIAL PRIMARY KEY,
    admin_employee_id   INT NOT NULL REFERENCES employees(employee_id) ON DELETE CASCADE,
                            -- the shared account (e.g. the "HR Admin" row) that was used
    acting_entra_oid    VARCHAR(128) NOT NULL,   -- real person's Entra ID OID
    acting_email        VARCHAR(255) NOT NULL,   -- real person's email at login time
    acting_display_name VARCHAR(150),            -- real person's display name at login time
    ip_address          VARCHAR(45),
    user_agent          TEXT,
    logged_in_at        TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_admin_access_log_account ON admin_account_access_log(admin_employee_id, logged_in_at DESC);


-- ================================================================
-- C. EMPLOYEE PROFILE DETAILS
-- ================================================================

-- Address (permanent + current)
CREATE TABLE employee_addresses (
    address_id          SERIAL PRIMARY KEY,
    employee_id         INT NOT NULL REFERENCES employees(employee_id) ON DELETE CASCADE,
    address_type        VARCHAR(20)  NOT NULL CHECK (address_type IN ('permanent','current','other')),
    address_line1       TEXT         NOT NULL,
    address_line2       TEXT,
    city                VARCHAR(80)  NOT NULL,
    state               VARCHAR(80)  NOT NULL,
    country             VARCHAR(80)  NOT NULL DEFAULT 'India',
    pincode             VARCHAR(20),
    updated_at          TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (employee_id, address_type)
);

-- Emergency contacts (Zoho People has a dedicated tab for this)
CREATE TABLE emergency_contacts (
    contact_id          SERIAL PRIMARY KEY,
    employee_id         INT NOT NULL REFERENCES employees(employee_id) ON DELETE CASCADE,
    contact_name        VARCHAR(150) NOT NULL,
    relationship        VARCHAR(50),                   -- 'spouse','parent','sibling', etc.
    phone               VARCHAR(20)  NOT NULL,
    alternate_phone     VARCHAR(20),
    email               VARCHAR(255),
    is_primary          BOOLEAN NOT NULL DEFAULT FALSE,
    updated_at          TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Education (Zoho People → Education Details tab)
CREATE TABLE employee_education (
    education_id        SERIAL PRIMARY KEY,
    employee_id         INT NOT NULL REFERENCES employees(employee_id) ON DELETE CASCADE,
    degree              VARCHAR(100) NOT NULL,          -- B.Tech, MBA, etc.
    field_of_study      VARCHAR(100),
    institution_name    VARCHAR(200) NOT NULL,
    start_year          SMALLINT,
    end_year            SMALLINT,
    grade_or_percentage VARCHAR(20),
    is_highest          BOOLEAN NOT NULL DEFAULT FALSE
);

-- Work experience before joining
CREATE TABLE employee_work_experience (
    experience_id       SERIAL PRIMARY KEY,
    employee_id         INT NOT NULL REFERENCES employees(employee_id) ON DELETE CASCADE,
    company_name        VARCHAR(200) NOT NULL,
    designation         VARCHAR(100),
    start_date          DATE,
    end_date            DATE,
    responsibilities    TEXT,
    reason_for_leaving  TEXT
);

-- KYC & sensitive identity (bank, PAN, Aadhaar — HR-controlled)
-- SECURITY NOTE: pan_number, aadhaar_number, passport_number, and the bank_*
-- columns are sensitive PII (PAN/Aadhaar fall under India's DPDP Act).
-- This schema stores them as plain text for POC purposes only. Before any
-- non-demo use, encrypt these columns at rest (e.g. pgcrypto pgp_sym_encrypt,
-- or application-layer envelope encryption) and restrict SELECT to the
-- hr_admin role via row/column-level security.
CREATE TABLE employee_identity_info (
    identity_id         SERIAL PRIMARY KEY,
    employee_id         INT NOT NULL UNIQUE REFERENCES employees(employee_id) ON DELETE RESTRICT,
    pan_number          VARCHAR(15),
    aadhaar_number      VARCHAR(20),
    passport_number     VARCHAR(20),
    passport_expiry     DATE,
    uan_number          VARCHAR(20),                   -- EPF UAN
    esi_number          VARCHAR(20),
    bank_account_number VARCHAR(30),
    bank_name           VARCHAR(100),
    bank_ifsc           VARCHAR(20),
    bank_branch         VARCHAR(100),
    bank_account_type   VARCHAR(20)  DEFAULT 'savings'
                            CHECK (bank_account_type IN ('savings','current')),
    updated_at          TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_by          INT REFERENCES employees(employee_id) ON DELETE SET NULL
);

-- Sensitive field change requests (require HR Admin approval)
CREATE TABLE profile_change_requests (
    change_request_id   SERIAL PRIMARY KEY,
    employee_id         INT NOT NULL REFERENCES employees(employee_id) ON DELETE RESTRICT,
    field_group         VARCHAR(30)  NOT NULL
                            CHECK (field_group IN ('identity','bank','designation','department','other')),
    field_name          VARCHAR(60)  NOT NULL,          -- exact column name
    old_value           TEXT,
    new_value           TEXT         NOT NULL,
    reason              TEXT,
    supporting_doc_url  TEXT,                           -- uploaded proof (optional)
    status              VARCHAR(20)  NOT NULL DEFAULT 'pending'
                            CHECK (status IN ('pending','approved','rejected','cancelled')),
    requested_at        TIMESTAMP NOT NULL DEFAULT NOW(),
    reviewed_by         INT REFERENCES employees(employee_id) ON DELETE SET NULL,
    reviewed_at         TIMESTAMP,
    reviewer_notes      TEXT
);

-- Employee documents (offer letter, contracts, certificates)
CREATE TABLE employee_documents (
    document_id         SERIAL PRIMARY KEY,
    employee_id         INT NOT NULL REFERENCES employees(employee_id) ON DELETE RESTRICT,
    document_type       VARCHAR(50)  NOT NULL,          -- 'offer_letter','contract','id_proof', etc.
    document_name       VARCHAR(255) NOT NULL,
    file_path           TEXT         NOT NULL,
    file_size_kb        INT,
    uploaded_by         INT REFERENCES employees(employee_id) ON DELETE SET NULL,
    uploaded_at         TIMESTAMP NOT NULL DEFAULT NOW(),
    is_verified         BOOLEAN NOT NULL DEFAULT FALSE,
    verified_by         INT REFERENCES employees(employee_id) ON DELETE SET NULL,
    expiry_date         DATE
);


-- ================================================================
-- D. LEAVE MANAGEMENT
-- ================================================================

CREATE TABLE leave_types (
    leave_type_id       SERIAL PRIMARY KEY,
    org_id              INT NOT NULL REFERENCES organisations(org_id) ON DELETE CASCADE,
    leave_type_name     VARCHAR(60)  NOT NULL,          -- Casual, Sick, Privilege, Compensatory, WFH
    leave_code          VARCHAR(10)  NOT NULL,          -- CL, SL, PL, COMP, WFH
    description         TEXT,
    annual_quota        DECIMAL(5,1) NOT NULL,
    monthly_quota       DECIMAL(4,1),                   -- for WFH (2/month)
    carryover_allowed   BOOLEAN NOT NULL DEFAULT FALSE,
    max_carryover_days  DECIMAL(5,1) DEFAULT 0,
    encashable          BOOLEAN NOT NULL DEFAULT FALSE,
    half_day_allowed    BOOLEAN NOT NULL DEFAULT TRUE,
    requires_document   BOOLEAN NOT NULL DEFAULT FALSE,  -- e.g. medical cert for SL
    min_days_notice     SMALLINT     DEFAULT 0,
    max_consecutive_days SMALLINT,
    applicable_gender   VARCHAR(10)  DEFAULT 'all'
                            CHECK (applicable_gender IN ('all','male','female')),
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE (org_id, leave_code)
);

CREATE TABLE leave_policies (
    policy_id           SERIAL PRIMARY KEY,
    org_id              INT NOT NULL REFERENCES organisations(org_id) ON DELETE CASCADE,
    policy_name         VARCHAR(100) NOT NULL,
    leave_type_id       INT NOT NULL REFERENCES leave_types(leave_type_id) ON DELETE CASCADE,
    employment_type     VARCHAR(20)  DEFAULT 'full_time',
    accrual_type        VARCHAR(20)  NOT NULL DEFAULT 'annual'
                            CHECK (accrual_type IN ('annual','monthly','earned')),
    reset_on            VARCHAR(20)  DEFAULT 'year_start'
                            CHECK (reset_on IN ('year_start','joining_date')),
    lapse_at_year_end   BOOLEAN NOT NULL DEFAULT TRUE,
    is_active           BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE holiday_calendar (
    holiday_id          SERIAL PRIMARY KEY,
    org_id              INT NOT NULL REFERENCES organisations(org_id) ON DELETE CASCADE,
    holiday_date        DATE         NOT NULL,
    holiday_name        VARCHAR(100) NOT NULL,
    holiday_type        VARCHAR(20)  NOT NULL DEFAULT 'public'
                            CHECK (holiday_type IN ('public','restricted','optional')),
    applicable_location INT REFERENCES locations(location_id) ON DELETE SET NULL,
    created_by          INT REFERENCES employees(employee_id) ON DELETE SET NULL,
    created_at          TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (org_id, holiday_date, holiday_name)
);

CREATE TABLE employee_leave_balances (
    balance_id          SERIAL PRIMARY KEY,
    employee_id         INT NOT NULL REFERENCES employees(employee_id) ON DELETE RESTRICT,
    leave_type_id       INT NOT NULL REFERENCES leave_types(leave_type_id) ON DELETE RESTRICT,
    year                SMALLINT     NOT NULL,
    total_allotted      DECIMAL(5,1) NOT NULL,
    carried_over        DECIMAL(5,1) NOT NULL DEFAULT 0,
    used_days           DECIMAL(5,1) NOT NULL DEFAULT 0,
    pending_days        DECIMAL(5,1) NOT NULL DEFAULT 0,
    lapsed_days         DECIMAL(5,1) NOT NULL DEFAULT 0,
    available_days      DECIMAL(5,1) GENERATED ALWAYS AS
                            (total_allotted + carried_over - used_days - pending_days) STORED,
    last_updated        TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (employee_id, leave_type_id, year)
);

CREATE TABLE leave_requests (
    leave_request_id    SERIAL PRIMARY KEY,
    employee_id         INT NOT NULL REFERENCES employees(employee_id) ON DELETE RESTRICT,
    leave_type_id       INT NOT NULL REFERENCES leave_types(leave_type_id) ON DELETE RESTRICT,
    start_date          DATE         NOT NULL,
    end_date            DATE         NOT NULL,
    number_of_days      DECIMAL(4,1) NOT NULL,
    is_half_day         BOOLEAN      NOT NULL DEFAULT FALSE,
    half_day_slot       VARCHAR(10)  CHECK (half_day_slot IN ('morning','afternoon')),
    reason              TEXT,
    supporting_doc_url  TEXT,
    status              VARCHAR(20)  NOT NULL DEFAULT 'pending'
                            CHECK (status IN ('pending','approved','rejected','cancelled','withdrawn')),
    applied_at          TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_dates CHECK (end_date >= start_date),
    CONSTRAINT chk_leave_days_positive CHECK (number_of_days > 0)
);

CREATE TABLE leave_approvals (
    approval_id         SERIAL PRIMARY KEY,
    leave_request_id    INT NOT NULL REFERENCES leave_requests(leave_request_id) ON DELETE CASCADE,
    approver_id         INT NOT NULL REFERENCES employees(employee_id) ON DELETE RESTRICT,
    approval_level      SMALLINT     NOT NULL DEFAULT 1,   -- 1=Manager, 2=HR Admin
    action              VARCHAR(20)  NOT NULL
                            CHECK (action IN ('pending','approved','rejected','forwarded')),
    comments            TEXT,
    actioned_at         TIMESTAMP    DEFAULT NOW()
);

-- Compensatory off earned when working on holidays
CREATE TABLE compensatory_off_log (
    comp_off_id         SERIAL PRIMARY KEY,
    employee_id         INT NOT NULL REFERENCES employees(employee_id) ON DELETE RESTRICT,
    worked_on_date      DATE         NOT NULL,
    hours_worked        DECIMAL(4,1),
    comp_days_earned    DECIMAL(3,1) NOT NULL DEFAULT 1,
    expiry_date         DATE,
    is_consumed         BOOLEAN NOT NULL DEFAULT FALSE,
    linked_leave_request_id INT REFERENCES leave_requests(leave_request_id) ON DELETE SET NULL
);


-- ================================================================
-- E. ATTENDANCE
-- ================================================================

CREATE TABLE work_shifts (
    shift_id            SERIAL PRIMARY KEY,
    org_id              INT NOT NULL REFERENCES organisations(org_id) ON DELETE CASCADE,
    shift_name          VARCHAR(60)  NOT NULL,           -- e.g. 'General Shift', 'Morning'
    shift_code          VARCHAR(10)  NOT NULL,
    start_time          TIME         NOT NULL,
    end_time            TIME         NOT NULL,
    grace_period_mins   SMALLINT     NOT NULL DEFAULT 15,
    weekly_off_days     VARCHAR(20)  NOT NULL DEFAULT 'Saturday,Sunday',
    is_active           BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE employee_shift_assignments (
    assignment_id       SERIAL PRIMARY KEY,
    employee_id         INT NOT NULL REFERENCES employees(employee_id) ON DELETE CASCADE,
    shift_id            INT NOT NULL REFERENCES work_shifts(shift_id) ON DELETE RESTRICT,
    effective_from      DATE         NOT NULL,
    effective_to        DATE,
    assigned_by         INT REFERENCES employees(employee_id) ON DELETE SET NULL
);

CREATE TABLE attendance_records (
    attendance_id       SERIAL PRIMARY KEY,
    employee_id         INT NOT NULL REFERENCES employees(employee_id) ON DELETE RESTRICT,
    attendance_date     DATE         NOT NULL,
    shift_id            INT REFERENCES work_shifts(shift_id) ON DELETE SET NULL,
    check_in_time       TIMESTAMP,
    check_out_time      TIMESTAMP,
    total_hours         DECIMAL(4,2) GENERATED ALWAYS AS
                            (EXTRACT(EPOCH FROM (check_out_time - check_in_time))/3600.0) STORED,
    status              VARCHAR(20)  NOT NULL
                            CHECK (status IN (
                                'present','absent','wfh','half_day_morning',
                                'half_day_afternoon','on_leave','holiday','weekend','not_marked')),
    is_late             BOOLEAN      NOT NULL DEFAULT FALSE,
    late_by_mins        SMALLINT,
    is_early_exit       BOOLEAN      NOT NULL DEFAULT FALSE,
    early_by_mins       SMALLINT,
    source              VARCHAR(20)  NOT NULL DEFAULT 'system'
                            CHECK (source IN ('system','biometric','manual','regularised')),
    remarks             TEXT,
    is_regularised      BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (employee_id, attendance_date)
);

-- Regularisation requests (Zoho People style — employee corrects their own attendance)
CREATE TABLE attendance_regularisation (
    regularisation_id   SERIAL PRIMARY KEY,
    employee_id         INT NOT NULL REFERENCES employees(employee_id) ON DELETE RESTRICT,
    attendance_date     DATE         NOT NULL,
    requested_check_in  TIMESTAMP,
    requested_check_out TIMESTAMP,
    requested_status    VARCHAR(20),
    reason              TEXT         NOT NULL,
    status              VARCHAR(20)  NOT NULL DEFAULT 'pending'
                            CHECK (status IN ('pending','approved','rejected')),
    requested_at        TIMESTAMP NOT NULL DEFAULT NOW(),
    reviewed_by         INT REFERENCES employees(employee_id) ON DELETE SET NULL,
    reviewed_at         TIMESTAMP,
    reviewer_comments   TEXT
);

-- HR Admin manual edits to attendance (with audit)
CREATE TABLE attendance_edit_log (
    log_id              SERIAL PRIMARY KEY,
    attendance_id       INT NOT NULL REFERENCES attendance_records(attendance_id) ON DELETE CASCADE,
    edited_by           INT NOT NULL REFERENCES employees(employee_id) ON DELETE RESTRICT,
    old_status          VARCHAR(20),
    new_status          VARCHAR(20),
    old_check_in        TIMESTAMP,
    new_check_in        TIMESTAMP,
    old_check_out       TIMESTAMP,
    new_check_out       TIMESTAMP,
    edit_reason         TEXT,
    edited_at           TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Monthly attendance summary (pre-computed for dashboard widgets)
CREATE TABLE attendance_monthly_summary (
    summary_id          SERIAL PRIMARY KEY,
    employee_id         INT NOT NULL REFERENCES employees(employee_id) ON DELETE RESTRICT,
    year                SMALLINT     NOT NULL,
    month               SMALLINT     NOT NULL CHECK (month BETWEEN 1 AND 12),
    total_working_days  SMALLINT     NOT NULL DEFAULT 0,
    days_present        SMALLINT     NOT NULL DEFAULT 0,
    days_absent         SMALLINT     NOT NULL DEFAULT 0,
    days_wfh            SMALLINT     NOT NULL DEFAULT 0,
    days_half_day       SMALLINT     NOT NULL DEFAULT 0,
    days_on_leave       SMALLINT     NOT NULL DEFAULT 0,
    late_arrivals       SMALLINT     NOT NULL DEFAULT 0,
    early_exits         SMALLINT     NOT NULL DEFAULT 0,
    total_hours_worked  DECIMAL(6,2) NOT NULL DEFAULT 0,
    last_computed_at    TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (employee_id, year, month)
);


-- ================================================================
-- F. PAYROLL & PAYSLIPS
-- ================================================================

CREATE TABLE salary_components (
    component_id        SERIAL PRIMARY KEY,
    org_id              INT NOT NULL REFERENCES organisations(org_id) ON DELETE CASCADE,
    component_name      VARCHAR(80)  NOT NULL,           -- 'Basic Salary','HRA','Transport Allowance'
    component_code      VARCHAR(20)  NOT NULL,           -- 'BASIC','HRA','TA'
    component_type      VARCHAR(25)  NOT NULL
                            CHECK (component_type IN ('earning','deduction','employer_contribution')),
    is_taxable          BOOLEAN NOT NULL DEFAULT TRUE,
    is_pf_applicable    BOOLEAN NOT NULL DEFAULT FALSE,
    calculation_type    VARCHAR(20)  NOT NULL DEFAULT 'fixed'
                            CHECK (calculation_type IN ('fixed','percentage_of_basic','formula')),
    default_value       DECIMAL(10,2) DEFAULT 0,
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE (org_id, component_code)
);

CREATE TABLE employee_salary_structure (
    structure_id        SERIAL PRIMARY KEY,
    employee_id         INT NOT NULL REFERENCES employees(employee_id) ON DELETE RESTRICT,
    component_id        INT NOT NULL REFERENCES salary_components(component_id) ON DELETE RESTRICT,
    amount              DECIMAL(12,2) NOT NULL DEFAULT 0,
    effective_from      DATE         NOT NULL,
    effective_to        DATE,
    created_by          INT REFERENCES employees(employee_id) ON DELETE SET NULL,
    created_at          TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (employee_id, component_id, effective_from)
);

CREATE TABLE monthly_payroll (
    payroll_id          SERIAL PRIMARY KEY,
    employee_id         INT NOT NULL REFERENCES employees(employee_id) ON DELETE RESTRICT,
    payroll_month       DATE         NOT NULL,           -- first day: e.g. 2025-06-01
    -- earnings
    basic_salary        DECIMAL(12,2) NOT NULL DEFAULT 0,
    hra                 DECIMAL(12,2) NOT NULL DEFAULT 0,
    transport_allowance DECIMAL(12,2) NOT NULL DEFAULT 0,
    medical_allowance   DECIMAL(12,2) NOT NULL DEFAULT 0,
    special_allowance   DECIMAL(12,2) NOT NULL DEFAULT 0,
    performance_bonus   DECIMAL(12,2) NOT NULL DEFAULT 0,
    other_earnings      DECIMAL(12,2) NOT NULL DEFAULT 0,
    gross_earnings      DECIMAL(12,2) GENERATED ALWAYS AS
                            (basic_salary + hra + transport_allowance + medical_allowance
                             + special_allowance + performance_bonus + other_earnings) STORED,
    -- deductions
    pf_employee         DECIMAL(12,2) NOT NULL DEFAULT 0,
    pf_employer         DECIMAL(12,2) NOT NULL DEFAULT 0,
    esi_employee        DECIMAL(12,2) NOT NULL DEFAULT 0,
    professional_tax    DECIMAL(12,2) NOT NULL DEFAULT 0,
    tds                 DECIMAL(12,2) NOT NULL DEFAULT 0,
    loan_deduction      DECIMAL(12,2) NOT NULL DEFAULT 0,
    loss_of_pay         DECIMAL(12,2) NOT NULL DEFAULT 0,
    other_deductions    DECIMAL(12,2) NOT NULL DEFAULT 0,
    total_deductions    DECIMAL(12,2) GENERATED ALWAYS AS
                            (pf_employee + esi_employee + professional_tax
                             + tds + loan_deduction + loss_of_pay + other_deductions) STORED,
    -- net
    net_salary          DECIMAL(12,2) GENERATED ALWAYS AS
                            (basic_salary + hra + transport_allowance + medical_allowance
                             + special_allowance + performance_bonus + other_earnings
                             - pf_employee - esi_employee - professional_tax
                             - tds - loan_deduction - loss_of_pay - other_deductions) STORED,
    -- attendance context
    total_working_days  SMALLINT,
    days_worked         SMALLINT,
    days_on_lop         SMALLINT     NOT NULL DEFAULT 0,
    -- status
    payroll_status      VARCHAR(20)  NOT NULL DEFAULT 'draft'
                            CHECK (payroll_status IN ('draft','processing','approved','paid','cancelled')),
    approved_by         INT REFERENCES employees(employee_id) ON DELETE SET NULL,
    approved_at         TIMESTAMP,
    payment_date        DATE,
    payment_mode        VARCHAR(20)  DEFAULT 'bank_transfer',
    processed_by        INT REFERENCES employees(employee_id) ON DELETE SET NULL,
    processed_at        TIMESTAMP,
    created_at          TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (employee_id, payroll_month)
);

CREATE TABLE payslips (
    payslip_id          SERIAL PRIMARY KEY,
    employee_id         INT NOT NULL REFERENCES employees(employee_id) ON DELETE RESTRICT,
    payroll_id          INT NOT NULL REFERENCES monthly_payroll(payroll_id) ON DELETE CASCADE,
    payslip_month       DATE         NOT NULL,
    pdf_path            TEXT         NOT NULL,           -- blob URL / file path of generated PDF
    pdf_size_kb         INT,
    generated_at        TIMESTAMP NOT NULL DEFAULT NOW(),
    last_downloaded_at  TIMESTAMP,
    download_count      INT NOT NULL DEFAULT 0,
    is_published        BOOLEAN NOT NULL DEFAULT FALSE,  -- HR publishes → employee can see
    published_at        TIMESTAMP,
    UNIQUE (employee_id, payslip_month)
);


-- ================================================================
-- G. HR REQUESTS
-- (Zoho People → Requests / Cases module equivalent)
-- ================================================================

CREATE TABLE hr_request_categories (
    category_id         SERIAL PRIMARY KEY,
    category_name       VARCHAR(80)  NOT NULL UNIQUE,
    description         TEXT,
    default_priority    VARCHAR(10)  DEFAULT 'normal'
                            CHECK (default_priority IN ('low','normal','high')),
    sla_hours           SMALLINT     DEFAULT 48,         -- expected resolution hours
    is_active           BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE hr_requests (
    hr_request_id       SERIAL PRIMARY KEY,
    employee_id         INT NOT NULL REFERENCES employees(employee_id) ON DELETE RESTRICT,
    category_id         INT NOT NULL REFERENCES hr_request_categories(category_id) ON DELETE RESTRICT,
    subject             VARCHAR(255) NOT NULL,
    description         TEXT         NOT NULL,
    attachment_url      TEXT,
    priority            VARCHAR(10)  NOT NULL DEFAULT 'normal'
                            CHECK (priority IN ('low','normal','high','urgent')),
    status              VARCHAR(20)  NOT NULL DEFAULT 'open'
                            CHECK (status IN ('open','in_progress','pending_info','resolved','closed','cancelled')),
    raised_at           TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMP NOT NULL DEFAULT NOW(),
    assigned_to         INT REFERENCES employees(employee_id) ON DELETE SET NULL,
    resolved_at         TIMESTAMP,
    resolution_notes    TEXT,
    sla_due_at          TIMESTAMP,
    is_sla_breached     BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE hr_request_comments (
    comment_id          SERIAL PRIMARY KEY,
    hr_request_id       INT NOT NULL REFERENCES hr_requests(hr_request_id) ON DELETE CASCADE,
    commenter_id        INT NOT NULL REFERENCES employees(employee_id) ON DELETE RESTRICT,
    comment_text        TEXT         NOT NULL,
    is_internal         BOOLEAN NOT NULL DEFAULT FALSE,  -- internal HR note vs visible to employee
    created_at          TIMESTAMP NOT NULL DEFAULT NOW()
);


-- ================================================================
-- H. IT / ASSET REQUESTS
-- ================================================================

CREATE TABLE asset_categories (
    asset_category_id   SERIAL PRIMARY KEY,
    category_name       VARCHAR(80)  NOT NULL UNIQUE,
    description         TEXT
);

CREATE TABLE assets (
    asset_id            SERIAL PRIMARY KEY,
    org_id              INT NOT NULL REFERENCES organisations(org_id) ON DELETE CASCADE,
    asset_category_id   INT NOT NULL REFERENCES asset_categories(asset_category_id) ON DELETE RESTRICT,
    asset_name          VARCHAR(150) NOT NULL,
    asset_tag           VARCHAR(50)  UNIQUE,             -- physical asset tag / serial number
    brand               VARCHAR(80),
    model               VARCHAR(80),
    purchase_date       DATE,
    warranty_expiry     DATE,
    status              VARCHAR(20)  NOT NULL DEFAULT 'available'
                            CHECK (status IN ('available','assigned','in_repair','decommissioned')),
    assigned_to         INT REFERENCES employees(employee_id) ON DELETE SET NULL,
    assigned_at         TIMESTAMP,
    location_id         INT REFERENCES locations(location_id) ON DELETE SET NULL
);

CREATE TABLE it_requests (
    it_request_id       SERIAL PRIMARY KEY,
    employee_id         INT NOT NULL REFERENCES employees(employee_id) ON DELETE RESTRICT,
    request_type        VARCHAR(40)  NOT NULL
                            CHECK (request_type IN (
                                'new_asset','access_provisioning','hardware_issue',
                                'software_install','peripheral','network','other')),
    subject             VARCHAR(255) NOT NULL,
    description         TEXT         NOT NULL,
    asset_id            INT REFERENCES assets(asset_id) ON DELETE SET NULL,  -- if about existing asset
    priority            VARCHAR(10)  NOT NULL DEFAULT 'normal'
                            CHECK (priority IN ('low','normal','high','urgent')),
    status              VARCHAR(20)  NOT NULL DEFAULT 'open'
                            CHECK (status IN ('open','in_progress','on_hold','resolved','closed')),
    raised_at           TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMP NOT NULL DEFAULT NOW(),
    assigned_to         INT REFERENCES employees(employee_id) ON DELETE SET NULL,
    resolved_at         TIMESTAMP,
    resolution_notes    TEXT
);

CREATE TABLE it_request_status_history (
    history_id          SERIAL PRIMARY KEY,
    it_request_id       INT NOT NULL REFERENCES it_requests(it_request_id) ON DELETE CASCADE,
    old_status          VARCHAR(20),
    new_status          VARCHAR(20)  NOT NULL,
    changed_by          INT NOT NULL REFERENCES employees(employee_id) ON DELETE RESTRICT,
    notes               TEXT,
    changed_at          TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE asset_assignments (
    assignment_id       SERIAL PRIMARY KEY,
    asset_id            INT NOT NULL REFERENCES assets(asset_id) ON DELETE CASCADE,
    employee_id         INT NOT NULL REFERENCES employees(employee_id) ON DELETE RESTRICT,
    assigned_by         INT REFERENCES employees(employee_id) ON DELETE SET NULL,
    assigned_at         TIMESTAMP NOT NULL DEFAULT NOW(),
    returned_at         TIMESTAMP,
    condition_at_issue  VARCHAR(20)  DEFAULT 'good'
                            CHECK (condition_at_issue IN ('new','good','fair','poor')),
    condition_at_return VARCHAR(20)
                            CHECK (condition_at_return IN ('good','fair','poor','damaged','lost')),
    notes               TEXT
);


-- ================================================================
-- I. ANNOUNCEMENTS & HOME FEED
-- (Zoho People → Home tab: notice board, birthdays, anniversaries)
-- ================================================================

CREATE TABLE announcements (
    announcement_id     SERIAL PRIMARY KEY,
    org_id              INT NOT NULL REFERENCES organisations(org_id) ON DELETE CASCADE,
    title               VARCHAR(255) NOT NULL,
    body                TEXT         NOT NULL,
    category            VARCHAR(30)  NOT NULL DEFAULT 'general'
                            CHECK (category IN ('general','policy','event','emergency','hr','it')),
    priority            VARCHAR(10)  NOT NULL DEFAULT 'normal'
                            CHECK (priority IN ('low','normal','high','urgent')),
    attachment_url      TEXT,
    published_by        INT REFERENCES employees(employee_id) ON DELETE SET NULL,
    published_at        TIMESTAMP,
    expires_at          TIMESTAMP,
    target_audience     VARCHAR(20)  NOT NULL DEFAULT 'all'
                            CHECK (target_audience IN ('all','department','team','location')),
    target_id           INT,                             -- department_id / team_id / location_id
    is_published        BOOLEAN NOT NULL DEFAULT FALSE,
    created_at          TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE announcement_reads (
    read_id             SERIAL PRIMARY KEY,
    announcement_id     INT NOT NULL REFERENCES announcements(announcement_id) ON DELETE CASCADE,
    employee_id         INT NOT NULL REFERENCES employees(employee_id) ON DELETE CASCADE,
    read_at             TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (announcement_id, employee_id)
);

-- Birthday / work anniversary event feed (auto-generated by a scheduled job)
CREATE TABLE employee_milestone_events (
    event_id            SERIAL PRIMARY KEY,
    employee_id         INT NOT NULL REFERENCES employees(employee_id) ON DELETE CASCADE,
    event_type          VARCHAR(20)  NOT NULL
                            CHECK (event_type IN ('birthday','work_anniversary','joining')),
    event_date          DATE         NOT NULL,
    year_number         SMALLINT,                        -- e.g. 5th work anniversary
    is_notified         BOOLEAN NOT NULL DEFAULT FALSE,
    notified_at         TIMESTAMP
);


-- ================================================================
-- J. QUICK LINKS / PORTAL SETTINGS
-- (Zoho People → My Apps / quick links on dashboard)
-- ================================================================

CREATE TABLE portal_quick_links (
    link_id             SERIAL PRIMARY KEY,
    org_id              INT NOT NULL REFERENCES organisations(org_id) ON DELETE CASCADE,
    link_title          VARCHAR(100) NOT NULL,
    link_url            TEXT         NOT NULL,
    icon_code           VARCHAR(50),
    display_order       SMALLINT     NOT NULL DEFAULT 0,
    visible_to_roles    TEXT[]       NOT NULL DEFAULT ARRAY['employee'],
    is_active           BOOLEAN NOT NULL DEFAULT TRUE
);


-- ================================================================
-- K. AI CHATBOT & RAG PIPELINE
-- ================================================================

CREATE TABLE hr_policy_documents (
    document_id         SERIAL PRIMARY KEY,
    org_id              INT NOT NULL REFERENCES organisations(org_id) ON DELETE CASCADE,
    document_name       VARCHAR(255) NOT NULL,
    document_type       VARCHAR(40)  NOT NULL
                            CHECK (document_type IN (
                                'company_policy','leave_policy','code_of_conduct',
                                'compensation_policy','legal_compliance','it_policy','other')),
    file_path           TEXT         NOT NULL,
    version             VARCHAR(20)  DEFAULT '1.0',
    language            VARCHAR(10)  DEFAULT 'en',
    total_pages         SMALLINT,
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    indexed_in_chromadb BOOLEAN NOT NULL DEFAULT FALSE,
    chromadb_collection VARCHAR(100),
    indexed_at          TIMESTAMP,
    uploaded_by         INT REFERENCES employees(employee_id) ON DELETE SET NULL,
    uploaded_at         TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE rag_document_chunks (
    chunk_id            SERIAL PRIMARY KEY,
    document_id         INT NOT NULL REFERENCES hr_policy_documents(document_id) ON DELETE CASCADE,
    chunk_index         INT          NOT NULL,
    chunk_text          TEXT         NOT NULL,
    token_count         INT,
    chromadb_chunk_id   VARCHAR(128) NOT NULL UNIQUE,
    embedding_model     VARCHAR(80)  DEFAULT 'all-MiniLM-L6-v2',
    created_at          TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE chatbot_sessions (
    session_id          SERIAL PRIMARY KEY,
    employee_id         INT NOT NULL REFERENCES employees(employee_id) ON DELETE RESTRICT,
    started_at          TIMESTAMP NOT NULL DEFAULT NOW(),
    ended_at            TIMESTAMP,
    total_messages      INT NOT NULL DEFAULT 0
);

CREATE TABLE chatbot_query_log (
    query_id            SERIAL PRIMARY KEY,
    session_id          INT NOT NULL REFERENCES chatbot_sessions(session_id) ON DELETE CASCADE,
    employee_id         INT NOT NULL REFERENCES employees(employee_id) ON DELETE RESTRICT,
    query_text          TEXT         NOT NULL,
    query_category      VARCHAR(40)
                            CHECK (query_category IN (
                                'leave_policy','compensation','code_of_conduct',
                                'attendance','it_assets','legal_compliance','general')),
    retrieved_chunk_ids TEXT[],                          -- chromadb_chunk_id[]
    source_documents    TEXT[],                          -- document names used
    llm_model_used      VARCHAR(60),                     -- 'gemini-2.5-flash','llama-3.3-70b'
    llm_response        TEXT,
    confidence_score    DECIMAL(4,3),                    -- 0.000 – 1.000
    is_grounded         BOOLEAN,
    is_escalated        BOOLEAN NOT NULL DEFAULT FALSE,
    asked_at            TIMESTAMP NOT NULL DEFAULT NOW(),
    response_latency_ms INT,
    user_feedback       SMALLINT CHECK (user_feedback IN (1, -1)),  -- thumbs up/down
    user_feedback_note  TEXT
);

CREATE TABLE escalation_tickets (
    escalation_id       SERIAL PRIMARY KEY,
    query_id            INT NOT NULL REFERENCES chatbot_query_log(query_id) ON DELETE CASCADE,
    employee_id         INT NOT NULL REFERENCES employees(employee_id) ON DELETE RESTRICT,
    escalated_query     TEXT         NOT NULL,
    escalation_reason   VARCHAR(50)  DEFAULT 'low_confidence'
                            CHECK (escalation_reason IN ('low_confidence','out_of_scope','user_requested')),
    status              VARCHAR(20)  NOT NULL DEFAULT 'open'
                            CHECK (status IN ('open','in_progress','resolved')),
    assigned_to         INT REFERENCES employees(employee_id) ON DELETE SET NULL,
    escalated_at        TIMESTAMP NOT NULL DEFAULT NOW(),
    resolved_at         TIMESTAMP,
    resolution_notes    TEXT
);


-- ================================================================
-- L. NOTIFICATIONS
-- ================================================================

CREATE TABLE notifications (
    notification_id     BIGSERIAL PRIMARY KEY,
    recipient_id        INT NOT NULL REFERENCES employees(employee_id) ON DELETE CASCADE,
    notification_type   VARCHAR(50)  NOT NULL,
                            -- 'leave_status','attendance_regularisation','payslip_published',
                            -- 'hr_request_update','it_request_update','profile_change_status',
                            -- 'announcement','escalation_resolved','birthday','asset_assigned'
    title               VARCHAR(255) NOT NULL,
    message             TEXT         NOT NULL,
    deep_link           TEXT,                            -- frontend route to click through
    is_read             BOOLEAN NOT NULL DEFAULT FALSE,
    read_at             TIMESTAMP,
    related_entity_type VARCHAR(50),
    related_entity_id   INT,
    created_at          TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE email_notification_log (
    email_log_id        BIGSERIAL PRIMARY KEY,
    recipient_id        INT NOT NULL REFERENCES employees(employee_id) ON DELETE CASCADE,
    recipient_email     VARCHAR(255) NOT NULL,
    subject             VARCHAR(255) NOT NULL,
    body_preview        TEXT,
    template_name       VARCHAR(80),
    status              VARCHAR(20)  NOT NULL DEFAULT 'sent'
                            CHECK (status IN ('queued','sent','failed','bounced')),
    related_entity_type VARCHAR(50),
    related_entity_id   INT,
    sent_at             TIMESTAMP NOT NULL DEFAULT NOW(),
    retried_count       SMALLINT     NOT NULL DEFAULT 0,
    error_message       TEXT
);


-- ================================================================
-- M. AUDIT TRAIL & SYSTEM CONFIG
-- ================================================================

CREATE TABLE audit_log (
    audit_id            BIGSERIAL PRIMARY KEY,
    actor_id            INT REFERENCES employees(employee_id) ON DELETE SET NULL,
    actor_role          VARCHAR(20),
    action              VARCHAR(30)  NOT NULL,            -- 'CREATE','UPDATE','DELETE','APPROVE','REJECT','LOGIN','LOGOUT'
    entity_type         VARCHAR(60)  NOT NULL,            -- table / domain
    entity_id           BIGINT       NOT NULL,
    old_value           JSONB,
    new_value           JSONB,
    changed_fields      TEXT[],
    ip_address          VARCHAR(45),
    user_agent          TEXT,
    session_id          BIGINT,
    occurred_at         TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE system_config (
    config_id           SERIAL PRIMARY KEY,
    org_id              INT NOT NULL REFERENCES organisations(org_id) ON DELETE CASCADE,
    config_key          VARCHAR(100) NOT NULL,
    config_value        TEXT,
    description         TEXT,
    updated_by          INT REFERENCES employees(employee_id) ON DELETE SET NULL,
    updated_at          TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (org_id, config_key)
);


-- ================================================================
-- INDEXES
-- ================================================================

-- Employees
CREATE INDEX idx_emp_dept          ON employees(department_id);
CREATE INDEX idx_emp_team          ON employees(team_id);
CREATE INDEX idx_emp_manager       ON employees(manager_id);
CREATE INDEX idx_emp_role          ON employees(role);
CREATE INDEX idx_emp_entra         ON employees(entra_object_id);
CREATE INDEX idx_emp_status        ON employees(employment_status);

-- Sessions
CREATE INDEX idx_sessions_emp      ON user_sessions(employee_id);
CREATE INDEX idx_sessions_active   ON user_sessions(is_active, expires_at);

-- Leave
CREATE INDEX idx_leave_req_emp     ON leave_requests(employee_id);
CREATE INDEX idx_leave_req_status  ON leave_requests(status);
CREATE INDEX idx_leave_req_dates   ON leave_requests(start_date, end_date);
CREATE INDEX idx_leave_bal_emp_yr  ON employee_leave_balances(employee_id, year);
CREATE INDEX idx_leave_approvals   ON leave_approvals(leave_request_id, approver_id);

-- Attendance
CREATE INDEX idx_att_emp_date      ON attendance_records(employee_id, attendance_date);
CREATE INDEX idx_att_status        ON attendance_records(status);
CREATE INDEX idx_att_summary       ON attendance_monthly_summary(employee_id, year, month);
CREATE INDEX idx_reg_emp_date      ON attendance_regularisation(employee_id, attendance_date);

-- Payroll
CREATE INDEX idx_payroll_emp_month ON monthly_payroll(employee_id, payroll_month);
CREATE INDEX idx_payroll_status    ON monthly_payroll(payroll_status);
CREATE INDEX idx_payslips_emp      ON payslips(employee_id, payslip_month);

-- HR & IT Requests
CREATE INDEX idx_hr_req_emp        ON hr_requests(employee_id);
CREATE INDEX idx_hr_req_status     ON hr_requests(status);
CREATE INDEX idx_it_req_emp        ON it_requests(employee_id);
CREATE INDEX idx_it_req_status     ON it_requests(status);

-- Notifications
CREATE INDEX idx_notif_recipient   ON notifications(recipient_id, is_read);
CREATE INDEX idx_notif_created     ON notifications(created_at);

-- Chatbot
CREATE INDEX idx_chat_session      ON chatbot_query_log(session_id);
CREATE INDEX idx_chat_emp          ON chatbot_query_log(employee_id);
CREATE INDEX idx_chat_category     ON chatbot_query_log(query_category);
CREATE INDEX idx_escalations_status ON escalation_tickets(status);
CREATE INDEX idx_rag_chunks_doc    ON rag_document_chunks(document_id);

-- Announcements
CREATE INDEX idx_announce_org      ON announcements(org_id, is_published);
CREATE INDEX idx_announce_expiry   ON announcements(expires_at);

-- Audit
CREATE INDEX idx_audit_entity      ON audit_log(entity_type, entity_id);
CREATE INDEX idx_audit_actor       ON audit_log(actor_id);
CREATE INDEX idx_audit_occurred    ON audit_log(occurred_at);
