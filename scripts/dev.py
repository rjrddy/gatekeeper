"""Owned local processes for browser review; SIGTERM shuts down every child."""

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

owned: list[subprocess.Popen] = []


def main() -> None:
    for line in Path(".env").read_text().splitlines():
        key, value = line.split("=", 1)
        os.environ[key] = value
    Path("data").mkdir(exist_ok=True)
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    signal.signal(signal.SIGINT, lambda *_: sys.exit(0))
    with open("data/dev.log", "a") as log:
        try:
            for port, mode in [(18301, "good"), (18302, "good"), (18303, "bad"), (18304, "slow")]:
                owned.append(
                    subprocess.Popen(
                        [
                            sys.executable,
                            "-m",
                            "uvicorn",
                            "gatekeeper.demo_service:app",
                            "--host",
                            "127.0.0.1",
                            "--port",
                            str(port),
                        ],
                        env={**os.environ, "GK_SERVICE_MODE": mode},
                        stdout=log,
                        stderr=log,
                    )
                )
            owned.append(
                subprocess.Popen(
                    [
                        sys.executable,
                        "-m",
                        "uvicorn",
                        "gatekeeper.app:create_app",
                        "--factory",
                        "--host",
                        "127.0.0.1",
                        "--port",
                        "8082",
                        "--log-config",
                        "deploy/logging.json",
                    ],
                    stdout=log,
                    stderr=log,
                )
            )
            print(
                "Gatekeeper local preview: http://127.0.0.1:8082 (operator password in .env)",
                flush=True,
            )
            while all(p.poll() is None for p in owned):
                time.sleep(0.2)
            raise RuntimeError("child exited; inspect data/dev.log")
        finally:
            for process in owned:
                if process.poll() is None:
                    process.terminate()
            for process in owned:
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)


if __name__ == "__main__":
    main()
