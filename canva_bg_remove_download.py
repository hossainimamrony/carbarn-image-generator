from __future__ import annotations

import argparse
import re
import subprocess
import time
import urllib.request
import zipfile
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = BASE_DIR / "assets"
CHROME_PROFILES_DIR = BASE_DIR / "chrome_profiles"
CHROME_EXE_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
DEFAULT_DESIGN_URL = (
    "https://www.canva.com/design/DAHLgWFcGFE/"
    "w_OFfQ7ABVOo_qv22LHUnA/edit?ui=eyJGIjp7fX0"
)
DEFAULT_GOOGLE_PHOTOS_URL = (
    "https://photos.google.com/share/"
    "AF1QipPVh9X00UNfaEmtBwhHcW9wGpSpEPX6xSZxhrs4CyE9h2_BKzrCVx3MIfdC_iviEg"
    "?key=eVJrdmhpRTV2Z2Nyd2JObEdhaU5wbkI1UGhSRmt3"
)
DEFAULT_DEBUG_PORT = 9223
DEFAULT_PROFILE_DIR = CHROME_PROFILES_DIR / "canva_automation_profile"
DEFAULT_IMAGE_PATH = BASE_DIR / "mycars.jpg"
DEFAULT_GOOGLE_PHOTOS_DIR = ASSETS_DIR / "google_photos_downloads"
DEFAULT_OUTPUT_DIR = ASSETS_DIR / "canva_download"
DEFAULT_OUTPUT_NAME = "mycar_bg_removed.jpg"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Automate Canva: upload an image, size/position it, run BG Remover, "
            "then download the design as a 100 quality JPG."
        )
    )
    parser.add_argument("--design-url", default=DEFAULT_DESIGN_URL)
    parser.add_argument("--photos-url", default=DEFAULT_GOOGLE_PHOTOS_URL)
    parser.add_argument("--image", default=str(DEFAULT_IMAGE_PATH))
    parser.add_argument("--photos-dir", default=str(DEFAULT_GOOGLE_PHOTOS_DIR))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--output-name", default=DEFAULT_OUTPUT_NAME)
    parser.add_argument("--stock-id", default="")
    parser.add_argument("--debug-port", type=int, default=DEFAULT_DEBUG_PORT)
    parser.add_argument("--profile-dir", default=str(DEFAULT_PROFILE_DIR))
    parser.add_argument("--chrome-exe", default=CHROME_EXE_PATH)
    parser.add_argument(
        "--login-timeout",
        type=int,
        default=900,
        help="Seconds to wait if Canva asks you to log in manually.",
    )
    parser.add_argument(
        "--editor-timeout",
        type=int,
        default=120,
        help="Seconds to wait for the Canva editor to load.",
    )
    parser.add_argument(
        "--upload-timeout",
        type=int,
        default=120,
        help="Maximum seconds to wait for Canva to finish uploading the image.",
    )
    parser.add_argument(
        "--bg-remove-timeout",
        type=int,
        default=240,
        help="Maximum seconds to wait for BG Remover's visible processing UI to settle.",
    )
    parser.add_argument(
        "--download-timeout",
        type=int,
        default=300,
        help="Seconds to wait for Canva's download to start.",
    )
    parser.add_argument(
        "--skip-download-settings",
        action="store_true",
        help=(
            "Use Canva's saved download preferences and click the final "
            "Download button without changing file type or quality."
        ),
    )
    parser.add_argument(
        "--google-download-timeout",
        type=int,
        default=600,
        help="Seconds to wait for Google Photos album download to start.",
    )
    parser.add_argument(
        "--skip-google-download",
        action="store_true",
        help="Use images already in --photos-dir instead of downloading Google Photos.",
    )
    parser.add_argument(
        "--single-image",
        action="store_true",
        help="Process only --image and skip Google Photos batch mode.",
    )
    parser.add_argument(
        "--max-images",
        type=int,
        default=None,
        help="Optional maximum number of downloaded images to process.",
    )
    parser.add_argument(
        "--fallback-thumbnail-x",
        type=int,
        default=150,
        help="Fallback X coordinate for the newest upload thumbnail.",
    )
    parser.add_argument(
        "--fallback-thumbnail-y",
        type=int,
        default=260,
        help="Fallback Y coordinate for the newest upload thumbnail.",
    )
    parser.add_argument("--initial-width", default="3651 px")
    parser.add_argument("--initial-height", default="2738 px")
    parser.add_argument("--initial-x", default="0 px")
    parser.add_argument("--initial-y", default="0 px")
    parser.add_argument("--target-width", default="3000 px")
    parser.add_argument("--target-x", default="500 px")
    parser.add_argument("--target-y", default="500 px")
    parser.add_argument(
        "--skip-initial-fit",
        action="store_true",
        help="Skip the pre-BG-remover full-canvas sizing step.",
    )
    parser.add_argument(
        "--keep-open",
        action="store_true",
        help="Leave Chrome open after the automation finishes.",
    )
    return parser.parse_args()


def require_playwright():
    try:
        from playwright.sync_api import TimeoutError, sync_playwright
    except ImportError as exc:
        raise RuntimeError(
            "Missing dependency: playwright. Install it with: "
            "python -m pip install playwright"
        ) from exc

    return sync_playwright, TimeoutError


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


def launch_chrome(
    port: int, profile_dir: Path, startup_url: str, chrome_exe_path: str = CHROME_EXE_PATH
) -> subprocess.Popen[Any] | None:
    if debugging_endpoint_ready(port):
        print(f"Reusing Chrome already listening on port {port}.")
        return None

    chrome_path = Path(chrome_exe_path)
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
        startup_url,
    ]

    print("Launching Chrome for Canva automation...")
    print(f"Profile folder: {profile_dir}")
    process = subprocess.Popen(command)
    wait_for_debugging_endpoint(port)
    return process


def get_page(context: Any) -> Any:
    if context.pages:
        return context.pages[-1]
    return context.new_page()


def sanitize_filename(name: str) -> str:
    cleaned = re.sub(r'[<>:"/\\\\|?*]+', "_", name).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned or "downloaded_image"


def sanitize_stock_id(stock_id: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", stock_id.strip())
    cleaned = cleaned.strip("._-")
    return cleaned or ""


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path

    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    index = 2
    while True:
        candidate = parent / f"{stem}_{index}{suffix}"
        if not candidate.exists():
            return candidate
        index += 1


def image_files_in_dir(directory: Path) -> list[Path]:
    if not directory.exists():
        return []
    return sorted(
        path
        for path in directory.rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    )


def wait_for_google_photos_album(page: Any, timeout_seconds: int = 90) -> None:
    print("Waiting for Google Photos shared album...")
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        markers = [
            page.get_by_text(re.compile(r"Google Photos", re.I)),
            page.get_by_text(re.compile(r"Shared", re.I)),
            page.locator("[aria-label*='Download' i]"),
            page.locator("img"),
        ]
        if any(safe_is_visible(marker, timeout=500) for marker in markers):
            print("Google Photos album is ready.")
            return
        page.wait_for_timeout(1000)

    raise RuntimeError("Google Photos album did not become ready in time.")


def click_google_photos_download_button(page: Any) -> bool:
    locators = [
        page.get_by_role("button", name=re.compile(r"Download all|Download", re.I)),
        page.get_by_label(re.compile(r"Download all|Download", re.I)),
        page.locator("[aria-label*='Download' i]"),
        page.locator("[title*='Download' i]"),
    ]
    for locator in locators:
        if click_locator(locator, timeout=5000):
            return True

    return False


def click_google_photos_more_download(page: Any) -> bool:
    more_buttons = [
        page.get_by_role("button", name=re.compile(r"More options|More", re.I)),
        page.get_by_label(re.compile(r"More options|More", re.I)),
        page.locator("[aria-label*='More' i]"),
    ]
    for locator in more_buttons:
        if click_locator(locator, timeout=3000):
            return click_by_text(page, "Download all", timeout=5000) or click_by_text(
                page, "Download", timeout=5000
            )

    return False


def download_google_photos_album(
    page: Any, photos_url: str, photos_dir: Path, timeout_seconds: int
) -> list[Path]:
    photos_dir.mkdir(parents=True, exist_ok=True)
    zip_dir = photos_dir / "_album_zips"
    extract_dir = photos_dir / "extracted" / time.strftime("album_%Y%m%d_%H%M%S")
    zip_dir.mkdir(parents=True, exist_ok=True)
    extract_dir.mkdir(parents=True, exist_ok=True)

    print(f"Opening Google Photos album: {photos_url}")
    page.goto(photos_url, wait_until="domcontentloaded", timeout=120_000)
    wait_for_google_photos_album(page)

    download = None
    actions = [
        ("download button", click_google_photos_download_button),
        ("more menu download", click_google_photos_more_download),
        ("Shift+D shortcut", lambda page: (page.keyboard.press("Shift+D") or True)),
    ]
    last_error: Exception | None = None

    for label, action in actions:
        try:
            print(f"Trying Google Photos {label}...")
            with page.expect_download(timeout=timeout_seconds * 1000) as download_info:
                if not action(page):
                    raise RuntimeError(f"Could not trigger {label}.")
            download = download_info.value
            break
        except Exception as exc:
            last_error = exc
            print(f"Google Photos {label} did not start a download.")

    if download is None:
        raise RuntimeError(
            "Could not start Google Photos album download."
        ) from last_error

    suggested_name = sanitize_filename(download.suggested_filename or "google_photos_album.zip")
    downloaded_path = unique_path(zip_dir / suggested_name)
    download.save_as(str(downloaded_path))
    print(f"Google Photos download saved to: {downloaded_path}")

    if downloaded_path.suffix.lower() == ".zip":
        extract_google_photos_zip(downloaded_path, extract_dir)
        images = image_files_in_dir(extract_dir)
    elif downloaded_path.suffix.lower() in IMAGE_EXTENSIONS:
        image_path = unique_path(photos_dir / downloaded_path.name)
        downloaded_path.replace(image_path)
        images = [image_path]
    else:
        raise RuntimeError(f"Downloaded file is not an image or ZIP: {downloaded_path}")

    if not images:
        raise RuntimeError(f"No images found after Google Photos download: {photos_dir}")

    print(f"Found {len(images)} Google Photos image(s).")
    return images


def extract_google_photos_zip(zip_path: Path, extract_dir: Path) -> None:
    print(f"Extracting Google Photos ZIP: {zip_path}")
    with zipfile.ZipFile(zip_path) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue

            source_name = sanitize_filename(Path(info.filename).name)
            if not source_name:
                continue

            target_path = unique_path(extract_dir / source_name)
            with archive.open(info) as source, target_path.open("wb") as target:
                target.write(source.read())


def safe_is_visible(locator: Any, timeout: int = 500) -> bool:
    try:
        locator.first.wait_for(state="visible", timeout=timeout)
        return True
    except Exception:
        return False


def click_locator(locator: Any, timeout: int = 5000) -> bool:
    try:
        target = locator.first
        target.wait_for(state="visible", timeout=timeout)
        target.scroll_into_view_if_needed(timeout=timeout)
        target.click(timeout=timeout)
        return True
    except Exception:
        return False


def click_by_text(page: Any, text: str, timeout: int = 5000) -> bool:
    escaped = re.escape(text)
    locators = [
        page.get_by_role("button", name=re.compile(escaped, re.I)),
        page.get_by_role("menuitem", name=re.compile(escaped, re.I)),
        page.get_by_role("option", name=re.compile(escaped, re.I)),
        page.get_by_text(re.compile(escaped, re.I)),
    ]
    for locator in locators:
        if click_locator(locator, timeout=timeout):
            print(f"Clicked: {text}")
            return True
    return False


def require_click_by_text(page: Any, text: str, timeout: int = 8000) -> None:
    if not click_by_text(page, text, timeout=timeout):
        raise RuntimeError(f"Could not find/click Canva UI text: {text!r}")


def is_login_page(page: Any) -> bool:
    url = page.url.lower()
    return "/login" in url or "/signup" in url or "login" in url


def wait_for_manual_login_if_needed(page: Any, design_url: str, timeout_seconds: int) -> None:
    if not is_login_page(page):
        return

    print("")
    print("Canva is asking for login in the opened Chrome window.")
    print("Log in manually there, then return to this terminal.")
    input("Press Enter after login is complete...")

    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if not is_login_page(page):
            page.goto(design_url, wait_until="domcontentloaded", timeout=120_000)
            return
        page.wait_for_timeout(2000)

    raise RuntimeError("Timed out waiting for manual Canva login.")


def wait_for_editor(page: Any, timeout_seconds: int) -> None:
    print("Waiting for Canva editor...")
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        editor_markers = [
            page.get_by_role("button", name=re.compile(r"^Share$", re.I)),
            page.get_by_text(re.compile(r"\+ Add page", re.I)),
            page.get_by_text(re.compile(r"Uploads", re.I)),
        ]
        if any(safe_is_visible(marker, timeout=800) for marker in editor_markers):
            print("Canva editor is ready.")
            return
        page.wait_for_timeout(1000)

    raise RuntimeError("Canva editor did not become ready in time.")


def open_uploads_panel(page: Any) -> None:
    if click_by_text(page, "Uploads", timeout=4000):
        wait_for_any_visible(
            page,
            [
                page.get_by_text(re.compile(r"Upload files|Upload file|Upload", re.I)),
                page.locator("input[type='file']"),
            ],
            timeout_seconds=20,
            description="Uploads panel",
        )


def wait_for_any_visible(
    page: Any, locators: list[Any], timeout_seconds: int, description: str
) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if any(safe_is_visible(locator, timeout=400) for locator in locators):
            return
        page.wait_for_timeout(500)
    raise RuntimeError(f"Timed out waiting for {description}.")


def upload_media_count(page: Any) -> int:
    return int(
        page.evaluate(
            """
            () => {
                const maxLeft = Math.min(460, window.innerWidth * 0.35);
                return Array.from(document.querySelectorAll('img, video, canvas'))
                    .filter((element) => {
                        const rect = element.getBoundingClientRect();
                        return (
                            rect.width >= 40 &&
                            rect.height >= 40 &&
                            rect.left >= 0 &&
                            rect.left <= maxLeft &&
                            rect.top >= 90 &&
                            rect.bottom <= window.innerHeight - 20
                        );
                    }).length;
            }
            """
        )
    )


def choose_file_for_upload(page: Any, image_path: Path, timeout_error: type[Exception]) -> None:
    upload_button_texts = ("Upload files", "Upload file", "Upload")
    for text in upload_button_texts:
        try:
            with page.expect_file_chooser(timeout=5000) as chooser_info:
                if not click_by_text(page, text, timeout=2500):
                    raise timeout_error(f"No button for {text}")
            chooser_info.value.set_files(str(image_path))
            print(f"Selected image for upload: {image_path}")
            return
        except Exception:
            pass

    file_inputs = page.locator("input[type='file']")
    try:
        file_inputs.last.set_input_files(str(image_path), timeout=7000)
        print(f"Selected image through file input: {image_path}")
        return
    except Exception as exc:
        raise RuntimeError(
            "Could not find Canva's upload file chooser or file input."
        ) from exc


def find_uploaded_thumbnail_by_name(page: Any, image_path: Path) -> Any | None:
    filename = image_path.name
    stem = image_path.stem
    patterns = [filename, stem]

    for pattern in patterns:
        escaped = re.escape(pattern)
        locators = [
            page.get_by_role("button", name=re.compile(escaped, re.I)),
            page.locator(f"img[alt*='{pattern}' i]"),
            page.get_by_text(re.compile(escaped, re.I)),
        ]
        for locator in locators:
            try:
                target = locator.first
                target.wait_for(state="visible", timeout=500)
                return target
            except Exception:
                pass

    return None


def newest_upload_thumbnail(page: Any) -> Any | None:
    thumbnail = page.evaluate_handle(
        """
        () => {
            const maxLeft = Math.min(460, window.innerWidth * 0.35);
            const media = Array.from(document.querySelectorAll('img, video, canvas'));
            const candidates = media
                .map((element) => ({ element, rect: element.getBoundingClientRect() }))
                .filter(({ rect }) => (
                    rect.width >= 40 &&
                    rect.height >= 40 &&
                    rect.left >= 0 &&
                    rect.left <= maxLeft &&
                    rect.top >= 90 &&
                    rect.bottom <= window.innerHeight - 20
                ))
                .sort((a, b) => (a.rect.top - b.rect.top) || (a.rect.left - b.rect.left));

            if (!candidates.length) {
                return null;
            }

            let node = candidates[0].element;
            for (let depth = 0; node && depth < 6; depth += 1) {
                const role = node.getAttribute && node.getAttribute('role');
                if (node.tagName === 'BUTTON' || role === 'button' || node.tabIndex >= 0) {
                    return node;
                }
                node = node.parentElement;
            }
            return candidates[0].element;
        }
        """
    )
    return thumbnail.as_element()


def click_uploaded_image_thumbnail(
    page: Any,
    image_path: Path,
    previous_media_count: int,
    upload_timeout: int,
    fallback_x: int,
    fallback_y: int,
) -> None:
    print("Waiting for Canva to expose the uploaded thumbnail...")
    deadline = time.time() + upload_timeout
    while time.time() < deadline:
        named_thumbnail = find_uploaded_thumbnail_by_name(page, image_path)
        if named_thumbnail is not None:
            named_thumbnail.click(timeout=5000)
            print(f"Clicked uploaded thumbnail: {image_path.name}")
            return

        current_count = upload_media_count(page)
        if current_count > previous_media_count:
            thumbnail = newest_upload_thumbnail(page)
            if thumbnail is not None:
                thumbnail.click(timeout=5000)
                print("Clicked newest uploaded thumbnail after media count changed.")
                return

        page.wait_for_timeout(750)

    print("Could not identify upload thumbnail dynamically, using coordinate fallback.")
    page.mouse.click(fallback_x, fallback_y)


def get_design_center(page: Any) -> tuple[float, float]:
    center = page.evaluate(
        """
        () => {
            const selectors = [
                '[aria-label*="Page 1"]',
                '[aria-label*="page 1"]',
                '[data-testid*="page"]',
                '[data-testid*="canvas"]'
            ];

            for (const selector of selectors) {
                const elements = Array.from(document.querySelectorAll(selector));
                const boxes = elements
                    .map((element) => element.getBoundingClientRect())
                    .filter((rect) => rect.width > 250 && rect.height > 250)
                    .sort((a, b) => (b.width * b.height) - (a.width * a.height));
                if (boxes.length) {
                    const rect = boxes[0];
                    return {
                        x: rect.left + rect.width / 2,
                        y: rect.top + rect.height / 2
                    };
                }
            }

            return {
                x: window.innerWidth / 2,
                y: Math.max(220, window.innerHeight * 0.52)
            };
        }
        """
    )
    return float(center["x"]), float(center["y"])


def wait_for_image_selection(page: Any, timeout_seconds: int = 30) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if image_selection_visible(page, timeout=400):
            print("Uploaded image appears selected.")
            return
        page.wait_for_timeout(500)

    raise RuntimeError("Uploaded image did not appear selected in Canva.")


def image_selection_visible(page: Any, timeout: int = 250) -> bool:
    selection_markers = [
        page.get_by_text(re.compile(r"BG Remover", re.I)),
        page.get_by_text(re.compile(r"Position", re.I)),
        page.get_by_text(re.compile(r"Ask Canva", re.I)),
        page.get_by_role("button", name=re.compile(r"Delete", re.I)),
        page.locator("[aria-label*='Delete' i]"),
    ]
    return any(safe_is_visible(marker, timeout=timeout) for marker in selection_markers)


def ensure_image_selected(page: Any, timeout_seconds: int = 30) -> None:
    if image_selection_visible(page):
        return

    x, y = get_design_center(page)
    page.mouse.click(x, y)
    wait_for_image_selection(page, timeout_seconds=timeout_seconds)


def button_near_label(page: Any, label_text: str) -> Any | None:
    handle = page.evaluate_handle(
        """
        (labelText) => {
            const visible = (element) => {
                const rect = element.getBoundingClientRect();
                const style = window.getComputedStyle(element);
                return (
                    rect.width > 0 &&
                    rect.height > 0 &&
                    style.visibility !== 'hidden' &&
                    style.display !== 'none'
                );
            };

            const labels = Array.from(document.querySelectorAll('body *'))
                .filter((element) => {
                    const text = (element.innerText || element.textContent || '').trim();
                    return text === labelText && visible(element);
                });

            for (const label of labels) {
                const labelRect = label.getBoundingClientRect();
                const candidates = Array.from(document.querySelectorAll('button, [role="button"]'))
                    .map((element) => ({ element, rect: element.getBoundingClientRect() }))
                    .filter(({ element, rect }) => (
                        visible(element) &&
                        rect.width >= 20 &&
                        rect.height >= 20 &&
                        rect.left >= labelRect.left - 20 &&
                        rect.left <= labelRect.right + 120 &&
                        rect.top >= labelRect.bottom - 10 &&
                        rect.top <= labelRect.bottom + 90
                    ))
                    .sort((a, b) => {
                        const aDistance = Math.abs(a.rect.left - labelRect.left);
                        const bDistance = Math.abs(b.rect.left - labelRect.left);
                        return aDistance - bDistance;
                    });

                if (candidates.length) {
                    return candidates[0].element;
                }
            }
            return null;
        }
        """,
        label_text,
    )
    return handle.as_element()


def toggle_ratio_lock_if_available(page: Any, reason: str = "Ratio lock toggle requested.") -> None:
    ratio_button = button_near_label(page, "Ratio")
    if ratio_button is None:
        print("Ratio lock button not found; retrying size inputs without toggling it.")
        return

    ratio_button.click(timeout=5000)
    print(reason)


def ratio_lock_looks_locked(page: Any) -> bool | None:
    ratio_button = button_near_label(page, "Ratio")
    if ratio_button is None:
        return None

    state = ratio_button.evaluate(
        """
        (element) => {
            const attrs = [
                element.getAttribute('aria-label') || '',
                element.getAttribute('title') || '',
                element.getAttribute('aria-pressed') || '',
                element.getAttribute('aria-checked') || '',
                element.innerText || '',
                element.textContent || '',
            ].join(' ').toLowerCase();
            return attrs;
        }
        """
    )
    text = str(state)
    if "unlock" in text or "true" in text:
        return True
    if "lock" in text or "false" in text:
        return False
    return None


def ensure_ratio_locked_before_width(page: Any) -> None:
    state = ratio_lock_looks_locked(page)
    if state is True:
        print("Ratio is already locked before setting final width.")
        return
    if state is False:
        toggle_ratio_lock_if_available(page, "Ratio locked before setting final width.")
        return
    toggle_ratio_lock_if_available(
        page,
        "Ratio lock state is unclear; clicked Ratio lock before setting final width.",
    )


def position_panel_visible(page: Any) -> bool:
    markers = [
        page.get_by_text(re.compile(r"^Advanced$", re.I)),
        page.get_by_text(re.compile(r"^Width$", re.I)),
        page.get_by_text(re.compile(r"^Height$", re.I)),
        page.get_by_text(re.compile(r"^X$", re.I)),
        page.get_by_text(re.compile(r"^Y$", re.I)),
    ]
    return sum(1 for marker in markers if safe_is_visible(marker, timeout=250)) >= 3


def open_position_panel(page: Any) -> None:
    if not position_panel_visible(page):
        require_click_by_text(page, "Position", timeout=10_000)

    wait_for_any_visible(
        page,
        [
            page.get_by_text(re.compile(r"Arrange", re.I)),
            page.get_by_text(re.compile(r"Advanced", re.I)),
            page.get_by_text(re.compile(r"Width", re.I)),
        ],
        timeout_seconds=20,
        description="Canva Position panel",
    )


def recover_position_panel(page: Any) -> None:
    ensure_image_selected(page)
    open_position_panel(page)
    page.wait_for_timeout(300)


def fill_labeled_value(page: Any, label_text: str, value: str) -> None:
    field = position_panel_input(page, label_text)
    if field is None:
        print(f"Could not find {label_text}; reopening Canva Position panel.")
        recover_position_panel(page)
        field = position_panel_input(page, label_text)
    if field is None:
        raise RuntimeError(f"Could not find Canva Position input for {label_text!r}.")

    for attempt in range(3):
        field.click(timeout=5000)
        page.keyboard.press("Control+A")
        page.keyboard.type(value)
        page.keyboard.press("Enter")
        page.wait_for_timeout(250)

        actual = field.evaluate(
            """
            (element) => {
                const raw = element.value ?? element.innerText ?? element.textContent ?? '';
                return String(raw).trim();
            }
            """
        )
        tolerance = 0.1 if label_text in {"X", "Y", "Rotate"} else 1.0
        if field_value_matches(str(actual), value, tolerance=tolerance):
            print(f"{label_text} set to {actual}.")
            return

        print(
            f"{label_text} still reads {actual!r} after attempt {attempt + 1}; retrying..."
        )

    raise RuntimeError(f"Could not set Canva Position field {label_text!r} to {value!r}.")


def read_labeled_value(page: Any, label_text: str) -> str:
    field = position_panel_input(page, label_text)
    if field is None:
        print(f"Could not read {label_text}; reopening Canva Position panel.")
        recover_position_panel(page)
        field = position_panel_input(page, label_text)
    if field is None:
        raise RuntimeError(f"Could not read Canva Position input for {label_text!r}.")

    return str(
        field.evaluate(
            """
            (element) => {
                const raw = element.value ?? element.innerText ?? element.textContent ?? '';
                return String(raw).trim();
            }
            """
        )
    )


def verify_position_values(
    page: Any,
    width: str,
    height: str | None,
    x_value: str,
    y_value: str,
    label_prefix: str = "Position",
) -> bool:
    expected = {
        "Width": (width, 1.0),
        "X": (x_value, 0.1),
        "Y": (y_value, 0.1),
    }
    if height is not None:
        expected["Height"] = (height, 1.0)

    actual_values: dict[str, str] = {}
    if height is None:
        actual_values["Height"] = read_labeled_value(page, "Height")

    for label, (expected_value, tolerance) in expected.items():
        actual = read_labeled_value(page, label)
        actual_values[label] = actual
        if not field_value_matches(actual, expected_value, tolerance=tolerance):
            print(
                f"{label} verification failed: expected {expected_value!r}, got {actual!r}."
            )
            return False

    print(
        f"{label_prefix} values verified: "
        f"Width={actual_values['Width']}, "
        f"Height={actual_values.get('Height', 'unchanged')}, "
        f"X={actual_values['X']}, "
        f"Y={actual_values['Y']}."
    )
    return True


def field_value_matches(actual: str, expected: str, tolerance: float = 1.0) -> bool:
    actual_number = first_number(actual)
    expected_number = first_number(expected)
    if actual_number is None or expected_number is None:
        return actual.strip() == expected.strip()
    return abs(actual_number - expected_number) <= tolerance


def first_number(text: str) -> float | None:
    match = re.search(r"-?\d+(?:,\d{3})*(?:\.\d+)?|-?\d+(?:\.\d+)?", text)
    if not match:
        return None
    return float(match.group(0).replace(",", ""))


def proportional_height(
    before_width: float | None, before_height: float | None, target_width: str
) -> float | None:
    target_number = first_number(target_width)
    if (
        before_width is None
        or before_height is None
        or target_number is None
        or before_width <= 0
    ):
        return None
    return before_height * target_number / before_width


def height_matches_ratio(actual_height: float | None, expected_height: float | None) -> bool:
    if actual_height is None or expected_height is None:
        return False
    return abs(actual_height - expected_height) <= 2.0


def position_panel_input(page: Any, label_text: str) -> Any | None:
    handle = page.evaluate_handle(
        """
        (labelText) => {
            const visible = (element) => {
                const rect = element.getBoundingClientRect();
                const style = window.getComputedStyle(element);
                return (
                    rect.width > 0 &&
                    rect.height > 0 &&
                    style.visibility !== 'hidden' &&
                    style.display !== 'none'
                );
            };

            const textOf = (element) => (
                element.innerText || element.textContent || ''
            ).trim();

            const advancedLabels = Array.from(document.querySelectorAll('body *'))
                .filter((element) => {
                    const rect = element.getBoundingClientRect();
                    return visible(element) && textOf(element) === 'Advanced' && rect.left < 460;
                })
                .sort((a, b) => {
                    const aRect = a.getBoundingClientRect();
                    const bRect = b.getBoundingClientRect();
                    return (aRect.top - bRect.top) || (aRect.left - bRect.left);
                });

            const inputSelectors = 'input, [role="spinbutton"], [contenteditable="true"]';

            for (const advancedLabel of advancedLabels) {
                const advancedRect = advancedLabel.getBoundingClientRect();
                let panel = advancedLabel.parentElement;
                while (panel && panel !== document.body) {
                    const panelRect = panel.getBoundingClientRect();
                    const visibleInputs = Array.from(panel.querySelectorAll(inputSelectors))
                        .filter((element) => {
                            const rect = element.getBoundingClientRect();
                            return (
                                visible(element) &&
                                rect.left >= panelRect.left - 2 &&
                                rect.right <= panelRect.right + 2 &&
                                rect.top > advancedRect.bottom &&
                                rect.top < advancedRect.bottom + 230
                            );
                        });

                    if (visibleInputs.length >= 4 && panelRect.left < 460) {
                        break;
                    }
                    panel = panel.parentElement;
                }
                panel = panel || document.body;

                const panelRect = panel.getBoundingClientRect();
                const controls = Array.from(panel.querySelectorAll(inputSelectors))
                    .map((element) => ({ element, rect: element.getBoundingClientRect() }))
                    .filter(({ element, rect }) => (
                        visible(element) &&
                        rect.width >= 50 &&
                        rect.height >= 25 &&
                        rect.left >= panelRect.left - 2 &&
                        rect.right <= panelRect.right + 2 &&
                        rect.top > advancedRect.bottom &&
                        rect.top < advancedRect.bottom + 230
                    ))
                    .sort((a, b) => (a.rect.top - b.rect.top) || (a.rect.left - b.rect.left));

                const rows = [];
                for (const control of controls) {
                    const existingRow = rows.find((row) => Math.abs(row.top - control.rect.top) < 20);
                    if (existingRow) {
                        existingRow.items.push(control);
                        existingRow.top = Math.min(existingRow.top, control.rect.top);
                    } else {
                        rows.push({ top: control.rect.top, items: [control] });
                    }
                }

                rows.sort((a, b) => a.top - b.top);
                for (const row of rows) {
                    row.items.sort((a, b) => a.rect.left - b.rect.left);
                }

                const grid = {
                    Width: rows[0]?.items[0]?.element,
                    Height: rows[0]?.items[1]?.element,
                    X: rows[1]?.items[0]?.element,
                    Y: rows[1]?.items[1]?.element,
                    Rotate: rows[1]?.items[2]?.element,
                };

                if (grid[labelText]) {
                    return grid[labelText];
                }
            }

            return null;
        }
        """,
        label_text,
    )
    return handle.as_element()


def set_image_size_and_position(
    page: Any,
    width: str,
    height: str | None,
    x_value: str,
    y_value: str,
    label_prefix: str = "Position",
    lock_ratio_for_width: bool = False,
) -> None:
    ensure_image_selected(page)

    open_position_panel(page)

    for attempt in range(3):
        try:
            recover_position_panel(page)
            before_width = first_number(read_labeled_value(page, "Width"))
            before_height = first_number(read_labeled_value(page, "Height"))
            expected_ratio_height = proportional_height(before_width, before_height, width)
            if lock_ratio_for_width and height is None:
                print("Locking Ratio before setting final Width.")
                ensure_ratio_locked_before_width(page)
                recover_position_panel(page)

            fill_labeled_value(page, "Width", width)
            after_width = first_number(read_labeled_value(page, "Width"))
            after_height = first_number(read_labeled_value(page, "Height"))

            if (
                lock_ratio_for_width
                and height is None
                and after_width is not None
                and after_height is not None
                and expected_ratio_height is not None
                and not height_matches_ratio(after_height, expected_ratio_height)
            ):
                toggle_ratio_lock_if_available(
                    page,
                    "Height did not follow Width after Ratio lock; toggled Ratio lock and retrying Width.",
                )
                recover_position_panel(page)
                fill_labeled_value(page, "Width", width)
                after_height = first_number(read_labeled_value(page, "Height"))
                if not height_matches_ratio(after_height, expected_ratio_height):
                    raise RuntimeError(
                        "Ratio lock did not keep Height proportional after setting Width."
                    )
                print(f"Ratio lock verified: Height adjusted to {after_height:g} px.")

            if height is not None:
                fill_labeled_value(page, "Height", height)
            fill_labeled_value(page, "X", x_value)
            fill_labeled_value(page, "Y", y_value)
            page.wait_for_timeout(500)

            if verify_position_values(
                page, width, height, x_value, y_value, label_prefix=label_prefix
            ):
                return

            print(f"Position values drifted after attempt {attempt + 1}; retrying...")
            if attempt == 0:
                toggle_ratio_lock_if_available(
                    page, "Toggled Ratio lock because Width/Height did not verify."
                )
                recover_position_panel(page)
        except Exception as exc:
            print(f"Position attempt {attempt + 1} failed: {exc}")
            if attempt == 2:
                raise
            page.wait_for_timeout(1000)

    raise RuntimeError(
        "Could not keep Canva image at the requested Width/Height/X/Y values."
    )


def canva_processing_status(page: Any) -> str | None:
    status = page.evaluate(
        """
        () => {
            const visible = (element) => {
                const rect = element.getBoundingClientRect();
                const style = window.getComputedStyle(element);
                return (
                    rect.width > 0 &&
                    rect.height > 0 &&
                    style.visibility !== 'hidden' &&
                    style.display !== 'none'
                );
            };

            const busyElement = Array.from(document.querySelectorAll(
                '[role="progressbar"], [aria-busy="true"], [data-loading="true"]'
            )).find(visible);
            if (busyElement) {
                return 'visible progress/loading indicator';
            }

            const busyText = [
                'removing background',
                'processing image',
                'processing your image',
                'applying changes',
                'preparing image'
            ];

            const busyTextElement = Array.from(document.querySelectorAll('body *')).find((element) => {
                if (!visible(element)) {
                    return false;
                }
                const text = (element.innerText || element.textContent || '')
                    .trim()
                    .toLowerCase();
                return text && busyText.some((needle) => text.includes(needle));
            });

            if (busyTextElement) {
                return (busyTextElement.innerText || busyTextElement.textContent || '')
                    .trim()
                    .slice(0, 80);
            }

            return null;
        }
        """
    )
    return str(status) if status else None


def canva_has_selected_image_toolbar(page: Any) -> bool:
    return any(
        safe_is_visible(locator, timeout=250)
        for locator in [
            page.get_by_text(re.compile(r"BG Remover", re.I)),
            page.get_by_text(re.compile(r"Ask Canva", re.I)),
            page.get_by_text(re.compile(r"Position", re.I)),
        ]
    )


def wait_for_canva_to_settle(
    page: Any,
    timeout_seconds: int,
    description: str,
    quiet_ms: int = 2500,
    minimum_seconds: float = 2.0,
) -> None:
    print(f"Waiting dynamically for {description} to finish...")
    deadline = time.time() + timeout_seconds
    started = time.time()
    last_busy_or_unselected = time.time()
    last_status_log = 0.0

    while time.time() < deadline:
        status = canva_processing_status(page)
        toolbar_ready = canva_has_selected_image_toolbar(page)
        blocking_status = status is not None and (
            not toolbar_ready or status != "visible progress/loading indicator"
        )

        if blocking_status or not toolbar_ready:
            last_busy_or_unselected = time.time()
            if time.time() - last_status_log >= 10:
                if status:
                    print(f"Still waiting for {description}: {status}")
                else:
                    print(f"Still waiting for {description}: image toolbar not ready")
                last_status_log = time.time()

        quiet_for_ms = (time.time() - last_busy_or_unselected) * 1000
        ran_minimum = (time.time() - started) >= minimum_seconds
        if ran_minimum and not blocking_status and toolbar_ready and quiet_for_ms >= quiet_ms:
            print(f"{description} looks settled.")
            return

        page.wait_for_timeout(500)

    print(
        f"{description} did not expose a clean settled state before "
        f"{timeout_seconds}s; continuing because Canva can keep background UI busy."
    )


def run_bg_remover(page: Any, timeout_seconds: int) -> None:
    ensure_image_selected(page)
    require_click_by_text(page, "BG Remover", timeout=12_000)
    print("BG Remover clicked.")
    wait_for_canva_to_settle(
        page,
        timeout_seconds=timeout_seconds,
        description="BG Remover",
        quiet_ms=3000,
        minimum_seconds=3.0,
    )


def open_download_panel(page: Any) -> None:
    require_click_by_text(page, "Share", timeout=10_000)
    wait_for_any_visible(
        page,
        [
            page.get_by_text(re.compile(r"Share design", re.I)),
            page.get_by_role("button", name=re.compile(r"^Download$", re.I)),
        ],
        timeout_seconds=20,
        description="Canva Share panel",
    )
    require_click_by_text(page, "Download", timeout=10_000)
    wait_for_any_visible(
        page,
        [
            page.get_by_text(re.compile(r"File type", re.I)),
            page.get_by_text(re.compile(r"Quality", re.I)),
            page.get_by_role("button", name=re.compile(r"^Download$", re.I)),
        ],
        timeout_seconds=20,
        description="Canva Download panel",
    )


def ensure_jpg_file_type(page: Any) -> None:
    if safe_is_visible(page.get_by_text("JPG", exact=True), timeout=400):
        print("File type already shows JPG.")
        return

    file_type_candidates = [
        page.get_by_role("button", name=re.compile(r"File type|PNG|PDF|JPG", re.I)),
        page.get_by_role("combobox", name=re.compile(r"File type", re.I)),
        page.get_by_text(re.compile(r"^(PNG|PDF Standard|PDF Print|JPG)$", re.I)),
    ]
    for locator in file_type_candidates:
        if click_locator(locator, timeout=4000):
            wait_for_any_visible(
                page,
                [page.get_by_text("JPG", exact=True)],
                timeout_seconds=4,
                description="JPG option",
            )
            break

    if not click_by_text(page, "JPG", timeout=2500):
        raise RuntimeError("Could not select JPG in Canva's download file type menu.")
    print("File type set to JPG.")


def input_near_label(page: Any, label_text: str) -> Any | None:
    handle = page.evaluate_handle(
        """
        (labelText) => {
            const visible = (element) => {
                const rect = element.getBoundingClientRect();
                const style = window.getComputedStyle(element);
                return (
                    rect.width > 0 &&
                    rect.height > 0 &&
                    style.visibility !== 'hidden' &&
                    style.display !== 'none'
                );
            };

            const labels = Array.from(document.querySelectorAll('body *'))
                .filter((element) => {
                    const text = (element.innerText || element.textContent || '').trim();
                    return text === labelText && visible(element);
                });

            for (const label of labels) {
                const labelRect = label.getBoundingClientRect();
                const labelY = labelRect.top + labelRect.height / 2;
                const candidates = Array.from(
                    document.querySelectorAll('input, [role="spinbutton"], [contenteditable="true"]')
                )
                    .map((element) => ({ element, rect: element.getBoundingClientRect() }))
                    .filter(({ element, rect }) => (
                        visible(element) &&
                        rect.width >= 25 &&
                        rect.height >= 15 &&
                        rect.left > labelRect.left &&
                        rect.top < labelRect.bottom + 90 &&
                        rect.bottom > labelRect.top - 90
                    ))
                    .sort((a, b) => {
                        const aY = a.rect.top + a.rect.height / 2;
                        const bY = b.rect.top + b.rect.height / 2;
                        const vertical = Math.abs(aY - labelY) - Math.abs(bY - labelY);
                        if (vertical !== 0) {
                            return vertical;
                        }
                        return b.rect.left - a.rect.left;
                    });

                if (candidates.length) {
                    return candidates[0].element;
                }
            }

            return null;
        }
        """,
        label_text,
    )
    return handle.as_element()


def set_quality_to_100(page: Any) -> None:
    quality_input = input_near_label(page, "Quality")
    if quality_input is not None:
        current = str(
            quality_input.evaluate(
                """
                (element) => {
                    const raw = element.value ?? element.innerText ?? element.textContent ?? '';
                    return String(raw).trim();
                }
                """
            )
        )
        if field_value_matches(current, "100", tolerance=0.1):
            print("Quality already set to 100.")
            return

        quality_input.click(timeout=5000)
        page.keyboard.press("Control+A")
        page.keyboard.type("100")
        page.keyboard.press("Enter")
        print("Quality set to 100.")
        return

    spinbuttons = page.get_by_role("spinbutton")
    count = spinbuttons.count()
    if count:
        spinbuttons.nth(min(1, count - 1)).fill("100", timeout=5000)
        print("Quality set to 100 using spinbutton fallback.")
        return

    raise RuntimeError("Could not find Canva's JPG quality input.")


def final_download_button_handle(page: Any) -> Any | None:
    handle = page.evaluate_handle(
        """
        () => {
            const visible = (element) => {
                const rect = element.getBoundingClientRect();
                const style = window.getComputedStyle(element);
                return (
                    rect.width > 0 &&
                    rect.height > 0 &&
                    style.visibility !== 'hidden' &&
                    style.display !== 'none' &&
                    style.pointerEvents !== 'none'
                );
            };

            const textOf = (element) => (
                element.innerText ||
                element.textContent ||
                element.getAttribute('aria-label') ||
                element.getAttribute('title') ||
                ''
            ).replace(/\\s+/g, ' ').trim();

            const buttons = Array.from(document.querySelectorAll('button, [role="button"]'))
                .map((element) => ({ element, rect: element.getBoundingClientRect(), text: textOf(element) }))
                .filter(({ element, rect, text }) => {
                    const disabled = element.hasAttribute('disabled') ||
                        (element.getAttribute('aria-disabled') || '').toLowerCase() === 'true';
                    return (
                        !disabled &&
                        visible(element) &&
                        /^Download$/i.test(text) &&
                        rect.width >= 70 &&
                        rect.height >= 30
                    );
                })
                .sort((a, b) => {
                    const bottom = b.rect.bottom - a.rect.bottom;
                    if (Math.abs(bottom) > 8) return bottom;
                    return b.rect.right - a.rect.right;
                });

            return buttons[0]?.element || null;
        }
        """
    )
    return handle.as_element()


def click_final_download_button(page: Any) -> bool:
    element = final_download_button_handle(page)
    if element is not None:
        try:
            element.scroll_into_view_if_needed(timeout=2000)
            element.click(timeout=2500, force=True)
            print("Clicked final Canva Download button.")
            return True
        except Exception:
            pass

        try:
            element.evaluate("(button) => button.click()")
            print("Clicked final Canva Download button with JS fallback.")
            return True
        except Exception:
            pass

        try:
            box = element.bounding_box()
            if box:
                page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
                print("Clicked final Canva Download button with coordinate fallback.")
                return True
        except Exception:
            pass

    fallback_locators = [
        page.get_by_role("button", name=re.compile(r"^Download$", re.I)).last,
        page.locator("[aria-label='Download']").last,
        page.locator("[aria-label*='Download' i]").last,
    ]
    for locator in fallback_locators:
        try:
            locator.wait_for(state="visible", timeout=1500)
            locator.scroll_into_view_if_needed(timeout=1500)
            locator.click(timeout=1500, force=True)
            print("Clicked final Canva Download button with locator fallback.")
            return True
        except Exception:
            pass

    try:
        page.keyboard.press("Enter")
        print("Pressed Enter as final Canva Download fallback.")
        return True
    except Exception:
        return False


def click_final_download(page: Any, output_path: Path, timeout_seconds: int) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    attempt_timeout = min(max(timeout_seconds // 3, 30), 90)
    deadline = time.time() + timeout_seconds
    last_error: Exception | None = None
    attempt = 1

    while time.time() < deadline:
        remaining = max(5, int(deadline - time.time()))
        current_timeout = min(attempt_timeout, remaining)
        print(
            f"Starting Canva download attempt {attempt} "
            f"(waiting up to {current_timeout}s)..."
        )
        try:
            with page.expect_download(timeout=current_timeout * 1000) as download_info:
                if not click_final_download_button(page):
                    raise RuntimeError("Could not click the final Canva Download button.")

            download = download_info.value
            download.save_as(str(output_path))
            print(f"Downloaded file saved to: {output_path}")
            return
        except Exception as exc:
            last_error = exc
            print(
                f"Canva download did not start on attempt {attempt}; "
                "retrying final Download button..."
            )
            attempt += 1
            page.wait_for_timeout(1000)

    raise RuntimeError("Canva download did not start in time.") from last_error


def close_share_or_download_panels(page: Any, timeout_seconds: float = 2.0) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        panel_markers = [
            page.get_by_text(re.compile(r"Share design", re.I)),
            page.get_by_text(re.compile(r"File type", re.I)),
            page.get_by_text(re.compile(r"Quality", re.I)),
            page.get_by_text(re.compile(r"PDF Standard|PDF Print|SVG|MP4 Video", re.I)),
        ]
        if not any(safe_is_visible(marker, timeout=100) for marker in panel_markers):
            return
        page.keyboard.press("Escape")
        page.wait_for_timeout(150)


def selection_toolbar_visible(page: Any) -> bool:
    markers = [
        page.get_by_text(re.compile(r"BG Remover", re.I)),
        page.get_by_text(re.compile(r"Ask Canva", re.I)),
        page.get_by_role("button", name=re.compile(r"Delete", re.I)),
    ]
    return any(safe_is_visible(marker, timeout=250) for marker in markers)


def wait_for_selection_to_clear(page: Any, timeout_seconds: float = 20.0) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if not selection_toolbar_visible(page):
            return True
        page.wait_for_timeout(500)
    return False


def click_toolbar_delete(page: Any) -> bool:
    delete_buttons = [
        page.get_by_role("button", name=re.compile(r"^Delete$", re.I)),
        page.locator("[aria-label*='Delete' i]"),
        page.locator("[title*='Delete' i]"),
    ]
    for locator in delete_buttons:
        if click_locator(locator, timeout=2000):
            print("Clicked selected image toolbar Delete.")
            return True
    return False


def right_click_delete_selected_image(page: Any) -> bool:
    x, y = get_design_center(page)
    page.mouse.click(x, y)
    if not safe_is_visible(page.get_by_text(re.compile(r"Ask Canva|BG Remover", re.I)), timeout=1500):
        return False

    page.mouse.click(x, y, button="right")
    if click_by_text(page, "Delete", timeout=4000):
        print("Clicked Delete from image context menu.")
        return True
    page.keyboard.press("Escape")
    return False


def cleanup_canvas_image(page: Any, timeout_seconds: float = 12.0) -> None:
    print("Cleaning Canva page for the next image...")
    close_share_or_download_panels(page)

    ensure_image_selected(page, timeout_seconds=4)

    page.keyboard.press("Delete")
    if wait_for_selection_to_clear(page, timeout_seconds=2.5):
        print("Canvas image deleted.")
        return

    delete_attempts = [
        ("toolbar Delete", click_toolbar_delete),
        ("right-click Delete", right_click_delete_selected_image),
    ]
    for label, action in delete_attempts:
        if action(page) and wait_for_selection_to_clear(page, timeout_seconds=4):
            print("Canvas image deleted.")
            return
        print(f"{label} did not clear the selected image; trying next delete method.")

    ensure_image_selected(page, timeout_seconds=3)
    page.keyboard.press("Delete")
    if wait_for_selection_to_clear(page, timeout_seconds=timeout_seconds):
        print("Canvas image deleted.")
        return

    raise RuntimeError(
        "Image delete did not complete in time. The image may still be selected."
    )


def output_path_for_image(
    image_path: Path,
    output_dir: Path,
    output_name: str,
    image_count: int,
    index: int,
    stock_id: str,
) -> Path:
    stock_slug = sanitize_stock_id(stock_id)
    if stock_slug:
        return unique_path(output_dir / f"{stock_slug}_{index:03d}_canva_bg_removed.jpg")
    if image_count == 1 and output_name:
        return output_dir / output_name
    return unique_path(output_dir / f"{image_path.stem}_bg_removed.jpg")


def process_image_in_canva(
    page: Any,
    image_path: Path,
    output_path: Path,
    args: argparse.Namespace,
    timeout_error: type[Exception],
) -> None:
    open_uploads_panel(page)
    previous_media_count = upload_media_count(page)
    choose_file_for_upload(page, image_path, timeout_error)
    click_uploaded_image_thumbnail(
        page,
        image_path,
        previous_media_count,
        args.upload_timeout,
        args.fallback_thumbnail_x,
        args.fallback_thumbnail_y,
    )
    wait_for_image_selection(page)

    if not args.skip_initial_fit:
        set_image_size_and_position(
            page,
            args.initial_width,
            args.initial_height,
            args.initial_x,
            args.initial_y,
            label_prefix="Initial fit",
        )
    run_bg_remover(page, args.bg_remove_timeout)
    set_image_size_and_position(
        page,
        args.target_width,
        None,
        args.target_x,
        args.target_y,
        label_prefix="Final placement",
        lock_ratio_for_width=True,
    )
    open_download_panel(page)
    if args.skip_download_settings:
        print("Using saved Canva download preferences; clicking Download immediately.")
    else:
        ensure_jpg_file_type(page)
        set_quality_to_100(page)
    click_final_download(page, output_path, args.download_timeout)
    cleanup_canvas_image(page)


def main() -> int:
    args = parse_args()
    image_path = Path(args.image).expanduser().resolve()
    photos_dir = Path(args.photos_dir).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    profile_dir = Path(args.profile_dir).expanduser().resolve()

    if args.single_image and not image_path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")

    sync_playwright, timeout_error = require_playwright()
    startup_url = (
        args.design_url
        if args.single_image or args.skip_google_download
        else args.photos_url
    )
    chrome_process = launch_chrome(
        args.debug_port, profile_dir, startup_url, args.chrome_exe
    )

    with sync_playwright() as playwright:
        browser = playwright.chromium.connect_over_cdp(
            f"http://127.0.0.1:{args.debug_port}"
        )
        context = browser.contexts[0] if browser.contexts else browser.new_context()
        page = get_page(context)

        try:
            if args.single_image:
                images = [image_path]
            elif args.skip_google_download:
                images = image_files_in_dir(photos_dir)
                if not images:
                    raise RuntimeError(f"No images found in: {photos_dir}")
                print(f"Using {len(images)} existing image(s) from: {photos_dir}")
            else:
                images = download_google_photos_album(
                    page,
                    args.photos_url,
                    photos_dir,
                    args.google_download_timeout,
                )

            if args.max_images is not None:
                images = images[: args.max_images]

            if not images:
                raise RuntimeError("No images to process.")

            if page.url != args.design_url:
                page.goto(args.design_url, wait_until="domcontentloaded", timeout=120_000)

            wait_for_manual_login_if_needed(page, args.design_url, args.login_timeout)
            wait_for_editor(page, args.editor_timeout)

            for index, current_image in enumerate(images, start=1):
                current_output = output_path_for_image(
                    current_image,
                    output_dir,
                    args.output_name,
                    len(images),
                    index,
                    args.stock_id,
                )
                print("")
                print(
                    f"Processing image {index}/{len(images)}: "
                    f"{current_image.name} -> {current_output.name}"
                )
                process_image_in_canva(
                    page,
                    current_image,
                    current_output,
                    args,
                    timeout_error,
                )

            print("")
            print(f"Finished processing {len(images)} image(s).")
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
