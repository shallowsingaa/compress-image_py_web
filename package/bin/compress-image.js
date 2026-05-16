#!/usr/bin/env node
const { platform } = require('os');
const path = require('path');
const { spawn } = require('child_process');
const fs = require('fs');

const RESOURCE_MAP = {
  win32: { dir: 'win', exe: 'compress-image.exe' },
  linux: { dir: 'linux', exe: 'compress-image' },
};

const { dir, exe } = RESOURCE_MAP[platform()] ?? {};
if (!dir) {
  console.error('不支持的平台:', platform());
  process.exit(1);
}

const executable = path.join(__dirname, '..', 'resources', dir, exe);

if (!fs.existsSync(executable)) {
  console.error(`错误：未找到 ${platform()} 平台的捆绑包。请重新安装。`);
  process.exit(1);
}

const child = spawn(executable, process.argv.slice(2), {
  stdio: 'inherit',
  windowsHide: true,
});

child.on('exit', (code) => process.exit(code ?? 0));