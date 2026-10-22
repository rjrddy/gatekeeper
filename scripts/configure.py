"""Generate local operator credentials without displaying them or overwriting state."""

import os
import secrets
from pathlib import Path

path = Path(".env")
values = (
    "\n".join(
        f"{key}={secrets.token_urlsafe(32)}"
        for key in ["GK_PASSWORD", "GK_TOKEN", "GK_WEBHOOK_SECRET"]
    )
    + "\n"
)
fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
with os.fdopen(fd, "w") as stream:
    stream.write(values)
print("Created ignored .env (mode 0600). Open locally for the operator password.")
