# Asks for your free Google Gemini API key (typing is hidden) and saves it in backend/.env,
# switching the teacher to Gemini. The key is never shown on screen or kept in history.
# Free tier: for made-up test students only, never real students.
# Run from anywhere:  powershell -ExecutionPolicy Bypass -File backend\scripts\set_gemini_key.ps1

$envFile = Join-Path (Split-Path $PSScriptRoot -Parent) ".env"

$secure = Read-Host "Paste your Gemini API key, then press Enter" -AsSecureString
$ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try {
    $key = ([Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)).Trim().Trim('"', "'")
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
}

if (-not $key.StartsWith("AIza") -or $key.Length -lt 30) {
    Write-Host "That doesn't look like a Gemini key (they start with AIza and are about 39 characters). Nothing saved." -ForegroundColor Red
    exit 1
}

# Keep every other line of .env, replace (or add) the provider and key lines.
$lines = @()
if (Test-Path $envFile) {
    $lines = @(Get-Content $envFile | Where-Object { $_ -notmatch '^\s*(AI_PROVIDER|AI_API_KEY)\s*=' })
}
$lines += "AI_PROVIDER=openai_compatible"
$lines += "AI_API_KEY=$key"
Set-Content -Path $envFile -Value $lines -Encoding ascii

Write-Host "Saved to $envFile ($($key.Length) characters). Tell Claude it's done." -ForegroundColor Green
