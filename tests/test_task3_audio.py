import os
import io
import wave
import tempfile
import pytest

from src.database.connection import get_connection, PROJECT_ROOT
from src.database.models import init_db, drop_all_tables
from src.app.main import run_pipeline
from src.audio.extractor import (
    lookup_candidate,
    extract_audio_metadata,
    process_and_store_submission,
    get_all_submissions,
    UPLOAD_DIR
)

def create_synthetic_wav_bytes(duration_sec=1.0, sample_rate=44100, num_channels=1):
    """Generates valid uncompressed PCM WAV bytes for testing."""
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wav_file:
        wav_file.setnchannels(num_channels)
        wav_file.setsampwidth(2)  # 16-bit PCM
        wav_file.setframerate(sample_rate)
        # 100 Hz tone
        num_frames = int(duration_sec * sample_rate)
        frames = bytearray()
        for i in range(num_frames):
            val = int(10000 * (i % 44) / 44)  # simple saw wave
            frames.extend(val.to_bytes(2, byteorder='little', signed=True))
        wav_file.writeframes(frames)
    return buf.getvalue()

class TestTask3AudioApp:
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

    def test_candidate_lookup_existing(self, test_db):
        conn, _ = test_db
        # Varun Jain is a known candidate from Task 1 (phone: 9000000263)
        pid, error = lookup_candidate("Varun Jain", "+91-9000000263", conn=conn)
        assert error is None
        assert pid is not None
        assert pid > 0

    def test_candidate_lookup_unknown_rejection(self, test_db):
        conn, _ = test_db
        # Unknown phone number
        pid, error = lookup_candidate("Nonexistent User", "9999999999", conn=conn)
        assert pid is None
        assert "Candidate not found" in error

    def test_candidate_lookup_invalid_phone(self, test_db):
        conn, _ = test_db
        pid, error = lookup_candidate("Test User", "123", conn=conn)
        assert pid is None
        assert "Invalid phone number format" in error

    def test_extract_audio_metadata_valid_wav(self):
        wav_bytes = create_synthetic_wav_bytes(duration_sec=1.5, sample_rate=44100)
        meta = extract_audio_metadata(wav_bytes, "test_recording.wav")
        
        assert meta["original_filename"] == "test_recording.wav"
        assert abs(meta["duration_seconds"] - 1.5) < 0.1
        assert meta["sample_rate_khz"] == 44.1
        assert meta["bitrate_kbps"] > 0
        assert meta["loudness_db"] <= 0.0

    def test_extract_audio_metadata_corrupt_file(self):
        corrupt_bytes = b"NOT_AN_AUDIO_FILE_HEADER_DATA"
        with pytest.raises(ValueError) as excinfo:
            extract_audio_metadata(corrupt_bytes, "bad.wav")
        assert "Failed to decode audio file" in str(excinfo.value)

    def test_extract_audio_metadata_file_size_exceeded(self):
        huge_bytes = b"0" * (26 * 1024 * 1024)  # 26 MB
        with pytest.raises(ValueError) as excinfo:
            extract_audio_metadata(huge_bytes, "huge.wav")
        assert "exceeds maximum allowed limit" in str(excinfo.value)

    def test_process_and_store_submission_success(self, test_db):
        conn, _ = test_db
        pid, _ = lookup_candidate("Varun Jain", "9000000263", conn=conn)
        
        wav_bytes = create_synthetic_wav_bytes(duration_sec=2.0, sample_rate=44100)
        res = process_and_store_submission(pid, wav_bytes, "applicant_sample.wav", conn=conn)
        
        assert res["submission_id"] > 0
        assert os.path.exists(os.path.join(PROJECT_ROOT, res["file_path"]))
        
        # Verify in database
        row = conn.execute("SELECT * FROM audio_submissions WHERE submission_id = %s;", (res["submission_id"],)).fetchone()
        assert row is not None
        assert row["person_id"] == pid
        assert row["original_filename"] == "applicant_sample.wav"
        assert abs(row["duration_seconds"] - 2.0) < 0.1
        assert row["sample_rate_khz"] == 44.1
        
        # Clean up test audio file
        abs_p = os.path.join(PROJECT_ROOT, res["file_path"])
        if os.path.exists(abs_p):
            os.remove(abs_p)

    def test_get_all_submissions_retrieval(self, test_db):
        conn, _ = test_db
        pid, _ = lookup_candidate("Varun Jain", "9000000263", conn=conn)
        
        wav_bytes = create_synthetic_wav_bytes(duration_sec=1.0, sample_rate=44100)
        res = process_and_store_submission(pid, wav_bytes, "gallery_sample.wav", conn=conn)
        
        submissions = get_all_submissions(conn=conn)
        assert len(submissions) >= 1
        top = submissions[0]
        assert top["canonical_name"] == "Varun Jain"
        assert top["original_filename"] == "gallery_sample.wav"
        
        # Clean up test file
        abs_p = os.path.join(PROJECT_ROOT, res["file_path"])
        if os.path.exists(abs_p):
            os.remove(abs_p)

    def test_process_and_store_submission_db_failure_cleanup(self, test_db):
        conn, _ = test_db
        invalid_pid = 999999  # Invalid person_id causing FK constraint violation
        wav_bytes = create_synthetic_wav_bytes(duration_sec=1.0, sample_rate=44100)
        
        with pytest.raises(Exception):
            process_and_store_submission(invalid_pid, wav_bytes, "orphan_test.wav", conn=conn)
            
        # Verify no orphan files starting with audio_999999_ exist in UPLOAD_DIR
        if os.path.exists(UPLOAD_DIR):
            orphans = [f for f in os.listdir(UPLOAD_DIR) if f.startswith("audio_999999_")]
            assert len(orphans) == 0, f"Found orphaned file(s) on disk: {orphans}"
