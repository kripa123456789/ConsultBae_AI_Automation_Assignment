import os
from src.database.connection import get_connection, PROJECT_ROOT

SCHEMA_FILE = os.path.join(PROJECT_ROOT, "database", "schema.sql")

def init_db(db_path=None):
    """Initializes the PostgreSQL database schema from schema.sql."""
    conn = get_connection(db_path)
    with open(SCHEMA_FILE, "r", encoding="utf-8") as f:
        schema_sql = f.read()
    
    # Split statements by semicolon
    statements = [stmt.strip() for stmt in schema_sql.split(";") if stmt.strip()]
    with conn:
        for stmt in statements:
            conn.execute(stmt)
    conn.close()

def drop_all_tables(db_path=None):
    """Drops all tables for clean reset capability."""
    conn = get_connection(db_path)
    tables = [
        "entity_conflicts", "candidate_skills", "person_phones", "person_emails",
        "candidate_profiles", "person_source_mappings", "persons",
        "ingestion_quarantine_log", "raw_source3_cbnexus",
        "raw_source2_gig_workers", "raw_source1_naukri"
    ]
    with conn:
        for t in tables:
            conn.execute(f"DROP TABLE IF EXISTS {t} CASCADE;")
    conn.close()
