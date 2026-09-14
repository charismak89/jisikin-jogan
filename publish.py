#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""publish.py — 회차 결과물을 저장소에 반영하고(아카이브·목록·링크) 커밋, 필요하면 push

publish.ps1(수동 경로)과 같은 일을 한다. 예약 세션이 clone 한 저장소 안에서 돌린다.

사용법 (저장소 루트에서. 기본 입력은 render.py 가 만든 out/ 의 세 파일)
  python3 publish.py                    # 아카이브·목록·링크 정리 + 커밋
  python3 publish.py --push             # + push. 루틴에 저장소가 붙어 있으면 프록시가 자격증명을 넣어 준다.
                                        #   그게 실패하고 GH_TOKEN 환경변수가 있으면 그 토큰으로 한 번 더 시도한다 (로컬용)
  python3 publish.py --dry-run          # 파일만 바꾸고 커밋·push 하지 않음
  python3 publish.py --allow-date       # 발행일이 오늘(KST)이 아니어도 진행 (테스트용)
  python3 publish.py --index X --cal Y --state Z   # 입력 파일 지정

안전장치
  - 새 index.html 의 <meta name="generated"> 날짜가 오늘(KST)이 아니면 중단 (--allow-date 로 해제)
  - 새 calibration.json 의 records 수가 기존보다 적으면 calibration.json 은 건너뛴다
  - 새 state.json 에 issue_date/forecast/closes 가 없으면 state.json 은 건너뛴다
  - 토큰은 인자로 받지 않는다. GH_TOKEN 환경변수가 있을 때만 폴백으로 쓰고 출력에 찍지 않는다
  - 클라우드 세션(Cowork·루틴)의 git 프록시는 PAT 를 그대로 통과시키지 않는다. 자동 발행은 루틴에 저장소를 붙여야 된다
"""
import io, json, os, re, subprocess, sys
from datetime import datetime, timedelta, timezone, date

KST = timezone(timedelta(hours=9))
DOW = '일월화수목금토'   # datetime.weekday: 월=0 → 아래에서 변환
FIRST_ISSUE = date(2026, 8, 21)

def arg(name, default=None):
    if name in sys.argv:
        i = sys.argv.index(name)
        return sys.argv[i + 1] if i + 1 < len(sys.argv) else default
    return default

def read(p):
    return io.open(p, encoding='utf-8').read() if os.path.exists(p) else None

def write(p, s):
    os.makedirs(os.path.dirname(p) or '.', exist_ok=True)
    io.open(p, 'w', encoding='utf-8', newline='').write(s)

def gen_date(html):
    if not html: return None
    m = re.search(r'<meta[^>]*\bname\s*=\s*["\']?generated["\']?[^>]*\bcontent\s*=\s*["\']?(\d{4}-\d{2}-\d{2})', html, re.I | re.S)
    return m.group(1) if m else None

def label(iso):
    d = date.fromisoformat(iso)
    return '%d년 %d월 %d일 (%s)' % (d.year, d.month, d.day, '월화수목금토일'[d.weekday()])

def issue_no(iso):
    d = date.fromisoformat(iso); n, cur = 0, FIRST_ISSUE
    while cur <= d:
        if cur.weekday() < 5: n += 1
        cur += timedelta(days=1)
    return n

def git(*a, check=True, env=None):
    r = subprocess.run(['git'] + list(a), capture_output=True, text=True, env=env)
    if check and r.returncode != 0:
        raise SystemExit('git %s 실패: %s' % (' '.join(a[:2]), (r.stderr or r.stdout).strip()[:400]))
    return r.stdout.strip()

def main():
    repo = os.path.abspath(arg('--repo', '.'))
    os.chdir(repo)
    if not os.path.isdir('.git'): raise SystemExit('[중단] git 저장소가 아님: %s' % repo)
    new_index = arg('--index', os.path.join('out', 'index.html'))
    new_cal = arg('--cal', os.path.join('out', 'calibration.json'))
    new_state = arg('--state', os.path.join('out', 'state.json'))
    dry, push, allow_date = '--dry-run' in sys.argv, '--push' in sys.argv, '--allow-date' in sys.argv
    if not new_index or not os.path.exists(new_index): raise SystemExit('[중단] 새 index.html 없음: %s (render.py 를 먼저 돌린다)' % new_index)
    new_html = read(new_index)
    new_date = gen_date(new_html)
    today = datetime.now(KST).date().isoformat()
    if not new_date: raise SystemExit('[중단] 새 index.html 에서 발행일(meta generated)을 찾지 못함')
    if new_date != today and not allow_date:
        raise SystemExit('[중단] 발행일 %s 가 오늘(KST %s)과 다름. 테스트면 --allow-date' % (new_date, today))

    changed = []
    # 1) 기존 index.html 을 아카이브로
    cur_html = read('index.html'); cur_date = gen_date(cur_html)
    if cur_html and cur_date and cur_date != new_date:
        ap = os.path.join('archive', cur_date + '.html')
        if not os.path.exists(ap):
            body = re.sub(r'(href\s*=\s*["\'])(?!\.\./)style\.css', r'\1../style.css', cur_html)
            write(ap, body); changed.append('archive/%s.html 생성' % cur_date)
    elif cur_date == new_date:
        changed.append('같은 날짜 재발행 — 아카이브 생성 없음')

    # 2) 새 파일 반영
    write('index.html', new_html); changed.append('index.html ← %s' % new_date)
    if new_cal and os.path.exists(new_cal):
        try:
            nc = json.loads(read(new_cal)); n_new = len(nc.get('records') or [])
            oc = read('calibration.json'); n_old = len((json.loads(oc).get('records') or [])) if oc else 0
            if n_new < n_old:
                changed.append('[경고] calibration.json 기록 %d건 < 기존 %d건 — 건너뜀' % (n_new, n_old))
            else:
                write('calibration.json', read(new_cal)); changed.append('calibration.json (%d건)' % n_new)
        except Exception as e:
            changed.append('[경고] calibration.json 이 올바른 JSON 이 아님 — 건너뜀 (%s)' % e)
    if new_state and os.path.exists(new_state):
        try:
            ns = json.loads(read(new_state))
            if not (ns.get('issue_date') and ns.get('forecast') and ns.get('closes')):
                changed.append('[경고] state.json 에 issue_date/forecast/closes 없음 — 건너뜀')
            else:
                write('state.json', read(new_state)); changed.append('state.json (전망 %s)' % ns['forecast'].get('date'))
        except Exception as e:
            changed.append('[경고] state.json 이 올바른 JSON 이 아님 — 건너뜀 (%s)' % e)

    # 3) 아카이브 목록 재생성 (호수 = 2026-08-21 을 제1호로 둔 평일 일련번호)
    files = sorted(f[:-5] for f in os.listdir('archive') if re.match(r'^20\d\d-\d\d-\d\d\.html$', f)) if os.path.isdir('archive') else []
    lines = ['<a class="item" href="./%s.html">%s<span>제 %d 호</span></a>' % (iso, label(iso), issue_no(iso)) for iso in reversed(files)]
    lp = os.path.join('archive', 'index.html'); lt = read(lp)
    if lt:
        block = '<!-- ARCHIVE_LIST_START -->\n' + '\n'.join(lines) + '\n<!-- ARCHIVE_LIST_END -->'
        nt = re.sub(r'<!-- ARCHIVE_LIST_START -->.*?<!-- ARCHIVE_LIST_END -->', lambda m: block, lt, flags=re.S)
        if nt != lt: write(lp, nt); changed.append('archive/index.html 목록 %d개' % len(files))

    # 4) 새 index.html 의 지난 회차 링크를 실제 파일 기준으로
    recent = [iso for iso in reversed(files) if iso < new_date][:3]
    links = ['<a href="./archive/%s.html">%d/%d (%s)</a>' % (iso, date.fromisoformat(iso).month, date.fromisoformat(iso).day, '월화수목금토일'[date.fromisoformat(iso).weekday()]) for iso in recent]
    links.append('<a href="./archive/">전체 보기</a>')
    idx = read('index.html')
    idx2 = re.sub(r'<div class="arch">.*?</div>', lambda m: '<div class="arch">' + ' '.join(links) + '</div>', idx, count=1, flags=re.S)
    if idx2 != idx: write('index.html', idx2); changed.append('지난 회차 링크 %d개' % len(recent))

    # 5) 평일 누락 참고
    for c in changed: print('·', c)
    if dry:
        print('(dry-run) 커밋·push 하지 않음'); print(git('status', '--short')); return 0

    # 6) 커밋
    if not git('status', '--porcelain'):
        print('변경 없음 — 커밋 생략'); return 0
    git('add', '-A')
    git('-c', 'user.name=jisikin-jogan bot', '-c', 'user.email=bot@jisikin.local', 'commit', '-q', '-m', 'brief: %s 발행' % new_date)
    sha = git('rev-parse', '--short', 'HEAD')
    print('커밋 %s — brief: %s 발행' % (sha, new_date))
    if not push:
        print('push 안 함 (--push 없음)'); return 0
    # 1차: 자격증명 없이 push. 루틴/클라우드 세션에 저장소가 붙어 있으면 git 프록시가 자격증명을 넣는다.
    env0 = dict(os.environ); env0['GIT_TERMINAL_PROMPT'] = '0'
    r = subprocess.run(['git', 'push', 'origin', 'HEAD:main'], capture_output=True, text=True, env=env0)
    if r.returncode == 0:
        print('push 완료 (프록시 자격증명) — https://charismak89.github.io/jisikin-jogan/ 에 1~2분 뒤 반영'); return 0
    first_err = (r.stderr or r.stdout).strip()[:300]
    token = os.environ.get('GH_TOKEN', '').strip()
    if not token:
        raise SystemExit('[실패] push 실패 (루틴에 저장소가 붙어 있지 않거나 권한 없음): %s\n세 파일을 수동 경로로 전달할 것' % first_err)
    # 2차: GH_TOKEN 폴백 (로컬 실행용. 클라우드 프록시는 이 토큰을 통과시키지 않는다)
    import tempfile
    fd, askpass = tempfile.mkstemp(prefix='askpass-', suffix='.sh')
    os.write(fd, b'#!/bin/sh\ncase "$1" in *sername*) echo x-access-token;; *) echo "$GH_TOKEN";; esac\n'); os.close(fd)
    os.chmod(askpass, 0o700)
    env = dict(os.environ); env['GIT_ASKPASS'] = askpass; env['GIT_TERMINAL_PROMPT'] = '0'
    try:
        r = subprocess.run(['git', '-c', 'credential.helper=', 'push', 'origin', 'HEAD:main'], capture_output=True, text=True, env=env)
    finally:
        try: os.remove(askpass)
        except Exception: pass
    if r.returncode != 0:
        msg = (r.stderr or r.stdout).replace(token, '***')
        raise SystemExit('[실패] push 실패: %s' % msg.strip()[:400])
    print('push 완료 (GH_TOKEN) — https://charismak89.github.io/jisikin-jogan/ 에 1~2분 뒤 반영')
    return 0

if __name__ == '__main__':
    sys.exit(main())
