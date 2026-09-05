"""Desktop entry point: runs the Streamlit app headlessly in a subprocess and
displays it in a native window via pywebview, so the whole thing can be
double-clicked instead of driven from a terminal.

Streamlit installs a SIGTERM handler that only works on a process's main
thread, so the server can't run in a background thread of this process --
it runs in a child process instead, with this process's main thread free
for the pywebview event loop. The child is this same script/executable,
re-invoked with an env var flag so a frozen build doesn't need a second exe.
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import webview

WORKER_ENV_FLAG = "FBR_APP_STREAMLIT_WORKER"
PORT_ENV_VAR = "FBR_APP_PORT"


def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parent


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _run_streamlit_worker() -> None:
    from streamlit.web import bootstrap

    port = int(os.environ[PORT_ENV_VAR])
    script_path = str(_base_dir() / "app.py")
    flag_options = {
        "server.port": port,
        "server.address": "127.0.0.1",
        "server.headless": True,
        "browser.gatherUsageStats": False,
        "server.enableXsrfProtection": False,
        "server.enableCORS": False,
        # Streamlit auto-detects development mode from its own install layout;
        # inside a frozen build that probe is unreliable and can come back
        # True, which then makes it reject an explicit server.port outright.
        "global.developmentMode": False,
    }
    # bootstrap.run() only re-applies flag_options when config.toml changes on
    # disk -- the CLI itself applies them once up front before calling run(),
    # so a caller going straight to run() (as this launcher does) must do the
    # same or the server silently starts on the default port/address.
    bootstrap.load_config_options(flag_options=flag_options)
    bootstrap.run(script_path, is_hello=False, args=[], flag_options=flag_options)


def _wait_for_server(port: int, timeout: float = 30.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.3)
    return False


def _spawn_worker(port: int) -> subprocess.Popen:
    env = os.environ.copy()
    env[WORKER_ENV_FLAG] = "1"
    env[PORT_ENV_VAR] = str(port)
    if getattr(sys, "frozen", False):
        cmd = [sys.executable]
    else:
        cmd = [sys.executable, str(Path(__file__).resolve())]
    return subprocess.Popen(cmd, cwd=str(_base_dir()), env=env)


def main() -> None:
    if os.environ.get(WORKER_ENV_FLAG) == "1":
        _run_streamlit_worker()
        return

    os.chdir(_base_dir())
    port = _find_free_port()
    proc = _spawn_worker(port)

    try:
        if not _wait_for_server(port):
            raise RuntimeError("Streamlit server did not start in time.")

        webview.create_window(
            "FBR vs Local Sales Tax Reconciliation",
            f"http://127.0.0.1:{port}",
            width=1280,
            height=800,
            min_size=(900, 600),
        )
        webview.start()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    main()
