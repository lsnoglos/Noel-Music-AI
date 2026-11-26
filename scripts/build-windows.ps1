$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
$src = Join-Path $root ".runtime/acestep.cpp"
$build = Join-Path $root ".runtime/build"
$rev = "973517be024ff8b6bbd50e0adc9e308ab2ed71b3"
function Run([string]$Program, [string[]]$Arguments) {
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Program fallo con codigo $LASTEXITCODE" }
}
foreach ($tool in @("git", "cmake", "cl", "nvcc", "ninja")) {
    if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) {
        throw "Falta $tool. Abra Developer PowerShell x64 y revise docs/installation/WINDOWS.md."
    }
}
if (-not (Test-Path $src)) {
    Run git @("clone", "--no-checkout", "https://github.com/ServeurpersoCom/acestep.cpp.git", $src)
}
$origin = & git -C $src remote get-url origin
if ($origin -ne "https://github.com/ServeurpersoCom/acestep.cpp.git") { throw "Origen inesperado en $src" }
# A fresh --no-checkout clone has staged deletions; never discard existing edits.
if (Test-Path (Join-Path $src "CMakeLists.txt")) {
    $dirty = & git -C $src status --porcelain
    if ($LASTEXITCODE -ne 0 -or $dirty) { throw "Revise los cambios locales en $src antes de compilar." }
}
Run git @("-C", $src, "checkout", "--detach", $rev)
Run git @("-C", $src, "submodule", "update", "--init", "--recursive")
Run cmake @("-S", $src, "-B", $build, "-G", "Ninja Multi-Config", "-DGGML_CUDA=ON", "-DGGML_BACKEND_DL=ON", "-DGGML_NATIVE=OFF", "-DCMAKE_CUDA_ARCHITECTURES=86")
Run cmake @("--build", $build, "--config", "Release", "--target", "ace-server", "ggml-cpu", "ggml-cuda", "--parallel", "2")
