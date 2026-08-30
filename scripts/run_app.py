"""Start the API and the frontend together.

Usage:  python scripts/run_app.py

The two run as separate processes, matching the architecture in spec section 19.
This just saves opening two terminals; running them by hand works identically:

    uvicorn app.api.main:app --reload --port 8010
    streamlit run frontend/streamlit_app.py

Ctrl-C stops both.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request

import _bootstrap  # noqa: F401  # must precede any app import

from app.config import PROJECT_ROOT

API_PORT = int(os.getenv("API_PORT", "8010"))
UI_PORT = int(os.getenv("UI_PORT", "8501"))
API_URL = f"http://127.0.0.1:{API_PORT}"


def wait_for_api(timeout: int = 60) -> bool:
    """Block until the API answers, so the UI never opens onto an error."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{API_URL}/health", timeout=2) as response:
                if response.status == 200:
                    return True
        except (urllib.error.URLError, OSError):
            time.sleep(1)
    return False


def main() -> int:
    environment = {**os.environ, "PYTHONPATH": str(PROJECT_ROOT), "API_URL": API_URL}

    print(f"starting API on {API_URL}")
    api = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.api.main:app",
         "--port", str(API_PORT), "--log-level", "warning"],
        cwd=PROJECT_ROOT,
        env=environment,
    )

    if not wait_for_api():
        print("API did not start; check the port is free", file=sys.stderr)
        api.terminate()
        return 1
    print("API ready")

    print(f"starting UI on http://localhost:{UI_PORT}")
    ui = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", "frontend/streamlit_app.py",
         "--server.port", str(UI_PORT)],
        cwd=PROJECT_ROOT,
        env=environment,
    )

    try:
        ui.wait()
    except KeyboardInterrupt:
        print("\nstopping")
    finally:
        for process in (ui, api):
            if process.poll() is None:
                process.send_signal(signal.SIGTERM)
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
