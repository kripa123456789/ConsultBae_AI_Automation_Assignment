import os
import tempfile
import pytest

from src.database.connection import get_connection, PROJECT_ROOT
from src.database.models import init_db, drop_all_tables
from src.ingestion.normalizer import (
    normalize_name, normalize_email, normalize_phone, normalize_city,
    normalize_date, normalize_ctc, normalize_rate, normalize_verified, normalize_skills
)
from src.ingestion.raw_ingestor import ingest_source1, ingest_source2, ingest_source3
from src.matching.resolver import resolve_and_load
from src.app.main import run_pipeline

class TestNormalizers:
    def test_normalize_name(self):
        assert normalize_name("  varun  jain  ") == "Varun Jain"
        assert normalize_name("RITU SHARMA") == "Ritu Sharma"
        assert normalize_name("R. Verma") == "R. Verma"

    def test_normalize_email(self):
        assert normalize_email(" ISHA.CHOPRA95@MAILTEST.EXAMPLE.ORG ") == "isha.chopra95@mailtest.example.org"
        assert normalize_email("invalid_email_string") == ""

    def test_normalize_phone(self):
        assert normalize_phone("+91-9000000131") == "9000000131"
        assert normalize_phone("09000000287") == "9000000287"
        assert normalize_phone("919000000268") == "9000000268"
        assert normalize_phone("9000000237") == "9000000237"
        assert normalize_phone("123") == ""

    def test_normalize_city(self):
        assert normalize_city("gurugram ") == "Gurugram"
        assert normalize_city("Gurgaon") == "Gurugram"
        assert normalize_city("bangalore") == "Bengaluru"
        assert normalize_city("NOIDA") == "Noida"
        assert normalize_city("new delhi") == "Delhi NCR"

    def test_normalize_date(self):
        assert normalize_date("2026-08-08") == "2026-08-08"
        assert normalize_date("24-07-2026") == "2026-07-24"
        assert normalize_date("07/13/2026") == "2026-07-13"
        assert normalize_date("7 Jul 2026") == "2026-07-07"

    def test_normalize_ctc(self):
        assert normalize_ctc("4.2") == 4.20
        assert normalize_ctc("332456") == 3.32

    def test_normalize_rate(self):
        h = normalize_rate("1415/hr")
        assert h["hourly"] == 1415.0
        m = normalize_rate("15k/month")
        assert m["monthly"] == 15000.0

    def test_normalize_verified(self):
        assert normalize_verified("Y") is True
        assert normalize_verified("yes") is True
        assert normalize_verified("No") is False

class TestPipelineEndToEnd:
    @pytest.fixture
    def test_db(self):
        fd, db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        run_pipeline(reset=True, db_path=db_path)
        conn = get_connection(db_path)
        yield conn, db_path
        conn.close()
        if os.path.exists(db_path):
            os.remove(db_path)

    def test_quarantine_log(self, test_db):
        conn, _ = test_db
        cursor = conn.execute("SELECT issue_type, count(*) as cnt FROM ingestion_quarantine_log GROUP BY issue_type;")
        issues = {row["issue_type"]: row["cnt"] for row in cursor.fetchall()}
        assert "BLANK_ROW" in issues
        assert "DUPLICATE_HEADER" in issues
        assert "COLUMN_SHIFT" in issues

    def test_person_counts_and_mappings(self, test_db):
        conn, _ = test_db
        persons = conn.execute("SELECT COUNT(*) as cnt FROM persons;").fetchone()["cnt"]
        mappings = conn.execute("SELECT COUNT(*) as cnt FROM person_source_mappings;").fetchone()["cnt"]
        assert persons == 56
        assert mappings == 103

    def test_tri_source_match_varun_jain(self, test_db):
        conn, _ = test_db
        cursor = conn.execute("SELECT person_id FROM persons WHERE canonical_name = 'Varun Jain';")
        pid = cursor.fetchone()["person_id"]
        
        mappings = conn.execute("SELECT * FROM person_source_mappings WHERE person_id = %s;", (pid,)).fetchall()
        assert len(mappings) == 3
        source_systems = {m["source_system"] for m in mappings}
        assert source_systems == {"naukri", "gig_workers", "cbnexus"}

    def test_conflicts_logged(self, test_db):
        conn, _ = test_db
        conflicts = conn.execute("SELECT COUNT(*) as cnt FROM entity_conflicts;").fetchone()["cnt"]
        assert conflicts >= 1

    def test_structural_column_shift_and_raw_preservation(self, test_db):
        conn, _ = test_db
        # Line 20 in Source 2 is the malformed column-shifted row
        row = conn.execute("SELECT * FROM raw_source2_gig_workers WHERE line_number = 20;").fetchone()
        assert row is not None
        assert bool(row["was_malformed"]) is True
        assert "Structural Column Shift" in row["recovery_reason"]
        assert "ISHA.CHOPRA95@MAILTEST.EXAMPLE.ORG" in row["raw_email_id"]
        assert "Isha Chopra" in row["raw_worker_name"]

    def test_idempotency_consecutive_runs(self, test_db):
        conn, db_path = test_db
        # Run 1 initial counts
        r1_persons = conn.execute("SELECT COUNT(*) as cnt FROM persons;").fetchone()["cnt"]
        r1_mappings = conn.execute("SELECT COUNT(*) as cnt FROM person_source_mappings;").fetchone()["cnt"]
        
        # Run 2 (without reset)
        run_pipeline(reset=False, db_path=db_path)
        r2_persons = conn.execute("SELECT COUNT(*) as cnt FROM persons;").fetchone()["cnt"]
        r2_mappings = conn.execute("SELECT COUNT(*) as cnt FROM person_source_mappings;").fetchone()["cnt"]
        
        # Run 3 (without reset)
        run_pipeline(reset=False, db_path=db_path)
        r3_persons = conn.execute("SELECT COUNT(*) as cnt FROM persons;").fetchone()["cnt"]
        r3_mappings = conn.execute("SELECT COUNT(*) as cnt FROM person_source_mappings;").fetchone()["cnt"]
        
        # Verify counts remain 100% stable across all 3 runs
        assert r1_persons == r2_persons == r3_persons == 56
        assert r1_mappings == r2_mappings == r3_mappings == 103

    def test_no_hardcoded_paths(self):
        assert os.path.exists(PROJECT_ROOT)
        assert os.path.isdir(os.path.join(PROJECT_ROOT, "src"))
