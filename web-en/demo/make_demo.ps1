# Regenerates a demo video (+ .srt) end to end.
#   powershell -File make_demo.ps1                -> out/x-treats-demo-v2.mp4 (default)
#   powershell -File make_demo.ps1 -Version v1    -> out/x-treats-demo.mp4
# Requires: the web-en server running (default http://127.0.0.1:5051) with no active run, a free GPU,
# Python 3.13 with edge-tts (narration), Python 3.7 with imageio-ffmpeg + numpy, Node 22+, Chrome.
param(
  [string]$Version = "v2",
  [string]$Url   = "http://127.0.0.1:5051",
  [string]$Py313 = "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe",
  [string]$Py37  = "$env:LOCALAPPDATA\Programs\Python\Python37\python.exe"
)
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Push-Location $here
try {
  $env:FFMPEG = (& $Py37 -c "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())").Trim()
  $env:PYTHONIOENCODING = "utf-8"
  $env:DEMO_VERSION = $Version
  Write-Host "1/3  Narration (edge-tts)";  & $Py313 tts.py;           if ($LASTEXITCODE) { throw "tts.py failed" }
  Write-Host "2/3  Recording (real run)";  $env:XT_URL = $Url; node record_demo.js; if ($LASTEXITCODE) { throw "record_demo.js failed" }
  Write-Host "3/3  Assembling video";      & $Py37 assemble.py;       if ($LASTEXITCODE) { throw "assemble.py failed" }
  $name = if ($Version -eq "v1") { "x-treats-demo" } else { "x-treats-demo-$Version" }
  Write-Host "Done: $here\out\$name.mp4"
} finally { Pop-Location }
