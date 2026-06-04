# Canva Background Remover Automation

Windows-only web UI for this automation. It can download images from a Google Photos shared album, open Canva in Chrome, run BG Remover, and save JPG output files.

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

- Canva design URL
- Google Photos shared album URL
- single image path
- Google Photos download folder
- output folder and output file name
- Chrome EXE path
- Chrome automation profile folder
- debug port
- Canva placement values
- timeout values
- batch options

Click **Start** in the web UI to run the automation. Logs appear in the live log panel.

## First Canva Login

The first run opens Chrome with a separate automation profile:

```text
chrome_profiles\canva_automation_profile
```

If Canva asks for login, log in inside the opened Chrome window. The same profile is reused next time, so you usually only need to log in once per device.

## Run Modes

Default mode downloads the Google Photos album and processes every image.

Enable **Use existing photos folder** if the album was already downloaded.

Enable **Process only single image** to skip Google Photos and process only the image path from the form.

Use **Max images** when testing with only a few images.

## Output

Processed images are saved to:

```text
assets\canva_download
```

For a batch, each output is named from the original image filename with `_bg_removed.jpg` added. For a single image, the UI uses the output name field.

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
