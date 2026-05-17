#requires -version 5.1

$ErrorActionPreference = "Stop"

$UserDir = Join-Path $env:LOCALAPPDATA "CompressImgHotkey"
$TaskDir = Join-Path $env:ProgramData "CompressImgHotkey"
$TaskName = "CompressImgClipboard65"
$CmdFile = Join-Path $TaskDir "run-compress-img.cmd"
$ExeFile = Join-Path $UserDir "CompressImgHotkey.exe"

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

New-Item -ItemType Directory -Force -Path $UserDir | Out-Null
Protect-AdminOnlyDirectory -Path $TaskDir

@"
@echo off
compress-img --clipboard --target-kb 65
"@ | Set-Content -Encoding ASCII -Path $CmdFile

# 创建/更新一个“最高权限运行”的计划任务
$Action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$CmdFile`""
$Principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Highest
$Settings = New-ScheduledTaskSettingsSet `
  -AllowStartIfOnBatteries `
  -DontStopIfGoingOnBatteries `
  -ExecutionTimeLimit (New-TimeSpan -Minutes 5)

Register-ScheduledTask `
  -TaskName $TaskName `
  -Action $Action `
  -Principal $Principal `
  -Settings $Settings `
  -Description "Run compress-img clipboard compression at 65 KB with elevated privileges." `
  -Force | Out-Null

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
                Arguments = "/run /tn ""CompressImgClipboard65""",
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

Stop-InstalledHotkeyProcess -ExePath $ExeFile

$TempExeFile = Join-Path $UserDir ("CompressImgHotkey.{0}.tmp.exe" -f [Guid]::NewGuid().ToString("N"))

try {
  Add-Type `
    -TypeDefinition $cs `
    -ReferencedAssemblies System.Windows.Forms,System.Drawing `
    -OutputAssembly $TempExeFile `
    -OutputType WindowsApplication

  Move-Item -LiteralPath $TempExeFile -Destination $ExeFile -Force
}
finally {
  if (Test-Path -LiteralPath $TempExeFile) {
    Remove-Item -LiteralPath $TempExeFile -Force
  }
}

# 添加到开机启动
$StartupDir = [Environment]::GetFolderPath("Startup")
$ShortcutPath = Join-Path $StartupDir "CompressImgHotkey.lnk"

$Shell = New-Object -ComObject WScript.Shell
$Shortcut = $Shell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $ExeFile
$Shortcut.WorkingDirectory = $UserDir
$Shortcut.Description = "Alt+E runs compress-img clipboard compression"
$Shortcut.Save()

Start-Process $ExeFile

Write-Host "安装完成。以后按 Alt+E 会运行：compress-img --clipboard --target-kb 65"
Write-Host "热键程序路径：$ExeFile"
Write-Host "提权命令路径：$CmdFile"
Write-Host "计划任务名称：$TaskName"
