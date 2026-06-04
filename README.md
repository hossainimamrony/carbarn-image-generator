# Canva Background Remover Automation

Windows-only web UI for the full car image automation. It can download images from a Google Photos shared album, open Canva in Chrome, run BG Remover, then send the cleaned images to Google Flow to create the final polished car images.

## One-Click Setup

Use this on a new Windows device.

1. Install **Python 3.10 or newer** from <https://www.python.org/downloads/windows/>.
2. During Python install, enable **Add python.exe to PATH**.
3. Install **Google Chrome** from <https://www.google.com/chrome/>.
4. Double-click:

```text
setup_and_run.bat
```

The setup script will:

- run `git pull --ff-only` to get the latest code when this folder is a Git repo
- create a local `.venv` virtual environment
- upgrade `pip`
- install all Python packages from `requirements.txt`
- download Playwright browser files
- create the needed `assets` and `chrome_profiles` folders
- start the web UI

When it finishes, the UI opens at:

```text
http://127.0.0.1:8765
```

Keep the setup/server window open while using the UI.

## Run After Setup

After the first setup, you can still use the same button:

```text
setup_and_run.bat
```

It will reuse the existing `.venv`, check/install dependencies, and start the UI again.

You can also run manually from PowerShell:

```powershell
.\.venv\Scripts\python.exe web_server.py
```

## What You Need Installed

- Windows 10 or Windows 11
- Python 3.10 or newer
- Google Chrome
- Canva account with access to the design and BG Remover

Everything Python-related is installed by `setup_and_run.bat`.

## Web UI Fields

The web UI lets you set:

- stock ID for unique folder and file naming
- Canva design URL
- Google Photos shared album URL
- single image path
- Google Photos download folder
- Canva output root and output file name
- Chrome EXE path
- Chrome automation profile folder
- debug port
- timeout values
- batch options
- Google Flow input and output roots
- Google Flow project URL
- Google Flow batch size, delay, and timeout values

The main buttons are separate jobs:

- **Download Photos**: downloads Google Photos images only
- **Canva Only**: runs only `canva_bg_remove_download.py`
- **Flow Only**: runs only `perfect_car_image.py`
- **Pause Flow**: pauses before the next major Flow action so you can change model/settings
- **Resume Flow**: continues Flow automation after a pause
- **Canva Output**: opens `assets\canva_download`
- **Gemini Output**: opens `assets\perfect_car_images`

Logs appear in the live log panel.

The **Flow prompt** field is live. The UI saves it while you type, and Flow reloads it before each image submission, so prompt changes apply without restarting the run.

## First Canva Login

The first run opens Chrome with a separate automation profile:

```text
chrome_profiles\canva_automation_profile
```

If Canva asks for login, log in inside the opened Chrome window. The same profile is reused next time, so you usually only need to log in once per device.

## First Google Flow Login

The perfect-image step opens Google Flow:

```text
https://labs.google/fx/tools/flow
```

If Google asks for login, log in inside the opened Chrome window. The automation profile is reused on the same device.

## Run Modes

Default Canva mode uses images already in the Google Photos folder.

Use **Download Photos** only when you want to download the album again.

Enable **Process only single image** to skip Google Photos and process only the image path from the form.

Use **Max images** when testing with only a few images.

## Output

Downloaded Google Photos images are saved under:

```text
assets\google_photos_downloads\<STOCK_ID>\photos
```

Canva background-removed images are saved to:

```text
assets\canva_download\<STOCK_ID>\canva
```

Final perfect images are saved to:

```text
assets\perfect_car_images\<STOCK_ID>\flow
```

Files are named from the stock ID and image number:

```text
<STOCK_ID>_001_canva_bg_removed.jpg
<STOCK_ID>_001_flow_final.jpg
```

The steps are intentionally separate. Run **Download Photos**, then **Canva Only**, then **Flow Only** when each stage is ready.

## Troubleshooting

If `setup_and_run.bat` closes quickly, open PowerShell in this folder and run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\setup_and_run.ps1
```

If Python is not found, reinstall Python and enable **Add python.exe to PATH**.

If Chrome does not open, check the **Chrome EXE** field in the UI.

If Canva asks for login repeatedly, delete this folder and log in again:

```text
chrome_profiles\canva_automation_profile
```

If the process cannot connect to Chrome, change the debug port from `9223` to another unused port, for example `9224`.

If Canva UI clicks fail, increase the timeout values in the UI and try again.
