# Task 1 PostgreSQL Migration Design Document

## 1. Executive Summary & Rationale

As part of hardening the ConsultBae AI Automation architecture for production readiness, the database engine is being migrated from a prototype local SQLite database to **PostgreSQL** (hosted on Supabase as the managed PostgreSQL environment).

### Why PostgreSQL over SQLite?
1. **Production Concurrency**: SQLite locks the entire database file during writes, creating `database is locked` bottlenecks during multi-threaded n8n workflow executions or simultaneous API requests from FastAPI. PostgreSQL handles multi-version concurrency control (MVCC) seamlessly.
2. **Native JSON & Advanced Indexing**: PostgreSQL provides native `JSONB` data types and expression indexes (`LOWER(email)`), allowing flexible schema evolution for unstructured candidate metadata and fast entity resolution queries.
3. **Decoupled Architecture**: Python ingestion scripts, n8n automation workflows (Task 2), and the FastAPI application (Task 3) will connect directly to PostgreSQL via standard database connection protocols (`psycopg2` / standard Postgres wire protocol) rather than relying on direct file access or proprietary REST APIs.
4. **Idempotent Upserts**: PostgreSQL native `INSERT ... ON CONFLICT (source_system, source_file, line_number) DO UPDATE` enables true pipeline idempotency across repeated runs without requiring destructive table truncations.

---

## 2. PostgreSQL Architecture & Connection Strategy

```
                             +-----------------------------------+
                             |     Managed PostgreSQL / Supabase |
                             |        (Port 5432 / SSL)          |
                             +-----------------------------------+
                                   ^               ^       ^
                                   |               |       |
            +----------------------+               |       +-----------------------+
            | Standard DB Driver                   | Postgres Node                 | asyncpg / psycopg2
            | (psycopg2)                           |                               |
+-----------------------+              +-----------------------+       +-----------------------+
|  Task 1 Python ETL    |              |  Task 2 n8n Workflows |       |   Task 3 FastAPI App  |
| Ingestion & Matching  |              | Automation Engine     |       | Candidate REST API    |
+-----------------------+              +-----------------------+       +-----------------------+
```

### Connection Strategy
* Business logic connects via the standard `psycopg2` PostgreSQL driver.
* Connections are created on demand, executed within explicit transaction blocks (`with conn:`), and closed gracefully upon task completion.
* Connections never hardcode hostnames, usernames, or passwords. All connection parameters are loaded dynamically from environment variables using `python-dotenv`.

---

## 3. Environment Variables Configuration (`.env.example`)

The application expects a `.env` file in the project root directory. Below is the specification for `.env.example`:

```env
# PostgreSQL / Supabase Database Connection Configuration
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=consultbae_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_secure_password_here
POSTGRES_SSLMODE=prefer

# Application Settings
LOG_LEVEL=INFO
PROJECT_ENV=development
```

> [!IMPORTANT]
> The actual `.env` file containing secrets is added to `.gitignore` and must **never** be committed to source control.

---

## 4. Database Schema & DDL Specification (`database/schema.sql`)

The PostgreSQL DDL schema defines explicit data types, primary keys, foreign keys, unique constraints, and indexes.

```sql
-- Enable UUID extension if needed
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================================
-- 1. RAW STAGING LAYER & QUARANTINE LOG
-- ============================================================================

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

-- ============================================================================
-- 2. CANONICAL CORE LAYER
-- ============================================================================

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

-- ============================================================================
-- 3. INDEXES FOR ENTITY RESOLUTION PERFORMANCE
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_persons_email ON persons(LOWER(primary_email));
CREATE INDEX IF NOT EXISTS idx_persons_phone ON persons(primary_phone);
CREATE INDEX IF NOT EXISTS idx_persons_name_city ON persons(LOWER(canonical_name), LOWER(canonical_city));
CREATE INDEX IF NOT EXISTS idx_person_emails_addr ON person_emails(LOWER(email_address));
CREATE INDEX IF NOT EXISTS idx_person_phones_num ON person_phones(phone_number);
CREATE INDEX IF NOT EXISTS idx_mappings_person ON person_source_mappings(person_id);
```

---

## 5. Unique Constraints & Idempotency Strategy

To guarantee that pipeline re-execution is strictly idempotent (Run 1 == Run 2 == Run 3):
1. **Raw Ingestion Layer**:
   * `UNIQUE(source_system, source_file, line_number)` enforces one raw entry per CSV line.
   * `INSERT ... ON CONFLICT (source_system, source_file, line_number) DO UPDATE SET ...` ensures re-running raw ingestion updates existing records without adding duplicate rows.
2. **Lineage Mapping Layer**:
   * `UNIQUE(source_system, source_file, source_line_number)` in `person_source_mappings` guarantees a single source mapping per line.
3. **Quarantine Layer**:
   * `UNIQUE(source_system, file_name, line_number, issue_type)` in `ingestion_quarantine_log` prevents duplicate quarantine entries on re-runs.
4. **Child Detail Tables**:
   * `UNIQUE(person_id, email_address)`, `UNIQUE(person_id, phone_number)`, `UNIQUE(person_id, skill_name, source_system)` ensure no duplicate emails, phones, or skills per candidate.

---

## 6. Raw-Data Preservation Strategy

For complete source auditability:
1. **Exact Unparsed Line**: `raw_line_content` stores the exact unparsed CSV line string (e.g. `'react, javascript, mysql,ISHA.CHOPRA95@MAILTEST.EXAMPLE.ORG,Isha Chopra,1406/hr,Pune,active'`).
2. **Structural Recovery Tracking**: For malformed rows (S2 Line 20 column shift), `was_malformed` is set to `TRUE` and `recovery_reason` stores the explanation (`'Structural Column Shift: Field 0 fails email format, Field 1 contains valid email'`).
3. **Quarantine Audit**: Excluded rows (S2 Line 12 blank, S3 Line 16 header) are stored in `ingestion_quarantine_log`.
4. **Source Files**: The original CSV files in `data/` are untouched.

---

## 7. Structural Malformed-Row Detection

Instead of brittle string matching (`"react"` or `"python"`), malformed row detection evaluates field structural rules:
* Expected schema for Source 2: `[email_id, worker_name, rate, location, status, skill_tags]`.
* **Detection Rule**:
  * Check if `r[0]` (email column) fails `normalize_email(r[0]) == ""`.
  * Check if `r[1]` (worker_name column) passes `normalize_email(r[1]) != ""`.
  * If `r[0]` is invalid as email AND `r[1]` is valid as email, a **structural column shift** is detected.
  * Re-map in memory: `skills = r[0]`, `email = r[1]`, `name = r[2]`, `rate = r[3]`, `location = r[4]`, `status = r[5]`.

---

## 8. Reproducibility & Downstream Integration

### For Reviewers / Recreating the DB
* Reviewers can set their PostgreSQL connection string in `.env` and execute `python -m src.app.main --reset` or run `psql -f database/schema.sql` to instantiate the complete schema.

### Task 2 (n8n Automation Integration)
* n8n connects to the same PostgreSQL / Supabase database using the standard PostgreSQL credentials or Supabase integration node. Queries against `persons` and `candidate_profiles` allow automated candidate workflows.

### Task 3 (FastAPI Application)
* The FastAPI backend connects to PostgreSQL using `psycopg2` or `asyncpg` connection pools. API endpoints query `persons`, `candidate_profiles`, and `candidate_skills` to serve candidate search and audio job matching.
