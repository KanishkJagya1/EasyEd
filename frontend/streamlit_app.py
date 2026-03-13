"""
Ease-Edu — AI Answer Sheet Evaluation Platform
Streamlit frontend that talks to the Flask backend.
"""

import io
import json
import time
import requests
import streamlit as st

# ── Config ─────────────────────────────────────────────────────────────────────
BACKEND = "http://localhost:5050"

st.set_page_config(
    page_title="Ease-Edu | AI Exam Evaluator",
    page_icon="📝",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Session helpers ────────────────────────────────────────────────────────────
def ss(key, default=None):
    return st.session_state.get(key, default)

def api(method, path, **kwargs):
    """Wrapper that carries the session cookie automatically."""
    cookies = ss("cookies", {})
    try:
        r = requests.request(method, BACKEND + path, cookies=cookies, timeout=120, **kwargs)
        # persist any new cookies
        if r.cookies:
            merged = dict(cookies)
            merged.update(dict(r.cookies))
            st.session_state["cookies"] = merged
        return r
    except requests.exceptions.ConnectionError:
        st.error("⚠️ Cannot reach the backend. Make sure Flask is running on port 5050.")
        return None

# ── Custom CSS ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* ── Global ── */
body { font-family: 'Inter', sans-serif; }
[data-testid="stSidebar"] { background: #0f172a; }
[data-testid="stSidebar"] * { color: #e2e8f0 !important; }

/* ── Cards ── */
.card {
    background: white;
    border-radius: 12px;
    padding: 1.5rem;
    box-shadow: 0 1px 3px rgba(0,0,0,.08), 0 4px 16px rgba(0,0,0,.04);
    margin-bottom: 1rem;
}
.metric-card {
    background: linear-gradient(135deg,#6366f1,#8b5cf6);
    color: white !important;
    border-radius: 12px;
    padding: 1.25rem 1.5rem;
    text-align: center;
}
.metric-card h2 { font-size: 2.2rem; margin: 0; }
.metric-card p  { margin: 0; opacity: .85; font-size:.9rem; }

/* ── Step badges ── */
.step-badge {
    display: inline-block;
    background: #6366f1;
    color: white;
    border-radius: 50%;
    width: 28px; height: 28px;
    line-height: 28px;
    text-align: center;
    font-weight: 700;
    margin-right: 8px;
    font-size: .85rem;
}

/* ── Q feedback ── */
.q-row {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    padding: .75rem 1rem;
    border-left: 4px solid #6366f1;
    background: #f8faff;
    border-radius: 0 8px 8px 0;
    margin-bottom: .5rem;
}
.q-marks { font-size: 1.3rem; font-weight: 700; color: #6366f1; min-width: 80px; text-align: right; }
.q-feedback { color: #475569; font-size: .9rem; margin-top: .25rem; }

/* ── Status pill ── */
.pill-pass { background:#dcfce7; color:#166534; border-radius:20px; padding:2px 10px; font-size:.8rem; font-weight:600; }
.pill-fail { background:#fee2e2; color:#991b1b; border-radius:20px; padding:2px 10px; font-size:.8rem; font-weight:600; }

/* ── Header ── */
.hero {
    background: linear-gradient(135deg,#6366f1 0%,#8b5cf6 60%,#a855f7 100%);
    border-radius: 16px;
    padding: 2rem 2.5rem;
    color: white;
    margin-bottom: 1.5rem;
}
.hero h1 { margin:0; font-size:2rem; }
.hero p  { margin:.5rem 0 0; opacity:.85; }
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# LOGIN PAGE
# ══════════════════════════════════════════════════════════════════════════════
def page_login():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("""
        <div style='text-align:center; padding: 3rem 0 1rem;'>
          <h1 style='font-size:2.5rem; background:linear-gradient(135deg,#6366f1,#a855f7);
                     -webkit-background-clip:text; -webkit-text-fill-color:transparent;'>
            📝 Ease-Edu
          </h1>
          <p style='color:#64748b; font-size:1.1rem;'>AI-Powered Answer Sheet Evaluation for Teachers</p>
        </div>
        """, unsafe_allow_html=True)

        with st.container():
            st.markdown("---")
            st.markdown("### 🔐 Sign In")

            with st.form("login_form"):
                name     = st.text_input("Full Name",       placeholder="Dr. Jane Smith")
                email    = st.text_input("Institutional Email", placeholder="teacher@school.edu")
                provider = st.selectbox("Sign In With", ["Google SSO", "Microsoft SSO", "Institutional SSO"])
                submitted = st.form_submit_button("Sign In", use_container_width=True, type="primary")

            if submitted:
                if not email or "@" not in email:
                    st.error("Please enter a valid email.")
                    return
                prov_map = {"Google SSO": "google", "Microsoft SSO": "microsoft", "Institutional SSO": "institutional"}
                r = api("POST", "/api/auth/login", json={
                    "name": name, "email": email, "provider": prov_map[provider]
                })
                if r and r.status_code == 200:
                    data = r.json()
                    st.session_state["teacher"]  = data
                    st.session_state["page"]     = "dashboard"
                    st.rerun()
                elif r:
                    st.error(r.json().get("error", "Login failed"))

        st.markdown("""
        <p style='text-align:center; color:#94a3b8; font-size:.8rem; margin-top:2rem;'>
          🔒 Demo mode — enter any institutional email to log in.<br>
          Production deployments use real OAuth tokens.
        </p>
        """, unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════
def sidebar():
    teacher = ss("teacher", {})
    with st.sidebar:
        st.markdown(f"""
        <div style='padding:1rem 0; border-bottom:1px solid #1e293b; margin-bottom:1rem;'>
          <div style='font-size:1.5rem; text-align:center;'>📝</div>
          <h2 style='text-align:center; font-size:1.1rem; margin:.5rem 0 0;'>Ease-Edu</h2>
          <p style='text-align:center; font-size:.75rem; opacity:.6;'>AI Exam Evaluator</p>
        </div>
        <div style='background:#1e293b; border-radius:8px; padding:.75rem 1rem; margin-bottom:1.5rem;'>
          <p style='margin:0; font-size:.75rem; opacity:.6;'>Signed in as</p>
          <p style='margin:0; font-weight:600; font-size:.9rem;'>{teacher.get('name','Teacher')}</p>
          <p style='margin:0; font-size:.75rem; opacity:.6;'>{teacher.get('email','')}</p>
        </div>
        """, unsafe_allow_html=True)

        pages = {
            "🏠 Dashboard":   "dashboard",
            "📤 New Evaluation": "evaluate",
            "📋 My Reports":  "reports",
        }
        for label, key in pages.items():
            active = ss("page") == key
            style = "background:#6366f1; border-radius:8px;" if active else ""
            if st.button(label, key=f"nav_{key}", use_container_width=True):
                st.session_state["page"] = key
                st.rerun()

        st.markdown("<div style='height:2rem'></div>", unsafe_allow_html=True)
        if st.button("🚪 Sign Out", use_container_width=True):
            api("POST", "/api/auth/logout")
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# DASHBOARD PAGE
# ══════════════════════════════════════════════════════════════════════════════
def page_dashboard():
    teacher = ss("teacher", {})
    st.markdown(f"""
    <div class='hero'>
      <h1>👋 Welcome back, {teacher.get('name','Teacher')}!</h1>
      <p>Upload answer sheets and get instant AI-powered evaluations.</p>
    </div>
    """, unsafe_allow_html=True)

    # Stats
    r = api("GET", "/api/reports")
    reports = r.json() if r and r.status_code == 200 else []

    rf = api("GET", "/api/files")
    files = rf.json() if rf and rf.status_code == 200 else {}

    c1, c2, c3, c4 = st.columns(4)
    metrics = [
        (c1, len(reports), "Total Evaluations"),
        (c2, len(files.get("question_papers", [])), "Question Papers"),
        (c3, len(files.get("marking_schemes", [])),  "Marking Schemes"),
        (c4, len(files.get("answer_sheets", [])),    "Answer Sheets"),
    ]
    for col, val, label in metrics:
        with col:
            st.markdown(f"""
            <div class='metric-card'>
              <h2>{val}</h2>
              <p>{label}</p>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Recent reports
    st.markdown("### 📋 Recent Evaluations")
    if not reports:
        st.info("No evaluations yet. Click **New Evaluation** to get started!")
    else:
        for rep in reports[:5]:
            total = rep.get("total_marks", 0)
            maxt  = rep.get("max_marks", 0)
            pct   = (total / maxt * 100) if maxt else 0
            pill  = "<span class='pill-pass'>PASS</span>" if pct >= 40 else "<span class='pill-fail'>FAIL</span>"
            st.markdown(f"""
            <div class='card'>
              <div style='display:flex; justify-content:space-between; align-items:center;'>
                <div>
                  <strong>Report #{rep['report_id'][:8]}</strong><br>
                  <span style='color:#64748b; font-size:.85rem;'>{rep['created_at']}</span>
                </div>
                <div style='text-align:right;'>
                  <span style='font-size:1.2rem; font-weight:700; color:#6366f1;'>{total} / {maxt}</span>
                  &nbsp; {pill}
                  <br><span style='font-size:.8rem; color:#64748b;'>{pct:.1f}%</span>
                </div>
              </div>
            </div>
            """, unsafe_allow_html=True)
            if st.button(f"View Report #{rep['report_id'][:8]}", key=f"view_{rep['report_id']}"):
                st.session_state["view_report_id"] = rep["report_id"]
                st.session_state["page"] = "reports"
                st.rerun()

    st.markdown("---")
    if st.button("➕ Start New Evaluation", type="primary", use_container_width=True):
        st.session_state["page"] = "evaluate"
        st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# NEW EVALUATION PAGE
# ══════════════════════════════════════════════════════════════════════════════
def page_evaluate():
    st.markdown("""
    <div class='hero'>
      <h1>📤 New Evaluation</h1>
      <p>Upload the question paper, marking scheme, and answer sheet — then let AI do the rest.</p>
    </div>
    """, unsafe_allow_html=True)

    # Step progress bar
    step = ss("eval_step", 1)
    progress_labels = ["Login", "Question Paper", "Marking Scheme", "Answer Sheet", "Evaluate", "Results"]
    progress = (step - 1) / (len(progress_labels) - 1)
    st.progress(progress, text=f"Step {step} of {len(progress_labels)-1}: {progress_labels[step]}")
    st.markdown("<br>", unsafe_allow_html=True)

    # ── Step 1: Upload Question Paper ──────────────────────────────────────────
    with st.expander("📄 Step 1 — Upload Question Paper", expanded=(step == 1)):
        st.markdown("Upload the question paper (PDF or image). Gemini will read all questions directly — no OCR needed.")
        qp_file = st.file_uploader("Question Paper", type=["pdf","png","jpg","jpeg"],
                                    key="qp_upload", label_visibility="collapsed")
        if qp_file:
            st.success(f"✅ Selected: **{qp_file.name}**")
            if st.button("Upload Question Paper", type="primary", key="btn_qp"):
                with st.spinner("Uploading..."):
                    r = api("POST", "/api/upload/question-paper",
                            files={"file": (qp_file.name, qp_file.getvalue(), qp_file.type)})
                if r and r.status_code == 200:
                    st.session_state["paper_id"]  = r.json()["paper_id"]
                    st.session_state["paper_name"] = qp_file.name
                    st.session_state["eval_step"]  = 2
                    st.success("Question paper uploaded!")
                    time.sleep(0.5)
                    st.rerun()
                elif r:
                    st.error(r.json().get("error"))
        elif ss("paper_id"):
            st.success(f"✅ Already uploaded: **{ss('paper_name')}**")
            if st.button("Proceed to Step 2 →", key="to_step2"):
                st.session_state["eval_step"] = 2
                st.rerun()

    # ── Step 2: Upload Marking Scheme ──────────────────────────────────────────
    if step >= 2:
        with st.expander("📋 Step 2 — Upload Marking Scheme", expanded=(step == 2)):
            st.markdown("Upload the marking scheme (PDF, image, or text). Gemini extracts rubric and partial-mark rules.")
            ms_file = st.file_uploader("Marking Scheme", type=["pdf","png","jpg","jpeg","txt"],
                                        key="ms_upload", label_visibility="collapsed")
            if ms_file:
                st.success(f"✅ Selected: **{ms_file.name}**")
                if st.button("Upload Marking Scheme", type="primary", key="btn_ms"):
                    with st.spinner("Uploading..."):
                        r = api("POST", "/api/upload/marking-scheme",
                                files={"file": (ms_file.name, ms_file.getvalue(), ms_file.type)})
                    if r and r.status_code == 200:
                        st.session_state["scheme_id"]   = r.json()["scheme_id"]
                        st.session_state["scheme_name"] = ms_file.name
                        st.session_state["eval_step"]   = 3
                        st.success("Marking scheme uploaded!")
                        time.sleep(0.5)
                        st.rerun()
                    elif r:
                        st.error(r.json().get("error"))
            elif ss("scheme_id"):
                st.success(f"✅ Already uploaded: **{ss('scheme_name')}**")
                if st.button("Proceed to Step 3 →", key="to_step3"):
                    st.session_state["eval_step"] = 3
                    st.rerun()

    # ── Step 3: Upload Answer Sheet ────────────────────────────────────────────
    if step >= 3:
        with st.expander("📝 Step 3 — Upload Student Answer Sheet", expanded=(step == 3)):
            st.markdown("Upload the student's handwritten or typed answer sheet. Gemini Vision reads and maps answers automatically.")
            as_file = st.file_uploader("Answer Sheet", type=["pdf","png","jpg","jpeg"],
                                        key="as_upload", label_visibility="collapsed")
            if as_file:
                st.success(f"✅ Selected: **{as_file.name}**")
                if st.button("Upload Answer Sheet", type="primary", key="btn_as"):
                    with st.spinner("Uploading..."):
                        r = api("POST", "/api/upload/answer-sheet",
                                files={"file": (as_file.name, as_file.getvalue(), as_file.type)})
                    if r and r.status_code == 200:
                        st.session_state["sheet_id"]   = r.json()["sheet_id"]
                        st.session_state["sheet_name"] = as_file.name
                        st.session_state["eval_step"]  = 4
                        st.success("Answer sheet uploaded!")
                        time.sleep(0.5)
                        st.rerun()
                    elif r:
                        st.error(r.json().get("error"))
            elif ss("sheet_id"):
                st.success(f"✅ Already uploaded: **{ss('sheet_name')}**")
                if st.button("Proceed to Evaluate →", key="to_step4"):
                    st.session_state["eval_step"] = 4
                    st.rerun()

    # ── Step 4: Evaluate ────────────────────────────────────────────────────────
    if step >= 4:
        with st.expander("🤖 Step 4 — Run AI Evaluation", expanded=(step == 4)):
            p_id = ss("paper_id")
            s_id = ss("scheme_id")
            a_id = ss("sheet_id")

            if p_id and s_id and a_id:
                st.markdown("#### Ready to evaluate")
                st.markdown(f"""
                | Document | File |
                |----------|------|
                | Question Paper   | `{ss('paper_name',  p_id[:8])}` |
                | Marking Scheme   | `{ss('scheme_name', s_id[:8])}` |
                | Answer Sheet     | `{ss('sheet_name',  a_id[:8])}` |
                """)
                if st.button("🚀 Start AI Evaluation", type="primary", use_container_width=True, key="btn_eval"):
                    with st.spinner("🤖 Gemini is reading and evaluating… this may take 30–60 seconds."):
                        r = api("POST", "/api/evaluate", json={
                            "paper_id":  p_id,
                            "scheme_id": s_id,
                            "sheet_id":  a_id,
                        })
                    if r and r.status_code == 200:
                        st.session_state["eval_result"] = r.json()
                        st.session_state["eval_step"]   = 5
                        st.rerun()
                    elif r:
                        st.error(r.json().get("error", "Evaluation failed"))
            else:
                st.warning("Please complete all 3 upload steps first.")

    # ── Step 5: Results ────────────────────────────────────────────────────────
    if step >= 5 and ss("eval_result"):
        render_results(ss("eval_result"))

    # Reset button
    st.markdown("---")
    if st.button("🔄 Start a New Evaluation (Reset)", key="reset_eval"):
        for k in ["paper_id","paper_name","scheme_id","scheme_name","sheet_id","sheet_name","eval_step","eval_result"]:
            st.session_state.pop(k, None)
        st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# RESULTS RENDERER
# ══════════════════════════════════════════════════════════════════════════════
def render_results(data):
    questions = data.get("questions", {})
    total     = data.get("total_marks", 0)
    max_t     = data.get("max_total_marks", 0)
    summary   = data.get("performance_summary", "")
    report_id = data.get("report_id", "")
    pct       = (total / max_t * 100) if max_t else 0

    st.markdown("---")
    st.markdown("## 🎯 Evaluation Results")

    # Score banner
    colour = "#22c55e" if pct >= 60 else "#f59e0b" if pct >= 40 else "#ef4444"
    grade  = "A" if pct >= 80 else "B" if pct >= 65 else "C" if pct >= 50 else "D" if pct >= 35 else "F"
    st.markdown(f"""
    <div style='background:linear-gradient(135deg,{colour}22,{colour}44);
                border:2px solid {colour}; border-radius:16px; padding:2rem;
                text-align:center; margin-bottom:1.5rem;'>
      <h1 style='margin:0; font-size:3rem; color:{colour};'>{total} / {max_t}</h1>
      <p style='font-size:1.2rem; margin:.5rem 0; color:#1e293b;'>{pct:.1f}% &nbsp;|&nbsp; Grade: <strong>{grade}</strong></p>
    </div>
    """, unsafe_allow_html=True)

    # Per-question breakdown
    st.markdown("### 📊 Question-wise Breakdown")
    for qnum, info in questions.items():
        am  = info.get("awarded_marks", 0)
        mm  = info.get("max_marks", 0)
        fb  = info.get("feedback", "")
        qpct = (am / mm * 100) if mm else 0
        bar_colour = "#22c55e" if qpct >= 60 else "#f59e0b" if qpct >= 40 else "#ef4444"
        st.markdown(f"""
        <div class='q-row'>
          <div style='flex:1;'>
            <strong>{qnum}</strong>
            <p class='q-feedback'>💬 {fb}</p>
          </div>
          <div class='q-marks'>{am} / {mm}</div>
        </div>
        """, unsafe_allow_html=True)

    # Performance summary
    if summary:
        st.markdown("### 🧠 AI Performance Summary")
        st.info(summary)

    # Download
    if report_id:
        st.markdown("### 📥 Download Report")
        if st.button("⬇️ Download Full Report (.txt)", use_container_width=True):
            r = api("GET", f"/api/reports/{report_id}/download")
            if r and r.status_code == 200:
                st.download_button(
                    "Click here to save",
                    data=r.content,
                    file_name=f"report_{report_id[:8]}.txt",
                    mime="text/plain",
                )

# ══════════════════════════════════════════════════════════════════════════════
# REPORTS PAGE
# ══════════════════════════════════════════════════════════════════════════════
def page_reports():
    st.markdown("""
    <div class='hero'>
      <h1>📋 My Evaluation Reports</h1>
      <p>View and download all your past AI evaluations.</p>
    </div>
    """, unsafe_allow_html=True)

    # If a specific report is requested
    view_id = ss("view_report_id")
    if view_id:
        r = api("GET", f"/api/reports/{view_id}")
        if r and r.status_code == 200:
            d = r.json()
            ev = d.get("evaluation_json", {})
            render_results({**ev, "report_id": view_id,
                             "total_marks": d["total_marks"],
                             "max_total_marks": d["max_marks"]})
        if st.button("← Back to Report List"):
            st.session_state.pop("view_report_id", None)
            st.rerun()
        return

    r = api("GET", "/api/reports")
    reports = r.json() if r and r.status_code == 200 else []

    if not reports:
        st.info("No reports yet. Create your first evaluation!")
        return

    for rep in reports:
        total = rep.get("total_marks", 0)
        maxt  = rep.get("max_marks", 0)
        pct   = (total / maxt * 100) if maxt else 0
        pill  = "<span class='pill-pass'>PASS</span>" if pct >= 40 else "<span class='pill-fail'>FAIL</span>"

        col1, col2 = st.columns([4, 1])
        with col1:
            st.markdown(f"""
            <div class='card'>
              <div style='display:flex; justify-content:space-between;'>
                <div>
                  <strong>📄 Report #{rep['report_id'][:8]}</strong><br>
                  <span style='color:#64748b; font-size:.85rem;'>📅 {rep['created_at']}</span><br>
                  <span style='font-size:.85rem; color:#475569;'>💬 {rep.get('summary','')[:120]}...</span>
                </div>
                <div style='text-align:right; min-width:100px;'>
                  <span style='font-size:1.3rem; font-weight:700; color:#6366f1;'>{total}/{maxt}</span><br>
                  {pill}
                </div>
              </div>
            </div>
            """, unsafe_allow_html=True)
        with col2:
            if st.button("View", key=f"view_{rep['report_id']}"):
                st.session_state["view_report_id"] = rep["report_id"]
                st.rerun()
            r2 = api("GET", f"/api/reports/{rep['report_id']}/download")
            if r2 and r2.status_code == 200:
                st.download_button("⬇️", data=r2.content,
                    file_name=f"report_{rep['report_id'][:8]}.txt",
                    mime="text/plain",
                    key=f"dl_{rep['report_id']}")

# ══════════════════════════════════════════════════════════════════════════════
# ROUTER
# ══════════════════════════════════════════════════════════════════════════════
def main():
    # Check if logged in
    if not ss("teacher"):
        page_login()
        return

    sidebar()
    page = ss("page", "dashboard")

    if page == "dashboard":
        page_dashboard()
    elif page == "evaluate":
        page_evaluate()
    elif page == "reports":
        page_reports()

if __name__ == "__main__":
    main()
