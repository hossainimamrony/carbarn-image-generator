from __future__ import annotations

import argparse
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = BASE_DIR / "assets"
CHROME_PROFILES_DIR = BASE_DIR / "chrome_profiles"
CHROME_EXE_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
PREFERRED_AUTOMATION_PROFILE_DIR = CHROME_PROFILES_DIR / "chrome_automation_profile"
LEGACY_AUTOMATION_PROFILE_DIR = BASE_DIR / "chrome_automation_profile"
AUTOMATION_PROFILE_DIR = (
    PREFERRED_AUTOMATION_PROFILE_DIR
    if PREFERRED_AUTOMATION_PROFILE_DIR.exists() or not LEGACY_AUTOMATION_PROFILE_DIR.exists()
    else LEGACY_AUTOMATION_PROFILE_DIR
)
DEFAULT_CHROME_USER_DATA_DIR = AUTOMATION_PROFILE_DIR
DEFAULT_CHROME_PROFILE_DIRECTORY = "Default"
FLOW_HOME_URL = "https://labs.google/fx/tools/flow"
DEFAULT_INPUT_DIR = ASSETS_DIR / "canva_download"
DEFAULT_OUTPUT_DIR = ASSETS_DIR / "perfect_car_images"
DEFAULT_DEBUG_PORT = 9222
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
PLACEHOLDER_IMAGE = "/fx/pinhole/flower-placeholder.webp"

PERFECT_CAR_PROMPT = """Use the uploaded image as the exact original base photo. This is a photo-editing task only, not a new image generation task.

The original image is the source of truth. Keep the same studio, same background, same floor, same wall, same ceiling, same lights, same camera angle, same framing, same crop, same vehicle position, same vehicle size, and same vehicle perspective.

CRITICAL BACKGROUND LOCK:
The studio background must remain exactly unchanged.
Do not regenerate, replace, redesign, clean, blur, brighten, darken, extend, crop, resize, or modify the background in any way.
Do not change the wall, floor, ceiling, studio curve, floor texture, lighting spots, room shape, or existing studio shadows.
Only edit the vehicle itself, the visible license plate area, and the soft contact shadow directly beneath the vehicle.

CRITICAL VEHICLE STRUCTURE LOCK:
Do not change the vehicle’s shape, size, angle, position, proportions, body structure, roofline, bumper shape, grille shape, window shape, wheel position, wheel alignment, tyres, mirrors, lights, handles, badges, panel gaps, body lines, or trim.
Do not rotate, shift, stretch, bend, resize, recompose, crop, or distort the vehicle.
Do not create a new front view, rear view, or different angle.
Do not invent missing body parts.
If an edit cannot be done without changing the vehicle structure, skip that edit and keep the original structure untouched.

MAIN TASK:
Professionally clean the vehicle and remove ALL unwanted reflections from the vehicle surfaces while keeping the vehicle realistic and natural.

REFLECTION CLEANUP — HIGHEST PRIORITY:
Remove all visible unwanted environmental reflections from the vehicle only.

This includes reflections visible on:
- bonnet / hood
- front fenders
- front doors
- sliding door
- rear quarter panels
- rear door / tailgate / trunk area
- front bumper
- rear bumper
- black plastic trims
- side mirrors
- windshield
- front side glass
- sliding door glass
- rear side glass
- rear glass

Remove reflected objects such as:
- ceiling reflections
- ceiling lights
- strip lights
- wall reflections
- shutter or warehouse reflections
- roof beam reflections
- person / human reflections
- camera reflections
- tripod reflections
- equipment reflections
- reflections of other vehicles
- studio clutter reflections
- any other visible reflected object or reflected structure

IMPORTANT:
Do not leave visible warehouse beams, roof lines, wall shapes, ceiling lines, or studio objects mirrored in the windows or paint.
Do not leave strong streaks, bands, lines, or patches of reflection on the car body or glass.
The goal is a clean dealership-style vehicle photo with the reflections removed from the vehicle surfaces only.

BACKGROUND PRESERVATION:
Do not remove or alter the actual studio environment itself.
Do not modify the actual background wall, floor, ceiling, or lights.
Only remove their reflections from the vehicle surface.

PAINT AND BODY RULES:
Keep the original paint color exactly the same.
Do not change the vehicle color, brightness, saturation, contrast, or tone.
Keep the paint finish glossy and realistic.
Do not make the paint matte, chalky, flat, plastic, fake, or over-smoothed.
Preserve natural clearcoat shine and realistic soft highlights, but remove all reflected objects and reflected lines.
Preserve real body lines, panel curves, panel gaps, edges, badges, handles, mirrors, lights, wheels, tyres, and trim details.
The vehicle must look like the same real car, only cleaner and professionally presented.

GLASS RULES:
Keep the original window tint exactly the same.
Remove all visible unwanted reflections from the glass surfaces.
Make the side windows, windshield, and rear glass look clean and realistic without reflected warehouse structure, light strips, people, or equipment.
Do not make the glass overly black, overly transparent, foggy, cloudy, fake, or artificial.
Do not change the dashboard, seats, steering wheel, or visible interior details unless necessary to remove a reflected person or reflected object.
Glass must remain natural and realistic, with the same tint level as the original image.

PLASTIC TRIM RULES:
Keep black plastic trims, bumpers, mirrors, grille areas, rubber seals, and textured parts natural.
Do not make matte plastic glossy.
Do not make textured plastic smooth.
Remove reflected objects and harsh reflected light streaks from plastic surfaces while preserving the real texture and natural finish.

GROUND SHADOW RULE:
Add or refine only a soft natural contact shadow directly beneath the vehicle.
The shadow must match the original studio lighting and perspective.
The vehicle must look naturally grounded, not floating.
Do not change the surrounding floor texture, floor tone, or background.

CARBARN DEALERSHIP PLATE RULE:
Add a CARBARN dealership number plate whenever the front or rear plate mounting area is visible in the original image.

A visible plate mounting area includes:
- front plate holder
- rear plate holder
- blank plate recess
- visible screw-hole mounting area
- blank rectangular plate space
- partially visible front plate area in a front three-quarter angle
- partially visible rear plate area in a rear three-quarter angle

Only skip the plate when the image is a true side-profile and no front or rear plate mounting area is visible at all.

Do not shift, rotate, crop, stretch, distort, or redesign the vehicle to make space for a plate.
Do not invent a fake plate holder in a place where no plate area exists.
Do not place the plate on the side body, side door, window, tyre, floor, or wall.
Keep the plate realistic and properly attached to the visible plate area.

When adding the plate:
- Text: CARBARN
- All caps
- Font: Manrope Bold or closest clean bold sans-serif
- Text color: #4073EA
- Plate background: solid white
- Text centered horizontally and vertically
- Correct perspective matching the vehicle angle
- Correct scale
- Realistic lighting
- Slight contact shadow
- Must look physically attached

FINAL OUTPUT REQUIREMENTS:
Output one final edited image only.
The final result must look like the same original photo, not a new generated scene.
The background must remain unchanged.
The vehicle must keep the exact same structure, angle, size, position, color, glass tint, and proportions.
All unwanted reflections must be removed from the vehicle surfaces and glass.
The vehicle should look professionally cleaned with controlled gloss, realistic trim texture, realistic glass, realistic CARBARN plate where the plate area is visible, and a soft natural ground shadow.
No CGI look, no illustration style, no artificial smoothing, no distorted details, no broken body parts, no changed studio, and no leftover visible environmental reflections on the vehicle."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Upload car images to Google Flow and generate polished final edits."
    )
    parser.add_argument("--input-dir", default=str(DEFAULT_INPUT_DIR))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument(
        "--project-url",
        default=None,
        help="Open this existing Flow project URL instead of creating a new project.",
    )
    parser.add_argument(
        "--use-current-page",
        action="store_true",
        help="Use the current tab in the debug Chrome session without navigating.",
    )
    parser.add_argument(
        "--debug-port",
        type=int,
        default=DEFAULT_DEBUG_PORT,
        help="Chrome remote debugging port.",
    )
    parser.add_argument(
        "--chrome-user-data-dir",
        default=str(DEFAULT_CHROME_USER_DATA_DIR),
        help="Chrome User Data folder to launch.",
    )
    parser.add_argument(
        "--chrome-profile-directory",
        default=DEFAULT_CHROME_PROFILE_DIRECTORY,
        help='Chrome profile folder name, for example "Default" or "Profile 1".',
    )
    parser.add_argument("--start-at", type=int, default=1)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--delay", type=float, default=2.0)
    parser.add_argument(
        "--batch-size",
        type=int,
        default=8,
        help="Submit this many image prompts before waiting for generated outputs.",
    )
    parser.add_argument("--upload-timeout", type=int, default=120)
    parser.add_argument("--download-timeout", type=int, default=420)
    parser.add_argument(
        "--keep-browser-open",
        action="store_true",
        help="Do not close Chrome after the run.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Start without the final confirmation prompt.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List selected images and exit without opening Flow.",
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
            f"http://127.0.0.1:{port}/json/version", timeout=2
        ) as response:
            return response.status == 200
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def wait_for_debugging_endpoint(port: int, timeout_seconds: int = 20) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if debugging_endpoint_ready(port):
            return
        time.sleep(0.5)
    raise RuntimeError(f"Timed out waiting for Chrome debugging port {port}.")


def uses_local_automation_profile(user_data_dir: Path) -> bool:
    try:
        profile_dir = user_data_dir.resolve()
    except OSError:
        return False

    local_dirs = (PREFERRED_AUTOMATION_PROFILE_DIR, LEGACY_AUTOMATION_PROFILE_DIR)
    for local_dir in local_dirs:
        try:
            if profile_dir == local_dir.resolve():
                return True
        except OSError:
            continue
    return False


def clear_crash_restore_flags(user_data_dir: Path, profile_directory: str) -> None:
    pref_paths = [
        user_data_dir / profile_directory / "Preferences",
        user_data_dir / "Local State",
    ]
    for path in pref_paths:
        if not path.exists():
            continue
        try:
            text = path.read_text(encoding="utf-8")
            text = text.replace('"exit_type":"Crashed"', '"exit_type":"Normal"')
            text = text.replace('"exited_cleanly":false', '"exited_cleanly":true')
            path.write_text(text, encoding="utf-8")
        except Exception:
            pass


def remove_stale_profile_locks(user_data_dir: Path) -> None:
    lock_paths = [
        user_data_dir / "lockfile",
        user_data_dir / "SingletonLock",
        user_data_dir / "SingletonCookie",
        user_data_dir / "SingletonSocket",
    ]
    for path in lock_paths:
        try:
            if path.exists() and path.is_file():
                path.unlink()
        except Exception:
            pass


def build_chrome_command(
    port: int, user_data_dir: Path, profile_directory: str, startup_url: str
) -> list[str]:
    return [
        CHROME_EXE_PATH,
        f"--user-data-dir={user_data_dir}",
        f"--profile-directory={profile_directory}",
        f"--remote-debugging-port={port}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-blink-features=AutomationControlled",
        "--disable-infobars",
        "--start-maximized",
        startup_url,
    ]


def launch_chrome_if_needed(
    port: int, user_data_dir: Path, profile_directory: str, startup_url: str
) -> subprocess.Popen[Any] | None:
    if debugging_endpoint_ready(port):
        print(f"Reusing Chrome already listening on port {port}.")
        return None

    if not Path(CHROME_EXE_PATH).exists():
        raise FileNotFoundError(f"Chrome was not found at: {CHROME_EXE_PATH}")

    print("Launching Chrome with remote debugging enabled...")
    print(f"Using Chrome user data dir: {user_data_dir}")
    print(f"Using Chrome profile directory: {profile_directory}")
    print(f"Opening startup URL: {startup_url}")
    process = subprocess.Popen(
        build_chrome_command(port, user_data_dir, profile_directory, startup_url)
    )
    try:
        wait_for_debugging_endpoint(port)
    except RuntimeError as exc:
        raise RuntimeError(
            "Chrome did not open the remote debugging port. If Chrome is already "
            "running with this same automation profile, close that Chrome window "
            "first and run the script again."
        ) from exc
    return process


def install_stealth_scripts(context: Any) -> None:
    context.add_init_script(
        """
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined,
        });

        window.chrome = window.chrome || { runtime: {} };

        Object.defineProperty(navigator, 'languages', {
            get: () => ['en-US', 'en'],
        });

        Object.defineProperty(navigator, 'plugins', {
            get: () => [1, 2, 3, 4, 5],
        });
        """
    )


def connect_context(playwright: Any, port: int) -> tuple[Any, Any]:
    browser = playwright.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
    context = browser.contexts[0] if browser.contexts else browser.new_context()
    install_stealth_scripts(context)
    return browser, context


def get_page(context: Any) -> Any:
    if context.pages:
        return context.pages[-1]
    return context.new_page()


def wait_through_google_sign_in(page: Any, timeout_seconds: int = 600) -> None:
    if "accounts.google.com" not in page.url:
        return

    print(
        "Google sign-in is open in the automation Chrome profile. "
        "Please finish signing in there; this script will wait."
    )
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if "accounts.google.com" not in page.url:
            page.wait_for_timeout(2000)
            return
        page.wait_for_timeout(1000)

    raise RuntimeError("Timed out waiting for Google sign-in to finish.")


def ensure_not_signed_out(page: Any) -> None:
    if "accounts.google.com" in page.url:
        raise RuntimeError(
            "Flow redirected to Google sign-in. Sign in inside the Chrome automation "
            "window first, then run this script again."
        )


def get_new_project_button(page: Any, timeout_ms: int = 2000) -> Any:
    selectors = [
        'button:has-text("New project")',
        '[role="button"]:has-text("New project")',
        'text=New project',
    ]
    for selector in selectors:
        locator = page.locator(selector).first
        try:
            locator.wait_for(state="visible", timeout=timeout_ms)
            return locator
        except Exception:
            continue
    raise RuntimeError("Could not find the Flow New project button.")


def get_prompt_editor(page: Any) -> Any:
    selectors = [
        'div[data-slate-editor="true"][contenteditable="true"]',
        '[contenteditable="true"][role="textbox"]',
        '[contenteditable="true"]',
    ]
    for selector in selectors:
        locator = page.locator(selector).first
        try:
            locator.wait_for(state="visible", timeout=2000)
            return locator
        except Exception:
            continue
    raise RuntimeError("Could not find the Flow prompt editor.")


def wait_for_project_workspace(page: Any, timeout_seconds: int = 60) -> str:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        wait_through_google_sign_in(page)
        ensure_not_signed_out(page)
        if "/project/" in page.url:
            try:
                get_prompt_editor(page)
                page.wait_for_timeout(1000)
                return page.url
            except Exception:
                pass
        page.wait_for_timeout(500)
    raise RuntimeError("Flow did not finish opening the project workspace.")


def open_flow_home(page: Any) -> None:
    print(f"Opening Flow home: {FLOW_HOME_URL}")
    page.goto(FLOW_HOME_URL, wait_until="domcontentloaded", timeout=60000)
    wait_through_google_sign_in(page)
    ensure_not_signed_out(page)
    get_new_project_button(page, timeout_ms=60000)
    page.wait_for_timeout(1000)


def create_new_project(page: Any) -> str:
    print("Creating a fresh Flow project...")
    button = get_new_project_button(page, timeout_ms=60000)
    button.scroll_into_view_if_needed()
    button.click(force=True)
    project_url = wait_for_project_workspace(page)
    print(f"Created Flow project: {project_url}")
    return project_url


def open_existing_project(page: Any, project_url: str) -> str:
    print(f"Opening existing Flow project: {project_url}")
    page.goto(project_url, wait_until="domcontentloaded", timeout=60000)
    wait_through_google_sign_in(page)
    ensure_not_signed_out(page)
    return wait_for_project_workspace(page)


def prepare_flow_page(page: Any, args: argparse.Namespace) -> str:
    page.bring_to_front()

    if args.use_current_page:
        print("Using current browser tab.")
        ensure_not_signed_out(page)
        return wait_for_project_workspace(page)

    if args.project_url:
        return open_existing_project(page, args.project_url)

    open_flow_home(page)
    return create_new_project(page)


def focus_prompt_editor(page: Any) -> Any:
    editor = get_prompt_editor(page)
    editor.scroll_into_view_if_needed()
    editor.click(force=True)
    return editor


def get_prompt_text(page: Any) -> str:
    editor = get_prompt_editor(page)
    return editor.evaluate(
        """
        (el) => (el.innerText || el.textContent || '').replace(/\\u200b/g, '').trim()
        """
    )


def get_create_button(page: Any) -> Any:
    selectors = [
        'button[aria-label*="Create"]',
        'button[aria-label*="create"]',
        'button:has-text("Create")',
        'button:has-text("arrow_forward")',
        'button:has(i:has-text("arrow_forward"))',
        'button:has(.google-symbols:has-text("arrow_forward"))',
        'button:has([class*="google-symbols"]:has-text("arrow_forward"))',
    ]
    for selector in selectors:
        locator = page.locator(selector).first
        try:
            locator.wait_for(state="visible", timeout=2000)
            return locator
        except Exception:
            continue
    raise RuntimeError("Could not find the Flow create/send button.")


def create_button_is_enabled(page: Any) -> bool:
    try:
        button = get_create_button(page)
        disabled_attr = button.get_attribute("disabled")
        aria_disabled = button.get_attribute("aria-disabled")
        return disabled_attr is None and aria_disabled != "true"
    except Exception:
        return False


def media_locator(page: Any) -> Any:
    return page.locator(
        '[data-testid="virtuoso-scroller"] img[src]:not([src*="flower-placeholder"]), '
        '[data-testid="virtuoso-scroller"] video'
    )


def get_media_source(element: Any) -> str:
    return element.evaluate(
        """
        (el) => {
            if (el.tagName === 'VIDEO') {
                return el.currentSrc || el.src || '';
            }
            return el.currentSrc || el.src || '';
        }
        """
    )


def get_media_entries(page: Any) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    locator = media_locator(page)
    total = locator.count()

    for index in range(total):
        element = locator.nth(index)
        try:
            src = get_media_source(element)
            if src and PLACEHOLDER_IMAGE not in src:
                entries.append({"element": element, "src": src})
        except Exception:
            continue

    return entries


def image_files_in_dir(directory: Path) -> list[Path]:
    if not directory.exists():
        return []
    return sorted(
        path
        for path in directory.rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    )


def slice_items(items: list[Path], start_at: int, limit: int | None) -> list[Path]:
    sliced = items[max(start_at - 1, 0) :]
    if limit is not None:
        sliced = sliced[: max(limit, 0)]
    return sliced


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path

    index = 2
    while True:
        candidate = path.with_name(f"{path.stem}_{index}{path.suffix}")
        if not candidate.exists():
            return candidate
        index += 1


def output_base_for_image(output_dir: Path, image_path: Path) -> Path:
    return unique_path(output_dir / f"{image_path.stem}_perfect")


def safe_is_visible(locator: Any, timeout: int = 500) -> bool:
    try:
        locator.first.wait_for(state="visible", timeout=timeout)
        return True
    except Exception:
        return False


def click_locator(locator: Any, timeout: int = 5000, force: bool = False) -> bool:
    try:
        target = locator.first
        target.wait_for(state="visible", timeout=timeout)
        target.scroll_into_view_if_needed(timeout=timeout)
        target.click(timeout=timeout, force=force)
        return True
    except Exception:
        return False


def wait_for_upload_to_attach(page: Any, previous_attachment_count: int, timeout_seconds: int) -> None:
    print("Waiting for selected image to attach to the composer...")
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if input_attachment_count(page) > previous_attachment_count:
            print("Selected image is attached to the composer.")
            return
        if create_button_is_enabled(page):
            print("Create button is enabled after upload.")
            return
        page.wait_for_timeout(750)

    raise RuntimeError("Timed out waiting for Flow image upload to attach.")


def close_asset_picker(page: Any) -> None:
    if not asset_picker_visible(page):
        return

    for _ in range(6):
        try:
            page.keyboard.press("Escape")
        except Exception:
            pass
        page.wait_for_timeout(500)
        if not asset_picker_visible(page):
            print("Closed asset picker.")
            return

    try:
        focus_prompt_editor(page)
        page.mouse.click(20, 20)
    except Exception:
        pass


def input_attachment_count(page: Any) -> int:
    return int(
        page.evaluate(
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
                const editor = document.querySelector('[data-slate-editor="true"][contenteditable="true"], [contenteditable="true"]');
                let root = editor;
                while (root && root !== document.body) {
                    const hasAgent = Array.from(root.querySelectorAll('button, [role="button"]'))
                        .some((button) => (button.innerText || button.textContent || '').trim().toLowerCase() === 'agent');
                    const hasCreateArrow = Array.from(root.querySelectorAll('i, .google-symbols, span'))
                        .some((node) => (node.textContent || '').trim().toLowerCase() === 'arrow_forward');
                    if (hasAgent && hasCreateArrow) break;
                    root = root.parentElement;
                }
                root = root && root !== document.body ? root : editor?.parentElement || document.body;
                const media = Array.from(root.querySelectorAll('img, video, canvas'));
                return media.filter((element) => {
                    const rect = element.getBoundingClientRect();
                    return visible(element) && rect.width >= 24 && rect.height >= 24;
                }).length;
            }
            """
        )
    )


def clear_prompt_attachments(page: Any) -> None:
    for _ in range(5):
        if input_attachment_count(page) == 0:
            return

        button = page.evaluate_handle(
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
                const editor = document.querySelector('[data-slate-editor="true"][contenteditable="true"], [contenteditable="true"]');
                let root = editor;
                while (root && root !== document.body) {
                    const hasAgent = Array.from(root.querySelectorAll('button, [role="button"]'))
                        .some((button) => (button.innerText || button.textContent || '').trim().toLowerCase() === 'agent');
                    const hasCreateArrow = Array.from(root.querySelectorAll('i, .google-symbols, span'))
                        .some((node) => (node.textContent || '').trim().toLowerCase() === 'arrow_forward');
                    if (hasAgent && hasCreateArrow) break;
                    root = root.parentElement;
                }
                if (!root || root === document.body) return null;
                return Array.from(root.querySelectorAll('button, [role="button"]'))
                    .find((element) => {
                        if (!visible(element)) return false;
                        const text = (element.innerText || element.textContent || '')
                            .replace(/\\s+/g, ' ')
                            .trim()
                            .toLowerCase();
                        return (
                            text.includes('clear prompt') ||
                            text === 'close' ||
                            text === 'cancel' ||
                            text.includes('close') ||
                            text.includes('cancel')
                        );
                    }) || null;
            }
            """
        )
        element = button.as_element()
        if element is None:
            print("Could not clear existing composer image; continuing.")
            return

        element.click(timeout=3000, force=True)
        page.wait_for_timeout(500)


def asset_picker_visible(page: Any) -> bool:
    markers = [
        page.locator("#add-menu-input"),
        page.locator('input[aria-label="Search assets"]'),
        page.get_by_text(re.compile(r"Search assets", re.I)),
        page.get_by_text(re.compile(r"Add to Prompt", re.I)),
    ]
    return any(safe_is_visible(marker, timeout=250) for marker in markers)


def get_asset_search_input(page: Any, timeout: int = 8000) -> Any:
    search_inputs = [
        page.locator("#add-menu-input"),
        page.locator('input[aria-label="Search assets"]'),
        page.locator('input[placeholder="Search assets"]'),
        page.get_by_placeholder(re.compile(r"Search assets", re.I)),
    ]
    for locator in search_inputs:
        try:
            target = locator.first
            target.wait_for(state="visible", timeout=timeout)
            return target
        except Exception:
            continue
    raise RuntimeError("Could not find Flow Search assets input.")


def upload_menu_visible(page: Any) -> bool:
    markers = [
        page.get_by_role("menuitem", name=re.compile(r"Upload media", re.I)),
        page.locator('[role="menuitem"]:has-text("Upload media")'),
        page.get_by_text(re.compile(r"Upload media", re.I)),
    ]
    return any(safe_is_visible(marker, timeout=250) for marker in markers)


def click_composer_plus(page: Any) -> None:
    plus = page.evaluate_handle(
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

            const candidates = Array.from(document.querySelectorAll('button, [role="button"]'))
                .map((element) => {
                    const rect = element.getBoundingClientRect();
                    const text = (element.innerText || element.textContent || '').trim().toLowerCase();
                    const label = (
                        element.getAttribute('aria-label') ||
                        element.getAttribute('title') ||
                        ''
                    ).toLowerCase();
                    const iconText = Array.from(element.querySelectorAll('i, .google-symbols, span'))
                        .map((node) => (node.textContent || '').trim().toLowerCase())
                        .join(' ');
                    return { element, rect, text, label, iconText };
                })
                .filter(({ element, rect, text, label, iconText }) => (
                    visible(element) &&
                    rect.top > window.innerHeight * 0.55 &&
                    rect.left < window.innerWidth * 0.55 &&
                    (
                        text === '+' ||
                        text.includes('add_2') ||
                        iconText.includes('add_2') ||
                        label.includes('add') ||
                        label.includes('media') ||
                        label.includes('asset') ||
                        (label.includes('create') && rect.width <= 70 && rect.height <= 70)
                    )
                ))
                .sort((a, b) => {
                    const aScore = (
                        (a.iconText.includes('add_2') ? 0 : 10) +
                        (a.rect.left < window.innerWidth * 0.50 ? 0 : 5) +
                        a.rect.left / 10000
                    );
                    const bScore = (
                        (b.iconText.includes('add_2') ? 0 : 10) +
                        (b.rect.left < window.innerWidth * 0.50 ? 0 : 5) +
                        b.rect.left / 10000
                    );
                    return aScore - bScore;
                });

            return candidates[0]?.element || null;
        }
        """
    )
    element = plus.as_element()
    if element is None:
        raise RuntimeError("Could not find the Flow composer plus button.")
    element.click(timeout=5000, force=True)


def ensure_agent_mode_off(page: Any) -> None:
    agent_button = page.evaluate_handle(
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

            return Array.from(document.querySelectorAll('button, [role="button"]'))
                .find((element) => (
                    visible(element) &&
                    (element.innerText || element.textContent || '').trim().toLowerCase() === 'agent'
                )) || null;
        }
        """
    )
    element = agent_button.as_element()
    if element is None:
        print("Agent mode button not found; continuing.")
        return

    state = element.evaluate(
        """
        (element) => ({
            pressed: element.getAttribute('aria-pressed'),
            checked: element.getAttribute('aria-checked'),
            selected: element.getAttribute('aria-selected'),
            text: (element.innerText || element.textContent || '').trim()
        })
        """
    )
    is_on = any(str(state.get(key, "")).lower() == "true" for key in ("pressed", "checked", "selected"))
    if is_on:
        element.click(timeout=5000)
        page.wait_for_timeout(500)
        print("Agent mode turned off.")
    else:
        print("Agent mode is already off.")


def open_asset_picker(page: Any) -> None:
    if asset_picker_visible(page):
        get_asset_search_input(page, timeout=3000)
        return

    deadline = time.time() + 90
    next_agent_check = 0.0
    last_status = ""
    while time.time() < deadline:
        now = time.time()
        if now >= next_agent_check:
            ensure_agent_mode_off(page)
            next_agent_check = now + 10
        try:
            click_composer_plus(page)
        except RuntimeError:
            status = "Flow composer plus is not ready yet"
            if status != last_status:
                print(f"Still waiting: {status}")
                last_status = status
            page.wait_for_timeout(1000)
            continue

        if asset_picker_visible(page):
            get_asset_search_input(page, timeout=3000)
            print("Search assets field is ready.")
            return
        page.wait_for_timeout(500)

    raise RuntimeError("Flow asset picker did not open after waiting for composer plus.")


def open_upload_menu(page: Any) -> None:
    if upload_menu_visible(page):
        return

    if not click_top_plus(page):
        raise RuntimeError("Could not find Flow top-right plus button.")

    deadline = time.time() + 20
    while time.time() < deadline:
        if upload_menu_visible(page):
            return
        page.wait_for_timeout(500)

    raise RuntimeError("Flow upload menu did not open after clicking top-right plus.")


def click_top_plus(page: Any) -> bool:
    plus = page.evaluate_handle(
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

            const candidates = Array.from(document.querySelectorAll('button, [role="button"]'))
                .map((element) => {
                    const rect = element.getBoundingClientRect();
                    const text = (element.innerText || element.textContent || '').trim().toLowerCase();
                    const label = (
                        element.getAttribute('aria-label') ||
                        element.getAttribute('title') ||
                        ''
                    ).toLowerCase();
                    const iconText = Array.from(element.querySelectorAll('i, .google-symbols, span'))
                        .map((node) => (node.textContent || '').trim().toLowerCase())
                        .join(' ');
                    return { element, rect, text, label, iconText };
                })
                .filter(({ element, rect, text, label, iconText }) => (
                    visible(element) &&
                    rect.top < 150 &&
                    rect.left > window.innerWidth * 0.70 &&
                    (
                        text === '+' ||
                        text.includes('add') ||
                        iconText.includes('add') ||
                        label.includes('add') ||
                        label.includes('upload') ||
                        label.includes('media')
                    )
                ))
                .sort((a, b) => b.rect.left - a.rect.left);
            return candidates[0]?.element || null;
        }
        """
    )
    element = plus.as_element()
    if element is None:
        return False
    element.click(timeout=5000)
    return True


def click_media_picker_uploads_tab(page: Any) -> None:
    locators = [
        page.get_by_role("tab", name=re.compile(r"^Uploads$", re.I)),
        page.get_by_role("button", name=re.compile(r"^Uploads$", re.I)),
        page.get_by_text(re.compile(r"^Uploads$", re.I)),
    ]
    for locator in locators:
        if click_locator(locator, timeout=2000):
            return


def media_picker_asset_count(page: Any) -> int:
    return int(
        page.evaluate(
            """
            () => {
                const visible = (element) => {
                    const rect = element.getBoundingClientRect();
                    const style = window.getComputedStyle(element);
                    return (
                        rect.width >= 28 &&
                        rect.height >= 28 &&
                        style.visibility !== 'hidden' &&
                        style.display !== 'none'
                    );
                };
                const dialogText = Array.from(document.querySelectorAll('body *')).find((element) => {
                    const text = (element.innerText || element.textContent || '').trim();
                    const rect = element.getBoundingClientRect();
                    return text.includes('Search assets') && rect.width > 0 && rect.height > 0;
                });
                const root = dialogText ? dialogText.closest('[role="dialog"], div') : document.body;
                return Array.from(root.querySelectorAll('img, video, canvas')).filter(visible).length;
            }
            """
        )
    )


def click_upload_media_button(page: Any) -> bool:
    locators = [
        page.get_by_role("menuitem", name=re.compile(r"Upload media", re.I)),
        page.locator('[role="menuitem"]:has-text("Upload media")'),
        page.locator('button[role="menuitem"]:has-text("Upload media")'),
        page.get_by_role("button", name=re.compile(r"^Upload media$", re.I)),
        page.get_by_text(re.compile(r"Upload media", re.I)),
        page.get_by_role("button", name=re.compile(r"^Upload$", re.I)),
        page.locator("[aria-label*='Upload media' i]"),
    ]
    for locator in locators:
        if click_locator(locator, timeout=4000):
            return True
        if click_locator(locator, timeout=1500, force=True):
            return True

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
                    style.display !== 'none'
                );
            };
            const candidates = Array.from(document.querySelectorAll('[role="menuitem"], button'))
                .filter((element) => {
                    const text = (element.innerText || element.textContent || '')
                        .replace(/\\s+/g, ' ')
                        .trim()
                        .toLowerCase();
                    return visible(element) && text.includes('upload media');
                });
            return candidates[0] || null;
        }
        """
    )
    element = handle.as_element()
    if element is None:
        return False
    element.click(timeout=5000, force=True)
    return True


def set_files_on_flow_file_input(page: Any, files: list[Path]) -> bool:
    file_paths = [str(path) for path in files]
    inputs = page.locator('input[type="file"]')

    try:
        count = inputs.count()
    except Exception:
        count = 0

    for index in range(count - 1, -1, -1):
        try:
            target = inputs.nth(index)
            target.set_input_files(file_paths if len(file_paths) > 1 else file_paths[0], timeout=10000)
            return True
        except Exception:
            continue

    return False


def upload_files_from_open_menu(page: Any, files: list[Path]) -> bool:
    try:
        with page.expect_file_chooser(timeout=6000) as chooser_info:
            if not click_upload_media_button(page):
                raise RuntimeError("Could not click Flow Upload media button.")
        chooser_info.value.set_files([str(path) for path in files])
        return True
    except Exception:
        if set_files_on_flow_file_input(page, files):
            return True
        return False


def flow_upload_gallery_state(page: Any) -> dict[str, Any]:
    return dict(
        page.evaluate(
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

                const inMainGalleryArea = (element) => {
                    const rect = element.getBoundingClientRect();
                    return (
                        rect.width >= 48 &&
                        rect.height >= 48 &&
                        rect.left > 160 &&
                        rect.top > 70 &&
                        rect.bottom < window.innerHeight - 90
                    );
                };

                const mediaElements = Array.from(document.querySelectorAll('img, video, canvas, [style*="background-image"]'))
                    .filter((element) => {
                        if (!visible(element) || !inMainGalleryArea(element)) return false;
                        const src = element.getAttribute('src') || '';
                        const style = element.getAttribute('style') || '';
                        const text = `${src} ${style}`.toLowerCase();
                        return !text.includes('flower-placeholder');
                    });

                const mediaKeys = new Set(mediaElements.map((element) => {
                    const rect = element.getBoundingClientRect();
                    return [
                        Math.round(rect.left / 8),
                        Math.round(rect.top / 8),
                        Math.round(rect.width / 8),
                        Math.round(rect.height / 8)
                    ].join(':');
                }));

                const busyElements = Array.from(document.querySelectorAll('[role="progressbar"], [aria-busy="true"], body *'))
                    .filter((element) => {
                        if (!visible(element) || !inMainGalleryArea(element)) return false;
                        const text = (element.innerText || element.textContent || '')
                            .replace(/\\s+/g, ' ')
                            .trim()
                            .toLowerCase();
                        const role = (element.getAttribute('role') || '').toLowerCase();
                        const busy = (element.getAttribute('aria-busy') || '').toLowerCase();
                        const isProgress = role === 'progressbar' || busy === 'true';
                        const uploadText = /\\b(uploading|processing|preparing|importing|finishing)\\b/.test(text);
                        const percentText = /\\b\\d{1,3}%\\b/.test(text);
                        return isProgress || uploadText || percentText;
                    });

                const composerPlusReady = Array.from(document.querySelectorAll('button, [role="button"]'))
                    .some((element) => {
                        if (!visible(element)) return false;
                        const rect = element.getBoundingClientRect();
                        if (rect.top <= window.innerHeight * 0.55) return false;
                        const text = (element.innerText || element.textContent || '').trim().toLowerCase();
                        const label = (
                            element.getAttribute('aria-label') ||
                            element.getAttribute('title') ||
                            ''
                        ).toLowerCase();
                        const iconText = Array.from(element.querySelectorAll('i, .google-symbols, span'))
                            .map((node) => (node.textContent || '').trim().toLowerCase())
                            .join(' ');
                        return (
                            text === '+' ||
                            text.includes('add_2') ||
                            iconText.includes('add_2') ||
                            label.includes('add') ||
                            label.includes('asset') ||
                            label.includes('media') ||
                            label.includes('create')
                        );
                    });

                return {
                    media_count: mediaKeys.size,
                    busy_count: busyElements.length,
                    composer_plus_ready: composerPlusReady
                };
            }
            """
        )
    )


def wait_for_asset_uploads(
    page: Any, expected_new: int, timeout_seconds: int, baseline_count: int
) -> None:
    print(f"Waiting dynamically for Flow upload handoff ({expected_new} asset(s))...")
    deadline = time.time() + timeout_seconds
    stable_ready_polls = 0
    quiet_partial_polls = 0
    expected_total = baseline_count + expected_new
    last_status = ""

    while time.time() < deadline:
        state = flow_upload_gallery_state(page)
        media_count = int(state.get("media_count", 0))
        busy_count = int(state.get("busy_count", 0))
        composer_ready = bool(state.get("composer_plus_ready", False))
        enough_cards = media_count >= expected_total

        if enough_cards and busy_count == 0 and composer_ready:
            stable_ready_polls += 1
            if stable_ready_polls >= 3:
                print(f"Flow media cards are ready ({media_count}/{expected_total}).")
                return
        else:
            stable_ready_polls = 0

        if media_count > baseline_count and busy_count == 0 and composer_ready:
            quiet_partial_polls += 1
            if quiet_partial_polls >= 12:
                print(
                    "Flow upload cards look ready, but not every card was countable; "
                    "continuing with asset search verification."
                )
                return
        else:
            quiet_partial_polls = 0

        status = (
            f"{media_count}/{expected_total} media card(s), "
            f"{busy_count} upload indicator(s), "
            f"composer {'ready' if composer_ready else 'not ready'}"
        )
        if status != last_status:
            print(f"Still waiting: {status}")
            last_status = status
        page.wait_for_timeout(1000)

    raise RuntimeError("Timed out waiting for Flow media uploads to finish.")


def asset_picker_result_count(page: Any) -> int:
    return int(
        page.evaluate(
            """
            () => {
                const visible = (element) => {
                    const rect = element.getBoundingClientRect();
                    const style = window.getComputedStyle(element);
                    return (
                        rect.width >= 32 &&
                        rect.height >= 32 &&
                        style.visibility !== 'hidden' &&
                        style.display !== 'none'
                    );
                };
                return Array.from(document.querySelectorAll('img, video, canvas'))
                    .filter((element) => {
                        const rect = element.getBoundingClientRect();
                        return (
                            visible(element) &&
                            rect.left > window.innerWidth * 0.18 &&
                            rect.top > 90 &&
                            rect.bottom < window.innerHeight - 80
                        );
                    }).length;
            }
            """
        )
    )


def asset_name_visible(page: Any, image_path: Path) -> bool:
    for pattern in (image_path.name, image_path.stem):
        try:
            if safe_is_visible(page.get_by_text(re.compile(re.escape(pattern), re.I)), timeout=500):
                return True
        except Exception:
            continue
        try:
            if safe_is_visible(
                page.locator(f'img[alt*="{css_string_fragment(pattern)}"]'),
                timeout=500,
            ):
                return True
        except Exception:
            continue
    return False


def css_string_fragment(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def wait_for_asset_search_result(page: Any, image_path: Path, timeout_seconds: int) -> None:
    print(f"Waiting for uploaded asset in picker: {image_path.name}")
    deadline = time.time() + timeout_seconds
    last_status = ""
    search_asset(page, image_path)

    while time.time() < deadline:
        if asset_name_visible(page, image_path):
            print(f"Uploaded asset is searchable by name: {image_path.name}")
            return

        result_count = asset_picker_result_count(page)
        if result_count == 1:
            print(f"Uploaded asset search returned {result_count} result(s).")
            return

        status = "asset search has no result yet"
        if status != last_status:
            print(f"Still waiting: {status}")
            last_status = status
        page.wait_for_timeout(1000)

        try:
            current_query = get_asset_search_input(page, timeout=1000).input_value(timeout=1000)
            if current_query != image_path.name:
                print("Search assets query drifted; re-entering filename.")
                search_asset(page, image_path)
        except Exception:
            print("Search assets input is not visible; reopening picker and re-entering filename.")
            open_asset_picker(page)
            search_asset(page, image_path)

    raise RuntimeError(f"Timed out waiting for uploaded asset: {image_path.name}")


def upload_all_images_to_flow_assets(
    page: Any, images: list[Path], timeout_seconds: int
) -> None:
    print("")
    print(f"Uploading all {len(images)} selected image(s) to Flow media first...")
    open_upload_menu(page)
    baseline_count = int(flow_upload_gallery_state(page).get("media_count", 0))

    if upload_files_from_open_menu(page, images):
        print("Selected all images for Flow media upload.")
    else:
        print("Bulk upload did not open; trying images one by one.")
        for image_path in images:
            open_upload_menu(page)
            if not upload_files_from_open_menu(page, [image_path]):
                raise RuntimeError("Could not click Flow Upload media button.")
            print(f"Selected for media upload: {image_path.name}")
            page.wait_for_timeout(500)

    wait_for_asset_uploads(page, len(images), timeout_seconds, baseline_count)
    try:
        page.keyboard.press("Escape")
    except Exception:
        pass


def clear_asset_search(page: Any) -> None:
    target = get_asset_search_input(page, timeout=5000)
    target.click(timeout=3000, force=True)
    target.fill("", timeout=3000)


def search_asset(page: Any, image_path: Path) -> None:
    query = image_path.name
    try:
        target = get_asset_search_input(page, timeout=3000)
    except Exception:
        print("Search assets input disappeared; reopening asset picker.")
        open_asset_picker(page)
        target = get_asset_search_input(page, timeout=8000)
    target.click(timeout=3000, force=True)
    target.fill("", timeout=3000)
    target.fill(query, timeout=5000)
    target.evaluate(
        """
        (element) => {
            element.dispatchEvent(new InputEvent('input', {
                bubbles: true,
                inputType: 'insertText',
                data: element.value
            }));
            element.dispatchEvent(new Event('change', { bubbles: true }));
        }
        """
    )
    page.wait_for_timeout(1000)
    actual = target.input_value(timeout=3000)
    if actual != query:
        raise RuntimeError(f"Search assets input did not keep query. Expected {query!r}, got {actual!r}.")
    print(f"Search assets query entered: {query}")


def click_asset_for_image(page: Any, image_path: Path, fallback_index: int) -> None:
    option = page.evaluate_handle(
        """
        ({ name, stem }) => {
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
            const needles = [name.toLowerCase(), stem.toLowerCase()];
            const options = Array.from(document.querySelectorAll('[role="option"], button, [data-index]'))
                .filter(visible);
            for (const option of options) {
                const text = (option.innerText || option.textContent || '').toLowerCase();
                const alt = Array.from(option.querySelectorAll('img'))
                    .map((img) => (img.getAttribute('alt') || '').toLowerCase())
                    .join(' ');
                if (needles.some((needle) => text.includes(needle) || alt.includes(needle))) {
                    return option;
                }
            }
            const image = Array.from(document.querySelectorAll('img'))
                .filter(visible)
                .find((img) => {
                    const alt = (img.getAttribute('alt') || '').toLowerCase();
                    return needles.some((needle) => alt.includes(needle));
                });
            return image ? image.closest('[role="option"], button, [data-index]') || image : null;
        }
        """,
        {"name": image_path.name, "stem": image_path.stem},
    )
    option_element = option.as_element()
    if option_element is not None:
        option_element.click(timeout=5000, force=True)
        print(f"Selected uploaded asset by exact filename: {image_path.name}")
        return

    patterns = [image_path.name, image_path.stem]
    for pattern in patterns:
        locator = page.get_by_text(re.compile(re.escape(pattern), re.I))
        if click_locator(locator, timeout=2500):
            print(f"Selected uploaded asset by name: {pattern}")
            return

    asset = page.evaluate_handle(
        """
        (index) => {
            const visible = (element) => {
                const rect = element.getBoundingClientRect();
                const style = window.getComputedStyle(element);
                return (
                    rect.width >= 45 &&
                    rect.height >= 45 &&
                    style.visibility !== 'hidden' &&
                    style.display !== 'none'
                );
            };
            const media = Array.from(document.querySelectorAll('img, video, canvas'))
                .map((element) => ({ element, rect: element.getBoundingClientRect() }))
                .filter(({ element, rect }) => (
                    visible(element) &&
                    rect.left > window.innerWidth * 0.20 &&
                    rect.top > 100 &&
                    rect.bottom < window.innerHeight - 80
                ))
                .sort((a, b) => (a.rect.top - b.rect.top) || (a.rect.left - b.rect.left));
            return media[index]?.element || media[0]?.element || null;
        }
        """,
        fallback_index,
    )
    element = asset.as_element()
    if element is None:
        raise RuntimeError(f"Could not select uploaded asset for: {image_path.name}")
    element.click(timeout=5000)
    print(f"Selected uploaded asset by picker position: {image_path.name}")


def click_add_to_prompt(page: Any) -> None:
    locators = [
        page.locator('button:has-text("Add to Prompt")'),
        page.locator('[role="dialog"] button:has-text("Add to Prompt")'),
        page.locator('div:has(input[aria-label="Search assets"]) button:has-text("Add to Prompt")'),
        page.get_by_role("button", name=re.compile(r"Add to Prompt", re.I)),
        page.get_by_text(re.compile(r"Add to Prompt", re.I)),
    ]

    deadline = time.time() + 25
    while time.time() < deadline:
        for locator in locators:
            if click_locator(locator, timeout=1200):
                print("Clicked Add to Prompt.")
                return
            if click_locator(locator, timeout=800, force=True):
                print("Clicked Add to Prompt.")
                return

        button = page.evaluate_handle(
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
                const buttons = Array.from(document.querySelectorAll('button, [role="button"]'))
                    .filter((element) => {
                        const text = (element.innerText || element.textContent || '')
                            .replace(/\\s+/g, ' ')
                            .trim()
                            .toLowerCase();
                        return visible(element) && text.includes('add to prompt');
                    });
                return buttons[0] || null;
            }
            """
        )
        element = button.as_element()
        if element is not None:
            element.click(timeout=5000, force=True)
            print("Clicked Add to Prompt.")
            return

        page.wait_for_timeout(500)

    raise RuntimeError("Could not click Flow Add to Prompt button.")


def attach_uploaded_asset_to_prompt(page: Any, image_path: Path, fallback_index: int, timeout_seconds: int) -> None:
    previous_count = input_attachment_count(page)
    open_asset_picker(page)
    wait_for_asset_search_result(page, image_path, timeout_seconds)
    click_asset_for_image(page, image_path, fallback_index)
    wait_for_upload_to_attach(page, previous_count, timeout_seconds)
    close_asset_picker(page)


def fill_prompt_exact(page: Any, prompt_text: str) -> None:
    expected = " ".join(prompt_text.split())
    last_seen_text = ""

    for attempt in range(1, 4):
        close_asset_picker(page)
        editor = page.locator('[data-slate-editor="true"][contenteditable="true"]').first
        editor.wait_for(state="visible", timeout=8000)
        box = editor.bounding_box()
        if box:
            page.mouse.click(box["x"] + 12, box["y"] + max(8, min(18, box["height"] / 2)))
        else:
            editor.click(force=True)
        page.wait_for_timeout(150)
        page.keyboard.press("Control+A")
        page.wait_for_timeout(100)
        page.keyboard.press("Backspace")
        page.wait_for_timeout(100)
        page.keyboard.insert_text(prompt_text)
        page.wait_for_timeout(500)
        last_seen_text = " ".join(get_prompt_text(page).split())
        if last_seen_text == expected:
            print("Full prompt inserted.")
            return

        print(f"Prompt insert attempt {attempt} did not stick; retrying text insert...")

    raise RuntimeError(f"Prompt text did not stick. Found: {last_seen_text!r}")


def composer_send_state(page: Any) -> dict[str, Any]:
    return dict(
        page.evaluate(
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

                const editor = document.querySelector('[data-slate-editor="true"][contenteditable="true"], [contenteditable="true"]');
                let root = editor;
                while (root && root !== document.body) {
                    const hasAgent = Array.from(root.querySelectorAll('button, [role="button"]'))
                        .some((button) => (button.innerText || button.textContent || '').trim().toLowerCase() === 'agent');
                    const hasCreateArrow = Array.from(root.querySelectorAll('i, .google-symbols, span'))
                        .some((node) => (node.textContent || '').trim().toLowerCase() === 'arrow_forward');
                    if (hasAgent && hasCreateArrow) break;
                    root = root.parentElement;
                }
                if (!root || root === document.body) {
                    return { found: false, enabled: false };
                }

                const button = Array.from(root.querySelectorAll('button, [role="button"]'))
                    .find((element) => {
                        if (!visible(element)) return false;
                        const iconText = Array.from(element.querySelectorAll('i, .google-symbols, span'))
                            .map((node) => (node.textContent || '').trim().toLowerCase())
                            .join(' ');
                        return iconText.includes('arrow_forward');
                    });
                if (!button) {
                    return { found: false, enabled: false };
                }

                const disabled = button.hasAttribute('disabled') ||
                    (button.getAttribute('aria-disabled') || '').toLowerCase() === 'true';
                return { found: true, enabled: !disabled };
            }
            """
        )
    )


def wait_for_composer_send_enabled(page: Any, timeout_seconds: int = 45) -> None:
    deadline = time.time() + timeout_seconds
    last_status = ""
    while time.time() < deadline:
        state = composer_send_state(page)
        if state.get("found") and state.get("enabled"):
            print("Composer send arrow is enabled.")
            return

        status = "send arrow not ready"
        if status != last_status:
            print(f"Still waiting: {status}")
            last_status = status
        page.wait_for_timeout(500)

    raise RuntimeError("Composer send arrow never became enabled.")


def click_send_arrow(page: Any) -> None:
    button = page.evaluate_handle(
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

            const editor = document.querySelector('[data-slate-editor="true"][contenteditable="true"], [contenteditable="true"]');
            let root = editor;
            while (root && root !== document.body) {
                const hasAgent = Array.from(root.querySelectorAll('button, [role="button"]'))
                    .some((candidate) => (candidate.innerText || candidate.textContent || '').trim().toLowerCase() === 'agent');
                const hasCreateArrow = Array.from(root.querySelectorAll('i, .google-symbols, span'))
                    .some((node) => (node.textContent || '').trim().toLowerCase() === 'arrow_forward');
                if (hasAgent && hasCreateArrow) break;
                root = root.parentElement;
            }
            if (!root || root === document.body) return null;

            return Array.from(root.querySelectorAll('button, [role="button"]'))
                .find((element) => {
                    if (!visible(element)) return false;
                    const disabled = element.hasAttribute('disabled') ||
                        (element.getAttribute('aria-disabled') || '').toLowerCase() === 'true';
                    if (disabled) return false;
                    const iconText = Array.from(element.querySelectorAll('i, .google-symbols, span'))
                        .map((node) => (node.textContent || '').trim().toLowerCase())
                        .join(' ');
                    return iconText.includes('arrow_forward');
                }) || null;
        }
        """
    )
    element = button.as_element()
    if element is None:
        raise RuntimeError("Could not find the enabled composer send arrow.")

    element.click(timeout=5000, force=True)
    print("Clicked composer send arrow.")


def submit_attached_image_prompt(page: Any, image_path: Path, fallback_index: int, upload_timeout: int) -> None:
    clear_prompt_attachments(page)
    attach_uploaded_asset_to_prompt(page, image_path, fallback_index, upload_timeout)
    fill_prompt_exact(page, PERFECT_CAR_PROMPT)
    close_asset_picker(page)
    wait_for_composer_send_enabled(page)
    click_send_arrow(page)
    page.wait_for_timeout(1500)


def extension_for_mime(mime_type: str) -> str:
    mime_type = (mime_type or "").split(";")[0].strip().lower()
    if mime_type == "image/png":
        return ".png"
    if mime_type == "image/webp":
        return ".webp"
    if mime_type == "image/jpeg":
        return ".jpg"
    if mime_type == "video/mp4":
        return ".mp4"
    if mime_type == "video/webm":
        return ".webm"
    return ".bin"


def save_generated_media(context: Any, element: Any, output_base: Path, source_url: str | None = None) -> Path:
    src = source_url or get_media_source(element)
    if not src:
        raise RuntimeError("Generated media has no source URL.")

    response = context.request.get(src, fail_on_status_code=False, timeout=60000)
    if not response.ok:
        raise RuntimeError(
            f"Failed to download generated media: HTTP {response.status} from {src}"
        )

    mime_type = response.headers.get("content-type", "")
    final_path = unique_path(output_base.with_suffix(extension_for_mime(mime_type)))
    final_path.parent.mkdir(parents=True, exist_ok=True)
    final_path.write_bytes(response.body())
    return final_path


def wait_for_generated_batch(
    page: Any, seen_sources: set[str], expected_count: int, timeout_seconds: int
) -> list[dict[str, Any]]:
    deadline = time.time() + timeout_seconds
    first_complete_at: float | None = None
    stable_sources: tuple[str, ...] = ()
    last_status = ""

    while time.time() < deadline:
        entries = get_media_entries(page)
        new_entries = [entry for entry in entries if entry["src"] not in seen_sources]
        new_entries = new_entries[:expected_count]
        sources = tuple(entry["src"] for entry in new_entries)

        if len(new_entries) >= expected_count:
            if sources != stable_sources:
                stable_sources = sources
                first_complete_at = time.time()
                print(
                    f"Generated batch appeared ({expected_count}/{expected_count}); "
                    "waiting for it to settle..."
                )
            elif first_complete_at is not None and time.time() - first_complete_at >= 5:
                print(f"Generated batch is stable ({expected_count}/{expected_count}).")
                return new_entries
        else:
            first_complete_at = None
            stable_sources = sources

        status = (
            f"{len(entries)} gallery media item(s), "
            f"{len(new_entries)}/{expected_count} new generated candidate(s)"
        )
        if status != last_status:
            print(f"Still waiting: {status}")
            last_status = status
        page.wait_for_timeout(1500)

    raise RuntimeError(
        f"Timed out waiting for generated batch: expected {expected_count} new image(s)."
    )


def process_images(
    context: Any,
    page: Any,
    images: list[Path],
    output_dir: Path,
    timeout_error: type[Exception],
    upload_timeout: int,
    download_timeout: int,
    delay_seconds: float,
    batch_size: int,
) -> list[Path]:
    saved_files: list[Path] = []

    upload_all_images_to_flow_assets(page, images, upload_timeout)
    seen_sources = {entry["src"] for entry in get_media_entries(page)}
    print(f"Generation baseline set after upload: {len(seen_sources)} existing media item(s).")

    batch_size = max(1, batch_size)
    for batch_start in range(0, len(images), batch_size):
        batch = images[batch_start : batch_start + batch_size]
        batch_number = batch_start // batch_size + 1
        batch_total = (len(images) + batch_size - 1) // batch_size
        seen_sources.update(entry["src"] for entry in get_media_entries(page))

        print("")
        print(
            f"Submitting batch {batch_number}/{batch_total}: "
            f"{len(batch)} image prompt(s)."
        )

        for offset, image_path in enumerate(batch):
            index = batch_start + offset + 1
            print("")
            print(f"[{index}/{len(images)}] Attaching uploaded Flow asset: {image_path.name}")
            submit_attached_image_prompt(page, image_path, index - 1, upload_timeout)
            print(f"[{index}/{len(images)}] Submitted.")

            if delay_seconds > 0 and offset < len(batch) - 1:
                print(f"[{index}/{len(images)}] Waiting {delay_seconds:g}s before next submit...")
                page.wait_for_timeout(int(delay_seconds * 1000))

        print("")
        print(
            f"Batch {batch_number}/{batch_total} submitted. "
            f"Waiting for {len(batch)} generated image(s)..."
        )
        new_entries = wait_for_generated_batch(page, seen_sources, len(batch), download_timeout)

        # Flow usually shows newest outputs first, so reverse the visible batch to map
        # back to the submit order in this batch.
        ordered_entries = list(reversed(new_entries))
        for image_path, new_entry in zip(batch, ordered_entries):
            output_base = output_base_for_image(output_dir, image_path)
            saved_path = save_generated_media(
                context,
                new_entry["element"],
                output_base,
                source_url=new_entry["src"],
            )
            saved_files.append(saved_path)
            seen_sources.add(new_entry["src"])
            print(f"Downloaded generated image for {image_path.name}: {saved_path}")

        seen_sources.update(entry["src"] for entry in get_media_entries(page))

    return saved_files


def main() -> int:
    args = parse_args()

    input_dir = Path(args.input_dir).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    images = slice_items(image_files_in_dir(input_dir), args.start_at, args.limit)

    if args.dry_run:
        print(f"Found {len(images)} selected image(s) in: {input_dir}")
        for image_path in images:
            print(image_path)
        return 0

    if not images:
        print(f"No images found in: {input_dir}")
        return 1

    print(f"Input folder: {input_dir}")
    print(f"Output folder: {output_dir}")
    print(f"Selected {len(images)} image(s).")

    if not args.yes:
        print("Flow will upload each selected image and submit the fixed car cleanup prompt.")
        input("Press Enter to continue, or Ctrl+C to cancel...")

    sync_playwright, timeout_error = require_playwright()
    chrome_user_data_dir = Path(args.chrome_user_data_dir).expanduser()
    chrome_profile_directory = args.chrome_profile_directory

    if uses_local_automation_profile(chrome_user_data_dir):
        chrome_user_data_dir.mkdir(parents=True, exist_ok=True)
        remove_stale_profile_locks(chrome_user_data_dir)
        clear_crash_restore_flags(chrome_user_data_dir, chrome_profile_directory)

    startup_url = args.project_url or FLOW_HOME_URL
    chrome_process = launch_chrome_if_needed(
        args.debug_port,
        chrome_user_data_dir,
        chrome_profile_directory,
        startup_url,
    )

    with sync_playwright() as playwright:
        browser, context = connect_context(playwright, args.debug_port)
        page = get_page(context)

        try:
            project_url = prepare_flow_page(page, args)
            print(f"Using Flow project: {project_url}")
            ensure_agent_mode_off(page)
            saved_files = process_images(
                context,
                page,
                images,
                output_dir,
                timeout_error,
                args.upload_timeout,
                args.download_timeout,
                args.delay,
                args.batch_size,
            )
            print("")
            print(f"Saved {len(saved_files)} Flow output file(s).")
        finally:
            if not args.keep_browser_open:
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
