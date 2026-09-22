"""Linux container launcher: initialize only the configured DB directory, then drop privileges."""
from __future__ import annotations
import os
import sys
from pathlib import Path


def main() -> None:
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        path = os.getenv("DB_PATH", "/app/data/vera.sqlite3")
        if path != ":memory:":
            db = Path(path).expanduser().resolve()
            db.parent.mkdir(parents=True, exist_ok=True)
            os.chown(db.parent, 10001, 10001)
            for suffix in ("", "-wal", "-shm", "-journal"):
                file = Path(str(db) + suffix)
                if file.exists():
                    os.chown(file, 10001, 10001)
        os.setgroups([])
        os.setgid(10001)
        os.setuid(10001)
    os.execv(sys.executable, [sys.executable, "start.py"])


if __name__ == "__main__":
    main()
