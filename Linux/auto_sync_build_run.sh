#!/usr/bin/env bash
set -Eeuo pipefail

#######################################
# 可修改配置区
#######################################

# Gitee HTTPS 仓库地址
REPO_URL="https://gitee.com/shallowspider/compress-image_py_web.git"

# 远程分支
BRANCH="master"

# 本地源码目录，必须用绝对路径
TARGET_DIR="/opt/compress-image/src"

# Python 依赖安装命令
PYTHON_INSTALL_CMD="/opt/compress-image/venv/bin/pip3 install -r requirements.txt"

# npm 依赖安装命令
# 生产环境如果有 package-lock.json，更推荐改成：npm ci
NPM_INSTALL_CMD="cd web && npm ci"

# npm 构建命令
BUILD_CMD="cd web && npm run build"

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

  if ps -p "$old_pid" >/dev/null 2>&1 && ! process_looks_like_backend "$old_pid"; then
    log "PID 文件中的进程不是当前后端服务，移除陈旧 PID：$old_pid"
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

backend_is_running() {
  local backend_pid

  if [[ ! -f "$BACKEND_PID_FILE" ]]; then
    backend_pid="$(find_backend_pid || true)"
    if [[ -n "$backend_pid" ]]; then
      echo "$backend_pid" > "$BACKEND_PID_FILE"
      return 0
    fi

    return 1
  fi

  backend_pid="$(cat "$BACKEND_PID_FILE" || true)"

  if [[ -z "$backend_pid" ]]; then
    rm -f "$BACKEND_PID_FILE"
    backend_pid="$(find_backend_pid || true)"
    if [[ -n "$backend_pid" ]]; then
      echo "$backend_pid" > "$BACKEND_PID_FILE"
      return 0
    fi

    return 1
  fi

  if ps -p "$backend_pid" >/dev/null 2>&1 && process_looks_like_backend "$backend_pid"; then
    return 0
  fi

  rm -f "$BACKEND_PID_FILE"
  backend_pid="$(find_backend_pid || true)"
  if [[ -n "$backend_pid" ]]; then
    echo "$backend_pid" > "$BACKEND_PID_FILE"
    return 0
  fi

  return 1
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

process_has_deploy_lock() {
  local pid="$1"
  local fd
  local fd_target

  [[ -d "/proc/$pid/fd" ]] || return 1

  for fd in "/proc/$pid/fd/"*; do
    [[ -e "$fd" ]] || continue

    fd_target="$(readlink "$fd" 2>/dev/null || true)"
    if [[ "$fd_target" == "$LOCK_FILE" || "$fd_target" == "$LOCK_FILE (deleted)" ]]; then
      return 0
    fi
  done

  return 1
}

process_cmdline() {
  local pid="$1"

  if [[ ! -r "/proc/$pid/cmdline" ]]; then
    return 1
  fi

  tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null || true
}

process_looks_like_backend() {
  local pid="$1"
  local cmdline

  cmdline="$(process_cmdline "$pid")"
  [[ -n "$cmdline" ]] || return 1

  [[ "$cmdline" == *"uvicorn"* && "$cmdline" == *"app:app"* && "$cmdline" == *"8793"* ]]
}

find_backend_pid() {
  local proc_dir
  local backend_pid

  for proc_dir in /proc/[0-9]*; do
    [[ -d "$proc_dir" ]] || continue

    backend_pid="${proc_dir##*/}"
    if process_looks_like_backend "$backend_pid"; then
      printf '%s\n' "$backend_pid"
      return 0
    fi
  done

  return 1
}

find_stale_backend_lock_pid() {
  local backend_pid

  if [[ -f "$BACKEND_PID_FILE" ]]; then
    backend_pid="$(cat "$BACKEND_PID_FILE" || true)"

    if [[ -z "$backend_pid" ]]; then
      rm -f "$BACKEND_PID_FILE"
    elif ps -p "$backend_pid" >/dev/null 2>&1 && process_has_deploy_lock "$backend_pid" && process_looks_like_backend "$backend_pid"; then
      printf '%s\n' "$backend_pid"
      return 0
    elif ! ps -p "$backend_pid" >/dev/null 2>&1; then
      rm -f "$BACKEND_PID_FILE"
    fi
  fi

  local proc_dir
  for proc_dir in /proc/[0-9]*; do
    [[ -d "$proc_dir" ]] || continue

    backend_pid="${proc_dir##*/}"
    if process_has_deploy_lock "$backend_pid" && process_looks_like_backend "$backend_pid"; then
      printf '%s\n' "$backend_pid"
      return 0
    fi
  done

  return 1
}

release_stale_backend_deploy_lock() {
  local backend_pid
  backend_pid="$(find_stale_backend_lock_pid || true)"

  [[ -n "$backend_pid" ]] || return 1

  log "检测到旧后台进程仍持有部署锁，准备停止该进程，PID：$backend_pid" | tee -a "$LOG_FILE"
  kill "$backend_pid" || true

  for _ in {1..10}; do
    if ps -p "$backend_pid" >/dev/null 2>&1; then
      sleep 1
    else
      break
    fi
  done

  if ps -p "$backend_pid" >/dev/null 2>&1; then
    log "旧后台进程未正常退出，执行强制终止，PID：$backend_pid" | tee -a "$LOG_FILE"
    kill -9 "$backend_pid" || true
  fi

  rm -f "$BACKEND_PID_FILE"
  return 0
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

run_deploy_steps() {
  run_python_install
  run_npm_install
  run_after_npm_install_cmd
  build_project
  publish_webroot
}

#######################################
# 主流程
#######################################

mkdir -p "$(dirname "$LOG_FILE")"
touch "$LOG_FILE"

if [[ "${GITEE_SITE_DEPLOY_LOCKED:-0}" != "1" ]]; then
  need_cmd flock

  for lock_attempt in 1 2; do
    set +e
    env GITEE_SITE_DEPLOY_LOCKED=1 flock -n -E 75 --close "$LOCK_FILE" bash "${BASH_SOURCE[0]}" "$@"
    lock_rc=$?
    set -e

    if [[ "$lock_rc" -ne 75 ]]; then
      exit "$lock_rc"
    fi

    if [[ "$lock_attempt" -eq 1 ]] && release_stale_backend_deploy_lock; then
      log "已释放旧后台进程持有的部署锁，重新尝试部署" | tee -a "$LOG_FILE"
      continue
    fi

    log "已有部署任务正在运行，本次退出" | tee -a "$LOG_FILE"
    exit 0
  done
fi

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

BACKEND_RUNNING="0"
if backend_is_running; then
  BACKEND_RUNNING="1"
  log "检测到后端服务正在运行，PID：$(cat "$BACKEND_PID_FILE")"
else
  log "未检测到正在运行的后端服务"
fi

SOURCE_IS_CURRENT="0"
if [[ "$FORCE" != "1" ]] && is_git_repo && [[ "$LOCAL_REMOTE" == "$REPO_URL" ]] && [[ "$LOCAL_COMMIT" == "$REMOTE_COMMIT" ]]; then
  SOURCE_IS_CURRENT="1"
fi

if [[ "$SOURCE_IS_CURRENT" == "1" && "$BACKEND_RUNNING" == "1" ]]; then
  log "远程仓库没有新提交，后端服务已运行，无需部署"
  log "========== 结束 =========="
  exit 0
fi

if [[ "$SOURCE_IS_CURRENT" == "1" && "$BACKEND_RUNNING" == "0" ]]; then
  log "远程仓库没有新提交，但后端服务未运行，将复用本地源码执行完整部署流程"
  run_deploy_steps
  log "========== 部署成功 =========="
  exit 0
fi

if [[ "$FORCE" == "1" ]]; then
  log "检测到 FORCE=1，将强制覆盖并构建"
fi

if [[ "$BACKEND_RUNNING" == "1" ]]; then
  log "需要更新源码，先完全停止正在运行的后端服务"
  stop_old_backend
fi

if ! is_git_repo || [[ "$LOCAL_REMOTE" != "$REPO_URL" ]]; then
  log "本地目录不是目标仓库，或远程地址不一致，将重新克隆并完全覆盖"
  clone_fresh
else
  force_update_existing_repo
fi

NEW_LOCAL_COMMIT="$(git -C "$TARGET_DIR" rev-parse HEAD)"
log "同步后的本地提交：$NEW_LOCAL_COMMIT"

run_deploy_steps

log "========== 部署成功 =========="
