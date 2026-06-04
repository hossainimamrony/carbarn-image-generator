from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import webbrowser
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from canva_bg_remove_download import (
    ASSETS_DIR,
    BASE_DIR,
    CHROME_EXE_PATH,
    DEFAULT_DEBUG_PORT,
    DEFAULT_DESIGN_URL,
    DEFAULT_GOOGLE_PHOTOS_DIR,
    DEFAULT_GOOGLE_PHOTOS_URL,
    DEFAULT_IMAGE_PATH,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_OUTPUT_NAME,
    DEFAULT_PROFILE_DIR,
)


HOST = "127.0.0.1"
PORT = 8765
WEB_DIR = BASE_DIR / "web"
SCRIPT_PATH = BASE_DIR / "canva_bg_remove_download.py"
SETTINGS_PATH = BASE_DIR / "canva_web_settings.json"


DEFAULTS: dict[str, Any] = {
    "design_url": DEFAULT_DESIGN_URL,
    "photos_url": DEFAULT_GOOGLE_PHOTOS_URL,
    "image": str(DEFAULT_IMAGE_PATH),
    "photos_dir": str(DEFAULT_GOOGLE_PHOTOS_DIR),
    "output_dir": str(DEFAULT_OUTPUT_DIR),
    "output_name": DEFAULT_OUTPUT_NAME,
    "chrome_exe": CHROME_EXE_PATH,
    "profile_dir": str(DEFAULT_PROFILE_DIR),
    "debug_port": str(DEFAULT_DEBUG_PORT),
    "login_timeout": "900",
    "editor_timeout": "120",
    "upload_timeout": "120",
    "bg_remove_timeout": "240",
    "download_timeout": "300",
    "google_download_timeout": "600",
    "max_images": "",
    "fallback_thumbnail_x": "150",
    "fallback_thumbnail_y": "260",
    "initial_width": "3651 px",
    "initial_height": "2738 px",
    "initial_x": "0 px",
    "initial_y": "0 px",
    "target_width": "3000 px",
    "target_x": "500 px",
    "target_y": "500 px",
    "single_image": False,
    "skip_google_download": False,
    "skip_initial_fit": False,
    "keep_open": False,
}


class AutomationState:
    def __init__(self) -> None:
        self.process: subprocess.Popen[str] | None = None
        self.logs: list[str] = []
        self.lock = threading.Lock()
        self.return_code: int | None = None

    def running(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def append_log(self, text: str) -> None:
        with self.lock:
            self.logs.append(text)
            if len(self.logs) > 4000:
                self.logs = self.logs[-4000:]

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            return {
                "running": self.running(),
                "return_code": self.return_code,
                "logs": self.logs,
            }


STATE = AutomationState()


def merged_settings() -> dict[str, Any]:
    settings = DEFAULTS.copy()
    if SETTINGS_PATH.exists():
        try:
            saved = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
            if isinstance(saved, dict):
                settings.update(
                    {key: value for key, value in saved.items() if key in DEFAULTS}
                )
        except json.JSONDecodeError:
            pass
    return settings


def build_command(settings: dict[str, Any]) -> list[str]:
    values = DEFAULTS.copy()
    values.update({key: settings.get(key, DEFAULTS[key]) for key in DEFAULTS})

    command = [
        sys.executable,
        "-u",
        str(SCRIPT_PATH),
        "--design-url",
        str(values["design_url"]).strip(),
        "--photos-url",
        str(values["photos_url"]).strip(),
        "--image",
        str(values["image"]).strip(),
        "--photos-dir",
        str(values["photos_dir"]).strip(),
        "--output-dir",
        str(values["output_dir"]).strip(),
        "--output-name",
        str(values["output_name"]).strip(),
        "--chrome-exe",
        str(values["chrome_exe"]).strip(),
        "--profile-dir",
        str(values["profile_dir"]).strip(),
        "--debug-port",
        str(values["debug_port"]).strip(),
        "--login-timeout",
        str(values["login_timeout"]).strip(),
        "--editor-timeout",
        str(values["editor_timeout"]).strip(),
        "--upload-timeout",
        str(values["upload_timeout"]).strip(),
        "--bg-remove-timeout",
        str(values["bg_remove_timeout"]).strip(),
        "--download-timeout",
        str(values["download_timeout"]).strip(),
        "--google-download-timeout",
        str(values["google_download_timeout"]).strip(),
        "--fallback-thumbnail-x",
        str(values["fallback_thumbnail_x"]).strip(),
        "--fallback-thumbnail-y",
        str(values["fallback_thumbnail_y"]).strip(),
        "--initial-width",
        str(values["initial_width"]).strip(),
        "--initial-height",
        str(values["initial_height"]).strip(),
        "--initial-x",
        str(values["initial_x"]).strip(),
        "--initial-y",
        str(values["initial_y"]).strip(),
        "--target-width",
        str(values["target_width"]).strip(),
        "--target-x",
        str(values["target_x"]).strip(),
        "--target-y",
        str(values["target_y"]).strip(),
    ]

    max_images = str(values["max_images"]).strip()
    if max_images:
        command.extend(["--max-images", max_images])

    flags = {
        "single_image": "--single-image",
        "skip_google_download": "--skip-google-download",
        "skip_initial_fit": "--skip-initial-fit",
        "keep_open": "--keep-open",
    }
    for key, flag in flags.items():
        if bool(values[key]):
            command.append(flag)

    return command


def read_json_body(handler: SimpleHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get("Content-Length", "0") or "0")
    if length <= 0:
        return {}
    body = handler.rfile.read(length).decode("utf-8")
    data = json.loads(body)
    if not isinstance(data, dict):
        raise ValueError("Expected a JSON object.")
    return data


def reader_thread(process: subprocess.Popen[str]) -> None:
    assert process.stdout is not None
    for line in process.stdout:
        STATE.append_log(line)

    return_code = process.wait()
    STATE.return_code = return_code
    if return_code == 0:
        STATE.append_log("\nAutomation finished successfully.\n")
    elif return_code == 130:
        STATE.append_log("\nAutomation stopped by user.\n")
    else:
        STATE.append_log(f"\nAutomation exited with code {return_code}.\n")


class CanvaWebHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(WEB_DIR), **kwargs)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/":
            self.path = "/index.html"
            return super().do_GET()
        if path == "/api/defaults":
            return self.send_json({"defaults": DEFAULTS, "settings": merged_settings()})
        if path == "/api/status":
            return self.send_json(STATE.snapshot())
        if path == "/api/open-output":
            output_dir = Path(str(merged_settings()["output_dir"])).expanduser()
            output_dir.mkdir(parents=True, exist_ok=True)
            os.startfile(output_dir)
            return self.send_json({"ok": True})
        return super().do_GET()

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        try:
            if path == "/api/settings":
                settings = read_json_body(self)
                clean = DEFAULTS.copy()
                clean.update({key: settings.get(key, DEFAULTS[key]) for key in DEFAULTS})
                SETTINGS_PATH.write_text(
                    json.dumps(clean, indent=2),
                    encoding="utf-8",
                )
                return self.send_json({"ok": True, "settings": clean})

            if path == "/api/start":
                if STATE.running():
                    return self.send_json(
                        {"ok": False, "error": "Automation is already running."},
                        HTTPStatus.CONFLICT,
                    )

                settings = read_json_body(self)
                command = build_command(settings)
                SETTINGS_PATH.write_text(
                    json.dumps({key: settings.get(key, DEFAULTS[key]) for key in DEFAULTS}, indent=2),
                    encoding="utf-8",
                )

                with STATE.lock:
                    STATE.logs = ["Starting Canva automation...\n"]
                    STATE.return_code = None

                process = subprocess.Popen(
                    command,
                    cwd=BASE_DIR,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                )
                STATE.process = process
                threading.Thread(
                    target=reader_thread,
                    args=(process,),
                    daemon=True,
                ).start()
                return self.send_json({"ok": True})

            if path == "/api/stop":
                if STATE.running() and STATE.process is not None:
                    STATE.append_log("\nStopping automation...\n")
                    STATE.process.terminate()
                return self.send_json({"ok": True})
        except Exception as exc:
            return self.send_json(
                {"ok": False, "error": str(exc)},
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )

        self.send_error(HTTPStatus.NOT_FOUND)

    def send_json(
        self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK
    ) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        return


def main() -> int:
    WEB_DIR.mkdir(exist_ok=True)
    server = ThreadingHTTPServer((HOST, PORT), CanvaWebHandler)
    url = f"http://{HOST}:{PORT}"
    print(f"Canva automation web UI: {url}")
    webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
    finally:
        if STATE.running() and STATE.process is not None:
            STATE.process.terminate()
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
