# install-compress-img-hotkey

当按 Alt+E 时，自动以管理员身份（不能每次都需要我批准）执行 `compress-img --clipboard --target-kb 65` 这条命令

---

## 以管理员身份运行安装脚本

在脚本所在文件夹空白处右键打开终端，然后执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\install-compress-img-hotkey.ps1
```

安装时会弹一次 UAC。之后按 `Alt+E` 不会每次都弹。

---

## 卸载

以管理员身份打开 PowerShell 执行：

```powershell
Stop-Process -Name "CompressImgHotkey" -Force -ErrorAction SilentlyContinue
Unregister-ScheduledTask -TaskName "CompressImgClipboard65" -Confirm:$false
Remove-Item "$env:LOCALAPPDATA\CompressImgHotkey" -Recurse -Force
Remove-Item "$env:ProgramData\CompressImgHotkey" -Recurse -Force
Remove-Item "$([Environment]::GetFolderPath('Startup'))\CompressImgHotkey.lnk" -Force
```

重新运行安装脚本时会自动停止旧的 `CompressImgHotkey.exe` 并刷新热键程序。
