const { platform } = require('os');
const path = require('path');
const fs = require('fs');

const RESOURCE_MAP = {
  win32: { dir: 'win', exe: 'compress-image.exe' },
  darwin: { dir: 'mac', exe: 'compress-image' },
  linux: { dir: 'linux', exe: 'compress-image' },
};

const { dir, exe } = RESOURCE_MAP[platform()] ?? {};
if (!dir) {
  console.error(`不支持的平台: ${platform()}`);
  process.exit(1);
}

const resourcePath = path.join(__dirname, '..', 'resources', dir, exe);
if (!fs.existsSync(resourcePath)) {
  console.error(`警告：未找到 ${platform()} 平台的捆绑包。CLI 可能无法正常工作。`);
  console.error(`期望路径: ${resourcePath}`);
}