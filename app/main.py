import os
import shutil
import traceback
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
    init_db,
    audit,
    save_conversation,
    user_conversations,
    all_conversations,
    dashboard,
    audit_rows,
    save_knowledge,
    create_escalation,
    escalations,
    update_escalation,
)
from .services.sentiment import analyze
from .services.rag import KnowledgeBase
from .services.agent import SupportAgent


# ============================================================
# APP CONFIGURATION
# ============================================================

app = FastAPI(
    title="SupportFlow AI",
    version="1.0.0"
)


app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    same_site="lax",
    https_only=False,
)


app.mount(
    "/static",
    StaticFiles(
        directory=str(Path(__file__).parent / "static")
    ),
    name="static",
)


templates = Jinja2Templates(
    directory=str(Path(__file__).parent / "templates")
)


# ============================================================
# DATABASE / AUTH / KNOWLEDGE INITIALIZATION
# ============================================================

init_db()
init_auth_db()

kb = KnowledgeBase(KB_DIR)


for filename in sorted(
    {item["filename"] for item in kb.chunks}
):
    save_knowledge(
        filename,
        sum(
            1
            for item in kb.chunks
            if item["filename"] == filename
        )
    )


agent = SupportAgent(kb)


ALLOWED_EXTENSIONS = {
    ".pdf",
    ".txt",
    ".md",
}


# ============================================================
# REQUEST MODELS
# ============================================================

class ChatRequest(BaseModel):
    message: str = Field(
        min_length=1,
        max_length=4000
    )


class EscalationRequest(BaseModel):
    reason: str = Field(
        default="Customer requested human support",
        max_length=800
    )


class StatusRequest(BaseModel):
    status: str = Field(
        min_length=1,
        max_length=30
    )


# ============================================================
# AUTH HELPERS
# ============================================================

def current_user(request: Request):
    return request.session.get("user")


def require_user(request: Request):
    user = current_user(request)

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Authentication required"
        )

    return user


def require_role(request: Request, role: str):
    user = require_user(request)

    if user["role"] != role:
        raise HTTPException(
            status_code=403,
            detail="Forbidden"
        )

    return user


# ============================================================
# HOME
# ============================================================

@app.get(
    "/",
    include_in_schema=False
)
def home(request: Request):

    user = current_user(request)

    if not user:
        return RedirectResponse(
            "/login",
            status_code=303
        )

    return RedirectResponse(
        "/admin" if user["role"] == "admin" else "/user",
        status_code=303
    )


# ============================================================
# LOGIN PAGE
# ============================================================

@app.get(
    "/login",
    response_class=HTMLResponse
)
def login_page(request: Request):

    if current_user(request):
        return RedirectResponse(
            "/",
            status_code=303
        )

    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={
            "request": request,
            "error": None
        }
    )


# ============================================================
# LOGIN
# ============================================================

@app.post(
    "/login",
    response_class=HTMLResponse
)
def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...)
):

    try:

        print("LOGIN STEP 1: request received")
        print("LOGIN STEP 2: email =", email)

        # ----------------------------------------------------
        # AUTHENTICATION
        # ----------------------------------------------------

        user = authenticate(
            email,
            password
        )

        print(
            "LOGIN STEP 3: authenticate result =",
            user
        )

        # ----------------------------------------------------
        # INVALID LOGIN
        # ----------------------------------------------------

        if not user:

            print(
                "LOGIN STEP 4: invalid credentials"
            )

            try:

                audit(
                    email,
                    "login_failed",
                    "Invalid credentials",
                    "failed"
                )

                print(
                    "LOGIN STEP 5: failed-login audit saved"
                )

            except Exception as audit_error:

                print(
                    "LOGIN AUDIT ERROR:",
                    repr(audit_error)
                )

            return templates.TemplateResponse(
                request=request,
                name="login.html",
                context={
                    "request": request,
                    "error": "Invalid email or password."
                },
                status_code=401,
            )

        # ----------------------------------------------------
        # SUCCESSFUL LOGIN
        # ----------------------------------------------------

        print(
            "LOGIN STEP 6: authentication successful"
        )

        request.session["user"] = user

        print(
            "LOGIN STEP 7: session saved"
        )

        try:

            audit(
                user["email"],
                "login",
                "Successful sign-in"
            )

            print(
                "LOGIN STEP 8: successful-login audit saved"
            )

        except Exception as audit_error:

            print(
                "LOGIN AUDIT ERROR:",
                repr(audit_error)
            )

        # ----------------------------------------------------
        # REDIRECT
        # ----------------------------------------------------

        if user["role"] == "admin":

            print(
                "LOGIN STEP 9: redirecting to admin"
            )

            return RedirectResponse(
                "/admin",
                status_code=303
            )

        print(
            "LOGIN STEP 9: redirecting to user"
        )

        return RedirectResponse(
            "/user",
            status_code=303
        )

    except Exception as e:

        print(
            "LOGIN ERROR:",
            repr(e)
        )

        traceback.print_exc()

        return HTMLResponse(
            content=(
                "<h2>Login Error</h2>"
                f"<p>{type(e).__name__}: {e}</p>"
            ),
            status_code=500
        )


# ============================================================
# LOGOUT
# ============================================================

@app.get(
    "/logout",
    response_class=HTMLResponse
)
def logout(request: Request):

    try:

        print(
            "LOGOUT STEP 1: request received"
        )

        user = current_user(request)

        print(
            "LOGOUT STEP 2: session user =",
            user
        )

        # Clear session FIRST.
        # Database/audit failure must not block logout.

        request.session.clear()

        print(
            "LOGOUT STEP 3: session cleared"
        )

        # Audit is optional.
        if user:

            try:

                audit(
                    user.get("email", ""),
                    "logout",
                    "Session ended"
                )

                print(
                    "LOGOUT STEP 4: audit saved"
                )

            except Exception as audit_error:

                print(
                    "LOGOUT AUDIT ERROR:",
                    repr(audit_error)
                )

        print(
            "LOGOUT STEP 5: redirecting to login"
        )

        return RedirectResponse(
            "/login",
            status_code=303
        )

    except Exception as e:

        print(
            "LOGOUT ERROR:",
            repr(e)
        )

        traceback.print_exc()

        try:
            request.session.clear()
        except Exception:
            pass

        return HTMLResponse(
            content=f"""
            <html>
                <head>
                    <title>Logout Error</title>
                </head>

                <body style="
                    font-family: Arial, sans-serif;
                    padding: 40px;
                    background: #f5f5f5;
                ">

                    <h1>Logout Error</h1>

                    <p>
                        <strong>Error Type:</strong>
                    </p>

                    <pre>{type(e).__name__}</pre>

                    <p>
                        <strong>Error Message:</strong>
                    </p>

                    <pre>{str(e)}</pre>

                    <br>

                    <a href="/login">
                        Go to Login
                    </a>

                </body>
            </html>
            """,
            status_code=500
        )


# ============================================================
# USER PANEL
# ============================================================

@app.get(
    "/user",
    response_class=HTMLResponse
)
def user_panel(request: Request):

    user = require_role(
        request,
        "user"
    )

    return templates.TemplateResponse(
        request=request,
        name="user.html",
        context={
            "request": request,
            "user": user
        }
    )


# ============================================================
# ADMIN PANEL
# ============================================================

@app.get(
    "/admin",
    response_class=HTMLResponse
)
def admin_panel(request: Request):

    user = require_role(
        request,
        "admin"
    )

    return templates.TemplateResponse(
        request=request,
        name="admin.html",
        context={
            "request": request,
            "user": user
        }
    )


# ============================================================
# HEALTH
# ============================================================

@app.get("/api/health")
def health():

    return {
        "status": "ok",
        "gemini_configured": bool(
            os.getenv("GEMINI_API_KEY")
        ),
        "model": os.getenv(
            "GEMINI_MODEL",
            "gemini-2.5-flash"
        )
    }


# ============================================================
# CHAT
# ============================================================

@app.post("/api/chat")
def chat(
    request: Request,
    payload: ChatRequest
):

    try:

        print(
            "CHAT STEP 1: request received"
        )

        # ----------------------------------------------------
        # AUTHENTICATION
        # ----------------------------------------------------

        user = require_user(request)

        print(
            "CHAT STEP 2: authenticated user =",
            user.get("email")
        )

        # ----------------------------------------------------
        # SENTIMENT ANALYSIS
        # ----------------------------------------------------

        print(
            "CHAT STEP 3: running sentiment analysis"
        )

        analysis = analyze(
            payload.message
        )

        print(
            "CHAT STEP 4: analysis completed =",
            analysis
        )

        # ----------------------------------------------------
        # GEMINI / AI AGENT
        # ----------------------------------------------------

        print(
            "CHAT STEP 5: calling SupportAgent"
        )

        answer = agent.answer(
            payload.message,
            analysis
        )

        print(
            "CHAT STEP 6: agent response received"
        )

        # ----------------------------------------------------
        # KNOWLEDGE BASE SEARCH
        # ----------------------------------------------------

        print(
            "CHAT STEP 7: searching knowledge base"
        )

        hits = kb.search(
            payload.message,
            top_k=4
        )

        print(
            "CHAT STEP 8: knowledge search completed, hits =",
            len(hits)
        )

        sources = [
            {
                "filename": h["filename"],
                "score": h["score"]
            }
            for h in hits
        ]

        # ----------------------------------------------------
        # SAVE CONVERSATION
        # ----------------------------------------------------

        print(
            "CHAT STEP 9: saving conversation"
        )

        try:

            conversation_id = save_conversation(
                user,
                payload.message,
                answer,
                analysis,
                sources
            )

            print(
                "CHAT STEP 10: conversation saved, id =",
                conversation_id
            )

        except Exception as db_error:

            print(
                "========================================"
            )

            print(
                "CHAT DATABASE ERROR:",
                repr(db_error)
            )

            print(
                "DATABASE ERROR TYPE:",
                type(db_error).__name__
            )

            traceback.print_exc()

            print(
                "========================================"
            )

            return JSONResponse(
                status_code=500,
                content={
                    "error": "Database error",
                    "message": str(db_error),
                    "type": type(db_error).__name__
                }
            )

        # ----------------------------------------------------
        # AUDIT
        # ----------------------------------------------------

        try:

            audit(
                user["email"],
                "chat",
                f"Conversation {conversation_id}"
            )

            print(
                "CHAT STEP 11: audit saved"
            )

        except Exception as audit_error:

            print(
                "CHAT AUDIT ERROR:",
                repr(audit_error)
            )

        # ----------------------------------------------------
        # AUTO ESCALATION
        # ----------------------------------------------------

        if analysis.get("escalated"):

            print(
                "CHAT STEP 12: creating escalation"
            )

            try:

                create_escalation(
                    conversation_id,
                    user,
                    "AI detected elevated urgency"
                )

                print(
                    "CHAT STEP 13: escalation created"
                )

            except Exception as escalation_error:

                print(
                    "ESCALATION ERROR:",
                    repr(escalation_error)
                )

            try:

                audit(
                    user["email"],
                    "auto_escalation",
                    f"Conversation {conversation_id}"
                )

            except Exception as audit_error:

                print(
                    "ESCALATION AUDIT ERROR:",
                    repr(audit_error)
                )

        # ----------------------------------------------------
        # SUCCESS RESPONSE
        # ----------------------------------------------------

        print(
            "CHAT STEP 14: returning successful response"
        )

        return {
            "id": conversation_id,
            "answer": answer,
            "analysis": analysis,
            "sources": sources,
        }

    except HTTPException:
        raise

    except Exception as e:

        print(
            "========================================"
        )

        print(
            "CHAT ERROR:",
            repr(e)
        )

        print(
            "CHAT ERROR TYPE:",
            type(e).__name__
        )

        traceback.print_exc()

        print(
            "========================================"
        )

        return JSONResponse(
            status_code=500,
            content={
                "error": "Chat service error",
                "message": str(e),
                "type": type(e).__name__
            }
        )


# ============================================================
# CURRENT USER
# ============================================================

@app.get("/api/me")
def me(request: Request):

    return {
        "user": require_user(request)
    }


# ============================================================
# USER CONVERSATIONS
# ============================================================

@app.get("/api/my/conversations")
def my_conversations(request: Request):

    user = require_role(
        request,
        "user"
    )

    return {
        "conversations": user_conversations(
            user["id"]
        )
    }


# ============================================================
# MANUAL ESCALATION
# ============================================================

@app.post(
    "/api/my/conversations/{conversation_id}/escalate"
)
def manual_escalate(
    request: Request,
    conversation_id: int,
    payload: EscalationRequest
):

    user = require_role(
        request,
        "user"
    )

    rows = [
        x
        for x in user_conversations(
            user["id"]
        )
        if x["id"] == conversation_id
    ]

    if not rows:

        raise HTTPException(
            404,
            "Conversation not found"
        )

    escalation_id = create_escalation(
        conversation_id,
        user,
        payload.reason
    )

    try:

        audit(
            user["email"],
            "manual_escalation",
            f"Escalation {escalation_id}"
        )

    except Exception as audit_error:

        print(
            "MANUAL ESCALATION AUDIT ERROR:",
            repr(audit_error)
        )

    return {
        "status": "open",
        "escalation_id": escalation_id
    }


# ============================================================
# ADMIN DASHBOARD API
# ============================================================

@app.get("/api/dashboard")
def api_dashboard(request: Request):

    require_role(
        request,
        "admin"
    )

    return dashboard()


# ============================================================
# ADMIN CONVERSATIONS
# ============================================================

@app.get("/api/conversations")
def api_conversations(request: Request):

    require_role(
        request,
        "admin"
    )

    return {
        "conversations": all_conversations()
    }


# ============================================================
# ADMIN ESCALATIONS
# ============================================================

@app.get("/api/escalations")
def api_escalations(request: Request):

    require_role(
        request,
        "admin"
    )

    return {
        "escalations": escalations()
    }


# ============================================================
# UPDATE ESCALATION
# ============================================================

@app.patch(
    "/api/escalations/{escalation_id}"
)
def api_update_escalation(
    request: Request,
    escalation_id: int,
    payload: StatusRequest
):

    user = require_role(
        request,
        "admin"
    )

    status = payload.status.strip().lower()

    if status not in {
        "open",
        "in_progress",
        "resolved",
        "closed"
    }:

        raise HTTPException(
            400,
            "Status must be open, in_progress, resolved, or closed"
        )

    update_escalation(
        escalation_id,
        status
    )

    try:

        audit(
            user["email"],
            "escalation_update",
            f"Escalation {escalation_id} → {status}"
        )

    except Exception as audit_error:

        print(
            "ESCALATION UPDATE AUDIT ERROR:",
            repr(audit_error)
        )

    return {
        "ok": True
    }


# ============================================================
# AUDIT LOGS
# ============================================================

@app.get("/api/audit")
def api_audit(request: Request):

    require_role(
        request,
        "admin"
    )

    return {
        "audit": audit_rows()
    }


# ============================================================
# KNOWLEDGE BASE UPLOAD
# ============================================================

@app.post("/api/knowledge/upload")
async def knowledge_upload(
    request: Request,
    file: UploadFile = File(...)
):

    user = require_role(
        request,
        "admin"
    )

    suffix = Path(
        file.filename or ""
    ).suffix.lower()

    if suffix not in ALLOWED_EXTENSIONS:

        raise HTTPException(
            400,
            "Only PDF, TXT and MD files are supported."
        )

    safe_name = Path(
        file.filename
    ).name

    destination = UPLOAD_DIR / safe_name

    with destination.open("wb") as buffer:

        shutil.copyfileobj(
            file.file,
            buffer
        )

    final_path = KB_DIR / safe_name

    shutil.copy2(
        destination,
        final_path
    )

    kb.add_file(
        final_path
    )

    chunk_count = sum(
        1
        for c in kb.chunks
        if c["filename"] == safe_name
    )

    save_knowledge(
        safe_name,
        chunk_count
    )

    try:

        audit(
            user["email"],
            "knowledge_upload",
            f"{safe_name} ({chunk_count} chunks)"
        )

    except Exception as audit_error:

        print(
            "KNOWLEDGE UPLOAD AUDIT ERROR:",
            repr(audit_error)
        )

    return {
        "ok": True,
        "message": f"{safe_name} indexed successfully.",
        "chunks": chunk_count
    }


# ============================================================
# KNOWLEDGE BASE
# ============================================================

@app.get("/api/knowledge")
def api_knowledge(request: Request):

    require_role(
        request,
        "admin"
    )

    return {
        "documents": [
            {
                "filename": name,
                "chunks": sum(
                    1
                    for c in kb.chunks
                    if c["filename"] == name
                )
            }
            for name in sorted(
                {
                    c["filename"]
                    for c in kb.chunks
                }
            )
        ]
    }