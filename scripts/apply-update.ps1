$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms
$dialog = New-Object Windows.Forms.FolderBrowserDialog
$dialog.Description = 'Selecciona la carpeta donde ya tienes instalado Noel Music AI.'
if ($dialog.ShowDialog() -ne 'OK') { exit 0 }
$target = $dialog.SelectedPath
$answer = [Windows.Forms.MessageBox]::Show('Cierra Noel Music AI y su motor antes de continuar. Tus modelos, canciones y configuraciones se conservarán. ¿Aplicar actualización?', 'Noel Music AI', 'YesNo', 'Question')
if ($answer -ne 'Yes') { exit 0 }
try {
    $python = Join-Path $target '.runtime/python/python.exe'
    $script = Join-Path $PSScriptRoot 'apply_update.py'
    if (Test-Path $python) {
        & $python $script $target
    } elseif (Get-Command py.exe -ErrorAction SilentlyContinue) {
        & py.exe -3 $script $target
    } elseif (Get-Command python.exe -ErrorAction SilentlyContinue) {
        & python.exe $script $target
    } else { throw 'No se encontró Python. Usa el paquete completo.' }
    if ($LASTEXITCODE -ne 0) { throw 'La actualización no pudo completarse. Revisa la consola.' }
    [void][Windows.Forms.MessageBox]::Show('Actualización aplicada. Abre NoelMusicAI.cmd en tu carpeta habitual.', 'Noel Music AI')
} catch {
    [void][Windows.Forms.MessageBox]::Show($_.Exception.Message, 'Noel Music AI')
    exit 1
}
