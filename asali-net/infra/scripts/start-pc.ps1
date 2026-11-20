# One command for one Windows computer of the four-computer run. Normally started by start-PC-A.cmd,
# start-PC-C.cmd or start-PC-D.cmd in the asali-net folder (double-click, or run them in a terminal).
#
#   powershell -ExecutionPolicy Bypass -File infra\scripts\start-pc.ps1 -Pc PC-A           start or restart
#   powershell -ExecutionPolicy Bypass -File infra\scripts\start-pc.ps1 -Pc PC-A -Fresh    reload the seeded data
#   powershell -ExecutionPolicy Bypass -File infra\scripts\start-pc.ps1 -Pc PC-A -Stop     stop
#
# This file only makes sure Docker is running and the Python 3.11 environment exists; infra\scripts\start_pc.py
# does the rest (databases, portal build, leftovers, data, the organisations).
param(
    [Parameter(Mandatory = $true)][ValidateSet('PC-A', 'PC-B', 'PC-C', 'PC-D')][string]$Pc,
    [switch]$Fresh,
    [switch]$Stop
)
$ErrorActionPreference = 'Continue'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
Set-Location $Root
try { $Host.UI.RawUI.WindowTitle = "Asali $Pc" } catch { }

function Say([string]$m) { Write-Host "[start] $m" }
function Fail([string]$m) {
    Write-Host ''
    Write-Host "[start] STOPPED: $m" -ForegroundColor Red
    Write-Host ''
    exit 1
}

# ---- Docker ----
if (-not $Stop) {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        Fail 'Docker is not installed. Install Docker Desktop (allow WSL 2 when it asks), start it once, then run this again.'
    }
    docker info *> $null
    if ($LASTEXITCODE -ne 0) {
        $desktop = Join-Path $env:ProgramFiles 'Docker\Docker\Docker Desktop.exe'
        if (-not (Test-Path $desktop)) { Fail 'Docker is installed but not running. Start Docker Desktop, then run this again.' }
        Say 'starting Docker Desktop (this can take a minute) ...'
        Start-Process $desktop
        $deadline = (Get-Date).AddMinutes(4)
        do {
            Start-Sleep -Seconds 5
            docker info *> $null
        } until ($LASTEXITCODE -eq 0 -or (Get-Date) -gt $deadline)
        if ($LASTEXITCODE -ne 0) { Fail 'Docker Desktop did not become ready within 4 minutes. Open it, wait until it says it is running, then run this again.' }
    }
    Say 'Docker is running'
}

# ---- Python 3.11 environment ----
$Py = Join-Path $Root '.venv\Scripts\python.exe'
function Test-Venv {
    if (-not (Test-Path $Py)) { return $false }
    & $Py -c "import sys, asali_node, asali_directory, psycopg, pymongo, yaml, httpx, uvicorn; sys.exit(0 if sys.version_info[:2] == (3, 11) else 1)" *> $null
    return ($LASTEXITCODE -eq 0)
}
function Test-Command([string]$exe, [string[]]$pre) {
    if (-not (Get-Command $exe -ErrorAction SilentlyContinue)) { return $false }
    & $exe @pre -c "import sys; sys.exit(0)" *> $null
    return ($LASTEXITCODE -eq 0)
}

if (-not (Test-Venv)) {
    Say 'setting up the Python 3.11 environment (first time only; a few minutes) ...'
    if (Get-Command uv -ErrorAction SilentlyContinue) {
        uv sync --python 3.11
    }
    elseif (Test-Command 'py' @('-3.11')) {
        py -3.11 -m venv --clear .venv
        & $Py -m pip install --disable-pip-version-check -r requirements.txt
    }
    else {
        # Any Python 3 can install uv, and uv fetches Python 3.11 by itself. The "python" that only opens the
        # Microsoft Store fails Test-Command, so it is skipped.
        $base = $null
        foreach ($c in @('py', 'python', 'python3')) { if (Test-Command $c @()) { $base = $c; break } }
        if ($base) {
            Say "installing uv with $base ..."
            & $base -m pip install --user --quiet --disable-pip-version-check uv
            & $base -m uv sync --python 3.11
        }
        elseif (Get-Command winget -ErrorAction SilentlyContinue) {
            Say 'no Python found: installing Python 3.11 with winget ...'
            winget install -e --id Python.Python.3.11 --silent --accept-package-agreements --accept-source-agreements
            $py311 = Join-Path $env:LOCALAPPDATA 'Programs\Python\Python311\python.exe'
            if (-not (Test-Path $py311)) { $py311 = Join-Path $env:ProgramFiles 'Python311\python.exe' }
            if (-not (Test-Path $py311)) { Fail 'Python 3.11 was installed but not found. Close this window and run the start file again.' }
            & $py311 -m venv --clear .venv
            & $Py -m pip install --disable-pip-version-check -r requirements.txt
        }
        else {
            Fail 'No Python found. Install Python 3.11 from python.org (tick "Add python.exe to PATH"), then run this again.'
        }
    }
    if (-not (Test-Venv)) { Fail 'the Python environment could not be set up (see the messages above).' }
    Say 'Python environment ready'
}

if (-not $Stop) { Say 'if Windows asks whether Python may use the network: tick Private AND Public, then Allow' }

$pyArgs = @('infra\scripts\start_pc.py', '--pc', $Pc)
if ($Fresh) { $pyArgs += '--fresh' }
if ($Stop) { $pyArgs += '--stop' }
& $Py @pyArgs
exit $LASTEXITCODE
