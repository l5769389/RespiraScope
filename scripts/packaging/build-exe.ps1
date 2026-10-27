param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $BuildArgs
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $ProjectRoot

if ($env:OS -ne "Windows_NT") {
    Write-Error "Build the Windows exe on Windows. PyInstaller cannot cross-compile from macOS/Linux."
    exit 2
}
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "uv is required. Install it with: winget install --id astral-sh.uv -e"
    Write-Host "Then reopen the terminal and run this script again."
    exit 2
}

uv run --frozen --python 3.13 --with "pyinstaller>=6.16" python scripts/packaging/build_exe.py @BuildArgs
exit $LASTEXITCODE
