#!/bin/sh
# 把路由器上的节点清单与拨测结果推回 GitHub，供 GitHub Actions 重建配置时使用。
#
# 为什么需要它：
#   GitHub Actions 访问不到本机（内网 IP），它重建配置时只能用仓库里的节点清单。
#   本脚本每天把「最新节点清单」和「拨测失败的节点名单」推到仓库，
#   这样 04:00 的 Actions 重建就能拿到最新节点，并同样剔除坏节点。
#
# 安装位置：/usr/local/bin/push-nodes-to-github.sh
# 依赖：/etc/qx-panel-token（GitHub token，600 权限）
LOG=/var/log/qx-push.log
AGG=http://127.0.0.1:8109/output
REPO=yjg954102/qx-rules
TOKEN_FILE=/etc/qx-panel-token
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

echo "===== $(date '+%F %T') 开始推送节点清单 =====" >> "$LOG"

TOKEN=$(cat "$TOKEN_FILE" 2>/dev/null | tr -d ' \r\n')
if [ -z "$TOKEN" ]; then
  echo "  未找到 GitHub token，跳过" >> "$LOG"
  exit 0
fi

# ---- 1) 取最新节点清单 ----
curl -s --max-time 30 -o "$WORK/nodes.txt" "$AGG/qx-compatible-all.txt" || {
  echo "  节点清单下载失败，跳过" >> "$LOG"; exit 0
}
NTAGS=$(grep -c '=' "$WORK/nodes.txt")
if [ "$NTAGS" -lt 10 ]; then
  echo "  节点数异常（$NTAGS），跳过以免覆盖" >> "$LOG"; exit 0
fi

# ---- 2) 取拨测失败的节点 tag ----
python3 - "$WORK" <<'PYEOF' >> "$LOG" 2>&1
import json, sys, os
work = sys.argv[1]
try:
    res = (json.load(open('/opt/open-box/data/subscription-aggregator/probe-results.json',
                          encoding='utf-8')) or {}).get('results') or {}
    nd = json.load(open('/opt/open-box/data/subscription-aggregator/published-nodes.json',
                        encoding='utf-8'))
    nodes = nd if isinstance(nd, list) else (nd.get('nodes') or [])
    meta = {str(n.get('id')): n.get('tag', '') for n in nodes if isinstance(n, dict)}
    dead = sorted({meta.get(str(k), '') for k, v in res.items()
                   if not v.get('success') and meta.get(str(k))})
    with open(os.path.join(work, 'dead.txt'), 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(dead) + ('\n' if dead else ''))
    print(f'  拨测失败 {len(dead)} 个节点')
except Exception as e:
    open(os.path.join(work, 'dead.txt'), 'w').close()
    print(f'  拨测结果读取失败（不影响主流程）: {e}')
PYEOF

# ---- 3) 推送到 GitHub ----
push_file() {
  rel="$1"; file="$2"
  [ -f "$file" ] || return 1
  # 取当前 sha（文件不存在时为空）
  sha=$(curl -s --max-time 20 -H "Authorization: Bearer $TOKEN" \
        -H "Accept: application/vnd.github+json" \
        "https://api.github.com/repos/$REPO/contents/$rel" \
        | python3 -c "import sys,json
try:
    print(json.load(sys.stdin).get('sha',''))
except Exception:
    print('')" 2>/dev/null)
  b64=$(base64 -w0 "$file")
  python3 - "$TOKEN" "$rel" "$sha" "$b64" <<'PYEOF'
import json, sys, urllib.request
token, rel, sha, content = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
body = {'message': f'chore(router): 更新 {rel}', 'content': content, 'branch': 'main'}
if sha:
    body['sha'] = sha
req = urllib.request.Request(
    f'https://api.github.com/repos/yjg954102/qx-rules/contents/{rel}',
    data=json.dumps(body).encode(),
    headers={'Authorization': 'Bearer ' + token,
             'Accept': 'application/vnd.github+json',
             'User-Agent': 'qx-router',
             'X-GitHub-Api-Version': '2022-11-28'},
    method='PUT')
try:
    r = json.loads(urllib.request.urlopen(req, timeout=60).read())
    print(f'  推送成功 {rel}  commit={r["commit"]["sha"][:7]}')
except Exception as e:
    print(f'  推送失败 {rel}: {str(e)[:80]}')
PYEOF
}

push_file "output/nodes-qx-compatible.txt" "$WORK/nodes.txt"
push_file "output/dead-nodes.txt" "$WORK/dead.txt"

echo "===== $(date '+%F %T') 结束（节点 $NTAGS 个）=====" >> "$LOG"
