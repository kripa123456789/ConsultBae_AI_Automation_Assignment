"""
Database schema and relational constraint unit tests for Task 2 ai_skill_classifications table.
Note: This test file validates PostgreSQL table structure, UNIQUE constraints, and FOREIGN KEY constraints only.
It does not execute or validate the external n8n no-code workflow.
"""

import os
import tempfile
import pytest

from src.database.connection import get_connection
from src.database.models import init_db, drop_all_tables
from src.app.main import run_pipeline

class TestTask2DatabaseSchema:
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

    def test_ai_skill_classifications_table_structure(self, test_db):
        conn, _ = test_db
        # Verify table exists and has expected columns
        cursor = conn.execute(
            """
            INSERT INTO persons (canonical_name, primary_email, primary_phone, canonical_city)
            VALUES ('Test Candidate', 'test.candidate@example.com', '9000000999', 'Bengaluru');
            """
        )
        pid = cursor.lastrowid
        assert pid > 0

        # Insert a valid classification row
        conn.execute(
            """
            INSERT INTO ai_skill_classifications (person_id, category, confidence, reason, model)
            VALUES (%s, %s, %s, %s, %s);
            """,
            (pid, 'automation-heavy', 0.95, 'Expert in n8n and Python automation', 'Gemini')
        )
        row = conn.execute("SELECT * FROM ai_skill_classifications WHERE person_id = %s;", (pid,)).fetchone()
        assert row is not None
        assert row["category"] == "automation-heavy"
        assert abs(row["confidence"] - 0.95) < 0.001
        assert row["reason"] == "Expert in n8n and Python automation"
        assert row["model"] == "Gemini"

    def test_ai_skill_classifications_unique_person_id_constraint(self, test_db):
        conn, _ = test_db
        cursor = conn.execute(
            """
            INSERT INTO persons (canonical_name, primary_email, primary_phone, canonical_city)
            VALUES ('Unique Constraint Candidate', 'unique.candidate@example.com', '9000000998', 'Noida');
            """
        )
        pid = cursor.lastrowid

        conn.execute(
            """
            INSERT INTO ai_skill_classifications (person_id, category, confidence, reason, model)
            VALUES (%s, %s, %s, %s, %s);
            """,
            (pid, 'web-dev', 0.90, 'React and Node expertise', 'Gemini')
        )

        # Second insert for the exact same person_id must fail unique constraint
        with pytest.raises(Exception):
            conn.execute(
                """
                INSERT INTO ai_skill_classifications (person_id, category, confidence, reason, model)
                VALUES (%s, %s, %s, %s, %s);
                """,
                (pid, 'data', 0.85, 'Pandas and SQL expertise', 'Gemini')
            )

    def test_ai_skill_classifications_foreign_key_constraint(self, test_db):
        conn, _ = test_db
        invalid_pid = 999999
        with pytest.raises(Exception):
            conn.execute(
                """
                INSERT INTO ai_skill_classifications (person_id, category, confidence, reason, model)
                VALUES (%s, %s, %s, %s, %s);
                """,
                (invalid_pid, 'data', 0.90, 'Invalid person reference', 'Gemini')
            )
