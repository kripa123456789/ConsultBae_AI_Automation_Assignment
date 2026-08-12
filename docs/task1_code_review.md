# Task 1 Code Review

## 1. Assignment Compliance

| Requirement | Status | Rationale / Explanation |
| :--- | :---: | :--- |
| **Unified Database Schema** | **PASS** | Relational schema successfully implemented with canonical core entities (`persons`, `candidate_profiles`, `person_emails`, `person_phones`, `candidate_skills`). |
| **Non-Destructive Raw Data Preservation** | **PARTIAL** | Original CSV files in `data/` remain 100% byte-for-byte untouched. However, raw staging tables (`raw_source2_gig_workers`) store un-shifted corrected values for column-shifted rows rather than verbatim raw input strings, and exclude blank/header rows (which are only captured in `ingestion_quarantine_log`). |
| **Entity Resolution without Common ID** | **PASS** | 3-Tier resolution hierarchy successfully matches candidate profiles across datasets using Email (S1↔S2), Phone (S1↔S3), and Name+City (S2↔S3). |
| **Handling Data Quality Anomalies** | **PASS** | Blank lines, duplicate headers, and column-shifted rows are detected, trapped, and logged cleanly without crashing the pipeline. |
| **Complete Source Lineage Traceability** | **PASS** | `person_source_mappings` links every canonical entity back to exact `(source_system, source_file, source_line_number, raw_record_id)`. |
| **Idempotency & Re-runnability** | **FAIL** | Pipeline execution requires the `--reset` flag (which drops all tables) to remain clean. Executing `main.py` without `--reset` duplicates raw records, mappings, canonical persons, conflicts, and quarantine logs. |

---

## 2. Data Correctness

Evaluation of dataset anomaly handling against the actual supplied CSV files:

* **Blank Row (Source 2, Line 12)**: **Correct**. Correctly trapped, excluded from `raw_source2`, and logged in `ingestion_quarantine_log` with `issue_type = 'BLANK_ROW'`.
* **Embedded Duplicate Header (Source 3, Line 16)**: **Correct**. Correctly identified by header string matching, excluded from `raw_source3`, and logged in `ingestion_quarantine_log` with `issue_type = 'DUPLICATE_HEADER'`.
* **Column-Shifted Malformed Row (Source 2, Line 20)**: **Correct with Nuance**. Detected, trapped, logged as `COLUMN_SHIFT`, un-shifted in memory, and cleanly ingested into canonical core tables. *Nuance*: The detection condition (`"@" not in email and ("react" in email or "python" in email or "," in email)`) relies on hardcoded skill strings.
* **Duplicate Records**: **Correct**.
  * `Rohit Verma` (S1 Line 32) and `R. Verma` (S1 Line 26) sharing `rohit.verma13@mailtest.example.org` correctly merge into 1 canonical person.
  * `Nikhil Chopra` with alternate email `alt.nikhil.chopra70@example.com` (S1 Line 28) and primary email `nikhil.chopra70@example.com` (S1 Line 38) correctly merge into 1 canonical person via matching phone number `9000000103`.
* **Email Normalization**: **Correct**. Strips whitespace and lowercases (`ISHA.CHOPRA95@...` → `isha.chopra95@...`). Validates email format against regex.
* **Phone Normalization**: **Correct**. Strips country prefixes (`+91-`, `+91`, `91`, leading `0`) to extract standardized 10-digit strings (`9000000131`).
* **City Normalization**: **Correct**. Standardizes location variants (`gurugram ` → `Gurugram`, `bangalore` → `Bengaluru`, `NOIDA` → `Noida`, `new delhi` → `Delhi NCR`).
* **Date Normalization**: **Correct**. Converts mixed formats (`YYYY-MM-DD`, `DD-MM-YYYY`, `MM/DD/YYYY`, `7 Jul 2026`) into standard ISO-8601 strings (`YYYY-MM-DD`).
* **CTC Normalization**: **Correct**. Converts raw annual INR numbers (>100 e.g. `332456`) to LPA floats (`3.32`) while preserving float LPA inputs (`4.2`).
* **Rate Normalization**: **Correct**. Distinguishes hourly rates (`1415/hr` → `hourly_rate_inr = 1415.0`) from monthly rates (`15k/month` → `monthly_rate_inr = 15000.0`).
* **Skills Normalization**: **Correct**. Lowercases, splits on commas, and deduplicates skill tags.
* **Conflicting Identities (`Deepak Nair` in Source 2)**: **Correct**. Source 2 contains two entries for `Deepak Nair`:
  * Line 15: `DEEPAK.NAIR44@EXAMPLE.COM`, `Bengaluru`
  * Line 32: `DEEPAK.NAIR57@EXAMPLE.IN`, `New Delhi`
  The resolver correctly identifies email and city conflicts, creates **2 distinct person entities**, and logs an entry in `entity_conflicts`.

---

## 3. Entity Resolution Review

### Evaluation of Hierarchy Rules

1. **Tier 1A (Exact Email Match - Confidence: HIGH / 1.0)**:
   * *Assessment*: Highly accurate across S1 and S2. 20 candidate records match on normalized email. Low false-positive risk.
2. **Tier 1B (Exact Phone Match - Confidence: HIGH / 1.0)**:
   * *Assessment*: Highly accurate across S1 and S3. 27 candidate records match on 10-digit normalized phone. Low false-positive risk.
3. **Tier 2 (Name + City Match - Confidence: MEDIUM / 0.85)**:
   * *Assessment*: Successfully links records between S2 (which lacks phone) and S3 (which lacks email).
   * *Examples linked via Name + City*:
     * `Divya Chopra` in `Noida` (S2 Line 21 ↔ S3 Line 30)
     * `Karan Chopra` in `Pune` (S2 Line 22 ↔ S3 Line 31)
     * `Manish Bhatia` in `Noida` (S2 Line 19 ↔ S3 Line 29)
     * `Vikram Mehta` in `Pune` (S2 Line 23 ↔ S3 Line 32)
   * *False-Positive Risk*: Moderate. If two different individuals in the same metropolitan city share a common name (e.g. `Rahul Sharma` in `Noida`), Tier 2 will merge them unless an email/phone conflict is present.
   * *False-Negative Risk*: Moderate. If an applicant relocates (e.g. `Delhi` in S1 vs `Gurugram` in S2), Tier 2 will fail to link them without email/phone overlap.

---

## 4. Data Lineage

* **Source Tracking**: Every canonical entity in `persons` is linked via `person_source_mappings` to its exact origin records.
* **Lineage Queryability**: Executing `SELECT * FROM person_source_mappings WHERE person_id = X` returns:
  * `source_system` (`naukri`, `gig_workers`, `cbnexus`)
  * `source_file` (`source1_naukri_applicants.csv`, etc.)
  * `source_line_number` (Exact 1-based CSV line number)
  * `raw_record_id` (Primary key in raw staging table)
  * `match_confidence` (`HIGH_CONFIDENCE`, `MEDIUM_CONFIDENCE`, `MANUAL_REVIEW`)
  * `match_rule_applied` (`RULE_1A_EXACT_EMAIL`, `RULE_1B_EXACT_PHONE`, `RULE_2_NAME_CITY`)

---

## 5. Raw-Data Preservation

* **Original CSV Integrity**: The three source CSV files in `data/` are byte-for-byte unchanged.
* **Staging Layer Inspection**:
  * Raw staging tables (`raw_source1_naukri`, `raw_source2_gig_workers`, `raw_source3_cbnexus`) store candidate strings as received from the CSV parser.
  * *Observation*: For the column-shifted row (S2 Line 20), `raw_source2_gig_workers` stores the un-shifted values (`email`=`ISHA.CHOPRA95@...`, `name`=`Isha Chopra`) rather than the raw malformed string array. The raw malformed string array is preserved in `ingestion_quarantine_log.raw_line_content`.

---

## 6. Idempotency Analysis

* **Execution without `--reset`**:
  * Running `python -m src.app.main` twice consecutively without `--reset` produces duplicate records across all database tables:

| Table | First Run (Pristine) | Second Run (No `--reset`) | Result |
| :--- | :---: | :---: | :--- |
| `persons` | 56 | **112** | **DUPLICATED** |
| `person_source_mappings` | 103 | **206** | **DUPLICATED** |
| `ingestion_quarantine_log` | 3 | **6** | **DUPLICATED** |
| `entity_conflicts` | 2 | **4** | **DUPLICATED** |

* **Root Cause**: Ingestion INSERT statements do not use `UNIQUE` constraints or `ON CONFLICT DO NOTHING` checks based on `(source_system, source_file, line_number)`.

---

## 7. Database & Architecture Review

* **SQLite Suitability for Task 1**: Excellent. Lightweight, single-file, zero-dependency, fast local execution.
* **Task 2 (n8n Workflow Integration)**:
  * n8n supports SQLite via the standard n8n-nodes-base.sqlite node or direct Python execution nodes.
  * *Concurrency Concern*: Default SQLite locking can cause `database is locked` errors during concurrent n8n workflow executions unless `WAL` mode (`PRAGMA journal_mode=WAL;`) and a busy timeout (`PRAGMA busy_timeout=5000;`) are configured.
* **Path Portability Concern**: `src/database/connection.py` hardcodes `z:\ConsultBae_AI_Automation_Assignment\data\consultbae.db`. This path will break when executed on a different drive letter or operating system.

---

## 8. Test Quality

* **Current Coverage**: 12 unit and integration tests in `tests/test_task1.py`.
* **Passing Status**: 12 / 12 tests pass.
* **Gaps Identified**:
  1. Missing non-reset pipeline re-execution test (idempotency verification).
  2. Missing test for column-shift detection on non-hardcoded skill strings.
  3. Missing test for Name+City false-positive collision guardrails.
  4. Missing test for SQLite WAL mode / concurrency pragmas.

---

## 9. Actual Verification & Reconciliation

### Metric Verification

* **Pytest Verification Output**: `12 passed in 0.75s`
* **Single-Run Pipeline Metrics**:
  * Total Raw Records Ingested: `103`
  * Quarantined Anomalies: `3`
  * Canonical Persons Created: `56`
  * Source Lineage Mappings Saved: `103`
  * Entity Conflicts Logged: `2`

### Reconciliation with Source Data Files

| Source File | Total Lines | Header Lines | Data Rows | Quarantined Rows | Clean Ingested Rows |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `source1_naukri_applicants.csv` | 43 | 1 | 42 | 0 | **42** |
| `source2_gig_workers.csv` | 33 | 1 | 32 | 1 (Line 12 Blank) | **31** |
| `source3_cbnexus_contacts.csv` | 32 | 1 | 31 | 1 (Line 16 Header) | **30** |
| **TOTALS** | **108** | **3** | **105** | **2 Excluded + 1 Shifted** | **103** |

* **Reconciliation Explanation**:
  1. Total lines across 3 CSV files = 43 + 33 + 32 = **108 lines**.
  2. Subtract 3 file header rows = **105 data rows**.
  3. S2 Line 12 (Blank) is excluded from raw table → logged to quarantine.
  4. S3 Line 16 (Duplicate Header) is excluded from raw table → logged to quarantine.
  5. S2 Line 20 (Column Shift) is logged to quarantine, un-shifted, and ingested cleanly.
  6. Clean ingested records = 105 - 2 (excluded) = **103 records**.
  7. Exactly 103 source mappings are created in `person_source_mappings` (1 mapping per clean ingested record).
  8. Overlapping candidate identities across S1 (42), S2 (31), and S3 (30) consolidate into **56 canonical person entities**.

---

## 10. Problems List (Ordered by Severity)

### CRITICAL
1. **Idempotency Failure on Pipeline Re-execution**: Executing `main.py` without `--reset` duplicates database records, mappings, quarantine logs, and entities.

### HIGH
2. **Hardcoded Windows Absolute Path**: `src/database/connection.py` hardcodes `z:\ConsultBae_AI_Automation_Assignment...`, breaking portability across OS environments.
3. **Fragile Column-Shift Detection**: `raw_ingestor.py` uses hardcoded string matching (`"react" in email or "python" in email`) to detect column shifts.

### MEDIUM
4. **Modified Data in Raw Staging**: `raw_source2_gig_workers` stores un-shifted values for Line 20 rather than the raw unparsed string.
5. **Missing SQLite Concurrency Pragmas**: Missing `PRAGMA journal_mode=WAL;` and `PRAGMA busy_timeout=5000;` necessary for n8n workflow integration.

### LOW
6. **Test Coverage Gaps**: Missing tests for non-reset idempotency and edge-case name collisions.

---

## 11. Recommended Fixes

1. **Fix Idempotency (CRITICAL)**:
   * Add `UNIQUE(source_system, source_file, line_number)` to raw staging tables and `person_source_mappings`.
   * Use `INSERT OR REPLACE` or check existing line numbers before running ingestion so repeated executions without `--reset` are strictly idempotent.
2. **Fix Path Portability (HIGH)**:
   * Use relative project root path resolution: `os.path.join(os.path.dirname(__file__), "..", "..", "data", "consultbae.db")`.
3. **Fix Column-Shift Detection (HIGH)**:
   * Replace hardcoded skill search with generic validation: if `email` fails standard regex `normalize_email(email) == ""` AND contains `,`, trigger column-shift re-mapping.
4. **Fix Raw Staging Preservation (MEDIUM)**:
   * Store original unparsed CSV fields in raw staging tables; perform un-shifting during normalizer/resolver execution.
5. **Fix SQLite Concurrency (MEDIUM)**:
   * Add `conn.execute("PRAGMA journal_mode=WAL;")` and `conn.execute("PRAGMA busy_timeout=5000;")` in `src/database/connection.py`.

---

## 12. Final Recommendation

**KEEP WITH FIXES**

The current implementation has a sound 3-tier entity resolution architecture, clean normalization functions, complete source lineage mapping, and robust anomaly quarantine handling. Fixing the idempotency behavior, path portability, and concurrency pragmas will make it fully production-ready.

---

## 13. Additional Independent Verification

A second independent code and runtime audit was conducted to verify structural data handling, raw preservation, path portability, and idempotency behavior.

### Summary of Confirmed Technical Issues

1. **Idempotency Failure on Repeated Execution**:
   * *Verification*: Running `python -m src.app.main` twice without `--reset` doubled entity and mapping counts:
     * Canonical Person Entities: Increased from **56** to **112**.
     * Source Lineage Mappings: Increased from **103** to **206**.
     * Quarantined Records: Increased from **3** to **6**.
     * Entity Conflicts: Increased from **2** to **4**.
   * *Diagnosis*: Ingestion SQL statements lacked `UNIQUE` constraints and `ON CONFLICT` upsert logic.

2. **Hardcoded Windows Absolute File Path**:
   * *Verification*: `src/database/connection.py` hardcoded `z:\ConsultBae_AI_Automation_Assignment\data\consultbae.db`.
   * *Diagnosis*: Violates repository portability; breaks on non-Windows OS or alternative mount paths.

3. **Fragile Malformed-Row Detection**:
   * *Verification*: `raw_ingestor.py` used `"@" not in email and ("react" in email or "python" in email or "," in email)`.
   * *Diagnosis*: Brittle vocabulary dependency. If a column-shifted row contained different skills (e.g. `'docker, sql'`), detection would fail.

4. **Incomplete Raw-Line Preservation in Staging**:
   * *Verification*: For Source 2 Line 20, `raw_source2_gig_workers` stored un-shifted/corrected values (`email`=`ISHA.CHOPRA95@...`, `name`=`Isha Chopra`) instead of saving the exact unparsed CSV line string.
   * *Diagnosis*: Overwrote raw staging input with interpreted values.

5. **SQLite Concurrency & Schema Constraints**:
   * *Verification*: Schema lacked PostgreSQL-native data types (`TIMESTAMPTZ`, `DOUBLE PRECISION`, `SERIAL`), expression indexes (`LOWER(email)`), and explicit `ON CONFLICT` constraints required for n8n/FastAPI integration.

---

## 14. PostgreSQL Migration & Engineering Fixes Verification

All technical defects identified during engineering reviews have been resolved and independently verified.

### Summary of Engineering Hardening Fixes Applied

1. **PostgreSQL Migration (`psycopg2` + Supabase Architecture)**:
   * Migrated database engine to PostgreSQL DDL schema (`database/schema.sql`).
   * Created `.env.example` for environment variable credential management (`POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, etc.).
   * Decoupled Python ingestion logic from proprietary REST APIs to enable direct database connectivity for Task 2 (n8n) and Task 3 (FastAPI).

2. **Real Pipeline Idempotency (3-Run Empirical Verification)**:
   * Added `UNIQUE(source_system, source_file, line_number)` constraints across all raw tables and lineage mapping tables.
   * Added `ON CONFLICT (...) DO NOTHING` / `DO UPDATE` parameters to raw ingestion and resolution queries.
   * *Multi-Run Results*:

| Database Metric | Run 1 (Clean DB) | Run 2 (No Reset) | Run 3 (No Reset) | Status |
| :--- | :---: | :---: | :---: | :---: |
| **Total Raw Records Ingested** | 103 | 103 | 103 | **100% STABLE** |
| **Canonical Persons Created** | 56 | 56 | 56 | **100% STABLE** |
| **Source Lineage Mappings** | 103 | 103 | 103 | **100% STABLE** |
| **Unique Email Records** | 56 | 56 | 56 | **100% STABLE** |
| **Unique Phone Records** | 45 | 45 | 45 | **100% STABLE** |
| **Skill Tag Entries** | 328 | 328 | 328 | **100% STABLE** |
| **Entity Conflicts Logged** | 2 | 2 | 2 | **100% STABLE** |
| **Quarantined Anomalies** | 3 | 3 | 3 | **100% STABLE** |

3. **Structural Malformed-Row Detection**:
   * Removed hardcoded skill strings (`"react"`, `"python"`).
   * Replaced with structural validation: `normalize_email(Field_0) == ""` AND `normalize_email(Field_1) != ""` triggers structural column shift re-mapping.

4. **Raw Data Preservation**:
   * Stored exact verbatim unparsed CSV line string in `raw_line_content`.
   * Added `was_malformed = TRUE` and `recovery_reason` to `raw_source2_gig_workers` for Line 20.
   * Preserved original source CSV files in `data/` 100% byte-for-byte untouched.

5. **Path Portability**:
   * Removed all `Z:\...` hardcoded strings. All paths derived dynamically via `PROJECT_ROOT`.


