#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""versioncheck.py — 화면을 바꾼 PR 이 화면 버전(web/versions.json)을 올렸는지 본다(2026-11-26).

  python3 versioncheck.py                 origin/main 과의 갈림점 대비 지금 작업 트리(커밋 안 한 변경 포함)
  python3 versioncheck.py --base <커밋>    비교 기준을 바꾼다

규칙
  실험실 먼저(2026-11-27 사용자 결정): web/src/labs/, web/src/styles/, web/labs.html 과 공용(web/src/components/, lib/, types.ts, index.css, brief.css) → labs 를 올린다.
    메인도 같은 앱을 빌드하지만 새 기능은 LAB 플래그 뒤에 두므로 main 은 올리지 않는다. main 은 메인 전환 PR 에서 labs 와 같게 올린다
    (LAB 밖에서 메인이 바뀌는지는 reviewer 가 본다).
  메인만: web/index.html, 옛 web/src/App.tsx, main.tsx → main 을 올린다
'올린다'는 기준 커밋의 값과 다르면 된다. 기준 커밋에 versions.json 이 없으면 통과한다.
결과: VERSIONCHECK PASS / FAIL 한 줄과 이유. FAIL 이면 종료 코드 1. 저장소 파일을 바꾸지 않는다.
"""
import json, subprocess, sys

VF = 'web/versions.json'
MAIN = ('web/src/App.tsx', 'web/src/main.tsx', 'web/index.html')   # 2026-11-27 실험실 먼저: web/src/labs 변경은 labs 만 올린다(메인 전환 PR 에서 main)
LABS = ('web/src/labs/', 'web/labs.html', 'web/src/styles/')
SHARED = ('web/src/components/', 'web/src/lib/', 'web/src/types.ts', 'web/src/index.css', 'web/src/brief.css')

def git(*a):
    return subprocess.run(['git', *a], capture_output=True, text=True)

def hit(files, pats):
    return sorted(f for f in files if any(f == p or (p.endswith('/') and f.startswith(p)) for p in pats))

def main():
    args = sys.argv[1:]
    base = args[args.index('--base') + 1] if '--base' in args else git('merge-base', 'origin/main', 'HEAD').stdout.strip()
    if not base:
        print('VERSIONCHECK FAIL — 기준 커밋을 못 찾음(origin/main 을 fetch 했는지 확인)'); return 1
    files = set(git('diff', '--name-only', base).stdout.split()) | set(git('ls-files', '--others', '--exclude-standard', 'web').stdout.split())
    old = git('show', '%s:%s' % (base, VF))
    if old.returncode != 0:
        print('VERSIONCHECK PASS — 기준 커밋에 %s 가 없음(처음 도입)' % VF); return 0
    o, n = json.loads(old.stdout), json.load(open(VF, encoding='utf-8'))
    need = {'main': hit(files, MAIN), 'labs': hit(files, LABS + SHARED)}
    bad = []
    for k, fs in need.items():
        if fs and o.get(k) == n.get(k):
            bad.append('%s 버전이 %s 그대로 — 바뀐 파일: %s' % (k, n.get(k), ', '.join(fs[:4]) + (' 외 %d개' % (len(fs) - 4) if len(fs) > 4 else '')))
    if bad:
        print('VERSIONCHECK FAIL'); [print('  - ' + b) for b in bad]
        print('  %s 의 값을 올린다(메인과 실험실이 같은 화면이면 두 값을 같게)' % VF); return 1
    print('VERSIONCHECK PASS — main %s → %s, labs %s → %s' % (o.get('main'), n.get('main'), o.get('labs'), n.get('labs')))
    return 0

if __name__ == '__main__':
    sys.exit(main())
