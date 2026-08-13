# ConsultBae — AI Automation Assignment

An AI automation pipeline and web application designed to merge candidate data across disparate source systems, automate skill tagging using AI, and collect gig worker audio submissions.

---

## Assignment Tasks & Overview

| Task | Title | Status | Deliverables |
| :-: | :--- | :-: | :--- |
| **Task 1** | **Merge & Data Normalization** | **COMPLETED** | PostgreSQL schema DDL, Python ingestion & normalization pipeline, tiered entity resolution, unit test suite. |
| **Task 2** | **No-Code AI Automation** | **COMPLETED** | n8n workflow export ([`n8n/candidate_skill_autotagging_flow.json`](n8n/candidate_skill_autotagging_flow.json)) & auto-classified candidate skill database records. |
| **Task 3** | **Mini Audio Collection App** | **COMPLETED** | Streamlit web application ([`src/audio/app.py`](src/audio/app.py)), metadata extractor ([`src/audio/extractor.py`](src/audio/extractor.py)), `audio_submissions` database table, and unit test suite. |
| **Task 4** | **Data Issues Report** | **COMPLETED** | Complete 13-item data quality analysis embedded in [Data Issues Report](#data-issues-report) below. |
| **Task 5** | **Stretch Architecture Exercise** | **COMPLETED** | 1-page scaling analysis for 5,000 workers embedded in [Task 5 — Stretch](#task-5--stretch-scaling-to-5000-workers) below. |

---

## Quick Start & Setup Guide

### Prerequisites
* Python 3.10+
* PostgreSQL database instance (local PostgreSQL or cloud Supabase instance)

### 1. Installation
```bash
# Clone the repository
git clone https://github.com/kripa123456789/ConsultBae_AI_Automation_Assignment.git
cd ConsultBae_AI_Automation_Assignment

# Create and activate virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1  # On Windows PowerShell
# source .venv/bin/activate   # On Linux/macOS

# Install dependencies
pip install -r requirements.txt
```

### 2. Environment Configuration
Copy `.env.example` to `.env` and fill in your PostgreSQL credentials:
```bash
cp .env.example .env
```

Ensure your `.env` contains:
```env
POSTGRES_HOST=your_postgres_host
POSTGRES_PORT=5432
POSTGRES_DB=postgres
POSTGRES_USER=your_user
POSTGRES_PASSWORD=your_password
POSTGRES_SSLMODE=require
```

### 3. Run Pipeline & Verify Tests
```bash
# Run Task 1 database initialization and data merging pipeline
python -m src.app.main --reset

# Run all 27 automated unit and integration tests
python -m pytest

# Run Task 3 Streamlit audio collection web app
streamlit run src/audio/app.py
```

---

## Task 1 — Data Ingestion & Entity Resolution

### Objective
Combine candidate records from three distinct CSV source files (`source1_naukri_applicants.csv`, `source2_gig_workers.csv`, `source3_cbnexus_contacts.csv`) into a single canonical PostgreSQL database.

### Implementation Summary
* **Data Cleaning & Normalization**: Standardized mixed date formats, phone numbers (to clean 10-digit strings), email addresses (lowercased), salaries (converted to LPA), gig rates (separated into hourly and monthly fields), and city names.
* **Structural Recovery**: Detected and fixed a column-shifted row in the gig worker file while preserving original raw line data in staging tables.
* **Tiered Entity Resolution**: Linked records across systems without a common global ID using a priority hierarchy:
  1. *Tier 1A*: Direct email match.
  2. *Tier 1B*: Direct phone match.
  3. *Tier 2*: Name + City match.
  4. *Tier 3 Guardrail*: Safety checks to prevent merging different candidates who happen to share the same name.
* **Results**: Successfully consolidated **103 raw source records into 56 canonical candidate profiles** in PostgreSQL with complete source lineage preserved.

---

## Task 2 — No-Code Skill Tagging Automation (n8n)

### Objective
Automatically analyze candidate skills stored in PostgreSQL and classify each candidate into standard engineering categories using an AI model within a no-code/low-code workflow.

### Implementation Summary
* **Platform**: Built using **n8n** connected to Google Gemini LLM and PostgreSQL.
* **Workflow Logic**: Reads unclassified candidate skills from PostgreSQL, passes them to Gemini via a structured JSON output prompt, extracts the category, confidence rating, and explanation, and writes the results back to the database.
* **Categories**: Classifies profiles into 7 categories: `backend`, `web-dev`, `full-stack`, `data`, `ai-ml`, `automation-heavy`, or `other`.
* **Rate Limiting**: Used an n8n loop with a 5-second delay between items to adhere to API rate limits without failing requests.
* **Results**: Successfully classified all **56 canonical candidates** into table `ai_skill_classifications`. The complete exported workflow is saved at [`n8n/candidate_skill_autotagging_flow.json`](n8n/candidate_skill_autotagging_flow.json).

---

## Task 3 — Mini Audio Collection Web App

### Objective
Create a simple web interface allowing gig workers to submit audio recordings, automatically link submissions to existing candidates, extract key audio properties, and display submissions in a playback gallery.

### Implementation Summary
* **Frontend UI**: Built with **Streamlit** (`src/audio/app.py`) featuring two views:
  1. *Submit Audio*: Candidate enters name and phone number, then uploads an audio file (`.wav`, `.mp3`, `.m4a`, etc.) or records live audio directly in the browser.
  2. *Submissions Gallery*: Displays recorded submissions with metadata cards and an inline audio player for instant playback.
* **Candidate Matching**: Automatically matches candidate phone numbers against the Task 1 canonical database to link the submission to the correct `person_id`.
* **Metadata Extraction**: Extracted four key audio properties using Python (`pydub`):
  * **Duration** (seconds)
  * **Sample Rate** (kHz)
  * **Bitrate** (kbps)
  * **Loudness** (dBFS)
* **Storage & Persistence**: Saved audio files locally in `data/audio_uploads/` for this take-home demo and saved metadata records in PostgreSQL table `audio_submissions`.
* **Verification**: Verified via 9 unit tests in `tests/test_task3_audio.py` and manually tested end-to-end in the live Streamlit browser UI.

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

### 1. Matching the Same Person Without a Common ID

- **Where I got stuck:** The three files did not have one common ID, so I was not sure how to identify the same person across different files without creating wrong matches.
- **How I got unstuck:** I asked AI about practical record-matching approaches and compared the options with the actual data. I rejected name-only matching because the same name can belong to different people, and used email and phone first, with name and city only as a weaker match.

### 2. Finding and Recovering the Broken Row

- **Where I got stuck:** One row in the gig-worker file had its values in the wrong columns, so the data could not be read normally.
- **How I got unstuck:** I asked AI about ways to detect a shifted CSV row without depending on fixed skill names. I rejected hardcoded keyword checks and used the expected format of each field to detect the shift, then moved the values back to the correct columns while keeping the original row.

### 3. Handling the Gemini Rate Limit in n8n

- **Where I got stuck:** When I tried to process many candidates through Gemini, the workflow started returning rate-limit errors.
- **How I got unstuck:** I checked n8n's flow-control options and asked AI for ways to handle rate limits without using custom code. I rejected sending all candidates in one large request and used one-candidate-at-a-time processing with a short wait between requests.

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

- [x] **GitHub repository** with clean commit history
- [x] **README.md** with setup guide, Data Issues Report, Stuck Log, and Task 5 Scaling Write-Up
- [x] **Task 2 n8n workflow JSON** exported in repository ([`n8n/candidate_skill_autotagging_flow.json`](n8n/candidate_skill_autotagging_flow.json))
- [ ] **Screen recording** ($\le$ 6 minutes, voice required)
- [ ] **Final email submission** with repository link + video link before deadline
