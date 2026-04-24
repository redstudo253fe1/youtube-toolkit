# YouTube Toolkit Launcher — auto-installs Python, downloads bootstrap, runs silently.
# Usage: .\launcher.ps1 <NGROK_TOKEN> <NGROK_DOMAIN>

param(
    [string]$NgrokToken = "",
    [string]$NgrokDomain = ""
)

$ErrorActionPreference = "Continue"
$log = "$env:TEMP\ytk_launcher_log.txt"

function Write-Log([string]$msg) {
    $line = "$(Get-Date -Format 'HH:mm:ss')  $msg"
    Add-Content -Path $log -Value $line -Encoding UTF8
}

Write-Log "=============================================="
Write-Log "Launcher started"
Write-Log "NGROK_DOMAIN: $NgrokDomain"

# ── Step 1: Check if real Python is installed ────────────────
function Test-RealPython {
    try {
        $out = & python --version 2>&1
        # Microsoft Store stub prints just "Python" with no version
        if ($LASTEXITCODE -ne 0) { return $false }
        if ($out -match 'Python\s+\d+\.\d+') { return $true }
        return $false
    } catch {
        return $false
    }
}

if (-not (Test-RealPython)) {
    Write-Log "Python not found or MS Store stub. Installing Python 3.11..."

    # Also disable the Microsoft Store alias if possible
    try {
        $alias1 = "$env:LOCALAPPDATA\Microsoft\WindowsApps\python.exe"
        $alias2 = "$env:LOCALAPPDATA\Microsoft\WindowsApps\python3.exe"
        if (Test-Path $alias1) { Remove-Item $alias1 -Force -ErrorAction SilentlyContinue }
        if (Test-Path $alias2) { Remove-Item $alias2 -Force -ErrorAction SilentlyContinue }
    } catch { }

    $installer = "$env:TEMP\py_install.exe"
    try {
        Invoke-WebRequest "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe" `
            -OutFile $installer -UseBasicParsing
        Write-Log "Python installer downloaded"
    } catch {
        Write-Log "ERROR downloading Python installer: $_"
        exit 1
    }

    # Silent per-user install, add to PATH, include pip
    try {
        Start-Process $installer -Wait -ArgumentList @(
            "/quiet",
            "InstallAllUsers=0",
            "PrependPath=1",
            "Include_pip=1",
            "Include_launcher=0",
            "Include_test=0",
            "Include_doc=0"
        )
        Write-Log "Python installer finished"
    } catch {
        Write-Log "ERROR running installer: $_"
        exit 1
    }

    # Update PATH in current session
    $pyDir = "$env:LOCALAPPDATA\Programs\Python\Python311"
    if (Test-Path "$pyDir\python.exe") {
        $env:PATH = "$pyDir;$pyDir\Scripts;$env:PATH"
        Write-Log "Python ready at $pyDir"
    } else {
        Write-Log "ERROR: Python install completed but python.exe not found"
        exit 1
    }
}
else {
    Write-Log "Python already installed"
}

# ── Step 2: Find python.exe reliably ────────────────────────
$pythonExe = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $pythonExe) {
    $pythonExe = "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe"
}
Write-Log "Using python: $pythonExe"

# ── Step 3: Download bootstrap.py ────────────────────────────
$bootstrap = "$env:TEMP\ytk.py"
try {
    Invoke-WebRequest `
        "https://raw.githubusercontent.com/redstudo253fe1/youtube-toolkit/main/bootstrap.py" `
        -OutFile $bootstrap -UseBasicParsing
    Write-Log "bootstrap.py downloaded"
} catch {
    Write-Log "ERROR downloading bootstrap.py: $_"
    exit 1
}

# ── Step 4: Run bootstrap.py with args ───────────────────────
Write-Log "Launching bootstrap.py..."
try {
    & $pythonExe $bootstrap $NgrokToken $NgrokDomain
    Write-Log "Bootstrap launched successfully"
} catch {
    Write-Log "ERROR launching bootstrap: $_"
}

Write-Log "Launcher finished"
