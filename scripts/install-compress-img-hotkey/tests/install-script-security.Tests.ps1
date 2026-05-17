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
