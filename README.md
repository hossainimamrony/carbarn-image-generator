# Canva Background Remover Automation

Windows-only helper for downloading images from a Google Photos shared album, opening Canva in Chrome, running BG Remover, and saving JPG output files.

## Requirements

- Windows 10 or Windows 11
- Google Chrome installed
- Python 3.10 or newer
- A Canva account with access to the design and BG Remover

## Setup On A New Windows Device

1. Install Python from <https://www.python.org/downloads/windows/>.
2. During install, enable **Add python.exe to PATH**.
3. Install Google Chrome from <https://www.google.com/chrome/>.
4. Open PowerShell in this project folder.
5. Install the Python dependency:

```powershell
python -m pip install playwright
python -m playwright install chromium
```

6. Confirm Chrome exists at:

```text
C:\Program Files\Google\Chrome\Application\chrome.exe
```

If Chrome is somewhere else, set the correct path in the UI.

## Start The Web UI

Run:

```powershell
python web_server.py
```

This opens a local browser UI at:

```text
http://127.0.0.1:8765
```

The web UI has fields for:

- Canva design URL
- Google Photos shared album URL
- Single image path
- Google Photos download folder
- Output folder and output file name
- Chrome EXE path
- Chrome automation profile folder
- Debug port
- Canva placement values
- Timeout values
- Batch options

Click **Start** to run. Logs appear in the live log panel.

## First Login

The first run opens Chrome with a separate profile in:

```text
chrome_profiles\canva_automation_profile
```

If Canva asks for login, log in inside the opened Chrome window. The same profile is reused next time, so you usually only need to log in once per device.

## Run Modes

Use the default mode to download a Google Photos album and process every image.

Enable **Use existing images in photos folder** if the album was already downloaded and extracted.

Enable **Process only the single image** to skip Google Photos and process only the image path from the form.

Use **Max images** to test with a small number of images before running the full batch.

## Output

Processed images are saved to:

```text
assets\canva_download
```

For a batch, each output is named from the original image filename with `_bg_removed.jpg` added. For a single image, the UI uses the output name field.

## Troubleshooting

If Chrome does not open, check the **Chrome EXE** field.

If Canva asks for login repeatedly, delete only the automation profile folder and log in again:

```text
chrome_profiles\canva_automation_profile
```

If the process cannot connect to Chrome, change the debug port from `9223` to another unused port, for example `9224`.

If Canva UI clicks fail, increase the timeout values in the UI and try again.
