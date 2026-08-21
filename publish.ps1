# 지식인 조간 - 원클릭 발행 스크립트
# 다운로드 폴더의 최신 index.html 을 가져와 아카이브 정리 + 커밋 + 푸시까지 한 번에 처리합니다.

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$repo = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $repo
$utf8 = New-Object System.Text.UTF8Encoding($false)

function Say($msg, $color = "White") { Write-Host $msg -ForegroundColor $color }
function GenDate($path) {
    if (-not (Test-Path $path)) { return $null }
    $html = [IO.File]::ReadAllText($path, $utf8)
    if ($html -match 'name="generated"\s+content="(\d{4}-\d{2}-\d{2})') { return $Matches[1] }
    return $null
}

Say "`n=== 지식인 조간 발행 ===`n" Cyan

# 1) 다운로드 폴더에서 새 index.html 찾기
$dl  = Join-Path $env:USERPROFILE "Downloads"
$new = Get-ChildItem -Path $dl -Filter "index*.html" -File -ErrorAction SilentlyContinue |
       Sort-Object LastWriteTime -Descending | Select-Object -First 1

if (-not $new) {
    Say "[중단] 다운로드 폴더에 index.html 이 없습니다." Red
    Say "       Claude가 보낸 파일을 먼저 다운로드해 주세요: $dl" Gray
    Read-Host "`nEnter 키를 누르면 닫힙니다"; exit 1
}
Say "새 파일   : $($new.Name)  ($($new.LastWriteTime.ToString('MM-dd HH:mm')))" Gray

$newDate = GenDate $new.FullName
$today   = (Get-Date).ToString("yyyy-MM-dd")
if (-not $newDate) {
    Say "[중단] 이 파일에 발행일 정보(generated)가 없습니다. 대시보드 파일이 맞는지 확인해 주세요." Red
    Read-Host "`nEnter 키를 누르면 닫힙니다"; exit 1
}
if ($newDate -ne $today) {
    Say "[경고] 파일의 발행일이 $newDate 인데 오늘은 $today 입니다." Yellow
    if ((Read-Host "그래도 발행할까요? (y/N)") -ne "y") { Say "취소했습니다." Gray; exit 0 }
}

# 2) 현재 index.html 을 아카이브로 이동
$prevDate = GenDate (Join-Path $repo "index.html")
if ($prevDate -and $prevDate -ne $newDate) {
    $archPath = Join-Path $repo "archive\$prevDate.html"
    if (-not (Test-Path $archPath)) {
        $old = [IO.File]::ReadAllText((Join-Path $repo "index.html"), $utf8)
        $old = $old -replace 'href="style\.css"', 'href="../style.css"'
        [IO.File]::WriteAllText($archPath, $old, $utf8)
        Say "아카이브  : archive\$prevDate.html 생성" Gray

        # 3) 아카이브 목록에 한 줄 추가
        $listPath = Join-Path $repo "archive\index.html"
        $list = [IO.File]::ReadAllText($listPath, $utf8)
        if ($list -notmatch [regex]::Escape("./$prevDate.html")) {
            $d   = [datetime]::ParseExact($prevDate, "yyyy-MM-dd", $null)
            $dow = @("일","월","화","수","목","금","토")[[int]$d.DayOfWeek]
            $label = "{0}년 {1}월 {2}일 ({3})" -f $d.Year, $d.Month, $d.Day, $dow
            $issue = (Get-ChildItem (Join-Path $repo "archive") -Filter "20*.html").Count
            $line  = "<a class=""item"" href=""./$prevDate.html"">$label<span>제 $issue 호</span></a>"
            $list  = $list -replace '(<!-- ARCHIVE_LIST_START -->)', "`$1`r`n$line"
            [IO.File]::WriteAllText($listPath, $list, $utf8)
            Say "목록 추가 : 제 $issue 호 ($label)" Gray
        }
    } else {
        Say "아카이브  : archive\$prevDate.html 이미 존재 - 건너뜀" Gray
    }
} elseif ($prevDate -eq $newDate) {
    Say "아카이브  : 같은 날짜 재발행 - 건너뜀" Gray
}

# 4) 새 파일로 교체
Copy-Item $new.FullName (Join-Path $repo "index.html") -Force
Say "교체 완료 : index.html <- $($new.Name)" Gray

# 5) 커밋 + 푸시
$status = git status --porcelain
if (-not $status) { Say "`n변경된 내용이 없습니다. 종료합니다." Yellow; Read-Host "`nEnter"; exit 0 }

git add -A | Out-Null
git commit -m "brief: $newDate 발행" | Out-Null
Say "`n푸시 중..." Gray
git push
if ($LASTEXITCODE -ne 0) {
    Say "`n[실패] 푸시에 실패했습니다. 위 메시지를 확인해 주세요." Red
    Read-Host "`nEnter 키를 누르면 닫힙니다"; exit 1
}

Say "`n발행 완료!" Green
Say "1~2분 뒤 반영됩니다 -> https://charismak89.github.io/jisikin-jogan/" Cyan
Remove-Item $new.FullName -ErrorAction SilentlyContinue
Say "(다운로드 폴더의 $($new.Name) 은 정리했습니다)" DarkGray
Read-Host "`nEnter 키를 누르면 닫힙니다"
