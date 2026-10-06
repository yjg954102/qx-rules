#!/usr/bin/env pwsh
<#
.SYNOPSIS
  合并多个开源 Quantumult X 去广告/解锁资源为单一订阅文件。

.DESCRIPTION
  输出两个文件，分别对应 QX 的两种订阅类型（QX 不支持单个 URL 同时承担分流+重写）：
    output/QX-AllInOne-Filter.conf   -> 放 [filter_remote]
    output/QX-AllInOne-Rewrite.conf  -> 放 [rewrite_remote]

.PARAMETER SourceMode
  local  : 优先使用 scripts/sources/ 下已下载的源文件；缺失时回退为联网下载（默认）
  remote : 始终联网下载最新上游

.EXAMPLE
  pwsh -File scripts/merge.ps1
  pwsh -File scripts/merge.ps1 -SourceMode remote
#>
[CmdletBinding()]
param(
  [ValidateSet('local','remote')]
  [string]$SourceMode = 'local',

  # 仓库根目录。留空时自动推断：优先脚本所在目录的上一级，其次当前工作目录
  [string]$RepoRoot
)

$ErrorActionPreference = 'Stop'
$ProgressPreference    = 'SilentlyContinue'

# ---------- 路径 ----------
$scriptDir = if ($PSScriptRoot) { $PSScriptRoot } else { (Get-Location).Path }
if (-not $RepoRoot) {
  $candidate = Split-Path -Parent $scriptDir
  # 若推断出的是 scripts 的父级且存在 output/ 或 .git，就认它为仓库根
  $RepoRoot = if ((Test-Path (Join-Path $candidate 'output')) -or (Test-Path (Join-Path $candidate '.git'))) {
    $candidate
  } elseif ((Test-Path (Join-Path (Get-Location).Path 'output'))) {
    (Get-Location).Path
  } else {
    $candidate
  }
}
$srcDir = Join-Path $scriptDir 'sources'
$outDir = Join-Path $RepoRoot  'output'
$enc    = [System.Text.UTF8Encoding]::new($false)

New-Item -ItemType Directory -Force -Path $srcDir,$outDir | Out-Null

# ---------- 源清单 ----------
# Kind: filter = 纯分流；rewrite = 纯重写；mixed = 分流+重写混合（需按行分类）
$sources = @(
  [pscustomobject]@{ Name='AWAvenue';       Kind='filter';  File='AWAvenue.list';       Url='https://raw.githubusercontent.com/TG-Twilight/AWAvenue-Ads-Rule/main/Filters/AWAvenue-Ads-Rule-QuantumultX.list' }
  [pscustomobject]@{ Name='fmz200-filter';  Kind='filter';  File='fmz200-filter.list';  Url='https://raw.githubusercontent.com/fmz200/wool_scripts/main/QuantumultX/filter/filter.list' }
  [pscustomobject]@{ Name='NobyDa';         Kind='filter';  File='NobyDa.list';         Url='https://raw.githubusercontent.com/NobyDa/Script/master/QuantumultX/AdRule.list' }
  [pscustomobject]@{ Name='Adblock4limbo';  Kind='filter';  File='Adblock4limbo.list';  Url='https://raw.githubusercontent.com/limbopro/Adblock4limbo/main/QuantumultX/rule/Adblock4limbo.list' }
  [pscustomobject]@{ Name='BanAD';          Kind='filter';  File='BanAD.list';          Url='https://raw.githubusercontent.com/limbopro/Adblock4limbo/main/QuantumultX/rule/BanAD.list' }
  [pscustomobject]@{ Name='easylistchina';  Kind='filter';  File='easylistchina.list';  Url='https://raw.githubusercontent.com/limbopro/Adblock4limbo/main/QuantumultX/rule/easylistchina.list' }
  # 注意：这个文件名为 rewrite，实际是「分流 + 重写」混合，必须按行拆分
  [pscustomobject]@{ Name='fmz200-rewrite'; Kind='mixed';   File='fmz200-rewrite.snippet'; Url='https://raw.githubusercontent.com/fmz200/wool_scripts/main/QuantumultX/rewrite/rewrite.snippet' }
  [pscustomobject]@{ Name='XWebAds';        Kind='rewrite'; File='XWebAds.snippet';     Url='https://raw.githubusercontent.com/fmz200/wool_scripts/main/QuantumultX/rewrite/XWebAds.snippet' }
  [pscustomobject]@{ Name='BoxJS';          Kind='rewrite'; File='boxjs.conf';          Url='https://raw.githubusercontent.com/chavyleung/scripts/master/box/rewrite/boxjs.rewrite.quanx.conf' }
  [pscustomobject]@{ Name='Bilibili';       Kind='rewrite'; File='bilibili.conf';       Url='https://raw.githubusercontent.com/app2smile/rules/master/module/bilibili-qx.conf' }
  [pscustomobject]@{ Name='Tieba';          Kind='rewrite'; File='tieba.conf';          Url='https://raw.githubusercontent.com/app2smile/rules/master/module/tieba-qx.conf' }
  [pscustomobject]@{ Name='Spotify';        Kind='rewrite'; File='spotify.conf';        Url='https://raw.githubusercontent.com/app2smile/rules/master/module/spotify.conf' }
  [pscustomobject]@{ Name='YouTube';        Kind='rewrite'; File='youtube.conf';        Url='https://raw.githubusercontent.com/limbopro/Adblock4limbo/main/QuantumultX/rewrite/YouTubeAds.conf' }
  [pscustomobject]@{ Name='Zhihu';          Kind='rewrite'; File='zhihu.conf';          Url='https://raw.githubusercontent.com/limbopro/Adblock4limbo/main/QuantumultX/rewrite/Zhihu.conf' }
  [pscustomobject]@{ Name='ContentFarm';    Kind='rewrite'; File='contentfarm.conf';    Url='https://raw.githubusercontent.com/limbopro/Adblock4limbo/main/QuantumultX/rewrite/contentFarm.conf' }
  # 会员解锁类（有账号风险，见 README 免责声明）
  [pscustomobject]@{ Name='Unlock-Notability'; Kind='rewrite'; File='unlock-notability.conf'; Url='https://raw.githubusercontent.com/curtinp118/QuantumultX/main/scripts/notability.conf' }
  [pscustomobject]@{ Name='Unlock-DandanVIP';  Kind='rewrite'; File='unlock-dandanvip.conf';  Url='https://raw.githubusercontent.com/curtinp118/QuantumultX/main/scripts/dandanvip.conf' }
  [pscustomobject]@{ Name='Unlock-DreamFace';  Kind='rewrite'; File='unlock-dreamface.conf';  Url='https://raw.githubusercontent.com/curtinp118/QuantumultX/main/scripts/dreamface.conf' }
)

# ---------- 取源 ----------
function Get-Source {
  param([pscustomobject]$Src)
  $path = Join-Path $srcDir $Src.File
  if ($SourceMode -eq 'local' -and (Test-Path $path)) {
    Write-Host ("   [本地] {0}" -f $Src.File)
    return [System.IO.File]::ReadAllText($path, [System.Text.Encoding]::UTF8)
  }
  Write-Host ("   [下载] {0}" -f $Src.Name)
  $wc = [System.Net.WebClient]::new()
  $wc.Headers.Add('User-Agent','Mozilla/5.0 (QX-Rule-Merger)')
  try {
    $bytes = $wc.DownloadData($Src.Url)
    $text  = [System.Text.Encoding]::UTF8.GetString($bytes)
    [System.IO.File]::WriteAllText($path, $text, $enc)   # 落盘缓存，供 local 模式复用
    return $text
  } finally { $wc.Dispose() }
}

# ---------- 行分类 ----------
function Get-LineKind {
  param([string]$Line)
  # 分流规则：<type>, <value>, <policy>
  if ($Line -match '(?i)^\s*(host|host-suffix|host-keyword|host-wildcard|domain|domain-suffix|domain-keyword|domain-wildcard|ip-cidr|ip6-cidr|ip-asn|geoip|user-agent)\s*,\s*.+,\s*\w+') { return 'filter' }
  # 重写规则：<url正则> url <action> [args]
  if ($Line -match '(?i)\surl(-and-header)?\s+\S') { return 'rewrite' }
  if ($Line -match '(?i)^\s*(hostname|host-name)\s*=') { return 'mitm' }
  return 'unknown'
}

# ---------- 聚合 ----------
$filterSeen = [System.Collections.Generic.HashSet[string]]::new()
$filterList = [System.Collections.Generic.List[string]]::new()
$rwSeen     = [System.Collections.Generic.HashSet[string]]::new()
$rwList     = [System.Collections.Generic.List[string]]::new()
$hostSeen   = [System.Collections.Generic.HashSet[string]]::new()
$skipped    = 0

Write-Host "== 解析上游 =="
foreach ($s in $sources) {
  $text = Get-Source -Src $s
  $section = ''
  $fAdd = 0; $rAdd = 0; $hAdd = 0

  foreach ($raw in ($text -split "`r?`n")) {
    $l = $raw.Trim()
    if (-not $l) { continue }
    if ($l.StartsWith('#!')) { continue }
    if ($l -match '^\[(.+?)\]\s*$') { $section = $Matches[1].ToLowerInvariant(); continue }
    if ($l.StartsWith('#') -or $l.StartsWith(';') -or $l.StartsWith('//')) { continue }

    # 段落上下文优先：位于 [rewrite_local] 内的行一律按重写处理
    $kind = Get-LineKind -Line $l
    if ($section -eq 'rewrite_local' -and $kind -eq 'unknown') { $kind = 'rewrite' }

    # MITM 主机名收集（阻止重写失效的关键一步）
    if ($kind -eq 'mitm' -or $section -eq 'mitm') {
      if ($l -match '(?i)^\s*(hostname|host-name)\s*=\s*(.+)$') {
        foreach ($x in ($Matches[2] -split ',')) {
          $x = ($x -replace '[\r\n\t]','').Trim()
          if ($x -and $hostSeen.Add($x)) { $hAdd++ }
        }
      }
      continue
    }

    switch ($kind) {
      'filter' {
        $p = $l -split ','
        $type = $p[0].Trim()
        $val  = ($p[1..($p.Count-2)] -join ',').Trim()
        $pol  = $p[-1].Trim().ToLowerInvariant()
        if ($pol -ne 'reject') { $skipped++; break }   # 非拦截策略（如 DIRECT 路由）不并入广告集
        $norm = "$type,$val,reject"
        if ($filterSeen.Add($norm.ToLowerInvariant())) { $filterList.Add($norm) | Out-Null; $fAdd++ }
      }
      'rewrite' {
        if ($rwSeen.Add($l.ToLowerInvariant())) { $rwList.Add($l) | Out-Null; $rAdd++ }
      }
      default { $skipped++ }
    }
  }
  Write-Host ("   {0,-20} 分流+{1,-6} 重写+{2,-5} MITM+{3}" -f $s.Name, $fAdd, $rAdd, $hAdd)
}

$hosts = @($hostSeen | Sort-Object)
$now   = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'

# ---------- 写分流订阅 ----------
# 注意：远程订阅必须是「纯净规则列表」
#   ✗ 不能有 [filter_local] 段头、#! 元数据行 —— QX 会报 INVALID LINE
#   ✓ 只能是一行一条规则
[System.IO.File]::WriteAllLines((Join-Path $outDir 'QX-AllInOne-Filter.conf'), ($filterList | Sort-Object), $enc)

# ---------- 写重写订阅 ----------
# 同理：只输出重写规则行，不带段头与元数据
[System.IO.File]::WriteAllLines((Join-Path $outDir 'QX-AllInOne-Rewrite.conf'), $rwList, $enc)

# ---------- 单独导出 MITM 主机名清单 ----------
# 远程订阅里没有 [MITM] 段，这些主机名必须由用户在 QX 的 MITM 界面手动填入。
# 每行最多 60 个，便于整段复制。
$hostLines = @()
for ($i = 0; $i -lt $hosts.Count; $i += 60) {
  $hostLines += (($hosts[$i..([Math]::Min($i+59, $hosts.Count-1))]) -join ', ')
}
[System.IO.File]::WriteAllLines((Join-Path $outDir 'MITM-主机名.txt'), $hostLines, $enc)

# ---------- 汇总 ----------
Write-Host ''
Write-Host '== 输出 =='
Write-Host ("   分流规则 {0} 条   重写规则 {1} 条   MITM 主机名 {2} 个   跳过 {3} 行" -f $filterList.Count, $rwList.Count, $hosts.Count, $skipped)
Get-ChildItem (Join-Path $outDir 'QX-AllInOne-*.conf') | ForEach-Object {
  Write-Host ("   {0}  {1} KB" -f $_.Name, [math]::Round($_.Length/1KB,1))
}
