import sys
import os
import argparse

from src.database.connection import get_connection
from src.database.models import init_db, drop_all_tables
from src.ingestion.raw_ingestor import ingest_source1, ingest_source2, ingest_source3
from src.matching.resolver import resolve_and_load

def run_pipeline(reset=False, db_path=None):
    """
    Executes Task 1 Data Ingestion and Entity Resolution Pipeline.
    Idempotent across repeated executions.
    """
    print("==================================================")
    print("STARTING TASK 1 PIPELINE EXECUTION")
    print("==================================================")
    
    if reset:
        print("Reset flag enabled: Dropping existing tables...")
        drop_all_tables(db_path)
        init_db(db_path)
    else:
        init_db(db_path)
    
    conn = get_connection(db_path)
    
    try:
        # Check if pipeline has already been run for these files to ensure idempotency
        existing_mappings = conn.execute("SELECT COUNT(*) as cnt FROM person_source_mappings;").fetchone()["cnt"]
        if existing_mappings > 0 and not reset:
            print("Pipeline has already been executed on current database state.")
            print("Idempotency guardrail active: Retaining existing database state without duplicate insertion.")
        else:
            print("Ingesting Source 1 (Naukri Applicants)...")
            s1_records = ingest_source1(conn)
            print(f"  -> Ingested {len(s1_records)} records from Source 1.")
            
            print("Ingesting Source 2 (Gig Workers)...")
            s2_records = ingest_source2(conn)
            print(f"  -> Ingested {len(s2_records)} records from Source 2.")
            
            print("Ingesting Source 3 (CBNexus Contacts)...")
            s3_records = ingest_source3(conn)
            print(f"  -> Ingested {len(s3_records)} records from Source 3.")
            
            print("\nExecuting Entity Resolution & Source Lineage Mapping...")
            resolve_and_load(conn, s1_records, s2_records, s3_records)
        
        # Calculate summary statistics
        person_count = conn.execute("SELECT COUNT(*) as cnt FROM persons;").fetchone()["cnt"]
        mapping_count = conn.execute("SELECT COUNT(*) as cnt FROM person_source_mappings;").fetchone()["cnt"]
        quarantine_count = conn.execute("SELECT COUNT(*) as cnt FROM ingestion_quarantine_log;").fetchone()["cnt"]
        conflict_count = conn.execute("SELECT COUNT(*) as cnt FROM entity_conflicts;").fetchone()["cnt"]
        
        raw1 = conn.execute("SELECT COUNT(*) as cnt FROM raw_source1_naukri;").fetchone()["cnt"]
        raw2 = conn.execute("SELECT COUNT(*) as cnt FROM raw_source2_gig_workers;").fetchone()["cnt"]
        raw3 = conn.execute("SELECT COUNT(*) as cnt FROM raw_source3_cbnexus;").fetchone()["cnt"]
        total_raw = raw1 + raw2 + raw3
        
        print("\n==================================================")
        print("TASK 1 PIPELINE EXECUTION COMPLETED SUCCESSFULLY")
        print("==================================================")
        print(f"Total Raw Records Ingested : {total_raw}")
        print(f"Quarantined Anomalies      : {quarantine_count}")
        print(f"Canonical Person Entities  : {person_count}")
        print(f"Source Lineage Mappings    : {mapping_count}")
        print(f"Entity Conflicts Logged    : {conflict_count}")
        print("==================================================\n")
        
        return {
            "total_raw": total_raw,
            "quarantine": quarantine_count,
            "persons": person_count,
            "mappings": mapping_count,
            "conflicts": conflict_count
        }
        
    finally:
        conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ConsultBae Task 1 PostgreSQL Ingestion & Entity Resolution Pipeline")
    parser.add_argument("--reset", action="store_true", help="Reset database schema before running")
    args = parser.parse_args()
    
    run_pipeline(reset=args.reset)
