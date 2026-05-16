# compress-img-cli 发布指南

本文档面向维护者，说明如何把 `compress-img-cli` 发布到 npm，让用户可以通过 `npm install -g compress-img-cli` 安装，并在终端执行 `compress-img`。

## 发布前检查

确认当前包名和命令名：

```bash
node -e "const p=require('./package.json'); console.log(p.name, Object.keys(p.bin))"
```

期望输出包含：

```text
compress-img-cli [ 'compress-img' ]
```

确认两个平台二进制都已生成：

```powershell
Test-Path .\resources\win\compress-image.exe
Test-Path .\resources\linux\compress-image
```

在 Linux 上：

```bash
test -f resources/linux/compress-image
test -f resources/win/compress-image.exe
```

## 构建二进制

Windows:

```powershell
cd package
npm run build:win
```

Linux:

```bash
cd package
npm run build:linux
```

`resources/` 是发布产物目录，已被 git 忽略。不要把生成的二进制提交到 git；发布前确保它们存在即可。

## 预览 npm 包内容

```bash
npm pack --dry-run
```

输出中必须包含：

```text
bin/compress-image.js
bin/verify-platform.js
resources/linux/compress-image
resources/win/compress-image.exe
README.md
HELP.md
PUBLISHING.md
CHANGELOG.md
LICENSE
```

如果缺少 `resources/` 下的二进制，先回到对应平台重新构建。

## 版本号

发布新版本前修改 `package.json` 和 `package-lock.json` 中的版本号：

```bash
npm version patch --no-git-tag-version
```

也可以指定版本：

```bash
npm version 1.0.1 --no-git-tag-version
```

## 登录与 2FA

普通交互式发布：

```bash
npm login
npm publish --otp=123456
```

如果使用 npm granular access token，在本机写入 token：

```bash
npm config set //registry.npmjs.org/:_authToken "你的token"
npm whoami
npm publish
```

发布后建议删除本机 token：

```bash
npm config delete //registry.npmjs.org/:_authToken
```

不要把 token 写入仓库、文档示例之外的配置文件或提交记录。

## 发布

```bash
cd package
npm publish
```

如果 npm 账号启用了发布 2FA，并且没有使用 bypass 2FA 的 token：

```bash
npm publish --otp=你的6位验证码
```

## 发布后验证

```bash
npm view compress-img-cli version
npm install -g compress-img-cli
compress-img --help
```

Windows 上建议额外验证剪贴板模式：

```powershell
compress-img --clipboard
```

Linux 上建议验证文件输入，并确认剪贴板模式给出友好提示。

## 回滚和废弃版本

如果刚发布的版本有严重问题，优先发布修复版本。npm 对删除版本有限制，通常不要依赖删除来回滚。

需要提示用户不要使用某个版本时：

```bash
npm deprecate compress-img-cli@1.0.0 "该版本存在发布包问题，请升级到更新版本。"
```
