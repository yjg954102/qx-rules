# QX Rules — Quantumult X 去广告 / 解锁 合并订阅

把十几个开源 QX 规则源合并成**两个**订阅文件，可直接上传到 GitHub / Gitee 后用 QX 引用。

---

## ⚠️ 先看这个：为什么是「两个」而不是「一个」

Quantumult X 的订阅分两种资源类型，**互不通用**：

| 订阅位置 | 只接受 |
| :-- | :-- |
| `[filter_remote]` | 分流规则，如 `host, x.com, reject` |
| `[rewrite_remote]` | 重写规则，如 `^https... url script-response-body ...` |

QX 没有官方支持「单个 URL 同时作为分流 + 重写订阅」的资源类型。
本仓库已把原来的十几个链接压缩到 **2 个**（一个分流 + 一个重写），这是 QX 框架下能做到的极限整合。

---

## 目录结构

```
.
├── output/                              # ★ 订阅文件（QX 引用这两个）
│   ├── QX-AllInOne-Filter.conf          #   分流：放 [filter_remote]
│   ├── QX-AllInOne-Rewrite.conf         #   重写：放 [rewrite_remote]
│   └── MITM-hostnames.txt               #   MITM 主机名，需手动填进 QX（977 个）
├── scripts/
│   ├── merge.ps1                        # 合并脚本（唯一需要维护的文件）
│   ├── fix-upload.ps1                   # 一键上传修正版到本仓库
│   └── sources/                         # 上游源文件缓存（local 模式离线复现用）
└── .github/workflows/update.yml          # 每日自动重建
```

> ⚠️ **订阅文件的格式要求**：远程订阅必须是「一行一条规则」的纯净列表。
> 不能包含 `#!name=` 之类的 Loon/Surge 元数据行，也不能包含 `[filter_local]`、`[rewrite_local]`、`[MITM]` 段头
> —— QX 会把它们判为 `INVALID LINE` 并拒绝整个订阅。`merge.ps1` 已按此规则生成。

---

## 一、上传到仓库

### GitHub

1. 新建仓库（**建议设为 Public**；私有仓库的 raw 链接 QX 无法直接访问）
2. 上传本目录全部文件（保持目录结构），或：

```bash
git init
git add .
git commit -m "init: merged QX rules"
git branch -M main
git remote add origin https://github.com/<你的用户名>/<仓库名>.git
git push -u origin main
```

### Gitee（国内访问更快）

同上，推送到 Gitee 后使用 raw 链接：

```
https://gitee.com/<用户名>/<仓库名>/raw/main/output/QX-AllInOne-Filter.conf
https://gitee.com/<用户名>/<仓库名>/raw/main/output/QX-AllInOne-Rewrite.conf
```

> Gitee 的「开源」仓库才允许匿名 raw 访问；私有仓库需要 token，QX 不适用。

---

## 二、在 Quantumult X 中引用

把 `<用户名>` `<仓库名>` 换成你自己的，然后：

**分流订阅** —— 风车 → 分流 → 规则资源 → 右上角 `+`

```
https://raw.githubusercontent.com/<用户名>/<仓库名>/main/output/QX-AllInOne-Filter.conf
```

**重写订阅** —— 风车 → 重写 → 规则资源 → 右上角 `+`

```
https://raw.githubusercontent.com/<用户名>/<仓库名>/main/output/QX-AllInOne-Rewrite.conf
```

添加后**右滑该条目点更新图标**，无报错即成功。

### MITM 证书必做（漏任何一步，重写全部静默失效）

1. 风车 → **MITM** → 生成证书
2. 按引导安装描述文件
3. iOS **设置 → 通用 → VPN与设备管理** → 信任该证书
4. iOS **设置 → 通用 → 关于本机 → 证书信任设置** → 打开完全信任

### MITM 主机名需要手动填（重要）

远程订阅文件里**不能**包含 `[MITM]` 段 —— QX 会报 `INVALID LINE`。
而这些主机名在 fmz200 的源文件里本身也是**注释状态**（`# hostname = ...`），QX 不会自动应用。

所以订阅只提供规则，主机名要手填（只需做一次）：

1. 打开 [`output/MITM-hostnames.txt`](output/MITM-hostnames.txt)
2. 全选复制（17 行，共 977 个主机名）
3. QX → 风车 → **重写** → **MITM** → **主机名** → 右上角 `+`
4. 把内容粘贴进去保存（QX 会自动按逗号拆分；若粘贴不进去，就逐行分 17 次添加）

> 不填主机名 → 去广告完全无效；填错/填少 → 对应 App 无效。只有分流规则（拦截域名）不需要 MITM。

---

## 三、更新规则

### 自动（推荐）

已内置 `.github/workflows/update.yml`，每个仓库每天 UTC 20:00（北京时间 04:00）自动拉取上游最新规则并提交。
也可在仓库 **Actions** 页面手动 `Run workflow`。

仓库更新后，QX 里右滑订阅条目点更新即可。

### 手动

```powershell
# 联网拉取最新上游并重建
pwsh -File scripts/merge.ps1 -SourceMode remote

# 用 scripts/sources/ 里的缓存离线重建（无需联网）
pwsh -File scripts/merge.ps1 -SourceMode local
```

> 若提示脚本被禁止运行：`pwsh -ExecutionPolicy Bypass -File scripts/merge.ps1`

---

## 四、合并了什么

### 分流（`QX-AllInOne-Filter.conf`）

| 上游 | 说明 |
| :-- | :-- |
| [AWAvenue 秋风广告规则](https://github.com/TG-Twilight/AWAvenue-Ads-Rule) | 国内 App 精准、误杀低 |
| [fmz200/wool_scripts](https://github.com/fmz200/wool_scripts) | 按 App 分类 |
| [NobyDa/Script](https://github.com/NobyDa/Script) | 老牌稳定 |
| [limbopro/Adblock4limbo](https://github.com/limbopro/Adblock4limbo) | 网站广告 |
| BanAD / easylistchina | 补充通用与中文广告域名 |

处理方式：**跨源去重**，策略统一归一化为 `reject`，非拦截策略（如 `DIRECT` 路由规则）不并入，避免污染分流决策。

### 重写（`QX-AllInOne-Rewrite.conf`）

| 上游 | 说明 |
| :-- | :-- |
| fmz200 `rewrite.snippet` | 去广告主力，覆盖约 730 款 App/小程序 |
| XWebAds | X(Twitter) 网页版去广告 |
| BoxJS | 许多脚本的配置依赖 |
| app2smile | 哔哩哔哩 / 贴吧 / Spotify |
| limbopro | YouTube / 知乎 / 内容农场 |
| curtinp118 | Notability / 蛋蛋不语 / DreamFace 会员解锁 |

**关键处理**：fmz200 的 `rewrite.snippet` 文件名虽是 rewrite，实际是**分流 + 重写混合文件**
（4384 行中约 2661 条是分流规则）。本脚本按行类型拆分归位——直接把它当重写订阅用，那些分流规则会全部失效。

---

## 五、实测数据（构建时校验）

| 项目 | 数值 |
| :-- | :-- |
| 分流规则 | 17753 条（642 KB，非 `reject` 策略 0 条） |
| 重写规则 | 1641 条 |
| MITM 主机名 | 977 个（分 17 行输出） |
| 最长行 | 1302 字符 |

脚本每次运行都会打印各项计数，可据此确认合并是否正常。

---

## 六、常见问题

**Q：加了规则完全没反应？**
A：99% 是 MITM 证书没配全，见上面「必做四步」。注意漏配时 QX **不会报错**。

**Q：某些 App 去广告无效？**
A：该 App 若走 TCP 或域名不可 MITM（如抖音系、起点），QX 结构上做不到，与规则无关。
部分 App 需清缓存或重装才生效。

**Q：更新订阅报 404 / 网络错误？**
A：① 仓库是否 Public；② 分支名是否 `main`；③ 国内直连 `raw.githubusercontent.com` 常被墙 —— 换个节点再更新，或改用 Gitee。

**Q：会不会误杀正常功能？**
A：分流订阅只含 `reject` 规则，不含代理策略，不会改变流量走向；但去广告规则本身可能误杀，出问题先在 QX 里禁用重写订阅逐项排查。

**Q：能再加一个「只去广告、不解锁」的版本吗？**
A：可以。编辑 `scripts/merge.ps1` 里 `$sources` 数组，注释掉 `Unlock-*` 三项即可。

---

## 免责声明

- 本仓库仅对公开开源规则做**合并与格式归一化**，不生产规则，所有规则版权归各原作者所有。
- 会员解锁类重写通过伪造服务端返回绕过付费校验，**违反 App 用户协议，存在账号封禁风险**，仅供学习研究，请勿用于商业用途。
- 分流规则由各上游项目维护，本项目不对规则的准确性、合法性作任何保证，使用后果自负。
- 请遵守当地法律法规及目标服务的使用条款。
