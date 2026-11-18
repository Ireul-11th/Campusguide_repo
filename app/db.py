import sqlite3
from contextlib import closing
from typing import Any, Iterable

from .config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  doc_type TEXT NOT NULL DEFAULT 'khac',
  number TEXT DEFAULT '',
  issuer TEXT DEFAULT '',
  issued_date TEXT DEFAULT '',
  effective_date TEXT DEFAULT '',
  validity TEXT NOT NULL DEFAULT 'chua_xac_minh',
  notes TEXT DEFAULT '',
  replaced_by TEXT DEFAULT '',
  failed_stage TEXT DEFAULT '',
  filename TEXT NOT NULL,
  stored_name TEXT NOT NULL,
  ext TEXT NOT NULL,
  proc_status TEXT NOT NULL DEFAULT 'pending',
  error TEXT DEFAULT '',
  pages INTEGER DEFAULT 0,
  n_chunks INTEGER DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS chunks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  doc_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  ord INTEGER NOT NULL,
  chapter TEXT DEFAULT '',
  article TEXT DEFAULT '',
  article_title TEXT DEFAULT '',
  page INTEGER DEFAULT 0,
  text TEXT NOT NULL,
  embedding BLOB
);
CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks(doc_id);
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT NOT NULL UNIQUE COLLATE NOCASE,
  full_name TEXT NOT NULL DEFAULT '',
  password_hash TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'user',
  can_manage_data INTEGER NOT NULL DEFAULT 0,
  is_active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  last_login TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS sessions (
  token_hash TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  expires_at TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_sess_user ON sessions(user_id);
CREATE TABLE IF NOT EXISTS conversations (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  title TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_conv_user ON conversations(user_id);
CREATE TABLE IF NOT EXISTS messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  conv_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  role TEXT NOT NULL,
  content TEXT NOT NULL,
  status TEXT DEFAULT '',
  sources TEXT DEFAULT '[]',
  warnings TEXT DEFAULT '[]',
  feedback INTEGER DEFAULT 0,
  feedback_reason TEXT DEFAULT '',
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_msg_conv ON messages(conv_id);
"""


def connect() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    return c


def init_db() -> None:
    with closing(connect()) as c, c:
        # Bản cũ lưu lịch sử theo trình duyệt (client_id). Nay lịch sử gắn với tài khoản nên bỏ bảng cũ.
        ccols = {r["name"] for r in c.execute("PRAGMA table_info(conversations)")}
        if ccols and "user_id" not in ccols:
            c.execute("DROP TABLE IF EXISTS messages")
            c.execute("DROP TABLE conversations")
        c.executescript(SCHEMA)
        cols = {r["name"] for r in c.execute("PRAGMA table_info(documents)")}
        if "replaced_by" not in cols:  # nâng cấp CSDL cũ
            c.execute("ALTER TABLE documents ADD COLUMN replaced_by TEXT DEFAULT ''")
        if "failed_stage" not in cols:
            c.execute("ALTER TABLE documents ADD COLUMN failed_stage TEXT DEFAULT ''")
        mcols = {r["name"] for r in c.execute("PRAGMA table_info(messages)")}
        if "feedback_reason" not in mcols:
            c.execute("ALTER TABLE messages ADD COLUMN feedback_reason TEXT DEFAULT ''")


def query(sql: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
    with closing(connect()) as c:
        return c.execute(sql, tuple(params)).fetchall()


def one(sql: str, params: Iterable[Any] = ()):
    rows = query(sql, params)
    return rows[0] if rows else None


def execute(sql: str, params: Iterable[Any] = ()) -> int:
    with closing(connect()) as c, c:
        cur = c.execute(sql, tuple(params))
        return cur.lastrowid


def executemany(sql: str, seq: Iterable[Iterable[Any]]) -> None:
    with closing(connect()) as c, c:
        c.executemany(sql, [tuple(s) for s in seq])
