# InAA No-Login Demo (Streamlit)
This is a demo site for your Inclusive Apprenticeship Assistant.

## Deploy (No coding)
1) Create a free account at Streamlit Community Cloud.
2) Make a new public GitHub repo and upload all files (keep folders).
3) In Streamlit Cloud → Deploy → choose your repo → Main file: `app.py`.
4) (Optional) In Settings → Secrets, add:
```
OPENAI_API_KEY="sk-..."
```
This turns on chat and smarter rewrites. Without it, the linter + exports still work.

Generated: 2025-08-31
