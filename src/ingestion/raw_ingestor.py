import csv
import os
import re
from src.database.connection import get_connection, PROJECT_ROOT
from src.ingestion.normalizer import normalize_email

DATA_DIR = os.path.join(PROJECT_ROOT, "data")

S1_FILE = os.path.join(DATA_DIR, "source1_naukri_applicants.csv")
S2_FILE = os.path.join(DATA_DIR, "source2_gig_workers.csv")
S3_FILE = os.path.join(DATA_DIR, "source3_cbnexus_contacts.csv")

def read_raw_csv(filepath):
    with open(filepath, "r", encoding="utf-8-sig", errors="replace") as f:
        reader = csv.reader(f)
        return list(reader)

def log_quarantine(conn, source_system, file_name, line_number, issue_type, raw_line_content, resolution_action):
    conn.execute(
        """
        INSERT INTO ingestion_quarantine_log 
        (source_system, file_name, line_number, issue_type, raw_line_content, resolution_action)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (source_system, file_name, line_number, issue_type) DO NOTHING;
        """,
        (source_system, file_name, line_number, issue_type, str(raw_line_content), resolution_action)
    )

def ingest_source1(conn, filepath=S1_FILE):
    rows = read_raw_csv(filepath)
    filename = os.path.basename(filepath)
    clean_records = []
    
    with conn:
        for idx, r in enumerate(rows[1:], start=2): # Line 1 is header
            raw_line_str = ",".join(r)
            if not r or all(c.strip() == "" for c in r):
                log_quarantine(conn, "naukri", filename, idx, "BLANK_ROW", raw_line_str, "DROPPED")
                continue
                
            c_name = r[0] if len(r) > 0 else ""
            email = r[1] if len(r) > 1 else ""
            phone = r[2] if len(r) > 2 else ""
            city = r[3] if len(r) > 3 else ""
            exp = r[4] if len(r) > 4 else ""
            ctc = r[5] if len(r) > 5 else ""
            date_app = r[6] if len(r) > 6 else ""
            skills = r[7] if len(r) > 7 else ""
            
            # Idempotent Upsert for raw staging
            conn.execute(
                """
                INSERT INTO raw_source1_naukri 
                (source_system, source_file, line_number, raw_line_content, raw_candidate_name, raw_email, raw_phone, raw_current_city, raw_total_experience, raw_expected_ctc, raw_application_date, raw_skills)
                VALUES ('naukri', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (source_system, source_file, line_number) DO UPDATE SET
                    raw_line_content = EXCLUDED.raw_line_content,
                    raw_candidate_name = EXCLUDED.raw_candidate_name,
                    raw_email = EXCLUDED.raw_email,
                    raw_phone = EXCLUDED.raw_phone,
                    raw_current_city = EXCLUDED.raw_current_city,
                    raw_total_experience = EXCLUDED.raw_total_experience,
                    raw_expected_ctc = EXCLUDED.raw_expected_ctc,
                    raw_application_date = EXCLUDED.raw_application_date,
                    raw_skills = EXCLUDED.raw_skills;
                """,
                (filename, idx, raw_line_str, c_name, email, phone, city, exp, ctc, date_app, skills)
            )
            
            cursor = conn.execute("SELECT id FROM raw_source1_naukri WHERE source_system='naukri' AND source_file=%s AND line_number=%s;", (filename, idx))
            raw_id = cursor.fetchone()["id"]
            
            clean_records.append({
                "source_system": "naukri",
                "source_file": filename,
                "line_number": idx,
                "raw_id": raw_id,
                "name": c_name,
                "email": email,
                "phone": phone,
                "city": city,
                "experience": exp,
                "ctc": ctc,
                "application_date": date_app,
                "skills": skills
            })
            
    return clean_records

def ingest_source2(conn, filepath=S2_FILE):
    rows = read_raw_csv(filepath)
    filename = os.path.basename(filepath)
    clean_records = []
    
    with conn:
        for idx, r in enumerate(rows[1:], start=2):
            raw_line_str = ",".join(r)
            if not r or all(c.strip() == "" for c in r):
                log_quarantine(conn, "gig_workers", filename, idx, "BLANK_ROW", raw_line_str, "DROPPED")
                continue
                
            email = r[0] if len(r) > 0 else ""
            name = r[1] if len(r) > 1 else ""
            rate = r[2] if len(r) > 2 else ""
            loc = r[3] if len(r) > 3 else ""
            status = r[4] if len(r) > 4 else ""
            skills = r[5] if len(r) > 5 else ""
            
            was_malformed = False
            recovery_reason = None
            
            # Structural Malformed Row Detection (Field 0 fails email format AND Field 1 passes email format)
            if normalize_email(email) == "" and normalize_email(name) != "":
                was_malformed = True
                recovery_reason = "Structural Column Shift: Field 0 fails email format, Field 1 contains valid email"
                log_quarantine(conn, "gig_workers", filename, idx, "COLUMN_SHIFT", raw_line_str, "RE_MAPPED_AND_INGESTED")
                
                # Un-shift fields: r[0]=skills, r[1]=email, r[2]=name, r[3]=rate, r[4]=location, r[5]=status
                skills = r[0]
                email = r[1]
                name = r[2]
                rate = r[3]
                loc = r[4]
                status = r[5]
                
            conn.execute(
                """
                INSERT INTO raw_source2_gig_workers
                (source_system, source_file, line_number, raw_line_content, raw_email_id, raw_worker_name, raw_rate, raw_location, raw_status, raw_skill_tags, was_malformed, recovery_reason)
                VALUES ('gig_workers', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (source_system, source_file, line_number) DO UPDATE SET
                    raw_line_content = EXCLUDED.raw_line_content,
                    raw_email_id = EXCLUDED.raw_email_id,
                    raw_worker_name = EXCLUDED.raw_worker_name,
                    raw_rate = EXCLUDED.raw_rate,
                    raw_location = EXCLUDED.raw_location,
                    raw_status = EXCLUDED.raw_status,
                    raw_skill_tags = EXCLUDED.raw_skill_tags,
                    was_malformed = EXCLUDED.was_malformed,
                    recovery_reason = EXCLUDED.recovery_reason;
                """,
                (filename, idx, raw_line_str, email, name, rate, loc, status, skills, was_malformed, recovery_reason)
            )
            
            cursor = conn.execute("SELECT id FROM raw_source2_gig_workers WHERE source_system='gig_workers' AND source_file=%s AND line_number=%s;", (filename, idx))
            raw_id = cursor.fetchone()["id"]
            
            clean_records.append({
                "source_system": "gig_workers",
                "source_file": filename,
                "line_number": idx,
                "raw_id": raw_id,
                "email": email,
                "name": name,
                "rate": rate,
                "location": loc,
                "status": status,
                "skills": skills
            })
            
    return clean_records

def ingest_source3(conn, filepath=S3_FILE):
    rows = read_raw_csv(filepath)
    filename = os.path.basename(filepath)
    clean_records = []
    
    with conn:
        for idx, r in enumerate(rows[1:], start=2):
            raw_line_str = ",".join(r)
            if not r or all(c.strip() == "" for c in r):
                log_quarantine(conn, "cbnexus", filename, idx, "BLANK_ROW", raw_line_str, "DROPPED")
                continue
                
            name = r[0] if len(r) > 0 else ""
            phone = r[1] if len(r) > 1 else ""
            city = r[2] if len(r) > 2 else ""
            verified = r[3] if len(r) > 3 else ""
            projects = r[4] if len(r) > 4 else ""
            
            # Structural Duplicate Header Detection
            if name.strip().lower() == "name" and phone.strip().lower() == "phone number":
                log_quarantine(conn, "cbnexus", filename, idx, "DUPLICATE_HEADER", raw_line_str, "DROPPED")
                continue
                
            conn.execute(
                """
                INSERT INTO raw_source3_cbnexus
                (source_system, source_file, line_number, raw_line_content, raw_name, raw_phone_number, raw_city, raw_verified, raw_projects_completed)
                VALUES ('cbnexus', %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (source_system, source_file, line_number) DO UPDATE SET
                    raw_line_content = EXCLUDED.raw_line_content,
                    raw_name = EXCLUDED.raw_name,
                    raw_phone_number = EXCLUDED.raw_phone_number,
                    raw_city = EXCLUDED.raw_city,
                    raw_verified = EXCLUDED.raw_verified,
                    raw_projects_completed = EXCLUDED.raw_projects_completed;
                """,
                (filename, idx, raw_line_str, name, phone, city, verified, projects)
            )
            
            cursor = conn.execute("SELECT id FROM raw_source3_cbnexus WHERE source_system='cbnexus' AND source_file=%s AND line_number=%s;", (filename, idx))
            raw_id = cursor.fetchone()["id"]
            
            clean_records.append({
                "source_system": "cbnexus",
                "source_file": filename,
                "line_number": idx,
                "raw_id": raw_id,
                "name": name,
                "phone": phone,
                "city": city,
                "verified": verified,
                "projects": projects
            })
            
    return clean_records
