$ErrorActionPreference = 'Stop'
$dest = 'portable/engine'
New-Item -ItemType Directory -Force $dest | Out-Null
$source = Resolve-Path '.runtime/build/Release'
$crt = Get-ChildItem "$env:VCToolsRedistDir/x64" -Directory -Filter '*.CRT' | Select-Object -First 1
$dirs = @($source.Path, "$env:CUDA_PATH/bin", $crt.FullName)
Copy-Item "$source/ace-server.exe" $dest
$queue = [Collections.Generic.Queue[string]]::new()
$queue.Enqueue('ace-server.exe')
foreach ($module in @('ggml-cpu.dll','ggml-cuda.dll')) {
    Copy-Item "$source/$module" $dest
    $queue.Enqueue($module)
}
while ($queue.Count) {
    $file = $queue.Dequeue()
    $deps = & dumpbin /nologo /dependents "$dest/$file"
    if ($LASTEXITCODE) { throw "dumpbin: $file" }
    foreach ($line in $deps) {
        $dll = $line.Trim()
        if ($dll -notmatch '^[\w.-]+\.dll$' -or (Test-Path "$dest/$dll")) { continue }
        $dep = $dirs | ForEach-Object { Join-Path $_ $dll } | Where-Object { Test-Path $_ } | Select-Object -First 1
        if ($dep) { Copy-Item $dep $dest; $queue.Enqueue($dll); continue }
        if ($dll -match '^(api-ms-|ext-ms-|nvcuda\.dll$)' -or (Test-Path "$env:SystemRoot/System32/$dll")) { continue }
        throw "DLL faltante: $dll"
    }
}
# cuBLAS dynamically loads its matching Lt library on some builds.
if (Test-Path "$dest/cublas64_12.dll") { Copy-Item "$env:CUDA_PATH/bin/cublasLt64_12.dll" $dest -Force }
Copy-Item .runtime/acestep.cpp/LICENSE "$dest/LICENSE-acestep.txt"
Copy-Item .runtime/acestep.cpp/ggml/LICENSE "$dest/LICENSE-ggml.txt"
Get-ChildItem $dest -File | ForEach-Object {
    [pscustomobject]@{name=$_.Name;sha256=(Get-FileHash $_.FullName).Hash;bytes=$_.Length}
} | ConvertTo-Json | Set-Content portable/engine-manifest.json -Encoding utf8
Copy-Item noel,scripts,docs,README.md,NoelMusicAI.cmd,THIRD_PARTY_NOTICES.md,LICENSE,requirements-ui.txt portable -Recurse
New-Item -ItemType Directory -Force portable/ui-wheels | Out-Null
foreach ($py in @('311','312','313','314')) {
    python -m pip download --only-binary=:all: --platform win_amd64 --implementation cp --python-version $py --dest portable/ui-wheels -r requirements-ui.txt
    if ($LASTEXITCODE) { throw "GUI wheel download failed for Python $py" }
}
python -m unittest discover -v
if ($LASTEXITCODE) { throw 'Unit tests failed' }
python -m tests.server_contract (Resolve-Path "$dest/ace-server.exe")
if ($LASTEXITCODE) { throw 'Server contract failed' }
(git -C .runtime/acestep.cpp rev-parse HEAD) | Set-Content portable/engine-revision.txt -Encoding utf8
Compress-Archive portable/* NoelMusicAI-Windows.zip
(Get-FileHash NoelMusicAI-Windows.zip).Hash | Set-Content NoelMusicAI-Windows.zip.sha256
