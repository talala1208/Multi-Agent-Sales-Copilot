#!/usr/bin/env bash
# 启动 agent-chat-ui，从调用方课程的 .env 读取 LANGSMITH_API_KEY 和 DAYTONA_API_KEY
# （而非可能过期的 .env.local 副本），覆盖 shell 中已设置的值
# （dotenv 类加载器，含 Next.js 自带，不会覆盖已存在的环境变量）。
#
# 调用方用 ENV_FILE 指定 .env；默认读项目根目录的 .env。
# 在本目录运行：./start.sh
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -d node_modules ]; then
    echo "正在安装依赖 (pnpm install) ..."
    pnpm install
fi

ENV_FILE="${ENV_FILE:-$SCRIPT_DIR/../.env}"
# `override: true` 使文件中的值优先于已设置的 shell 变量；
# `.parsed` 使值直接来自文件而非 process.env。
# 单独任一即可修复；两者一起可避免静默使用指向其他工作区的外层 shell 密钥。
# `quiet: true` 阻止 dotenv v17+ 向 stdout 打印启动横幅，
# 否则会被捕获进 CORRECT_KEY 与密钥本身混在一起。
CORRECT_KEY=$(node -e "const parsed = require('dotenv').config({path: '$ENV_FILE', override: true, quiet: true}).parsed || {}; process.stdout.write(parsed.LANGSMITH_API_KEY || '')")
DAYTONA_KEY=$(node -e "const parsed = require('dotenv').config({path: '$ENV_FILE', override: true, quiet: true}).parsed || {}; process.stdout.write(parsed.DAYTONA_API_KEY || '')")

if [ -z "$CORRECT_KEY" ]; then
    echo "无法从 $ENV_FILE 读取 LANGSMITH_API_KEY — 请确认文件存在且已设置该密钥。" >&2
    exit 1
fi

if [ -z "$DAYTONA_KEY" ]; then
    echo "无法从 $ENV_FILE 读取 DAYTONA_API_KEY — 请确认文件存在且已设置该密钥。" >&2
    exit 1
fi

echo "正在启动 agent-chat-ui http://localhost:3000 ..."
exec env \
  -u LANGSMITH_API_KEY LANGSMITH_API_KEY="$CORRECT_KEY" \
  DAYTONA_API_KEY="$DAYTONA_KEY" \
  pnpm run dev
