#requires -version 5.1

param(
  [string]$LogFile
)

$ErrorActionPreference = "Stop"

$UserDir = Join-Path $env:LOCALAPPDATA "CompressImgHotkey"
$TaskDir = Join-Path $env:ProgramData "CompressImgHotkey"
$TaskName = "CompressImgClipboard65"
$CmdFile = Join-Path $TaskDir "run-compress-img.cmd"
$ExeFile = Join-Path $UserDir "CompressImgHotkey.exe"
$InstallLogFile = if ($LogFile) { $LogFile } else { Join-Path $UserDir "install.log" }

function Write-InstallLog {
  param(
    [Parameter(Mandatory = $true)]
    [string]$Message
  )

  $Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
  Add-Content -Encoding UTF8 -Path $InstallLogFile -Value ("[{0}] {1}" -f $Timestamp, $Message)
}

New-Item -ItemType Directory -Force -Path $UserDir | Out-Null

trap {
  Write-InstallLog ("安装失败：{0}" -f $_.Exception.Message)
  if ($_.InvocationInfo -and $_.InvocationInfo.PositionMessage) {
    Write-InstallLog $_.InvocationInfo.PositionMessage
  }
  if ($_.ScriptStackTrace) {
    Write-InstallLog $_.ScriptStackTrace
  }
  exit 1
}

function Get-CurrentWindowsUserId {
  [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
}

function Get-CurrentWindowsUserSid {
  [System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value
}

function Test-IsRunningAsAdministrator {
  $Identity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
  $Principal = New-Object System.Security.Principal.WindowsPrincipal($Identity)
  $Principal.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Protect-AdminOnlyDirectory {
  param(
    [Parameter(Mandatory = $true)]
    [string]$Path
  )

  New-Item -ItemType Directory -Force -Path $Path | Out-Null

  $Acl = New-Object System.Security.AccessControl.DirectorySecurity
  $Acl.SetAccessRuleProtection($true, $false)

  $InheritanceFlags = [System.Security.AccessControl.InheritanceFlags]"ContainerInherit,ObjectInherit"
  $PropagationFlags = [System.Security.AccessControl.PropagationFlags]::None
  $Rights = [System.Security.AccessControl.FileSystemRights]::FullControl
  $Allow = [System.Security.AccessControl.AccessControlType]::Allow

  foreach ($SidValue in @("S-1-5-18", "S-1-5-32-544")) {
    $Sid = New-Object System.Security.Principal.SecurityIdentifier($SidValue)
    $Rule = New-Object System.Security.AccessControl.FileSystemAccessRule(
      $Sid,
      $Rights,
      $InheritanceFlags,
      $PropagationFlags,
      $Allow
    )
    $Acl.AddAccessRule($Rule)
  }

  Set-Acl -Path $Path -AclObject $Acl
}

function Stop-InstalledHotkeyProcess {
  param(
    [Parameter(Mandatory = $true)]
    [string]$ExePath
  )

  $HotkeyProcessName = [System.IO.Path]::GetFileNameWithoutExtension($ExePath)
  $FullExePath = [System.IO.Path]::GetFullPath($ExePath)
  $Processes = Get-Process -Name $HotkeyProcessName -ErrorAction SilentlyContinue | Where-Object {
    try {
      $_.Path -and [string]::Equals(
        [System.IO.Path]::GetFullPath($_.Path),
        $FullExePath,
        [System.StringComparison]::OrdinalIgnoreCase
      )
    }
    catch {
      $false
    }
  }

  foreach ($Process in $Processes) {
    Write-Host "正在停止旧的热键程序：$($Process.Id)"
    Stop-Process -Id $Process.Id -Force -ErrorAction SilentlyContinue
    try {
      $Process.WaitForExit(5000) | Out-Null
    }
    catch {
      # 进程可能已经退出；继续安装即可。
    }
  }
}

function Register-HotkeyScheduledTask {
  param(
    [Parameter(Mandatory = $true)]
    [string]$UserId,

    [Parameter(Mandatory = $true)]
    [string]$UserSid,

    [Parameter(Mandatory = $true)]
    [string]$CommandPath
  )

  $TaskService = New-Object -ComObject "Schedule.Service"
  $TaskService.Connect()

  $RootFolder = $TaskService.GetFolder("\")
  $TaskDefinition = $TaskService.NewTask(0)

  $TaskDefinition.RegistrationInfo.Description = "Run compress-img clipboard compression at 65 KB with elevated privileges."
  $TaskDefinition.Principal.UserId = $UserId
  $TaskDefinition.Principal.LogonType = 3 # TASK_LOGON_INTERACTIVE_TOKEN
  $TaskDefinition.Principal.RunLevel = 1 # TASK_RUNLEVEL_HIGHEST

  $TaskDefinition.Settings.Enabled = $true
  $TaskDefinition.Settings.AllowDemandStart = $true
  $TaskDefinition.Settings.DisallowStartIfOnBatteries = $false
  $TaskDefinition.Settings.StopIfGoingOnBatteries = $false
  $TaskDefinition.Settings.ExecutionTimeLimit = "PT5M"

  $TaskAction = $TaskDefinition.Actions.Create(0) # TASK_ACTION_EXEC
  $TaskAction.Path = "cmd.exe"
  $TaskAction.Arguments = ('/c "{0}"' -f $CommandPath)

  $RegisteredComTask = $RootFolder.RegisterTaskDefinition(
    $TaskName,
    $TaskDefinition,
    6, # TASK_CREATE_OR_UPDATE
    $null,
    $null,
    3, # TASK_LOGON_INTERACTIVE_TOKEN
    $null
  )

  $TaskSecurityDescriptor = "D:P(A;;FA;;;SY)(A;;FA;;;BA)(A;;GRGX;;;$UserSid)"
  $RegisteredComTask.SetSecurityDescriptor($TaskSecurityDescriptor, 0)

  $RegisteredTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
  if (-not $RegisteredTask) {
    throw "计划任务注册失败：任务创建后无法查询到 $TaskName。"
  }
}

if (-not (Test-IsRunningAsAdministrator)) {
  $ScriptPath = $PSCommandPath
  if (-not $ScriptPath) {
    $ScriptPath = $MyInvocation.MyCommand.Path
  }

  if (-not $ScriptPath) {
    throw "无法确定安装脚本路径。请以管理员身份打开 PowerShell 后重新运行此脚本。"
  }

  $ElevatedArguments = @(
    "-NoProfile",
    "-ExecutionPolicy",
    "Bypass",
    "-File",
    ('"{0}"' -f $ScriptPath),
    "-LogFile",
    ('"{0}"' -f $InstallLogFile)
  )

  try {
    Write-InstallLog "正在请求管理员权限。"
    Write-Host "正在请求管理员权限以安装 CompressImgHotkey..."
    $ElevatedProcess = Start-Process `
      -FilePath "powershell.exe" `
      -ArgumentList $ElevatedArguments `
      -Verb RunAs `
      -Wait `
      -PassThru
    Write-InstallLog ("提权安装进程已结束，退出码：{0}" -f $ElevatedProcess.ExitCode)
    Write-Host "提权安装进程已结束，退出码：$($ElevatedProcess.ExitCode)"
    exit $ElevatedProcess.ExitCode
  }
  catch {
    throw '无法请求管理员权限。请右键 PowerShell 选择“以管理员身份运行”，然后重新执行此安装脚本。'
  }
}

Write-InstallLog "开始安装 CompressImgHotkey。"
Write-InstallLog ("当前用户：{0}" -f (Get-CurrentWindowsUserId))
Write-InstallLog ("安装日志：{0}" -f $InstallLogFile)

Write-InstallLog ("准备保护任务命令目录：{0}" -f $TaskDir)
Protect-AdminOnlyDirectory -Path $TaskDir

Write-InstallLog ("准备写入提权命令：{0}" -f $CmdFile)
@"
@echo off
compress-img --clipboard --target-kb 65
"@ | Set-Content -Encoding ASCII -Path $CmdFile

# 创建/更新一个“最高权限运行”的计划任务
$CurrentUserId = Get-CurrentWindowsUserId
$CurrentUserSid = Get-CurrentWindowsUserSid
Write-InstallLog ("准备注册计划任务：{0}，用户：{1}，SID：{2}" -f $TaskName, $CurrentUserId, $CurrentUserSid)
Register-HotkeyScheduledTask -UserId $CurrentUserId -UserSid $CurrentUserSid -CommandPath $CmdFile
Write-InstallLog "计划任务注册完成。"

# 编译一个小的 Windows 热键程序：Alt+E 触发 schtasks /run
$cs = @"
using System;
using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Windows.Forms;

public class Program
{
    private const int MOD_ALT = 0x0001;
    private const int WM_HOTKEY = 0x0312;
    private const int HOTKEY_ID = 1;

    [DllImport("user32.dll")]
    private static extern bool RegisterHotKey(IntPtr hWnd, int id, int fsModifiers, int vk);

    [DllImport("user32.dll")]
    private static extern bool UnregisterHotKey(IntPtr hWnd, int id);

    public class HotkeyWindow : Form
    {
        public HotkeyWindow()
        {
            ShowInTaskbar = false;
            WindowState = FormWindowState.Minimized;
            Load += (s, e) =>
            {
                Visible = false;

                // Alt + E
                bool ok = RegisterHotKey(this.Handle, HOTKEY_ID, MOD_ALT, (int)Keys.E);
                if (!ok)
                {
                    MessageBox.Show(
                        "注册 Alt+E 失败，可能已被其它程序占用。",
                        "CompressImgHotkey",
                        MessageBoxButtons.OK,
                        MessageBoxIcon.Error
                    );
                    Application.Exit();
                }
            };
        }

        protected override void WndProc(ref Message m)
        {
            if (m.Msg == WM_HOTKEY && m.WParam.ToInt32() == HOTKEY_ID)
            {
                RunTask();
            }

            base.WndProc(ref m);
        }

        private static void RunTask()
        {
            var psi = new ProcessStartInfo
            {
                FileName = "schtasks.exe",
                Arguments = "/run /tn \"CompressImgClipboard65\"",
                CreateNoWindow = true,
                UseShellExecute = false,
                WindowStyle = ProcessWindowStyle.Hidden
            };

            Process.Start(psi);
        }

        protected override void Dispose(bool disposing)
        {
            UnregisterHotKey(this.Handle, HOTKEY_ID);
            base.Dispose(disposing);
        }
    }

    [STAThread]
    public static void Main()
    {
        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);
        Application.Run(new HotkeyWindow());
    }
}
"@

Write-InstallLog "准备停止旧热键进程。"
Stop-InstalledHotkeyProcess -ExePath $ExeFile

$TempExeFile = Join-Path $UserDir ("CompressImgHotkey.{0}.tmp.exe" -f [Guid]::NewGuid().ToString("N"))

try {
  Write-InstallLog ("准备编译热键程序：{0}" -f $TempExeFile)
  Add-Type `
    -TypeDefinition $cs `
    -ReferencedAssemblies System.Windows.Forms,System.Drawing `
    -OutputAssembly $TempExeFile `
    -OutputType WindowsApplication

  Move-Item -LiteralPath $TempExeFile -Destination $ExeFile -Force
  Write-InstallLog ("热键程序已更新：{0}" -f $ExeFile)
}
finally {
  if (Test-Path -LiteralPath $TempExeFile) {
    Remove-Item -LiteralPath $TempExeFile -Force
  }
}

# 添加到开机启动
$StartupDir = [Environment]::GetFolderPath("Startup")
$ShortcutPath = Join-Path $StartupDir "CompressImgHotkey.lnk"

Write-InstallLog ("准备创建启动项：{0}" -f $ShortcutPath)
$Shell = New-Object -ComObject WScript.Shell
$Shortcut = $Shell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $ExeFile
$Shortcut.WorkingDirectory = $UserDir
$Shortcut.Description = "Alt+E runs compress-img clipboard compression"
$Shortcut.Save()

Write-InstallLog "准备启动热键程序。"
Start-Process $ExeFile
Write-InstallLog "安装完成。"

Write-Host "安装完成。以后按 Alt+E 会运行：compress-img --clipboard --target-kb 65"
Write-Host "热键程序路径：$ExeFile"
Write-Host "提权命令路径：$CmdFile"
Write-Host "计划任务名称：$TaskName"
Write-Host "安装日志路径：$InstallLogFile"
