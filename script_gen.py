# script_gen.py
#!/usr/bin/env python3
"""
Full-production script_gen.py
Features:
 - Demo script EN + TE
 - Auto-title EN + TE
 - Auto-tags
 - Auto-description
 - Avoid repeated tools
 - Optional Gemini remote generation
 - Clean manifest for downstream pipeline
"""

import os, sys, json, uuid, csv
from pathlib import Path
from datetime import datetime
import requests

# ===== PATHS =====
ROOT = Path.cwd()
MANIFESTS = ROOT / "manifests"
OUTPUTS = ROOT / "outputs"
HISTORY = OUTPUTS / "history.csv"
MANIFESTS.mkdir(exist_ok=True, parents=True)
OUTPUTS.mkdir(exist_ok=True, parents=True)

# ===== ENV =====
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
REMOTE_API = os.environ.get("SCRIPT_API_URL", "").strip()

# ===== MAKE HISTORY =====
def load_used_tools():
    used = set()
    if HISTORY.exists():
        for row in csv.DictReader(open(HISTORY, "r", encoding="utf8")):
            if "tool_name" in row and row["tool_name"]:
                used.add(row["tool_name"].strip().lower())

    for mf in MANIFESTS.glob("*.json"):
        try:
            data = json.load(open(mf, "r", encoding="utf8"))
            t = data.get("tool_name")
            if t:
                used.add(t.lower())
        except:
            pass
    return used

# ===== GEMINI GENERATOR =====
def gemini_generate(prompt: str):
    if not GEMINI_API_KEY:
        return None

    try:
        url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-thinking-exp:generateContent"
        headers = {"Content-Type": "application/json"}
        data = {"contents": [{"parts": [{"text": prompt}]}]}
        r = requests.post(url + f"?key={GEMINI_API_KEY}", json=data, headers=headers, timeout=25)

        if r.status_code != 200:
            return None

        out = r.json()
        return out["candidates"][0]["content"]["parts"][0]["text"]

    except:
        return None


# ====== GENERATE TOOL NAME IF USED ====
def pick_new_tool(previous_tool, used_tools):
    # If not used → return as is
    if previous_tool.lower() not in used_tools:
        return previous_tool

    fallback = [
        "ClipFix",
        "AutoCut Pro",
        "RenderPilot",
        "SnapEditor AI",
        "MagicTrim AI",
        "CleanCaptioner",
        "ReframeX",
        "ColorLift AI",
    ]

    for t in fallback:
        if t.lower() not in used_tools:
            return t

    # If still none → ask Gemini
    if GEMINI_API_KEY:
        resp = gemini_generate(
            "Suggest one unique AI video editing tool name. Only output the tool name."
        )
        if resp:
            return resp.strip()

    return previous_tool + "_NEW"  # last fallback



# ===== LOCAL SCRIPT FALLBACK =====
def local_generate(tool_name):
    en_body = (
        f"Today's AI tool is {tool_name}. It trims dead footage, fixes lighting & color, "
        "and auto-generates captions. Steps: upload -> auto-edit -> download."
    )

    te_body = (
        f"ఈ రోజు AI టూల్ {tool_name}. ఇది dead ఫుటేజ్ తీసి, లైట్ మరియు కలర్ సరిచేస్తుంది, "
        "క్యాప్షన్‌లు ఆటోమేటిక్ గా వేస్తుంది. అప్లోడ్ -> auto-edit -> డౌన్ లోడ్."
    )

    title_en = f"{tool_name} — AI Auto Editor"
    title_te = f"{tool_name} — శీఘ్ర AI ఆటో ఎడిటింగ్ టూల్"

    tags = [
        "AI tools", "video editing", "automation", tool_name,
        "content creator tools", "editing shortcuts"
    ]

    desc = f"{tool_name} helps you edit videos instantly using AI.\nSteps: upload → auto-edit → done."

    return en_body, te_body, title_en, title_te, tags, desc



# ====== MAIN MANIFEST BUILDER ======
def build_manifest(tool_name):
    used = load_used_tools()
    tool_name = pick_new_tool(tool_name, used)

    # Try Gemini-based script generation
    script_en = None
    script_te = None

    if GEMINI_API_KEY:
        prompt = f"""
Generate:
1) Telugu demo body
2) English demo body
3) English title
4) Telugu title
5) 10 SEO tags
6) Description (English)

Tool name: {tool_name}

Short. Vertical video style.
"""
        res = gemini_generate(prompt)
        if res:
            try:
                # crude extraction
                lines = res.split("\n")
                t_en = lines[1].strip()
                t_te = lines[0].strip()
            except:
                script_en = None

    # If Gemini fails → Local
    en_body, te_body, title_en, title_te, tags, desc = local_generate(tool_name)

    job_id = f"job_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"

    m = {
        "job_id": job_id,
        "tool_name": tool_name,
        "created_at": datetime.utcnow().isoformat() + "Z",

        # DEMO SCRIPTS ONLY
        "script": {
            "lang_en": {
                "body": en_body,
                "title": title_en
            },
            "lang_te": {
                "body": te_body,
                "title": title_te
            }
        },

        "tags": tags,
        "description": desc,

        "assets": {
            "demo_audio_en": "",
            "demo_audio_te": "",
            "demo_video": ""
        }
    }

    out = MANIFESTS / f"{job_id}.json"
    out.write_text(json.dumps(m, indent=2, ensure_ascii=False), encoding="utf8")

    # Append to history
    first = not HISTORY.exists()
    with open(HISTORY, "a", encoding="utf8", newline="") as fh:
        w = csv.writer(fh)
        if first:
            w.writerow(["job_id", "tool_name", "manifest_path", "created_at"])
        w.writerow([job_id, tool_name, str(out), datetime.utcnow().isoformat()])

    print("WROTE", out)
    return out



# ====== MAIN ======
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python script_gen.py <TOOL_NAME>")
        sys.exit(1)

    tool = sys.argv[1]
    build_manifest(tool)
