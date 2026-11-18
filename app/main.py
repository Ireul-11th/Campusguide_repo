import json
import logging
import re
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from . import accounts, auth, config, db
from .constants import DOC_TYPES, PROC_STATUS, VALIDITY
from .rag import embedding, llm, pipeline, rerank
from .rag.ingest import process_document, purge_vectors
from .rag.retrieval import index

log = logging.getLogger("campusguide")
APP_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(APP_DIR / "templates"))


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.init_db()
    # Tài liệu đang xử lý dở khi server tắt: đánh dấu thất bại để quản trị viên thử lại.
    db.execute(
        "UPDATE documents SET proc_status='failed', error='Bị gián đoạn khi máy chủ khởi động lại, hãy bấm Thử lại.' "
        "WHERE proc_status IN ('pending','extracting','chunking','indexing')"
    )
    auth.bootstrap_admin()
    index.reload()
    yield


app = FastAPI(title="CampusGuide AI", lifespan=lifespan)
app.include_router(accounts.router)
app.mount("/static", StaticFiles(directory=str(APP_DIR / "static")), name="static")


# ---------------------------------------------------------------- helpers
def doc_row(r) -> dict:
    d = dict(r)
    d["doc_type_label"] = DOC_TYPES.get(d["doc_type"], "Khác")
    d["validity_label"] = VALIDITY.get(d["validity"], "Chưa xác minh")
    d["proc_label"] = PROC_STATUS.get(d["proc_status"], d["proc_status"])
    d.pop("stored_name", None)
    return d


def valid_date(value: str, label: str) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(422, f"{label} phải có dạng YYYY-MM-DD.")
    return value


def page_ctx(request: Request, active: str, user=None) -> dict:
    return {
        "active": active,
        "doc_types": DOC_TYPES,
        "validity": VALIDITY,
        "user": auth.public_user(user) if user else None,
    }


def _page(request: Request, template: str, active: str, need: str = "login", status_code: int = 200, **extra):
    """need: '' (công khai) | 'login' | 'data' (quản trị dữ liệu) | 'admin'."""
    user = auth.user_from_request(request)
    if need and not user:
        return RedirectResponse(auth.login_redirect_url(request), status_code=303)
    ctx = {**page_ctx(request, active, user), **extra}
    if need == "admin" and user["role"] != "admin" or need == "data" and not auth.public_user(user)["can_manage_data"]:
        ctx["denied"] = "admin" if need == "admin" else "data"
        return templates.TemplateResponse(request, "denied.html", ctx, status_code=403)
    return templates.TemplateResponse(request, template, ctx, status_code=status_code)


# ---------------------------------------------------------------- pages
@app.get("/login")
def page_login(request: Request, next: str = ""):
    if auth.user_from_request(request):
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(request, "login.html", {**page_ctx(request, "login"), "next": next if next.startswith("/") and not next.startswith("//") else "/"})


@app.get("/")
def page_chat(request: Request):
    return _page(request, "chat.html", "chat")


@app.get("/library")
def page_library(request: Request):
    return _page(request, "library.html", "library")


@app.get("/library/{doc_id}")
def page_document(request: Request, doc_id: int):
    r = db.one("SELECT id FROM documents WHERE id = ? AND proc_status = 'done'", [doc_id])
    return _page(request, "document.html", "library", status_code=200 if r else 404, doc_id=doc_id)


@app.get("/admin")
def page_admin(request: Request):
    return _page(request, "admin.html", "admin", need="data")


@app.get("/users")
def page_users(request: Request):
    return _page(request, "users.html", "users", need="admin")


@app.get("/api/health")
def health(_=Depends(auth.current_user)):
    return {
        "llm_configured": llm.is_configured(),
        "llm": llm.provider_label(),
        "semantic_search": index.stats["semantic"],
        "embedding_model": config.EMBEDDING_MODEL or None,
        "index": index.stats,
        "rerank_model": config.RERANK_MODEL or None,
        "ocr": config.OCR_ENABLED,
        "max_upload_mb": config.MAX_UPLOAD_MB,
        "allowed_ext": sorted(config.ALLOWED_EXT),
    }


# ---------------------------------------------------------------- chat
class ChatIn(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    conversation_id: int | None = None


def _own_conv(conv_id: int, uid: int):
    conv = db.one("SELECT * FROM conversations WHERE id = ? AND user_id = ?", [conv_id, uid])
    if not conv:
        raise HTTPException(404, "Không tìm thấy hội thoại.")
    return conv


def _msg(r) -> dict:
    d = dict(r)
    d["sources"] = json.loads(d["sources"] or "[]")
    d["warnings"] = json.loads(d["warnings"] or "[]")
    return d


@app.post("/api/chat")
def chat(body: ChatIn, user=Depends(auth.current_user)):
    question = body.question.strip()
    if not question:
        raise HTTPException(422, "Câu hỏi trống.")

    if body.conversation_id:
        conv = _own_conv(body.conversation_id, user["id"])
        conv_id = conv["id"]
    else:
        title = question if len(question) <= 60 else question[:57] + "..."
        conv_id = db.execute("INSERT INTO conversations (user_id, title) VALUES (?, ?)", [user["id"], title])

    history = [
        {"role": r["role"], "content": r["content"]}
        for r in db.query("SELECT role, content FROM messages WHERE conv_id = ? ORDER BY id", [conv_id])
    ]
    user_msg_id = db.execute("INSERT INTO messages (conv_id, role, content) VALUES (?, 'user', ?)", [conv_id, question])

    result = pipeline.ask(question, history)
    content = result["answer"]
    bot_id = db.execute(
        "INSERT INTO messages (conv_id, role, content, status, sources, warnings) VALUES (?, 'assistant', ?, ?, ?, ?)",
        [conv_id, content, result["status"], json.dumps(result["sources"]), json.dumps(result["warnings"])],
    )
    db.execute("UPDATE conversations SET updated_at = datetime('now') WHERE id = ?", [conv_id])
    return {
        "conversation_id": conv_id,
        "user_message_id": user_msg_id,
        "message": _msg(db.one("SELECT * FROM messages WHERE id = ?", [bot_id])),
        "error": result.get("error", ""),
    }


@app.get("/api/conversations")
def list_conversations(user=Depends(auth.current_user)):
    rows = db.query(
        "SELECT id, title, updated_at FROM conversations WHERE user_id = ? ORDER BY updated_at DESC, id DESC", [user["id"]]
    )
    return [dict(r) for r in rows]


@app.get("/api/conversations/{conv_id}")
def get_conversation(conv_id: int, user=Depends(auth.current_user)):
    conv = _own_conv(conv_id, user["id"])
    msgs = db.query("SELECT * FROM messages WHERE conv_id = ? ORDER BY id", [conv_id])
    return {"id": conv["id"], "title": conv["title"], "messages": [_msg(m) for m in msgs]}


class RenameIn(BaseModel):
    title: str = Field(min_length=1, max_length=100)


@app.patch("/api/conversations/{conv_id}")
def rename_conversation(conv_id: int, body: RenameIn, user=Depends(auth.current_user)):
    _own_conv(conv_id, user["id"])
    db.execute("UPDATE conversations SET title = ? WHERE id = ?", [body.title.strip(), conv_id])
    return {"ok": True}


@app.delete("/api/conversations/{conv_id}")
def delete_conversation(conv_id: int, user=Depends(auth.current_user)):
    _own_conv(conv_id, user["id"])
    db.execute("DELETE FROM conversations WHERE id = ?", [conv_id])
    return {"ok": True}


class FeedbackIn(BaseModel):
    value: int = Field(ge=-1, le=1)
    reason: str = Field(default="", max_length=100)


@app.post("/api/messages/{msg_id}/feedback")
def feedback(msg_id: int, body: FeedbackIn, user=Depends(auth.current_user)):
    row = db.one(
        "SELECT m.id FROM messages m JOIN conversations c ON c.id = m.conv_id "
        "WHERE m.id = ? AND c.user_id = ? AND m.role = 'assistant'",
        [msg_id, user["id"]],
    )
    if not row:
        raise HTTPException(404, "Không tìm thấy câu trả lời.")
    db.execute("UPDATE messages SET feedback = ?, feedback_reason = ? WHERE id = ?",
               [body.value, body.reason.strip() if body.value == -1 else "", msg_id])
    return {"ok": True}


# ---------------------------------------------------------------- documents (cần đăng nhập)
@app.get("/api/documents")
def list_documents(q: str = "", _=Depends(auth.current_user)):
    sql = "SELECT * FROM documents WHERE proc_status = 'done'"
    params: list = []
    q = q.strip()
    if q:
        esc = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        like = f"%{esc}%"
        sql += (" AND (title LIKE ? ESCAPE '\\' OR number LIKE ? ESCAPE '\\' OR issuer LIKE ? ESCAPE '\\' "
                "OR EXISTS (SELECT 1 FROM chunks c WHERE c.doc_id = documents.id AND c.text LIKE ? ESCAPE '\\'))")
        params += [like, like, like, like]
    sql += " ORDER BY COALESCE(NULLIF(issued_date,''), created_at) DESC, id DESC"
    return [doc_row(r) for r in db.query(sql, params)]


@app.get("/api/documents/{doc_id}")
def get_document(doc_id: int, _=Depends(auth.current_user)):
    r = db.one("SELECT * FROM documents WHERE id = ?", [doc_id])
    if not r:
        raise HTTPException(404, "Không tìm thấy tài liệu.")
    chunks = db.query(
        "SELECT id, ord, chapter, article, article_title, page, text FROM chunks WHERE doc_id = ? ORDER BY ord", [doc_id]
    )
    d = doc_row(r)
    d["chunks"] = [dict(c) for c in chunks]
    d["file_url"] = f"/api/files/{doc_id}"
    return d


@app.get("/api/files/{doc_id}")
def get_file(doc_id: int, _=Depends(auth.current_user)):
    r = db.one("SELECT filename, stored_name, ext FROM documents WHERE id = ?", [doc_id])
    path = config.UPLOAD_DIR / r["stored_name"] if r else None
    if not r or not path.exists():
        raise HTTPException(404, "Không còn file gốc của tài liệu này.")
    media = {".pdf": "application/pdf", ".txt": "text/plain; charset=utf-8", ".md": "text/plain; charset=utf-8"}.get(
        r["ext"], "application/octet-stream"
    )
    resp = FileResponse(path, media_type=media)
    disp = "inline" if r["ext"] in (".pdf", ".txt", ".md") else "attachment"
    from urllib.parse import quote

    resp.headers["Content-Disposition"] = f"{disp}; filename*=UTF-8''{quote(r['filename'])}"
    return resp


# ---------------------------------------------------------------- admin
@app.get("/api/admin/check", dependencies=[Depends(auth.require_data_manager)])
def admin_check():
    return {"ok": True}


@app.get("/api/admin/documents", dependencies=[Depends(auth.require_data_manager)])
def admin_list_documents():
    return [doc_row(r) for r in db.query("SELECT * FROM documents ORDER BY id DESC")]


@app.post("/api/admin/documents/detect", dependencies=[Depends(auth.require_data_manager)])
async def detect_metadata(file: UploadFile = File(...)):
    """Đọc nhanh file và gợi ý thông tin văn bản để điền sẵn vào biểu mẫu (không lưu gì)."""
    import tempfile

    from starlette.concurrency import run_in_threadpool

    from .rag import extract, metadata

    ext = Path(file.filename or "").suffix.lower()
    if ext not in config.ALLOWED_EXT:
        raise HTTPException(422, f"Chỉ nhận file {', '.join(sorted(config.ALLOWED_EXT))}.")
    data = await file.read()
    if not data or len(data) > config.MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(422, "File rỗng hoặc quá lớn.")

    def work() -> dict:
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d) / f"f{ext}"
            tmp.write_bytes(data)
            try:
                pages, _note = extract.extract_pages(tmp, ext)
            except extract.ExtractError:
                return {}
            return metadata.detect(pages[:3] + pages[3:][-2:])    # đầu văn bản (số hiệu, ngày) và cuối (hiệu lực)

    return {"fields": await run_in_threadpool(work)}


@app.post("/api/admin/documents", dependencies=[Depends(auth.require_data_manager)])
async def upload_document(
    background: BackgroundTasks,
    file: UploadFile = File(...),
    title: str = Form(""),
    doc_type: str = Form(...),
    number: str = Form(""),
    issuer: str = Form(""),
    issued_date: str = Form(""),
    effective_date: str = Form(""),
    validity: str = Form("chua_xac_minh"),
    notes: str = Form(""),
    replaced_by: str = Form(""),
):
    ext = Path(file.filename or "").suffix.lower()
    if ext not in config.ALLOWED_EXT:
        raise HTTPException(422, f"Chỉ nhận file {', '.join(sorted(config.ALLOWED_EXT))}.")
    if doc_type not in DOC_TYPES:
        raise HTTPException(422, "Loại văn bản không hợp lệ.")
    if validity not in VALIDITY:
        raise HTTPException(422, "Tình trạng hiệu lực không hợp lệ.")
    issued_date = valid_date(issued_date, "Ngày ban hành")
    effective_date = valid_date(effective_date, "Ngày hiệu lực")

    data = await file.read()
    if not data:
        raise HTTPException(422, "File rỗng.")
    if len(data) > config.MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(413, f"File vượt quá {config.MAX_UPLOAD_MB} MB.")

    stored = f"{uuid.uuid4().hex}{ext}"
    (config.UPLOAD_DIR / stored).write_bytes(data)
    title = title.strip() or Path(file.filename).stem
    doc_id = db.execute(
        "INSERT INTO documents (title, doc_type, number, issuer, issued_date, effective_date, validity, notes, "
        "replaced_by, filename, stored_name, ext) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        [title, doc_type, number.strip(), issuer.strip(), issued_date, effective_date, validity, notes.strip(),
         replaced_by.strip(), file.filename, stored, ext],
    )
    background.add_task(process_document, doc_id)
    return doc_row(db.one("SELECT * FROM documents WHERE id = ?", [doc_id]))


class DocPatch(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    doc_type: str
    number: str = ""
    issuer: str = ""
    issued_date: str = ""
    effective_date: str = ""
    validity: str = "chua_xac_minh"
    notes: str = ""
    replaced_by: str = ""


@app.patch("/api/admin/documents/{doc_id}", dependencies=[Depends(auth.require_data_manager)])
def update_document(doc_id: int, body: DocPatch, background: BackgroundTasks):
    old = db.one("SELECT * FROM documents WHERE id = ?", [doc_id])
    if not old:
        raise HTTPException(404, "Không tìm thấy tài liệu.")
    if body.doc_type not in DOC_TYPES or body.validity not in VALIDITY:
        raise HTTPException(422, "Loại văn bản hoặc hiệu lực không hợp lệ.")
    issued = valid_date(body.issued_date, "Ngày ban hành")
    eff = valid_date(body.effective_date, "Ngày hiệu lực")
    db.execute(
        "UPDATE documents SET title=?, doc_type=?, number=?, issuer=?, issued_date=?, effective_date=?, validity=?, "
        "notes=?, replaced_by=?, updated_at=datetime('now') WHERE id=?",
        [body.title.strip(), body.doc_type, body.number.strip(), body.issuer.strip(), issued, eff, body.validity,
         body.notes.strip(), body.replaced_by.strip(), doc_id],
    )
    # Tên văn bản nằm trong chuỗi lập chỉ mục, nên đổi tên thì phải lập lại chỉ mục.
    if old["title"] != body.title.strip() and old["proc_status"] == "done":
        db.execute("UPDATE documents SET proc_status='pending', error='', failed_stage='' WHERE id = ?", [doc_id])
        background.add_task(process_document, doc_id)
    else:
        index.reload()
    return doc_row(db.one("SELECT * FROM documents WHERE id = ?", [doc_id]))


@app.post("/api/admin/documents/{doc_id}/replace", dependencies=[Depends(auth.require_data_manager)])
async def replace_document_file(doc_id: int, background: BackgroundTasks, file: UploadFile = File(...)):
    """Thay file của một tài liệu, giữ nguyên metadata, rồi lập chỉ mục lại."""
    old = db.one("SELECT * FROM documents WHERE id = ?", [doc_id])
    if not old:
        raise HTTPException(404, "Không tìm thấy tài liệu.")
    if old["proc_status"] not in ("failed", "done"):
        raise HTTPException(409, "Tài liệu đang được xử lý.")
    ext = Path(file.filename or "").suffix.lower()
    if ext not in config.ALLOWED_EXT:
        raise HTTPException(422, f"Chỉ nhận file {', '.join(sorted(config.ALLOWED_EXT))}.")
    data = await file.read()
    if not data:
        raise HTTPException(422, "File rỗng.")
    if len(data) > config.MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(413, f"File vượt quá {config.MAX_UPLOAD_MB} MB.")
    stored = f"{uuid.uuid4().hex}{ext}"
    (config.UPLOAD_DIR / stored).write_bytes(data)
    db.execute(
        "UPDATE documents SET filename=?, stored_name=?, ext=?, proc_status='pending', error='', pages=0, "
        "n_chunks=0, updated_at=datetime('now') WHERE id=?",
        [file.filename, stored, ext, doc_id],
    )
    try:
        (config.UPLOAD_DIR / old["stored_name"]).unlink(missing_ok=True)
    except OSError:
        log.warning("Không xóa được file cũ %s", old["stored_name"])
    index.reload()  # tài liệu tạm thời rời khỏi chỉ mục cho đến khi xử lý xong
    background.add_task(process_document, doc_id)
    return doc_row(db.one("SELECT * FROM documents WHERE id = ?", [doc_id]))


@app.post("/api/admin/documents/{doc_id}/retry", dependencies=[Depends(auth.require_data_manager)])
def retry_document(doc_id: int, background: BackgroundTasks):
    r = db.one("SELECT * FROM documents WHERE id = ?", [doc_id])
    if not r:
        raise HTTPException(404, "Không tìm thấy tài liệu.")
    if r["proc_status"] not in ("failed", "done"):
        raise HTTPException(409, "Tài liệu đang được xử lý.")
    db.execute("UPDATE documents SET proc_status='pending', error='', failed_stage='' WHERE id = ?", [doc_id])
    background.add_task(process_document, doc_id)
    return doc_row(db.one("SELECT * FROM documents WHERE id = ?", [doc_id]))


@app.delete("/api/admin/documents/{doc_id}", dependencies=[Depends(auth.require_data_manager)])
def delete_document(doc_id: int):
    r = db.one("SELECT stored_name FROM documents WHERE id = ?", [doc_id])
    if not r:
        raise HTTPException(404, "Không tìm thấy tài liệu.")
    db.execute("DELETE FROM documents WHERE id = ?", [doc_id])
    purge_vectors(doc_id)
    try:
        (config.UPLOAD_DIR / r["stored_name"]).unlink(missing_ok=True)
    except OSError:
        log.warning("Không xóa được file %s", r["stored_name"])
    index.reload()
    return {"ok": True}
