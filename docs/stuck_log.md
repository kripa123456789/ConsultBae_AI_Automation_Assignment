# Continuous Project Journal & Stuck Log

This document serves as the running, continuous engineering journal for the ConsultBae AI Automation project. Every genuine technical blocker, architectural pivot, debugging event, and resolution is documented here as it occurs during development.

---

## Technical Events & Problem-Solving Journal

### 1. Entity Resolution Without a Common Global ID

* **Problem**:
  The three input CSV files (`source1_naukri_applicants.csv`, `source2_gig_workers.csv`, `source3_cbnexus_contacts.csv`) originate from completely separate product databases without any shared candidate primary key or global identifier. Furthermore, each source collects a disjoint subset of candidate attributes: Source 2 (Gig Workers) contains emails and skills but lacks phone numbers; Source 3 (CBNexus) contains phone numbers and project stats but lacks email addresses.

* **What I initially considered**:
  * Attempting a single global exact-string match across all fields simultaneously.
  * Using fuzzy string distance (e.g., Levenshtein distance on candidate names) as the primary entity join key.

* **What I tried**:
  * Tested global exact-matching across `Name + Email + Phone + City`. This failed immediately because Source 2 records have empty phone fields and Source 3 records have empty email fields, resulting in 0 cross-source matches.

* **What failed / was rejected**:
  * **Rejected Name-Only Matching**: Merging candidate profiles based solely on candidate name strings (e.g., `Deepak Nair` or `Arjun Mehta`) was explicitly rejected. In real-world data, identical names represent distinct individuals operating in different locations or using different email domains. Name-only matching creates severe false-positive merges, corrupting candidate profiles.

* **What I searched or asked AI**:
  * Used AI assistance to explore entity-resolution hierarchy patterns for record linkage when primary identifiers are partially disjoint.

* **Final solution**:
  * Designed and implemented a **3-Tier Entity Resolution Hierarchy** in [src/matching/resolver.py](file:///Z:/ConsultBae_AI_Automation_Assignment/src/matching/resolver.py):
    * **Tier 1A (Exact Email Match)**: High confidence (`1.0`). Links Source 1 $\leftrightarrow$ Source 2.
    * **Tier 1B (Exact Phone Match)**: High confidence (`1.0`). Links Source 1 $\leftrightarrow$ Source 3.
    * **Tier 2 (Name + Canonical City Match)**: Medium confidence (`0.85`). Links Source 2 $\leftrightarrow$ Source 3 when email/phone are absent.
    * **Tier 3 (Conflict Guardrail)**: Evaluates attribute contradictions. If a Tier 2 Name+City candidate match possesses conflicting email addresses or phone numbers, the engine refuses to merge them, creates **2 distinct canonical `person` entities**, and logs the conflict in `entity_conflicts` with `resolution_strategy = 'SEPARATE_ENTITIES_RETAINED'`.

* **Why I chose it**:
  * Maximizes high-confidence automated matches via unique identifiers (email/phone) while preventing false-positive name collisions through strict conflict guardrails.

* **How I verified it**:
  * Executed unit tests in `tests/test_task1.py` (`test_tri_source_match_varun_jain` and `test_conflicts_logged`). Verified that candidate `Varun Jain` correctly links across all 3 source systems into a single `person_id` (18), while ambiguous candidates (`Deepak Nair`) remain separate entities. Consolidated 103 raw records into **56 canonical person entities** with zero false-positive merges.

---

### 2. Malformed Source 2 Column-Shifted Record

* **Problem**:
  Line 20 of `source2_gig_workers.csv` is structurally malformed. The fields are shifted 1 position to the right: `['react, javascript, mysql', 'ISHA.CHOPRA95@MAILTEST.EXAMPLE.ORG', 'Isha Chopra', '1406/hr', 'Pune', 'active']`. The standard CSV parser places comma-separated skills into the `email_id` field and the email address into the `worker_name` field.

* **What I initially considered**:
  * Hardcoding keyword searches in the email string (e.g. checking if `"react"` or `"python"` appears inside `field[0]`).

* **What I tried**:
  * Implemented an early draft checking `"@" not in email and ("react" in email or "python" in email)`.

* **What failed / was rejected**:
  * **Rejected Domain Keyword Matching**: Hardcoded skill keyword checks were rejected because they introduce fragile vocabulary dependencies. If a future malformed CSV row contained different skill tags (e.g., `'docker, sql'`), keyword detection would fail silently and ingest corrupt data.

* **What I searched or asked AI**:
  * Used AI assistance to explore structural CSV validation techniques for detecting column-shifted rows without domain-specific vocabulary dependencies.

* **Final solution**:
  * Replaced keyword matching with **structural field validation** in `src/ingestion/raw_ingestor.py`:
    * Check if `Field 0` fails email regex validation (`normalize_email(r[0]) == ""`).
    * Check if `Field 1` passes email regex validation (`normalize_email(r[1]) != ""`).
    * If `Field 0` is invalid as an email AND `Field 1` is valid as an email, a **structural column shift** is identified.
    * When detected, log `COLUMN_SHIFT` in `ingestion_quarantine_log` with `resolution_action = 'RE_MAPPED_AND_INGESTED'`.
    * Set `was_malformed = TRUE` and record `recovery_reason` in `raw_source2_gig_workers`.
    * Save the exact verbatim raw unparsed CSV line string in `raw_line_content`.
    * Un-shift fields into proper memory slots (`r[0]` $\rightarrow$ skills, `r[1]` $\rightarrow$ email, `r[2]` $\rightarrow$ name, `r[3]` $\rightarrow$ rate, `r[4]` $\rightarrow$ location, `r[5]` $\rightarrow$ status) for canonical table loading.

* **Why I chose it**:
  * Structural field type validation is completely domain-agnostic and robust, ensuring accurate recovery without relying on hardcoded vocabulary keywords while preserving 100% raw data lineage.

* **How I verified it**:
  * Ran `test_structural_column_shift_and_raw_preservation` in `tests/test_task1.py`. Verified that Line 20 stores `was_malformed = TRUE` in PostgreSQL, saves the verbatim unparsed line, and cleanly extracts candidate `Isha Chopra` with email `isha.chopra95@mailtest.example.org`.

---

### 3. SQLite $\rightarrow$ PostgreSQL Migration + Pipeline Idempotency

* **Problem**:
  The prototype Task 1 implementation used a local SQLite database file (`consultbae.db`). However, downstream workflow engines (n8n in Task 2) and web applications (Task 3) require simultaneous multi-client database access, where SQLite file-locking causes concurrency bottlenecks. Additionally, initial pipeline executions lacked idempotency constraints: running `main.py` twice without dropping tables duplicated records across all database tables (`persons` count doubled from 56 to 112).

* **What I initially considered**:
  * Retaining SQLite and configuring WAL mode (`PRAGMA journal_mode=WAL;`), or forcing table resets (`DROP TABLE`) on every execution.

* **What I tried**:
  * Ran consecutive pipeline executions on the unconstrained prototype schema; confirmed table counts doubled on each run.

* **What failed / was rejected**:
  * **Rejected Destructive Reset**: Forcing `DROP TABLE` on script launch was rejected because real production ETL pipelines must safely re-run over existing production databases idempotently without destroying historical data.

* **What I searched or asked AI**:
  * Used AI assistance to evaluate idempotent SQL upsert patterns (`INSERT ... ON CONFLICT DO UPDATE / DO NOTHING`) for PostgreSQL schema constraints.

* **Final solution**:
  * Migrated database engine to PostgreSQL (hosted on Supabase Managed Postgres Pooler) via [database/schema.sql](file:///Z:/ConsultBae_AI_Automation_Assignment/database/schema.sql).
  * Implemented custom PostgreSQL database connection wrapper in [src/database/connection.py](file:///Z:/ConsultBae_AI_Automation_Assignment/src/database/connection.py) with dynamic environment configuration via `.env`.
  * Added composite `UNIQUE` constraints across the schema:
    * `UNIQUE (source_system, source_file, line_number)` on raw staging tables.
    * `UNIQUE (source_system, source_file, source_line_number)` on `person_source_mappings`.
    * `UNIQUE (person_id, email_address)` on `person_emails`.
    * `UNIQUE (person_id, phone_number)` on `person_phones`.
  * Updated ingestion queries to use `ON CONFLICT (source_system, source_file, line_number) DO UPDATE SET ...` and `resolver.py` to use `ON CONFLICT DO NOTHING`.
  * Added an existing-mapping guardrail check in [src/app/main.py](file:///Z:/ConsultBae_AI_Automation_Assignment/src/app/main.py).

* **Why I chose it**:
  * Provides production-grade concurrency for n8n/web apps while guaranteeing strict ETL pipeline idempotency (Run 1 == Run 2 == Run 3).

* **How I verified it**:
  * Executed 3 consecutive pipeline runs against live Supabase PostgreSQL without `--reset`. Verified via `test_idempotency_consecutive_runs` in `test_task1.py` that database table counts remained 100% stable (56 persons, 103 mappings).

---

### 4. Supabase Connection / Network Choice

* **Problem**:
  Supabase direct database connection strings default to IPv6-oriented network endpoints.

* **What I initially considered**:
  * Purchasing Supabase's paid IPv4 Add-on subscription ($4/month).

* **What I tried**:
  * Evaluated connection options provided in the Supabase management console.

* **What failed / was rejected**:
  * **Rejected Paid IPv4 Add-on**: Paying for the IPv4 add-on was rejected because Supabase provides built-in connection pooler endpoints designed specifically for standard network compatibility at no extra charge.

* **What I searched or asked AI**:
  * Used AI assistance to review Supabase connection pooler configurations and `psycopg2` SSL parameters.

* **Final solution**:
  * Configured connection parameters to use the free Supabase Session Pooler (`aws-0-ap-south-1.pooler.supabase.com:5432`) with `sslmode=require`.
  * Encapsulated connection settings in `.env` loaded dynamically via `python-dotenv` in `src/database/connection.py`.

* **Why I chose it**:
  * Enables zero-cost, reliable database connectivity over standard network connections with SSL transport security.

* **How I verified it**:
  * Verified connection with `psycopg2`, executed `database/schema.sql` DDL, and confirmed successful table creation and live database queries across all 11 catalog tables.

---

### 5. Manual Verification Caught a Bad SQL Query

* **Problem**:
  During manual SQL verification of source lineage, a verification query failed with error `psycopg2.errors.UndefinedColumn: column psm.id does not exist`.

* **What I initially considered**:
  * Assuming the verification script logic was correct and suspecting that table schema creation had failed.

* **What I tried**:
  * Inspected PostgreSQL catalog table schemas using `information_schema.columns`.

* **What failed / was rejected**:
  * **Rejected Retrying Without Inspection**: Re-running the verification query without checking the actual DDL definition was rejected.

* **What I searched or asked AI**:
  * Inspected `database/schema.sql` to verify explicit column names for `person_source_mappings`.

* **Final solution**:
  * Identified that `person_source_mappings` defines its primary key column as `mapping_id`, not `id`.
  * Corrected the manual verification query to use `COUNT(*)` and explicit primary key `mapping_id`.

* **Why I chose it**:
  * Aligning SQL queries with exact catalog schema definitions ensures accurate verification.

* **How I verified it**:
  * Executed corrected query against Supabase PostgreSQL: confirmed that candidates appearing across all 3 source systems (e.g. `Varun Jain`, `person_id = 18`) map back to exactly 3 distinct lineage records in `person_source_mappings`. Demonstrated the critical importance of independent manual verification over trusting unverified automated assumptions.

---

### 6. n8n Postgres Write Node Override (`classification_id = 0`)

* **Problem**:
  During the initial single-candidate Task 2 test run in n8n, the classification row for candidate `person_id = 1` was inserted into Supabase PostgreSQL with `classification_id = 0` instead of starting from `1` via PostgreSQL's `SERIAL` auto-increment sequence.

* **What I initially considered**:
  * Suspecting that the database schema was missing a `SERIAL` sequence default on `classification_id`.

* **What I tried**:
  * Inspected `database/schema.sql` and queried PostgreSQL catalog table definitions using `information_schema.columns` and `information_schema.sequences`. Confirmed that `classification_id` was already defined as `SERIAL PRIMARY KEY` with default `nextval('ai_skill_classifications_classification_id_seq'::regclass)`.

* **What failed / was rejected**:
  * **Rejected Re-creating Database Schema**: Re-executing DDL schema scripts was rejected because catalog inspection proved the sequence was intact.

* **What I searched or asked AI**:
  * Investigated n8n Postgres node column mapping behavior when auto-mapping schema fields.

* **Final solution**:
  * Identified that n8n's Edit Fields / Postgres node automatically included `classification_id: 0` in the SQL `INSERT/UPSERT` payload, overriding PostgreSQL's native `DEFAULT nextval(...)` sequence expression.
  * Explicitly removed `classification_id` from n8n's Edit Fields output and Postgres node mapping configuration, leaving `person_id` as the match key and passing only data attributes (`category`, `confidence`, `reason`, `model`).
  * Updated candidate `person_id = 1`'s record in Supabase to `classification_id = 1` and synchronized sequence `ai_skill_classifications_classification_id_seq` via `setval(...)`.

* **Why I chose it**:
  * Omitting auto-increment primary keys from write payloads lets PostgreSQL manage sequences natively, ensuring reliable sequential IDs across all 56 records without primary key collisions.

* **How I verified it**:
  * Executed upsert queries for Candidate #1 and Candidate #2 without passing `classification_id`. Verified that Candidate #2 automatically received `classification_id = 2`, and subsequent full-batch processing populated all 56 records with clean sequential IDs (`1..56`).

---

### 7. Google Gemini API Rate-Limiting (HTTP 429)

* **Problem**:
  When attempting to send all unclassified candidate skills through the Gemini Chat Model node in batch mode, the workflow failed with HTTP 429 / Rate Limit Exceeded errors from Google Gemini's free-tier endpoint.

* **What I initially considered**:
  * Sending the entire candidate list in a single large prompt, or increasing execution concurrency.

* **What I tried**:
  * Executed the workflow without concurrency throttling; received API rate limit rejections after the first few candidate items.

* **What failed / was rejected**:
  * **Rejected Single-Prompt Mega Batching**: Sending all candidate skills in a single prompt was rejected because combining 56 candidates reduces classification accuracy, risks context truncation, and fails structured output validation per candidate.

* **What I searched or asked AI**:
  * Evaluated n8n flow-control constructs for rate-limiting LangChain LLM nodes.

* **Final solution**:
  * Redesigned the workflow by introducing a **Loop Over Items** (`splitInBatches` node with batch size = 1) combined with a **Wait** node (1-second delay between loop iterations).
  * Candidate records are fetched from SQL, iterated serially item-by-item, passed to the Gemini chain, written back to PostgreSQL, and paused briefly before iterating to the next candidate.

* **Why I chose it**:
  * Preserves full no-code architecture while enforcing controlled request rates, adhering strictly to Gemini API rate limits.

* **How I verified it**:
  * Ran the full 56-candidate workflow in local n8n. All 56 candidates were processed sequentially with 0 rate-limit rejections and written to Supabase `ai_skill_classifications`.

---

### 8. Manual Verification vs. Trusting Workflow Automation

* **Problem**:
  No-code workflow tools (like n8n) can visually display a green "Success" execution badge even if individual data fields inside the write payload contain logical errors (e.g., `classification_id = 0` or missing timestamps).

* **What I initially considered**:
  * Relying solely on n8n's visual node completion indicators to declare Task 2 completed.

* **What I tried**:
  * Checked n8n execution log UI, which showed successful node completions.

* **What failed / was rejected**:
  * **Rejected Relying Only on Node Status**: Assuming database correctness based on UI success badges was rejected because UI indicators confirm execution completion, not data accuracy.

* **What I searched or asked AI**:
  * Formulated SQL validation suites to audit downstream PostgreSQL table state directly via `psycopg2`.

* **Final solution**:
  * Created an independent Python/SQL database verification suite (`verify_phase2.py`) querying Supabase directly after workflow completion to validate row counts, unique constraints, distinct categories, null field checks, and primary key sequence ranges.

* **Why I chose it**:
  * Independent database inspection provides empirical proof of correctness and caught the `classification_id = 0` issue before full-batch execution.

* **How I verified it**:
  * Ran SQL verification queries confirming 56 total rows, 0 duplicate candidate IDs, 0 null essential fields, 100% valid categories, and sequence alignment (`min=1`, `max=56`).

---

### 9. Audio Decibel Extraction (`dBFS`) for Silent / Low-Volume Clips

* **Problem**:
  When processing silent or extremely low-amplitude audio files with `pydub`, `audio_segment.dBFS` evaluates to `-inf` (negative infinity), which causes PostgreSQL floating-point schema insertion errors or invalid JSON values in web views.

* **What I initially considered**:
  * Leaving loudness values unhandled or letting `math.isinf()` throw an unhandled exception.

* **What I tried**:
  * Tested metadata extraction on silent WAV buffers; confirmed `-inf` values caused database constraint issues.

* **What failed / was rejected**:
  * **Rejected Storing NaN / Inf**: Inserting `NaN` or `-inf` directly into relational numeric columns was rejected because standard PostgreSQL numeric types and JSON serializers reject non-finite floating-point representations.

* **What I searched or asked AI**:
  * Evaluated AudioSegment decibel normalization handling for zero-amplitude digital signals.

* **Final solution**:
  * Implemented an explicit decibel floor check in `src/audio/extractor.py`: if `math.isinf(loudness_db)` or `math.isnan(loudness_db)`, default `loudness_db = -99.0`. An application-level -99 dBFS floor is used to keep non-finite loudness values out of the database and UI.

* **Why I chose it**:
  * Guarantees safe numeric range values for PostgreSQL schema validation and Streamlit frontend UI components.

* **How I verified it**:
  * Executed unit tests in `tests/test_task3_audio.py` against synthetic wave buffers and verified clean float representation (-17.15 dBFS) without overflow errors.

---

### 10. Compensating Disk Cleanup on Database Insert Failure

* **Problem**:
  If a user uploads a valid audio file that passes metadata extraction, the application writes the file to disk (`data/audio_uploads/`) *before* executing the PostgreSQL `INSERT` transaction. If the database transaction fails (e.g. database network disruption or foreign key constraint error), the audio file remains on disk as an orphaned file.

* **What I initially considered**:
  * Writing to the database first before saving the file to disk.

* **What I tried**:
  * Writing to the database first required knowing the final file path in advance, but generating a safe file path after DB insertion leads to secondary update queries.

* **What failed / was rejected**:
  * **Rejected Leaving Orphaned Disk Files**: Allowing files to remain on disk when database writes fail causes disk leakage and broken data lineage.

* **What I searched or asked AI**:
  * Evaluated cleanup guardrails for disk file operations accompanying relational database transactions.

* **Final solution**:
  * Wrapped the database insertion in a `try...except` block in `src/audio/extractor.py`. If `conn.execute()` or `conn.commit()` raises an exception, the handler issues `conn.rollback()` and deletes the newly created audio file from disk (`os.remove(file_path)`). This provides compensating cleanup so failed database writes do not normally leave orphaned audio files.

* **Why I chose it**:
  * Reduces filesystem pollution by removing unreferenced temporary audio uploads when database operations fail.

* **How I verified it**:
  * Executed unit test `test_process_and_store_submission_db_failure_cleanup` in `tests/test_task3_audio.py`, simulating a database foreign-key violation and verifying that temporary audio files are cleanly deleted from `data/audio_uploads/`.
