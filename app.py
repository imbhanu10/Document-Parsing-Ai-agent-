import streamlit as st
import json
import os
import tempfile
import google.generativeai as genai
from agent import run_agent, save_output

# ------------------------
# HARDCODE YOUR API KEY HERE
# ------------------------
GEMINI_API_KEY = "AIzaSyCdXe87cfAd3daQQ8RFhLUBKHCRU2BOqIw"   # <<< REPLACE THIS ONLY
genai.configure(api_key=GEMINI_API_KEY)
os.environ["GOOGLE_API_KEY"] = GEMINI_API_KEY

# ----------------------------------------
# Page config (changed title per your request)
# ----------------------------------------
st.set_page_config(
    page_title="AI Document Parser",
    page_icon="📄",
    layout="wide"
)

# Custom CSS (same styling)
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 1rem;
    }
    .status-pass {
        background-color: #d4edda;
        color: #155724;
        padding: 0.5rem;
        border-radius: 5px;
        font-weight: bold;
    }
    .status-fail {
        background-color: #f8d7da;
        color: #721c24;
        padding: 0.5rem;
        border-radius: 5px;
        font-weight: bold;
    }
    .confidence-high { color: #28a745; font-weight: bold; }
    .confidence-medium { color: #ffc107; font-weight: bold; }
    .confidence-low { color: #dc3545; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# ---------------------------
# Initialize session state
# ---------------------------
if "results" not in st.session_state:
    st.session_state.results = None

# ---------------------------
# HEADER (updated)
# ---------------------------
st.markdown('<div class="main-header">📄 AI Document Parser</div>', unsafe_allow_html=True)

# ---------------------------
# Removed Sidebar completely
# ---------------------------
st.sidebar.text("")  # Empty sidebar placeholder to avoid layout shift

# ---------------------------
# MAIN TABS
# ---------------------------
tab1, tab2, tab3, tab4 = st.tabs(["📤 Upload & Analyze", "📝 Summary", "🔍 Sections", "✅ Rule Checks"])

# --------------------------------------------------------------------
# TAB 1 — Upload & Analyze
# --------------------------------------------------------------------
with tab1:
    st.header("Upload PDF Document")

    uploaded_file = st.file_uploader(
        "Choose a PDF document",
        type=['pdf']
    )

    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        if st.button("🚀 Analyze Document", type="primary"):
            if not uploaded_file:
                st.error("⚠️ Please upload a PDF file first")
            else:
                # Save temporary file
                with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
                    tmp_file.write(uploaded_file.getvalue())
                    tmp_path = tmp_file.name

                progress_bar = st.progress(0)
                status_text = st.empty()

                def update_progress(msg, progress):
                    status_text.text(msg)
                    progress_bar.progress(int(progress))

                try:
                    # Run agent
                    with st.spinner("Analyzing document..."):
                        results = run_agent(tmp_path, progress_callback=update_progress)
                        st.session_state.results = results
                        output_file = save_output(results)

                    progress_bar.empty()
                    status_text.empty()
                    st.success("✅ Analysis complete!")

                    # Download JSON
                    with open(output_file, 'rb') as f:
                        file_bytes = f.read()
                        st.download_button(
                            label="📥 Download JSON Report",
                            data=f.read(),
                            file_name="analysis.json",
                            mime="application/json"
                        )

                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")

                finally:
                    if os.path.exists(tmp_path):
                        os.unlink(tmp_path)

# --------------------------------------------------------------------
# TAB 2 — Summary
# --------------------------------------------------------------------
with tab2:
    st.header("📝 Summary")
    if st.session_state.results:
        st.write(st.session_state.results.get("summary", "No summary generated"))
    else:
        st.info("👈 Upload a document to see its summary")

# --------------------------------------------------------------------
# TAB 3 — Sections
# --------------------------------------------------------------------
with tab3:
    st.header("🔍 Key Legislative Sections")

    if st.session_state.results:
        sections = st.session_state.results.get("sections", {})
        if "error" in sections:
            st.error(sections["error"])
        else:
            for key, value in sections.items():
                with st.expander(key.upper()):
                    st.write(value)
    else:
        st.info("👈 Upload a document to view extracted sections")

# --------------------------------------------------------------------
# TAB 4 — Rule Checks
# --------------------------------------------------------------------
with tab4:
    st.header("✅ Rule Compliance Checks")

    if st.session_state.results:
        rules = st.session_state.results.get("rules", [])
        
        passed = sum(1 for r in rules if r.get("status") == "pass")
        failed = sum(1 for r in rules if r.get("status") == "fail")

        col1, col2 = st.columns(2)
        col1.metric("Passed", passed)
        col2.metric("Failed", failed)

        st.divider()

        for r in rules:
            st.subheader(r.get("rule"))
            st.write(f"**Evidence:** {r.get('evidence')}")
            st.write(f"**Confidence:** {r.get('confidence')}%")
            st.write("---")

    else:
        st.info("👈 Upload a document to run rule checks")
