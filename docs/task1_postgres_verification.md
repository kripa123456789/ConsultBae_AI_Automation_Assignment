# Task 1 PostgreSQL Verification Report

## 1. Database Connection

* **Database Engine**: PostgreSQL 17.6 (Supabase Managed PostgreSQL Pooler)
* **Host**: `aws-0-ap-south-1.pooler.supabase.com:5432`
* **Database Name**: `postgres`
* **Database User**: `postgres`
* **SSL Mode**: `require` (SSL Enabled & Active)
* **Authentication**: Credentials managed via local `.env` file (Git-ignored).

---

## 2. Schema Verification

The PostgreSQL schema defined in `database/schema.sql` was executed on the live Supabase PostgreSQL database inside a single atomic transaction.

### Catalog Verification Query (`information_schema` / `pg_indexes`)
* **Tables Created & Verified (11 Tables)**:
  * `raw_source1_naukri` (PK: `raw_source1_naukri_pkey`, UNIQUE: `uq_raw_s1_line`)
  * `raw_source2_gig_workers` (PK: `raw_source2_gig_workers_pkey`, UNIQUE: `uq_raw_s2_line`)
  * `raw_source3_cbnexus` (PK: `raw_source3_cbnexus_pkey`, UNIQUE: `uq_raw_s3_line`)
  * `ingestion_quarantine_log` (PK: `ingestion_quarantine_log_pkey`, UNIQUE: `uq_quarantine_line`)
  * `persons` (PK: `persons_pkey`)
  * `person_source_mappings` (PK: `person_source_mappings_pkey`, FK: `person_source_mappings_person_id_fkey`, UNIQUE: `uq_person_source_line`)
  * `candidate_profiles` (PK: `candidate_profiles_pkey`, FK: `candidate_profiles_person_id_fkey`, UNIQUE: `candidate_profiles_person_id_key`)
  * `person_emails` (PK: `person_emails_pkey`, FK: `person_emails_person_id_fkey`, UNIQUE: `uq_person_email`)
  * `person_phones` (PK: `person_phones_pkey`, FK: `person_phones_person_id_fkey`, UNIQUE: `uq_person_phone`)
  * `candidate_skills` (PK: `candidate_skills_pkey`, FK: `candidate_skills_person_id_fkey`, UNIQUE: `uq_person_skill_source`)
  * `entity_conflicts` (PK: `entity_conflicts_pkey`, FK: `entity_conflicts_person_id_fkey`, UNIQUE: `uq_conflict_record`)

* **Indexes Verified**:
  * `idx_persons_email` on `persons(LOWER(primary_email))`
  * `idx_persons_phone` on `persons(primary_phone)`
  * `idx_persons_name_city` on `persons(LOWER(canonical_name), LOWER(canonical_city))`
  * `idx_person_emails_addr` on `person_emails(LOWER(email_address))`
  * `idx_person_phones_num` on `person_phones(phone_number)`
  * `idx_mappings_person` on `person_source_mappings(person_id)`

---

## 3. Actual PostgreSQL Table Counts

Direct SQL count queries executed against the live Supabase PostgreSQL database:

```sql
SELECT COUNT(*) FROM raw_source1_naukri;         -- Result: 42
SELECT COUNT(*) FROM raw_source2_gig_workers;    -- Result: 31
SELECT COUNT(*) FROM raw_source3_cbnexus;        -- Result: 30
SELECT COUNT(*) FROM persons;                    -- Result: 56
SELECT COUNT(*) FROM person_source_mappings;    -- Result: 103
SELECT COUNT(*) FROM person_emails;              -- Result: 56
SELECT COUNT(*) FROM person_phones;              -- Result: 45
SELECT COUNT(*) FROM candidate_skills;          -- Result: 328
SELECT COUNT(*) FROM entity_conflicts;          -- Result: 2
SELECT COUNT(*) FROM ingestion_quarantine_log;  -- Result: 3
```

---

## 4. Entity Resolution Verification

Direct PostgreSQL SQL queries verifying cross-source candidate linking:

1. **Tri-Source Candidate Linkage (`Varun Jain`)**:
   * Query: `SELECT person_id, canonical_name, primary_email, primary_phone, canonical_city FROM persons WHERE canonical_name = 'Varun Jain';`
   * Result: `ID=18`, Name=`Varun Jain`, Email=`varun.jain29@example.com`, Phone=`9000000263`, City=`Pune`.
   * Lineage Query (`SELECT source_system, source_line_number, match_rule_applied FROM person_source_mappings WHERE person_id = 18;`):
     * Lineage Entry 1: `naukri`, Line `19`, Rule `INITIAL_RECORD`
     * Lineage Entry 2: `gig_workers`, Line `2`, Rule `RULE_1A_EXACT_EMAIL`
     * Lineage Entry 3: `cbnexus`, Line `12`, Rule `RULE_1B_EXACT_PHONE`

2. **Email Match Verification (`tanvi.gupta31@example.com`)**:
   * Linked across 3 source records (`naukri` Line 2, `gig_workers` Line 11, `cbnexus` Line 22) into a single canonical `person_id`.

3. **Phone Match Verification (`9000000146`)**:
   * Linked across 2 source records (`naukri` Line 16, `cbnexus` Line 3) into a single canonical `person_id` for candidate `Ritu Sharma`.

4. **Ambiguous Conflict Guardrail (`Deepak Nair` & `Arjun Mehta`)**:
   * Query: `SELECT * FROM entity_conflicts;`
   * Result: Logged 2 conflict entries trapping email and phone collisions across separate profiles without false-positive entity merges.

---

## 5. Anomaly / Quarantine Verification

Direct PostgreSQL query inspecting the malformed Source 2 record:

```sql
SELECT line_number, raw_email_id, raw_worker_name, was_malformed, recovery_reason, raw_line_content 
FROM raw_source2_gig_workers WHERE line_number = 20;
```

* **`was_malformed`**: `True`
* **`recovery_reason`**: `Structural Column Shift: Field 0 fails email format, Field 1 contains valid email`
* **`raw_line_content`**: `react, javascript, mysql,ISHA.CHOPRA95@MAILTEST.EXAMPLE.ORG,Isha Chopra,1406/hr,Pune,active` (Verbatim raw CSV string preserved)
* **Recovered Email**: `ISHA.CHOPRA95@MAILTEST.EXAMPLE.ORG`
* **Recovered Name**: `Isha Chopra`
* **Quarantine Log**: Trapped `1` blank row (S2 Line 12), `1` duplicate header row (S3 Line 16), and `1` column shift (S2 Line 20).

---

## 6. Idempotency Verification

The Task 1 pipeline was executed **3 consecutive times** against the live Supabase PostgreSQL database:

| Table Metric | Run 1 (Clean DB) | Run 2 (No Reset) | Run 3 (No Reset) | Status |
| :--- | :---: | :---: | :---: | :---: |
| `raw_source1_naukri` | 42 | 42 | 42 | **100% STABLE** |
| `raw_source2_gig_workers` | 31 | 31 | 31 | **100% STABLE** |
| `raw_source3_cbnexus` | 30 | 30 | 30 | **100% STABLE** |
| `persons` | 56 | 56 | 56 | **100% STABLE** |
| `person_source_mappings` | 103 | 103 | 103 | **100% STABLE** |
| `person_emails` | 56 | 56 | 56 | **100% STABLE** |
| `person_phones` | 45 | 45 | 45 | **100% STABLE** |
| `candidate_skills` | 328 | 328 | 328 | **100% STABLE** |
| `entity_conflicts` | 2 | 2 | 2 | **100% STABLE** |
| `ingestion_quarantine_log` | 3 | 3 | 3 | **100% STABLE** |

* **Result**: Table counts remained 100% identical across all 3 runs. Zero duplicate source mappings or canonical records were created.

---

## 7. Source File Integrity

* `data/source1_naukri_applicants.csv`: 5,296 bytes
* `data/source2_gig_workers.csv`: 3,415 bytes
* `data/source3_cbnexus_contacts.csv`: 1,269 bytes
* **Result**: All 3 source CSV files remain 100% byte-for-byte untouched.

---

## 8. Issues Found

* **None**. All schema requirements, constraints, entity resolution logic, malformed row recovery, and idempotency guardrails executed without errors.

---

## 9. Final Status

* **PostgreSQL Schema Execution**: SUCCESS
* **Live Catalog Verification**: SUCCESS
* **Multi-Run Idempotency Verification**: STABLE (100% PASS)
* **Source Lineage Traceability**: VERIFIED
* **Source File Integrity**: UNCHANGED
