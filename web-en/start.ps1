# Starts the X-TREATS web interface. Picks the first Python that has Flask + lemon + torch.
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$candidates = @(
  "$env:LOCALAPPDATA\Programs\Python\Python37\python.exe",
  (Get-Command python -ErrorAction SilentlyContinue).Source
) | Where-Object { $_ -and (Test-Path $_) }
foreach ($py in $candidates) {
  & $py -c "import flask, lemon, torch" 2>$null
  if ($LASTEXITCODE -eq 0) { Write-Host "Using $py"; & $py "$here\app.py"; exit }
}
Write-Error "No Python with flask, lemon and torch found. Activate the right environment and run: python web-en/app.py"
