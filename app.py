import os, io, re, json
from datetime import datetime
import streamlit as st

st.set_page_config(page_title="InAA — No-Login Demo", page_icon="🧭", layout="wide")

# Optional OpenAI (for chat/polish). App still works without a key.
API_KEY = os.environ.get("OPENAI_API_KEY", "").strip()
client = None
if API_KEY:
    try:
        from openai import OpenAI
        client = OpenAI(api_key=API_KEY)
    except Exception:
        client = None

# ---------- Helpers ----------
def extract_text(file):
    name = file.name.lower()
    data = file.read()
    if name.endswith((".txt", ".md")):
        return data.decode("utf-8", "ignore")
    if name.endswith(".docx"):
        try:
            from docx import Document as DocxDocument
            doc = DocxDocument(io.BytesIO(data))
            parts = [p.text for p in doc.paragraphs]
            for tbl in doc.tables:
                for row in tbl.rows:
                    parts.append(" | ".join([c.text for c in row.cells]))
            return "\n".join(parts)
        except Exception:
            return ""
    if name.endswith(".pdf"):
        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(data))
            out = []
            for page in reader.pages:
                try: out.append(page.extract_text() or "")
                except: out.append("")
            return "\n".join(out)
        except Exception:
            return ""
    return ""

def run_linter(text):
    # Minimal, deterministic rules matching your v0.1 spirit
    rules = [
        ("R-A1", r"\bclimb(ing)?\b", "warn",
         "Replace physical-method verb with task-focused wording.",
         "Use 'ascend a ladder' or 'access elevated work areas'."),
        ("R-A2", r"lift(?:ing)?\s*(\d+)\s*(lb|lbs|pounds|kg)?", "warn",
         "Hard physical requirement may exclude qualified candidates if not essential.",
         "Say 'move materials up to N using safe methods' and allow assistive devices/team lifts."),
        ("R-B3", r"(excellent communication|team player|self[- ]starter|strong work ethic|detail[- ]oriented)", "info",
         "Vague soft-skill language.", "Define observable behaviors."),
        ("R-D1", r"with or without reasonable accommodation", "info",
         "ADA boilerplate belongs in HR, not in the WPS text.", "Remove from WPS; keep in policy docs."),
    ]
    flags = []
    for rid, pat, sev, msg, sug in rules:
        for m in re.finditer(pat, text, re.I):
            flags.append({"rule_id": rid, "severity": sev, "match": m.group(0), "message": msg, "suggestion": sug})
    # Simple auto-clean examples
    clean = re.sub(r"\bclimb(ing)?\b", "ascend", text, flags=re.I)
    clean = re.sub(r"lift(?:ing)?\s*(\d+)\s*(lb|lbs|pounds|kg)?",
                   r"move materials up to \1 \2 using safe methods", clean, flags=re.I)
    clean = re.sub(r"(excellent communication|team player|self[- ]starter|strong work ethic|detail[- ]oriented)",
                   r"communicates clearly with mentors and closes the loop on tasks", clean, flags=re.I)
    return flags, clean

def gpt_reply(text, context_hint=""):
    if not client:
        return "AI chat is off (no API key). I can still lint text and export files."
    try:
        msg = text + (f"\n\nContext:\n{context_hint}" if context_hint else "")
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role":"system","content":"You are the Accessibility WPS Assistant. Use inclusive, plain language; task-not-method."},
                {"role":"user","content": msg}
            ],
            temperature=0.3, max_tokens=900
        )
        return resp.choices[0].message.content
    except Exception as e:
        return f"Chat unavailable right now: {e}"

def export_docx(title, body):
    try:
        from docx import Document as DocxDocument
        doc = DocxDocument()
        doc.add_heading(title, 0)
        for line in body.split("\n"):
            doc.add_paragraph(line)
        bio = io.BytesIO(); doc.save(bio); bio.seek(0)
        return bio
    except Exception as e:
        return None, str(e)

def export_xlsx_from_flags(flags):
    try:
        import pandas as pd
        from io import BytesIO
        bio = BytesIO()
        df = pd.DataFrame(flags or [{"rule_id":"","severity":"","match":"","message":"","suggestion":""}])
        with pd.ExcelWriter(bio, engine="openpyxl") as w:
            df.to_excel(w, index=False, sheet_name="Linter Flags")
        bio.seek(0)
        return bio
    except Exception:
        return None

# ---------- UI ----------
st.title("InAA — Inclusive Apprenticeship Assistant (No-Login Demo)")
st.caption("Upload, lint, export, and chat. Conversation starters behave like InAA: click → the question is sent.")

# Keep chat state
if "chat" not in st.session_state:
    st.session_state["chat"] = []

# Conversation Starters (exact style: one-click sends the prompt)
with st.sidebar:
    st.header("Conversation Starters")
    starters = {
        "Draft my WPS": "Draft a hybrid Work Process Schedule for [occupation], [region]. Use task-not-method verbs and include accessibility notes.",
        "Audit this WPS/RTI": "Audit the draft I provide (below) for accessibility issues, show flags, and produce a clean copy.",
        "Accommodation SOP": "Create an Accommodation SOP for a small employer with community-college RTI; include a 10-day SLA and privacy notes.",
        "Partner & Funding map": "Draft a partner map (DOR/VR, AJCs, CILs, unions, CBOs, education) and a braided funding sketch for [county/region]."
    }
    for label, text in starters.items():
        if st.button(label, use_container_width=True):
            # push as a user message and mark to respond
            st.session_state["chat"].append(("user", text))
            st.session_state["starter_fired"] = True

    st.divider()
    st.write("OpenAI API:", "Enabled ✅" if client else "Off (linter still works)")

# Render chat history
for role, msg in st.session_state["chat"]:
    st.chat_message(role).write(msg)

# If a starter was clicked, reply (like InAA does)
if st.session_state.get("starter_fired"):
    reply = gpt_reply(st.session_state["chat"][-1][1])
    st.session_state["chat"].append(("assistant", reply))
    st.chat_message("assistant").write(reply)
    del st.session_state["starter_fired"]

# Normal chat box
user_msg = st.chat_input("Ask about WPS/RTI, accessibility, partners, or funding…")
if user_msg:
    st.session_state["chat"].append(("user", user_msg))
    st.chat_message("user").write(user_msg)
    st.session_state["chat"].append(("assistant", gpt_reply(user_msg)))
    st.chat_message("assistant").write(st.session_state["chat"][-1][1])

st.markdown("---")

# Upload/Paste → Linter → Exports
colL, colR = st.columns(2)
with colL:
    up = st.file_uploader("Upload WPS/RTI (.docx, .pdf, .txt, .md)", type=["docx","pdf","txt","md"])
with colR:
    pasted = st.text_area("Or paste your text here", height=220, placeholder="Paste a paragraph or full WPS…")

text = ""
if up is not None:
    text = extract_text(up)
elif pasted.strip():
    text = pasted

st.subheader("Accessibility Linter")
if st.button("Run Accessibility Linter", type="primary"):
    if not text.strip():
        st.warning("Upload or paste some text first.")
    else:
        flags, clean = run_linter(text)
        st.success(f"Found {len(flags)} potential issues.")
        if flags:
            try:
                import pandas as pd
                st.dataframe(pd.DataFrame(flags))
            except Exception:
                st.write(flags)
        st.subheader("Clean Copy (rule-based)")
        st.write(clean[:4000])

        if st.checkbox("Polish with AI (optional)"):
            st.write(gpt_reply("Rewrite into inclusive, task-focused language; remove needless prerequisites; keep plain language.\n\nOriginal:\n"+clean))

        st.subheader("Exports")
        c1, c2, c3 = st.columns(3)
        with c1:
            bio = export_docx("Linted/Rewritten WPS", clean)
            if isinstance(bio, tuple):  # error
                st.error(f"DOCX export error: {bio[1]}")
            else:
                st.download_button("Download WPS (.docx)", data=bio,
                                   file_name=f"WPS_Clean_{datetime.now().strftime('%Y%m%d_%H%M')}.docx")
        with c2:
            body = "RTI Outline (Derived)\n- Modules with UDL hooks\n- Accessible materials\n- Performance-based assessments\n"
            body += "\nNotes:\n" + clean[:1500]
            bio = export_docx("RTI Outline", body)
            if isinstance(bio, tuple):
                st.error(f"DOCX export error: {bio[1]}")
            else:
                st.download_button("Download RTI (.docx)", data=bio,
                                   file_name=f"RTI_Outline_{datetime.now().strftime('%Y%m%d_%H%M')}.docx")
        with c3:
            xbio = export_xlsx_from_flags(flags)
            if xbio:
                st.download_button("Download Checklist (.xlsx)", data=xbio,
                                   file_name=f"Accessibility_Checklist_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx")
            else:
                st.warning("Excel export unavailable on this runtime.")
