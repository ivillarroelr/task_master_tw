#Requires -Version 5.1
<#
.SYNOPSIS
    One-shot setup for TaskMaster (TaskWarrior wrapper for Windows + WSL2).
.DESCRIPTION
    Installs and configures: WSL2, Ubuntu, TaskWarrior, Python 3.11+, pipx, and the tw command.
    Run from the taskmaster/ directory.
.EXAMPLE
    powershell -ExecutionPolicy Bypass -File setup.ps1
#>

Set-StrictMode -Version Latest
# Use Continue so that stderr output from external tools (pip, pipx, wsl, winget)
# does not trigger a fatal PowerShell exception. We check $LASTEXITCODE explicitly.
$ErrorActionPreference = 'Continue'

# ── Helpers ────────────────────────────────────────────────────────────────

function Banner {
    param([string]$msg)
    Write-Host ""
    Write-Host "  $msg" -ForegroundColor Cyan
    Write-Host ("  " + ("-" * $msg.Length)) -ForegroundColor DarkGray
}

function OK   { param([string]$t) Write-Host "    [OK]  $t" -ForegroundColor Green  }
function Warn  { param([string]$t) Write-Host "    [!]   $t" -ForegroundColor Yellow }
function Info  { param([string]$t) Write-Host "          $t" -ForegroundColor DarkGray }

function Die {
    param([string]$t)
    Write-Host ""
    Write-Host "  [FAIL] $t" -ForegroundColor Red
    Write-Host ""
    Read-Host "Press Enter to exit"
    exit 1
}

function Refresh-Path {
    $env:PATH = [System.Environment]::GetEnvironmentVariable('PATH','Machine') + ';' +
                [System.Environment]::GetEnvironmentVariable('PATH','User')
}

function Find-Python {
    Refresh-Path
    # Check PATH commands first
    foreach ($c in @('python3','python','py')) {
        try {
            $v = & $c --version 2>&1
            if ($v -match 'Python 3\.(\d+)' -and [int]$Matches[1] -ge 11) { return $c }
        } catch {}
    }
    # Check common Windows installation paths (useful when running elevated)
    $roots = @(
        "$env:LOCALAPPDATA\Programs\Python",
        "$env:USERPROFILE\AppData\Local\Programs\Python",
        "C:\Python3",
        "C:\Program Files\Python3"
    )
    foreach ($root in $roots) {
        if (-not (Test-Path $root)) { continue }
        foreach ($dir in (Get-ChildItem $root -Directory -ErrorAction SilentlyContinue)) {
            $exe = Join-Path $dir.FullName 'python.exe'
            if (Test-Path $exe) {
                try {
                    $v = & $exe --version 2>&1
                    if ($v -match 'Python 3\.(\d+)' -and [int]$Matches[1] -ge 11) {
                        # Add this path to the session so subsequent calls work
                        $env:PATH = "$($dir.FullName);$env:PATH"
                        return $exe
                    }
                } catch {}
            }
        }
    }
    return $null
}

function Wsl-Run {
    # Run a bash one-liner in Ubuntu as default user; return output as string
    param([string]$cmd, [string]$user = '')
    $extra = if ($user) { @('-u', $user) } else { @() }
    $out = wsl -d Ubuntu @extra -- bash -c $cmd 2>&1
    return ($out -join "`n")
}

# ── Header ─────────────────────────────────────────────────────────────────

Write-Host ""
Write-Host "  +------------------------------------------+" -ForegroundColor Magenta
Write-Host "  |        TaskMaster  --  Setup             |" -ForegroundColor Magenta
Write-Host "  +------------------------------------------+" -ForegroundColor Magenta
Write-Host ""

# ── Step 1: WSL2 ───────────────────────────────────────────────────────────

Banner "Step 1 of 6 -- WSL2"

# Use wsl.exe presence as the install check — running "wsl echo ok" is too
# fragile (fails transiently if WSL is starting up or updating).
$wslExe = [bool](Get-Command wsl -ErrorAction SilentlyContinue)

if (-not $wslExe) {
    # WSL is genuinely not installed — need admin to enable Windows features
    $isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole('Administrator')

    if (-not $isAdmin) {
        Warn "WSL not installed. Relaunching as Administrator to install it..."
        $selfArgs = "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`""
        Start-Process powershell -ArgumentList $selfArgs -Verb RunAs -Wait
        exit $LASTEXITCODE
    }

    # Try modern one-liner (Windows 11 / WSL 2.0+)
    Info "Running: wsl --install --no-distribution"
    wsl --install --no-distribution 2>&1 | ForEach-Object { Info $_ }

    if ($LASTEXITCODE -ne 0) {
        Info "Enabling Windows features individually..."
        Enable-WindowsOptionalFeature -Online -FeatureName Microsoft-Windows-Subsystem-Linux -NoRestart -ErrorAction SilentlyContinue | Out-Null
        Enable-WindowsOptionalFeature -Online -FeatureName VirtualMachinePlatform             -NoRestart -ErrorAction SilentlyContinue | Out-Null
    }

    Write-Host ""
    Write-Host "  REBOOT REQUIRED. After rebooting, run this script again." -ForegroundColor Yellow
    Write-Host ""
    $ans = Read-Host "Reboot now? [Y/n]"
    if ($ans -notmatch '^[Nn]') { Restart-Computer -Force }
    exit
}

wsl --set-default-version 2 2>&1 | Out-Null
OK "WSL2 is ready"

# ── Step 2: Ubuntu ─────────────────────────────────────────────────────────

Banner "Step 2 of 6 -- Ubuntu"

# Detect Ubuntu by actually running a command in it (avoids UTF-16 list parsing issues)
$hasUbuntu = $false
try {
    $probe = wsl -d Ubuntu -u root -- bash -c "echo ok" 2>&1
    $hasUbuntu = ($probe -join '') -match 'ok'
} catch {}

if (-not $hasUbuntu) {
    Info "Installing Ubuntu (may take a few minutes)..."
    wsl --install -d Ubuntu --no-launch 2>&1 | ForEach-Object { Info $_ }

    # Exit code may be non-zero even on success if distro already exists in a broken state;
    # re-probe after install attempt
    $probeAfter = $false
    try {
        $p2 = wsl -d Ubuntu -u root -- bash -c "echo ok" 2>&1
        $probeAfter = ($p2 -join '') -match 'ok'
    } catch {}

    if (-not $probeAfter -and $LASTEXITCODE -ne 0) {
        Die "Ubuntu install failed. Try manually: wsl --install -d Ubuntu"
    }

    Write-Host ""
    Write-Host "  Ubuntu was just installed and needs first-time setup." -ForegroundColor Yellow
    Write-Host "  A terminal will open -- set your Unix username and password." -ForegroundColor Yellow
    Write-Host "  When done, type 'exit' and press Enter, then re-run this script." -ForegroundColor Yellow
    Write-Host ""
    Read-Host "Press Enter to open Ubuntu"
    Start-Process wsl -ArgumentList "-d Ubuntu" -Wait
    Write-Host ""
    Write-Host "  Re-run setup.ps1 to continue." -ForegroundColor Cyan
    Read-Host "Press Enter to exit"
    exit
}

$ubuntuTest = Wsl-Run "echo ok" "root"
if ($ubuntuTest -notmatch 'ok') {
    Die "Ubuntu is installed but not responding. Complete the first-time setup by opening Ubuntu manually, then re-run."
}

OK "Ubuntu distro is ready"

# ── Step 3: TaskWarrior ────────────────────────────────────────────────────

Banner "Step 3 of 6 -- TaskWarrior (inside WSL)"

$twVer = Wsl-Run "task --version 2>/dev/null" "root"
if ($twVer -match '\d+\.\d+') {
    OK "Already installed: TaskWarrior $twVer"
} else {
    Info "Running apt-get update..."
    wsl -d Ubuntu -u root -- bash -c "apt-get update -qq" 2>&1 | Select-Object -Last 2 | ForEach-Object { Info $_ }

    Info "Installing taskwarrior..."
    wsl -d Ubuntu -u root -- bash -c "DEBIAN_FRONTEND=noninteractive apt-get install -y taskwarrior" 2>&1 | Select-Object -Last 3 | ForEach-Object { Info $_ }

    if ($LASTEXITCODE -ne 0) { Die "apt-get failed. Check WSL network connectivity." }

    $twVer = Wsl-Run "task --version 2>/dev/null" "root"
    OK "TaskWarrior $twVer installed"
}

# Configure .taskrc for the default WSL user (no interactive wizard)
Info "Configuring TaskWarrior..."

wsl -d Ubuntu -- bash -c "mkdir -p ~/.task" 2>&1 | Out-Null

# Write a minimal .taskrc to skip the first-run data.location prompt
$initRc  = "test -f ~/.taskrc && echo exists || "
$initRc += "printf 'data.location=~/.task\nconfirmation=no\nverbosity=nothing\n' > ~/.taskrc"
wsl -d Ubuntu -- bash -c $initRc 2>&1 | Out-Null

# Set data.location via task config as well
wsl -d Ubuntu -- bash -c "task config data.location ~/.task 2>/dev/null; true" 2>&1 | Out-Null

OK "TaskWarrior configured (data.location=~/.task)"

# ── Step 4: Python 3.11+ ───────────────────────────────────────────────────

Banner "Step 4 of 6 -- Python 3.11+ (Windows)"

$pyCmd = Find-Python
if ($pyCmd) {
    $pyVer = (& $pyCmd --version 2>&1) -join ''
    OK "Found: $pyVer"
} else {
    Info "Python 3.11+ not found. Installing via winget..."
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        Die "winget not found. Install Python 3.11 from https://www.python.org/downloads/ then re-run."
    }
    # winget may return non-zero exit code due to msstore search failures
    # even when the install from the winget source succeeds. Check for Python
    # after the attempt instead of trusting the exit code.
    winget install --id Python.Python.3.11 --source winget --silent --accept-package-agreements --accept-source-agreements
    $wingetCode = $LASTEXITCODE
    Refresh-Path
    $pyCmd = Find-Python
    if (-not $pyCmd) {
        if ($wingetCode -ne 0) {
            Die "Python 3.11 install failed (winget exit $wingetCode). Install manually from https://www.python.org/downloads/ (check 'Add to PATH'), then re-run."
        }
        Die "Python installed but not found in PATH. Open a new terminal and re-run."
    }
    $pyVer = (& $pyCmd --version 2>&1) -join ''
    OK "$pyVer installed"
}

# ── Step 5: pipx ───────────────────────────────────────────────────────────

Banner "Step 5 of 6 -- pipx"

$hasPipx = [bool](Get-Command pipx -ErrorAction SilentlyContinue)

if ($hasPipx) {
    OK "pipx is already installed"
} else {
    Info "Installing pipx via pip..."
    & $pyCmd -m pip install --quiet --user --no-warn-script-location pipx 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) { Die "pip install pipx failed." }

    # Register pipx scripts folder in PATH for this session and future sessions
    & $pyCmd -m pipx ensurepath 2>&1 | Out-Null

    Refresh-Path

    # Manually add common pipx bin locations to the current session PATH
    $candidates = @(
        "$env:USERPROFILE\.local\bin",
        "$env:USERPROFILE\AppData\Roaming\Python\Python311\Scripts",
        "$env:USERPROFILE\AppData\Roaming\Python\Python312\Scripts",
        "$env:LOCALAPPDATA\Programs\Python\Python311\Scripts"
    )
    foreach ($p in $candidates) {
        if ((Test-Path $p) -and ($env:PATH -notlike "*$p*")) {
            $env:PATH = "$p;$env:PATH"
        }
    }

    OK "pipx installed"
}

# ── Step 6: tw command ─────────────────────────────────────────────────────

Banner "Step 6 of 6 -- tw command (TaskMaster)"

# The script lives inside the taskmaster/ directory
$tmDir = Split-Path -Parent $PSCommandPath
if (-not (Test-Path (Join-Path $tmDir 'pyproject.toml'))) {
    $tmDir = Join-Path $tmDir 'taskmaster'
    if (-not (Test-Path (Join-Path $tmDir 'pyproject.toml'))) {
        Die "Cannot find pyproject.toml. Run setup.ps1 from inside the taskmaster/ directory."
    }
}

Push-Location $tmDir
try {
    Info "Running: pipx install . --force"
    if (Get-Command pipx -ErrorAction SilentlyContinue) {
        pipx install . --force 2>&1 | ForEach-Object { Info $_ }
    } else {
        & $pyCmd -m pipx install . --force 2>&1 | ForEach-Object { Info $_ }
    }
    if ($LASTEXITCODE -ne 0) { Die "pipx install failed." }
} finally {
    Pop-Location
}

Refresh-Path

# ── Verify ─────────────────────────────────────────────────────────────────

Banner "Verification"

$twCmd = Get-Command tw -ErrorAction SilentlyContinue
if ($twCmd) {
    OK "tw command: $($twCmd.Source)"
} else {
    Warn "tw is not in PATH yet -- open a new terminal after this script finishes."
}

$wslVer = Wsl-Run "task --version 2>/dev/null"
if ($wslVer -match '\d') { OK "TaskWarrior in WSL: $wslVer" }

# ── Done ───────────────────────────────────────────────────────────────────

Write-Host ""
Write-Host "  +------------------------------------------------------+" -ForegroundColor Green
Write-Host "  |  Setup complete!  Open a new terminal and run:  tw  |" -ForegroundColor Green
Write-Host "  +------------------------------------------------------+" -ForegroundColor Green
Write-Host ""
Write-Host "  Quick-add examples:" -ForegroundColor Gray
Write-Host "    tw                                       opens the dashboard" -ForegroundColor DarkGray
Write-Host "    tw add `"!h Fix bug @work #api due:fri`"   add a high-priority task" -ForegroundColor DarkGray
Write-Host "    tw add `"Write report @personal`"          add a simple task" -ForegroundColor DarkGray
Write-Host "    tw done 3                                mark task 3 as done" -ForegroundColor DarkGray
Write-Host ""
Read-Host "Press Enter to exit"
