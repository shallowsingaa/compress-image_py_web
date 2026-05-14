#!/usr/bin/env bash
set -Eeuo pipefail

#######################################
# 可修改配置区
#######################################

# Gitee HTTPS 仓库地址
REPO_URL="https://gitee.com/shallowspider/compress-image_py_web.git"

# 远程分支
BRANCH="master"

# 本地源码目录
TARGET_DIR="./src"

# Python 依赖安装命令
PYTHON_INSTALL_CMD="/opt/compress-image/venv/bin/pip3 install -r requirements.txt"

# npm 依赖安装命令
# 生产环境如果有 package-lock.json，更推荐改成：npm ci
NPM_INSTALL_CMD="npm ci"

# npm 构建命令
BUILD_CMD="npm run build"

# npm install 成功后执行的命令
# 注意：uvicorn 是常驻进程，脚本会以后台方式启动它，避免阻塞后续构建。
AFTER_NPM_INSTALL_CMD="/opt/compress-image/venv/bin/python3 -m uvicorn app:app --host 0.0.0.0 --port 8793"

# 执行 AFTER_NPM_INSTALL_CMD 的工作目录
AFTER_NPM_INSTALL_WORKDIR="$TARGET_DIR"

# 是否启用 npm install 后的命令
ENABLE_AFTER_NPM_INSTALL_CMD="1"

# 后台服务 PID 文件和日志文件
BACKEND_PID_FILE="/tmp/gitee-site-uvicorn.pid"
BACKEND_LOG_FILE="/var/log/gitee-site-uvicorn.log"

# 构建产物目录，相对于 TARGET_DIR
BUILD_OUTPUT_DIR="web/dist"

# Web 服务目录。留空则只构建，不发布。
WEB_ROOT="/opt/1panel/www/sites/ci.clicli.asia/index"

# 部署日志和锁文件
LOG_FILE="/var/log/gitee-site-deploy.log"
LOCK_FILE="/tmp/gitee-site-deploy.lock"

# 设置 FORCE=1 可强制重新覆盖和构建：
# FORCE=1 ./deploy-gitee-site.sh
FORCE="${FORCE:-0}"

#######################################
# 内部函数区
#######################################

log() {
  printf '[%s] %s\n' "$(date '+%F %T')" "$*"
}

die() {
  log "ERROR: $*"
  exit 1
}

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "缺少命令：$1"
}

is_git_repo() {
  [[ -d "$TARGET_DIR/.git" ]]
}

safe_delete_target() {
  local dir="$1"

  [[ -n "$dir" ]] || die "TARGET_DIR 不能为空"
  [[ "$dir" != "/" ]] || die "拒绝删除根目录 /"
  [[ "$dir" != "/opt" ]] || die "TARGET_DIR 过于危险：/opt"
  [[ "$dir" != "/var" ]] || die "TARGET_DIR 过于危险：/var"
  [[ "$dir" != "/var/www" ]] || die "TARGET_DIR 过于危险：/var/www"
  [[ "$dir" == /* ]] || die "TARGET_DIR 必须使用绝对路径"

  rm -rf -- "$dir"
}

clone_fresh() {
  local tmp_dir="${TARGET_DIR}.tmp.$$"

  log "准备全新克隆仓库到临时目录：$tmp_dir"
  rm -rf -- "$tmp_dir"

  git clone \
    --branch "$BRANCH" \
    --single-branch \
    "$REPO_URL" \
    "$tmp_dir"

  log "用新克隆结果完全覆盖本地目录：$TARGET_DIR"
  safe_delete_target "$TARGET_DIR"
  mkdir -p "$(dirname "$TARGET_DIR")"
  mv "$tmp_dir" "$TARGET_DIR"
}

force_update_existing_repo() {
  log "远程仓库有新提交，开始强制同步本地仓库"

  git -C "$TARGET_DIR" remote set-url origin "$REPO_URL"
  git -C "$TARGET_DIR" fetch --force --prune origin "$BRANCH"

  git -C "$TARGET_DIR" checkout -B "$BRANCH" "origin/$BRANCH"
  git -C "$TARGET_DIR" reset --hard "origin/$BRANCH"

  # 删除所有未跟踪文件，包括 node_modules、旧构建产物等
  git -C "$TARGET_DIR" clean -fdx
}

run_python_install() {
  if [[ -z "$PYTHON_INSTALL_CMD" ]]; then
    log "PYTHON_INSTALL_CMD 为空，跳过 Python 依赖安装"
    return 0
  fi

  log "执行 Python 依赖安装命令：$PYTHON_INSTALL_CMD"
  cd "$TARGET_DIR"
  bash -lc "$PYTHON_INSTALL_CMD"
  log "Python 依赖安装完成"
}

run_npm_install() {
  if [[ -z "$NPM_INSTALL_CMD" ]]; then
    log "NPM_INSTALL_CMD 为空，跳过 npm 依赖安装"
    return 0
  fi

  log "执行 npm 依赖安装命令：$NPM_INSTALL_CMD"
  cd "$TARGET_DIR"
  bash -lc "$NPM_INSTALL_CMD"
  log "npm 依赖安装完成"
}

stop_old_backend() {
  if [[ ! -f "$BACKEND_PID_FILE" ]]; then
    return 0
  fi

  local old_pid
  old_pid="$(cat "$BACKEND_PID_FILE" || true)"

  if [[ -z "$old_pid" ]]; then
    rm -f "$BACKEND_PID_FILE"
    return 0
  fi

  if ps -p "$old_pid" >/dev/null 2>&1; then
    log "停止旧的后台进程，PID：$old_pid"
    kill "$old_pid" || true

    for _ in {1..10}; do
      if ps -p "$old_pid" >/dev/null 2>&1; then
        sleep 1
      else
        break
      fi
    done

    if ps -p "$old_pid" >/dev/null 2>&1; then
      log "旧进程未正常退出，执行强制终止，PID：$old_pid"
      kill -9 "$old_pid" || true
    fi
  fi

  rm -f "$BACKEND_PID_FILE"
}

run_after_npm_install_cmd() {
  if [[ "$ENABLE_AFTER_NPM_INSTALL_CMD" != "1" ]]; then
    log "ENABLE_AFTER_NPM_INSTALL_CMD != 1，跳过 npm install 后置命令"
    return 0
  fi

  if [[ -z "$AFTER_NPM_INSTALL_CMD" ]]; then
    log "AFTER_NPM_INSTALL_CMD 为空，跳过 npm install 后置命令"
    return 0
  fi

  [[ -d "$AFTER_NPM_INSTALL_WORKDIR" ]] || die "AFTER_NPM_INSTALL_WORKDIR 不存在：$AFTER_NPM_INSTALL_WORKDIR"

  mkdir -p "$(dirname "$BACKEND_LOG_FILE")"
  touch "$BACKEND_LOG_FILE"

  stop_old_backend

  log "后台启动 npm install 后置命令：$AFTER_NPM_INSTALL_CMD"
  log "后置命令工作目录：$AFTER_NPM_INSTALL_WORKDIR"
  log "后置命令日志：$BACKEND_LOG_FILE"

  cd "$AFTER_NPM_INSTALL_WORKDIR"

  nohup bash -lc "$AFTER_NPM_INSTALL_CMD" >> "$BACKEND_LOG_FILE" 2>&1 &
  local new_pid="$!"

  echo "$new_pid" > "$BACKEND_PID_FILE"

  sleep 2

  if ps -p "$new_pid" >/dev/null 2>&1; then
    log "后置命令已启动，PID：$new_pid"
  else
    rm -f "$BACKEND_PID_FILE"
    die "后置命令启动失败，请查看日志：$BACKEND_LOG_FILE"
  fi
}

build_project() {
  if [[ -z "$BUILD_CMD" ]]; then
    log "BUILD_CMD 为空，跳过构建"
    return 0
  fi

  log "开始构建项目：$TARGET_DIR"
  cd "$TARGET_DIR"

  log "执行构建命令：$BUILD_CMD"
  bash -lc "$BUILD_CMD"

  log "构建完成"
}

publish_webroot() {
  if [[ -z "$WEB_ROOT" ]]; then
    log "WEB_ROOT 为空，跳过发布步骤"
    return 0
  fi

  local output_path="$TARGET_DIR/$BUILD_OUTPUT_DIR"

  [[ -d "$output_path" ]] || die "构建产物目录不存在：$output_path"

  log "发布构建产物到：$WEB_ROOT"
  mkdir -p "$WEB_ROOT"

  rsync -a --delete "$output_path"/ "$WEB_ROOT"/

  log "发布完成"
}

#######################################
# 主流程
#######################################

mkdir -p "$(dirname "$LOG_FILE")"
touch "$LOG_FILE"

exec > >(tee -a "$LOG_FILE") 2>&1

trap 'rc=$?; log "部署失败，退出码：$rc，出错命令：$BASH_COMMAND"; exit $rc' ERR

need_cmd git
need_cmd awk
need_cmd flock
need_cmd bash
need_cmd rsync
need_cmd ps
need_cmd kill
need_cmd sleep
need_cmd nohup

if [[ -n "$PYTHON_INSTALL_CMD" ]]; then
  need_cmd pip3
fi

if [[ -n "$NPM_INSTALL_CMD" || -n "$BUILD_CMD" ]]; then
  need_cmd npm
fi

if [[ -n "$AFTER_NPM_INSTALL_CMD" ]]; then
  need_cmd python3
fi

[[ "$REPO_URL" == https://* ]] || die "REPO_URL 必须使用 HTTPS 协议"
[[ -n "$BRANCH" ]] || die "BRANCH 不能为空"
[[ -n "$TARGET_DIR" ]] || die "TARGET_DIR 不能为空"

exec 200>"$LOCK_FILE"
flock -n 200 || {
  log "已有部署任务正在运行，本次退出"
  exit 0
}

log "========== 开始检查 Gitee 仓库 =========="
log "仓库：$REPO_URL"
log "分支：$BRANCH"
log "本地目录：$TARGET_DIR"

REMOTE_COMMIT="$(
  git ls-remote --heads "$REPO_URL" "$BRANCH" | awk '{print $1}'
)"

[[ -n "$REMOTE_COMMIT" ]] || die "无法获取远程分支提交，请检查仓库地址、分支名或 HTTPS 凭据"

LOCAL_COMMIT=""
LOCAL_REMOTE=""

if is_git_repo; then
  LOCAL_COMMIT="$(git -C "$TARGET_DIR" rev-parse HEAD 2>/dev/null || true)"
  LOCAL_REMOTE="$(git -C "$TARGET_DIR" remote get-url origin 2>/dev/null || true)"
fi

log "远程提交：$REMOTE_COMMIT"
log "本地提交：${LOCAL_COMMIT:-无}"
log "本地远程：${LOCAL_REMOTE:-无}"

if [[ "$FORCE" != "1" ]] && is_git_repo && [[ "$LOCAL_REMOTE" == "$REPO_URL" ]] && [[ "$LOCAL_COMMIT" == "$REMOTE_COMMIT" ]]; then
  log "远程仓库没有新提交，无需更新和构建"
  log "========== 结束 =========="
  exit 0
fi

if [[ "$FORCE" == "1" ]]; then
  log "检测到 FORCE=1，将强制覆盖并构建"
fi

if ! is_git_repo || [[ "$LOCAL_REMOTE" != "$REPO_URL" ]]; then
  log "本地目录不是目标仓库，或远程地址不一致，将重新克隆并完全覆盖"
  clone_fresh
else
  force_update_existing_repo
fi

NEW_LOCAL_COMMIT="$(git -C "$TARGET_DIR" rev-parse HEAD)"
log "同步后的本地提交：$NEW_LOCAL_COMMIT"

run_python_install
run_npm_install
run_after_npm_install_cmd
build_project
publish_webroot

log "========== 部署成功 =========="