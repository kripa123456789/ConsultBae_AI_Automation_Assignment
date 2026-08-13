import os
import sys
import streamlit as st

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.audio.extractor import (
    lookup_candidate,
    extract_audio_metadata,
    process_and_store_submission,
    get_all_submissions
)

st.set_page_config(
    page_title="ConsultBae — Audio Collection App",
    page_icon="🎙️",
    layout="wide"
)

st.title("🎙️ ConsultBae — Audio Collection App")
st.caption("Task 3 mini audio collection tool: Candidate submission, audio storage, identity linkage, and acoustic metadata extraction.")

tab_submit, tab_gallery = st.tabs(["📤 Submit Audio", "🎧 Submissions Gallery"])

with tab_submit:
    st.markdown("#### Candidate Audio Submission")
    
    with st.form("audio_submission_form", clear_on_submit=False):
        col1, col2 = st.columns(2)
        with col1:
            candidate_name = st.text_input("Candidate Name", placeholder="e.g. Varun Jain")
        with col2:
            phone_number = st.text_input("Phone Number", placeholder="e.g. 9000000263")
            
        recorded_audio = None
        if hasattr(st, "audio_input"):
            col_up, col_rec = st.columns(2)
            with col_up:
                uploaded_file = st.file_uploader(
                    "Upload Audio File",
                    type=["wav", "mp3", "m4a", "ogg", "webm", "flac", "aac"],
                    help="Supported formats: WAV, MP3, M4A, OGG, WEBM (Max size 25 MB)"
                )
            with col_rec:
                recorded_audio = st.audio_input("Or Record Audio directly in browser")
        else:
            uploaded_file = st.file_uploader(
                "Upload Audio File",
                type=["wav", "mp3", "m4a", "ogg", "webm", "flac", "aac"],
                help="Supported formats: WAV, MP3, M4A, OGG, WEBM (Max size 25 MB)"
            )
            
        submitted = st.form_submit_button("Submit & Analyze Audio", type="primary", use_container_width=True)

    if submitted:
        if not candidate_name.strip():
            st.error("Please enter candidate name.")
        elif not phone_number.strip():
            st.error("Please enter phone number.")
        elif uploaded_file is None and recorded_audio is None:
            st.error("Please upload an audio file or record audio in the browser.")
        else:
            with st.spinner("Processing candidate identity lookup & extracting audio metadata..."):
                # 1. Candidate lookup
                person_id, lookup_error = lookup_candidate(candidate_name, phone_number)
                
                if lookup_error:
                    st.error(f"❌ Identity Validation Error: {lookup_error}")
                else:
                    # 2. Get audio bytes and filename
                    if uploaded_file is not None:
                        file_bytes = uploaded_file.getvalue()
                        filename = uploaded_file.name
                    else:
                        file_bytes = recorded_audio.getvalue()
                        filename = f"recorded_audio_{phone_number.strip()}.wav"

                    try:
                        # 3. Process & store submission
                        result = process_and_store_submission(person_id, file_bytes, filename)
                        st.success(f"✅ Audio submission successfully recorded and linked to Candidate ID #{person_id}!")
                        
                        m1, m2, m3, m4 = st.columns(4)
                        m1.metric("Duration", f"{result['duration_seconds']:.2f} s")
                        m2.metric("Sample Rate", f"{result['sample_rate_khz']:.1f} kHz")
                        m3.metric("Bitrate", f"{result['bitrate_kbps']:.1f} kbps")
                        m4.metric("Loudness", f"{result['loudness_db']:.1f} dBFS")
                        
                        st.caption(f"Stored File Path: `{result['file_path']}`")
                    except Exception as e:
                        st.error(f"❌ Audio Processing Error: {str(e)}")

with tab_gallery:
    col_hdr, col_btn = st.columns([3, 1])
    with col_hdr:
        st.markdown("#### Audio Submissions Gallery")
    with col_btn:
        if st.button("🔄 Refresh Submissions", use_container_width=True):
            st.rerun()

    submissions = get_all_submissions()
    
    if not submissions:
        st.info("No audio submissions found in database.")
    else:
        st.caption(f"Total Submissions: {len(submissions)}")
        
        for sub in submissions:
            with st.container(border=True):
                st.markdown(
                    f"**Submission #{sub['submission_id']}** — **{sub['canonical_name']}** | "
                    f"Phone: `{sub['phone_number']}` | Candidate ID: `#{sub['person_id']}` | "
                    f"Submitted: `{sub['created_at']}`"
                )
                
                c_player, c_metrics = st.columns([1.2, 1.8])
                with c_player:
                    abs_audio_path = os.path.join(PROJECT_ROOT, sub['file_path'])
                    if os.path.exists(abs_audio_path):
                        st.audio(abs_audio_path)
                    else:
                        st.warning(f"File missing: `{sub['file_path']}`")
                
                with c_metrics:
                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("Duration", f"{sub['duration_seconds']:.2f} s")
                    m2.metric("Sample Rate", f"{sub['sample_rate_khz']:.1f} kHz")
                    m3.metric("Bitrate", f"{sub['bitrate_kbps']:.1f} kbps")
                    m4.metric("Loudness", f"{sub['loudness_db']:.1f} dBFS")
