from __future__ import annotations

import argparse
from pathlib import Path

from canva_bg_remove_download import (
    CHROME_EXE_PATH,
    DEFAULT_DEBUG_PORT,
    DEFAULT_GOOGLE_PHOTOS_DIR,
    DEFAULT_GOOGLE_PHOTOS_URL,
    DEFAULT_PROFILE_DIR,
    download_google_photos_album,
    get_page,
    launch_chrome,
    require_playwright,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download a Google Photos shared album into a local folder."
    )
    parser.add_argument("--photos-url", default=DEFAULT_GOOGLE_PHOTOS_URL)
    parser.add_argument("--photos-dir", default=str(DEFAULT_GOOGLE_PHOTOS_DIR))
    parser.add_argument("--chrome-exe", default=CHROME_EXE_PATH)
    parser.add_argument("--profile-dir", default=str(DEFAULT_PROFILE_DIR))
    parser.add_argument("--debug-port", type=int, default=DEFAULT_DEBUG_PORT)
    parser.add_argument("--google-download-timeout", type=int, default=600)
    parser.add_argument("--keep-open", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    photos_dir = Path(args.photos_dir).expanduser().resolve()
    profile_dir = Path(args.profile_dir).expanduser().resolve()

    sync_playwright, _timeout_error = require_playwright()
    chrome_process = launch_chrome(
        args.debug_port,
        profile_dir,
        args.photos_url,
        args.chrome_exe,
    )

    with sync_playwright() as playwright:
        browser = playwright.chromium.connect_over_cdp(
            f"http://127.0.0.1:{args.debug_port}"
        )
        context = browser.contexts[0] if browser.contexts else browser.new_context()
        page = get_page(context)

        try:
            images = download_google_photos_album(
                page,
                args.photos_url,
                photos_dir,
                args.google_download_timeout,
            )
            print("")
            print(f"Downloaded {len(images)} image(s) to: {photos_dir}")
        finally:
            if not args.keep_open:
                try:
                    browser.close()
                except Exception:
                    pass
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
