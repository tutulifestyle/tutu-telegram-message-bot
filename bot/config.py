import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # 必需配置
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    ADMIN_ID: int = int(os.getenv("ADMIN_ID", "0"))

    # 频率限制
    RATE_LIMIT_PER_MINUTE: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "3"))
    RATE_LIMIT_PER_DAY: int = int(os.getenv("RATE_LIMIT_PER_DAY", "20"))
    COOLDOWN_MINUTES: int = int(os.getenv("COOLDOWN_MINUTES", "5"))

    # 数据库路径
    DB_PATH: str = os.getenv("DB_PATH", "data/bot.db")

    @classmethod
    def validate(cls) -> bool:
        if not cls.BOT_TOKEN:
            raise ValueError("BOT_TOKEN 未设置")
        if not cls.ADMIN_ID:
            raise ValueError("ADMIN_ID 未设置")
        return True


config = Config()
