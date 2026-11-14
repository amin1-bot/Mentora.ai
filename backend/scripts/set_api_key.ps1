# Asks for your Anthropic API key (typing is hidden) and saves it in backend/.env.
# The key is never shown on screen and never stored in your command history.
# Run from anywhere:  powershell -ExecutionPolicy Bypass -File backend\scripts\set_api_key.ps1

$envFile = Join-Path (Split-Path $PSScriptRoot -Parent) ".env"

$secure = Read-Host "Paste your Anthropic API key, then press Enter" -AsSecureString
$ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try {
    $key = ([Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)).Trim().Trim('"', "'")
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
}

if (-not $key.StartsWith("sk-ant-")) {
    Write-Host "That doesn't look like an Anthropic key (they start with sk-ant-). Nothing saved." -ForegroundColor Red
    exit 1
}

# Keep every other line of .env, replace (or add) the ANTHROPIC_API_KEY line.
$lines = @()
if (Test-Path $envFile) {
    $lines = @(Get-Content $envFile | Where-Object { $_ -notmatch '^\s*ANTHROPIC_API_KEY\s*=' })
}
$lines += "ANTHROPIC_API_KEY=$key"
Set-Content -Path $envFile -Value $lines -Encoding ascii

Write-Host "Saved to $envFile ($($key.Length) characters). Restart the backend to use it." -ForegroundColor Green
