
import os, io, re, json
from datetime import datetime
import streamlit as st
from pypdf import PdfReader
from docx import Document as DocxDocument
import pandas as pd
from io import BytesIO

st.set_page_config(page_title="InAA — No-Login Demo", page_icon="🧭", layout="wide")

API_KEY = os.environ.get("OPENAI_API_KEY", "").strip()
client = None
if API_KEY:
    try:
        from openai import OpenAI
        client = OpenAI(api_key=API_KEY)
    except Exception:
        client = None

# Load rules & knowledge
with open("assets/linter_rules_v01.json","r",encoding="utf-8") as f:
    RULES = json.load(f)
KNOWLEDGE = []
if os.path.isdir("assets/knowledge"):
    for name in os.listdir("assets/knowledge"):
        if name.endswith(".txt"):
            try:
                KNOWLEDGE.append(open(os.path.join("assets/knowledge",name),"r",encoding="utf-8").read())
            except Exception:
                pass

def extract_text(file):
    name = file.name.lower()
    data = file.read()
    if name.endswith(".txt") or name.endswith(".md"):
        return data.decode("utf-8","ignore")
    if name.endswith(".docx"):
        buf = io.BytesIO(data)
        doc = DocxDocument(buf)
        parts = [p.text for p in doc.paragraphs]
        for tbl in doc.tables:
            for row in tbl.rows:
                parts.append(" | ".join([c.text for c in row.cells]))
        return "\n".join(parts)
    if name.endswith(".pdf"):
        buf = io.BytesIO(data)
        reader = PdfReader(buf)
        out = []
        for page in reader.pages:
            try: out.append(page.extract_text() or "")
            except: out.append("")
        return "\n".join(out)
    return ""

def lint(text):
    flags = []
    clean = text
    for r in RULES:
        pat = r.get("pattern","")
        flg = re.I if "i" in r.get("flags","") else 0
        try:
            for m in re.finditer(pat, text, flg):
                flags.append({
                    "rule_id": r["id"],
                    "category": r["category"],
                    "severity": r["severity"],
                    "match": m.group(0),
                    "message": r["message"],
                    "suggestion": r["suggestion"]
                })
            if r["id"]=="R-A1":
                clean = re.sub(r"\bclimb(ing)?\b","ascend", clean, flg)
            if r["id"]=="R-A2":
                clean = re.sub(r"lift(?:ing)?\s*(\d+)\s*(lb|lbs|pounds|kg)?",
                               r"move materials up to \1 \2 using safe methods", clean, flg)
            if r["id"]=="R-B3":
                clean = re.sub(r"(excellent communication|team player|self[- ]starter|strong work ethic|detail[- ]oriented)",
                               r"communicates clearly with mentors and closes the loop on tasks", clean, flg)
        except:
            pass
    return flags, clean

def gpt(prompt, text):
    if not client: return text
    system = "You are the Accessibility WPS Assistant. Use inclusive, plain language and task-not-method phrasing."
    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role":"system","content":system},
                      {"role":"user","content":prompt + "\n\n---\nOriginal:\n" + text}],
            temperature=0.3, max_tokens=1200
        )
        return resp.choices[0].message.content
    except Exception:
        return text

def export_docx(template_name, title, body):
    path = os.path.join("assets","templates",template_name)
    try:
        doc = DocxDocument(path)
    except Exception:
        doc = DocxDocument()
    doc.add_page_break()
    doc.add_heading(title, level=1)
    for line in body.split("\n"):
        doc.add_paragraph(line)
    bio = BytesIO()
    doc.save(bio); bio.seek(0)
    return bio

def export_checklist(flags):
    df = pd.DataFrame(flags)
    bio = BytesIO()
    with pd.ExcelWriter(bio, engine="openpyxl") as w:
        df.to_excel(w, index=False, sheet_name="Linter Flags")
    bio.seek(0); return bio

st.title("InAA — Inclusive Apprenticeship Assistant (No-Login Demo)")
st.caption("Upload, lint, chat, and export. No ChatGPT account required.")

with st.sidebar:
    st.header("Conversation Starters")
    if st.button("Draft my WPS"):
        st.session_state["seed"] = "Draft a hybrid WPS for [occupation], [region]. Use task-not-method verbs and include accessibility notes."
    if st.button("Audit this WPS/RTI"):
        st.session_state["seed"] = "Audit the uploaded/pasted draft for accessibility issues, show flags, and produce a clean copy."
    if st.button("Accommodation SOP"):
        st.session_state["seed"] = "Create an Accommodation SOP for a small employer with community-college RTI, include a 10-day SLA and privacy notes."
    if st.button("Partner & Funding map"):
        st.session_state["seed"] = "Draft a partner map (DOR/VR, AJCs, CILs, unions, CBOs) and a braided funding sketch for [county]."
    st.divider()
    st.write("OpenAI API:", "Enabled ✅" if client else "Off (linter still works)")

left, right = st.columns(2)
with left:
    up = st.file_uploader("Upload WPS/RTI (.docx, .pdf, .txt, .md)", type=["docx","pdf","txt","md"])
with right:
    pasted = st.text_area("Or paste your text here", height=220)

text = ""
if up is not None:
    text = extract_text(up)
elif pasted.strip():
    text = pasted

flags, clean = ([], "")
if text.strip() and st.button("Run Accessibility Linter"):
    flags, clean = lint(text)
    st.success(f"Found {len(flags)} potential issues.")
    if flags:
        st.dataframe(pd.DataFrame(flags))
    st.subheader("Clean Copy (rule-based)")
    st.write(clean[:4000])
    if st.checkbox("Polish with AI (if API enabled)"):
        clean = gpt("Rewrite into inclusive, task-focused language; remove needless prerequisites; keep plain language.", clean)
        st.subheader("Clean Copy (polished)")
        st.write(clean[:4000])

st.divider()
st.subheader("Ask Questions")
if "chat" not in st.session_state: st.session_state["chat"] = []
if "seed" in st.session_state:
    st.chat_message("assistant").write(st.session_state["seed"])
    del st.session_state["seed"]

msg = st.chat_input("Ask about WPS/RTI, accessibility, partners, or funding…")
if msg:
    st.chat_message("user").write(msg)
    if client:
        context = "\n\n".join([k[:1800] for k in KNOWLEDGE[:3]])
        reply = gpt("Answer plainly; cite concepts from context where helpful.\nContext:\n"+context, msg)
    else:
        reply = "AI chat is off (no API key). I can still lint text and export files."
    st.chat_message("assistant").write(reply)

st.divider()
st.subheader("Exports")
c1, c2, c3 = st.columns(3)
with c1:
    if st.button("Export WPS (.docx)"):
        content = clean if clean else text
        if not content.strip():
            st.warning("Upload or paste text, run the linter, then export.")
        else:
            bio = export_docx("WPS_Draft_Template.docx", "Linted/Rewritten WPS", content)
            st.download_button("Download WPS", data=bio, file_name=f"WPS_Clean_{datetime.now().strftime('%Y%m%d_%H%M')}.docx")
with c2:
    if st.button("Export RTI (.docx)"):
        body = "RTI Outline (Derived)\n- Modules with UDL hooks\n- Accessible materials\n- Performance-based assessments\n"
        if clean.strip(): body += "\nNotes:\n"+clean[:1500]
        bio = export_docx("RTI_Outline_Template.docx", "RTI Outline", body)
        st.download_button("Download RTI", data=bio, file_name=f"RTI_Outline_{datetime.now().strftime('%Y%m%d_%H%M')}.docx")
with c3:
    if st.button("Export Accommodation SOP (.docx)"):
        body = "Accommodation SOP (Derived)\n- Acknowledge in 2 business days\n- Meet in 5–10 days\n- Privacy-respecting workflow\n"
        bio = export_docx("Accommodation_SOP_Template.docx", "Accommodation SOP", body)
        st.download_button("Download SOP", data=bio, file_name=f"Accommodation_SOP_{datetime.now().strftime('%Y%m%d_%H%M')}.docx")

c4, c5, c6 = st.columns(3)
with c4:
    if st.button("Export Checklist (.xlsx)"):
        bio = export_checklist(flags)
        st.download_button("Download Checklist", data=bio, file_name=f"Accessibility_Checklist_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx")
with c5:
    if st.button("Export Partner Map (.md)"):
        md = "# Partner Map\n\n- DOR/VR\n- AJCs\n- CILs\n- Unions/LM\n- CBOs\n- Education partners\n"
        st.download_button("Download Partner Map", data=md, file_name=f"Partner_Map_{datetime.now().strftime('%Y%m%d_%H%M')}.md")
with c6:
    if st.button("Export Funding Plan (.md)"):
        md = "# Funding Plan\n\n- WIOA I/III/IV\n- Perkins V\n- SNAP E&T\n- VR\n- Employer match\n- Philanthropy\n"
        st.download_button("Download Funding Plan", data=md, file_name=f"Funding_Plan_{datetime.now().strftime('%Y%m%d_%H%M')}.md")

if st.button("Export Decision Log (.md)"):
    md = "# Decision Log\n\n| Date | Decision | Rationale | Source | Owner |\n|---|---|---|---|---|\n"
    st.download_button("Download Decision Log", data=md, file_name=f"Decision_Log_{datetime.now().strftime('%Y%m%d_%H%M')}.md")

st.caption("Tip: Prefer DOCX or paste text if a PDF's text layer is messy.")
