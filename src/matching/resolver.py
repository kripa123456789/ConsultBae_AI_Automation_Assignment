from src.ingestion.normalizer import (
    normalize_name, normalize_email, normalize_phone, normalize_city,
    normalize_date, normalize_ctc, normalize_rate, normalize_verified, normalize_skills
)
from src.matching.conflict_handler import log_conflict

def resolve_and_load(conn, s1_records, s2_records, s3_records):
    """
    Executes the 3-Tier Entity Resolution algorithm across all three source record lists.
    Populates: persons, person_source_mappings, candidate_profiles, person_emails, person_phones, candidate_skills, entity_conflicts.
    Idempotent across repeated pipeline executions.
    """
    
    # In-memory indexes for fast resolution
    email_index = {}
    phone_index = {}
    name_city_index = {}
    person_profiles = {}
    
    with conn:
        def create_person(name, email, phone, city):
            norm_n = normalize_name(name)
            norm_e = normalize_email(email)
            norm_p = normalize_phone(phone)
            norm_c = normalize_city(city)
            
            # Check if matching person already exists
            existing_pid = None
            if norm_e and norm_e in email_index:
                existing_pid = email_index[norm_e]
            elif norm_p and norm_p in phone_index:
                existing_pid = phone_index[norm_p]
                
            if existing_pid:
                return existing_pid

            cursor = conn.execute(
                """
                INSERT INTO persons (canonical_name, primary_email, primary_phone, canonical_city)
                VALUES (%s, %s, %s, %s);
                """,
                (norm_n, norm_e, norm_p, norm_c)
            )
            pid = cursor.lastrowid
            
            person_profiles[pid] = {
                "name": norm_n,
                "primary_email": norm_e,
                "primary_phone": norm_p,
                "city": norm_c,
                "emails": set([norm_e]) if norm_e else set(),
                "phones": set([norm_p]) if norm_p else set(),
                "exp": None,
                "ctc_lpa": None,
                "hourly_rate": None,
                "monthly_rate": None,
                "status": None,
                "is_verified": None,
                "projects": None,
                "skills": {}
            }
            
            if norm_e:
                email_index[norm_e] = pid
            if norm_p:
                phone_index[norm_p] = pid
            if norm_n and norm_c:
                name_city_key = (norm_n.lower(), norm_c.lower())
                if name_city_key not in name_city_index:
                    name_city_index[name_city_key] = []
                name_city_index[name_city_key].append(pid)
                
            return pid

        def add_mapping(pid, source_sys, source_file, line_num, raw_id, confidence, rule):
            conn.execute(
                """
                INSERT INTO person_source_mappings
                (person_id, source_system, source_file, source_line_number, raw_record_id, match_confidence, match_rule_applied)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (source_system, source_file, source_line_number) DO NOTHING;
                """,
                (pid, source_sys, source_file, line_num, raw_id, confidence, rule)
            )

        def add_email(pid, email, source_sys, is_primary=False):
            norm_e = normalize_email(email)
            if not norm_e:
                return
            conn.execute(
                """
                INSERT INTO person_emails (person_id, email_address, is_primary, source_system)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (person_id, email_address) DO NOTHING;
                """,
                (pid, norm_e, True if is_primary else False, source_sys)
            )
            if pid in person_profiles:
                person_profiles[pid]["emails"].add(norm_e)
            if norm_e not in email_index:
                email_index[norm_e] = pid

        def add_phone(pid, phone, source_sys, is_primary=False):
            norm_p = normalize_phone(phone)
            if not norm_p:
                return
            conn.execute(
                """
                INSERT INTO person_phones (person_id, phone_number, is_primary, source_system)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (person_id, phone_number) DO NOTHING;
                """,
                (pid, norm_p, True if is_primary else False, source_sys)
            )
            if pid in person_profiles:
                person_profiles[pid]["phones"].add(norm_p)
            if norm_p not in phone_index:
                phone_index[norm_p] = pid

        def add_skills(pid, skills_str, source_sys):
            skills_list = normalize_skills(skills_str)
            for s in skills_list:
                conn.execute(
                    """
                    INSERT INTO candidate_skills (person_id, skill_name, source_system)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (person_id, skill_name, source_system) DO NOTHING;
                    """,
                    (pid, s, source_sys)
                )
                if pid in person_profiles:
                    person_profiles[pid]["skills"][s] = source_sys

        # --- PROCESS SOURCE 1 (Naukri Applicants) ---
        for r in s1_records:
            norm_e = normalize_email(r["email"])
            norm_p = normalize_phone(r["phone"])
            norm_n = normalize_name(r["name"])
            norm_c = normalize_city(r["city"])
            
            pid = None
            match_rule = None
            match_conf = None
            
            if norm_e and norm_e in email_index:
                pid = email_index[norm_e]
                match_rule = "RULE_1A_EXACT_EMAIL"
                match_conf = "HIGH_CONFIDENCE"
            elif norm_p and norm_p in phone_index:
                pid = phone_index[norm_p]
                match_rule = "RULE_1B_EXACT_PHONE"
                match_conf = "HIGH_CONFIDENCE"
            else:
                pid = create_person(r["name"], r["email"], r["phone"], r["city"])
                match_rule = "INITIAL_RECORD"
                match_conf = "HIGH_CONFIDENCE"
                
            add_mapping(pid, r["source_system"], r["source_file"], r["line_number"], r["raw_id"], match_conf, match_rule)
            add_email(pid, r["email"], r["source_system"], is_primary=True)
            add_phone(pid, r["phone"], r["source_system"], is_primary=True)
            add_skills(pid, r["skills"], r["source_system"])
            
            prof = person_profiles[pid]
            prof["exp"] = float(r["experience"]) if r["experience"] else prof["exp"]
            prof["ctc_lpa"] = normalize_ctc(r["ctc"]) if r["ctc"] else prof["ctc_lpa"]

        # --- PROCESS SOURCE 2 (Gig Workers) ---
        for r in s2_records:
            norm_e = normalize_email(r["email"])
            norm_n = normalize_name(r["name"])
            norm_c = normalize_city(r["location"])
            
            pid = None
            match_rule = None
            match_conf = None
            
            if norm_e and norm_e in email_index:
                pid = email_index[norm_e]
                match_rule = "RULE_1A_EXACT_EMAIL"
                match_conf = "HIGH_CONFIDENCE"
            else:
                name_city_key = (norm_n.lower(), norm_c.lower())
                if name_city_key in name_city_index:
                    cand_pids = name_city_index[name_city_key]
                    candidate_pid = cand_pids[0]
                    cand_prof = person_profiles[candidate_pid]
                    
                    if norm_e and cand_prof["primary_email"] and norm_e != cand_prof["primary_email"]:
                        pid = create_person(r["name"], r["email"], "", r["location"])
                        match_rule = "RULE_3A_CONFLICT_SEPARATE_PROFILE"
                        match_conf = "MANUAL_REVIEW"
                        log_conflict(conn, pid, "email", "naukri", cand_prof["primary_email"], "gig_workers", norm_e, "SEPARATE_ENTITIES_RETAINED")
                    else:
                        pid = candidate_pid
                        match_rule = "RULE_2_NAME_CITY"
                        match_conf = "MEDIUM_CONFIDENCE"
                else:
                    pid = create_person(r["name"], r["email"], "", r["location"])
                    match_rule = "INITIAL_RECORD"
                    match_conf = "HIGH_CONFIDENCE"

            add_mapping(pid, r["source_system"], r["source_file"], r["line_number"], r["raw_id"], match_conf, match_rule)
            add_email(pid, r["email"], r["source_system"], is_primary=False)
            add_skills(pid, r["skills"], r["source_system"])
            
            prof = person_profiles[pid]
            rate_info = normalize_rate(r["rate"])
            if rate_info["hourly"]:
                prof["hourly_rate"] = rate_info["hourly"]
            if rate_info["monthly"]:
                prof["monthly_rate"] = rate_info["monthly"]
            if r["status"]:
                prof["status"] = r["status"].strip().lower()

        # --- PROCESS SOURCE 3 (CBNexus Contacts) ---
        for r in s3_records:
            norm_p = normalize_phone(r["phone"])
            norm_n = normalize_name(r["name"])
            norm_c = normalize_city(r["city"])
            
            pid = None
            match_rule = None
            match_conf = None
            
            if norm_p and norm_p in phone_index:
                pid = phone_index[norm_p]
                match_rule = "RULE_1B_EXACT_PHONE"
                match_conf = "HIGH_CONFIDENCE"
            else:
                name_city_key = (norm_n.lower(), norm_c.lower())
                if name_city_key in name_city_index:
                    cand_pids = name_city_index[name_city_key]
                    candidate_pid = cand_pids[0]
                    cand_prof = person_profiles[candidate_pid]
                    
                    if norm_p and cand_prof["primary_phone"] and norm_p != cand_prof["primary_phone"]:
                        pid = create_person(r["name"], "", r["phone"], r["city"])
                        match_rule = "RULE_3A_CONFLICT_SEPARATE_PROFILE"
                        match_conf = "MANUAL_REVIEW"
                        log_conflict(conn, pid, "phone", "naukri", cand_prof["primary_phone"], "cbnexus", norm_p, "SEPARATE_ENTITIES_RETAINED")
                    else:
                        pid = candidate_pid
                        match_rule = "RULE_2_NAME_CITY"
                        match_conf = "MEDIUM_CONFIDENCE"
                else:
                    pid = create_person(r["name"], "", r["phone"], r["city"])
                    match_rule = "INITIAL_RECORD"
                    match_conf = "HIGH_CONFIDENCE"
                    
            add_mapping(pid, r["source_system"], r["source_file"], r["line_number"], r["raw_id"], match_conf, match_rule)
            add_phone(pid, r["phone"], r["source_system"], is_primary=False)
            
            prof = person_profiles[pid]
            prof["is_verified"] = normalize_verified(r["verified"])
            try:
                prof["projects"] = int(r["projects"]) if r["projects"] else prof["projects"]
            except ValueError:
                pass

        # --- WRITE FINAL AGGREGATED CANDIDATE PROFILES ---
        for pid, prof in person_profiles.items():
            conn.execute(
                """
                INSERT INTO candidate_profiles
                (person_id, experience_years, expected_ctc_lpa, hourly_rate_inr, monthly_rate_inr, status, is_verified, projects_completed)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (person_id) DO UPDATE SET
                    experience_years = EXCLUDED.experience_years,
                    expected_ctc_lpa = EXCLUDED.expected_ctc_lpa,
                    hourly_rate_inr = EXCLUDED.hourly_rate_inr,
                    monthly_rate_inr = EXCLUDED.monthly_rate_inr,
                    status = EXCLUDED.status,
                    is_verified = EXCLUDED.is_verified,
                    projects_completed = EXCLUDED.projects_completed,
                    updated_at = CURRENT_TIMESTAMP;
                """,
                (pid, prof["exp"], prof["ctc_lpa"], prof["hourly_rate"], prof["monthly_rate"], prof["status"], prof["is_verified"], prof["projects"])
            )
            
            conn.execute(
                """
                UPDATE persons
                SET primary_email = COALESCE(primary_email, %s),
                    primary_phone = COALESCE(primary_phone, %s)
                WHERE person_id = %s;
                """,
                (prof["primary_email"], prof["primary_phone"], pid)
            )
