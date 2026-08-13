-- PostgreSQL Schema for ConsultBae AI Automation Assignment (Task 1)

-- 1. RAW STAGING LAYER & QUARANTINE LOG
CREATE TABLE IF NOT EXISTS raw_source1_naukri (
    id SERIAL PRIMARY KEY,
    source_system VARCHAR(50) NOT NULL DEFAULT 'naukri',
    source_file VARCHAR(255) NOT NULL DEFAULT 'source1_naukri_applicants.csv',
    line_number INT NOT NULL,
    raw_line_content TEXT,
    raw_candidate_name TEXT,
    raw_email TEXT,
    raw_phone TEXT,
    raw_current_city TEXT,
    raw_total_experience TEXT,
    raw_expected_ctc TEXT,
    raw_application_date TEXT,
    raw_skills TEXT,
    ingested_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_raw_s1_line UNIQUE (source_system, source_file, line_number)
);

CREATE TABLE IF NOT EXISTS raw_source2_gig_workers (
    id SERIAL PRIMARY KEY,
    source_system VARCHAR(50) NOT NULL DEFAULT 'gig_workers',
    source_file VARCHAR(255) NOT NULL DEFAULT 'source2_gig_workers.csv',
    line_number INT NOT NULL,
    raw_line_content TEXT,
    raw_email_id TEXT,
    raw_worker_name TEXT,
    raw_rate TEXT,
    raw_location TEXT,
    raw_status TEXT,
    raw_skill_tags TEXT,
    was_malformed BOOLEAN DEFAULT FALSE,
    recovery_reason TEXT,
    ingested_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_raw_s2_line UNIQUE (source_system, source_file, line_number)
);

CREATE TABLE IF NOT EXISTS raw_source3_cbnexus (
    id SERIAL PRIMARY KEY,
    source_system VARCHAR(50) NOT NULL DEFAULT 'cbnexus',
    source_file VARCHAR(255) NOT NULL DEFAULT 'source3_cbnexus_contacts.csv',
    line_number INT NOT NULL,
    raw_line_content TEXT,
    raw_name TEXT,
    raw_phone_number TEXT,
    raw_city TEXT,
    raw_verified TEXT,
    raw_projects_completed TEXT,
    ingested_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_raw_s3_line UNIQUE (source_system, source_file, line_number)
);

CREATE TABLE IF NOT EXISTS ingestion_quarantine_log (
    quarantine_id SERIAL PRIMARY KEY,
    source_system VARCHAR(50) NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    line_number INT NOT NULL,
    issue_type VARCHAR(100) NOT NULL,
    raw_line_content TEXT NOT NULL,
    resolution_action VARCHAR(100) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_quarantine_line UNIQUE (source_system, file_name, line_number, issue_type)
);

-- 2. CANONICAL CORE LAYER
CREATE TABLE IF NOT EXISTS persons (
    person_id SERIAL PRIMARY KEY,
    canonical_name VARCHAR(255) NOT NULL,
    primary_email VARCHAR(255),
    primary_phone VARCHAR(50),
    canonical_city VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS person_source_mappings (
    mapping_id SERIAL PRIMARY KEY,
    person_id INT NOT NULL REFERENCES persons(person_id) ON DELETE CASCADE,
    source_system VARCHAR(50) NOT NULL,
    source_file VARCHAR(255) NOT NULL,
    source_line_number INT NOT NULL,
    raw_record_id INT NOT NULL,
    match_confidence VARCHAR(50) NOT NULL,
    match_rule_applied VARCHAR(100) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_person_source_line UNIQUE (source_system, source_file, source_line_number)
);

CREATE TABLE IF NOT EXISTS candidate_profiles (
    profile_id SERIAL PRIMARY KEY,
    person_id INT UNIQUE NOT NULL REFERENCES persons(person_id) ON DELETE CASCADE,
    experience_years DOUBLE PRECISION,
    expected_ctc_lpa DOUBLE PRECISION,
    hourly_rate_inr DOUBLE PRECISION,
    monthly_rate_inr DOUBLE PRECISION,
    status VARCHAR(50),
    is_verified BOOLEAN,
    projects_completed INT,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS person_emails (
    email_id SERIAL PRIMARY KEY,
    person_id INT NOT NULL REFERENCES persons(person_id) ON DELETE CASCADE,
    email_address VARCHAR(255) NOT NULL,
    is_primary BOOLEAN DEFAULT FALSE,
    source_system VARCHAR(50) NOT NULL,
    CONSTRAINT uq_person_email UNIQUE (person_id, email_address)
);

CREATE TABLE IF NOT EXISTS person_phones (
    phone_id SERIAL PRIMARY KEY,
    person_id INT NOT NULL REFERENCES persons(person_id) ON DELETE CASCADE,
    phone_number VARCHAR(50) NOT NULL,
    is_primary BOOLEAN DEFAULT FALSE,
    source_system VARCHAR(50) NOT NULL,
    CONSTRAINT uq_person_phone UNIQUE (person_id, phone_number)
);

CREATE TABLE IF NOT EXISTS candidate_skills (
    skill_id SERIAL PRIMARY KEY,
    person_id INT NOT NULL REFERENCES persons(person_id) ON DELETE CASCADE,
    skill_name VARCHAR(100) NOT NULL,
    source_system VARCHAR(50) NOT NULL,
    CONSTRAINT uq_person_skill_source UNIQUE (person_id, skill_name, source_system)
);

CREATE TABLE IF NOT EXISTS entity_conflicts (
    conflict_id SERIAL PRIMARY KEY,
    person_id INT NOT NULL REFERENCES persons(person_id) ON DELETE CASCADE,
    attribute_name VARCHAR(50) NOT NULL,
    source_system_1 VARCHAR(50) NOT NULL,
    source_1_value TEXT,
    source_system_2 VARCHAR(50) NOT NULL,
    source_2_value TEXT,
    resolution_strategy VARCHAR(100) NOT NULL,
    logged_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_conflict_record UNIQUE (person_id, attribute_name, source_system_1, source_system_2)
);

-- 3. INDEXES FOR ENTITY RESOLUTION PERFORMANCE
CREATE INDEX IF NOT EXISTS idx_persons_email ON persons(LOWER(primary_email));
CREATE INDEX IF NOT EXISTS idx_persons_phone ON persons(primary_phone);
CREATE INDEX IF NOT EXISTS idx_persons_name_city ON persons(LOWER(canonical_name), LOWER(canonical_city));
CREATE INDEX IF NOT EXISTS idx_person_emails_addr ON person_emails(LOWER(email_address));
CREATE INDEX IF NOT EXISTS idx_person_phones_num ON person_phones(phone_number);
CREATE INDEX IF NOT EXISTS idx_mappings_person ON person_source_mappings(person_id);

-- 4. TASK 2 AI CLASSIFICATION LAYER
CREATE TABLE IF NOT EXISTS ai_skill_classifications (
    classification_id SERIAL PRIMARY KEY,
    person_id INT UNIQUE NOT NULL REFERENCES persons(person_id) ON DELETE CASCADE,
    category VARCHAR(100) NOT NULL,
    confidence DOUBLE PRECISION,
    reason TEXT,
    model VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ai_classifications_person ON ai_skill_classifications(person_id);

-- 5. TASK 3 AUDIO SUBMISSIONS LAYER
CREATE TABLE IF NOT EXISTS audio_submissions (
    submission_id SERIAL PRIMARY KEY,
    person_id INT NOT NULL REFERENCES persons(person_id) ON DELETE CASCADE,
    original_filename VARCHAR(255) NOT NULL,
    file_path TEXT NOT NULL,
    file_size_bytes BIGINT NOT NULL,
    duration_seconds DOUBLE PRECISION NOT NULL,
    sample_rate_khz DOUBLE PRECISION NOT NULL,
    bitrate_kbps DOUBLE PRECISION NOT NULL,
    loudness_db DOUBLE PRECISION NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_audio_submissions_person ON audio_submissions(person_id);
