"""Public HTTPS URL via Serveo. Saves only the URL Serveo actually prints."""

from __future__ import annotations

import os
import re
import subprocess
import threading
import time
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"
URL_FILE = DATA_DIR / "public_url.txt"
KEY_FILE = DATA_DIR / "tunnel_ed25519"
URL_RE = re.compile(r"https://[a-zA-Z0-9.-]+\.serveousercontent\.com")


def public_url() -> str | None:
    if not URL_FILE.exists():
        return None
    text = URL_FILE.read_text(encoding="utf-8").strip().rstrip("/")
    if not text or text.endswith(".serveo.net"):
        return None
    return text


def tunnel_alias() -> str:
    env = os.environ.get("TUNNEL_ALIAS", "").strip()
    if env:
        return env
    path = DATA_DIR / "secret.txt"
    suffix = path.read_text(encoding="utf-8").strip()[:8] if path.exists() else "anketa"
    return f"qr-anketa-{suffix.lower()}"


def _ensure_key() -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if KEY_FILE.exists():
        return KEY_FILE
    subprocess.run(
        ["ssh-keygen", "-t", "ed25519", "-f", str(KEY_FILE), "-N", "", "-q"],
        check=True,
    )
    return KEY_FILE


def _save_url(url: str) -> None:
    url = url.rstrip("/")
    if url.endswith(".serveo.net"):
        return
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    URL_FILE.write_text(url, encoding="utf-8")
    print(f"Публичный адрес: {url}/", flush=True)
    print(f"QR-страница:     {url}/qr", flush=True)


def _ssh_cmd(local_port: int) -> list[str]:
    alias = tunnel_alias()
    host = f"{alias}.serveousercontent.com"
    return [
        "ssh",
        "-p",
        "443",
        "-l",
        alias,
        "-i",
        str(_ensure_key()),
        "-o",
        "StrictHostKeyChecking=accept-new",
        "-o",
        "ServerAliveInterval=15",
        "-o",
        "ServerAliveCountMax=4",
        "-o",
        "TCPKeepAlive=yes",
        "-o",
        "ExitOnForwardFailure=yes",
        "-R",
        f"{host}:80:127.0.0.1:{local_port}",
        "serveo.net",
    ]


def start_tunnel(local_port: int) -> None:
    def worker() -> None:
        while True:
            try:
                proc = subprocess.Popen(
                    _ssh_cmd(local_port),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    encoding="utf-8",
                    errors="replace",
                )
            except Exception as exc:
                print(f"Туннель не запустился: {exc}", flush=True)
                time.sleep(8)
                continue
            assert proc.stdout is not None
            for line in proc.stdout:
                print(line.rstrip(), flush=True)
                match = URL_RE.search(line)
                if match:
                    _save_url(match.group(0))
            proc.wait()
            time.sleep(4)

    threading.Thread(target=worker, daemon=True).start()
