#!/bin/bash
# 常驻跑：macOS 用 caffeinate 防睡眠；Linux 直接跑。崩溃自动重启，抢到后正常退出
cd "$(dirname "$0")" || exit 1

ARGS=("$@")
if [ ${#ARGS[@]} -eq 0 ]; then
  ARGS=(run --value 200)
fi

RUN=()
if command -v caffeinate >/dev/null 2>&1; then
  RUN=(caffeinate -dimsu)
fi

while true; do
  echo "$(date '+%F %T') 启动: python3 snatch.py ${ARGS[*]}" >> run.log
  "${RUN[@]}" python3 snatch.py "${ARGS[@]}"
  rc=$?
  if [ "$rc" -eq 0 ]; then
    echo "$(date '+%F %T') 已成功抢到，退出" >> run.log
    break
  fi
  echo "$(date '+%F %T') 异常退出 rc=$rc，5 秒后重启" >> run.log
  sleep 5
done
