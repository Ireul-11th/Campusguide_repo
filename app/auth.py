"""Tài khoản, băm mật khẩu, phiên đăng nhập và phân quyền. Chỉ dùng thư viện chuẩn của Python."""
import hashlib
import hmac
import re
import secrets
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

from fastapi import Depends, HTTPException, Request, Response

from . import config, db

COOKIE = "cg_session"
ITERATIONS = 600_000           # PBKDF2-HMAC-SHA256, mức khuyến nghị của OWASP
USERNAME_RE = re.compile(r"[a-z0-9_.]{3,32}")
MIN_PASSWORD, MAX_PASSWORD = 8, 128


# ---------------------------------------------------------------- mật khẩu
def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS)
    return f"pbkdf2_sha256${ITERATIONS}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iters, salt, digest = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(iters))
        return hmac.compare_digest(dk.hex(), digest)
    except (ValueError, TypeError):
        return False


_DUMMY = hash_password("không-ai-dùng-mật-khẩu-này")   # để tên đăng nhập sai cũng tốn thời gian như đúng


def check_password_rules(password: str) -> None:
    if not (MIN_PASSWORD <= len(password) <= MAX_PASSWORD):
        raise HTTPException(422, f"Mật khẩu phải dài từ {MIN_PASSWORD} đến {MAX_PASSWORD} ký tự.")
    if password.isdigit() or password.isalpha():
        raise HTTPException(422, "Mật khẩu cần có cả chữ và số (hoặc ký tự đặc biệt).")


def normalize_username(username: str) -> str:
    u = (username or "").strip().lower()
    if not USERNAME_RE.fullmatch(u):
        raise HTTPException(422, "Tên đăng nhập gồm 3–32 ký tự: chữ thường không dấu, số, dấu chấm hoặc gạch dưới.")
    return u


# ---------------------------------------------------------------- chống dò mật khẩu
_FAILS: dict[str, list[float]] = {}
MAX_FAILS, WINDOW = 5, 300


def _key(username: str, ip: str) -> str:
    return f"{username}|{ip}"


def throttled(username: str, ip: str) -> int:
    """Trả số giây phải chờ nếu đăng nhập sai quá nhiều lần, 0 nếu được phép thử."""
    now = time.time()
    hits = [t for t in _FAILS.get(_key(username, ip), []) if now - t < WINDOW]
    _FAILS[_key(username, ip)] = hits
    return int(WINDOW - (now - hits[0])) + 1 if len(hits) >= MAX_FAILS else 0


def record_fail(username: str, ip: str) -> None:
    _FAILS.setdefault(_key(username, ip), []).append(time.time())


def clear_fails(username: str, ip: str) -> None:
    _FAILS.pop(_key(username, ip), None)


# ---------------------------------------------------------------- phiên đăng nhập
def _th(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def create_session(user_id: int, response: Response) -> None:
    token = secrets.token_urlsafe(32)
    exp = datetime.now(timezone.utc) + timedelta(days=config.SESSION_DAYS)
    db.execute("DELETE FROM sessions WHERE expires_at < datetime('now')")
    db.execute("INSERT INTO sessions (token_hash, user_id, expires_at) VALUES (?, ?, ?)", [_th(token), user_id, _iso(exp)])
    db.execute("UPDATE users SET last_login = datetime('now') WHERE id = ?", [user_id])
    response.set_cookie(COOKIE, token, max_age=config.SESSION_DAYS * 86400, httponly=True,
                        samesite="lax", secure=config.COOKIE_SECURE, path="/")


def destroy_session(request: Request, response: Response) -> None:
    token = request.cookies.get(COOKIE)
    if token:
        db.execute("DELETE FROM sessions WHERE token_hash = ?", [_th(token)])
    response.delete_cookie(COOKIE, path="/")


def revoke_user_sessions(user_id: int, except_token: str | None = None) -> None:
    if except_token:
        db.execute("DELETE FROM sessions WHERE user_id = ? AND token_hash != ?", [user_id, _th(except_token)])
    else:
        db.execute("DELETE FROM sessions WHERE user_id = ?", [user_id])


def user_from_request(request: Request):
    token = request.cookies.get(COOKIE)
    if not token:
        return None
    return db.one(
        "SELECT u.* FROM sessions s JOIN users u ON u.id = s.user_id "
        "WHERE s.token_hash = ? AND s.expires_at > datetime('now') AND u.is_active = 1",
        [_th(token)],
    )


def public_user(u) -> dict:
    is_admin = u["role"] == "admin"
    return {
        "id": u["id"], "username": u["username"], "full_name": u["full_name"] or u["username"],
        "role": u["role"], "is_admin": is_admin,
        "can_manage_data": is_admin or bool(u["can_manage_data"]),
    }


# ---------------------------------------------------------------- phụ thuộc cho API
def _csrf(request: Request) -> None:
    # Cookie SameSite=Lax đã chặn phần lớn CSRF; thêm header tự đặt vì trang web khác không gửi được kèm cookie.
    if request.method not in ("GET", "HEAD", "OPTIONS") and request.headers.get("x-requested-with") != "cg":
        raise HTTPException(403, "Yêu cầu không hợp lệ.")


def current_user(request: Request):
    _csrf(request)
    u = user_from_request(request)
    if not u:
        raise HTTPException(401, "Bạn cần đăng nhập.")
    return u


def require_data_manager(u=Depends(current_user)):
    if u["role"] != "admin" and not u["can_manage_data"]:
        raise HTTPException(403, "Bạn chưa được cấp quyền quản trị dữ liệu.")
    return u


def require_admin(u=Depends(current_user)):
    if u["role"] != "admin":
        raise HTTPException(403, "Chỉ quản trị viên mới dùng được chức năng này.")
    return u


def login_redirect_url(request: Request) -> str:
    path = request.url.path + (("?" + request.url.query) if request.url.query else "")
    return "/login" if path == "/" else f"/login?next={quote(path, safe='')}"


# ---------------------------------------------------------------- quản trị viên đầu tiên
def bootstrap_admin() -> None:
    admins = db.one("SELECT COUNT(*) AS n FROM users WHERE role = 'admin'")["n"]
    if admins and not config.ADMIN_FORCE_RESET:
        return
    if config.ADMIN_FORCE_RESET and config.ADMIN_PASSWORD:
        existing = db.one("SELECT id FROM users WHERE username = ?", [config.ADMIN_USERNAME])
        h = hash_password(config.ADMIN_PASSWORD)
        if existing:
            db.execute("UPDATE users SET password_hash=?, role='admin', is_active=1 WHERE id=?", [h, existing["id"]])
            revoke_user_sessions(existing["id"])
        else:
            db.execute("INSERT INTO users (username, full_name, password_hash, role, can_manage_data) VALUES (?,?,?,'admin',1)",
                       [config.ADMIN_USERNAME, "Quản trị viên", h])
        print(f"[CampusGuide] Đã đặt lại mật khẩu quản trị viên '{config.ADMIN_USERNAME}'. Hãy xóa ADMIN_FORCE_RESET khỏi .env.")
        return
    password = config.ADMIN_PASSWORD
    generated = not password
    if generated:
        password = secrets.token_urlsafe(9)
    db.execute("INSERT INTO users (username, full_name, password_hash, role, can_manage_data) VALUES (?,?,?,'admin',1)",
               [config.ADMIN_USERNAME, "Quản trị viên", hash_password(password)])
    if generated:
        print("=" * 62)
        print(f"[CampusGuide] Đã tạo tài khoản quản trị viên đầu tiên:\n  Tên đăng nhập: {config.ADMIN_USERNAME}\n  Mật khẩu     : {password}")
        print("  (Chỉ hiện một lần. Muốn tự chọn, đặt ADMIN_PASSWORD trong .env trước khi chạy lần đầu.)")
        print("=" * 62)
    else:
        print(f"[CampusGuide] Đã tạo tài khoản quản trị viên '{config.ADMIN_USERNAME}' từ file .env.")
