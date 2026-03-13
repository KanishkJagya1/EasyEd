# 📝 Ease-Edu — AI Answer Sheet Evaluation Platform

> A production-ready AI-powered exam evaluation system for teachers.  
> Built with **Flask** (backend) + **Streamlit** (frontend) + **Gemini 1.5 Flash** (AI).

---

## ✨ Features

| Feature | Details |
|---|---|
| 🔐 SSO Authentication | Google / Microsoft / Institutional SSO (demo mode ships out-of-the-box) |
| 📤 File Upload | Question Paper, Marking Scheme, Answer Sheet (PDF / PNG / JPG / TXT) |
| 🤖 AI Evaluation | Multi-stage Gemini Vision pipeline — reads, maps, and scores answers |
| 📊 Reports | Question-wise marks, feedback, performance summary |
| ⬇️ Download | Download evaluation report as `.txt` |
| 🗃️ Per-teacher DB | Each teacher only sees their own data |

---

## 🚀 Quick Start (local)

### 1. Clone / copy the project
```bash
git clone <repo-url>
cd ease-edu
```

### 2. Set your Gemini API key
```bash
export GEMINI_API_KEY="your_gemini_api_key_here"
```
Get a key at https://aistudio.google.com/app/apikey

### 3. Run everything with one command
```bash
bash start.sh
```

Open **http://localhost:8501** in your browser.

---

## 🐳 Docker Deployment

```bash
docker build -t ease-edu .
docker run -p 8501:8501 -p 5050:5050 \
  -e GEMINI_API_KEY="your_key" \
  -e FLASK_SECRET="your_secret" \
  ease-edu
```

---

## ☁️ Cloud Deployment (Streamlit Community Cloud)

1. Push your code to GitHub.
2. Go to https://streamlit.io/cloud → New App.
3. Point to `frontend/streamlit_app.py`.
4. Add secrets:
   ```toml
   GEMINI_API_KEY = "your_key"
   FLASK_SECRET   = "your_secret"
   ```

> **Note:** For cloud deployment, run the Flask backend separately (e.g., Railway, Render, or a VPS) and update `BACKEND` in `frontend/streamlit_app.py` to the public URL.

---

## 🏗️ Architecture

```
ease-edu/
├── backend/
│   └── app.py              ← Flask REST API
├── frontend/
│   └── streamlit_app.py    ← Streamlit UI
├── storage/
│   ├── question_papers/
│   ├── marking_schemes/
│   ├── answer_sheets/
│   └── reports/
├── ease_edu.db             ← SQLite (auto-created)
├── requirements.txt
├── start.sh
└── Dockerfile
```

### Evaluation Pipeline (5 stages)
```
Stage 1 → Gemini reads Question Paper  → extracts questions
Stage 2 → Gemini reads Marking Scheme  → extracts rubric
Stage 3 → Gemini reads Answer Sheet    → extracts student answers
Stage 4 → Backend maps answers → questions
Stage 5 → Gemini evaluates per-question → returns structured JSON
```

---

## 🔌 API Routes

| Method | Route | Description |
|--------|-------|-------------|
| POST | `/api/auth/login` | SSO login (demo stub) |
| POST | `/api/auth/logout` | Logout |
| GET  | `/api/auth/me` | Current teacher info |
| POST | `/api/upload/question-paper` | Upload question paper |
| POST | `/api/upload/marking-scheme` | Upload marking scheme |
| POST | `/api/upload/answer-sheet` | Upload answer sheet |
| POST | `/api/evaluate` | Run AI evaluation |
| GET  | `/api/reports` | List all reports |
| GET  | `/api/reports/<id>` | Get single report |
| GET  | `/api/reports/<id>/download` | Download report |
| GET  | `/api/files` | List uploaded files |

---

## 💰 Cost Optimisation

- **Gemini 1.5 Flash** is used (10x cheaper than Pro).
- Single multi-modal prompt sends all 3 documents in one API call.
- SQLite caching — re-evaluations reuse stored IDs.
- For high volume, cache `paper_id` and `scheme_id` extracted data to avoid re-processing the same paper for multiple students.

---

## 🔐 Production Auth Upgrade

Replace the demo stub in `app.py` `/api/auth/login` with:
- **Google OAuth 2.0**: use `authlib` or `google-auth`
- **Microsoft MSAL**: use `msal` library
- Store verified JWT tokens in sessions

---

## 📋 Database Schema

```sql
teachers          (teacher_id, name, email, auth_provider, created_at)
question_papers   (paper_id, teacher_id, file_path, file_name, upload_ts)
marking_schemes   (scheme_id, teacher_id, file_path, file_name, upload_ts)
answer_sheets     (sheet_id, teacher_id, file_path, file_name, upload_ts)
evaluation_reports(report_id, teacher_id, paper_id, scheme_id, sheet_id,
                   evaluation_json, total_marks, max_marks, summary, created_at)
```
