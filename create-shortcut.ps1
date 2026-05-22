# 바탕화면에 민티스페이스 바로가기 만들기
$desktop = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktop "민티스페이스.lnk"
$targetPath = Join-Path $PSScriptRoot "start.bat"
$workingDir = $PSScriptRoot
$iconPath = Join-Path $PSScriptRoot "web\assets\icon.ico"

$WshShell = New-Object -comObject WScript.Shell
$shortcut = $WshShell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $targetPath
$shortcut.WorkingDirectory = $workingDir
$shortcut.WindowStyle = 7  # Minimized
$shortcut.Description = "민티스페이스 워크스페이스 시작"
if (Test-Path $iconPath) {
    $shortcut.IconLocation = $iconPath
}
$shortcut.Save()

Write-Host "✅ 바탕화면 바로가기 생성됨: $shortcutPath"
Write-Host "더블클릭하면 헬퍼 시작 + 브라우저 자동 오픈"
