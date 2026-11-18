"""API đăng nhập, đăng ký, đổi mật khẩu và quản lý tài khoản (chỉ quản trị viên)."""
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from . import auth, db

router = APIRouter()
ROLES = ("user", "admin")


def _ip(request: Request) -> str:
    return request.client.host if request.client else "?"


def _full_name(v: str, username: str) -> str:
    return (v or "").strip()[:80] or username


# ---------------------------------------------------------------- đăng nhập / đăng ký
class LoginIn(BaseModel):
    username: str = Field(max_length=64)
    password: str = Field(max_length=auth.MAX_PASSWORD)


@router.post("/api/auth/login")
def login(body: LoginIn, request: Request, response: Response):
    auth._csrf(request)
    username, ip = body.username.strip().lower(), _ip(request)
    wait = auth.throttled(username, ip)
    if wait:
        raise HTTPException(429, f"Đăng nhập sai quá nhiều lần. Thử lại sau {wait // 60 + 1} phút.")
    u = db.one("SELECT * FROM users WHERE username = ?", [username])
    ok = auth.verify_password(body.password, u["password_hash"] if u else auth._DUMMY)
    if not (u and ok):
        auth.record_fail(username, ip)
        raise HTTPException(401, "Sai tên đăng nhập hoặc mật khẩu.")
    if not u["is_active"]:
        raise HTTPException(403, "Tài khoản đã bị khóa. Hãy liên hệ quản trị viên.")
    auth.clear_fails(username, ip)
    auth.create_session(u["id"], response)
    return auth.public_user(u)


class RegisterIn(BaseModel):
    username: str = Field(max_length=64)
    full_name: str = Field(default="", max_length=80)
    password: str = Field(max_length=auth.MAX_PASSWORD)


@router.post("/api/auth/register")
def register(body: RegisterIn, request: Request, response: Response):
    auth._csrf(request)
    username = auth.normalize_username(body.username)
    auth.check_password_rules(body.password)
    if username in body.password.lower():
        raise HTTPException(422, "Mật khẩu không được chứa tên đăng nhập.")
    try:
        uid = db.execute(
            "INSERT INTO users (username, full_name, password_hash, role, can_manage_data) VALUES (?,?,?, 'user', 0)",
            [username, _full_name(body.full_name, username), auth.hash_password(body.password)],
        )
    except sqlite3.IntegrityError:
        raise HTTPException(409, "Tên đăng nhập đã có người dùng.")
    auth.create_session(uid, response)
    return auth.public_user(db.one("SELECT * FROM users WHERE id = ?", [uid]))


@router.post("/api/auth/logout")
def logout(request: Request, response: Response):
    auth._csrf(request)
    auth.destroy_session(request, response)
    return {"ok": True}


@router.get("/api/auth/me")
def me(u=Depends(auth.current_user)):
    return auth.public_user(u)


class PasswordIn(BaseModel):
    current: str = Field(max_length=auth.MAX_PASSWORD)
    new: str = Field(max_length=auth.MAX_PASSWORD)


@router.post("/api/auth/password")
def change_password(body: PasswordIn, request: Request, u=Depends(auth.current_user)):
    if not auth.verify_password(body.current, u["password_hash"]):
        raise HTTPException(403, "Mật khẩu hiện tại không đúng.")
    auth.check_password_rules(body.new)
    if body.new == body.current:
        raise HTTPException(422, "Mật khẩu mới phải khác mật khẩu cũ.")
    db.execute("UPDATE users SET password_hash = ? WHERE id = ?", [auth.hash_password(body.new), u["id"]])
    auth.revoke_user_sessions(u["id"], except_token=request.cookies.get(auth.COOKIE))   # đăng xuất các máy khác
    return {"ok": True}


# ---------------------------------------------------------------- quản lý tài khoản (admin)
def _row(r) -> dict:
    return {
        "id": r["id"], "username": r["username"], "full_name": r["full_name"], "role": r["role"],
        "can_manage_data": bool(r["can_manage_data"]) or r["role"] == "admin",
        "is_active": bool(r["is_active"]), "created_at": r["created_at"], "last_login": r["last_login"] or "",
        "n_conversations": r["n_conv"] if "n_conv" in r.keys() else 0,
    }


def _active_admins() -> int:
    return db.one("SELECT COUNT(*) AS n FROM users WHERE role = 'admin' AND is_active = 1")["n"]


def _get(uid: int):
    r = db.one("SELECT * FROM users WHERE id = ?", [uid])
    if not r:
        raise HTTPException(404, "Không tìm thấy tài khoản.")
    return r


@router.get("/api/admin/users")
def list_users(q: str = "", _=Depends(auth.require_admin)):
    sql = ("SELECT u.*, (SELECT COUNT(*) FROM conversations c WHERE c.user_id = u.id) AS n_conv FROM users u")
    params: list = []
    q = q.strip().lower()
    if q:
        esc = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        sql += " WHERE lower(u.username) LIKE ? ESCAPE '\\' OR lower(u.full_name) LIKE ? ESCAPE '\\'"
        params = [f"%{esc}%"] * 2
    sql += " ORDER BY (u.role = 'admin') DESC, u.username"
    return [_row(r) for r in db.query(sql, params)]


class UserIn(BaseModel):
    username: str = Field(max_length=64)
    full_name: str = Field(default="", max_length=80)
    password: str = Field(max_length=auth.MAX_PASSWORD)
    role: str = "user"
    can_manage_data: bool = False
    is_active: bool = True


@router.post("/api/admin/users")
def create_user(body: UserIn, _=Depends(auth.require_admin)):
    username = auth.normalize_username(body.username)
    auth.check_password_rules(body.password)
    if body.role not in ROLES:
        raise HTTPException(422, "Vai trò không hợp lệ.")
    try:
        uid = db.execute(
            "INSERT INTO users (username, full_name, password_hash, role, can_manage_data, is_active) VALUES (?,?,?,?,?,?)",
            [username, _full_name(body.full_name, username), auth.hash_password(body.password), body.role,
             int(body.can_manage_data or body.role == "admin"), int(body.is_active)],
        )
    except sqlite3.IntegrityError:
        raise HTTPException(409, "Tên đăng nhập đã có người dùng.")
    return _row(_get(uid))


class UserPatch(BaseModel):
    full_name: str | None = Field(default=None, max_length=80)
    role: str | None = None
    can_manage_data: bool | None = None
    is_active: bool | None = None
    password: str | None = Field(default=None, max_length=auth.MAX_PASSWORD)


@router.patch("/api/admin/users/{uid}")
def update_user(uid: int, body: UserPatch, me=Depends(auth.require_admin)):
    u = _get(uid)
    role = body.role if body.role is not None else u["role"]
    active = body.is_active if body.is_active is not None else bool(u["is_active"])
    if role not in ROLES:
        raise HTTPException(422, "Vai trò không hợp lệ.")
    if uid == me["id"] and (role != "admin" or not active):
        raise HTTPException(409, "Bạn không thể tự hạ quyền hoặc tự khóa tài khoản của mình.")
    if u["role"] == "admin" and u["is_active"] and (role != "admin" or not active) and _active_admins() <= 1:
        raise HTTPException(409, "Phải còn ít nhất một quản trị viên đang hoạt động.")
    cmd = body.can_manage_data if body.can_manage_data is not None else bool(u["can_manage_data"])
    name = _full_name(body.full_name, u["username"]) if body.full_name is not None else u["full_name"]
    db.execute("UPDATE users SET full_name=?, role=?, can_manage_data=?, is_active=? WHERE id=?",
               [name, role, int(cmd or role == "admin"), int(active), uid])
    if body.password:
        auth.check_password_rules(body.password)
        db.execute("UPDATE users SET password_hash = ? WHERE id = ?", [auth.hash_password(body.password), uid])
        auth.revoke_user_sessions(uid)
    elif not active:
        auth.revoke_user_sessions(uid)
    return _row(_get(uid))


@router.delete("/api/admin/users/{uid}")
def delete_user(uid: int, me=Depends(auth.require_admin)):
    u = _get(uid)
    if uid == me["id"]:
        raise HTTPException(409, "Bạn không thể tự xóa tài khoản của mình.")
    if u["role"] == "admin" and u["is_active"] and _active_admins() <= 1:
        raise HTTPException(409, "Phải còn ít nhất một quản trị viên đang hoạt động.")
    db.execute("DELETE FROM users WHERE id = ?", [uid])    # lịch sử hỏi đáp và phiên tự xóa theo (ON DELETE CASCADE)
    return {"ok": True}
