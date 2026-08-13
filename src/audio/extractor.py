import os
import uuid
import io
import math
from datetime import datetime
from pydub import AudioSegment

from src.database.connection import get_connection, PROJECT_ROOT
from src.ingestion.normalizer import normalize_name, normalize_phone

UPLOAD_DIR = os.path.join(PROJECT_ROOT, "data", "audio_uploads")
MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB

SUPPORTED_EXTENSIONS = {".wav", ".mp3", ".m4a", ".ogg", ".webm", ".flac", ".aac"}

def lookup_candidate(raw_name, raw_phone, conn=None):
    """
    Looks up canonical person_id from Task 1 database matching the normalized phone number.
    Rules:
    - Exactly 1 match -> returns (person_id, None)
    - 0 matches -> returns (None, "Candidate not found. Please verify the phone number.")
    - >1 matches -> returns (None, "Ambiguous candidates found for this phone number.")
    """
    cleaned_name = normalize_name(raw_name or "")
    cleaned_phone = normalize_phone(raw_phone or "")
    
    if not cleaned_name:
        return None, "Candidate name cannot be empty."
        
    if not cleaned_phone or len(cleaned_phone) != 10:
        return None, "Invalid phone number format. Please enter a valid 10-digit phone number."

    close_conn = False
    if conn is None:
        conn = get_connection()
        close_conn = True

    try:
        # 1. Search person_phones table
        cursor = conn.execute("SELECT DISTINCT person_id FROM person_phones WHERE phone_number = %s;", (cleaned_phone,))
        rows = cursor.fetchall()
        pids = {r["person_id"] for r in rows}

        # 2. Search persons primary_phone if not found
        if not pids:
            cursor2 = conn.execute("SELECT person_id FROM persons WHERE primary_phone = %s;", (cleaned_phone,))
            rows2 = cursor2.fetchall()
            pids = {r["person_id"] for r in rows2}

        if len(pids) == 0:
            return None, f"Candidate not found for phone number '{cleaned_phone}'. Please verify the phone number."
        elif len(pids) > 1:
            return None, f"Ambiguity detected: Multiple candidate profiles ({len(pids)}) share phone number '{cleaned_phone}'."
        else:
            person_id = list(pids)[0]
            return person_id, None
    finally:
        if close_conn:
            conn.close()

def extract_audio_metadata(file_bytes, original_filename):
    """
    Extracts acoustic properties from audio bytes using pydub.
    Calculates:
    - duration_seconds
    - sample_rate_khz
    - bitrate_kbps
    - loudness_db
    """
    if not file_bytes:
        raise ValueError("Audio file is empty.")

    file_size_bytes = len(file_bytes)
    if file_size_bytes > MAX_FILE_SIZE_BYTES:
        raise ValueError(f"Audio file size ({file_size_bytes / (1024*1024):.2f} MB) exceeds maximum allowed limit of 25 MB.")

    ext = os.path.splitext(original_filename)[1].lower()
    if ext and ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported audio format '{ext}'. Supported formats: {', '.join(sorted(SUPPORTED_EXTENSIONS))}")

    # Decode audio using pydub
    try:
        file_stream = io.BytesIO(file_bytes)
        format_param = ext.lstrip(".") if ext else None
        if format_param == "m4a":
            format_param = "mp4"
            
        audio = AudioSegment.from_file(file_stream, format=format_param)
    except Exception as e:
        raise ValueError(f"Failed to decode audio file. File may be corrupted or unsupported format. ({str(e)})")

    duration_seconds = len(audio) / 1000.0
    if duration_seconds <= 0:
        raise ValueError("Invalid audio file: duration is zero seconds.")

    sample_rate_khz = audio.frame_rate / 1000.0
    
    # Calculate bitrate (kbps) = (total file bits) / duration seconds / 1000
    bitrate_kbps = (file_size_bytes * 8.0) / duration_seconds / 1000.0
    
    # Extract loudness (dBFS). If audio is totally silent, dBFS is -inf. Handle -inf gracefully.
    loudness_db = audio.dBFS
    if math.isinf(loudness_db) or math.isnan(loudness_db):
        loudness_db = -99.0

    return {
        "original_filename": original_filename,
        "file_size_bytes": file_size_bytes,
        "duration_seconds": round(duration_seconds, 3),
        "sample_rate_khz": round(sample_rate_khz, 2),
        "bitrate_kbps": round(bitrate_kbps, 2),
        "loudness_db": round(loudness_db, 2)
    }

def process_and_store_submission(person_id, file_bytes, original_filename, conn=None):
    """
    Extracts metadata, saves audio file safely to data/audio_uploads/,
    and inserts submission record into PostgreSQL.
    Rolls back disk file if database insertion fails.
    """
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    
    # 1. Extract metadata first before saving
    metadata = extract_audio_metadata(file_bytes, original_filename)
    
    # 2. Generate safe unique filename
    ext = os.path.splitext(original_filename)[1].lower() or ".wav"
    timestamp_str = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
    unique_suffix = uuid.uuid4().hex[:8]
    safe_filename = f"audio_{person_id}_{timestamp_str}_{unique_suffix}{ext}"
    abs_file_path = os.path.join(UPLOAD_DIR, safe_filename)
    rel_file_path = os.path.relpath(abs_file_path, PROJECT_ROOT).replace("\\", "/")
    
    # 3. Write file to disk
    with open(abs_file_path, "wb") as f:
        f.write(file_bytes)

    # 4. Database Transaction
    close_conn = False
    if conn is None:
        conn = get_connection()
        close_conn = True

    try:
        sql = """
            INSERT INTO audio_submissions (
                person_id, original_filename, file_path, file_size_bytes,
                duration_seconds, sample_rate_khz, bitrate_kbps, loudness_db
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
        """
        cursor = conn.execute(sql, (
            person_id,
            original_filename,
            rel_file_path,
            metadata["file_size_bytes"],
            metadata["duration_seconds"],
            metadata["sample_rate_khz"],
            metadata["bitrate_kbps"],
            metadata["loudness_db"]
        ))
        submission_id = cursor.lastrowid
        conn.commit()
        
        metadata["submission_id"] = submission_id
        metadata["file_path"] = rel_file_path
        return metadata
    except Exception as e:
        conn.rollback()
        # Clean up orphaned disk file if DB write failed
        if os.path.exists(abs_file_path):
            try:
                os.remove(abs_file_path)
            except Exception:
                pass
        raise e
    finally:
        if close_conn:
            conn.close()

def get_all_submissions(conn=None):
    """
    Retrieves all audio submissions ordered by latest created_at first.
    Joins persons and person_phones to provide complete candidate metadata.
    """
    close_conn = False
    if conn is None:
        conn = get_connection()
        close_conn = True

    try:
        sql = """
            SELECT 
                s.submission_id,
                s.person_id,
                p.canonical_name,
                COALESCE(ph.phone_number, p.primary_phone, '') AS phone_number,
                s.original_filename,
                s.file_path,
                s.file_size_bytes,
                s.duration_seconds,
                s.sample_rate_khz,
                s.bitrate_kbps,
                s.loudness_db,
                s.created_at
            FROM audio_submissions s
            JOIN persons p ON p.person_id = s.person_id
            LEFT JOIN person_phones ph ON ph.person_id = p.person_id AND ph.is_primary = TRUE
            ORDER BY s.created_at DESC, s.submission_id DESC;
        """
        cursor = conn.execute(sql)
        rows = cursor.fetchall()
        return rows
    finally:
        if close_conn:
            conn.close()
