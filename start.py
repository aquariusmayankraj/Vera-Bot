"""Same portable start command on macOS, Windows, Docker and cloud hosts."""
import os

from dotenv import load_dotenv
import uvicorn

if __name__ == "__main__":
    load_dotenv()
    try:
        port = int(os.getenv("PORT", "8080"))
        if not 1 <= port <= 65535:
            raise ValueError
    except ValueError:
        raise SystemExit("PORT must be an integer from 1 to 65535") from None
    uvicorn.run("bot:app", host="0.0.0.0", port=port, workers=1,
                log_level=os.getenv("LOG_LEVEL", "info"), access_log=False)
