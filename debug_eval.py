"""
Run this from D:\edulens to test Gemini evaluation.
Usage:  python debug_eval.py
"""
import os, sys, json
from pathlib import Path

# Load .env
env_file = Path(".env")
if env_file.exists():
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ[k.strip()] = v.strip()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
print(f"API Key loaded: ...{GEMINI_API_KEY[-8:]}")

# Find the most recently uploaded files
storage = Path("storage")
def latest(folder):
    files = list((storage / folder).glob("*"))
    return max(files, key=lambda f: f.stat().st_mtime) if files else None

paper  = latest("question_papers")
scheme = latest("marking_schemes")
sheet  = latest("answer_sheets")

print(f"Question Paper : {paper}")
print(f"Marking Scheme : {scheme}")
print(f"Answer Sheet   : {sheet}")

if not all([paper, scheme, sheet]):
    print("\n❌ One or more uploaded files not found in storage/")
    sys.exit(1)

print("\n🤖 Calling Gemini...")
try:
    from google import genai

    client = genai.Client(api_key=GEMINI_API_KEY)

    def make_part(path):
        ext = str(path).rsplit(".", 1)[-1].lower()
        mime_map = {"pdf":"application/pdf","png":"image/png",
                    "jpg":"image/jpeg","jpeg":"image/jpeg","txt":"text/plain"}
        mime = mime_map.get(ext, "application/octet-stream")
        data = Path(path).read_bytes()
        if ext == "txt":
            return {"text": data.decode("utf-8", errors="ignore")}
        import base64
        return {"inline_data": {"mime_type": mime, "data": base64.b64encode(data).decode()}}

    prompt = """Evaluate the student answer sheet against the question paper and marking scheme.
Return ONLY valid JSON (no markdown fences) like:
{
  "questions": {
    "Q1": {"max_marks": 5, "awarded_marks": 4, "feedback": "Good answer."}
  },
  "total_marks": 4,
  "max_total_marks": 5,
  "performance_summary": "Student performed well overall."
}"""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[make_part(paper), make_part(scheme), make_part(sheet), {"text": prompt}],
    )

    print("\n✅ Gemini responded!")
    raw = response.text.strip()
    print("Raw output:\n", raw[:1000])

    if raw.startswith("```"):
        raw = "\n".join(raw.split("\n")[1:])
        raw = raw.rstrip("`").strip()

    result = json.loads(raw)
    print("\n✅ JSON parsed successfully!")
    print(json.dumps(result, indent=2))

except Exception as e:
    import traceback
    print("\n❌ ERROR:")
    traceback.print_exc()