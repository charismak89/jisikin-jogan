#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""regress.py — 렌더 회귀 검사. 고치기 전(origin/main)과 고친 뒤(지금 작업 트리)를 마지막 회차의 같은 입력으로 렌더해 비교한다.

  python3 regress.py                     마지막 'brief:' 커밋의 입력으로
  python3 regress.py --commit <sha>      그 발행 커밋의 입력으로
  python3 regress.py --fill <path>       fill.json 을 직접 지정 (fixtures 가 없던 회차를 시험할 때)

입력: fill = fixtures/last-fill.json (publish.py 가 회차마다 남긴다), perp = fixtures/last-perp.json(있으면),
      state.json · calibration.json = 그 발행 커밋 직전 상태.
결과: 두 쪽 GATE 줄, index.html 바뀐 줄 수, diff 파일 경로. 고친 뒤가 GATE PASS 면 종료 코드 0, 아니면 1, 입력이 없으면 2.
      지난 회차 입력이라 '발행일이 오늘이 아님' 보류만 있으면 통과로 본다.
네트워크를 쓰지 않는다. 저장소 파일을 바꾸지 않는다(임시 폴더에서 돈다).
"""
import difflib, io, os, shutil, subprocess, sys, tempfile

def arg(name):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv and sys.argv.index(name) + 1 < len(sys.argv) else None

def git(*a, binary=False):
    r = subprocess.run(['git'] + list(a), capture_output=True)
    if r.returncode != 0: raise SystemExit('git %s 실패: %s' % (' '.join(a[:2]), r.stderr.decode('utf-8', 'replace').strip()[:300]))
    return r.stdout if binary else r.stdout.decode('utf-8').strip()

SKIP = {'.git', 'out', 'fill.json', 'perp.json', '__pycache__'}

def main():
    root = git('rev-parse', '--show-toplevel'); os.chdir(root)
    b = arg('--commit') or git('log', '-1', '--format=%H', '--grep=^brief: ', 'origin/main')
    if not b: raise SystemExit('발행 커밋(brief:)을 찾지 못함')
    fill = arg('--fill')
    if fill:
        fill_s = io.open(fill, encoding='utf-8').read()
    else:
        try: fill_s = git('show', '%s:fixtures/last-fill.json' % b)
        except SystemExit:
            print('fixtures/last-fill.json 이 %s 에 없음 — publish.py 가 남기기 시작한 뒤의 회차부터 쓸 수 있다. --fill 로 지정할 것' % b[:7]); return 2
    try: perp_s = git('show', '%s:fixtures/last-perp.json' % b)
    except SystemExit: perp_s = None
    state_s, cal_s = git('show', '%s~:state.json' % b), git('show', '%s~:calibration.json' % b)

    tmp = tempfile.mkdtemp(prefix='regress-')
    old, new = os.path.join(tmp, 'old'), os.path.join(tmp, 'new')
    os.makedirs(old)
    tar = git('archive', 'origin/main', binary=True)                       # 고치기 전 = origin/main
    subprocess.run(['tar', '-x', '-C', old], input=tar, check=True)
    shutil.copytree(root, new, ignore=lambda d, names: [n for n in names if n in SKIP])   # 고친 뒤 = 작업 트리
    res = {}
    for side, d in (('old', old), ('new', new)):
        for name, s in (('fill.json', fill_s), ('perp.json', perp_s), ('state.json', state_s), ('calibration.json', cal_s)):
            p = os.path.join(d, name)
            if s is None:
                if os.path.exists(p): os.remove(p)
            else: io.open(p, 'w', encoding='utf-8', newline='').write(s if s.endswith('\n') else s + '\n')
        r = subprocess.run([sys.executable, 'render.py'], cwd=d, capture_output=True, text=True)
        out = (r.stdout + r.stderr).strip().splitlines()
        gate = next((l for l in reversed(out) if l.startswith('GATE')), '(GATE 줄 없음 — render.py 실패, 종료 코드 %d)' % r.returncode)
        io.open(os.path.join(tmp, side + '.log'), 'w', encoding='utf-8').write('\n'.join(out) + '\n')
        page = os.path.join(d, 'out', 'index.html')
        res[side] = (gate, io.open(page, encoding='utf-8').read().splitlines() if os.path.exists(page) else [])
    diff = list(difflib.unified_diff(res['old'][1], res['new'][1], 'old/index.html', 'new/index.html', lineterm='', n=1))
    dp = os.path.join(tmp, 'index.diff'); io.open(dp, 'w', encoding='utf-8').write('\n'.join(diff) + '\n')
    added = sum(1 for l in diff if l.startswith('+') and not l.startswith('+++'))
    removed = sum(1 for l in diff if l.startswith('-') and not l.startswith('---'))
    print('입력: %s 회차 (fill %s)' % (b[:7], fill or 'fixtures'))
    print('고치기 전 %s' % res['old'][0]); print('고친 뒤   %s' % res['new'][0])
    print('index.html +%d −%d 줄 · diff %s · 로그 %s/{old,new}.log' % (added, removed, dp, tmp))
    return 0 if gate_ok(res['new'][0]) else 1

def gate_ok(line):
    """지난 회차 입력이라 '발행일이 오늘이 아님' 보류는 당연하다. 그 밖의 보류 사유가 없으면 통과로 본다."""
    if line.startswith('GATE PASS'): return True
    if not line.startswith('GATE HOLD'): return False
    reasons = [x.strip() for x in line.split('—', 1)[-1].split(' · ') if x.strip()]
    return all(r.startswith('발행일이 오늘이 아님') for r in reasons)

if __name__ == '__main__':
    sys.exit(main())
