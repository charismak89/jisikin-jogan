#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""template.html + fill.json -> index.html

값이 리스트로 와도 이어붙인다. str() 로 뭉개면 페이지에 ['...'] 가 그대로 찍힌다.
"""
import io, json, re, sys

def flat(v):
    if isinstance(v, (list, tuple)):
        return ''.join(flat(x) for x in v)
    if v is None:
        return ''
    return str(v)

tpl  = io.open('template.html', encoding='utf-8').read()
vals = json.load(io.open('fill.json', encoding='utf-8'))

listed  = sorted(k for k, v in vals.items() if isinstance(v, (list, tuple)))
need    = set(re.findall(r'\{\{([A-Z_]+)\}\}', tpl))
missing = sorted(need - set(vals))
extra   = sorted(set(vals) - need)

out = tpl
for k, v in vals.items():
    out = out.replace('{{%s}}' % k, flat(v))
left = sorted(set(re.findall(r'\{\{([A-Z_]+)\}\}', out)))

if missing or left:
    print('FAIL 채우지 못한 자리:', missing or left); sys.exit(1)

# 리스트 잔해가 본문에 새어 나왔는지
leak = re.findall(r"\['|', '|'\]", out)
if leak:
    print('FAIL 본문에 파이썬 리스트 잔해 %d곳. fill.json 값을 문자열로 고칠 것.' % len(leak))
    sys.exit(1)

body = re.sub(r'<(style|script).*?</\1>', '', out, flags=re.S)
vis  = re.sub(r'<details.*?</details>', '', body, flags=re.S)
txt  = lambda x: re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', x)).strip()
collapsed, full = len(txt(vis)), len(txt(body))
pairs = re.findall(r'<td class="pr num([^"]*)">[^<]*</td><td class="ch ([a-z ]*)num"', out)
bad   = [p for p in pairs if p[0].strip() != p[1].strip()]
noarr = len(re.findall(r'<td class="ch (?:up|down) num">(?![^<]*[▲▼])', out))

io.open('index.html', 'w', encoding='utf-8', newline='').write(out)
print('OK   index.html (%d bytes)' % len(out.encode('utf-8')))
print('접힘 %d자 / 전체 %d자  %s' % (collapsed, full,
      'OK' if collapsed <= 4000 else '*** 4,000자 초과 — 접기로 옮길 것'))
if listed: print('참고 리스트로 들어와 이어붙인 키:', listed)
if extra:  print('경고 쓰이지 않은 키:', extra)
if bad:    print('*** 가격/등락 색 불일치 %d행' % len(bad))
if noarr:  print('*** 화살표 빠진 등락 칸 %d개' % noarr)
