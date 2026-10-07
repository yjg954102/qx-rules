#!/bin/sh
# refresh-nodes.sh 的收尾校验：确认拉取到的配置没有失效的策略引用。
#
# 背景：GitHub 上的 qx-integrated.conf 若含旧策略名（如 final, 🐟 兜底分流），
# 每天 05:00 拉取后 QX 就会报「未知策略组」。本脚本在拉取后立即校验并告警，
# 避免问题静默扩散到客户端。
LOG=/var/log/qx-refresh.log
QXD=/opt/roceos/www/openbox
CONF="$QXD/qx.conf"
VALIDATOR=/usr/local/bin/validate-qx.py

[ -f "$CONF" ] || exit 0

# 1) 有校验器就用校验器
if [ -f "$VALIDATOR" ] && command -v python3 >/dev/null 2>&1; then
  OUT=$(python3 "$VALIDATOR" "$CONF" 2>&1)
  if echo "$OUT" | grep -q '❌'; then
    {
      echo "===== $(date '+%F %T') 配置校验失败 ====="
      echo "$OUT" | grep -A20 '❌' | head -25
    } >> "$LOG"
    logger -t qx-post-refresh "配置校验失败，详见 $LOG"
  else
    echo "===== $(date '+%F %T') 配置校验通过 =====" >> "$LOG"
  fi
fi

# 2) 兜底：关键策略名必须存在（防止校验器缺失时报错无声）
if grep -qE '(final|,)\s*🐟 兜底分流\s*$' "$CONF"; then
  {
    echo "===== $(date '+%F %T') [严重] 配置引用了已删除的「🐟 兜底分流」====="
    grep -n '兜底分流' "$CONF" | head -3
    echo "请更新 GitHub 上的 qx-integrated.conf"
  } >> "$LOG"
  logger -t qx-post-refresh "严重：配置引用了已删除的策略组"
fi

exit 0
