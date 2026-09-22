from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    db_path: str = "data/vera.sqlite3"
    team_name: str = "My Vera Bot"
    team_members: tuple[str, ...] = ("Your Name",)
    contact_email: str = ""
    submitted_at: str = ""
    api_token: str = ""
    teardown_token: str = ""
    max_body_bytes: int = 500 * 1024
    max_actions: int = 20
    min_gap_seconds: int = 1800
    max_unanswered: int = 3
    state_ttl_hours: int = 24
    docs_enabled: bool = True

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)

        def integer(name: str, default: int, lower: int, upper: int) -> int:
            try:
                value = int(os.getenv(name, str(default)))
            except ValueError as exc:
                raise ValueError(f"{name} must be an integer") from exc
            if not lower <= value <= upper:
                raise ValueError(f"{name} must be between {lower} and {upper}")
            return value

        return cls(
            db_path=os.getenv("DB_PATH", "data/vera.sqlite3"),
            team_name=os.getenv("TEAM_NAME", "My Vera Bot"),
            team_members=tuple(x.strip() for x in os.getenv("TEAM_MEMBERS", "Your Name").split(",") if x.strip()),
            contact_email=os.getenv("CONTACT_EMAIL", ""),
            submitted_at=os.getenv("SUBMITTED_AT", ""),
            api_token=os.getenv("API_TOKEN", ""),
            teardown_token=os.getenv("TEARDOWN_TOKEN", ""),
            min_gap_seconds=integer("MIN_GAP_SECONDS", 1800, 0, 86400),
            max_unanswered=integer("MAX_UNANSWERED", 3, 1, 3),
            state_ttl_hours=integer("STATE_TTL_HOURS", 24, 1, 168),
            docs_enabled=os.getenv("DOCS_ENABLED", "true").lower() == "true",
        )
