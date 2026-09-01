# 지식인 조간 - 원클릭 발행 스크립트 v3
# 다운로드 폴더의 최신 index.html 을 반영하고, 아카이브를 git 이력에서 자동 복구합니다.

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$repo = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $repo
$utf8 = New-Object System.Text.UTF8Encoding($false)
$DOW  = @("일","월","화","수","목","금","토")

function Say($msg, $color = "White") { Write-Host $msg -ForegroundColor $color }

function Get-GenDate([string]$html) {
    if (-not $html) { return $null }
    # 속성 순서가 바뀌어도, 따옴표 종류가 달라도 인식
    if ($html -match '(?is)<meta[^>]*\bname\s*=\s*["'']?generated["'']?[^>]*\bcontent\s*=\s*["'']?(\d{4}-\d{2}-\d{2})') { return $Matches[1] }
    if ($html -match '(?is)<meta[^>]*\bcontent\s*=\s*["'']?(\d{4}-\d{2}-\d{2})[^>]*\bname\s*=\s*["'']?generated') { return $Matches[1] }
    return $null
}
function Read-Utf8($path) { if (Test-Path $path) { return [IO.File]::ReadAllText($path, $utf8) } return $null }
function Write-Utf8($path, $text) { [IO.File]::WriteAllText($path, $text, $utf8) }
function Label($iso) {
    $d = [datetime]::ParseExact($iso, "yyyy-MM-dd", $null)
    return "{0}년 {1}월 {2}일 ({3})" -f $d.Year, $d.Month, $d.Day, $DOW[[int]$d.DayOfWeek]
}

Say "`n=== 지식인 조간 발행 v5 ===`n" Cyan

# ── 0) 사전 점검 ────────────────────────────────────────────────
if (-not (Test-Path (Join-Path $repo ".git"))) {
    Say "[중단] 이 폴더는 git 저장소가 아닙니다: $repo" Red
    Say "       publish.bat 이 jisikin-jogan 폴더 안에 있는지 확인해 주세요." Gray
    Read-Host "`nEnter 키를 누르면 닫힙니다"; exit 1
}

# ── 0-b) 원격 최신 내용 먼저 받아오기 (노트북 여러 대를 쓸 때 필수) ──
Say "원격 확인 중..." Gray
git fetch --quiet 2>$null
$behind = $null
try { $behind = git rev-list --count "HEAD..@{u}" 2>$null } catch { }
if ($behind -and [int]$behind -gt 0) {
    Say "  원격에 새 커밋 ${behind}개가 있습니다. 먼저 받아옵니다." Yellow
    $dirty = git status --porcelain
    if ($dirty) {
        Say "`n[중단] 로컬에 저장 안 된 변경이 있어 안전하게 받아올 수 없습니다." Red
        Say "       아래 파일을 먼저 정리하거나 되돌린 뒤 다시 실행해 주세요:" Gray
        $dirty | ForEach-Object { Say "         $_" DarkGray }
        Read-Host "`nEnter 키를 누르면 닫힙니다"; exit 1
    }
    git pull --rebase
    if ($LASTEXITCODE -ne 0) {
        Say "`n[중단] 원격 내용을 받아오지 못했습니다. 위 메시지를 확인해 주세요." Red
        Say "       충돌이 났다면 다른 노트북에서 올린 내용과 겹친 것입니다." Gray
        Read-Host "`nEnter 키를 누르면 닫힙니다"; exit 1
    }
    Say "  받아오기 완료" Green
} else {
    Say "  최신 상태입니다" Gray
}

# ── 1) 다운로드 폴더에서 새 index.html 찾기 ──────────────────────
$dl = $null
try {
    $key = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders"
    $raw = (Get-ItemProperty -Path $key -Name "{374DE290-123F-4565-9164-39C4925E467B}" -ErrorAction Stop)."{374DE290-123F-4565-9164-39C4925E467B}"
    if ($raw) { $dl = [Environment]::ExpandEnvironmentVariables($raw) }
} catch { }
if (-not $dl -or -not (Test-Path $dl)) { $dl = Join-Path $env:USERPROFILE "Downloads" }
Say "다운로드  : $dl" DarkGray

$new = Get-ChildItem -Path $dl -Filter "index*.html" -File -ErrorAction SilentlyContinue |
       Sort-Object LastWriteTime -Descending | Select-Object -First 1
$repairOnly = $false
if (-not $new) {
    Say "`n다운로드 폴더에 새 index.html 이 없습니다." Yellow
    if ((Read-Host "아카이브 점검/복구만 실행할까요? (y/N)") -ne "y") {
        Say "취소했습니다." Gray; exit 0
    }
    $repairOnly = $true
    Say "`n[아카이브 점검 모드]" Cyan
}
if (-not $repairOnly) { Say "새 파일   : $($new.Name)  ($($new.LastWriteTime.ToString('MM-dd HH:mm')))" Gray }

$newText = if ($repairOnly) { $null } else { Read-Utf8 $new.FullName }
$today = (Get-Date).ToString("yyyy-MM-dd")
$newDate = if ($repairOnly) { Get-GenDate (Read-Utf8 (Join-Path $repo "index.html")) } else { Get-GenDate $newText }

if (-not $newDate -and -not $repairOnly) {
    Say "`n[중단] 이 파일에서 발행일을 못 찾았습니다." Red
    Say "       <meta name=`"generated`" content=`"YYYY-MM-DD...`"> 태그가 있어야 합니다." Gray
    Say "       파일을 직접 수정하셨다면 이 태그가 지워졌을 수 있습니다." Gray
    Read-Host "`nEnter 키를 누르면 닫힙니다"; exit 1
}
Say "발행일    : $newDate" Gray
if (-not $repairOnly -and $newDate -ne $today) {
    Say "[경고] 파일 발행일($newDate)이 오늘($today)과 다릅니다." Yellow
    if ((Read-Host "그래도 발행할까요? (y/N)") -ne "y") { Say "취소했습니다." Gray; exit 0 }
}

# ── 2) 교체 후 커밋 ─────────────────────────────────────────────
if (-not $repairOnly) {
    $curDate = Get-GenDate (Read-Utf8 (Join-Path $repo "index.html"))
    if ($curDate) { Say "현재 게시 : $curDate" Gray } else { Say "현재 게시 : (발행일 불명)" Yellow }

    Write-Utf8 (Join-Path $repo "index.html") $newText

    # ── 2-b) calibration.json 도 함께 받아온다 (예약 세션이 만들어 준 최신본) ──
    $cal = Get-ChildItem -Path $dl -Filter "calibration*.json" -File -ErrorAction SilentlyContinue |
           Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($cal) {
        try {
            $calText = Read-Utf8 $cal.FullName
            $parsed  = $calText | ConvertFrom-Json          # 깨진 JSON 이면 여기서 멈춘다
            $cnt     = @($parsed.records).Count
            $old     = Read-Utf8 (Join-Path $repo "calibration.json")
            $oldCnt  = 0
            if ($old) { try { $oldCnt = @(($old | ConvertFrom-Json).records).Count } catch { } }
            if ($cnt -lt $oldCnt) {
                Say "[경고] 새 calibration.json 의 기록이 $cnt 건으로 기존 $oldCnt 건보다 적습니다. 건너뜁니다." Yellow
            } else {
                Write-Utf8 (Join-Path $repo "calibration.json") $calText
                Say "캘리브레이션: $($cal.Name) 반영 ($cnt 건)" Gray
                Remove-Item $cal.FullName -ErrorAction SilentlyContinue
            }
        } catch {
            Say "[경고] $($cal.Name) 이 올바른 JSON 이 아니라 건너뜁니다." Yellow
        }
    } else {
        Say "캘리브레이션: 새 파일 없음 (기존 유지)" DarkGray
    }
    if (git status --porcelain) {
        git add -A | Out-Null
        git commit -m "brief: $newDate 발행" | Out-Null
        Say "커밋      : brief: $newDate 발행" Gray
    } else {
        Say "커밋      : 변경 없음 (같은 내용)" Yellow
    }
}

# ── 3) git 이력에서 아카이브 복구 ────────────────────────────────
Say "`n아카이브 점검 중..." Gray
$archDir = Join-Path $repo "archive"
if (-not (Test-Path $archDir)) { New-Item -ItemType Directory -Path $archDir | Out-Null }

$seen = New-Object 'System.Collections.Specialized.OrderedDictionary'
foreach ($sha in (git log --format=%H -- index.html)) {
    $txt = (git show "$($sha):index.html" 2>$null) -join "`r`n"
    $d = Get-GenDate $txt
    if ($d -and -not $seen.Contains($d)) { $seen.Add($d, $txt) }   # 최신 커밋 우선
}

$added = @()
foreach ($d in @($seen.Keys)) {
    if ($d -eq $newDate) { continue }                     # 오늘자는 index.html 로 이미 게시 중
    $path = Join-Path $archDir "$d.html"
    if (Test-Path $path) { continue }
    $body = $seen[$d]
    # 외부 CSS를 쓰는 파일만 경로 보정 (인라인 CSS 파일은 그대로 둠)
    $body = $body -replace '(href\s*=\s*["''])style\.css', '${1}../style.css'
    Write-Utf8 $path $body
    $added += $d
    Say "  + archive/$d.html 복구" Green
}
if ($added.Count -eq 0) { Say "  누락 없음" Gray }

# ── 3-b) 기존 아카이브 파일 CSS 경로 정규화 ─────────────────────
$fixed = 0
foreach ($f in (Get-ChildItem $archDir -Filter "20??-??-??.html")) {
    $t = Read-Utf8 $f.FullName
    $n = $t -replace '(href\s*=\s*["''])(?!\.\./)style\.css', '${1}../style.css'
    if ($n -ne $t) { Write-Utf8 $f.FullName $n; $fixed++ }
}
if ($fixed -gt 0) { Say "  CSS 경로 보정: ${fixed}개 파일" Green }

# ── 4) 아카이브 목록 재생성 ─────────────────────────────────────
$files = Get-ChildItem $archDir -Filter "20??-??-??.html" | Sort-Object Name
$order = @{}; $i = 1
foreach ($f in $files) { $order[$f.BaseName] = $i; $i++ }     # 오래된 것이 제1호
$lines = @()
foreach ($f in ($files | Sort-Object Name -Descending)) {      # 최신이 위
    $iso = $f.BaseName
    $lines += "<a class=""item"" href=""./$iso.html"">$(Label $iso)<span>제 $($order[$iso]) 호</span></a>"
}
$listPath = Join-Path $archDir "index.html"
$list = Read-Utf8 $listPath
$block = "<!-- ARCHIVE_LIST_START -->`r`n" + ($lines -join "`r`n") + "`r`n<!-- ARCHIVE_LIST_END -->"
$newList = [regex]::Replace($list, '(?s)<!-- ARCHIVE_LIST_START -->.*?<!-- ARCHIVE_LIST_END -->', { param($m) $block })
if ($newList -ne $list) { Write-Utf8 $listPath $newList; Say "목록 갱신 : $($files.Count)개 회차" Gray }

# 평일 누락 점검 (공휴일은 구분 못 하므로 참고용)
if ($files.Count -ge 2) {
    $dates = $files | ForEach-Object { [datetime]::ParseExact($_.BaseName, "yyyy-MM-dd", $null) }
    $all   = @($dates) + @([datetime]::ParseExact($newDate, "yyyy-MM-dd", $null))
    $cur   = ($all | Sort-Object)[0]; $end = ($all | Sort-Object)[-1]
    $gaps  = @()
    while ($cur -lt $end) {
        if ($cur.DayOfWeek -ne "Saturday" -and $cur.DayOfWeek -ne "Sunday" -and ($all -notcontains $cur)) {
            $gaps += $cur.ToString("yyyy-MM-dd")
        }
        $cur = $cur.AddDays(1)
    }
    if ($gaps.Count -gt 0) {
        Say "`n[참고] 아카이브에 없는 평일: $($gaps -join ', ')" Yellow
        Say "       공휴일이면 정상입니다. 아니라면 그날 index.html 을 다시 받아" Gray
        Say "       archive\<날짜>.html 로 저장한 뒤 이 스크립트를 다시 돌리세요." Gray
    }
}

# ── 4-b) index.html 의 "지난 회차" 링크를 실제 파일 기준으로 다시 씀 ──
#     08:00 브리핑이 만들어질 때는 어제자 아카이브가 아직 없어서 링크가 빠진다.
#     아카이브를 만든 지금 시점에는 정확히 알 수 있으므로 여기서 바로잡는다.
$idxPath = Join-Path $repo "index.html"
$idx = Read-Utf8 $idxPath
if ($idx -match '(?s)<div class="arch">.*?</div>') {
    $recent = @($files | Sort-Object Name -Descending | Select-Object -First 3)
    $links = @()
    foreach ($f in $recent) {
        $d = [datetime]::ParseExact($f.BaseName, "yyyy-MM-dd", $null)
        $lbl = "{0}/{1} ({2})" -f $d.Month, $d.Day, $DOW[[int]$d.DayOfWeek]
        $links += "<a href=""./archive/$($f.BaseName).html"">$lbl</a>"
    }
    $links += '<a href="./archive/">전체 보기</a>'
    $newArch = '<div class="arch">' + ($links -join ' ') + '</div>'
    $idx2 = [regex]::Replace($idx, '(?s)<div class="arch">.*?</div>', { param($m) $newArch })
    if ($idx2 -ne $idx) {
        Write-Utf8 $idxPath $idx2
        Say "지난 회차 : $($recent.Count)개 링크 재작성" Gray
    }
} else {
    Say "지난 회차 : arch 블록을 찾지 못해 건너뜀" Yellow
}

# ── 5) 푸시 ─────────────────────────────────────────────────────
if (git status --porcelain) {
    git add -A | Out-Null
    git commit -m "archive: $newDate 기준 정리" | Out-Null
}
Say "`n푸시 중..." Gray
git push
if ($LASTEXITCODE -ne 0) {
    Say "`n[실패] 푸시에 실패했습니다. 위 메시지를 확인해 주세요." Red
    Read-Host "`nEnter 키를 누르면 닫힙니다"; exit 1
}

Say "`n$(if ($repairOnly) { '아카이브 정리 완료!' } else { '발행 완료!' })" Green
Say "1~2분 뒤 반영됩니다 -> https://charismak89.github.io/jisikin-jogan/" Cyan
if (-not $repairOnly) { Remove-Item $new.FullName -ErrorAction SilentlyContinue }
Read-Host "`nEnter 키를 누르면 닫힙니다"