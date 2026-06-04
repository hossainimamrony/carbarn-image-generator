from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import traceback
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
from perfect_car_image import (
    DEFAULT_CHROME_PROFILE_DIRECTORY as PERFECT_DEFAULT_CHROME_PROFILE_DIRECTORY,
    DEFAULT_CHROME_USER_DATA_DIR as PERFECT_DEFAULT_CHROME_USER_DATA_DIR,
    DEFAULT_DEBUG_PORT as PERFECT_DEFAULT_DEBUG_PORT,
    DEFAULT_INPUT_DIR as PERFECT_DEFAULT_INPUT_DIR,
    DEFAULT_OUTPUT_DIR as PERFECT_DEFAULT_OUTPUT_DIR,
    PERFECT_CAR_PROMPT,
)


HOST = "127.0.0.1"
PORT = 8765
WEB_DIR = BASE_DIR / "web"
BG_SCRIPT_PATH = BASE_DIR / "canva_bg_remove_download.py"
PERFECT_SCRIPT_PATH = BASE_DIR / "perfect_car_image.py"
SETTINGS_PATH = BASE_DIR / "canva_web_settings.json"
FLOW_PROMPT_PATH = BASE_DIR / "flow_prompt.txt"
FLOW_CONTROL_PATH = BASE_DIR / "flow_control.json"


def load_flow_prompt() -> str:
    try:
        if FLOW_PROMPT_PATH.exists():
            prompt = FLOW_PROMPT_PATH.read_text(encoding="utf-8").strip()
            if prompt:
                return prompt
    except OSError:
        pass
    return PERFECT_CAR_PROMPT


def save_flow_prompt(prompt: str) -> None:
    FLOW_PROMPT_PATH.write_text(prompt.strip() or PERFECT_CAR_PROMPT, encoding="utf-8")


def set_flow_paused(paused: bool) -> None:
    FLOW_CONTROL_PATH.write_text(
        json.dumps({"paused": paused}, indent=2),
        encoding="utf-8",
    )


def flow_paused() -> bool:
    try:
        if not FLOW_CONTROL_PATH.exists():
            return False
        data = json.loads(FLOW_CONTROL_PATH.read_text(encoding="utf-8"))
        return bool(data.get("paused"))
    except (OSError, json.JSONDecodeError, AttributeError):
        return False


DEFAULTS: dict[str, Any] = {
    "stock_id": "",
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
    "download_google_photos": False,
    "skip_google_download": True,
    "skip_initial_fit": False,
    "keep_open": False,
    "perfect_input_dir": str(PERFECT_DEFAULT_INPUT_DIR),
    "perfect_output_dir": str(PERFECT_DEFAULT_OUTPUT_DIR),
    "perfect_project_url": "",
    "perfect_debug_port": str(PERFECT_DEFAULT_DEBUG_PORT),
    "perfect_chrome_user_data_dir": str(PERFECT_DEFAULT_CHROME_USER_DATA_DIR),
    "perfect_chrome_profile_directory": PERFECT_DEFAULT_CHROME_PROFILE_DIRECTORY,
    "perfect_start_at": "1",
    "perfect_limit": "",
    "perfect_delay": "2.0",
    "perfect_batch_size": "8",
    "perfect_upload_timeout": "120",
    "perfect_download_timeout": "420",
    "perfect_use_current_page": False,
    "perfect_keep_browser_open": False,
    "perfect_dry_run": False,
    "flow_prompt": PERFECT_CAR_PROMPT,
}


def sanitize_stock_id(stock_id: str) -> str:
    cleaned = "".join(char if char.isalnum() or char in "._-" else "_" for char in stock_id.strip())
    cleaned = cleaned.strip("._-")
    return cleaned


def effective_canva_output_dir(settings: dict[str, Any]) -> Path:
    base = Path(str(settings.get("output_dir", DEFAULT_OUTPUT_DIR))).expanduser()
    stock_slug = sanitize_stock_id(str(settings.get("stock_id", "")))
    if stock_slug:
        return base / stock_slug / "canva"
    return base


def effective_flow_input_dir(settings: dict[str, Any]) -> Path:
    override = settings.get("_flow_input_dir")
    if override:
        return Path(str(override)).expanduser()

    base = Path(str(settings.get("perfect_input_dir", PERFECT_DEFAULT_INPUT_DIR))).expanduser()
    stock_slug = sanitize_stock_id(str(settings.get("stock_id", "")))
    if stock_slug:
        return base / stock_slug / "canva"
    return base


def effective_flow_output_dir(settings: dict[str, Any]) -> Path:
    base = Path(str(settings.get("perfect_output_dir", PERFECT_DEFAULT_OUTPUT_DIR))).expanduser()
    stock_slug = sanitize_stock_id(str(settings.get("stock_id", "")))
    if stock_slug:
        return base / stock_slug / "flow"
    return base


class AutomationState:
    def __init__(self) -> None:
        self.process: subprocess.Popen[str] | None = None
        self.sequence_running = False
        self.logs: list[str] = []
        self.lock = threading.Lock()
        self.return_code: int | None = None

    def running(self) -> bool:
        process_running = self.process is not None and self.process.poll() is None
        return self.sequence_running or process_running

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
                "flow_paused": flow_paused(),
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
    settings["flow_prompt"] = load_flow_prompt()
    return settings


def build_bg_command(settings: dict[str, Any]) -> list[str]:
    values = DEFAULTS.copy()
    values.update(settings)
    stock_id = sanitize_stock_id(str(values.get("stock_id", "")))

    command = [
        sys.executable,
        "-u",
        str(BG_SCRIPT_PATH),
        "--design-url",
        str(values["design_url"]).strip(),
        "--photos-url",
        str(values["photos_url"]).strip(),
        "--image",
        str(values["image"]).strip(),
        "--photos-dir",
        str(values["photos_dir"]).strip(),
        "--output-dir",
        str(effective_canva_output_dir(values)),
        "--output-name",
        str(values["output_name"]).strip(),
        "--stock-id",
        stock_id,
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

    if not bool(values["single_image"]) and not bool(values["download_google_photos"]):
        command.append("--skip-google-download")

    flags = {
        "single_image": "--single-image",
        "skip_initial_fit": "--skip-initial-fit",
        "keep_open": "--keep-open",
    }
    for key, flag in flags.items():
        if bool(values[key]):
            command.append(flag)

    return command


def build_perfect_command(settings: dict[str, Any]) -> list[str]:
    values = DEFAULTS.copy()
    values.update(settings)
    stock_id = sanitize_stock_id(str(values.get("stock_id", "")))

    command = [
        sys.executable,
        "-u",
        str(PERFECT_SCRIPT_PATH),
        "--input-dir",
        str(effective_flow_input_dir(values)),
        "--output-dir",
        str(effective_flow_output_dir(values)),
        "--stock-id",
        stock_id,
        "--debug-port",
        str(values["perfect_debug_port"]).strip(),
        "--chrome-user-data-dir",
        str(values["perfect_chrome_user_data_dir"]).strip(),
        "--chrome-profile-directory",
        str(values["perfect_chrome_profile_directory"]).strip(),
        "--start-at",
        str(values["perfect_start_at"]).strip(),
        "--delay",
        str(values["perfect_delay"]).strip(),
        "--batch-size",
        str(values["perfect_batch_size"]).strip(),
        "--upload-timeout",
        str(values["perfect_upload_timeout"]).strip(),
        "--download-timeout",
        str(values["perfect_download_timeout"]).strip(),
        "--prompt-file",
        str(FLOW_PROMPT_PATH),
        "--control-file",
        str(FLOW_CONTROL_PATH),
        "--yes",
    ]

    project_url = str(values["perfect_project_url"]).strip()
    if project_url:
        command.extend(["--project-url", project_url])

    limit = str(values["perfect_limit"]).strip()
    if limit:
        command.extend(["--limit", limit])

    flags = {
        "perfect_use_current_page": "--use-current-page",
        "perfect_keep_browser_open": "--keep-browser-open",
        "perfect_dry_run": "--dry-run",
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


def run_command(label: str, command: list[str]) -> int:
    STATE.append_log(f"\n===== {label} =====\n")
    STATE.append_log("Command:\n")
    STATE.append_log(" ".join(f'"{part}"' if " " in part else part for part in command))
    STATE.append_log("\n\n")
    try:
        process = subprocess.Popen(
            command,
            cwd=BASE_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
    except Exception:
        STATE.append_log("Could not start process:\n")
        STATE.append_log(traceback.format_exc())
        return 1
    STATE.process = process

    assert process.stdout is not None
    for line in process.stdout:
        STATE.append_log(line)

    return process.wait()


def run_sequence(commands: list[tuple[str, list[str]]]) -> None:
    STATE.sequence_running = True
    STATE.return_code = None
    try:
        for label, command in commands:
            return_code = run_command(label, command)
            STATE.return_code = return_code
            if return_code != 0:
                STATE.append_log(f"\n{label} exited with code {return_code}.\n")
                return
        STATE.append_log("\nAutomation finished successfully.\n")
    except Exception:
        STATE.return_code = 1
        STATE.append_log("\nWeb server command runner crashed:\n")
        STATE.append_log(traceback.format_exc())
    finally:
        STATE.sequence_running = False
        STATE.process = None


def start_sequence(commands: list[tuple[str, list[str]]], first_log: str) -> None:
    with STATE.lock:
        STATE.logs = [first_log]
        STATE.return_code = None
        STATE.sequence_running = True

    thread = threading.Thread(target=run_sequence, args=(commands,), daemon=True)
    thread.start()


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
            settings = merged_settings()
            query = urlparse(self.path).query
            target = "perfect" if "target=perfect" in query else "canva"
            output_dir = (
                effective_flow_output_dir(settings)
                if target == "perfect"
                else effective_canva_output_dir(settings)
            )
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
                save_flow_prompt(str(clean.get("flow_prompt", PERFECT_CAR_PROMPT)))
                SETTINGS_PATH.write_text(
                    json.dumps(clean, indent=2),
                    encoding="utf-8",
                )
                return self.send_json({"ok": True, "settings": clean})

            if path == "/api/flow-prompt":
                settings = read_json_body(self)
                save_flow_prompt(str(settings.get("flow_prompt", PERFECT_CAR_PROMPT)))
                return self.send_json({"ok": True})

            if path == "/api/flow-pause":
                set_flow_paused(True)
                STATE.append_log("\nFlow pause requested.\n")
                return self.send_json({"ok": True})

            if path == "/api/flow-resume":
                set_flow_paused(False)
                STATE.append_log("\nFlow resume requested.\n")
                return self.send_json({"ok": True})

            if path in {"/api/start-bg", "/api/start-perfect", "/api/start-pipeline"}:
                if STATE.running():
                    return self.send_json(
                        {"ok": False, "error": "Automation is already running."},
                        HTTPStatus.CONFLICT,
                    )

                settings = read_json_body(self)
                clean_settings = {
                    key: settings.get(key, DEFAULTS[key]) for key in DEFAULTS
                }
                save_flow_prompt(str(clean_settings.get("flow_prompt", PERFECT_CAR_PROMPT)))
                SETTINGS_PATH.write_text(
                    json.dumps(clean_settings, indent=2),
                    encoding="utf-8",
                )
                set_flow_paused(False)

                if path == "/api/start-bg":
                    commands = [("Canva", build_bg_command(clean_settings))]
                    first_log = "Starting Canva automation...\n"
                elif path == "/api/start-perfect":
                    commands = [("Flow", build_perfect_command(clean_settings))]
                    first_log = "Starting Flow automation...\n"
                else:
                    clean_settings["_flow_input_dir"] = str(
                        effective_canva_output_dir(clean_settings)
                    )
                    commands = [
                        ("Canva", build_bg_command(clean_settings)),
                        ("Flow", build_perfect_command(clean_settings)),
                    ]
                    first_log = "Starting full pipeline: Canva then Flow...\n"

                start_sequence(commands, first_log)
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
