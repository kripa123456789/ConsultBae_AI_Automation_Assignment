# ConsultBae — AI Automation Take-Home Assignment

An AI automation repository merging candidate data across disparate systems, resolving candidate identities without common keys, handling data quality anomalies with complete source lineage, and building downstream automation workflows.

---

## Assignment Tasks & Implementation Status

*(Authoritative Reference: `assignment/ConsultBae_Assignment_Rulebook.pdf`)*

| Task | Title | Core / Optional | Status | Key Deliverables / Artifacts |
| :-: | :--- | :-: | :-: | :--- |
| **Task 1** | **Merge** | **Core** | **COMPLETED** | PostgreSQL schema ([database/schema.sql](file:///Z:/ConsultBae_AI_Automation_Assignment/database/schema.sql)), Ingestion & Normalization pipeline ([src/ingestion/](file:///Z:/ConsultBae_AI_Automation_Assignment/src/ingestion/)), 3-Tier Entity Resolution engine ([src/matching/](file:///Z:/ConsultBae_AI_Automation_Assignment/src/matching/)), automated test suite ([tests/test_task1.py](file:///Z:/ConsultBae_AI_Automation_Assignment/tests/test_task1.py)). |
| **Task 2** | **Automate with a no-code/low-code tool** | **Core** | **NOT STARTED** | Reserved for n8n workflow JSON export in [n8n/](file:///Z:/ConsultBae_AI_Automation_Assignment/n8n/). |
| **Task 3** | **Mini audio collection app** | **Core** | **NOT STARTED** | Reserved for web audio recorder/uploader app & metadata extractor. |
| **Task 4** | **Data issues report** | **Core** | **COMPLETED** | Complete report embedded in [README.md](#data-issues-report) below. |
| **Task 5** | **Stretch** | **Optional** | **NOT STARTED** | 1-page no-code architectural write-up for 5,000 gig worker scale. |

---

## Setup & Execution Guide

### Prerequisites
* Python 3.10+
* PostgreSQL database instance (or Supabase PostgreSQL connection)

### 1. Clone Repository & Set Up Environment
```bash
git clone https://github.com/your-username/ConsultBae_AI_Automation_Assignment.git
cd ConsultBae_AI_Automation_Assignment

# Create virtual environment
python -m venv .venv
# Activate virtual environment (Windows PowerShell)
.\.venv\Scripts\Activate.ps1
# Activate virtual environment (Linux/macOS)
# source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment Variables
Copy `.env.example` to `.env` and fill in your PostgreSQL credentials (e.g. Supabase connection details):
```bash
cp .env.example .env
```
Ensure your `.env` contains:
```env
POSTGRES_HOST=aws-0-ap-south-1.pooler.supabase.com
POSTGRES_PORT=5432
POSTGRES_DB=postgres
POSTGRES_USER=your_user
POSTGRES_PASSWORD=your_password
POSTGRES_SSLMODE=require
```

### 3. Run Task 1 Ingestion & Entity Resolution Pipeline
To initialize the database schema and execute the ETL pipeline:
```bash
python -m src.app.main --reset
```

### 4. Run Automated Test Suite
To verify pipeline normalization, anomaly recovery, entity resolution, and idempotency:
```bash
python -m pytest tests/test_task1.py
```
*(All 15 unit and end-to-end integration tests pass cleanly).*

---

## Data Issues Report

This section documents every data-quality problem found across the three raw source files (`source1_naukri_applicants.csv`, `source2_gig_workers.csv`, `source3_cbnexus_contacts.csv`) and the precise engineering actions taken in Task 1.

---

### A. Data Quality / Consistency Findings

The following 11 items represent directly observed raw file anomalies, syntax errors, structural corruptions, and field formatting variations:

#### 1. Blank Row (`source2_gig_workers.csv`)
* **Evidence**: Line 12 in `source2_gig_workers.csv` is completely empty (`,,,,,`).
* **Problem**: Causes empty record insertions or database `NOT NULL` constraint validation failures.
* **Why it matters**: Inserting empty rows pollutes analytics and breaks relational integrity.
* **Task 1 Handling**: Checked in `ingest_source2()` during CSV loop (`all(c.strip() == "" for c in r)`). Quarantined & dropped; logged in `ingestion_quarantine_log` as `BLANK_ROW` with `resolution_action = 'DROPPED'`.

#### 2. Embedded Duplicate Header (`source3_cbnexus_contacts.csv`)
* **Evidence**: Line 16 in `source3_cbnexus_contacts.csv` contains `Name,Phone Number,City,Verified,Projects Completed`.
* **Problem**: Duplicate CSV header row embedded in the middle of data rows.
* **Why it matters**: Treats column titles ("Name", "Phone Number") as an actual candidate record.
* **Task 1 Handling**: Structural check in `ingest_source3()` (`name == "Name"` & `phone == "Phone Number"`). Quarantined & dropped; logged in `ingestion_quarantine_log` as `DUPLICATE_HEADER` with `resolution_action = 'DROPPED'`.

#### 3. Structural Column Shift / Malformed Row (`source2_gig_workers.csv`)
* **Evidence**: Line 20 in `source2_gig_workers.csv` contains `['react, javascript, mysql', 'ISHA.CHOPRA95@MAILTEST.EXAMPLE.ORG', 'Isha Chopra', '1406/hr', 'Pune', 'active']`.
* **Problem**: Values shifted 1 column position to the right (skills in email column, email in name column, name in rate column, rate in location column, location in status column, status in skills column).
* **Why it matters**: Skews parser completely; puts comma-separated skills into email field.
* **Task 1 Handling**: Structural validation check in `ingest_source2()` (`Field 0` fails email regex & `Field 1` passes email regex). Saved verbatim raw CSV line in `raw_line_content`, set `was_malformed = TRUE` and `recovery_reason` in `raw_source2_gig_workers`, logged `COLUMN_SHIFT` in quarantine, and un-shifted fields into correct slots in memory (`email`, `name`, `rate`, `location`, `status`, `skills`) for canonical ingestion.

#### 4. Inconsistent CTC Units (`source1_naukri_applicants.csv`)
* **Evidence**: Line 3 (`332456` raw annual INR) vs Line 2 (`4.2` LPA float).
* **Problem**: Raw annual INR figures (e.g. 332,456) mixed with LPA floats (e.g. 4.2).
* **Why it matters**: Direct sorting or filtering distorts salary metrics by orders of magnitude.
* **Task 1 Handling**: `normalize_ctc()` in `normalizer.py` converts values > 100 into LPA float by dividing by 100,000 and rounding to 2 decimal places (`332456` $\rightarrow$ `3.32`). Stored in `candidate_profiles.expected_ctc_lpa`.

#### 5. Inconsistent Rate Units & Formats (`source2_gig_workers.csv`)
* **Evidence**: Line 2 (`1415/hr`) vs Line 3 (`15k/month`).
* **Problem**: Hourly rates (`/hr`) and monthly rates (`k/month`) mixed in a single text column.
* **Why it matters**: Hourly and monthly rates are distinct compensation structures and cannot be stored or compared in a single raw numeric field.
* **Task 1 Handling**: `normalize_rate()` in `normalizer.py` parses string into separate structured numeric fields (`hourly_rate_inr` or `monthly_rate_inr`). Stored in distinct columns in `candidate_profiles`.

#### 6. Mixed Date Formats (`source1_naukri_applicants.csv`)
* **Evidence**: Line 2 (`2026-08-08` YYYY-MM-DD), Line 3 (`24-07-2026` DD-MM-YYYY), Line 5 (`07/13/2026` MM/DD/YYYY), Line 6 (`7 Jul 2026` D MMM YYYY).
* **Problem**: Four distinct date string representations across applicant records.
* **Why it matters**: Non-standard date strings break SQL range queries, indexing, and chronological sorting.
* **Task 1 Handling**: `normalize_date()` in `normalizer.py` tries multiple `strptime` formats and standardizes all dates into ISO-8601 strings (`YYYY-MM-DD`).

#### 7. Phone Format Inconsistencies (`source1_naukri_applicants.csv` & `source3_cbnexus_contacts.csv`)
* **Evidence**: S1 Line 2 (`+919000000254`), S1 Line 5 (`09000000287`), S3 Line 3 (`919000000146`), S3 Line 5 (`+91-9000000131`), S1 Line 10 (`9000000237`).
* **Problem**: Leading zeros, `+91` country codes, `91` prefixes, and hyphen delimiters.
* **Why it matters**: Exact string matching fails for entity resolution between Source 1 and Source 3 despite representing the identical telephone number.
* **Task 1 Handling**: `normalize_phone()` in `normalizer.py` strips non-digits and leading `+91`, `91`, or `0` trunk prefixes to extract clean 10-digit strings stored in `person_phones` and used as the Tier 1B matching key.

#### 8. City Name Casing & Variations (All 3 CSV Sources)
* **Evidence**: S1 Line 4 (`GURGAON`), S2 Line 2 (`bangalore`), S2 Line 3 (`Noida ` trailing space), S3 Line 4 (`Gurgaon`), S3 Line 5 (`new delhi`).
* **Problem**: Casing differences, trailing spaces, and naming variants (`Gurgaon` vs `Gurugram`, `bangalore` vs `Bengaluru`, `new delhi` vs `Delhi`).
* **Why it matters**: Prevents location filtering and breaks Tier 2 (Name + City) entity resolution.
* **Task 1 Handling**: `normalize_city()` in `normalizer.py` uses `CITY_CANONICAL_MAP` to map variants to standardized canonical city names (`Bengaluru`, `Gurugram`, `Noida`, `Delhi NCR`).

#### 9. Email Casing & Whitespace (`source1_naukri_applicants.csv` & `source2_gig_workers.csv`)
* **Evidence**: S2 Line 7 (`ISHA.CHOPRA95@MAILTEST.EXAMPLE.ORG` in ALL CAPS) vs S1 Line 2 (`tanvi.gupta31@example.com`).
* **Problem**: Uppercase email strings and leading/trailing whitespace.
* **Why it matters**: Case-sensitive string joins fail between Source 1 and Source 2.
* **Task 1 Handling**: `normalize_email()` in `normalizer.py` lowercases, trims whitespace, and validates regex format. Stored in `person_emails` and used as the Tier 1A matching key.

#### 10. Categorical Field Variations (`source2_gig_workers.csv` & `source3_cbnexus_contacts.csv`)
* **Evidence**: S3 Line 2 (`Y`), Line 3 (`yes`), Line 4 (`No`), Line 7 (`Verified`); S2 Line 2 (`Active`), Line 7 (`active`), Line 15 (`paused`).
* **Problem**: Categorical fields stored as mixed text strings (`Y`, `yes`, `Verified`).
* **Why it matters**: Prevents boolean filtering and enum queries in database operations.
* **Task 1 Handling**: `normalize_verified()` maps positive strings (`y`, `yes`, `verified`, `true`) to boolean `TRUE`/`FALSE`. Status strings are trimmed and lowercased. Stored in `candidate_profiles`.

#### 11. Abbreviated Name vs Full Name (`source1_naukri_applicants.csv`)
* **Evidence**: S1 Line 26 (`R. Verma`, `rohit.verma13@mailtest.example.org`) vs Line 32 (`Rohit Verma`, `rohit.verma13@mailtest.example.org`).
* **Problem**: Candidate listed with abbreviated initial (`R. Verma`) on one line and full name (`Rohit Verma`) on another.
* **Why it matters**: Exact name matching fails to link the abbreviated name record to the full candidate entry.
* **Task 1 Handling**: Tier 1A Email Match in `resolver.py` anchors both records via identical normalized email address (`rohit.verma13@mailtest.example.org`), consolidating both source records into a single canonical `person` entity.

---

### B. Derived Data Finding

The following item represents a genuine discovery derived by cross-referencing attributes across multiple rows:

#### 12. Alternate Emails for Same Individual (`source1_naukri_applicants.csv`)
* **Evidence**: S1 Line 28 (`Nikhil Chopra`, `alt.nikhil.chopra70@example.com`, phone `09000000103`) vs S1 Line 38 (`Nikhil Chopra`, `nikhil.chopra70@example.com`, phone `09000000103`). Both share identical phone, city (`NOIDA`), exp (`0.8`), CTC (`7.8`), and skills (`Pandas, SQL, n8n`).
* **Problem**: Candidate registered using a secondary/alternate email address.
* **Why it matters**: Email-only matching would fail to merge these records, creating duplicate candidate profiles.
* **Task 1 Handling**: Tier 1B Phone Match in `resolver.py` anchors both records via normalized phone `9000000103`, linking both email addresses to a single canonical `person` record while preserving both in `person_emails` (one flagged primary).

---

### C. Entity Resolution Risk / Guardrail

The following item represents a safety guardrail implemented to handle identity risks present in the raw data:

#### 13. Ambiguous Candidates with Identical Names (`source2_gig_workers.csv` & `source3_cbnexus_contacts.csv`)
* **Evidence**: S2 Line 15 (`Deepak Nair`, `DEEPAK.NAIR44@EXAMPLE.COM` in Bengaluru) vs S2 Line 32 (`Deepak Nair`, `DEEPAK.NAIR57@EXAMPLE.IN` in New Delhi).
* **Problem**: Two distinct real-world individuals sharing the exact same name (`Deepak Nair`) across different locations and email domains.
* **Why it matters**: Naive name-only or name-first matching would incorrectly collapse two distinct individuals into a single corrupted candidate profile.
* **Task 1 Handling**: Tier 3 Conflict Guardrail in `resolver.py` checks for email/phone contradictions when Name+City matches. When conflicting emails or phone numbers exist, the resolver refuses to merge them, creates **2 distinct canonical `person` entities**, and logs the conflict in `entity_conflicts` with `resolution_strategy = 'SEPARATE_ENTITIES_RETAINED'`.

---

## Stuck Log

Documentation of the technical challenges encountered during the design and implementation of Task 1, along with the precise resolutions.

---

### Challenge 1: Entity Resolution without a Common Global ID
* **Problem**: The three source CSV datasets represent candidates from distinct products (Naukri, Gig Workers, CBNexus) without any shared primary key or global candidate identifier.
* **What I Tried**:
  * Evaluated pure exact string matching across all fields simultaneously (failed because S2 lacks phone and S3 lacks email).
  * Evaluated fuzzy name matching (Levenshtein distance) as a primary join key.
* **What I Searched / Asked AI**:
  * Used AI assistance to explore entity-resolution hierarchy patterns for record linkage when primary identifiers are partially disjoint.
* **What Worked**:
  * Implemented a **3-Tier Resolution Hierarchy** in `resolver.py`:
    * *Tier 1A (Email Match)*: Links S1 ↔ S2 with high confidence (`1.0`).
    * *Tier 1B (Phone Match)*: Links S1 ↔ S3 with high confidence (`1.0`).
    * *Tier 2 (Name + City Match)*: Links S2 ↔ S3 with medium confidence (`0.85`).
    * *Tier 3 (Conflict Guardrail)*: Rejects merges if email/phone attributes explicitly contradict each other.
* **What I Rejected & Why**:
  * Rejected Name-Only matching because common Indian names (e.g. `Deepak Nair`, `Arjun Mehta`) collide across different locations and email domains, creating false-positive entity merges.
* **Final Result**: Successfully consolidated 103 raw records across 3 datasets into **56 canonical person entities** with 0 false-positive merges.

---

### Challenge 2: Malformed Source 2 Column-Shift Detection
* **Problem**: Line 20 of `source2_gig_workers.csv` is malformed, shifting all fields 1 column position to the right (putting skills into the email field).
* **What I Tried**:
  * Initially considered string keyword searching (e.g. checking if `"react"` or `"python"` is in the email string).
* **What I Searched / Asked AI**:
  * Used AI assistance to explore structural CSV validation techniques for detecting column-shifted rows without domain-specific vocabulary dependencies.
* **What Worked**:
  * Replaced vocabulary matching with **structural field validation**:
    * Check if `Field 0` fails email regex (`normalize_email(r[0]) == ""`).
    * Check if `Field 1` passes email regex (`normalize_email(r[1]) != ""`).
    * If `Field 0` is invalid as an email AND `Field 1` is valid as an email, a structural column shift is detected.
    * Un-shifted fields in memory (`r[0]` $\rightarrow$ skills, `r[1]` $\rightarrow$ email, `r[2]` $\rightarrow$ name, `r[3]` $\rightarrow$ rate, `r[4]` $\rightarrow$ location, `r[5]` $\rightarrow$ status).
    * Saved verbatim raw line string in `raw_line_content`, flagged `was_malformed = TRUE` in `raw_source2_gig_workers`, and logged to `ingestion_quarantine_log`.
* **What I Rejected & Why**:
  * Rejected hardcoded skill string matching (`"react" in email`) because it is brittle and would fail if a column-shifted row contained different skill tags (e.g. `'docker, sql'`).
* **Final Result**: Detected, quarantined, un-shifted, and ingested Line 20 cleanly into canonical database tables while preserving complete raw line lineage.

---

### Challenge 3: PostgreSQL Migration & Multi-Run Pipeline Idempotency
* **Problem**: The prototype pipeline duplicated records (`persons` count doubled from 56 to 112) when executed repeatedly without table reset because SQL INSERT statements lacked uniqueness constraints and conflict resolution.
* **What I Tried**:
  * Considered clearing tables automatically on every run, but this violates non-destructive production data pipelines.
* **What I Searched / Asked AI**:
  * Used AI assistance to evaluate idempotent SQL upsert patterns (`INSERT ... ON CONFLICT DO UPDATE / DO NOTHING`) for PostgreSQL schema constraints.
* **What Worked**:
  * Added composite `UNIQUE` constraints to schema DDL (`database/schema.sql`):
    * `UNIQUE (source_system, source_file, line_number)` on raw staging tables.
    * `UNIQUE (source_system, source_file, source_line_number)` on `person_source_mappings`.
    * `UNIQUE (person_id, email_address)` on `person_emails`.
    * `UNIQUE (person_id, phone_number)` on `person_phones`.
  * Updated ingestion queries to use `ON CONFLICT (source_system, source_file, line_number) DO UPDATE SET ...` and `resolver.py` to use `ON CONFLICT DO NOTHING`.
  * Added an idempotency guardrail check in `src/app/main.py`.
* **What I Rejected & Why**:
  * Rejected relying solely on table truncation (`DROP TABLE`), as real production ETL pipelines must safely re-run over existing databases idempotently.
* **Final Result**: Verified multi-run idempotency across 3 consecutive executions against live PostgreSQL (Supabase); database table counts remained 100% stable (Run 1 == Run 2 == Run 3: 56 persons, 103 mappings).

---

## Task 5 — Stretch

**Status: NOT STARTED**

*(Optional 1-page no-code architectural scaling analysis for 5,000 gig workers over a weekend load reserved for future implementation).*

---

## Submission Checklist

- [x] **GitHub repository** with incremental commit history
- [x] **README.md** with setup guide + Data Issues Report + Stuck Log
- [ ] **Task 2 n8n flow JSON** exported into repo
- [ ] **Task 3 Mini audio collection app** working end-to-end
- [ ] **Screen recording** ($\le$ 6 minutes, voice required, face optional)
- [ ] **Final email reply** containing repository link + video link before deadline
