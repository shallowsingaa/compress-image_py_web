# Superpowers 工作文档索引

此目录保存和 `compress-image_py_web` 相关的计划、设计和执行材料。它不是 npm 发布包的一部分，而是给维护者和后续 agent 使用的工程上下文。

## 当前 npm 分发决策

- npm 包名：`compress-img-cli`
- 安装命令：`npm install -g compress-img-cli`
- 全局命令：`compress-img`
- 支持平台：Windows (`win32`) 和 Linux (`linux`)
- 不支持平台：macOS
- 二进制产物：发布前构建，进入 npm tarball，但不纳入 git

## 相关文档

- [npm 分发设计方案](./specs/2026-05-16-npm-distribution-design.md)
- [npm 分发实现计划](./plans/2026-05-16-npm-distribution-plan.md)
- 项目级 npm 分发说明：[../npm-package.md](../npm-package.md)
- npm 包用户文档：[../../package/README.md](../../package/README.md)
- npm 包发布文档：[../../package/PUBLISHING.md](../../package/PUBLISHING.md)
- 命令帮助文档：[../../package/HELP.md](../../package/HELP.md)

## 维护规则

- 改包名、命令名、支持平台或发布流程时，同步更新 `package/`、`docs/npm-package.md` 和本目录下的 npm 分发文档。
- `package/resources/` 下的二进制只用于发布，不提交到 git。
- 发布前使用 `npm pack --dry-run` 检查 tarball 内容。
