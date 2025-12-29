import aiosqlite
from datetime import datetime, date
from typing import Optional
from bot.config import config


class Database:
    def __init__(self, db_path: str = None):
        self.db_path = db_path or config.DB_PATH
        self.conn: Optional[aiosqlite.Connection] = None

    async def connect(self):
        self.conn = await aiosqlite.connect(self.db_path)
        self.conn.row_factory = aiosqlite.Row
        await self._create_tables()

    async def close(self):
        if self.conn:
            await self.conn.close()

    async def _create_tables(self):
        await self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                is_banned INTEGER DEFAULT 0,
                ban_reason TEXT,
                msg_count INTEGER DEFAULT 0,
                msg_count_today INTEGER DEFAULT 0,
                last_msg_date TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                user_msg_id INTEGER,
                forward_msg_id INTEGER,
                content_type TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );

            CREATE TABLE IF NOT EXISTS rate_limits (
                user_id INTEGER PRIMARY KEY,
                minute_count INTEGER DEFAULT 0,
                minute_start TEXT,
                cooldown_until TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_messages_forward ON messages(forward_msg_id);
            CREATE INDEX IF NOT EXISTS idx_messages_user ON messages(user_id);
        """)
        await self.conn.commit()

    # ===== 用户相关 =====

    async def get_or_create_user(self, user_id: int, username: str = None,
                                  first_name: str = None, last_name: str = None) -> dict:
        cursor = await self.conn.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        )
        row = await cursor.fetchone()

        if row:
            # 更新用户信息
            await self.conn.execute("""
                UPDATE users SET username = ?, first_name = ?, last_name = ?
                WHERE user_id = ?
            """, (username, first_name, last_name, user_id))
            await self.conn.commit()
            # 重新获取
            cursor = await self.conn.execute(
                "SELECT * FROM users WHERE user_id = ?", (user_id,)
            )
            row = await cursor.fetchone()
        else:
            await self.conn.execute("""
                INSERT INTO users (user_id, username, first_name, last_name, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, username, first_name, last_name, datetime.now().isoformat()))
            await self.conn.commit()
            cursor = await self.conn.execute(
                "SELECT * FROM users WHERE user_id = ?", (user_id,)
            )
            row = await cursor.fetchone()

        return dict(row)

    async def is_user_banned(self, user_id: int) -> bool:
        cursor = await self.conn.execute(
            "SELECT is_banned FROM users WHERE user_id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        return bool(row and row["is_banned"])

    async def ban_user(self, user_id: int, reason: str = None):
        await self.conn.execute("""
            UPDATE users SET is_banned = 1, ban_reason = ? WHERE user_id = ?
        """, (reason, user_id))
        await self.conn.commit()

    async def unban_user(self, user_id: int):
        await self.conn.execute("""
            UPDATE users SET is_banned = 0, ban_reason = NULL WHERE user_id = ?
        """, (user_id,))
        await self.conn.commit()

    async def get_user(self, user_id: int) -> Optional[dict]:
        cursor = await self.conn.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def increment_msg_count(self, user_id: int):
        today = date.today().isoformat()
        cursor = await self.conn.execute(
            "SELECT last_msg_date FROM users WHERE user_id = ?", (user_id,)
        )
        row = await cursor.fetchone()

        if row and row["last_msg_date"] == today:
            await self.conn.execute("""
                UPDATE users SET msg_count = msg_count + 1, msg_count_today = msg_count_today + 1
                WHERE user_id = ?
            """, (user_id,))
        else:
            await self.conn.execute("""
                UPDATE users SET msg_count = msg_count + 1, msg_count_today = 1, last_msg_date = ?
                WHERE user_id = ?
            """, (today, user_id))
        await self.conn.commit()

    async def get_today_msg_count(self, user_id: int) -> int:
        today = date.today().isoformat()
        cursor = await self.conn.execute(
            "SELECT msg_count_today, last_msg_date FROM users WHERE user_id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        if row and row["last_msg_date"] == today:
            return row["msg_count_today"]
        return 0

    # ===== 消息相关 =====

    async def save_message(self, user_id: int, user_msg_id: int,
                           forward_msg_id: int, content_type: str) -> int:
        cursor = await self.conn.execute("""
            INSERT INTO messages (user_id, user_msg_id, forward_msg_id, content_type, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, user_msg_id, forward_msg_id, content_type, datetime.now().isoformat()))
        await self.conn.commit()
        return cursor.lastrowid

    async def get_message_by_forward_id(self, forward_msg_id: int) -> Optional[dict]:
        cursor = await self.conn.execute(
            "SELECT * FROM messages WHERE forward_msg_id = ?", (forward_msg_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def get_user_message_count(self, user_id: int) -> int:
        cursor = await self.conn.execute(
            "SELECT COUNT(*) as count FROM messages WHERE user_id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        return row["count"] if row else 0

    # ===== 频率限制 =====

    async def check_rate_limit(self, user_id: int) -> tuple[bool, str]:
        """返回 (是否允许, 原因)"""
        now = datetime.now()
        cursor = await self.conn.execute(
            "SELECT * FROM rate_limits WHERE user_id = ?", (user_id,)
        )
        row = await cursor.fetchone()

        # 检查冷却
        if row and row["cooldown_until"]:
            cooldown_until = datetime.fromisoformat(row["cooldown_until"])
            if now < cooldown_until:
                remaining = int((cooldown_until - now).total_seconds() / 60) + 1
                return False, f"发送过于频繁，请 {remaining} 分钟后再试"

        # 检查每日限制
        today_count = await self.get_today_msg_count(user_id)
        if today_count >= config.RATE_LIMIT_PER_DAY:
            return False, "已达到今日消息上限，请明天再试"

        # 检查每分钟限制
        if row:
            minute_start = datetime.fromisoformat(row["minute_start"]) if row["minute_start"] else None
            if minute_start and (now - minute_start).total_seconds() < 60:
                if row["minute_count"] >= config.RATE_LIMIT_PER_MINUTE:
                    # 触发冷却
                    from datetime import timedelta
                    cooldown_until = now + timedelta(minutes=config.COOLDOWN_MINUTES)
                    await self.conn.execute("""
                        UPDATE rate_limits SET cooldown_until = ?, minute_count = 0
                        WHERE user_id = ?
                    """, (cooldown_until.isoformat(), user_id))
                    await self.conn.commit()
                    return False, f"发送过于频繁，请 {config.COOLDOWN_MINUTES} 分钟后再试"
                else:
                    # 增加计数
                    await self.conn.execute("""
                        UPDATE rate_limits SET minute_count = minute_count + 1
                        WHERE user_id = ?
                    """, (user_id,))
            else:
                # 新的一分钟
                await self.conn.execute("""
                    UPDATE rate_limits SET minute_count = 1, minute_start = ?, cooldown_until = NULL
                    WHERE user_id = ?
                """, (now.isoformat(), user_id))
        else:
            # 首次记录
            await self.conn.execute("""
                INSERT INTO rate_limits (user_id, minute_count, minute_start)
                VALUES (?, 1, ?)
            """, (user_id, now.isoformat()))

        await self.conn.commit()
        return True, ""

    # ===== 统计 =====

    async def get_stats(self) -> dict:
        cursor = await self.conn.execute("SELECT COUNT(*) as count FROM users")
        total_users = (await cursor.fetchone())["count"]

        cursor = await self.conn.execute("SELECT COUNT(*) as count FROM messages")
        total_messages = (await cursor.fetchone())["count"]

        cursor = await self.conn.execute("SELECT COUNT(*) as count FROM users WHERE is_banned = 1")
        banned_users = (await cursor.fetchone())["count"]

        today = date.today().isoformat()
        cursor = await self.conn.execute(
            "SELECT COUNT(*) as count FROM messages WHERE date(created_at) = ?", (today,)
        )
        today_messages = (await cursor.fetchone())["count"]

        return {
            "total_users": total_users,
            "total_messages": total_messages,
            "banned_users": banned_users,
            "today_messages": today_messages,
        }


# 全局数据库实例
db = Database()
