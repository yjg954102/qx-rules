#!/usr/bin/env pwsh
<#
.SYNOPSIS
  生成带 APP / 域名注释的规则版本，并按 APP、按域名拆分出独立订阅文件。

.DESCRIPTION
  QX 解析远程资源时【不支持行尾注释】—— `规则  ;注释` 会被当作 url 动作的参数而报
  「Invalid Line」。因此本脚本的注释一律【独立成行】（以 ; 开头），QX 会正常忽略。

  输出：
    output/QX-AllInOne-Rewrite-Annotated.conf  重写，按 APP 分组 + 规则上方标注域名（可作订阅）
    output/QX-AllInOne-Filter-Annotated.conf   分流，注释独立成行（仅供本地粘贴）
    output/per-app/<APP>.conf                  按 APP 拆分（订阅 tag 写 APP 名即可显示）
    output/per-domain/<域名>.list              按主域名拆分（≥3 条规则）
    output/per-app-订阅清单.txt                 可直接复制的订阅行
    output/per-domain-订阅清单.txt              可直接复制的订阅行

.PARAMETER RepoRoot
  仓库根目录，留空自动推断。
#>
[CmdletBinding()]
param([string]$RepoRoot)

$ErrorActionPreference = 'Stop'
$ProgressPreference    = 'SilentlyContinue'

$scriptDir = if ($PSScriptRoot) { $PSScriptRoot } else { (Get-Location).Path }
if (-not $RepoRoot) {
  $cand = Split-Path -Parent $scriptDir
  $RepoRoot = if ($cand -and (Test-Path (Join-Path $cand 'output'))) { $cand }
              elseif (Test-Path (Join-Path (Get-Location).Path 'output')) { (Get-Location).Path }
              else { $cand }
}
$srcDir = Join-Path $scriptDir 'sources'
$outDir = Join-Path $RepoRoot 'output'
$appDir = Join-Path $outDir 'per-app'
$domDir = Join-Path $outDir 'per-domain'
$enc    = [System.Text.UTF8Encoding]::new($false)
$sep    = ';' + ('=' * 58)

foreach ($d in @($appDir, $domDir)) {
  if (Test-Path $d) { Remove-Item $d -Recurse -Force -ErrorAction SilentlyContinue }
  New-Item -ItemType Directory -Force -Path $d | Out-Null
}
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

# ---------------- 工具 ----------------
$FileExt = @('php','html','htm','js','json','jpg','jpeg','png','gif','webp','css','txt','xml',
             'apk','ipa','zip','mp4','m3u8','ts','svg','ico','woff','woff2','ttf','map')
$MultiTld = @('com.cn','net.cn','org.cn','gov.cn','edu.cn','ac.cn','com.hk','com.tw','com.au',
              'co.uk','co.jp','co.kr','co.nz','co.in','com.br','com.mx','com.sg','com.my','com.vn',
              'org.uk','net.uk','gov.hk','edu.hk','org.hk','com.ru','com.tr','com.sa','com.ar')

function Get-Hosts {
  param([string]$Text, [int]$Limit = 4)
  $t = $Text -replace '\\',''
  $found = [System.Collections.Generic.List[string]]::new()
  foreach ($m in [regex]::Matches($t, '(?:\*\.)?(?:[A-Za-z0-9_\-]+\.)+[A-Za-z]{2,}')) {
    $h = $m.Value.Trim('*','.')
    if ($FileExt -contains $h.Split('.')[-1].ToLowerInvariant()) { continue }
    $found.Add($h)
  }
  foreach ($m in [regex]::Matches($t, '\b\d{1,3}(?:\.\d{1,3}){3}\b')) { $found.Add($m.Value) }
  $out = [System.Collections.Generic.List[string]]::new()
  foreach ($h in ($found | Select-Object -Unique)) {
    $covered = $false
    foreach ($o in $found) { if ($o -ne $h -and $o.EndsWith(".$h")) { $covered = $true; break } }
    if (-not $covered) { $out.Add($h) }
  }
  return @($out | Select-Object -Unique | Select-Object -First $Limit)
}

function Get-Root {
  param([string]$V)
  $v = $V.Trim().TrimStart('*','.').TrimStart('-')
  if ($v -match '^\d{1,3}(\.\d{1,3}){3}$') { return $v }
  $p = @($v.Split('.') | Where-Object { $_ })
  if ($p.Count -lt 2) { return $v }
  $last2 = ($p[-2..-1] -join '.')
  if ($MultiTld -contains $last2 -and $p.Count -ge 3) { return ($p[-3..-1] -join '.') }
  return $last2
}

function Get-SafeName {
  param([string]$Name)
  $s = $Name -replace [char]0x2605, 'unlock-'           # ★ -> unlock-
  foreach ($ch in [System.IO.Path]::GetInvalidFileNameChars()) { $s = $s.Replace($ch, '_') }
  $s = $s -replace '[\s/\\]+', '_'
  $s = $s.Trim('_','.')
  if (-not $s) { $s = 'unknown' }
  if ($s.Length -gt 80) { $s = $s.Substring(0, 80) }
  return $s
}

# ---------------- 收集重写规则，按 APP 分组 ----------------
$appRules = [ordered]@{}
function Add-Rule([string]$App, [string]$Rule) {
  if (-not $appRules.Contains($App)) { $appRules[$App] = [System.Collections.Generic.List[string]]::new() }
  if (-not $appRules[$App].Contains($Rule)) { $appRules[$App].Add($Rule) }
}

$snip = Join-Path $srcDir 'fmz200-rewrite.snippet'
if (Test-Path $snip) {
  $cur = '(未分组)'
  foreach ($raw in [System.IO.File]::ReadAllLines($snip, [System.Text.Encoding]::UTF8)) {
    $l = $raw.Trim()
    if (-not $l) { continue }
    if ($l -match '^#\s*>\s*(.+?)\s*$') { $cur = $Matches[1].Trim(); continue }
    if ($l.StartsWith('#')) { continue }
    if ($l -match '\surl(-and-header)?\s+\S') { Add-Rule $cur $l }
  }
}

$map = @(
  @{ App='Spotify(解锁Premium)'; File='spotify.conf' }
  @{ App='哔哩哔哩';              File='bilibili.conf' }
  @{ App='百度贴吧';              File='tieba.conf' }
  @{ App='X(Twitter)网页版';      File='XWebAds.snippet' }
  @{ App='YouTube';              File='youtube.conf' }
  @{ App='知乎';                  File='zhihu.conf' }
  @{ App='内容农场';              File='contentfarm.conf' }
  @{ App='BoxJS';                File='boxjs.conf' }
  @{ App='★解锁-Notability';      File='unlock-notability.conf' }
  @{ App='★解锁-蛋蛋不语VIP';     File='unlock-dandanvip.conf' }
  @{ App='★解锁-DreamFace';       File='unlock-dreamface.conf' }
)
foreach ($m in $map) {
  $p = Join-Path $srcDir $m.File
  if (-not (Test-Path $p)) { continue }
  foreach ($raw in [System.IO.File]::ReadAllLines($p, [System.Text.Encoding]::UTF8)) {
    $l = $raw.Trim()
    if (-not $l -or $l.StartsWith('#')) { continue }
    if ($l -match '\surl(-and-header)?\s+\S') { Add-Rule $m.App $l }
  }
}

# ---------------- 1. 重写注释版（注释独立成行） ----------------
$rw = [System.Collections.Generic.List[string]]::new()
$rw.Add('; QX 重写规则 —— 已按 APP 分组标注')
$rw.Add('; 注释一律独立成行（QX 不支持行尾注释，会报 Invalid Line）')
$rw.Add('; 用法：可作为 rewrite_remote 订阅，或粘贴到本地重写规则')
$rw.Add('; 仍需在 风车 → 重写 → MITM → 主机名 填入主机名（见 MITM-hostnames.txt）')
$total = 0
$appMeta = [ordered]@{}
foreach ($app in ($appRules.Keys | Sort-Object { -$appRules[$_].Count }, { $_ })) {
  $rules = $appRules[$app]
  $total += $rules.Count
  $hs = [System.Collections.Generic.List[string]]::new()
  foreach ($r in $rules) {
    $sp = $r.IndexOf(' url ')
    $pat = if ($sp -gt 0) { $r.Substring(0, $sp) } else { $r }
    foreach ($h in (Get-Hosts -Text $pat -Limit 4)) { if (-not $hs.Contains($h)) { $hs.Add($h) } }
  }
  $appMeta[$app] = @{ Count = $rules.Count; Hosts = @($hs) }
  $rw.Add($sep)
  $tag = ''
  if ($hs.Count -gt 0) { $tag = ' | ' + (($hs | Select-Object -First 4) -join ', ') }
  $rw.Add(';【' + $app + '】' + $rules.Count + ' 条' + $tag)
  $rw.Add($sep)
  foreach ($r in $rules) {
    $sp = $r.IndexOf(' url ')
    $pat = if ($sp -gt 0) { $r.Substring(0, $sp) } else { $r }
    $d = Get-Hosts -Text $pat -Limit 3
    if ($d.Count) { $rw.Add(';   ' + ($d -join ', ')) }
    $rw.Add($r)
  }
  $rw.Add('')
}
[System.IO.File]::WriteAllLines((Join-Path $outDir 'QX-AllInOne-Rewrite-Annotated.conf'), $rw, $enc)

# ---------------- 2. 按 APP 拆分 + 清单 ----------------
foreach ($app in $appRules.Keys) {
  $fn = (Get-SafeName $app) + '.conf'
  [System.IO.File]::WriteAllLines((Join-Path $appDir $fn), @($appRules[$app]), $enc)
}
$ib = [System.Collections.Generic.List[string]]::new()
$ib.Add('; ============================================================')
$ib.Add('; 按 APP 拆分的重写订阅清单')
$ib.Add('; 用法：QX → 重写 → 规则资源 → + → 路径填下方网址，资源标签填方括号中的 APP 名')
$ib.Add('; 每个 APP 独立订阅 = 可单独启停，且自动跟随仓库更新')
$ib.Add('; ============================================================')
$ib.Add('')
$ib.Add("; 共 $($appRules.Count) 个 APP，按规则数排序：")
$ib.Add('')
foreach ($app in ($appRules.Keys | Sort-Object { -$appRules[$_].Count }, { $_ })) {
  $meta = $appMeta[$app]
  $fn = (Get-SafeName $app) + '.conf'
  $ib.Add("; --- $app  （$($meta.Count) 条）")
  $ib.Add(";     标签: $app")
  $ib.Add(";     路径: https://raw.githubusercontent.com/<用户名>/<仓库名>/main/output/per-app/$fn")
  if ($meta.Hosts.Count) { $ib.Add(';     域名: ' + (($meta.Hosts | Select-Object -First 6) -join ', ')) }
  $ib.Add('')
}
[System.IO.File]::WriteAllLines((Join-Path $outDir 'per-app-订阅清单.txt'), $ib, $enc)

# ---------------- 3. 分流按主域名拆分 ----------------
$flPath = Join-Path $outDir 'QX-AllInOne-Filter.conf'
$byRoot = [ordered]@{}
$all = @()
if (Test-Path $flPath) {
  $all = @([System.IO.File]::ReadAllLines($flPath, [System.Text.Encoding]::UTF8) | Where-Object { $_.Trim() })
  foreach ($l in $all) {
    $parts = $l.Split(',')
    $val = ($parts[1..($parts.Count-2)] -join ',').Trim()
    $root = Get-Root -V $val
    if (-not $byRoot.Contains($root)) { $byRoot[$root] = [System.Collections.Generic.List[string]]::new() }
    $byRoot[$root].Add($l)
  }
}
$big = @($byRoot.Keys | Where-Object { $byRoot[$_].Count -ge 3 } | Sort-Object { -$byRoot[$_].Count }, { $_ })
foreach ($root in $big) {
  [System.IO.File]::WriteAllLines((Join-Path $domDir ((Get-SafeName $root) + '.list')), @($byRoot[$root]), $enc)
}
$db = [System.Collections.Generic.List[string]]::new()
$db.Add('; ============================================================')
$db.Add('; 按主域名拆分的分流订阅清单（仅含规则数 ≥3 的域名）')
$db.Add('; 用法：QX → 分流 → 规则资源 → + → 路径填下方网址，资源标签填域名')
$db.Add('; ============================================================')
$db.Add('')
$db.Add("; 共 $($big.Count) 个域名，覆盖 $((($big | ForEach-Object { $byRoot[$_].Count }) | Measure-Object -Sum).Sum) 条规则")
$db.Add('')
foreach ($root in $big) {
  $db.Add("; --- $root  （$($byRoot[$root].Count) 条）")
  $db.Add(";     标签: $root")
  $db.Add(";     路径: https://raw.githubusercontent.com/<用户名>/<仓库名>/main/output/per-domain/$((Get-SafeName $root)).list")
  $db.Add('')
}
[System.IO.File]::WriteAllLines((Join-Path $outDir 'per-domain-订阅清单.txt'), $db, $enc)

# ---------------- 4. 分流注释版（本地用） ----------------
if (Test-Path $flPath) {
  $fo = [System.Collections.Generic.List[string]]::new()
  $fo.Add('; QX 分流规则 —— 注释独立成行')
  $fo.Add('; ⚠️ 分流格式为 <type>,<value>,<policy> 三元组，无注释字段，')
  $fo.Add(';    本文件仅供【本地分流规则】粘贴，勿作 filter_remote 订阅')
  $fo.Add("; 共 $($all.Count) 条")
  $groups = [ordered]@{
    '后缀匹配（拦截该域名及其全部子域名）' = @('domain-suffix','host-suffix')
    '精确匹配（仅拦截该域名本身）'         = @('domain','host')
    '关键词匹配'                          = @('domain-keyword','host-keyword')
    '通配符匹配'                          = @('domain-wildcard','host-wildcard')
    'IP 段 / 地区 / UA'                   = @('ip-cidr','ip6-cidr','ip-asn','geoip','user-agent')
  }
  foreach ($g in $groups.Keys) {
    $rows = @($all | Where-Object { $groups[$g] -contains ($_.Split(',')[0].Trim().ToLowerInvariant()) })
    if (-not $rows.Count) { continue }
    $fo.Add('')
    $fo.Add($sep)
    $fo.Add("; $g   【$($rows.Count) 条】")
    $fo.Add($sep)
    foreach ($l in $rows) {
      $parts = $l.Split(',')
      $val = ($parts[1..($parts.Count-2)] -join ',').Trim()
      $fo.Add("; $(Get-Root -V $val)")
      $fo.Add($l)
    }
  }
  [System.IO.File]::WriteAllLines((Join-Path $outDir 'QX-AllInOne-Filter-Annotated.conf'), $fo, $enc)
}

Write-Host '== 注释版与拆分文件 =='
Write-Host ("   重写 $total 条 / APP $($appRules.Count) 个")
Write-Host ("   分流 $($all.Count) 条 / 主域名 $($byRoot.Count) 个（≥3 条的 $($big.Count) 个）")
Write-Host ("   output/per-app/    $($appRules.Count) 个文件")
Write-Host ("   output/per-domain/ $($big.Count) 个文件")
