# Data Profiling Report

## 1. Executive Summary

This Data Profiling Report presents a comprehensive, programmatic analysis of three candidate datasets provided for the ConsultBae AI Automation project:
1. **Source 1 — Naukri Applicants** (`data/source1_naukri_applicants.csv`)
2. **Source 2 — Gig Workers** (`data/source2_gig_workers.csv`)
3. **Source 3 — CBNexus Contacts** (`data/source3_cbnexus_contacts.csv`)

The objective of this phase is to evaluate the schema, completeness, duplicates, formatting inconsistencies, structural corruption, and cross-source record alignment **without modifying, cleaning, or merging any raw data**.

### Key Highlights & Metrics

| Source Dataset | Total File Lines | Header Rows | Data Records | Total Columns | Null/Blank Cells | Corrupted / Shifted Rows | Duplicate Header Rows |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Source 1 (Naukri)** | 43 | 1 | 42 | 8 | 0 | 0 | 0 |
| **Source 2 (Gig Workers)** | 33 | 1 | 32 | 6 | 6 (1 empty row) | 1 (Column shift) | 0 |
| **Source 3 (CBNexus)** | 32 | 1 | 31 | 5 | 0 | 0 | 1 (In-data header) |

---

## 2. Source 1 — Naukri Applicants

* **File Name**: `source1_naukri_applicants.csv`
* **File Path**: `data/source1_naukri_applicants.csv`
* **File Size**: 5,296 bytes
* **Total Rows**: 43 (1 Header + 42 Data Rows)

### Schema

| Column Name | Apparent Data Type | Example Values | Inferred Semantics |
| :--- | :--- | :--- | :--- |
| `Candidate Name` | String | `Tanvi Gupta`, `R. Verma`, `Varun Jain` | Full or abbreviated candidate name |
| `Email` | String (Email format) | `tanvi.gupta31@example.com`, `alt.nikhil.chopra70@example.com` | Primary candidate email contact |
| `Phone` | String (Numeric with prefixes) | `+919000000254`, `09000000287`, `9000000113` | Candidate telephone number |
| `Current City` | String | `Bengaluru`, `GURGAON`, `pune`, `Noida ` | Current operating location of applicant |
| `Total Experience (Years)` | Float / String | `4.2`, `3.5`, `0.8`, `5.0` | Total work experience in years |
| `Expected CTC (LPA)` | Float / Integer String | `4.2`, `8.3`, `332456`, `1181149` | **Unit mismatch**: Some in LPA (e.g. 4.2), some in raw INR (e.g. 332,456) |
| `Application Date` | Date String | `24-07-2026`, `2026-08-08`, `07/13/2026`, `7 Jul 2026` | Date of job application submit |
| `Skills` | String (Comma-separated) | `n8n, LangChain, REST APIs, MongoDB, SQL` | Self-reported technical skills |

### Completeness
* Total values checked: 336 (42 rows × 8 columns).
* Null / Blank Count: **0** nulls across all rows and columns.

### Duplicates
* **Exact Duplicate Records across all fields**: 0 records are 100% identical byte-for-byte.
* **Near-Duplicate / Duplicate Identifier Audit**:
  * `rohit.verma13@mailtest.example.org`:
    * Line 26 (Row 25): Name `R. Verma`, Phone `9000000294`, City `Bangalore`, Experience `2.4`, CTC `6.1`, Date `08/13/2026`, Skills `Python, React, MongoDB`.
    * Line 32 (Row 31): Name `Rohit Verma`, Phone `9000000294`, City `Bangalore`, Experience `2.4`, CTC `6.1`, Date `08/13/2026`, Skills `Python, React, MongoDB`.
    * *Observation*: Identical candidate record where name is abbreviated (`R. Verma`) in one record and fully expanded (`Rohit Verma`) in another.
  * `nikhil.chopra70@example.com` / `09000000103`:
    * Line 28 (Row 27): Name `Nikhil Chopra`, Email `alt.nikhil.chopra70@example.com`, Phone `09000000103`, City `NOIDA`, Exp `0.8`, CTC `7.8`, Date `07/03/2026`, Skills `Pandas, SQL, n8n`.
    * Line 38 (Row 37): Name `Nikhil Chopra`, Email `nikhil.chopra70@example.com`, Phone `09000000103`, City `NOIDA`, Exp `0.8`, CTC `7.8`, Date `07/03/2026`, Skills `Pandas, SQL, n8n`.
    * *Observation*: Same person with identical phone, experience, CTC, skills, and date, but using two distinct email addresses (`alt.nikhil.chopra70@...` vs `nikhil.chopra70@...`).

### Formatting Issues
1. **Expected CTC Unit Inconsistency**:
   * Standard LPA format (e.g. `4.2`, `8.3`, `5.1`, `6.1`, `2.4`, `7.8`, `10.3`).
   * Raw annual salary values in INR (e.g. `332456` = ~3.32 LPA, `775670`, `654699`, `806661`, `472935`, `871686`, `864237`, `1195422`, `826748`, `1181149`, `327287`, `410629`, `775796`, `792474`, `1160787`, `1135514`, `626740`, `621881`, `694306`).
2. **Date Format Variations**:
   * `YYYY-MM-DD` (e.g. `2026-08-08`, `2026-08-02`, `2026-07-13`)
   * `DD-MM-YYYY` (e.g. `24-07-2026`, `19-07-2026`, `28-07-2026`, `03-07-2026`)
   * `MM/DD/YYYY` (e.g. `07/13/2026`, `07/03/2026`, `08/19/2026`, `08/13/2026`)
   * `D MMM YYYY` (e.g. `7 Jul 2026`, `19 Jul 2026`, `8 Jul 2026`, `15 Jul 2026`, `22 Jul 2026`)
3. **Phone Number Formatting**:
   * Leading zero prefix: `09000000287`, `09000000138`, `09000000167`
   * Country code prefix `+91`: `+919000000254`, `+919000000288`
   * Bare 10-digit number: `9000000237`, `9000000113`
4. **City Name Casing & Spacing**:
   * `Bengaluru` vs `bangalore` vs `Bangalore`
   * `GURGAON` vs `Gurugram` vs `gurugram ` (trailing space)
   * `pune` vs `PUNE` vs `Pune`
   * `Noida` vs `NOIDA` vs `Noida ` (trailing space)
   * `Delhi` vs `new delhi` vs `Delhi NCR`

### Suspicious Records
* **Line 26 (Row 25)**: Candidate Name `R. Verma` — abbreviated name requires string resolution during matching.
* **Line 28 (Row 27)**: Email `alt.nikhil.chopra70@example.com` — secondary/alternate email for `nikhil.chopra70@example.com`.

---

## 3. Source 2 — Gig Workers

* **File Name**: `source2_gig_workers.csv`
* **File Path**: `data/source2_gig_workers.csv`
* **File Size**: 3,415 bytes
* **Total Rows**: 33 (1 Header + 32 Data Lines)

### Schema

| Column Name | Apparent Data Type | Example Values | Inferred Semantics |
| :--- | :--- | :--- | :--- |
| `email_id` | String | `varun.jain29@example.com`, `ISHA.CHOPRA95@...` | Worker primary email |
| `worker_name` | String | `Varun Jain`, `Tanvi Agarwal`, `Isha Chopra` | Full worker name |
| `rate` | String | `1415/hr`, `15k/month`, `28k/month` | Compensation rate |
| `location` | String | `Pune`, `Noida `, `Delhi`, `bangalore` | Worker operating city |
| `status` | Categorical String | `Active`, `active`, `ACTIVE`, `Inactive`, `paused` | Engagement status |
| `skill_tags` | String (Comma-separated) | `n8n, web scraping, fastapi, mysql` | Technical competencies |

### Completeness
* Total values checked: 192 (32 data lines × 6 columns).
* **Blank Line**: **Line 12 (Row 11)** is a completely empty row (`['', '', '', '', '', '']`). Total 6 blank cells.

### Duplicates
* **Exact Duplicate Records**: 0.
* **Duplicate Email & Person Overlaps**:
  * `ISHA.CHOPRA95@MAILTEST.EXAMPLE.ORG`:
    * Line 7 (Row 6): Email `ISHA.CHOPRA95@MAILTEST.EXAMPLE.ORG`, Name `Isha Chopra`, Rate `1406/hr`, Location `Pune`, Status `active`, Skills `react, javascript, mysql`.
    * Line 20 (Row 19): **Malformed Row** (see Suspicious Records below).
  * `Deepak Nair`:
    * Line 15 (Row 14): Email `DEEPAK.NAIR44@EXAMPLE.COM`, Rate `465/hr`, Location `Bengaluru`, Status `paused`.
    * Line 32 (Row 31): Email `DEEPAK.NAIR57@EXAMPLE.IN`, Rate `1462/hr`, Location `New Delhi`, Status `Active`.
    * *Observation*: Two separate entries for `Deepak Nair` with different email domains, locations, and rates.

### Formatting Issues
1. **Rate Unit Inconsistency**:
   * Hourly rates (`/hr`): `1415/hr`, `1231/hr`, `403/hr`, `440/hr`, `1406/hr`, `330/hr`, `843/hr`, `1331/hr`, `917/hr`, `465/hr`, `437/hr`, `1483/hr`, `763/hr`, `1018/hr`, `590/hr`, `1462/hr`.
   * Monthly rates (`k/month`): `15k/month`, `72k/month`, `28k/month`, `56k/month`, `79k/month`, `42k/month`, `73k/month`, `55k/month`, `22k/month`, `21k/month`, `59k/month`, `38k/month`, `71k/month`.
2. **Email Casing Inconsistency**:
   * Lowercase: `varun.jain29@example.com`, `tanvi.agarwal97@example.in`
   * ALL CAPS: `ISHA.CHOPRA95@MAILTEST.EXAMPLE.ORG`, `VARUN.SAXENA21@EXAMPLE.IN`, `DEEPAK.NAIR44@EXAMPLE.COM`, `NEHA.BHATIA60@MAILTEST.EXAMPLE.ORG`, `KARAN.CHOPRA76@MAILTEST.EXAMPLE.ORG`, `KAVYA.VERMA74@MAILTEST.EXAMPLE.ORG`, `TANVI.REDDY80@EXAMPLE.COM`, `TANVI.SHARMA56@MAILTEST.EXAMPLE.ORG`, `DEEPAK.NAIR57@EXAMPLE.IN`.
3. **Status Categorical Inconsistency**:
   * Active variations: `Active`, `active`, `ACTIVE`
   * Inactive variations: `Inactive`
   * Paused variations: `paused`

### Suspicious Records
* **Line 12 (Row 11)**: Completely blank row (`['', '', '', '', '', '']`).
* **Line 20 (Row 19)**: **Column-Shifted / Corrupted Row**:
  * Raw values: `['react, javascript, mysql', 'ISHA.CHOPRA95@MAILTEST.EXAMPLE.ORG', 'Isha Chopra', '1406/hr', 'Pune', 'active']`
  * Column mapping anomaly:
    * `email_id` contains skills: `'react, javascript, mysql'`
    * `worker_name` contains email: `'ISHA.CHOPRA95@MAILTEST.EXAMPLE.ORG'`
    * `rate` contains name: `'Isha Chopra'`
    * `location` contains rate: `'1406/hr'`
    * `status` contains location: `'Pune'`
    * `skill_tags` contains status: `'active'`

---

## 4. Source 3 — CBNexus Contacts

* **File Name**: `source3_cbnexus_contacts.csv`
* **File Path**: `data/source3_cbnexus_contacts.csv`
* **File Size**: 1,269 bytes
* **Total Rows**: 32 (1 Header + 31 Data Lines)

### Schema

| Column Name | Apparent Data Type | Example Values | Inferred Semantics |
| :--- | :--- | :--- | :--- |
| `Name` | String | `Rohit Nair`, `RITU SHARMA`, `Arjun Mehta` | Full contact name |
| `Phone Number` | String (Phone format) | `9000000268`, `919000000146`, `+91-9000000131` | Contact phone number |
| `City` | String | `Gurgaon`, `Noida `, `New Delhi`, `pune` | Contact city |
| `Verified` | Categorical String / Boolean | `Y`, `yes`, `Yes`, `No`, `N` | Account verification status |
| `Projects Completed` | Integer String | `13`, `15`, `0`, `11` | Completed project count |

### Completeness
* Total values checked: 155 (31 data lines × 5 columns).
* Null / Blank Count: **0** nulls.

### Duplicates
* **Exact Duplicate Records**: 0.
* **Duplicate Name / Person Entries**:
  * `Arjun Mehta`:
    * Line 5 (Row 4): Phone `+91-9000000131`, City `Noida`, Verified `No`, Projects `9`.
    * Line 28 (Row 27): Phone `9000000272`, City `Noida`, Verified `Yes`, Projects `14`.
    * *Observation*: Two distinct phone numbers (`...131` vs `...272`) listed for `Arjun Mehta` in `Noida`.

### Formatting Issues
1. **Phone Format Inconsistencies**:
   * 10-digit standard: `9000000268`, `9000000116`, `9000000143`, `9000000287`
   * Prefix `91` (12 digits): `919000000146`, `919000000231`, `919000000260`, `919000000263`
   * Prefix `+91-`: `+91-9000000131`, `+91-9000000104`, `+91-9000000227`, `+91-9000000295`, `+91-9000000162`, `+91-9000000261`
2. **Verified Field Categorical Variations**:
   * Positive verification: `Y`, `Verified`, `yes`, `Yes`
   * Negative verification: `No`, `N`
3. **Name Casing**:
   * Title Case: `Rohit Nair`, `Priya Saxena`, `Arjun Mehta`
   * ALL CAPS: `RITU SHARMA`, `RAHUL MALHOTRA`, `SAHIL MALHOTRA`, `KARAN BHATIA`, `MEERA BHATIA`, `VARUN SAXENA`, `DEEPAK NAIR`, `MANISH BHATIA`, `DIVYA CHOPRA`

### Suspicious Records
* **Line 16 (Row 15)**: **Duplicate Header Row Embedded in Data**:
  * Raw values: `['Name', 'Phone Number', 'City', 'Verified', 'Projects Completed']`
  * Occurs directly in the middle of the dataset at line 16.

---

## 5. Cross-Source Observations

### Field Availability Across Sources

| Information Dimension | Source 1 (Naukri) | Source 2 (Gig Workers) | Source 3 (CBNexus) |
| :--- | :--- | :--- | :--- |
| **Person Name** | `Candidate Name` | `worker_name` | `Name` |
| **Email Address** | `Email` | `email_id` | *(Not Available)* |
| **Phone Number** | `Phone` | *(Not Available)* | `Phone Number` |
| **Location / City** | `Current City` | `location` | `City` |
| **Skills / Tech Stack**| `Skills` | `skill_tags` | *(Not Available)* |
| **Compensation / CTC** | `Expected CTC (LPA)` | `rate` | *(Not Available)* |
| **Experience / Stats** | `Total Experience` | *(Not Available)* | `Projects Completed` |
| **Status / Verified** | *(Not Available)* | `status` | `Verified` |

---

## 6. Candidate Matching Signals

### Primary Exact Matching Keys

1. **Email Address (Source 1 ↔ Source 2)**:
   * **Overlapping Unique Emails**: **20 candidates** share identical normalized emails across S1 and S2.
   * *Examples*:
     * `tanvi.gupta31@example.com` (S1 Line 2 ↔ S2 Line 11)
     * `arjun.mishra70@example.com` (S1 Line 17 ↔ S2 Line 5)
     * `karan.bhatia32@mailtest.example.org` (S1 Line 15 ↔ S2 Line 4)
     * `varun.jain29@example.com` (S1 Line 19 ↔ S2 Line 2)

2. **Normalized Phone Number (Source 1 ↔ Source 3)**:
   * **Overlapping Unique Phone Numbers**: **27 candidates** match on 10-digit standardized phone numbers between S1 and S3.
   * *Examples*:
     * Phone `9000000254` → S1 Line 2 (`Tanvi Gupta`) ↔ S3 Line 22 (`Tanvi Gupta`)
     * Phone `9000000146` → S1 Line 16 (`Ritu Sharma`) ↔ S3 Line 3 (`RITU SHARMA`)
     * Phone `9000000268` → S1 Line 32 (`Rohit Nair`) ↔ S3 Line 2 (`Rohit Nair`)
     * Phone `9000000295` → S1 Line 40 (`Isha Kapoor`) ↔ S3 Line 17 (`Isha Kapoor`)

### Secondary Matching & Entity Resolution Attributes

* **Tri-Source Name + City Overlap**:
  * **25 candidate names** appear across all 3 source files.
  * *Examples of Safe Matches (Matching Email/Phone + Name + City)*:
    * `Varun Jain`: S1 Line 19 (Email: `varun.jain29@...`, Phone: `9000000263`, City: `Pune`) ↔ S2 Line 2 (Email: `varun.jain29@...`, City: `Pune`) ↔ S3 Line 12 (Phone: `919000000263`, City: `Pune`).
    * `Tanvi Agarwal`: S1 Line 38 ↔ S2 Line 3 ↔ S3 Line 13.
    * `Karan Bhatia`: S1 Line 15 ↔ S2 Line 4 ↔ S3 Line 14.
  
* **Why Name Alone Is Unsafe**:
  * **Deepak Nair**:
    * S1 Line 33: Email `deepak.nair44@example.com`, Phone `9000000296`, City `bangalore`.
    * S2 Line 15: Email `DEEPAK.NAIR44@EXAMPLE.COM`, Rate `465/hr`, City `Bengaluru`.
    * S2 Line 32: Email `DEEPAK.NAIR57@EXAMPLE.IN`, Rate `1462/hr`, City `New Delhi`.
    * S3 Line 25: Phone `919000000296`, City `Bengaluru`.
    * *Conflict*: S2 contains two different `Deepak Nair` records (`DEEPAK.NAIR44@...` vs `DEEPAK.NAIR57@...`). Matching on Name alone would incorrectly collapse two distinct individuals into one.
  * **Arjun Mehta**:
    * S1 Line 20: Email `arjun.mehta9@example.in`, Phone `09000000131`, City `NOIDA`.
    * S2 Line 18: Email `arjun.mehta77@mailtest.example.org`, Rate `42k/month`, City `Noida`.
    * S3 Line 5: Phone `+91-9000000131`, City `Noida`.
    * S3 Line 28: Phone `9000000272`, City `Noida`.
    * *Conflict*: S1 & S3 share Phone `...131`, but S2 has a different email domain (`arjun.mehta77@...`) and S3 has a second phone number (`...272`).

---

## 7. Data-Quality Issues Requiring Handling

The table below summarizes every data-quality anomaly discovered during programmatic profiling:

| Source | Row / Line | Issue Type | Concrete Example | Why It Matters | Possible Handling Later |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Source 2** | Line 20 | **Column Shift / Malformed Row** | `['react, javascript, mysql', 'ISHA.CHOPRA95@...', 'Isha Chopra', ...]` | Skews parser, puts skills in email field and email in name field. | Detect header/type mismatch, un-shift fields into correct columns before ingestion. |
| **Source 2** | Line 12 | **Blank Row** | `['', '', '', '', '', '']` | Causes empty DB records or NULL insertion errors. | Filter out completely empty rows during ingestion pipeline. |
| **Source 3** | Line 16 | **Duplicate Header Row** | `['Name', 'Phone Number', 'City', 'Verified', 'Projects Completed']` | Treats column titles as candidate record during parsing. | Ignore rows matching header string exact values. |
| **Source 1** | Line 3, 4, 7, etc. | **CTC Unit Inconsistency** | `332456` vs `4.2` LPA | Cannot compare or filter salaries without standardizing units. | Convert raw figures (>100) by dividing by 100,000 into LPA floats. |
| **Source 2** | Multiple | **Rate Unit Inconsistency** | `1415/hr` vs `15k/month` | Hourly vs monthly rates cannot be sorted or compared directly. | Parse rate string into float value and normalized unit type (`hourly` / `monthly`). |
| **Source 1** | Multiple | **Date Format Variety** | `2026-08-08`, `24-07-2026`, `07/13/2026`, `7 Jul 2026` | Date queries and sorting will fail. | Standardize all dates to ISO-8601 (`YYYY-MM-DD`). |
| **Source 1, 3** | Multiple | **Phone Number Variations** | `09000000287`, `+919000000254`, `+91-9000000131`, `919000000268` | Prevents exact join/lookup between S1 and S3. | Standardize to clean 10-digit string (e.g. `9000000287`). |
| **Source 2** | Multiple | **Email Upper Casing** | `ISHA.CHOPRA95@MAILTEST.EXAMPLE.ORG` | Case-sensitive string joins will fail between S1 and S2. | Lowercase and trim all email strings. |
| **Source 1, 2, 3** | Multiple | **City Name Inconsistencies** | `Gurgaon` vs `gurugram ` vs `NOIDA` vs `bangalore` vs `Bengaluru` | Location filtering and matching will miss identical locations. | Normalize city names to standard canonical names (e.g. `Bengaluru`, `Gurugram`, `Noida`). |
| **Source 3** | Multiple | **Verified Status Variety** | `Y`, `yes`, `Yes`, `Verified`, `No`, `N` | Boolean filters will miss true/false values. | Map to standard boolean `True` / `False`. |
| **Source 2** | Multiple | **Status Variety** | `Active`, `active`, `ACTIVE`, `paused`, `Inactive` | Status queries require clean enum value. | Normalize casing to lowercase/title-case enum (`active`, `inactive`, `paused`). |
| **Source 1** | Line 26, 32 | **Abbreviated Name vs Full Name** | `R. Verma` (Line 26) vs `Rohit Verma` (Line 32) | Exact string name match fails. | Use email (`rohit.verma13@...`) as primary anchor to resolve name. |
| **Source 1** | Line 28, 38 | **Alternate Emails for Same Person** | `alt.nikhil.chopra70@...` vs `nikhil.chopra70@...` | Email join misses candidate across records. | Use phone (`09000000103`) as secondary join key. |

---

## 8. Open Questions / Assumptions

1. **Assumptions**:
   * **Phone Number Standard**: All phone numbers represent Indian mobile numbers (10 digits starting with `90000...`).
   * **CTC Units**: Any numeric string > 100 in Source 1 `Expected CTC` represents annual INR amount (e.g., `332,456` = 3.32 LPA).
   * **Rate Conversion**: 1 month is assumed to equal 160 billable hours if hourly/monthly conversion is needed later.

2. **Open Questions for Client / Domain Experts**:
   * Should candidates with conflicting details across sources (e.g. `Deepak Nair` in S2 with different email domains) be merged or kept as separate profiles?
   * How should `Projects Completed` in S3 be weighted against `Total Experience (Years)` in S1?

---

## 9. Summary

* **Dataset Integrity**: All three original CSV files remain **byte-for-byte untouched** in `data/`.
* **Primary Key Availability**:
  * **S1 ↔ S2**: Linked via `Email` (20 exact matches).
  * **S1 ↔ S3**: Linked via 10-digit `Phone Number` (27 exact matches).
  * **S1 ↔ S2 ↔ S3**: 25 candidate entities are present across all three sources.
* **Cleaning Blueprint Prepared**: The data-quality table defines clear normalization rules for Phase 2 database schema design and ingestion pipelines.
