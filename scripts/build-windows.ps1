$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')
python -m pip install -r requirements-build-windows.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
python scripts/smoke_test.py
if ($LASTEXITCODE -ne 0) { throw 'Source smoke test failed' }
python -m PyInstaller --clean --noconfirm --onefile --windowed --name clips-1.0-windows-x86_64 --add-data 'assets:assets' --add-data 'LICENSE:.' mascote.py
if ($LASTEXITCODE -ne 0) { throw 'Build failed' }
python scripts/smoke_test.py dist/clips-1.0-windows-x86_64.exe
if ($LASTEXITCODE -ne 0) { throw 'Executable smoke test failed' }
Compress-Archive -Path dist/clips-1.0-windows-x86_64.exe,LICENSE,README.md -DestinationPath dist/clips-1.0-windows-x86_64.zip -Force
git archive --format=zip --output=dist/clips-1.0-windows-source.zip HEAD
if ($LASTEXITCODE -ne 0) { throw 'Source archive failed' }
$names = @('clips-1.0-windows-x86_64.exe', 'clips-1.0-windows-x86_64.zip', 'clips-1.0-windows-source.zip')
$lines = foreach ($name in $names) {
    $hash = (Get-FileHash "dist/$name" -Algorithm SHA256).Hash.ToLowerInvariant()
    "$hash  $name"
}
[System.IO.File]::WriteAllText((Join-Path $PWD 'dist/SHA256SUMS-windows.txt'), (($lines -join "`n") + "`n"), [System.Text.UTF8Encoding]::new($false))
