# ConsultBae — AI Automation Take-Home Assignment

An AI automation repository merging candidate data across disparate systems, resolving candidate identities without common keys, handling data quality anomalies with complete source lineage, and building downstream automation workflows.

---

## Assignment Tasks & Implementation Status

*(Authoritative Reference: `assignment/ConsultBae_Assignment_Rulebook.pdf`)*

| Task | Title | Core / Optional | Status | Key Deliverables / Artifacts |
| :-: | :--- | :-: | :-: | :--- |
| **Task 1** | **Merge** | **Core** | **COMPLETED** | PostgreSQL schema ([database/schema.sql](file:///Z:/ConsultBae_AI_Automation_Assignment/database/schema.sql)), Ingestion & Normalization pipeline ([src/ingestion/](file:///Z:/ConsultBae_AI_Automation_Assignment/src/ingestion/)), 3-Tier Entity Resolution engine ([src/matching/](file:///Z:/ConsultBae_AI_Automation_Assignment/src/matching/)), automated test suite ([tests/test_task1.py](file:///Z:/ConsultBae_AI_Automation_Assignment/tests/test_task1.py)). |
| **Task 2** | **Automate with a no-code/low-code tool** | **Core** | **COMPLETED** | n8n workflow JSON export in [n8n/candidate_skill_autotagging_flow.json](file:///Z:/ConsultBae_AI_Automation_Assignment/n8n/candidate_skill_autotagging_flow.json) & auto-classified PostgreSQL database results (`ai_skill_classifications`). |
| **Task 3** | **Mini audio collection app** | **Core** | **COMPLETED** | Streamlit web app ([src/audio/app.py](file:///Z:/ConsultBae_AI_Automation_Assignment/src/audio/app.py)), metadata extractor ([src/audio/extractor.py](file:///Z:/ConsultBae_AI_Automation_Assignment/src/audio/extractor.py)), PostgreSQL table (`audio_submissions`), and test suite ([tests/test_task3_audio.py](file:///Z:/ConsultBae_AI_Automation_Assignment/tests/test_task3_audio.py)). |
| **Task 4** | **Data issues report** | **Core** | **COMPLETED** | Complete report embedded in [README.md](#data-issues-report) below. |
| **Task 5** | **Stretch** | **Optional** | **COMPLETED** | 1-page architectural scaling analysis ([README.md#task-5--stretch-scaling-to-5000-workers](#task-5--stretch-scaling-to-5000-workers)). |

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

## Task 2 — Automate with a No-Code/Low-Code Tool

### 1. Objective
Automate downstream candidate processing by integrating PostgreSQL canonical candidate data with an AI model via a no-code/low-code workflow engine. Unclassified candidates and their aggregated skills are evaluated by an LLM to automatically categorize candidate profiles into standardized engineering categories and write results back to PostgreSQL.

### 2. Why n8n Was Chosen
n8n was selected as the automation platform because it is open-source, self-hostable, natively supports complex database nodes (PostgreSQL with parameter mapping & upsert logic), features native LangChain nodes (LLM chains, Gemini chat models, structured JSON output parsers), and supports flow control constructs (`Loop Over Items` and `Wait` nodes) required for API rate-limit management.

### 3. High-Level Workflow Architecture
```
[Schedule Trigger]
       ↓
[Postgres: Execute Query]  ── Fetches unclassified candidates & aggregated skills
       ↓
[Loop Over Items]          ── Processes candidates item-by-item (batch size = 1)
       ↓
[Basic LLM Chain]          ── Sends candidate skills prompt to Gemini Chat Model
   ├── Google Gemini Chat Model
   └── Structured Output Parser
       ↓
[Edit Fields]              ── Formats person_id, category, confidence, reason, model
       ↓
[Postgres: Insert or Update] ── Upserts into ai_skill_classifications (match key: person_id)
       ↓
[Wait]                     ── 1-second rate-limiting delay per candidate
       ↓
(Loops back to Loop Over Items until all items processed)
```

### 4. Node-by-Node Explanation
1. **Schedule Trigger**: Triggers execution automatically (or manually on demand).
2. **Execute a SQL Query (Postgres Node)**: Aggregates skills per canonical candidate using `STRING_AGG(DISTINCT cs.skill_name, ', ')` where `ai_skill_classifications.person_id IS NULL`.
3. **Loop Over Items (SplitInBatches Node)**: Iterates over candidate records one at a time to prevent API rate spikes.
4. **Basic LLM Chain (LangChain Node)**: Constructs prompt passing candidate name and skill list.
5. **Google Gemini Chat Model (LM Node)**: Connects to `models/gemini-3.5-flash-lite` (or equivalent Gemini model) via Google PaLM API.
6. **Structured Output Parser (LangChain Node)**: Enforces JSON schema response format matching `{category, confidence, reason}`.
7. **Edit Fields (Set Node)**: Maps original candidate `person_id` from the SQL query node together with LLM output attributes (`category`, `confidence`, `reason`) and sets `model = 'Gemini'`.
8. **Insert or Update Rows in a Table (Postgres Node)**: Executes an upsert into table `ai_skill_classifications` matching on `person_id`. `classification_id` is excluded from the node mapping so PostgreSQL's native `SERIAL` sequence automatically generates sequential primary keys (`1..56`).
9. **Wait Node**: Introduces a controlled delay between item iterations to adhere to Google Gemini API free-tier RPM rate limits.

### 5. Gemini Classification Categories
Candidates are classified into exactly one of seven permitted categories:
* `automation-heavy`
* `web-dev`
* `data`
* `backend`
* `ai-ml`
* `full-stack`
* `other`

### 6. Structured Output & Explainability Note
The structured JSON output extracted from Gemini includes:
* `category`: Exact string matching one of the 7 allowed categories.
* `confidence`: Model-reported confidence score between 0.0 and 1.0. *(Note: Confidence and reason fields were intentionally added as engineering enhancements for model explainability and auditability; they were not explicitly required by the assignment rulebook. Confidence represents a model-reported rating, not a statistically calibrated probability).*
* `reason`: Concise natural language explanation of why the category was assigned based on candidate skills.

### 7. PostgreSQL Write-Back & Upsert Behavior
Results are written back into table `ai_skill_classifications`. The Postgres node is configured with **Insert or Update** mode on matching column `person_id`. This ensures idempotency: re-running the workflow updates existing classifications without duplicating rows. `classification_id` is auto-generated by PostgreSQL's `SERIAL` sequence, and timestamps (`created_at`, `updated_at`) are automatically set by PostgreSQL default expressions.

### 8. Rate-Limit Handling
Initial batch execution triggered HTTP 429 / Rate Limit errors from the Gemini API when processing many candidates simultaneously. To resolve this, the workflow was structured using `Loop Over Items` paired with a `Wait` node. This guarantees serial, single-candidate requests spaced apart, ensuring 100% completion without API throttling failures.

### 9. Verification & Execution Results
* **Total Candidates Classified**: All **56 canonical person profiles** successfully processed.
* **Database State**: `SELECT COUNT(*) FROM ai_skill_classifications;` = `56`.
* **Integrity**: `0` duplicate `person_id` records, `0` null values in essential fields (`person_id`, `category`, `model`), `56` distinct auto-incremented `classification_id` values (`1..56`).

### 10. Workflow Export Location
The complete n8n workflow export is committed in the repository at:
[n8n/candidate_skill_autotagging_flow.json](file:///z:/ConsultBae_AI_Automation_Assignment/n8n/candidate_skill_autotagging_flow.json)

### 11. Import & Setup Instructions
1. Open local or hosted n8n instance (`http://localhost:5678`).
2. Select **Workflows** $\rightarrow$ **Import from File** and select `n8n/candidate_skill_autotagging_flow.json`.
3. Configure credentials:
   * **Postgres Account**: Set host, port, database name, user, password, and SSL (`require`).
   * **Google Gemini API Account**: Set Google Gemini API key.
4. Execute workflow.

> [!IMPORTANT]
> **Credential Security**: All credential identifiers in `candidate_skill_autotagging_flow.json` are sanitized local references. Real database credentials and Gemini API keys must be configured inside your local n8n instance and are never committed to Git.

---

## Task 3 — Mini Audio Collection App

### 1. Objective
Build a web application enabling gig workers to submit audio recordings (via file upload or browser recording), link submissions directly to the canonical candidate database from Task 1 via phone identity lookup, automatically analyze and store acoustic metadata properties (duration, sample rate, bitrate, loudness), and provide a gallery view with inline browser audio playback.

### 2. Architecture & Technology Stack
* **UI Framework**: **Streamlit** ([`src/audio/app.py`](file:///Z:/ConsultBae_AI_Automation_Assignment/src/audio/app.py)) providing dual-tab form and gallery views.
* **Audio Extraction Engine**: **`pydub`** ([`src/audio/extractor.py`](file:///Z:/ConsultBae_AI_Automation_Assignment/src/audio/extractor.py)) analyzing uncompressed and compressed audio streams (`.wav`, `.mp3`, `.m4a`, `.ogg`, `.webm`, `.flac`, `.aac`).
* **Database & Identity Linkage**: PostgreSQL table `audio_submissions` linked to canonical candidate table `persons` via FOREIGN KEY (`person_id`).
* **File Storage**: Local filesystem storage in `data/audio_uploads/` with UUID timestamped filenames (`audio_{person_id}_{YYYYMMDDTHHMMSS}_{uuid[:8]}.ext`). `data/audio_uploads/` is tracked in `.gitignore` to prevent committing user audio files.

### 3. Database Schema (`audio_submissions`)
Defined in [`database/schema.sql`](file:///Z:/ConsultBae_AI_Automation_Assignment/database/schema.sql#L164-L177):
```sql
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
```

### 4. Canonical Identity Resolution & Validation Rules
1. **Normalization & Identity Lookup**: Candidate name is normalized and checked that it is non-empty; candidate phone is normalized using `normalize_phone()` (extracting clean 10-digit string). Existing candidates are resolved primarily by normalized phone number.
2. **Identity Lookup**: Searches `person_phones` and `persons` tables for existing canonical candidate matching the normalized phone number.
3. **Guardrails**:
   * If **0 candidates match**: Shows validation error `"Candidate not found for phone number 'X'. Please verify the phone number."`
   * If **>1 candidates match**: Shows ambiguity error preventing corrupted identity merges.
   * If **1 candidate matches**: Obtains `person_id` and links submission.
4. **Compensating Disk Cleanup**: If database insertion fails after saving the file to disk, the application provides compensating cleanup by deleting the newly created audio file from `data/audio_uploads/` so failed database writes do not normally leave orphaned audio files.

### 5. Automated Audio Metadata Extraction
For every submission, `extract_audio_metadata()` decodes the audio stream and computes:
* **Duration (seconds)**: `round(len(audio_segment) / 1000.0, 3)`
* **Sample Rate (kHz)**: `round(audio_segment.frame_rate / 1000.0, 2)`
* **Bitrate (kbps)**: `round((file_size_bytes * 8.0) / duration_seconds / 1000.0, 2)`
* **Loudness (dBFS)**: `round(audio_segment.dBFS, 2)`. An application-level -99 dBFS floor is used to keep non-finite loudness values out of the database and UI.

### 6. Application Views
* **View 1 — Submit Audio (`📤 Submit Audio`)**:
  * Fields: Candidate Name, Phone Number, Audio File Upload / Browser Recording.
  * Workflow: Validates fields $\rightarrow$ normalizes phone $\rightarrow$ looks up candidate $\rightarrow$ decodes audio $\rightarrow$ extracts metadata $\rightarrow$ writes file & DB record $\rightarrow$ renders metric summary cards.
* **View 2 — Submissions Gallery (`🎧 Submissions Gallery`)**:
  * Displays latest submissions first with Candidate Name, Phone, Submission Timestamp, and metric cards.
  * Includes an inline Streamlit browser audio player (`st.audio`) for instant playback of stored media.

### 7. How to Launch the Web Application
To run the Streamlit audio application locally:
```bash
streamlit run src/audio/app.py
```
App will open in your browser at `http://localhost:8501`.

### 8. Automated & Manual Verification Results
* **Automated Tests**: 9 dedicated unit and integration tests in [`tests/test_task3_audio.py`](file:///Z:/ConsultBae_AI_Automation_Assignment/tests/test_task3_audio.py) testing WAV metadata extraction, duration/sample rate/bitrate/loudness accuracy, corrupt file rejection, size limit enforcement, candidate lookup, DB insertion, and compensating disk cleanup on DB failure.
* **End-to-End Manual Verification**: Verified end-to-end in live Streamlit browser UI (`http://localhost:8501`) with candidate `Varun Jain` (`9000000263`, `person_id = 18`):
  * **Input & Identity Resolution**: Verified candidate Name and Phone input; successfully resolved existing candidate `person_id = 18`.
  * **File Upload Test**: Verified uploading external `.wav` and `.mp3` audio files.
  * **Native Browser Recording Test**: Verified capturing live audio via native browser audio recorder widget (`st.audio_input`).
  * **Acoustic Property Extraction**: Extracted and verified Duration (2.5s), Sample Rate (44.1 kHz), Bitrate (705.74 kbps), and Loudness (-17.15 dBFS).
  * **File Storage**: Verified media files saved safely in `data/audio_uploads/audio_18_{timestamp}_{uuid}.wav`.
  * **Database Persistence**: Verified Supabase PostgreSQL database insertion in `audio_submissions`.
  * **Gallery & Playback Test**: Verified Submissions Gallery view renders stored candidate submissions with inline browser audio player (`st.audio`) playback, displaying complete metadata and handling multiple submissions per candidate.

---

# Data Issues Report

While working with the three source files, I found several problems in the data. I cleaned, corrected, or safely handled these problems before using the data for matching and storing it in the database.

## 1. Blank row

**Issue:** One row in the gig-worker file was completely empty.

**How I handled it:** I ignored the empty row and recorded it in the quarantine log instead of putting it into the database.

## 2. Duplicate header in the middle of the file

**Issue:** The third source file had another header row in the middle of the actual data.

**How I handled it:** I detected that row as a duplicate header, removed it from the actual data, and recorded it in the quarantine log.

## 3. One row had its columns shifted

**Issue:** One gig-worker record had its values in the wrong columns. For example, the skills were where the email should have been, and the email was where the name should have been.

**How I handled it:** I detected the problem by checking whether the values matched the expected type of each column. I recovered the row by moving the values back into the correct positions, while also keeping the original row for traceability.

## 4. Different salary formats

**Issue:** Salary values in the Naukri file were not stored in the same format. Some were given as LPA, while another value was given as an annual amount in rupees.

**How I handled it:** I converted all salary values into the same LPA format before storing them.

## 5. Different payment rate formats

**Issue:** Gig-worker rates were written in different ways, such as hourly rates and monthly rates.

**How I handled it:** I separated them into different fields for hourly and monthly rates so they could be stored and compared correctly.

## 6. Different date formats

**Issue:** Dates were written in several different formats, such as `2026-08-08`, `24-07-2026`, `07/13/2026`, and `7 Jul 2026`.

**How I handled it:** I converted all dates into one standard date format before storing them.

## 7. Different phone number formats

**Issue:** The same type of phone number appeared in different formats, for example with `+91`, `91`, a leading `0`, or hyphens.

**How I handled it:** I removed the extra formatting and converted the numbers into a standard 10-digit format. I then used that cleaned phone number for matching people across sources.

## 8. Different city names and formats

**Issue:** City names were written with different capitalization, extra spaces, or different names for the same place, such as Gurgaon/Gurugram and Bangalore/Bengaluru.

**How I handled it:** I mapped these variations to one standard city name before using the data.

## 9. Different email formats

**Issue:** Some email addresses were written in uppercase or had extra spaces.

**How I handled it:** I removed extra spaces and converted emails to lowercase so that the same email could be matched correctly.

## 10. Different ways of writing categories and status values

**Issue:** Some fields used different values for the same meaning, such as `Y`, `yes`, `Verified`, or `true`.

**How I handled it:** I converted these values into a common format, such as a proper true/false value, and standardized status text.

## 11. Same person written with a short name and full name

**Issue:** One record used `R. Verma`, while another record used `Rohit Verma`.

**How I handled it:** Instead of depending on the name, I used the matching email address to identify that both records belonged to the same person.

## 12. Same person had two different email addresses

**Issue:** Nikhil Chopra appeared with two different email addresses, but the phone number and other details showed that both records belonged to the same person.

**How I handled it:** I used the normalized phone number to connect the two records to one person and kept both email addresses in the database.

## 13. Two different people had the same name

**Issue:** There were two candidates named Deepak Nair, but their other details were different. Automatically merging them just because their names were the same could create a wrong person record.

**How I handled it:** I did not merge them. When the other identifying information conflicted, I kept them as separate people and recorded the conflict for review.

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

### Challenge 4: n8n Postgres Write Node Override (`classification_id = 0`)
* **Problem**: During the initial single-candidate Task 2 test run in n8n, candidate `person_id = 1` was inserted into Supabase PostgreSQL with `classification_id = 0` instead of starting from `1` via PostgreSQL's `SERIAL` sequence.
* **What I Tried**:
  * Inspected `database/schema.sql` and PostgreSQL catalog via `information_schema.columns` / `sequences` to check if `classification_id` was missing default sequence expressions. Confirmed `classification_id` was correctly defined as `SERIAL PRIMARY KEY`.
* **What I Searched / Asked AI**:
  * Investigated n8n Postgres node payload field mapping behavior when auto-mapping table schemas.
* **What Worked**:
  * Identified that n8n's Edit Fields / Postgres node automatically included `classification_id: 0` in the write payload, overriding PostgreSQL's `DEFAULT nextval(...)` sequence.
  * Removed `classification_id` from n8n's Edit Fields output and Postgres node mapping configuration, leaving `person_id` as the match key and passing only data attributes (`category`, `confidence`, `reason`, `model`).
  * Corrected candidate `person_id = 1`'s record in Supabase to `classification_id = 1` and synchronized sequence `ai_skill_classifications_classification_id_seq` via `setval(...)`.
* **What I Rejected & Why**:
  * Rejected re-executing DDL schema scripts because catalog inspection proved the schema sequence was already intact.
* **Final Result**: Omitting `classification_id` from write payloads allowed PostgreSQL to manage sequences natively, ensuring reliable sequential IDs across all 56 records (`1..56`).

---

### Challenge 5: Google Gemini API Rate-Limiting (HTTP 429)
* **Problem**: Sending all unclassified candidate skills through the Gemini Chat Model node in batch mode triggered HTTP 429 / Rate Limit Exceeded errors from Google Gemini's free-tier endpoint.
* **What I Tried**:
  * Executed the workflow without concurrency throttling; received API rate limit rejections after the first few candidate items.
* **What I Searched / Asked AI**:
  * Evaluated n8n flow-control constructs for rate-limiting LangChain LLM nodes.
* **What Worked**:
  * Redesigned the workflow by introducing a **Loop Over Items** (`splitInBatches` node with batch size = 1) combined with a **Wait** node (1-second delay between loop iterations).
  * Candidate records are fetched from SQL, iterated serially item-by-item, passed to Gemini, written back to PostgreSQL, and paused briefly before iterating to the next candidate.
* **What I Rejected & Why**:
  * Rejected single-prompt mega-batching (combining all 56 candidates into one prompt) because it reduces classification precision, risks context truncation, and fails structured output validation per candidate.
* **Final Result**: All 56 candidates were processed sequentially with 0 rate-limit rejections and written to Supabase `ai_skill_classifications`.

---

### Challenge 6: Manual Verification vs. Trusting Workflow Automation
* **Problem**: No-code workflow tools (like n8n) can visually display a green "Success" execution badge even if individual data fields inside the write payload contain logical errors (e.g., `classification_id = 0` or missing timestamps).
* **What I Tried**:
  * Inspected n8n execution log UI, which showed successful node completions.
* **What I Searched / Asked AI**:
  * Formulated SQL validation queries to audit downstream PostgreSQL table state directly via `psycopg2`.
* **What Worked**:
  * Created an independent Python/SQL database verification suite (`verify_phase2.py`) querying Supabase directly after workflow completion to validate row counts, unique constraints, distinct categories, null field checks, and primary key sequence ranges.
* **What I Rejected & Why**:
  * Rejected relying solely on UI completion badges because UI indicators confirm execution status, not data payload correctness.
* **Final Result**: Independent database inspection provided empirical proof of correctness and caught the `classification_id = 0` issue before full-batch execution.

---

### Challenge 7: Audio Decibel Extraction (`dBFS`) for Silent / Low-Volume Clips
* **Problem**: When processing silent or low-amplitude audio files with `pydub`, `audio_segment.dBFS` evaluates to `-inf` (negative infinity), causing PostgreSQL schema floating-point insert errors or invalid JSON values in web views.
* **What I Tried**: Tested metadata extraction on silent WAV buffers; confirmed `-inf` values caused database insertion failures.
* **What I Searched / Asked AI**: Evaluated AudioSegment decibel normalization handling for zero-amplitude digital signals.
* **What Worked**: Implemented an explicit decibel floor check in `src/audio/extractor.py`: if `math.isinf(loudness_db)` or `math.isnan(loudness_db)`, default `loudness_db = -99.0`. An application-level -99 dBFS floor is used to keep non-finite loudness values out of the database and UI.
* **What I Rejected & Why**: Rejected storing `NaN` or `-inf` directly into relational numeric columns because standard PostgreSQL numeric types and JSON serializers reject non-finite floating-point representations.
* **Final Result**: Guarantees safe numeric range values for PostgreSQL schema validation and Streamlit frontend UI components.

---

### Challenge 8: Compensating Disk Cleanup on Database Insert Failure
* **Problem**: If a user uploads a valid audio file that passes metadata extraction, the application writes the file to disk (`data/audio_uploads/`) *before* executing the PostgreSQL `INSERT` transaction. If the database transaction fails, the audio file remains on disk as an orphaned file.
* **What I Tried**: Considered writing to the database first before saving the file to disk, but generating a safe file path after DB insertion leads to secondary update queries.
* **What I Searched / Asked AI**: Evaluated cleanup guardrails for disk file operations accompanying relational database transactions.
* **What Worked**: Wrapped the database insertion in a `try...except` block in `src/audio/extractor.py`. If `conn.execute()` or `conn.commit()` raises an exception, the handler issues `conn.rollback()` and deletes the newly created audio file from disk (`os.remove(file_path)`). This provides compensating cleanup so failed database writes do not normally leave orphaned audio files.
* **What I Rejected & Why**: Rejected leaving orphaned disk files when database writes fail because it causes disk leakage and broken data lineage.
* **Final Result**: Reduces filesystem pollution by removing unreferenced temporary audio uploads when database operations fail. Automated test `test_process_and_store_submission_db_failure_cleanup` in `tests/test_task3_audio.py` simulates database failure and verifies temporary file cleanup.

---

## Task 5 — Stretch: Scaling to 5,000 Workers

1. Storage

What will break:
The current app stores audio files on the local computer. This will not work well when thousands of workers are uploading files because the storage can fill up and files can be lost if the server goes down.

What I would do before launch:
Move audio files to cloud storage such as Amazon S3 or Supabase Storage. Keep only the file path and other details in PostgreSQL.

2. Uploads

What will break:
Thousands of workers may try to upload audio at the same time. Sending all those files through the application server can make the app slow or unavailable.

What I would do before launch:
Let workers upload the audio directly to cloud storage and use resumable uploads so a failed upload can continue instead of starting again.

3. Audio Processing

What will break:
Processing thousands of audio files at the same time can use a lot of CPU and memory and can slow down the application.

What I would do before launch:
Move audio processing to background workers. The main application should accept the upload quickly and let background workers calculate the audio properties.

4. Failures

What will break:
Some uploads, database operations, or audio processing jobs will fail because of network problems or temporary service failures.

What I would do before launch:
Add retries and a way to record failed jobs so they can be checked and processed again without losing submissions.

5. Duplicate Submissions

What will break:
A worker may press the submit button twice or the browser may retry the same request. This can create duplicate submissions.

What I would do before launch:
Use a unique submission ID or idempotency key so the same submission cannot be saved more than once.

6. Database Load

What will break:
Thousands of submissions can create many database connections and increase the load on PostgreSQL.

What I would do before launch:
Use connection pooling and make sure the database is sized for the expected number of workers and requests.

7. Cost

What will break:
Large audio files, storage, processing and data transfer can become expensive at higher usage.

What I would do before launch:
Use compressed audio where appropriate, apply storage lifecycle rules, and monitor storage, processing and bandwidth costs.
---

## Submission Checklist

- [x] **GitHub repository** with incremental commit history
- [x] **README.md** with setup guide + Data Issues Report + Stuck Log + Task 5 Scaling Write-Up
- [x] **Task 2 n8n workflow JSON** exported into repo ([`n8n/candidate_skill_autotagging_flow.json`](file:///z:/ConsultBae_AI_Automation_Assignment/n8n/candidate_skill_autotagging_flow.json))
- [ ] **Screen recording** ($\le$ 6 minutes, voice required, face optional)
- [ ] **Final email reply** containing repository link + video link before deadline
