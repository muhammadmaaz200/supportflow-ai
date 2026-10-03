import os
import shutil
from pathlib import Path

from fastapi import FastAPI, Request, Form, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from starlette.middleware.sessions import SessionMiddleware

from .config import SESSION_SECRET, UPLOAD_DIR, KB_DIR
from .auth import init_auth_db, authenticate
from .db import (
    init_db, audit, save_conversation, user_conversations, all_conversations,
    dashboard, audit_rows, save_knowledge, create_escalation, escalations,
    update_escalation,
)
from .services.sentiment import analyze
from .services.rag import KnowledgeBase
from .services.agent import SupportAgent

app = FastAPI(title="SupportFlow AI", version="1.0.0")
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET, same_site="lax", https_only=False)
app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

init_db()
init_auth_db()
kb = KnowledgeBase(KB_DIR)
for filename in sorted({item["filename"] for item in kb.chunks}):
    save_knowledge(filename, sum(1 for item in kb.chunks if item["filename"] == filename))
agent = SupportAgent(kb)

ALLOWED_EXTENSIONS = {".pdf", ".txt", ".md"}


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


class EscalationRequest(BaseModel):
    reason: str = Field(default="Customer requested human support", max_length=800)


class StatusRequest(BaseModel):
    status: str = Field(min_length=1, max_length=30)


def current_user(request: Request):
    return request.session.get("user")


def require_user(request: Request):
    user = current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


def require_role(request: Request, role: str):
    user = require_user(request)
    if user["role"] != role:
        raise HTTPException(status_code=403, detail="Forbidden")
    return user


@app.get("/", include_in_schema=False)
def home(request: Request):
    user = current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    return RedirectResponse("/admin" if user["role"] == "admin" else "/user", status_code=303)


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    if current_user(request):
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(request=request, name="login.html", context={"request": request, "error": None})


@app.post("/login", response_class=HTMLResponse)
def login(request: Request, email: str = Form(...), password: str = Form(...)):
    user = authenticate(email, password)
    if not user:
        audit(email, "login_failed", "Invalid credentials", "failed")
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={"request": request, "error": "Invalid email or password."},
            status_code=401,
        )
    request.session["user"] = user
    audit(user["email"], "login", "Successful sign-in")
    return RedirectResponse("/admin" if user["role"] == "admin" else "/user", status_code=303)


@app.get("/logout")
def logout(request: Request):
    user = current_user(request)
    if user:
        audit(user["email"], "logout", "Session ended")
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


@app.get("/user", response_class=HTMLResponse)
def user_panel(request: Request):
    user = require_role(request, "user")
    return templates.TemplateResponse(request=request, name="user.html", context={"request": request, "user": user})


@app.get("/admin", response_class=HTMLResponse)
def admin_panel(request: Request):
    user = require_role(request, "admin")
    return templates.TemplateResponse(request=request, name="admin.html", context={"request": request, "user": user})


@app.get("/api/health")
def health():
    return {"status": "ok", "gemini_configured": bool(os.getenv("GEMINI_API_KEY")), "model": os.getenv("GEMINI_MODEL", "gemini-2.5-flash")}


@app.post("/api/chat")
def chat(request: Request, payload: ChatRequest):
    user = require_user(request)
    analysis = analyze(payload.message)
    answer = agent.answer(payload.message, analysis)
    hits = kb.search(payload.message, top_k=4)
    sources = [{"filename": h["filename"], "score": h["score"]} for h in hits]
    conversation_id = save_conversation(user, payload.message, answer, analysis, sources)
    audit(user["email"], "chat", f"Conversation {conversation_id}")
    if analysis["escalated"]:
        create_escalation(conversation_id, user, "AI detected elevated urgency")
        audit(user["email"], "auto_escalation", f"Conversation {conversation_id}")
    return {
        "id": conversation_id,
        "answer": answer,
        "analysis": analysis,
        "sources": sources,
    }


@app.get("/api/me")
def me(request: Request):
    return {"user": require_user(request)}


@app.get("/api/my/conversations")
def my_conversations(request: Request):
    user = require_role(request, "user")
    return {"conversations": user_conversations(user["id"])}


@app.post("/api/my/conversations/{conversation_id}/escalate")
def manual_escalate(request: Request, conversation_id: int, payload: EscalationRequest):
    user = require_role(request, "user")
    rows = [x for x in user_conversations(user["id"]) if x["id"] == conversation_id]
    if not rows:
        raise HTTPException(404, "Conversation not found")
    escalation_id = create_escalation(conversation_id, user, payload.reason)
    audit(user["email"], "manual_escalation", f"Escalation {escalation_id}")
    return {"status": "open", "escalation_id": escalation_id}


@app.get("/api/dashboard")
def api_dashboard(request: Request):
    require_role(request, "admin")
    return dashboard()


@app.get("/api/conversations")
def api_conversations(request: Request):
    require_role(request, "admin")
    return {"conversations": all_conversations()}


@app.get("/api/escalations")
def api_escalations(request: Request):
    require_role(request, "admin")
    return {"escalations": escalations()}


@app.patch("/api/escalations/{escalation_id}")
def api_update_escalation(request: Request, escalation_id: int, payload: StatusRequest):
    user = require_role(request, "admin")
    status = payload.status.strip().lower()
    if status not in {"open", "in_progress", "resolved", "closed"}:
        raise HTTPException(400, "Status must be open, in_progress, resolved, or closed")
    update_escalation(escalation_id, status)
    audit(user["email"], "escalation_update", f"Escalation {escalation_id} → {status}")
    return {"ok": True}


@app.get("/api/audit")
def api_audit(request: Request):
    require_role(request, "admin")
    return {"audit": audit_rows()}


@app.post("/api/knowledge/upload")
async def knowledge_upload(request: Request, file: UploadFile = File(...)):
    user = require_role(request, "admin")
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, "Only PDF, TXT and MD files are supported.")
    safe_name = Path(file.filename).name
    destination = UPLOAD_DIR / safe_name
    with destination.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    final_path = KB_DIR / safe_name
    shutil.copy2(destination, final_path)
    kb.add_file(final_path)
    chunk_count = sum(1 for c in kb.chunks if c["filename"] == safe_name)
    save_knowledge(safe_name, chunk_count)
    audit(user["email"], "knowledge_upload", f"{safe_name} ({chunk_count} chunks)")
    return {"ok": True, "message": f"{safe_name} indexed successfully.", "chunks": chunk_count}


@app.get("/api/knowledge")
def api_knowledge(request: Request):
    require_role(request, "admin")
    return {"documents": [{"filename": name, "chunks": sum(1 for c in kb.chunks if c["filename"] == name)} for name in sorted({c["filename"] for c in kb.chunks})]}
