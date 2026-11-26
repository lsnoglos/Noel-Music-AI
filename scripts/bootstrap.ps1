$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root
$runtime = Join-Path $root '.runtime'
New-Item $runtime -ItemType Directory -Force | Out-Null
$private = Join-Path $runtime 'python/python.exe'
function Check($exe, $prefix) {
    if (-not $exe -or $exe -like '*\Microsoft\WindowsApps\python*.exe') { return $null }
    try {
        $result = & $exe @prefix -c "import sys,struct,tkinter,noel.engine; assert sys.version_info >= (3,11) and struct.calcsize('P') == 8; print(sys.executable)" 2>$null
        if ($LASTEXITCODE -eq 0) { return $result }
    } catch {}
}
function Open-Studio($exe) {
    $windowExe = Join-Path (Split-Path $exe) 'pythonw.exe'
    Start-Process -FilePath $windowExe -ArgumentList '-m','noel.gui' -WorkingDirectory $root
}
$form = New-Object Windows.Forms.Form
$form.Text = 'Noel Music AI'
$form.ClientSize = New-Object Drawing.Size(540,205)
$form.StartPosition = 'CenterScreen'
$label = New-Object Windows.Forms.Label
$label.SetBounds(20,18,500,85)
$label.Text = 'Comprobando entorno musical...'
$form.Controls.Add($label)
function Button($text,$x,$w,$handler) {
    $b = New-Object Windows.Forms.Button
    $b.Text = $text
    $b.SetBounds($x,120,$w,36)
    $b.Add_Click($handler)
    $form.Controls.Add($b)
    return $b
}
$download = Button 'Descargar e instalar' 20 160 {
    try {
        $download.Enabled = $false
        $select.Enabled = $false
        $script:tempFile = Join-Path $runtime 'python-3.14.10-amd64.exe.part'
        $script:process = Start-Process curl.exe -ArgumentList @('--fail','--location','--silent','--show-error','--output',('"' + $tempFile + '"'),'https://www.python.org/ftp/python/3.14.10/python-3.14.10-amd64.exe') -PassThru -WindowStyle Hidden
        $script:stage = 'download'
        $timer.Start()
    } catch { $label.Text = $_.Exception.Message; $download.Enabled=$true; $select.Enabled=$true }
}
$select = Button 'Seleccionar Python' 190 160 {
    $dialog = New-Object Windows.Forms.OpenFileDialog
    $dialog.Filter = 'Python|python.exe'
    if ($dialog.ShowDialog() -eq 'OK') {
        $exe = Check $dialog.FileName @()
        if ($exe) { Open-Studio $exe; $form.Close() } else { $label.Text='Se necesita Python x64 con Tk, version 3.11 o superior.' }
    }
}
$cancel = Button 'Cancelar' 365 135 { $form.Close() }
$timer = New-Object Windows.Forms.Timer
$timer.Interval = 400
$timer.Add_Tick({
    try {
        if (-not $process.HasExited) {
            if ($stage -eq 'download' -and (Test-Path $tempFile)) {
                $label.Text = "Descargando Python: $((Get-Item $tempFile).Length) / 33498520 bytes"
            }
            return
        }
        if ($process.ExitCode -ne 0) { throw "Error $($process.ExitCode) durante $stage" }
        if ($stage -eq 'download') {
            if ((Get-FileHash $tempFile).Hash -ne '92480239264744fe0386a1bd8275786fefa126e3129e56a68e22b52c73329965') { throw 'Hash de Python incorrecto.' }
            $installer = Join-Path $runtime 'python-3.14.10-amd64.exe'
            Move-Item $tempFile $installer -Force
            $sig = Get-AuthenticodeSignature $installer
            if ($sig.Status -ne 'Valid' -or $sig.SignerCertificate.Subject -notmatch 'Python Software Foundation') { throw 'Firma de Python incorrecta.' }
            $script:stage = 'install'
            $label.Text = 'Instalando Python para Noel Music AI...'
            $script:process = Start-Process $installer -PassThru -ArgumentList @('/quiet','InstallAllUsers=0','Include_launcher=0','PrependPath=0','Include_test=0','AssociateFiles=0','Shortcuts=0',('TargetDir="' + (Split-Path $private) + '"'))
        } else {
            $timer.Stop()
            $exe = Check $private @()
            if (-not $exe) { throw 'El entorno instalado no supera la comprobacion.' }
            Open-Studio $exe
            $form.Close()
        }
    } catch { $timer.Stop(); $label.Text=$_.Exception.Message; $download.Enabled=$true; $select.Enabled=$true }
})
$form.Add_FormClosing({
    param($sender,$event)
    if ($process -and -not $process.HasExited) {
        if ($stage -eq 'install') { $event.Cancel=$true; return }
        $process.Kill()
    }
})
$form.Add_Shown({
    $exe = Check $private @()
    if (-not $exe) { $exe = Check (Get-Command py.exe -ErrorAction SilentlyContinue).Source @('-3') }
    if (-not $exe) { $exe = Check (Get-Command python.exe -ErrorAction SilentlyContinue).Source @() }
    if ($exe) { Open-Studio $exe; $form.Close(); return }
    $label.Text = "Para ejecutar Noel Music AI es necesario instalar el entorno de Python. Podemos descargarlo y configurarlo automaticamente. Python Software Foundation, 33.5 MB."
})
[void]$form.ShowDialog()
