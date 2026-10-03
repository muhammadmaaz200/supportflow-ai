# SupportFlow AI — Complete Admin + User Edition

A local FastAPI portfolio project for an AI customer support platform with:

- Separate **Customer** and **Admin** panels
- Role-based login using signed sessions
- Gemini-powered support responses
- Lightweight lexical RAG over PDF/TXT/MD knowledge files
- Sentiment, emotion and urgency signals
- Automatic escalation for elevated urgency
- Manual human-support requests
- Admin dashboard, analytics, conversations and audit trail
- Knowledge-base upload + indexing
- SQLite persistence

## 1. Setup

Create and activate a virtual environment, then install dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and add your **newly rotated** Gemini API key:

```env
GEMINI_API_KEY=YOUR_NEW_KEY
GEMINI_MODEL=gemini-2.5-flash
SESSION_SECRET=use-a-long-random-secret
```

Do not put a real key in GitHub or share it in chat.

## 2. Run

```powershell
python -m uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000`.

## 3. Demo accounts

- Admin: `admin@supportflow.local` / `Admin@123`
- Customer: `user@supportflow.local` / `User@123`

These credentials are for local portfolio testing only.

## 4. Knowledge base

Log in as Admin → **Knowledge Base** → upload a PDF, TXT or MD file. The application extracts text, chunks it and makes it available to the lexical retriever.

A fictional NovaMart demo PDF can be placed in `data/knowledge/` for testing.

## 5. Important implementation note

The included RAG layer is intentionally lightweight: it uses lexical token overlap, not embeddings/vector search. For a production architecture, replace the retriever with an embedding model + vector database and add stronger authentication, CSRF protection, rate limiting, structured observability and a production secret manager.
