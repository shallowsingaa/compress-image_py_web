# install-compress-img-hotkey

当按 Alt+E 时，自动以管理员身份（不能每次都需要我批准）执行 `compress-img --clipboard --target-kb 40` 这条命令

---

## 以管理员身份运行安装脚本

在脚本所在文件夹空白处右键打开终端，然后执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\install-compress-img-hotkey.ps1
```

安装时会弹一次 UAC。之后按 `Alt+E` 不会每次都弹。

如果从非管理员终端运行，脚本会等待提权安装进程结束，然后在原终端返回退出码并启动热键程序。

安装脚本会在当前用户目录写入日志：

```text
C:\Users\<你的用户名>\AppData\Local\CompressImgHotkey\install.log
```

如果 UAC 授权后安装窗口很快关闭，先看这份日志。它会记录计划任务注册、热键程序编译、启动项写入和最终启动步骤。

## 安装结果

安装完成后会创建以下内容：

- 计划任务 `CompressImgClipboard`
- 热键程序 `%LOCALAPPDATA%\CompressImgHotkey\CompressImgHotkey.exe`
- 提权命令 `%ProgramData%\CompressImgHotkey\run-compress-img.cmd`
- 启动项 `CompressImgHotkey.lnk`

热键程序常驻后，按 `Alt+E` 会触发计划任务，以最高权限执行：

```text
compress-img --clipboard --target-kb 40
```

如需修改热键执行的命令，改安装脚本开头的 `$TaskCommand`，然后重新运行安装脚本。

---

## 卸载

以管理员身份打开 PowerShell 执行：

```powershell
Stop-Process -Name "CompressImgHotkey" -Force -ErrorAction SilentlyContinue
Unregister-ScheduledTask -TaskName "CompressImgClipboard65" -Confirm:$false
Unregister-ScheduledTask -TaskName "CompressImgClipboard" -Confirm:$false
Remove-Item "$env:LOCALAPPDATA\CompressImgHotkey" -Recurse -Force
Remove-Item "$env:ProgramData\CompressImgHotkey" -Recurse -Force
Remove-Item "$([Environment]::GetFolderPath('Startup'))\CompressImgHotkey.lnk" -Force
```

重新运行安装脚本时会自动停止旧的 `CompressImgHotkey.exe` 并刷新热键程序。
