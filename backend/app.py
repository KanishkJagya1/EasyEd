import os
import json
import uuid
import base64
import hashlib
import sqlite3
import traceback
import datetime
from pathlib import Path
from functools import wraps
from flask import Flask, request, jsonify, session, send_file
from google import genai
from google.genai import types as genai_types
from werkzeug.utils import secure_filename

# ── Load .env file automatically (Windows-friendly, no extra packages) ─────────
_env_file = Path(__file__).parent.parent / ".env"
if _env_file.exists():
    for _line in _env_file.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())
    print(f"✅ Loaded .env from {_env_file}")

# ── App setup ──────────────────────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "dev-secret-change-in-prod")

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
BASE_DIR       = Path(__file__).parent.parent
STORAGE_DIR    = BASE_DIR / "storage"
DB_PATH        = BASE_DIR / "ease_edu.db"

for sub in ["question_papers", "marking_schemes", "answer_sheets", "reports"]:
    (STORAGE_DIR / sub).mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "txt"}

if GEMINI_API_KEY:
    print(f"✅ Gemini API key loaded (ends with ...{GEMINI_API_KEY[-6:]})")
else:
    print("⚠️  WARNING: GEMINI_API_KEY is not set! Evaluations will fail.")

# ── DB helpers ─────────────────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS teachers (
            teacher_id   TEXT PRIMARY KEY,
            name         TEXT NOT NULL,
            email        TEXT UNIQUE NOT NULL,
            auth_provider TEXT DEFAULT 'google',
            created_at   TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS question_papers (
            paper_id     TEXT PRIMARY KEY,
            teacher_id   TEXT NOT NULL,
            file_path    TEXT NOT NULL,
            file_name    TEXT NOT NULL,
            upload_ts    TEXT DEFAULT (datetime('now')),
            FOREIGN KEY(teacher_id) REFERENCES teachers(teacher_id)
        );
        CREATE TABLE IF NOT EXISTS marking_schemes (
            scheme_id    TEXT PRIMARY KEY,
            teacher_id   TEXT NOT NULL,
            file_path    TEXT NOT NULL,
            file_name    TEXT NOT NULL,
            upload_ts    TEXT DEFAULT (datetime('now')),
            FOREIGN KEY(teacher_id) REFERENCES teachers(teacher_id)
        );
        CREATE TABLE IF NOT EXISTS answer_sheets (
            sheet_id     TEXT PRIMARY KEY,
            teacher_id   TEXT NOT NULL,
            file_path    TEXT NOT NULL,
            file_name    TEXT NOT NULL,
            upload_ts    TEXT DEFAULT (datetime('now')),
            FOREIGN KEY(teacher_id) REFERENCES teachers(teacher_id)
        );
        CREATE TABLE IF NOT EXISTS evaluation_reports (
            report_id        TEXT PRIMARY KEY,
            teacher_id       TEXT NOT NULL,
            paper_id         TEXT,
            scheme_id        TEXT,
            sheet_id         TEXT,
            evaluation_json  TEXT,
            total_marks      REAL,
            max_marks        REAL,
            summary          TEXT,
            created_at       TEXT DEFAULT (datetime('now')),
            FOREIGN KEY(teacher_id) REFERENCES teachers(teacher_id)
        );
        """)
    print("DB initialized.")

init_db()

# ── Auth helpers ───────────────────────────────────────────────────────────────
def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        tid = session.get("teacher_id")
        if not tid:
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated

def current_teacher():
    return session.get("teacher_id")

# ── Utility ────────────────────────────────────────────────────────────────────
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def save_upload(file, subdir):
    ext   = file.filename.rsplit(".", 1)[1].lower()
    uid   = str(uuid.uuid4())
    fname = f"{uid}.{ext}"
    path  = STORAGE_DIR / subdir / fname
    file.save(str(path))
    return str(path), file.filename

# ── Gemini evaluation ──────────────────────────────────────────────────────────
def run_evaluation(paper_path, scheme_path, sheet_path):
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY is not set. Add it to your .env file.")

    client = genai.Client(api_key=GEMINI_API_KEY)

    def make_part(path: str):
        ext = path.rsplit(".", 1)[-1].lower()
        mime_map = {
            "pdf":  "application/pdf",
            "png":  "image/png",
            "jpg":  "image/jpeg",
            "jpeg": "image/jpeg",
            "txt":  "text/plain",
        }
        mime = mime_map.get(ext, "application/octet-stream")
        with open(path, "rb") as f:
            data = f.read()
        if ext == "txt":
            return {"text": data.decode("utf-8", errors="ignore")}
        return {"inline_data": {"mime_type": mime, "data": base64.b64encode(data).decode()}}

    prompt = """You are an expert exam evaluator. You have been provided three documents:
1. QUESTION PAPER — contains all questions with their numbers.
2. MARKING SCHEME — contains correct answers, marks per question, and rubric/partial-marking rules.
3. STUDENT ANSWER SHEET — contains the student's handwritten or typed answers.

Your task:
- Extract every question from the question paper with its question number and maximum marks.
- Extract the marking rubric from the marking scheme.
- Read the student answer sheet and match each student answer to its corresponding question
  (handle out-of-order answers intelligently).
- Evaluate each answer against the rubric.
- Return ONLY valid JSON in the following format (no markdown fences, no extra text):

{
  "questions": {
    "Q1": {"max_marks": 5, "awarded_marks": 4, "feedback": "Good answer but missing one example."},
    "Q2": {"max_marks": 3, "awarded_marks": 0, "feedback": "Not attempted."}
  },
  "total_marks": 4,
  "max_total_marks": 8,
  "performance_summary": "2-3 sentence summary of student performance."
}

Rules:
- If a question is not attempted, awarded_marks = 0 and feedback = "Not attempted."
- Apply partial marking where the scheme allows.
- Map answers to questions even if answered in a different order.
- Be fair, consistent, and detailed in feedback.
- Output ONLY the JSON object. No markdown, no explanation, no code fences."""

    print(f"  → Sending to Gemini: {paper_path}, {scheme_path}, {sheet_path}")
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[
            make_part(paper_path),
            make_part(scheme_path),
            make_part(sheet_path),
            {"text": prompt},
        ],
    )
    raw = response.text.strip()
    print(f"  → Gemini raw response (first 300 chars): {raw[:300]}")

    # Strip markdown fences if Gemini adds them anyway
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:])
        if raw.strip().endswith("```"):
            raw = raw.strip()[:-3].strip()

    return json.loads(raw)

# ── Auth routes ────────────────────────────────────────────────────────────────
@app.route("/api/auth/login", methods=["POST"])
def login():
    data     = request.json or {}
    name     = data.get("name", "").strip()
    email    = data.get("email", "").strip().lower()
    provider = data.get("provider", "google")

    if not email:
        return jsonify({"error": "email required"}), 400

    tid = hashlib.sha256(email.encode()).hexdigest()[:16]

    with get_db() as conn:
        existing = conn.execute("SELECT * FROM teachers WHERE teacher_id=?", (tid,)).fetchone()
        if not existing:
            conn.execute(
                "INSERT INTO teachers (teacher_id,name,email,auth_provider) VALUES (?,?,?,?)",
                (tid, name or email.split("@")[0], email, provider)
            )
    session["teacher_id"]    = tid
    session["teacher_email"] = email
    return jsonify({"teacher_id": tid, "email": email, "name": name})

@app.route("/api/auth/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"ok": True})

@app.route("/api/auth/me", methods=["GET"])
@require_auth
def me():
    tid = current_teacher()
    with get_db() as conn:
        row = conn.execute("SELECT * FROM teachers WHERE teacher_id=?", (tid,)).fetchone()
    if not row:
        return jsonify({"error": "not found"}), 404
    return jsonify(dict(row))

# ── Upload routes ──────────────────────────────────────────────────────────────
@app.route("/api/upload/question-paper", methods=["POST"])
@require_auth
def upload_question_paper():
    if "file" not in request.files:
        return jsonify({"error": "No file"}), 400
    f = request.files["file"]
    if not allowed_file(f.filename):
        return jsonify({"error": "Invalid file type"}), 400
    path, orig = save_upload(f, "question_papers")
    pid = str(uuid.uuid4())
    with get_db() as conn:
        conn.execute(
            "INSERT INTO question_papers VALUES (?,?,?,?,datetime('now'))",
            (pid, current_teacher(), path, orig)
        )
    return jsonify({"paper_id": pid, "file_name": orig})

@app.route("/api/upload/marking-scheme", methods=["POST"])
@require_auth
def upload_marking_scheme():
    if "file" not in request.files:
        return jsonify({"error": "No file"}), 400
    f = request.files["file"]
    if not allowed_file(f.filename):
        return jsonify({"error": "Invalid file type"}), 400
    path, orig = save_upload(f, "marking_schemes")
    sid = str(uuid.uuid4())
    with get_db() as conn:
        conn.execute(
            "INSERT INTO marking_schemes VALUES (?,?,?,?,datetime('now'))",
            (sid, current_teacher(), path, orig)
        )
    return jsonify({"scheme_id": sid, "file_name": orig})

@app.route("/api/upload/answer-sheet", methods=["POST"])
@require_auth
def upload_answer_sheet():
    if "file" not in request.files:
        return jsonify({"error": "No file"}), 400
    f = request.files["file"]
    if not allowed_file(f.filename):
        return jsonify({"error": "Invalid file type"}), 400
    path, orig = save_upload(f, "answer_sheets")
    aid = str(uuid.uuid4())
    with get_db() as conn:
        conn.execute(
            "INSERT INTO answer_sheets VALUES (?,?,?,?,datetime('now'))",
            (aid, current_teacher(), path, orig)
        )
    return jsonify({"sheet_id": aid, "file_name": orig})

# ── Evaluate ───────────────────────────────────────────────────────────────────
@app.route("/api/evaluate", methods=["POST"])
@require_auth
def evaluate():
    data      = request.json or {}
    paper_id  = data.get("paper_id")
    scheme_id = data.get("scheme_id")
    sheet_id  = data.get("sheet_id")

    if not all([paper_id, scheme_id, sheet_id]):
        return jsonify({"error": "paper_id, scheme_id, sheet_id all required"}), 400

    tid = current_teacher()
    with get_db() as conn:
        paper  = conn.execute("SELECT * FROM question_papers WHERE paper_id=?  AND teacher_id=?", (paper_id,  tid)).fetchone()
        scheme = conn.execute("SELECT * FROM marking_schemes  WHERE scheme_id=? AND teacher_id=?", (scheme_id, tid)).fetchone()
        sheet  = conn.execute("SELECT * FROM answer_sheets    WHERE sheet_id=?  AND teacher_id=?", (sheet_id,  tid)).fetchone()

    if not all([paper, scheme, sheet]):
        return jsonify({"error": "Files not found or access denied"}), 404

    try:
        result = run_evaluation(paper["file_path"], scheme["file_path"], sheet["file_path"])
    except Exception as e:
        tb = traceback.format_exc()
        print(f"EVALUATION ERROR:\n{tb}")
        return jsonify({"error": f"Evaluation failed: {str(e)}"}), 500

    rid     = str(uuid.uuid4())
    total   = result.get("total_marks", 0)
    max_t   = result.get("max_total_marks", 0)
    summary = result.get("performance_summary", "")

    with get_db() as conn:
        conn.execute(
            """INSERT INTO evaluation_reports
               (report_id,teacher_id,paper_id,scheme_id,sheet_id,
                evaluation_json,total_marks,max_marks,summary)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (rid, tid, paper_id, scheme_id, sheet_id,
             json.dumps(result), total, max_t, summary)
        )

    return jsonify({"report_id": rid, **result})

# ── Reports ────────────────────────────────────────────────────────────────────
@app.route("/api/reports", methods=["GET"])
@require_auth
def list_reports():
    tid = current_teacher()
    with get_db() as conn:
        rows = conn.execute(
            """SELECT report_id, total_marks, max_marks, summary, created_at
               FROM evaluation_reports WHERE teacher_id=? ORDER BY created_at DESC""",
            (tid,)
        ).fetchall()
    return jsonify([dict(r) for r in rows])

@app.route("/api/reports/<report_id>", methods=["GET"])
@require_auth
def get_report(report_id):
    tid = current_teacher()
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM evaluation_reports WHERE report_id=? AND teacher_id=?",
            (report_id, tid)
        ).fetchone()
    if not row:
        return jsonify({"error": "Not found"}), 404
    d = dict(row)
    d["evaluation_json"] = json.loads(d["evaluation_json"] or "{}")
    return jsonify(d)

@app.route("/api/reports/<report_id>/download", methods=["GET"])
@require_auth
def download_report(report_id):
    tid = current_teacher()
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM evaluation_reports WHERE report_id=? AND teacher_id=?",
            (report_id, tid)
        ).fetchone()
    if not row:
        return jsonify({"error": "Not found"}), 404

    ev        = json.loads(row["evaluation_json"] or "{}")
    questions = ev.get("questions", {})
    summary   = ev.get("performance_summary", "")

    lines = [
        "EASE-EDU — AI Evaluation Report",
        "=" * 50,
        f"Report ID  : {report_id}",
        f"Generated  : {row['created_at']}",
        f"Total Score: {row['total_marks']} / {row['max_marks']}",
        "",
        "QUESTION-WISE BREAKDOWN",
        "-" * 50,
    ]
    for qnum, info in questions.items():
        lines += [
            f"{qnum}:",
            f"  Marks    : {info.get('awarded_marks')} / {info.get('max_marks')}",
            f"  Feedback : {info.get('feedback')}",
            "",
        ]
    lines += ["PERFORMANCE SUMMARY", "-" * 50, summary]
    content = "\n".join(lines)

    report_path = STORAGE_DIR / "reports" / f"{report_id}.txt"
    report_path.write_text(content, encoding="utf-8")
    return send_file(str(report_path), as_attachment=True,
                     download_name=f"report_{report_id[:8]}.txt",
                     mimetype="text/plain")

# ── Teacher file history ───────────────────────────────────────────────────────
@app.route("/api/files", methods=["GET"])
@require_auth
def list_files():
    tid = current_teacher()
    with get_db() as conn:
        papers  = [dict(r) for r in conn.execute("SELECT paper_id,file_name,upload_ts FROM question_papers WHERE teacher_id=?", (tid,))]
        schemes = [dict(r) for r in conn.execute("SELECT scheme_id,file_name,upload_ts FROM marking_schemes  WHERE teacher_id=?", (tid,))]
        sheets  = [dict(r) for r in conn.execute("SELECT sheet_id,file_name,upload_ts  FROM answer_sheets    WHERE teacher_id=?", (tid,))]
    return jsonify({"question_papers": papers, "marking_schemes": schemes, "answer_sheets": sheets})

if __name__ == "__main__":
    app.run(debug=True, port=5050)