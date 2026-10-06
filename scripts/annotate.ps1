#!/usr/bin/env pwsh
<#
.SYNOPSIS
  从已合并的规则生成「带 APP / 域名注释」的版本，可直接作为 QX 订阅引用。

.DESCRIPTION
  · QX-AllInOne-Rewrite-Annotated.conf —— 重写规则，按 APP 分组，行尾附 ;域名
    远程订阅可用：格式为 <正则> url <动作> [参数]，多余字段被忽略，官方远程样例同样含 ; 注释
  · QX-AllInOne-Filter-Annotated.conf  —— 分流规则（参考版，每条后附 ;主域名）
    ⚠️ 分流规则格式固定为 <type>,<value>,<policy>，没有注释字段，
       这个文件可用作【本地】分流规则，但【不可】作为 filter_remote 订阅（会 INVALID LINE）

.PARAMETER RepoRoot
  仓库根目录。留空时自动推断。
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
$outDir  = Join-Path $RepoRoot 'output'
$srcDir  = Join-Path $scriptDir 'sources'
$enc     = [System.Text.UTF8Encoding]::new($false)
$sep     = ';' * 58

# ---------- 域名提取工具 ----------
$FileExt = @('php','html','htm','js','json','jpg','jpeg','png','gif','webp','css','txt','xml',
             'apk','ipa','zip','mp4','m3u8','ts','svg','ico','woff','woff2','ttf','map')

function Get-Hosts {
  param([string]$Text,[int]$Limit = 3)
  $t = $Text -replace '\\',''
  $found = [System.Collections.Generic.List[string]]::new()
  foreach ($m in [regex]::Matches($t, '(?:\*\.)?(?:[A-Za-z0-9_\-]+\.)+[A-Za-z]{2,}')) {
    $h = $m.Value.Trim('*','.')
    $last = $h.Split('.')[-1].ToLowerInvariant()
    if ($FileExt -contains $last) { continue }
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

$MultiTld = @('com.cn','net.cn','org.cn','gov.cn','edu.cn','ac.cn','com.hk','com.tw','com.au',
              'co.uk','co.jp','co.kr','co.nz','co.in','com.br','com.mx','com.sg','com.my','com.vn',
              'org.uk','net.uk','gov.hk','edu.hk','org.hk','com.ru','com.tr','com.sa','com.ar')
function Get-Root {
  param([string]$V)
  $v = $V.Trim().TrimStart('*','.').TrimStart('-')
  if ($v -match '^\d{1,3}(\.\d{1,3}){3}$') { return $v }
  $p = $v.Split('.') | Where-Object { $_ }
  if ($p.Count -lt 2) { return $v }
  $last2 = ($p[-2..-1] -join '.')
  if ($MultiTld -contains $last2 -and $p.Count -ge 3) { return ($p[-3..-1] -join '.') }
  return $last2
}

# ---------- 1. 收集重写规则并按 APP 分组 ----------
$appRules = [ordered]@{}
function Add-Rule([string]$App,[string]$Rule){
  if (-not $appRules.Contains($App)) { $appRules[$App] = [System.Collections.Generic.List[string]]::new() }
  if (-not $appRules[$App].Contains($Rule)) { $appRules[$App].Add($Rule) }
}

# fmz200 主合集：'# > App名' 标记分组
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

# 其余来源按文件归属
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

# ---------- 2. 写重写注释版（可作为 rewrite_remote 订阅） ----------
$totalRules = 0; foreach ($v in $appRules.Values) { $totalRules += $v.Count }
$rw = [System.Collections.Generic.List[string]]::new()
$rw.Add('; QX 重写规则 —— 已按 APP 分组标注（可作为重写订阅直接引用）')
$rw.Add('; 每行末尾的 ;域名 为注释，QX 会忽略；分组标题标明 APP 名称')
$rw.Add("; 共 $totalRules 条，覆盖 $($appRules.Count) 个 APP/来源")
$rw.Add('; 仍需在 风车 → 重写 → MITM → 主机名 填入主机名（见 MITM-hostnames.txt）')
foreach ($app in ($appRules.Keys | Sort-Object { -$appRules[$_].Count }, { $_ })) {
  $rules = $appRules[$app]
  $hs = [System.Collections.Generic.List[string]]::new()
  foreach ($r in $rules) {
    $sp = $r.IndexOf(' url ')
    $pat = if ($sp -gt 0) { $r.Substring(0, $sp) } else { $r }
    foreach ($h in (Get-Hosts -Text $pat -Limit 3)) { if (-not $hs.Contains($h)) { $hs.Add($h) } }
  }
  $tag = if ($hs.Count) { ' | ' + (($hs | Select-Object -First 3) -join ', ') } else { '' }
  
  $rw.Add($sep)
  $rw.Add((";【{0}】{1} 条规则{2}" -f $app, $rules.Count, $tag))
  $rw.Add($sep)
  foreach ($r in $rules) {
    $sp = $r.IndexOf(' url ')
    $pat = if ($sp -gt 0) { $r.Substring(0, $sp) } else { $r }
    $d = Get-Hosts -Text $pat -Limit 2
    $note = if ($d.Count) { '  ;' + ($d -join ',') } else { '' }
    $rw.Add($r + $note)
  }
  $rw.Add('')
}
[System.IO.File]::WriteAllLines((Join-Path $outDir 'QX-AllInOne-Rewrite-Annotated.conf'), $rw, $enc)

# ---------- 3. 写分流注释版（仅适合本地使用） ----------
$fl = Join-Path $outDir 'QX-AllInOne-Filter.conf'
if (Test-Path $fl) {
  $groups = [ordered]@{
    '后缀匹配（拦截该域名及其全部子域名）' = @('domain-suffix','host-suffix')
    '精确匹配（仅拦截该域名本身）'         = @('domain','host')
    '关键词匹配'                          = @('domain-keyword','host-keyword')
    '通配符匹配'                          = @('domain-wildcard','host-wildcard')
    'IP 段 / 地区 / UA'                   = @('ip-cidr','ip6-cidr','ip-asn','geoip','user-agent')
  }
  $all = [System.IO.File]::ReadAllLines($fl, [System.Text.Encoding]::UTF8) | Where-Object { $_.Trim() }
  $fo = [System.Collections.Generic.List[string]]::new()
  $fo.Add('; QX 分流规则 —— 每条后附 ;主域名 注释')
  $fo.Add('; ⚠️ 分流规则格式为 <type>,<value>,<policy>，没有注释字段。')
  $fo.Add(';    本文件适用于【本地分流规则】，请勿作为 filter_remote 订阅（会 INVALID LINE）')
  $fo.Add("; 共 $($all.Count) 条")
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
      $fo.Add("$l  ;$(Get-Root -V $val)")
    }
  }
  [System.IO.File]::WriteAllLines((Join-Path $outDir 'QX-AllInOne-Filter-Annotated.conf'), $fo, $enc)
}

Write-Host '== 注释版输出 =='
Write-Host ("   重写 $totalRules 条 / APP $($appRules.Count) 个")
Get-ChildItem (Join-Path $outDir '*-Annotated.conf') | ForEach-Object {
  Write-Host ("   {0}  {1} KB" -f $_.Name, [math]::Round($_.Length/1KB,1))
}
