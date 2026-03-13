#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────
# Ease-Edu — one-command startup
# Usage:
#   GEMINI_API_KEY=your_key bash start.sh
# ─────────────────────────────────────────────────────────────────

set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"

echo "📦 Installing dependencies…"
pip install -r "$ROOT/requirements.txt" -q

# ── Start Flask backend ────────────────────────────────────────────────────────
echo "🚀 Starting Flask backend on http://localhost:5050 …"
GEMINI_API_KEY="${GEMINI_API_KEY:-}" \
FLASK_SECRET="${FLASK_SECRET:-super-secret-change-me}" \
python "$ROOT/backend/app.py" &
FLASK_PID=$!
echo "   Flask PID: $FLASK_PID"

sleep 2   # Give Flask a moment to bind

# ── Start Streamlit frontend ───────────────────────────────────────────────────
echo "🎨 Starting Streamlit on http://localhost:8501 …"
streamlit run "$ROOT/frontend/streamlit_app.py" \
    --server.port 8501 \
    --server.headless true \
    --browser.gatherUsageStats false &
ST_PID=$!
echo "   Streamlit PID: $ST_PID"

echo ""
echo "═══════════════════════════════════════════════════════"
echo "  ✅  Ease-Edu is running!"
echo "  🌐  Open: http://localhost:8501"
echo "  🔑  Set GEMINI_API_KEY env var for real evaluations"
echo "═══════════════════════════════════════════════════════"

# ── Trap Ctrl-C to kill both ───────────────────────────────────────────────────
trap 'echo ""; echo "Stopping…"; kill $FLASK_PID $ST_PID 2>/dev/null; exit' INT TERM
wait
