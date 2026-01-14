import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Settings:
    bot_token: str
    tz: str
    daily_hour: int
    daily_minute: int
    db_path: str

def get_settings() -> Settings:
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("BOT_TOKEN is not set")

    tz = os.getenv("TZ", "Europe/Vienna").strip()
    daily_hour = int(os.getenv("DAILY_HOUR", "10"))
    daily_minute = int(os.getenv("DAILY_MINUTE", "0"))
    db_path = os.getenv("DB_PATH", "data.sqlite3")

    return Settings(
        bot_token=token,
        tz=tz,
        daily_hour=daily_hour,
        daily_minute=daily_minute,
        db_path=db_path,
    )
