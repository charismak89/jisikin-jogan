#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""template.html + fill.json -> index.html

회차 세션은 template.html 을 열지 않는다. 플레이스홀더 값만 fill.json 에 쓰고
이 스크립트를 돌린다. CSS 13KB 를 매일 다시 출력하지 않기 위한 장치다.

사용: python3 fill.py                       (template.html / fill.json / index.html)
      python3 fill.py <tpl> <fill> <out>
"""
import io, json, re, sys

tpl_p  = sys.argv[1] if len(sys.argv) > 1 else 'template.html'
fill_p = sys.argv[2] if len(sys.argv) > 2 else 'fill.json'
out_p  = sys.argv[3] if len(sys.argv) > 3 else 'index.html'

tpl  = io.open(tpl_p, encoding='utf-8').read()
vals = json.load(io.open(fill_p, encoding='utf-8'))

need    = set(re.findall(r'\{\{([A-Z_]+)\}\}', tpl))
missing = sorted(need - set(vals))
extra   = sorted(set(vals) - need)

out = tpl
for k, v in vals.items():
    out = out.replace('{{%s}}' % k, str(v))
left = sorted(set(re.findall(r'\{\{([A-Z_]+)\}\}', out)))

if missing or left:
    print('FAIL 채우지 못한 자리:', missing or left)
    sys.exit(1)

# 접힘 상태 글자수
body = re.sub(r'<(style|script).*?</\1>', '', out, flags=re.S)
vis  = re.sub(r'<details.*?</details>', '', body, flags=re.S)
txt  = lambda x: re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', x)).strip()
collapsed, full = len(txt(vis)), len(txt(body))

# 가격·등락 색 일치, 화살표 누락 점검
pairs = re.findall(r'<td class="pr num([^"]*)">[^<]*</td><td class="ch ([a-z ]*)num"', out)
bad   = [p for p in pairs if p[0].strip() != p[1].strip()]
noarr = len(re.findall(r'<td class="ch (?:up|down) num">(?![^<]*[▲▼])', out))

io.open(out_p, 'w', encoding='utf-8', newline='').write(out)

print('OK   %s (%d bytes)' % (out_p, len(out.encode('utf-8'))))
print('접힘 %d자 / 전체 %d자  %s' % (
    collapsed, full, 'OK' if collapsed <= 4000 else '*** 4,000자 초과 — 접기로 옮길 것'))
if extra: print('경고 쓰이지 않은 키:', extra)
if bad:   print('*** 가격/등락 색 불일치 %d행' % len(bad))
if noarr: print('*** 화살표 빠진 등락 칸 %d개' % noarr)
