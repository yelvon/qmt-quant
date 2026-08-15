#!/usr/bin/env bash
# Start qmt-quant Web workbench — Git Bash / MSYS wrapper around scripts/service.ps1
#
# Usage:
#   ./scripts/start.sh              # start both servers
#   ./scripts/start.sh --install    # npm install before start
#   ./scripts/start.sh --stop       # stop servers
#   ./scripts/start.sh --restart    # stop then start
#   ./scripts/start.sh --setup-only # setup env only, do not start servers
#   ./scripts/start.sh --no-browser # do not open browser

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

to_win_path() {
  local p="$1"
  if command -v cygpath >/dev/null 2>&1; then
    cygpath -w "$p"
    return
  fi
  if [[ "$p" =~ ^/([a-zA-Z])/(.*)$ ]]; then
    local drive="${BASH_REMATCH[1]^^}"
    local rest="${BASH_REMATCH[2]}"
    printf '%s:\\%s' "$drive" "${rest//\//\\}"
    return
  fi
  echo "$p"
}

SERVICE_PS1="$(to_win_path "$SCRIPT_DIR/service.ps1")"

INSTALL=false
NO_BROWSER=false
STOP=false
RESTART=false
SETUP_ONLY=false

usage() {
  cat <<'EOF'
用法: ./scripts/start.sh [选项]

选项:
  --install      强制重新安装 Python / 前端依赖
  --setup-only   仅搭建环境（配置、依赖、PostgreSQL、init-db），不启动服务
  --no-browser   不自动打开浏览器
  --stop         停止 8788 / 5173 端口上的服务
  --restart      先停止再启动（代码更新后推荐）
  -h, --help     显示帮助
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --install) INSTALL=true; shift ;;
    --setup-only) SETUP_ONLY=true; shift ;;
    --no-browser) NO_BROWSER=true; shift ;;
    --stop) STOP=true; shift ;;
    --restart) RESTART=true; STOP=true; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "未知参数: $1" >&2; usage; exit 1 ;;
  esac
done

if ! command -v powershell.exe >/dev/null 2>&1; then
  echo "未找到 powershell.exe" >&2
  exit 1
fi

# Git Bash ↔ PowerShell: use UTF-8 to avoid mojibake / duplicated CJK glyphs
if command -v chcp.com >/dev/null 2>&1; then
  chcp.com 65001 >/dev/null 2>&1 || true
fi

PS_ARGS=(-NoProfile -ExecutionPolicy Bypass -File "$SERVICE_PS1")
if $SETUP_ONLY; then
  PS_ARGS+=(-SetupOnly)
  $INSTALL && PS_ARGS+=(-Install)
elif $STOP && ! $RESTART; then
  PS_ARGS+=(-Stop)
else
  $RESTART && PS_ARGS+=(-Restart)
  $INSTALL && PS_ARGS+=(-Install)
  $NO_BROWSER && PS_ARGS+=(-NoBrowser)
fi

powershell.exe "${PS_ARGS[@]}"
