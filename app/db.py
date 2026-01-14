import sqlite3
from typing import Optional, Dict, Any

class DB:
    def __init__(self, path: str):
        self.path = path
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row

    def init(self) -> None:
        cur = self.conn.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            chat_id INTEGER PRIMARY KEY,
            tips_enabled INTEGER NOT NULL DEFAULT 0,
            tips_index INTEGER NOT NULL DEFAULT 0,
            last_result TEXT
        );
        """)
        self.conn.commit()

    def ensure_user(self, chat_id: int) -> None:
        cur = self.conn.cursor()
        cur.execute("INSERT OR IGNORE INTO users(chat_id) VALUES (?);", (chat_id,))
        self.conn.commit()

    def set_tips(self, chat_id: int, enabled: bool) -> None:
        cur = self.conn.cursor()
        cur.execute("UPDATE users SET tips_enabled=? WHERE chat_id=?;", (1 if enabled else 0, chat_id))
        self.conn.commit()

    def get_tips_enabled(self, chat_id: int) -> bool:
        cur = self.conn.cursor()
        row = cur.execute("SELECT tips_enabled FROM users WHERE chat_id=?;", (chat_id,)).fetchone()
        return bool(row["tips_enabled"]) if row else False

    def get_all_tips_enabled_users(self):
        cur = self.conn.cursor()
        rows = cur.execute("SELECT chat_id, tips_index FROM users WHERE tips_enabled=1;").fetchall()
        return [(int(r["chat_id"]), int(r["tips_index"])) for r in rows]

    def advance_tip_index(self, chat_id: int, new_index: int) -> None:
        cur = self.conn.cursor()
        cur.execute("UPDATE users SET tips_index=? WHERE chat_id=?;", (new_index, chat_id))
        self.conn.commit()

    def save_last_result(self, chat_id: int, text: str) -> None:
        cur = self.conn.cursor()
        cur.execute("UPDATE users SET last_result=? WHERE chat_id=?;", (text, chat_id))
        self.conn.commit()

    def get_last_result(self, chat_id: int) -> Optional[str]:
        cur = self.conn.cursor()
        row = cur.execute("SELECT last_result FROM users WHERE chat_id=?;", (chat_id,)).fetchone()
        if not row:
            return None
        return row["last_result"]

    def close(self) -> None:
        self.conn.close()
