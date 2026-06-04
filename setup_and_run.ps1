$ErrorActionPreference = "Stop"

Set-Location -LiteralPath $PSScriptRoot

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Get-PythonCommand {
    $commands = @(
        @("py", "-3"),
        @("python", $null),
        @("python3", $null)
    )

    foreach ($candidate in $commands) {
        $exe = $candidate[0]
        $arg = $candidate[1]
        try {
            if ($arg) {
                & $exe $arg --version *> $null
            } else {
                & $exe --version *> $null
            }

            if ($LASTEXITCODE -eq 0) {
                return $candidate
            }
        } catch {
        }
    }

    throw "Python 3 was not found. Install Python from https://www.python.org/downloads/windows/ and enable 'Add python.exe to PATH'."
}

$venvPath = Join-Path $PSScriptRoot ".venv"
$venvPython = Join-Path $venvPath "Scripts\python.exe"

Write-Host "Canva Background Remover setup for Windows" -ForegroundColor Green
Write-Host "Project folder: $PSScriptRoot"

Write-Step "Checking Python"
$pythonCommand = Get-PythonCommand
Write-Host "Using: $($pythonCommand -join ' ')"

if (!(Test-Path -LiteralPath $venvPython)) {
    Write-Step "Creating virtual environment"
    if ($pythonCommand[1]) {
        & $pythonCommand[0] $pythonCommand[1] -m venv ".venv"
    } else {
        & $pythonCommand[0] -m venv ".venv"
    }
} else {
    Write-Step "Using existing virtual environment"
}

Write-Step "Upgrading pip"
& $venvPython -m pip install --upgrade pip

Write-Step "Installing Python packages"
& $venvPython -m pip install -r requirements.txt

Write-Step "Downloading Playwright browser files"
& $venvPython -m playwright install chromium

Write-Step "Creating local folders"
$folders = @(
    "assets",
    "assets\canva_download",
    "assets\google_photos_downloads",
    "assets\perfect_car_images",
    "chrome_profiles"
)

foreach ($folder in $folders) {
    $fullPath = Join-Path $PSScriptRoot $folder
    if (!(Test-Path -LiteralPath $fullPath)) {
        New-Item -ItemType Directory -Path $fullPath | Out-Null
    }
}

Write-Step "Checking Google Chrome"
$chromePath = "C:\Program Files\Google\Chrome\Application\chrome.exe"
if (Test-Path -LiteralPath $chromePath) {
    Write-Host "Chrome found: $chromePath"
} else {
    Write-Host "Chrome was not found at the default path." -ForegroundColor Yellow
    Write-Host "Install Chrome from https://www.google.com/chrome/ or set the Chrome EXE path in the web UI." -ForegroundColor Yellow
}

Write-Step "Starting web UI"
Write-Host "Open this URL if the browser does not open automatically:"
Write-Host "http://127.0.0.1:8765" -ForegroundColor Green
Write-Host ""
Write-Host "Keep this window open while using the UI. Press Ctrl+C here to stop the server." -ForegroundColor Yellow
& $venvPython web_server.py
