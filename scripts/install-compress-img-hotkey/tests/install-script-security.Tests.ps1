$ErrorActionPreference = "Stop"

$InstallerPath = Join-Path $PSScriptRoot "..\install-compress-img-hotkey.ps1"
$Installer = Get-Content -Raw -Path $InstallerPath

function Assert-Contains {
  param(
    [Parameter(Mandatory = $true)][string]$Text,
    [Parameter(Mandatory = $true)][string]$Pattern,
    [Parameter(Mandatory = $true)][string]$Message
  )

  if ($Text -notmatch $Pattern) {
    throw $Message
  }
}

Assert-Contains `
  -Text $Installer `
  -Pattern '\$TaskDir\s*=\s*Join-Path\s+\$env:ProgramData\s+"CompressImgHotkey"' `
  -Message "Elevated task command must live under ProgramData, not the user profile."

Assert-Contains `
  -Text $Installer `
  -Pattern 'SetAccessRuleProtection\(\$true,\s*\$false\)' `
  -Message "The elevated task directory must disable inherited user-writable ACLs."

Assert-Contains `
  -Text $Installer `
  -Pattern 'S-1-5-32-544' `
  -Message "The protected task directory must grant Administrators access by SID."

Assert-Contains `
  -Text $Installer `
  -Pattern 'S-1-5-18' `
  -Message "The protected task directory must grant SYSTEM access by SID."

Assert-Contains `
  -Text $Installer `
  -Pattern '\[System\.Security\.Principal\.WindowsIdentity\]::GetCurrent\(\)\.Name' `
  -Message "Scheduled task principal must use the fully-qualified current Windows identity."

Assert-Contains `
  -Text $Installer `
  -Pattern 'Test-IsRunningAsAdministrator' `
  -Message "Installer must check administrator rights before registering an elevated scheduled task."

Assert-Contains `
  -Text $Installer `
  -Pattern 'Start-Process[\s\S]+-Verb\s+RunAs' `
  -Message "Installer must request UAC elevation when it is not already elevated."

Assert-Contains `
  -Text $Installer `
  -Pattern '无法请求管理员权限' `
  -Message "Installer must give a clear Chinese error when UAC elevation cannot be started."

if ($Installer -match 'New-ScheduledTaskPrincipal[^\r\n]+-UserId\s+\$env:USERNAME') {
  throw "Scheduled task principal must not use the short USERNAME value."
}

Assert-Contains `
  -Text $Installer `
  -Pattern 'function\s+Register-HotkeyScheduledTask' `
  -Message "Installer must wrap scheduled task registration so it can verify the actual task state."

Assert-Contains `
  -Text $Installer `
  -Pattern 'New-Object\s+-ComObject\s+"Schedule\.Service"' `
  -Message "Installer must use the Task Scheduler COM API instead of the unreliable ScheduledTasks module."

Assert-Contains `
  -Text $Installer `
  -Pattern 'RegisterTaskDefinition' `
  -Message "Installer must register the task through the Task Scheduler COM API."

Assert-Contains `
  -Text $Installer `
  -Pattern 'SetSecurityDescriptor' `
  -Message "Installer must grant the unelevated user permission to run the elevated task."

Assert-Contains `
  -Text $Installer `
  -Pattern 'GRGX' `
  -Message "Scheduled task security descriptor must grant read/execute rights to the current user."

Assert-Contains `
  -Text $Installer `
  -Pattern 'Get-ScheduledTask\s+-TaskName\s+\$TaskName' `
  -Message "Installer must verify that the scheduled task exists after registration."

if ($Installer -match 'Register-ScheduledTask') {
  throw "Installer must not use Register-ScheduledTask in this environment."
}

if ($Installer -match 'Arguments\s*=\s*"/run /tn ""') {
  throw "Hotkey C# source must use C# string escaping for the schtasks argument."
}

$HotkeySourceMatch = [regex]::Match($Installer, '(?s)\$cs\s*=\s*@"\r?\n(.*?)\r?\n"@')
if (-not $HotkeySourceMatch.Success) {
  throw "Installer must contain the hotkey C# source block."
}

$TempExeFile = Join-Path $PSScriptRoot "CompressImgHotkey.compile-check.tmp.exe"
try {
  Add-Type `
    -TypeDefinition $HotkeySourceMatch.Groups[1].Value `
    -ReferencedAssemblies System.Windows.Forms,System.Drawing `
    -OutputAssembly $TempExeFile `
    -OutputType WindowsApplication
}
finally {
  if (Test-Path -LiteralPath $TempExeFile) {
    Remove-Item -LiteralPath $TempExeFile -Force
  }
}

$StopIndex = $Installer.IndexOf("Stop-Process -Id")
$CompileIndex = $Installer.IndexOf("Add-Type")

if ($StopIndex -lt 0) {
  throw "Installer must stop an existing CompressImgHotkey process before rebuilding the exe."
}

if ($CompileIndex -lt 0) {
  throw "Installer must compile the hotkey exe."
}

if ($StopIndex -gt $CompileIndex) {
  throw "Existing hotkey process must be stopped before Add-Type rebuilds the exe."
}

Assert-Contains `
  -Text $Installer `
  -Pattern '-OutputAssembly\s+\$TempExeFile' `
  -Message "Installer should build to a temporary exe before replacing the installed exe."

Write-Host "install script security checks passed"
