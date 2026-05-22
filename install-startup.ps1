# 부팅 시 mintspace 헬퍼 자동 시작 등록 (Windows 시작 프로그램 폴더)
# 헬퍼만 백그라운드 켜고, 브라우저는 열지 않음 (--no-browser 옵션)
#
# 사용: PowerShell에서 한 번만 실행
#   powershell -ExecutionPolicy Bypass -File install-startup.ps1
#
# 제거: shell:startup 폴더의 "민티스페이스 헬퍼 자동시작.lnk" 삭제

$startup = [Environment]::GetFolderPath("Startup")
$shortcutPath = Join-Path $startup "민티스페이스 헬퍼 자동시작.lnk"
$targetPath = Join-Path $PSScriptRoot "start.bat"
$workingDir = $PSScriptRoot
$iconPath = Join-Path $PSScriptRoot "web\assets\icon.ico"

$WshShell = New-Object -comObject WScript.Shell
$shortcut = $WshShell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $targetPath
$shortcut.Arguments = "--no-browser"
$shortcut.WorkingDirectory = $workingDir
$shortcut.WindowStyle = 7  # Minimized
$shortcut.Description = "부팅 시 mintspace 헬퍼 백그라운드 시작 (브라우저 X)"
if (Test-Path $iconPath) {
    $shortcut.IconLocation = $iconPath
}
$shortcut.Save()

Write-Host ""
Write-Host "[OK] 시작 프로그램 등록됨" -ForegroundColor Green
Write-Host "  위치: $shortcutPath"
Write-Host ""
Write-Host "다음 부팅부터 헬퍼가 백그라운드로 자동 켜짐."
Write-Host "지금 바로 켜고 싶으면:"
Write-Host "  start.bat --no-browser   (헬퍼만)"
Write-Host "  start.bat                (헬퍼 + 브라우저 자동 오픈)"
Write-Host ""
Write-Host "제거하려면 이 파일 삭제:"
Write-Host "  $shortcutPath"
