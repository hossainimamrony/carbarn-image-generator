from __future__ import annotations

import argparse
import json
import subprocess
import time
import urllib.request
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent
CHROME_PROFILES_DIR = BASE_DIR / "chrome_profiles"
CHROME_EXE_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
CANVA_LOGIN_URL = "https://www.canva.com/login"
DEFAULT_DEBUG_PORT = 9223
DEFAULT_PROFILE_DIR = CHROME_PROFILES_DIR / "canva_automation_profile"
DEFAULT_SESSION_STATE = CHROME_PROFILES_DIR / "canva_session_state.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Open Canva in an automation browser, wait for manual login, "
            "then save the browser session."
        )
    )
    parser.add_argument(
        "--debug-port",
        type=int,
        default=DEFAULT_DEBUG_PORT,
        help="Chrome remote debugging port to use.",
    )
    parser.add_argument(
        "--profile-dir",
        default=str(DEFAULT_PROFILE_DIR),
        help="Persistent Chrome user data folder for this Canva test.",
    )
    parser.add_argument(
        "--session-state",
        default=str(DEFAULT_SESSION_STATE),
        help="Path where Playwright storage state JSON will be saved.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=900,
        help="Maximum seconds to wait while you complete login manually.",
    )
    parser.add_argument(
        "--keep-open",
        action="store_true",
        help="Leave Chrome open after saving the session.",
    )
    return parser.parse_args()


def require_playwright():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError(
            "Missing dependency: playwright. Install it with: "
            "python -m pip install playwright"
        ) from exc

    return sync_playwright


def debugging_endpoint_ready(port: int) -> bool:
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/json/version", timeout=1
        ) as response:
            return response.status == 200
    except Exception:
        return False


def wait_for_debugging_endpoint(port: int, timeout_seconds: int = 20) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if debugging_endpoint_ready(port):
            return
        time.sleep(0.25)
    raise RuntimeError(f"Chrome did not open remote debugging port {port}.")


def remove_stale_profile_locks(profile_dir: Path) -> None:
    for name in ("lockfile", "SingletonLock", "SingletonCookie", "SingletonSocket"):
        path = profile_dir / name
        try:
            if path.exists() and path.is_file():
                path.unlink()
        except Exception:
            pass


def launch_chrome(port: int, profile_dir: Path) -> subprocess.Popen[Any] | None:
    if debugging_endpoint_ready(port):
        print(f"Reusing Chrome already listening on port {port}.")
        return None

    chrome_path = Path(CHROME_EXE_PATH)
    if not chrome_path.exists():
        raise FileNotFoundError(f"Chrome was not found at: {chrome_path}")

    profile_dir.mkdir(parents=True, exist_ok=True)
    remove_stale_profile_locks(profile_dir)

    command = [
        str(chrome_path),
        f"--user-data-dir={profile_dir}",
        "--profile-directory=Default",
        f"--remote-debugging-port={port}",
        "--no-first-run",
        "--no-default-browser-check",
        "--start-maximized",
        CANVA_LOGIN_URL,
    ]

    print("Launching Chrome for Canva login test...")
    print(f"Profile folder: {profile_dir}")
    process = subprocess.Popen(command)
    wait_for_debugging_endpoint(port)
    return process


def get_page(context: Any) -> Any:
    if context.pages:
        return context.pages[-1]
    return context.new_page()


def looks_logged_in(page: Any) -> bool:
    url = page.url.lower()
    if "canva.com" not in url:
        return False
    if "/login" in url or "/signup" in url:
        return False

    try:
        cookies = page.context.cookies("https://www.canva.com")
    except Exception:
        cookies = []

    canva_cookie_names = {
        cookie.get("name", "").lower()
        for cookie in cookies
        if "canva.com" in cookie.get("domain", "")
    }
    return bool(canva_cookie_names)


def wait_for_manual_login(page: Any, timeout_seconds: int) -> bool:
    print("")
    print("A Chrome window is open at Canva.")
    print("Log in manually there. Complete any MFA, CAPTCHA, or browser checks yourself.")
    print("When Canva finishes loading your account/home page, return here.")
    input("Press Enter after you believe the login is complete...")

    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if looks_logged_in(page):
            return True
        print("Still looks like the login is not complete. Waiting 5 seconds...")
        page.wait_for_timeout(5000)
        answer = input("Press Enter to check again, or type q then Enter to stop: ")
        if answer.strip().lower() == "q":
            return False

    return False


def save_session(context: Any, session_path: Path) -> None:
    session_path.parent.mkdir(parents=True, exist_ok=True)
    context.storage_state(path=str(session_path))

    data = json.loads(session_path.read_text(encoding="utf-8"))
    canva_cookies = [
        cookie
        for cookie in data.get("cookies", [])
        if "canva.com" in cookie.get("domain", "")
    ]
    print(f"Saved session state: {session_path}")
    print(f"Canva cookies saved: {len(canva_cookies)}")


def main() -> int:
    args = parse_args()
    profile_dir = Path(args.profile_dir).expanduser().resolve()
    session_path = Path(args.session_state).expanduser().resolve()

    sync_playwright = require_playwright()
    chrome_process = launch_chrome(args.debug_port, profile_dir)

    with sync_playwright() as playwright:
        browser = playwright.chromium.connect_over_cdp(
            f"http://127.0.0.1:{args.debug_port}"
        )
        context = browser.contexts[0] if browser.contexts else browser.new_context()
        page = get_page(context)

        if "canva.com" not in page.url.lower():
            page.goto(CANVA_LOGIN_URL, wait_until="domcontentloaded")

        logged_in = wait_for_manual_login(page, args.timeout)
        save_session(context, session_path)

        if logged_in:
            print("Result: Canva login appears to be active in this automation browser.")
        else:
            print("Result: session saved, but the script could not confirm Canva login.")

        if not args.keep_open:
            browser.close()
            if chrome_process is not None and chrome_process.poll() is None:
                chrome_process.terminate()

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nStopped by user.")
        raise SystemExit(130)
    except Exception as exc:
        print(exc)
        raise SystemExit(1)
