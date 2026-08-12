# Task 1 Database & Entity Resolution Design Document (PostgreSQL)

## 1. Overview & System Goals

The goal of Task 1 is to design and build a clean, unified relational database that ingests data from three disparate, messy source systems:
1. **Source 1 — Naukri Applicants** (`data/source1_naukri_applicants.csv`)
2. **Source 2 — Gig Workers** (`data/source2_gig_workers.csv`)
3. **Source 3 — CBNexus Contacts** (`data/source3_cbnexus_contacts.csv`)

Although no common global ID exists across these systems, candidates appearing across multiple sources must be resolved into a single canonical `person` record while preserving **complete source traceability**, raw data byte-for-byte lineage, and explicitly capturing data quality anomalies and conflicts without silent data destruction.

---

## 2. PostgreSQL Database Architecture

The database architecture is implemented in **PostgreSQL** (compatible with Supabase managed environments) following a 3-layer pattern:
1. **Staging & Raw Layer**: Stores raw source records byte-for-byte, structural recovery metadata (`was_malformed`, `recovery_reason`), and logs quarantined rows.
2. **Canonical Core Layer**: Normalized unified entities (`persons`, `candidate_profiles`, `person_emails`, `person_phones`, `candidate_skills`).
3. **Lineage & Audit Layer**: Links canonical entities back to exact source files/lines (`person_source_mappings`, `entity_conflicts`, `ingestion_quarantine_log`).

```
                    +------------------------------------+
                    |        Raw CSV Source Files        |
                    +------------------------------------+
                                      |
                                      v
                    +------------------------------------+
                    |      Raw Layer & Quarantine        |
                    | (raw_source1/2/3 & quarantine_log) |
                                      |
                                      v
                    +------------------------------------+
                    |       Normalization Engine         |
                    | (Cleaner, Standardizer, Parsers)   |
                                      |
                                      v
                    +------------------------------------+
                    |     Entity Resolution Engine       |
                    | (Tier 1 -> Tier 2 -> Tier 3 Rules) |
                                      |
                                      v
+---------------------------------------------------------------------------+
|                      PostgreSQL Canonical Core Database                   |
|  +--------------+   +------------------------+   +---------------------+  |
|  |   persons    |---| person_source_mappings |---| candidate_profiles  |  |
|  +--------------+   +------------------------+   +---------------------+  |
|         |                      |                            |             |
|  +--------------+   +------------------------+   +---------------------+  |
|  |person_emails |   |    person_phones       |   |  candidate_skills   |  |
|  +--------------+   +------------------------+   +---------------------+  |
|                                                                           |
|  +---------------------------------------------------------------------+  |
|  |                          entity_conflicts                           |  |
|  +---------------------------------------------------------------------+  |
+---------------------------------------------------------------------------+
```

---

## 3. PostgreSQL Database Tables Specification (`database/schema.sql`)

### 3.1 Raw & Quarantine Layer

#### Table: `raw_source1_naukri`
Stores raw lines from Naukri Applicants.
* `id` SERIAL PRIMARY KEY
* `source_system` VARCHAR(50) DEFAULT 'naukri'
* `source_file` VARCHAR(255) DEFAULT 'source1_naukri_applicants.csv'
* `line_number` INT NOT NULL
* `raw_line_content` TEXT
* `raw_candidate_name` TEXT
* `raw_email` TEXT
* `raw_phone` TEXT
* `raw_current_city` TEXT
* `raw_total_experience` TEXT
* `raw_expected_ctc` TEXT
* `raw_application_date` TEXT
* `raw_skills` TEXT
* `ingested_at` TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
* `CONSTRAINT uq_raw_s1_line UNIQUE (source_system, source_file, line_number)`

#### Table: `raw_source2_gig_workers`
Stores raw lines from Gig Workers including verbatim raw string and recovery reason for malformed lines.
* `id` SERIAL PRIMARY KEY
* `source_system` VARCHAR(50) DEFAULT 'gig_workers'
* `source_file` VARCHAR(255) DEFAULT 'source2_gig_workers.csv'
* `line_number` INT NOT NULL
* `raw_line_content` TEXT NOT NULL  -- Exact verbatim unparsed CSV line
* `raw_email_id` TEXT
* `raw_worker_name` TEXT
* `raw_rate` TEXT
* `raw_location` TEXT
* `raw_status` TEXT
* `raw_skill_tags` TEXT
* `was_malformed` BOOLEAN DEFAULT FALSE
* `recovery_reason` TEXT
* `ingested_at` TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
* `CONSTRAINT uq_raw_s2_line UNIQUE (source_system, source_file, line_number)`

#### Table: `raw_source3_cbnexus`
Stores raw lines from CBNexus Contacts.
* `id` SERIAL PRIMARY KEY
* `source_system` VARCHAR(50) DEFAULT 'cbnexus'
* `source_file` VARCHAR(255) DEFAULT 'source3_cbnexus_contacts.csv'
* `line_number` INT NOT NULL
* `raw_line_content` TEXT
* `raw_name` TEXT
* `raw_phone_number` TEXT
* `raw_city` TEXT
* `raw_verified` TEXT
* `raw_projects_completed` TEXT
* `ingested_at` TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
* `CONSTRAINT uq_raw_s3_line UNIQUE (source_system, source_file, line_number)`

#### Table: `ingestion_quarantine_log`
Tracks malformed, blank, or header rows excluded or re-mapped during ingestion.
* `quarantine_id` SERIAL PRIMARY KEY
* `source_system` VARCHAR(50) NOT NULL
* `file_name` VARCHAR(255) NOT NULL
* `line_number` INT NOT NULL
* `issue_type` VARCHAR(100) NOT NULL     -- 'BLANK_ROW', 'DUPLICATE_HEADER', 'COLUMN_SHIFT'
* `raw_line_content` TEXT NOT NULL
* `resolution_action` VARCHAR(100) NOT NULL -- 'DROPPED', 'RE_MAPPED_AND_INGESTED'
* `created_at` TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
* `CONSTRAINT uq_quarantine_line UNIQUE (source_system, file_name, line_number, issue_type)`

---

### 3.2 Canonical Core Layer

#### Table: `persons`
The central unified entity record representing a unique individual.
* `person_id` SERIAL PRIMARY KEY
* `canonical_name` VARCHAR(255) NOT NULL
* `primary_email` VARCHAR(255)
* `primary_phone` VARCHAR(50)
* `canonical_city` VARCHAR(100)
* `created_at` TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
* `updated_at` TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP

#### Table: `person_source_mappings` (Source Lineage)
Maps every canonical person back to exact source file records.
* `mapping_id` SERIAL PRIMARY KEY
* `person_id` INT NOT NULL REFERENCES `persons`(`person_id`) ON DELETE CASCADE
* `source_system` VARCHAR(50) NOT NULL
* `source_file` VARCHAR(255) NOT NULL
* `source_line_number` INT NOT NULL
* `raw_record_id` INT NOT NULL
* `match_confidence` VARCHAR(50) NOT NULL -- 'HIGH_CONFIDENCE', 'MEDIUM_CONFIDENCE', 'MANUAL_REVIEW'
* `match_rule_applied` VARCHAR(100) NOT NULL -- 'RULE_1A_EXACT_EMAIL', 'RULE_1B_EXACT_PHONE', 'RULE_2_NAME_CITY'
* `created_at` TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
* `CONSTRAINT uq_person_source_line UNIQUE (source_system, source_file, source_line_number)`

#### Table: `candidate_profiles`
Aggregated unified attributes compiled across sources.
* `profile_id` SERIAL PRIMARY KEY
* `person_id` INT UNIQUE NOT NULL REFERENCES `persons`(`person_id`) ON DELETE CASCADE
* `experience_years` DOUBLE PRECISION
* `expected_ctc_lpa` DOUBLE PRECISION     -- Normalized to LPA float
* `hourly_rate_inr` DOUBLE PRECISION      -- From Gig Workers S2 (/hr)
* `monthly_rate_inr` DOUBLE PRECISION     -- From Gig Workers S2 (k/month)
* `status` VARCHAR(50)                     -- Active / Inactive / Paused
* `is_verified` BOOLEAN                   -- Mapped from Y/yes/Verified
* `projects_completed` INT
* `updated_at` TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP

#### Table: `person_emails`
* `email_id` SERIAL PRIMARY KEY
* `person_id` INT NOT NULL REFERENCES `persons`(`person_id`) ON DELETE CASCADE
* `email_address` VARCHAR(255) NOT NULL
* `is_primary` BOOLEAN DEFAULT FALSE
* `source_system` VARCHAR(50) NOT NULL
* `CONSTRAINT uq_person_email UNIQUE (person_id, email_address)`

#### Table: `person_phones`
* `phone_id` SERIAL PRIMARY KEY
* `person_id` INT NOT NULL REFERENCES `persons`(`person_id`) ON DELETE CASCADE
* `phone_number` VARCHAR(50) NOT NULL
* `is_primary` BOOLEAN DEFAULT FALSE
* `source_system` VARCHAR(50) NOT NULL
* `CONSTRAINT uq_person_phone UNIQUE (person_id, phone_number)`

#### Table: `candidate_skills`
* `skill_id` SERIAL PRIMARY KEY
* `person_id` INT NOT NULL REFERENCES `persons`(`person_id`) ON DELETE CASCADE
* `skill_name` VARCHAR(100) NOT NULL
* `source_system` VARCHAR(50) NOT NULL
* `CONSTRAINT uq_person_skill_source UNIQUE (person_id, skill_name, source_system)`

#### Table: `entity_conflicts`
* `conflict_id` SERIAL PRIMARY KEY
* `person_id` INT NOT NULL REFERENCES `persons`(`person_id`) ON DELETE CASCADE
* `attribute_name` VARCHAR(50) NOT NULL
* `source_system_1` VARCHAR(50) NOT NULL
* `source_1_value` TEXT
* `source_system_2` VARCHAR(50) NOT NULL
* `source_2_value` TEXT
* `resolution_strategy` VARCHAR(100) NOT NULL
* `logged_at` TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
* `CONSTRAINT uq_conflict_record UNIQUE (person_id, attribute_name, source_system_1, source_system_2)`

---

## 4. Entity Resolution Hierarchy & Matching Rules

```
                              [Input Candidate Record]
                                         |
                                         v
                    +------------------------------------------+
                    |  Tier 1A: Exact Normalized Email Match?  |----> YES: Merge into existing person
                    +------------------------------------------+      Confidence: HIGH (1.0)
                                         | NO
                                         v
                    +------------------------------------------+
                    |  Tier 1B: Exact Normalized Phone Match?  |----> YES: Merge into existing person
                    +------------------------------------------+      Confidence: HIGH (1.0)
                                         | NO
                                         v
                    +------------------------------------------+
                    |  Tier 2: Normalized Name + City Match?   |----> YES: Merge into existing person
                    +------------------------------------------+      Confidence: MEDIUM (0.85)
                                         | NO
                                         v
                    +------------------------------------------+
                    | Tier 3: Conflicting Attributes / Initial? |----> YES: Flag for Manual Review /
                    +------------------------------------------+      Log in entity_conflicts
                                         | NO
                                         v
                          [Create New Canonical Person]
```

---

## 5. Structural Malformed-Row Detection

Structural Column-Shift Detection in Source 2:
* **Rule**: Evaluate structural field properties without relying on hardcoded skill strings (`"react"`, `"python"`).
* **Condition**:
  * Check if Field 0 (`email`) fails email validation (`normalize_email(r[0]) == ""`).
  * Check if Field 1 (`worker_name`) passes email validation (`normalize_email(r[1]) != ""`).
  * If Field 0 is invalid as email AND Field 1 is valid as email, a **structural column shift** is detected.
* **Recovery**: Un-shift fields into proper memory slots and flag `was_malformed = TRUE` in `raw_source2_gig_workers` while logging the raw unparsed string.
