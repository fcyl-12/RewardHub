from __future__ import annotations

import hashlib
import os
import re
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from functools import wraps
from pathlib import Path
from typing import Any, Iterator

from flask import Flask, jsonify, render_template, request, session


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("DATA_DIR", str(BASE_DIR / "data")))
DATABASE_PATH = Path(os.getenv("DATABASE_PATH", str(DATA_DIR / "points.db")))
SECRET_KEY = os.getenv("SECRET_KEY", "change-this-secret-key-in-production")
PASSWORD_ITERATIONS = 240_000
APP_VERSION = "0.6.3"
AVATAR_OPTIONS = {"boy", "girl", "adult-male", "adult-female"}
CHILD_AVATARS = {"boy", "girl"}
PROJECT_ICONS = {
    "television.svg", "book.svg", "homework.svg", "chore.svg", "sport.svg",
    "bedtime.svg", "snack.svg", "game.svg", "outing.svg", "points.svg",
    "gift.svg", "warning.svg",
}
ITEM_DEFAULT_ICONS = {"earn": "points.svg", "deduct": "warning.svg", "reward": "gift.svg"}

DEFAULT_EARN_ITEMS = [
    ("完成作业", 10, "homework.svg"),
    ("阅读30分钟", 5, "book.svg"),
    ("做家务", 15, "chore.svg"),
    ("锻炼身体", 8, "sport.svg"),
    ("早睡早起", 5, "bedtime.svg"),
]
DEFAULT_DEDUCT_ITEMS = [
    ("未完成作业", 10, "warning.svg"),
    ("迟到", 5, "warning.svg"),
    ("说脏话", 8, "warning.svg"),
    ("不整理房间", 5, "chore.svg"),
]
DEFAULT_REWARDS = [
    ("看电视30分钟", 50, "television.svg"),
    ("玩游戏1小时", 100, "game.svg"),
    ("买零食", 30, "snack.svg"),
    ("周末外出", 200, "outing.svg"),
]
ITEM_TABLES = {"earn": "earn_items", "deduct": "deduct_items", "reward": "rewards"}
USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{3,32}$")

app = Flask(__name__)
app.config.update(
    SECRET_KEY=SECRET_KEY,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
)


@contextmanager
def connection() -> Iterator[sqlite3.Connection]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def password_hash(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("ascii"), PASSWORD_ITERATIONS
    )
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${salt}${digest.hex()}"


def password_matches(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt, expected = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt.encode("ascii"), int(iterations)
        ).hex()
        return secrets.compare_digest(actual, expected)
    except (TypeError, ValueError):
        return False


def table_has_column(conn: sqlite3.Connection, table: str, column: str) -> bool:
    return any(row["name"] == column for row in conn.execute(f"PRAGMA table_info({table})").fetchall())


def migrate_point_requests(conn: sqlite3.Connection) -> None:
    schema = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'point_requests'"
    ).fetchone()
    if schema is None or "exchange" in (schema["sql"] or ""):
        return
    conn.execute("ALTER TABLE point_requests RENAME TO point_requests_legacy")
    conn.execute(
        """
        CREATE TABLE point_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            requester_id INTEGER NOT NULL,
            kind TEXT NOT NULL CHECK (kind IN ('earn', 'deduct', 'exchange', 'manual')),
            title TEXT NOT NULL,
            amount INTEGER NOT NULL,
            type TEXT NOT NULL CHECK (type IN ('income', 'expense')),
            date TEXT NOT NULL,
            time TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
            created_at TEXT NOT NULL,
            reviewed_at TEXT,
            reviewer_id INTEGER,
            reject_reason TEXT
        )
        """
    )
    conn.execute(
        """
        INSERT INTO point_requests(
            id, account_id, requester_id, kind, title, amount, type, date, time,
            status, created_at, reviewed_at, reviewer_id, reject_reason
        )
        SELECT id, account_id, requester_id, kind, title, amount, type, date, time,
               status, created_at, reviewed_at, reviewer_id, reject_reason
        FROM point_requests_legacy
        """
    )
    conn.execute("DROP TABLE point_requests_legacy")


def seed_items_for_child(conn: sqlite3.Connection, account_id: int) -> None:
    defaults = (
        ("earn_items", DEFAULT_EARN_ITEMS),
        ("deduct_items", DEFAULT_DEDUCT_ITEMS),
        ("rewards", DEFAULT_REWARDS),
    )
    for table, items in defaults:
        if conn.execute(f"SELECT COUNT(*) FROM {table} WHERE account_id = ?", (account_id,)).fetchone()[0] == 0:
            conn.executemany(
                f"INSERT INTO {table}(account_id, name, points, icon) VALUES (?, ?, ?, ?)",
                [(account_id, name, points, icon) for name, points, icon in items],
            )


def remove_legacy_default_child(conn: sqlite3.Connection) -> None:
    """Remove the untouched child created by versions before 0.6.2."""
    child = conn.execute(
        "SELECT id FROM accounts WHERE username = 'child' AND role = 'child' AND display_name = '小朋友'"
    ).fetchone()
    if child is None:
        return
    child_id = int(child["id"])
    activity = conn.execute(
        """
        SELECT EXISTS(
            SELECT 1 FROM records WHERE account_id = ?
            UNION ALL SELECT 1 FROM point_requests WHERE account_id = ?
            UNION ALL SELECT 1 FROM account_logs WHERE target_id = ? OR actor_id = ?
        )
        """,
        (child_id, child_id, child_id, child_id),
    ).fetchone()[0]
    if activity:
        return
    for table in ("earn_items", "deduct_items", "rewards", "records", "point_requests"):
        conn.execute(f"DELETE FROM {table} WHERE account_id = ?", (child_id,))
    conn.execute("DELETE FROM accounts WHERE id = ?", (child_id,))


def init_db() -> None:
    with connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                display_name TEXT NOT NULL,
                role TEXT NOT NULL CHECK (role IN ('admin', 'child')),
                avatar TEXT NOT NULL DEFAULT 'boy',
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS earn_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                points INTEGER NOT NULL CHECK (points > 0),
                icon TEXT NOT NULL DEFAULT 'points.svg'
            );
            CREATE TABLE IF NOT EXISTS deduct_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                points INTEGER NOT NULL CHECK (points > 0),
                icon TEXT NOT NULL DEFAULT 'warning.svg'
            );
            CREATE TABLE IF NOT EXISTS rewards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                points INTEGER NOT NULL CHECK (points > 0),
                icon TEXT NOT NULL DEFAULT 'gift.svg'
            );
            CREATE TABLE IF NOT EXISTS records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                amount INTEGER NOT NULL,
                type TEXT NOT NULL CHECK (type IN ('income', 'expense')),
                date TEXT NOT NULL,
                time TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS point_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER NOT NULL,
                requester_id INTEGER NOT NULL,
                kind TEXT NOT NULL CHECK (kind IN ('earn', 'deduct', 'exchange', 'manual')),
                title TEXT NOT NULL,
                amount INTEGER NOT NULL,
                type TEXT NOT NULL CHECK (type IN ('income', 'expense')),
                date TEXT NOT NULL,
                time TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
                created_at TEXT NOT NULL,
                reviewed_at TEXT,
                reviewer_id INTEGER,
                reject_reason TEXT
            );
            CREATE TABLE IF NOT EXISTS account_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                actor_id INTEGER,
                actor_username TEXT NOT NULL,
                actor_name TEXT NOT NULL,
                actor_avatar TEXT NOT NULL DEFAULT 'adult-male',
                target_id INTEGER,
                target_username TEXT NOT NULL,
                target_name TEXT NOT NULL,
                target_role TEXT NOT NULL,
                target_avatar TEXT NOT NULL DEFAULT 'boy',
                action TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )
        migrate_point_requests(conn)
        if not table_has_column(conn, "accounts", "avatar"):
            conn.execute("ALTER TABLE accounts ADD COLUMN avatar TEXT NOT NULL DEFAULT 'boy'")
        for column, default in (("actor_avatar", "adult-male"), ("target_avatar", "boy")):
            if not table_has_column(conn, "account_logs", column):
                conn.execute(f"ALTER TABLE account_logs ADD COLUMN {column} TEXT NOT NULL DEFAULT '{default}'")
        for table in ("earn_items", "deduct_items", "rewards", "records", "point_requests"):
            if not table_has_column(conn, table, "account_id"):
                conn.execute(f"ALTER TABLE {table} ADD COLUMN account_id INTEGER")
        for table, default_icon in ITEM_DEFAULT_ICONS.items():
            if not table_has_column(conn, ITEM_TABLES[table], "icon"):
                conn.execute(
                    f"ALTER TABLE {ITEM_TABLES[table]} ADD COLUMN icon TEXT NOT NULL DEFAULT '{default_icon}'"
                )
            conn.execute(
                f"UPDATE {ITEM_TABLES[table]} SET icon = ? WHERE icon IS NULL OR TRIM(icon) = '' OR icon NOT IN ({','.join('?' for _ in PROJECT_ICONS)})",
                (default_icon, *PROJECT_ICONS),
            )

        now = datetime.now().astimezone().isoformat(timespec="seconds")
        admin = conn.execute("SELECT * FROM accounts WHERE username = 'admin'").fetchone()
        if admin is None:
            conn.execute(
                "INSERT INTO accounts(username, password_hash, display_name, role, avatar, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                ("admin", password_hash("admin123"), "管理员", "admin", "adult-male", now),
            )
        conn.execute("UPDATE accounts SET avatar = 'adult-male' WHERE username = 'admin' AND avatar = 'boy'")
        remove_legacy_default_child(conn)
        for row in conn.execute("SELECT id FROM accounts WHERE role = 'child' AND active = 1").fetchall():
            seed_items_for_child(conn, int(row["id"]))


def current_date() -> str:
    return datetime.now().astimezone().date().isoformat()


def current_time() -> str:
    return datetime.now().astimezone().strftime("%H:%M")


def valid_date(value: Any) -> str:
    if value in (None, ""):
        return current_date()
    try:
        return date.fromisoformat(str(value)).isoformat()
    except ValueError as exc:
        raise ValueError("日期格式必须为 YYYY-MM-DD") from exc


def positive_int(value: Any, label: str = "积分") -> int:
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label}必须是整数") from exc
    if number <= 0:
        raise ValueError(f"{label}必须大于 0")
    return number


def safe_account(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "id": row["id"],
        "username": row["username"],
        "display_name": row["display_name"],
        "role": row["role"],
        "avatar": row["avatar"] or ("adult-male" if row["role"] == "admin" else "boy"),
        "active": bool(row["active"]),
    }


def current_user(conn: sqlite3.Connection) -> sqlite3.Row | None:
    user_id = session.get("user_id")
    if not user_id:
        return None
    user = conn.execute("SELECT * FROM accounts WHERE id = ? AND active = 1", (user_id,)).fetchone()
    if user is None:
        session.clear()
    return user


def active_child_id(conn: sqlite3.Connection, user: sqlite3.Row) -> int | None:
    if user["role"] == "child":
        return int(user["id"])
    selected = session.get("selected_child_id")
    if selected:
        child = conn.execute(
            "SELECT id FROM accounts WHERE id = ? AND role = 'child' AND active = 1", (selected,)
        ).fetchone()
        if child:
            return int(child["id"])
    child = conn.execute("SELECT id FROM accounts WHERE role = 'child' AND active = 1 ORDER BY id LIMIT 1").fetchone()
    if child:
        session["selected_child_id"] = int(child["id"])
        return int(child["id"])
    return None


def require_user(handler):
    @wraps(handler)
    def wrapped(*args, **kwargs):
        with connection() as conn:
            user = current_user(conn)
            if user is None:
                return api_error("请先登录", 401)
        return handler(*args, **kwargs)

    return wrapped


def require_admin(handler):
    @wraps(handler)
    def wrapped(*args, **kwargs):
        with connection() as conn:
            user = current_user(conn)
            if user is None:
                return api_error("请先登录", 401)
            if user["role"] != "admin":
                return api_error("只有管理员可以执行此操作", 403)
        return handler(*args, **kwargs)

    return wrapped


def row_item(row: sqlite3.Row, kind: str) -> dict[str, Any]:
    points = int(row["points"])
    if kind == "deduct":
        points = -points
    return {"id": row["id"], "name": row["name"], "points": points, "icon": row["icon"] or ITEM_DEFAULT_ICONS[kind]}


def get_balance(conn: sqlite3.Connection, account_id: int) -> int:
    return int(
        conn.execute("SELECT COALESCE(SUM(amount), 0) FROM records WHERE account_id = ?", (account_id,)).fetchone()[0]
    )


def request_rows(conn: sqlite3.Connection, user: sqlite3.Row) -> list[dict[str, Any]]:
    if user["role"] == "admin":
        rows = conn.execute(
            """
            SELECT pr.*, a.display_name AS child_name, a.username AS child_username, a.avatar AS child_avatar
            FROM point_requests pr
            JOIN accounts a ON a.id = pr.account_id
            ORDER BY CASE pr.status WHEN 'pending' THEN 0 ELSE 1 END, pr.id DESC
            """
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT pr.*, a.display_name AS child_name, a.username AS child_username, a.avatar AS child_avatar
            FROM point_requests pr
            JOIN accounts a ON a.id = pr.account_id
            WHERE pr.account_id = ?
            ORDER BY pr.id DESC
            """,
            (user["id"],),
        ).fetchall()
    return [dict(row) for row in rows]


def account_overview_rows(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    today = current_date()
    rows = conn.execute(
        """
        SELECT
            a.id, a.username, a.display_name, a.role, a.avatar, a.active, a.created_at,
            COALESCE((SELECT SUM(r.amount) FROM records r WHERE r.account_id = a.id), 0) AS total_points,
            COALESCE((SELECT SUM(r.amount) FROM records r WHERE r.account_id = a.id AND r.date = ?), 0) AS today_net,
            (SELECT COUNT(*) FROM point_requests pr WHERE pr.account_id = a.id AND pr.status = 'pending') AS pending_count,
            (SELECT MAX(r.created_at) FROM records r WHERE r.account_id = a.id) AS last_activity
        FROM accounts a
        WHERE a.active = 1
        ORDER BY CASE a.role WHEN 'child' THEN 0 ELSE 1 END, a.id
        """,
        (today,),
    ).fetchall()
    return [dict(row) for row in rows]


def account_log_rows(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT id, actor_id, actor_username, actor_name, actor_avatar, target_id, target_username,
               target_name, target_role, target_avatar, action, created_at
        FROM account_logs
        ORDER BY id DESC
        LIMIT 200
        """
    ).fetchall()
    return [dict(row) for row in rows]


def state_payload(conn: sqlite3.Connection, user: sqlite3.Row) -> dict[str, Any]:
    account_id = active_child_id(conn, user)
    if account_id is None:
        return {
            "version": APP_VERSION,
            "user": safe_account(user),
            "children": [],
            "active_child": None,
            "active_child_id": None,
            "total_points": 0,
            "earn_items": [],
            "deduct_items": [],
            "rewards": [],
            "records": [],
            "requests": request_rows(conn, user),
            "account_overview": account_overview_rows(conn) if user["role"] == "admin" else [],
            "account_logs": account_log_rows(conn) if user["role"] == "admin" else [],
            "permissions": {
                "can_manage_points": user["role"] == "admin",
                "can_manage_accounts": user["role"] == "admin",
                "can_request_earn": user["role"] == "child",
                "can_request_exchange": user["role"] == "child",
            },
        }
    active_child = conn.execute("SELECT * FROM accounts WHERE id = ?", (account_id,)).fetchone()
    earn = conn.execute("SELECT id, name, points, icon FROM earn_items WHERE account_id = ? ORDER BY id", (account_id,)).fetchall()
    deduct = conn.execute("SELECT id, name, points, icon FROM deduct_items WHERE account_id = ? ORDER BY id", (account_id,)).fetchall()
    rewards = conn.execute("SELECT id, name, points, icon FROM rewards WHERE account_id = ? ORDER BY id", (account_id,)).fetchall()
    records = conn.execute(
        "SELECT id, title, amount, type, date, time FROM records WHERE account_id = ? ORDER BY id DESC", (account_id,)
    ).fetchall()
    children = conn.execute("SELECT * FROM accounts WHERE role = 'child' AND active = 1 ORDER BY id").fetchall()
    return {
        "version": APP_VERSION,
        "user": safe_account(user),
        "children": [safe_account(row) for row in children],
        "active_child": safe_account(active_child),
        "active_child_id": account_id,
        "total_points": get_balance(conn, account_id),
        "earn_items": [row_item(row, "earn") for row in earn],
        "deduct_items": [row_item(row, "deduct") for row in deduct],
        "rewards": [row_item(row, "reward") for row in rewards],
        "records": [dict(row) for row in records],
        "requests": request_rows(conn, user),
        "account_overview": account_overview_rows(conn) if user["role"] == "admin" else [],
        "account_logs": account_log_rows(conn) if user["role"] == "admin" else [],
        "permissions": {
            "can_manage_points": user["role"] == "admin",
            "can_manage_accounts": user["role"] == "admin",
            "can_request_earn": user["role"] == "child",
            "can_request_exchange": user["role"] == "child",
        },
    }


def api_error(message: str, status: int = 400):
    return jsonify({"error": message}), status


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/health")
def health():
    return jsonify({"status": "ok", "version": APP_VERSION})


@app.post("/api/auth/login")
def login():
    payload = request.get_json(silent=True) or {}
    username = str(payload.get("username", "")).strip()
    password = str(payload.get("password", ""))
    with connection() as conn:
        user = conn.execute("SELECT * FROM accounts WHERE username = ? AND active = 1", (username,)).fetchone()
        if user is None or not password_matches(password, user["password_hash"]):
            return api_error("账号或密码错误", 401)
        session.clear()
        session["user_id"] = int(user["id"])
        if user["role"] == "admin":
            first_child = conn.execute("SELECT id FROM accounts WHERE role = 'child' AND active = 1 ORDER BY id LIMIT 1").fetchone()
            if first_child:
                session["selected_child_id"] = int(first_child["id"])
        else:
            session["selected_child_id"] = int(user["id"])
        return jsonify(state_payload(conn, user))


@app.post("/api/auth/logout")
def logout():
    session.clear()
    return jsonify({"ok": True})


@app.get("/api/auth/me")
def auth_me():
    with connection() as conn:
        user = current_user(conn)
        if user is None:
            return jsonify({"authenticated": False}), 401
        return jsonify({"authenticated": True, "user": safe_account(user)})


@app.post("/api/auth/select-child")
@require_admin
def select_child():
    payload = request.get_json(silent=True) or {}
    try:
        child_id = int(payload.get("child_id"))
    except (TypeError, ValueError):
        return api_error("娃娃账号无效")
    with connection() as conn:
        user = current_user(conn)
        child = conn.execute("SELECT * FROM accounts WHERE id = ? AND role = 'child' AND active = 1", (child_id,)).fetchone()
        if user is None or child is None:
            return api_error("娃娃账号不存在", 404)
        session["selected_child_id"] = child_id
        return jsonify(state_payload(conn, user))


@app.get("/api/accounts")
@require_admin
def list_accounts():
    with connection() as conn:
        return jsonify({"accounts": [safe_account(row) for row in conn.execute("SELECT * FROM accounts ORDER BY role, id").fetchall()]})


@app.post("/api/accounts")
@require_admin
def create_account():
    payload = request.get_json(silent=True) or {}
    username = str(payload.get("username", "")).strip()
    display_name = str(payload.get("display_name", "")).strip()
    password = str(payload.get("password", ""))
    role = str(payload.get("role", "child")).lower()
    avatar = str(payload.get("avatar") or ("adult-male" if role == "admin" else "boy"))
    if not USERNAME_PATTERN.fullmatch(username):
        return api_error("账号需为 3-32 位字母、数字、下划线、点或短横线")
    if len(password) < 6:
        return api_error("密码至少需要 6 位")
    if role not in ("admin", "child"):
        return api_error("账号类型无效")
    if avatar not in AVATAR_OPTIONS or (role == "child" and avatar not in CHILD_AVATARS):
        return api_error("头像类型无效")
    if not display_name:
        display_name = username
    with connection() as conn:
        try:
            cursor = conn.execute(
                "INSERT INTO accounts(username, password_hash, display_name, role, avatar, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (username, password_hash(password), display_name, role, avatar, datetime.now().astimezone().isoformat(timespec="seconds")),
            )
        except sqlite3.IntegrityError:
            return api_error("账号名已存在")
        if role == "child":
            seed_items_for_child(conn, int(cursor.lastrowid))
        row = conn.execute("SELECT * FROM accounts WHERE id = ?", (cursor.lastrowid,)).fetchone()
        actor = current_user(conn)
        conn.execute(
            """
            INSERT INTO account_logs(
                actor_id, actor_username, actor_name, actor_avatar, target_id, target_username,
                target_name, target_role, target_avatar, action, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                actor["id"],
                actor["username"],
                actor["display_name"],
                actor["avatar"],
                row["id"],
                row["username"],
                row["display_name"],
                row["role"],
                row["avatar"],
                "create_child" if role == "child" else "create_admin",
                datetime.now().astimezone().isoformat(timespec="seconds"),
            ),
        )
        return jsonify(safe_account(row)), 201


@app.delete("/api/accounts/<int:account_id>")
@require_admin
def delete_account(account_id: int):
    with connection() as conn:
        user = current_user(conn)
        target = conn.execute("SELECT * FROM accounts WHERE id = ?", (account_id,)).fetchone()
        if user is None or target is None:
            return api_error("账号不存在", 404)
        if int(user["id"]) == account_id:
            return api_error("不能删除当前登录账号")
        if target["role"] == "admin" and conn.execute("SELECT COUNT(*) FROM accounts WHERE role = 'admin' AND active = 1").fetchone()[0] <= 1:
            return api_error("至少需要保留一个管理员账号")
        conn.execute(
            """
            INSERT INTO account_logs(
                actor_id, actor_username, actor_name, actor_avatar, target_id, target_username,
                target_name, target_role, target_avatar, action, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user["id"],
                user["username"],
                user["display_name"],
                user["avatar"],
                target["id"],
                target["username"],
                target["display_name"],
                target["role"],
                target["avatar"],
                "delete_child" if target["role"] == "child" else "delete_admin",
                datetime.now().astimezone().isoformat(timespec="seconds"),
            ),
        )
        for table in ("earn_items", "deduct_items", "rewards", "records", "point_requests"):
            conn.execute(f"DELETE FROM {table} WHERE account_id = ?", (account_id,))
        conn.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
        if session.get("selected_child_id") == account_id:
            session.pop("selected_child_id", None)
        return jsonify({"deleted": True})


@app.route("/api/accounts/<int:account_id>", methods=["PUT", "PATCH"])
@require_admin
def update_account(account_id: int):
    payload = request.get_json(silent=True) or {}
    display_name = str(payload.get("display_name", "")).strip()
    password = str(payload.get("password", ""))
    avatar = str(payload.get("avatar", ""))
    if not display_name:
        return api_error("显示名称不能为空")
    if password and len(password) < 6:
        return api_error("密码至少需要 6 位")
    with connection() as conn:
        user = current_user(conn)
        target = conn.execute("SELECT * FROM accounts WHERE id = ? AND active = 1", (account_id,)).fetchone()
        if user is None or target is None:
            return api_error("账号不存在", 404)
        allowed_avatars = CHILD_AVATARS if target["role"] == "child" else {"adult-male", "adult-female"}
        if not avatar:
            avatar = target["avatar"]
        if avatar not in allowed_avatars:
            return api_error("头像类型无效")
        assignments = ["display_name = ?", "avatar = ?"]
        values: list[Any] = [display_name, avatar]
        if password:
            assignments.append("password_hash = ?")
            values.append(password_hash(password))
        values.append(account_id)
        conn.execute(f"UPDATE accounts SET {', '.join(assignments)} WHERE id = ?", values)
        target = conn.execute("SELECT * FROM accounts WHERE id = ?", (account_id,)).fetchone()
        conn.execute(
            """
            INSERT INTO account_logs(
                actor_id, actor_username, actor_name, actor_avatar, target_id, target_username,
                target_name, target_role, target_avatar, action, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user["id"], user["username"], user["display_name"], user["avatar"],
                target["id"], target["username"], target["display_name"], target["role"], target["avatar"],
                "update_child" if target["role"] == "child" else "update_admin",
                datetime.now().astimezone().isoformat(timespec="seconds"),
            ),
        )
        return jsonify(safe_account(target))


@app.get("/api/state")
@require_user
def get_state():
    with connection() as conn:
        user = current_user(conn)
        return jsonify(state_payload(conn, user))


@app.post("/api/transactions")
@require_user
def create_transaction():
    payload = request.get_json(silent=True) or {}
    kind = str(payload.get("kind", "")).lower()
    try:
        with connection() as conn:
            user = current_user(conn)
            if user["role"] == "child" and kind == "deduct":
                return api_error("娃娃账号不能直接扣取积分，请使用兑换奖励", 403)
            account_id = active_child_id(conn, user)
            if account_id is None:
                return api_error("当前没有可用的娃娃账号")
            name = str(payload.get("name", "")).strip()
            points_value = payload.get("points")
            transaction_type = "income"
            if kind == "earn":
                item_id = int(payload.get("item_id")) if payload.get("item_id") is not None else None
                if item_id:
                    item = conn.execute("SELECT name, points FROM earn_items WHERE id = ? AND account_id = ?", (item_id, account_id)).fetchone()
                    if item is None:
                        return api_error("赚取项目不存在", 404)
                    name, points_value = item["name"], item["points"]
                points = positive_int(points_value)
                amount = points
            elif kind == "deduct":
                item_id = int(payload.get("item_id")) if payload.get("item_id") is not None else None
                if item_id:
                    item = conn.execute("SELECT name, points FROM deduct_items WHERE id = ? AND account_id = ?", (item_id, account_id)).fetchone()
                    if item is None:
                        return api_error("扣取项目不存在", 404)
                    name, points_value = item["name"], item["points"]
                points = positive_int(points_value)
                amount = -points
                transaction_type = "expense"
            elif kind == "exchange":
                reward_id = int(payload.get("reward_id")) if payload.get("reward_id") is not None else None
                if reward_id:
                    reward = conn.execute("SELECT name, points FROM rewards WHERE id = ? AND account_id = ?", (reward_id, account_id)).fetchone()
                    if reward is None:
                        return api_error("兑换奖励不存在", 404)
                    name, points_value = reward["name"], reward["points"]
                points = positive_int(points_value)
                if get_balance(conn, account_id) < points:
                    return api_error("积分不足", 409)
                amount = -points
                transaction_type = "expense"
            elif kind == "manual":
                try:
                    amount = int(points_value)
                except (TypeError, ValueError) as exc:
                    raise ValueError("积分数值必须是整数") from exc
                if amount == 0:
                    raise ValueError("积分数值不能为 0")
                name = f"补积分：{name}" if name else "补积分"
                transaction_type = "income" if amount > 0 else "expense"
            else:
                return api_error("不支持的交易类型")
            transaction_date = valid_date(payload.get("date"))
            transaction_time = str(payload.get("time") or current_time())[:5]
            if not name:
                name = transaction_date
            if user["role"] == "child" and amount < 0 and kind != "exchange":
                return api_error("娃娃账号不能扣除积分", 403)
            if user["role"] == "child" and kind in ("earn", "exchange", "manual"):
                cursor = conn.execute(
                    """
                    INSERT INTO point_requests(
                        account_id, requester_id, kind, title, amount, type, date, time, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        account_id,
                        user["id"],
                        kind,
                        name,
                        amount,
                        transaction_type,
                        transaction_date,
                        transaction_time,
                        datetime.now().astimezone().isoformat(timespec="seconds"),
                    ),
                )
                return jsonify({"request_submitted": True, "request_id": cursor.lastrowid, **state_payload(conn, user)}), 202
            cursor = conn.execute(
                "INSERT INTO records(account_id, title, amount, type, date, time, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (account_id, name, amount, transaction_type, transaction_date, transaction_time, datetime.now().astimezone().isoformat(timespec="seconds")),
            )
            return jsonify({"record_id": cursor.lastrowid, **state_payload(conn, user)}), 201
    except (TypeError, ValueError) as exc:
        return api_error(str(exc))


@app.post("/api/requests/<int:request_id>/approve")
@require_admin
def approve_request(request_id: int):
    with connection() as conn:
        user = current_user(conn)
        point_request = conn.execute(
            "SELECT * FROM point_requests WHERE id = ? AND status = 'pending'", (request_id,)
        ).fetchone()
        if point_request is None:
            return api_error("待审核申请不存在或已经处理", 404)
        if point_request["amount"] < 0 and get_balance(conn, point_request["account_id"]) < abs(point_request["amount"]):
            return api_error("当前积分不足，无法通过兑换申请", 409)
        conn.execute(
            """
            INSERT INTO records(account_id, title, amount, type, date, time, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                point_request["account_id"],
                point_request["title"],
                point_request["amount"],
                point_request["type"],
                point_request["date"],
                point_request["time"],
                datetime.now().astimezone().isoformat(timespec="seconds"),
            ),
        )
        conn.execute(
            "UPDATE point_requests SET status = 'approved', reviewed_at = ?, reviewer_id = ? WHERE id = ?",
            (datetime.now().astimezone().isoformat(timespec="seconds"), user["id"], request_id),
        )
        return jsonify(state_payload(conn, user))


@app.post("/api/requests/<int:request_id>/reject")
@require_admin
def reject_request(request_id: int):
    payload = request.get_json(silent=True) or {}
    reason = str(payload.get("reason", "管理员拒绝了这条申请")).strip()[:200]
    with connection() as conn:
        user = current_user(conn)
        point_request = conn.execute(
            "SELECT id FROM point_requests WHERE id = ? AND status = 'pending'", (request_id,)
        ).fetchone()
        if point_request is None:
            return api_error("待审核申请不存在或已经处理", 404)
        conn.execute(
            "UPDATE point_requests SET status = 'rejected', reviewed_at = ?, reviewer_id = ?, reject_reason = ? WHERE id = ?",
            (datetime.now().astimezone().isoformat(timespec="seconds"), user["id"], reason or "管理员拒绝了这条申请", request_id),
        )
        return jsonify(state_payload(conn, user))


@app.post("/api/transactions/<int:record_id>/undo")
@require_user
def undo_transaction(record_id: int):
    with connection() as conn:
        user = current_user(conn)
        if user["role"] == "child":
            return api_error("娃娃账号不能撤销积分记录", 403)
        account_id = active_child_id(conn, user)
        cursor = conn.execute("DELETE FROM records WHERE id = ? AND account_id = ?", (record_id, account_id))
        if cursor.rowcount == 0:
            return api_error("积分记录不存在", 404)
        return jsonify(state_payload(conn, user))


@app.post("/api/items/<kind>")
@require_admin
def create_item(kind: str):
    if kind not in ITEM_TABLES:
        return api_error("不支持的项目类型", 404)
    payload = request.get_json(silent=True) or {}
    name = str(payload.get("name", "")).strip()
    icon = str(payload.get("icon") or ITEM_DEFAULT_ICONS[kind])
    try:
        points = positive_int(payload.get("points"))
    except ValueError as exc:
        return api_error(str(exc))
    if not name:
        return api_error("项目名称不能为空")
    if icon not in PROJECT_ICONS:
        return api_error("项目图片类型无效")
    with connection() as conn:
        user = current_user(conn)
        account_id = active_child_id(conn, user)
        if account_id is None:
            return api_error("当前没有可用的娃娃账号")
        table = ITEM_TABLES[kind]
        cursor = conn.execute(f"INSERT INTO {table}(account_id, name, points, icon) VALUES (?, ?, ?, ?)", (account_id, name, points, icon))
        row = conn.execute(f"SELECT id, name, points, icon FROM {table} WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return jsonify(row_item(row, kind)), 201


@app.route("/api/items/<kind>/<int:item_id>", methods=["PUT", "DELETE"])
@require_admin
def item_detail(kind: str, item_id: int):
    if kind not in ITEM_TABLES:
        return api_error("不支持的项目类型", 404)
    with connection() as conn:
        user = current_user(conn)
        account_id = active_child_id(conn, user)
        table = ITEM_TABLES[kind]
        existing = conn.execute(f"SELECT id, name, points, icon FROM {table} WHERE id = ? AND account_id = ?", (item_id, account_id)).fetchone()
        if existing is None:
            return api_error("项目不存在", 404)
        if request.method == "DELETE":
            conn.execute(f"DELETE FROM {table} WHERE id = ? AND account_id = ?", (item_id, account_id))
            return jsonify({"deleted": True})
        payload = request.get_json(silent=True) or {}
        name = str(payload.get("name", "")).strip()
        icon = str(payload.get("icon") or existing["icon"] or ITEM_DEFAULT_ICONS[kind])
        if not name:
            return api_error("项目名称不能为空")
        if icon not in PROJECT_ICONS:
            return api_error("项目图片类型无效")
        try:
            points = positive_int(payload.get("points"))
        except ValueError as exc:
            return api_error(str(exc))
        conn.execute(f"UPDATE {table} SET name = ?, points = ?, icon = ? WHERE id = ? AND account_id = ?", (name, points, icon, item_id, account_id))
        row = conn.execute(f"SELECT id, name, points, icon FROM {table} WHERE id = ?", (item_id,)).fetchone()
        return jsonify(row_item(row, kind))


@app.post("/api/system/clear")
@require_admin
def clear_points():
    with connection() as conn:
        user = current_user(conn)
        account_id = active_child_id(conn, user)
        conn.execute("DELETE FROM records WHERE account_id = ?", (account_id,))
        conn.execute("DELETE FROM point_requests WHERE account_id = ?", (account_id,))
        return jsonify(state_payload(conn, user))


@app.post("/api/system/reset")
@require_admin
def reset_system():
    with connection() as conn:
        user = current_user(conn)
        account_id = active_child_id(conn, user)
        if account_id is None:
            return api_error("当前没有可用的娃娃账号")
        conn.execute("DELETE FROM records WHERE account_id = ?", (account_id,))
        conn.execute("DELETE FROM point_requests WHERE account_id = ?", (account_id,))
        for table in ("earn_items", "deduct_items", "rewards"):
            conn.execute(f"DELETE FROM {table} WHERE account_id = ?", (account_id,))
        seed_items_for_child(conn, account_id)
        return jsonify(state_payload(conn, user))


@app.errorhandler(404)
def not_found(error):
    if request.path.startswith("/api/"):
        return api_error("接口不存在", 404)
    return error


init_db()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "9696")), debug=False)
