#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""render.py — 지식인 조간 v4 렌더러

fill.json(v2: 값과 문장만) + template-v4.html + state.json(직전 회차) + calibration.json
  -> out/index.html, out/state.json(이번 회차), out/calibration.json(복사)
입력 파일은 고치지 않으므로 몇 번을 다시 돌려도 안전하다.

회차(LLM)는 HTML 을 쓰지 않는다. 태그·화살표·색·등락률·시사 갭·채점 표시·차트는 전부 여기서 만든다.

사용법
  python3 render.py            렌더 + 검증 + out/ 에 결과물 3개
  python3 render.py --check    렌더·검증만 (out/ 을 쓰지 않음)
  python3 render.py --today    오늘(KST)이 거래일이면 OPEN, 아니면 HOLIDAY <사유> 를 출력

종료 코드 0 = OK (경고가 있어도 0). 1 = FAIL (플레이스홀더 누락·타입 오류·구간 역전 등)
"""
import io, json, re, sys, os, math
from datetime import datetime, timedelta, timezone, date

KST = timezone(timedelta(hours=9))
HERE = os.path.dirname(os.path.abspath(__file__)) or '.'
TEMPLATE = os.path.join(HERE, 'template-v4.html')
CONTEXT = os.path.join(HERE, 'CONTEXT.md')
HOLIDAYS = os.path.join(HERE, 'holidays.json')
FIRST_ISSUE = date(2026, 8, 21)   # 제1호

# 표기명·코드. CONTEXT.md 의 "표기용 종목명" 표가 있으면 그 표기가 우선한다.
NAMES = {
    'K200N':  ('K200 야간선물', '야간 · 05:00'),
    'SOX':    ('SOX', 'PHLX'),
    'NVDA':   ('엔비디아', 'NVDA'),
    'MU':     ('마이크론', 'MU'),
    'EWY':    ('MSCI 한국 ETF', 'EWY'),
    'SKHY':   ('SK하이닉스 ADR', 'SKHY'),
    'K200F':  ('코스피200 선물', 'K200F · 주간'),
    'USDKRW': ('원달러', 'USD/KRW'),
    '005930': ('삼성전자', '005930'),
    '000660': ('SK하이닉스', '000660'),
    '402340': ('SK스퀘어', '402340'),
    '009150': ('삼성전기', '009150'),
    '0167A0': ('SOL AI반도체TOP2', '0167A0'),
    '442580': ('PLUS 글로벌HBM', '442580'),
    'KOSPI':  ('KOSPI', 'KRX'),
    'KOSDAQ': ('KOSDAQ', 'KRX'),
}
GLOBAL_ORDER = ['K200N', 'SOX', 'NVDA', 'MU', 'EWY', 'SKHY', 'K200F', 'USDKRW']
DOMESTIC_ORDER = ['005930', '000660', '402340', '009150', '0167A0', '442580']
KPI_ORDER = ['KOSPI', 'SOX', '005930', '000660']
STATE_KEYS = ['KOSPI', 'KOSDAQ', 'SOX', 'NVDA', 'MU', 'EWY', 'SKHY', 'K200F', 'USDKRW',
              '005930', '000660', '402340', '009150', '0167A0', '442580']
DECIMALS = {k: 0 for k in DOMESTIC_ORDER}
DECIMALS.update({'USDKRW': 2})

# 글자 상한 (접힘 상태에서 보이는 부분). 넘으면 경고만 한다.
LIMITS = {'tldr.h': 35, 'tldr.b': 45, 'sums': 50, 'cm': 45, 'flow.note': 60, 'bull.t': 25, 'bull.d': 45,
          'ladder.d': 40, 'scen.h': 35, 'scen.b': 90, 'scen.cond': 90, 'why': 150, 'points.t': 25,
          'points.d': 60, 'checks.lead': 90, 'score.lead': 110, 'score.more': 150}

FAILS, WARNS = [], []
def fail(msg): FAILS.append(msg)
def warn(msg): WARNS.append(msg)

# ---------- 유틸 ----------
def esc(s):
    return (str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            if s is not None else '')

def esc_keep(s):
    """문장 안의 &amp; 같은 기존 엔티티는 살리고, 위험한 < > 만 막는다."""
    if s is None: return ''
    s = str(s)
    s = re.sub(r'&(?!(amp|lt|gt|quot|#\d+);)', '&amp;', s)
    return s.replace('<', '&lt;').replace('>', '&gt;')

def num(v, dec=2):
    if v is None: return '—'
    if dec == 0: return '{:,.0f}'.format(v)
    return '{:,.{d}f}'.format(v, d=dec)

def pct_str(p):
    if p is None: return '미확보'
    if abs(p) < 0.005: return '0.00%'
    return ('▲ +' if p > 0 else '▼ −') + '{:.2f}%'.format(abs(p))

def cls(p):
    if p is None: return 'na'
    if abs(p) < 0.005: return ''
    return 'up' if p > 0 else 'down'

def plist(items):
    return ''.join('<p>%s</p>' % esc_keep(x) for x in (items or []) if x)

def details(summary, items):
    if not items: return ''
    return '<details><summary>%s</summary><div class="dbody">%s</div></details>' % (esc(summary), plist(items))

def clen(s):
    return len(re.sub(r'\s+', ' ', str(s or '')).strip())

def check_len(label, s, limit):
    n = clen(s)
    if n > limit * 1.3:
        warn('%s %d자 (상한 %d)' % (label, n, limit))

def as_num(v, label):
    if v is None: return None
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        try:
            return float(str(v).replace(',', ''))
        except Exception:
            fail('%s 는 숫자여야 함: %r' % (label, v)); return None
    return float(v)

def kst_today():
    return datetime.now(KST).date()

def weekday_ordinal(d):
    """2026-08-21 을 제1호로 둔 평일 일련번호. 휴장일도 번호를 차지한다(건너뛴 날은 빈다)."""
    n, cur = 0, FIRST_ISSUE
    while cur <= d:
        if cur.weekday() < 5: n += 1
        cur += timedelta(days=1)
    return n

def holiday_of(d):
    try:
        h = json.load(io.open(HOLIDAYS, encoding='utf-8'))
    except Exception:
        h = {}
    if d.weekday() >= 5: return '주말'
    return h.get(d.isoformat())

def context_section(title_prefix):
    """CONTEXT.md 에서 '## <title_prefix>…' 절의 본문만 돌려준다 (다음 ## 전까지)."""
    try:
        txt = io.open(CONTEXT, encoding='utf-8').read()
    except Exception:
        return ''
    m = re.search(r'^##\s*' + re.escape(title_prefix) + r'[^\n]*\n(.*?)(?=^##\s|\Z)', txt, re.M | re.S)
    return m.group(1) if m else ''

def load_context_names():
    """CONTEXT.md '표기용 종목명' 절의 '| 정식 | 표기 | 코드 |' 표에서 코드→표기 를 읽는다."""
    out = {}
    sec = context_section('표기용 종목명')
    for m in re.finditer(r'^\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([A-Z0-9/]+)\s*\|\s*$', sec, re.M):
        formal, short, code = m.groups()
        if formal in ('정식', '---') or short.startswith('-'): continue
        out[code] = short
    return out

def load_banned():
    """CONTEXT.md '금지 표현' 절의 표 첫 열('쓰지 말 것')을 금지 표현 목록으로 읽는다."""
    pats = []
    sec = context_section('금지 표현')
    for m in re.finditer(r'^\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*$', sec, re.M):
        left = m.group(1)
        if left in ('쓰지 말 것', '---') or left.startswith('-'): continue
        for piece in left.split('/'):
            piece = re.sub(r'\s*\(.*?\)\s*', '', piece.strip())
            piece = piece.replace('~', '').strip()
            if len(piece) >= 2:
                pats.append(piece)
    return pats

# ---------- 본체 ----------
def main():
    if '--today' in sys.argv:
        d = kst_today()
        h = holiday_of(d)
        print(('HOLIDAY %s' % h) if h else 'OPEN', d.isoformat())
        return 0

    check_only = '--check' in sys.argv
    tpl = io.open(TEMPLATE, encoding='utf-8').read()
    fill = json.load(io.open('fill.json', encoding='utf-8'))
    try:
        prev = json.load(io.open('state.json', encoding='utf-8'))
    except Exception:
        prev = {}
        warn('state.json 없음 — 등락률은 fill.json 의 pct_screen 을 쓴다')
    try:
        cal = json.load(io.open('calibration.json', encoding='utf-8'))
    except Exception:
        cal = {'records': []}
        warn('calibration.json 없음 — 채점 섹션을 비운다')

    names = dict(NAMES)
    for code, short in load_context_names().items():
        if code in names: names[code] = (short, names[code][1])

    issue_date = str(fill.get('issue_date') or kst_today().isoformat())
    try:
        d = date.fromisoformat(issue_date)
    except Exception:
        fail('issue_date 형식 오류: %r' % issue_date); d = kst_today()
    if d != kst_today():
        warn('issue_date %s 가 오늘(KST %s)과 다름 — publish 스크립트가 막는다' % (issue_date, kst_today()))
    DOW = '월화수목금토일'
    V = {}
    V['GENERATED'] = '%sT07:45+09:00' % issue_date
    V['ISSUE'] = str(weekday_ordinal(d))
    V['DATE_LABEL'] = '%d년 %d월 %d일 (%s)' % (d.year, d.month, d.day, DOW[d.weekday()])
    V['SUBTITLE'] = '07:45 KST · 전일 종가 &amp; 간밤 미국장 반영'

    # ----- 시세 -----
    prices = fill.get('prices') or {}
    prev_closes = (prev.get('closes') or {})
    pct = {}      # 계산 등락률
    close = {}
    for k in STATE_KEYS + ['K200N']:
        p = prices.get(k) or {}
        c = as_num(p.get('close'), 'prices.%s.close' % k)
        close[k] = c
        scr = as_num(p.get('pct_screen'), 'prices.%s.pct_screen' % k)
        base = as_num(prev_closes.get(k), 'state.closes.%s' % k) if k != 'K200N' else None
        if k == 'K200N':
            pct[k] = scr   # 야간선물은 페이지가 주는 값(주간 종가 대비)을 그대로 쓴다
            continue
        if c is not None and base:
            calc = (c / base - 1) * 100
            pct[k] = calc
            if scr is not None and abs(calc - scr) >= 0.05:
                warn('%s 등락률 계산값 %+.2f%% 와 화면값 %+.2f%% 가 0.05%%p 이상 다름 — 재확인하고 data_note 에 남길 것' % (k, calc, scr))
            if abs(calc) > 15:
                warn('%s 등락률 %+.1f%% — 액면분할·병합 또는 기준값 오류 의심' % (k, calc))
        elif c is not None and scr is not None:
            pct[k] = scr
            if base is None: warn('%s 기준값이 state.json 에 없어 화면 등락률을 씀' % k)
        else:
            pct[k] = None
    for k in ('KOSPI', 'SOX', '005930', '000660'):
        if close.get(k) is None: warn('KPI 값 없음: %s' % k)

    def row(k):
        nm, cd = names[k]
        p = prices.get(k) or {}
        c, q = close.get(k), pct.get(k)
        cm = p.get('cm') or ''
        if not cm: warn('%s 해설(cm) 없음' % k)
        check_len('%s.cm' % k, cm, LIMITS['cm'])
        if k == 'K200N' and p.get('asof'):
            cd = '야간 · %s' % esc(p.get('asof'))
        if c is None:
            pr = '<td class="pr num">—</td><td class="ch na">미확보</td>'
        else:
            cc = cls(q)
            pr = '<td class="pr num%s">%s</td><td class="ch %snum">%s</td>' % (
                (' ' + cc) if cc else '', num(c, DECIMALS.get(k, 2)), (cc + ' ') if cc else '', pct_str(q))
        return ('<tbody class="st"><tr><td class="nm">%s<span class="cd">%s</span></td>%s</tr>'
                '<tr><td class="cm" colspan="3">%s%s</td></tr></tbody>' % (
                    esc(nm), esc_keep(cd), pr, esc_keep(cm), details('근거', p.get('more'))))

    V['GLOBAL_ROWS'] = ''.join(row(k) for k in GLOBAL_ORDER)
    V['DOMESTIC_ROWS'] = ''.join(row(k) for k in DOMESTIC_ORDER)

    def kpi(k):
        nm = names[k][0]
        c, q = close.get(k), pct.get(k)
        cc = cls(q) if c is not None else 'na'
        v = num(c, DECIMALS.get(k, 2)) if c is not None else '—'
        return '<div class="k"><div class="n">%s</div><div class="v num %s">%s</div><div class="c %s num">%s</div></div>' % (
            esc(nm), cc, v, cc, pct_str(q) if c is not None else '미확보')
    V['KPI'] = ''.join(kpi(k) for k in KPI_ORDER)

    tags = fill.get('tags') or {}
    V['GLOBAL_TAG'] = esc_keep(tags.get('global') or '')
    V['DOMESTIC_TAG'] = esc_keep(tags.get('domestic') or '')
    if not tags.get('global') or not tags.get('domestic'): warn('tags.global / tags.domestic 비어 있음')

    # ----- 시사 갭 (스크립트 계산) -----
    def implied(fx_key, us_key, kr_key):
        a, b, c = pct.get(us_key), pct.get(fx_key), pct.get(kr_key)
        if a is None or b is None or c is None: return None
        return ((1 + a / 100) * (1 + b / 100) / (1 + c / 100) - 1) * 100
    sig_in = fill.get('signals') or {}
    signals = {
        'k200n_pct': pct.get('K200N'),
        'k200n_close': close.get('K200N'),
        'k200n_asof': (prices.get('K200N') or {}).get('asof'),
        'k200f_close': close.get('K200F'),
        'ewy_implied_pct': implied('USDKRW', 'EWY', 'KOSPI'),
        'adr_implied_pct': implied('USDKRW', 'SKHY', '000660'),
        'news_flag': sig_in.get('news_flag'),
    }
    for k in ('ewy_implied_pct', 'adr_implied_pct'):
        if signals[k] is not None: signals[k] = round(signals[k], 2)
    if signals['k200n_pct'] is None: warn('야간선물(K200N) 미확보 — 자동 발행 게이트에 걸린다')
    if signals['k200n_pct'] is not None and close.get('K200N') and close.get('K200F'):
        calc = (close['K200N'] / close['K200F'] - 1) * 100
        if abs(calc - signals['k200n_pct']) >= 0.05:
            warn('야간선물 등락률 페이지값 %+.2f%% 와 (야간종가/주간종가) 계산값 %+.2f%% 가 다름' % (signals['k200n_pct'], calc))
    def chip(label, p, note=''):
        if p is None: return '<span class="na">%s 미확보</span>' % label
        return '<span class="%s">%s %s%s</span>' % (cls(p) or '', label, pct_str(p), ('<small>%s</small>' % esc(note)) if note else '')
    V['SIGNAL_STRIP'] = (chip('야간선물', signals['k200n_pct'], signals['k200n_asof'] or '') +
                         chip('EWY 시사', signals['ewy_implied_pct']) +
                         chip('ADR 시사', signals['adr_implied_pct']))

    # ----- 전망 -----
    fc = fill.get('forecast') or {}
    fdir = str(fc.get('dir') or '').strip()
    low, high = as_num(fc.get('low'), 'forecast.low'), as_num(fc.get('high'), 'forecast.high')
    kospi_close = close.get('KOSPI')
    if fdir not in ('갭상승', '보합', '갭하락'): fail('forecast.dir 는 갭상승|보합|갭하락 중 하나: %r' % fdir)
    if low is None or high is None: fail('forecast.low/high 없음')
    elif low >= high: fail('forecast.low >= high')
    elif kospi_close:
        lo_p, hi_p = (low / kospi_close - 1) * 100, (high / kospi_close - 1) * 100
        if low > kospi_close and fdir != '갭상승': warn('구간 전체가 전일 종가 위인데 방향이 %s' % fdir)
        if high < kospi_close and fdir != '갭하락': warn('구간 전체가 전일 종가 아래인데 방향이 %s' % fdir)
        if hi_p - lo_p < 1.0: warn('구간 폭 %.2f%%p — 최근 |갭| 중앙값(1.3%%) 보다 좁다' % (hi_p - lo_p))
    else:
        lo_p = hi_p = None
        warn('코스피 종가가 없어 구간 % 를 계산하지 못함')
    V['OPEN_FORECAST'] = esc(fdir) + ' 출발' if fdir else '전망 없음'
    if low is not None and high is not None:
        rng = '코스피 %s ~ %s' % (num(low, 0), num(high, 0))
        if lo_p is not None:
            rng += '<br>(%s%.2f%% ~ %s%.2f%%)' % ('+' if lo_p >= 0 else '−', abs(lo_p), '+' if hi_p >= 0 else '−', abs(hi_p))
        V['OPEN_RANGE'] = rng
    else:
        V['OPEN_RANGE'] = '구간 없음'

    # 구간 막대 SVG: -R ~ +R (%), 전일 종가 = 0
    if lo_p is not None:
        R = max(4.0, math.ceil(max(abs(lo_p), abs(hi_p)) + 0.5))
        W, H, L = 360, 46, 22
        x = lambda p: L + (p + R) / (2 * R) * (W - 2 * L)
        ticks = ''.join('<text x="%.1f" y="41" font-size="10" text-anchor="middle" style="fill:var(--tx3)">%+d%%</text>' % (x(t), t)
                        for t in range(-int(R), int(R) + 1, 2) if t != 0)
        sig_marks = ''
        for key, lab in (('k200n_pct', '야간'), ('ewy_implied_pct', 'EWY')):
            p = signals.get(key)
            if p is not None and abs(p) <= R:
                sig_marks += ('<line x1="%.1f" x2="%.1f" y1="8" y2="26" style="stroke:var(--tx3)" stroke-width="1.5" stroke-dasharray="2 2"/>'
                              '<text x="%.1f" y="7" font-size="9" text-anchor="middle" style="fill:var(--tx3)">%s</text>') % (x(p), x(p), x(p), lab)
        V['BAND_BAR'] = ('<svg viewBox="0 0 %d %d" role="img" aria-label="예상 구간 %s ~ %s, 전일 종가 %s">'
                         '<line x1="%d" x2="%d" y1="26" y2="26" style="stroke:var(--line2)" stroke-width="2"/>'
                         '<rect x="%.1f" y="12" width="%.1f" height="16" rx="4" style="fill:var(--warnstrong);opacity:.55"/>'
                         '<line x1="%.1f" x2="%.1f" y1="4" y2="34" style="stroke:var(--tx)" stroke-width="2"/>'
                         '<text x="%.1f" y="41" font-size="10" text-anchor="middle" style="fill:var(--tx2)" font-weight="700">전일 종가</text>'
                         '%s%s</svg>') % (W, H, num(low, 0), num(high, 0), num(kospi_close, 2), L, W - L,
                                          x(lo_p), max(2.0, x(hi_p) - x(lo_p)), x(0), x(0), x(0), ticks, sig_marks)
    else:
        V['BAND_BAR'] = ''

    # ----- 채점 (calibration.json 은 score.py 가 이미 갱신) -----
    recs = cal.get('records') or []
    scored = [r for r in recs if r.get('in_range') is not None]
    prev_fc = (prev.get('forecast') or {})
    last = recs[-1] if recs else None
    today_scored = bool(last and prev_fc.get('date') and last.get('date') == prev_fc.get('date'))

    def md(iso):
        try:
            dd = date.fromisoformat(iso); return '%d/%d' % (dd.month, dd.day)
        except Exception:
            return iso
    strip = ['<div class="s wait">오늘</div>']
    for r in reversed(recs[-9:]):
        strip.append('<div class="s %s">%s</div>' % ('hit' if r.get('verdict') == 'hit' else 'miss', md(r.get('date', ''))))
    while len(strip) < 10: strip.append('<div class="s">—</div>')
    V['SCORE_STRIP'] = ''.join(strip)

    sc = fill.get('score') or {}
    if today_scored:
        V['VERDICT_CLASS'] = 'hit' if last.get('verdict') == 'hit' else 'miss'
        V['VERDICT'] = '%s 회차 — %s' % (md(last['date']), '적중' if last.get('verdict') == 'hit' else '빗나감')
        lead = sc.get('lead') or ''
        if last.get('actual_open') is not None and num(last['actual_open'], 2).replace(',', '') not in str(lead).replace(',', ''):
            warn('score.lead 에 실제 시초가 %s 가 없음' % num(last['actual_open'], 2))
    else:
        V['VERDICT_CLASS'] = ''
        V['VERDICT'] = '직전 회차 — 채점 불가' if prev_fc else '채점 기록 없음'
        lead = sc.get('lead') or '직전 회차를 채점할 시초가를 확보하지 못했습니다.'
    check_len('score.lead', lead, LIMITS['score.lead'])
    V['SCORE_LEAD'] = esc_keep(lead)
    V['SCORE_MORE'] = plist(sc.get('more'))
    for x in (sc.get('more') or []): check_len('score.more', x, LIMITS['score.more'])

    if scored:
        cov = sum(1 for r in scored if r['in_range']) / len(scored)
        dirh = sum(1 for r in recs if r.get('dir_hit')) / len(recs)
        bws = [r['band_width_pct'] for r in recs if r.get('band_width_pct') is not None]
        V['COVERAGE'] = '누적 %d회차 — 구간 커버리지 %.1f%% (%d/%d) · 방향 적중 %.1f%% · 평균 구간폭 %.2f%%p' % (
            len(recs), cov * 100, sum(1 for r in scored if r['in_range']), len(scored), dirh * 100,
            (sum(bws) / len(bws)) if bws else 0)
        last10 = scored[-10:]
        errs = []
        for r in last10:
            if r.get('low') is not None and r.get('prev_close'):
                c = ((r['low'] + r['high']) / 2 / r['prev_close'] - 1) * 100
                errs.append(abs(r['gap_pct'] - c))
        errs.sort()
        med = errs[len(errs) // 2] if errs else None
        V['CONF_LINE'] = '최근 %d회 — 구간 안 %d · 방향 %d · 중심 오차 중앙 %s' % (
            len(last10), sum(1 for r in last10 if r['in_range']), sum(1 for r in last10 if r.get('dir_hit')),
            ('%.2f%%p' % med) if med is not None else '—')
    else:
        V['COVERAGE'] = '누적 기록 없음'
        V['CONF_LINE'] = '채점 기록이 쌓이면 여기에 최근 적중률이 붙습니다'

    # 채점 차트 SVG (최근 16회)
    rows = [r for r in recs if r.get('low') is not None and r.get('prev_close')][-16:]
    if rows:
        W, H, L, T, B = 360, 150, 22, 10, 22
        R = 4.0
        for r in rows:
            for v in ((r['low'] / r['prev_close'] - 1) * 100, (r['high'] / r['prev_close'] - 1) * 100, r.get('gap_pct') or 0):
                R = max(R, math.ceil(abs(v) + 0.3))
        y = lambda p: T + (R - p) / (2 * R) * (H - T - B)
        n = len(rows); step = (W - L - 8) / n
        parts = ['<svg viewBox="0 0 %d %d" role="img" aria-label="최근 %d회차 예상 구간과 실제 시초가">' % (W, H, n)]
        for t in range(-int(R), int(R) + 1, 2):
            parts.append('<line x1="%d" x2="%d" y1="%.1f" y2="%.1f" style="stroke:var(--line)" stroke-width="%s"/>' % (L, W - 4, y(t), y(t), '1.5' if t == 0 else '1'))
            parts.append('<text x="%d" y="%.1f" font-size="9" text-anchor="end" style="fill:var(--tx3)">%+d</text>' % (L - 4, y(t) + 3, t))
        for i, r in enumerate(rows):
            cx = L + step * (i + 0.5)
            lo = (r['low'] / r['prev_close'] - 1) * 100; hi = (r['high'] / r['prev_close'] - 1) * 100
            parts.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="2" style="fill:var(--line2)"/>' % (cx - 4, y(hi), 8, max(2.0, y(lo) - y(hi))))
            g = r.get('gap_pct')
            if g is not None:
                if r.get('in_range'):
                    parts.append('<circle cx="%.1f" cy="%.1f" r="3.6" style="fill:var(--ok)"/>' % (cx, y(g)))
                else:
                    parts.append('<circle cx="%.1f" cy="%.1f" r="3.2" style="fill:var(--panel);stroke:var(--tx2)" stroke-width="1.8"/>' % (cx, y(g)))
            if n <= 10 or i % 2 == (n - 1) % 2:
                parts.append('<text x="%.1f" y="%d" font-size="8" text-anchor="middle" style="fill:var(--tx3)">%s</text>' % (cx, H - 7, md(r.get('date', ''))))
        parts.append('</svg>')
        V['SCORE_CHART'] = ''.join(parts)
    else:
        V['SCORE_CHART'] = ''

    # ----- 본문 블록 -----
    tl = fill.get('tldr') or []
    if len(tl) != 3: fail('tldr 는 정확히 3개 (지금 %d개)' % len(tl))
    out = []
    for i, t in enumerate(tl, 1):
        check_len('tldr[%d].h' % i, t.get('h'), LIMITS['tldr.h']); check_len('tldr[%d].b' % i, t.get('b'), LIMITS['tldr.b'])
        out.append('<div class="tl"><div class="tn">%d</div><div><div class="th">%s</div><div class="tb">%s</div>%s</div></div>' % (
            i, esc_keep(t.get('h')), esc_keep(t.get('b')), details('더 보기', t.get('more'))))
    V['TLDR'] = ''.join(out)

    sums = fill.get('sums') or {}
    for k, key in (('global', 'GLOBAL_SUM'), ('domestic', 'DOMESTIC_SUM'), ('issue', 'ISSUE_SUM'), ('scen', 'SCEN_SUM')):
        if not sums.get(k): warn('sums.%s 비어 있음' % k)
        check_len('sums.%s' % k, sums.get(k), LIMITS['sums'])
        V[key] = esc_keep(sums.get(k) or '')

    flow = fill.get('flow') or {}
    def eok(v):
        if v is None: return '<span class="fv na">미확보</span>'
        v = float(v); a = abs(v)
        s = ('%d조%s억' % (int(a // 10000), '{:,.0f}'.format(a % 10000))) if a >= 10000 else '{:,.0f}억'.format(a)
        if a >= 10000 and a % 10000 == 0: s = '%d조' % int(a // 10000)
        c = 'up' if v > 0 else ('down' if v < 0 else '')
        arrow = '▲ +' if v > 0 else ('▼ −' if v < 0 else '')
        return '<span class="fv %s num">%s%s</span>' % (c, arrow, s)
    V['FLOW_GRID'] = ''.join('<div><span class="fk">%s</span>%s</div>' % (lab, eok(as_num(flow.get(k), 'flow.%s' % k)))
                             for k, lab in (('foreign', '외국인'), ('inst', '기관'), ('retail', '개인'), ('other', '기타법인')))
    check_len('flow.note', flow.get('note'), LIMITS['flow.note'])
    V['FLOW_NOTE'] = esc_keep(flow.get('note') or '') + details('짚을 것', flow.get('more'))
    if flow.get('foreign') is None: warn('외국인 순매수 미확보')

    bull, bear = fill.get('bull') or [], fill.get('bear') or []
    if len(bull) != len(bear): fail('bull %d개 / bear %d개 — 개수가 같아야 함' % (len(bull), len(bear)))
    if not bull: fail('bull/bear 비어 있음')
    def li(items, tag):
        o = []
        for i, it in enumerate(items, 1):
            check_len('%s[%d].t' % (tag, i), it.get('t'), LIMITS['bull.t']); check_len('%s[%d].d' % (tag, i), it.get('d'), LIMITS['bull.d'])
            o.append('<li><b>%s</b><span>%s</span></li>' % (esc_keep(it.get('t')), esc_keep(it.get('d'))))
        return ''.join(o)
    V['BULL_ITEMS'], V['BEAR_ITEMS'] = li(bull, 'bull'), li(bear, 'bear')
    V['N_BULL'], V['N_BEAR'] = str(len(bull)), str(len(bear))

    lad = fill.get('ladder') or []
    kinds = [x.get('kind') for x in lad]
    if kinds != ['res', 'now', 'sup', 'sup2']: fail('ladder 는 kind 순서 res, now, sup, sup2 4개: %r' % kinds)
    PRE = {'res': '1차 저항 — ', 'now': '', 'sup': '1차 지지 — ', 'sup2': '2차 지지 — '}
    o = []
    for x in lad:
        lv = as_num(x.get('level'), 'ladder.level')
        check_len('ladder.%s.d' % x.get('kind'), x.get('d'), LIMITS['ladder.d'])
        o.append('<div class="lv %s"><span class="lvl num">%s</span><span class="lvd">%s%s</span></div>' % (
            esc(x.get('kind')), num(lv, 2) if lv is not None else '—', PRE.get(x.get('kind'), ''), esc_keep(x.get('d'))))
    V['LADDER'] = ''.join(o)
    if lad and kospi_close and as_num(lad[1].get('level'), 'ladder.now') not in (None, kospi_close) and abs(as_num(lad[1].get('level'), '') - kospi_close) > 0.01:
        warn('ladder now 값 %s 가 코스피 종가 %s 와 다름' % (lad[1].get('level'), kospi_close))

    scn = fill.get('scenarios') or {}
    base, alt = scn.get('base') or {}, scn.get('alt') or {}
    if not base or not alt: fail('scenarios.base / alt 필요')
    for tag, s in (('base', base), ('alt', alt)):
        check_len('scenarios.%s.h' % tag, s.get('h'), LIMITS['scen.h']); check_len('scenarios.%s.b' % tag, s.get('b'), LIMITS['scen.b']); check_len('scenarios.%s.cond' % tag, s.get('cond'), LIMITS['scen.cond'])
        if not re.search(r'\d', str(s.get('cond') or '')): warn('scenarios.%s.cond 에 숫자 조건이 없음' % tag)
    V['SCENARIOS'] = ('<div class="sc base"><div class="st">기본 시나리오 · 확률 우위</div><div class="sch">%s</div><div class="scb">%s</div><div class="sif">유지 조건 — %s</div></div>'
                      '<div class="sc alt"><div class="st">대안 시나리오 · 깨질 때</div><div class="sch">%s</div><div class="scb">%s</div><div class="sif">전환 신호 — %s</div></div>') % (
        esc_keep(base.get('h')), esc_keep(base.get('b')), esc_keep(base.get('cond')), esc_keep(alt.get('h')), esc_keep(alt.get('b')), esc_keep(alt.get('cond')))

    why = fill.get('why') or []
    if len(why) != 4: warn('why 는 4개 문단 (아래로 미는 힘 / 위로 받치는 힘 / 왜 이 방향 / 구간 폭 근거), 지금 %d개' % len(why))
    for i, w in enumerate(why, 1): check_len('why[%d]' % i, w, LIMITS['why'])
    V['FCAST_WHY'] = plist(why)

    pts = fill.get('points') or []
    if len(pts) != 3: fail('points 는 3개 (지금 %d개)' % len(pts))
    o = []
    for i, p in enumerate(pts, 1):
        check_len('points[%d].t' % i, p.get('t'), LIMITS['points.t']); check_len('points[%d].d' % i, p.get('d'), LIMITS['points.d'])
        o.append('<div class="pt"><div class="pn">%d</div><div><b>%s</b><span>%s</span></div></div>' % (i, esc_keep(p.get('t')), esc_keep(p.get('d'))))
    V['POINTS'] = ''.join(o)

    chks = fill.get('checks') or {}
    for k, key in (('global', 'GLOBAL_CHK'), ('domestic', 'DOMESTIC_CHK'), ('issue', 'ISSUE_CHK'), ('scenario', 'SCENARIO_CHK')):
        c = chks.get(k) or {}
        if not c.get('lead'): fail('checks.%s.lead 없음 — 상승장이어도 4개 모두 채운다' % k)
        check_len('checks.%s.lead' % k, c.get('lead'), LIMITS['checks.lead'])
        V[key] = '<div class="cl">%s</div>%s' % (esc_keep(c.get('lead')), details('근거', c.get('more')))

    # 지난 회차 링크 — 채점 기록의 날짜(=발행일) 최근 3개. publish 스크립트가 실제 파일 기준으로 다시 쓴다.
    past = [r['date'] for r in recs if r.get('date') and r['date'] < issue_date]
    if prev.get('issue_date') and prev['issue_date'] < issue_date and prev['issue_date'] not in past: past.append(prev['issue_date'])
    past = sorted(set(past))[-3:][::-1]
    DOWS = '월화수목금토일'
    links = []
    for iso in past:
        try:
            dd = date.fromisoformat(iso); links.append('<a href="./archive/%s.html">%d/%d (%s)</a>' % (iso, dd.month, dd.day, DOWS[dd.weekday()]))
        except Exception:
            pass
    links.append('<a href="./archive/">전체 보기</a>')
    V['ARCHIVE_LINKS'] = ' '.join(links)

    src = fill.get('sources') or ''
    if not str(src).startswith('출처'): warn('sources 는 "출처 — " 로 시작')
    V['SOURCES'] = esc_keep(src)
    dn = fill.get('data_note') or {}
    if not dn.get('lead'): fail('data_note.lead 없음 — 대조 결과를 반드시 쓴다')
    V['DATA_NOTE'] = esc_keep(dn.get('lead') or '') + details('대조 내역', dn.get('more'))

    # ----- 치환 -----
    need = set(re.findall(r'\{\{([A-Z_]+)\}\}', tpl))
    missing = sorted(need - set(V))
    if missing: fail('템플릿 자리를 채우지 못함: %s' % missing)
    out = tpl
    for k, v in V.items(): out = out.replace('{{%s}}' % k, v if v is not None else '')
    left = sorted(set(re.findall(r'\{\{([A-Z_]+)\}\}', out)))
    if left: fail('치환 뒤 남은 자리: %s' % left)

    # ----- 사후 검증 -----
    body = re.sub(r'<(style|script).*?</\1>', '', out, flags=re.S)
    body = re.sub(r'<svg.*?</svg>', '', body, flags=re.S)
    body = re.sub(r'<div class="fwide (?:fsig num|fconf)">.*?</div>|<div class="sl">.*?</div>|<div class="legend">.*?</div>', '', body, flags=re.S)  # 스크립트가 만든 문구는 글자수에서 뺀다
    vis = re.sub(r'<details.*?</details>', '', body, flags=re.S)
    txt = lambda x: re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', x)).strip()
    collapsed, full = len(txt(vis)), len(txt(body))
    if collapsed > 4000: warn('접힘 본문 %d자 — 4,000자 초과. 긴 내용은 more 로 옮길 것' % collapsed)
    plain = txt(body)
    banned = load_banned() or ['되돌렸', '되돌림', '끌어내렸', '판가', '매겼습니다', '덧붙인', '가리킵니다', '예탁증서',
                               '것입니다', '로 보입니다', '에 대한', '를 통해', '로 인해', '에 있어서', '와 관련하여']
    for pat in banned:
        n = plain.count(pat)
        if n: warn('금지 표현 "%s" %d회' % (pat, n))
    for pat, lim in (('한 셈입니다', 2), ('반영했습니다', 3)):
        n = plain.count(pat)
        if n > lim: warn('"%s" %d회 (상한 %d)' % (pat, n, lim))

    if FAILS:
        for f in FAILS: print('FAIL', f)
        return 1
    if not check_only:
        os.makedirs('out', exist_ok=True)
        io.open(os.path.join('out', 'index.html'), 'w', encoding='utf-8', newline='').write(out)
        try:
            io.open(os.path.join('out', 'calibration.json'), 'w', encoding='utf-8', newline='\n').write(io.open('calibration.json', encoding='utf-8').read())
        except Exception:
            pass
    print('OK   out/index.html (%d bytes)' % len(out.encode('utf-8')))
    print('접힘 %d자 / 전체 %d자  %s' % (collapsed, full, 'OK' if collapsed <= 4000 else '*** 4,000자 초과'))
    print('전망 %s %s~%s (%s) · 야간선물 %s · EWY시사 %s · ADR시사 %s' % (
        fdir, num(low, 0) if low else '—', num(high, 0) if high else '—', V['OPEN_RANGE'].split('<br>')[-1].strip('()'),
        pct_str(signals['k200n_pct']), pct_str(signals['ewy_implied_pct']), pct_str(signals['adr_implied_pct'])))
    print(V['COVERAGE'])

    # ----- state.json (이번 회차) -----
    if not check_only:
        closes = {'as_of': fill.get('closes_as_of') or (tags.get('domestic') or '').split(' ')[0],
                  'note': '다음 회차의 등락률 계산 기준이 되는 직전 영업일 종가'}
        for k in STATE_KEYS: closes[k] = close.get(k)
        state = {'schema': 2,
                 'note': '회차 간 인수인계 파일. render.py 가 매 회차 통째로 갱신한다. 아카이브 HTML 을 파싱하지 않기 위해 존재한다.',
                 'issue_date': issue_date,
                 'forecast': {'date': issue_date, 'dir': fdir, 'low': low, 'high': high, 'prev_close': kospi_close,
                              'note': '다음 회차가 이 전망을 실제 시초가와 대조해 채점한다'},
                 'signals': signals,
                 'closes': closes}
        if not closes['as_of']: warn('closes.as_of 가 비어 있음 — fill.json 에 closes_as_of (YYYY-MM-DD) 를 넣을 것')
        io.open(os.path.join('out', 'state.json'), 'w', encoding='utf-8', newline='\n').write(json.dumps(state, ensure_ascii=False, indent=1) + '\n')
        print('out/state.json — forecast %s, closes as_of %s' % (issue_date, closes['as_of'] or '(비어 있음)'))
    for w in WARNS: print('경고', w)
    print('경고 %d건' % len(WARNS))
    # 자동 발행 게이트 — 마지막 줄. PASS 일 때만 publish.py --push
    hold = []
    if any(w.startswith('금지 표현') or '(상한 ' in w and '회' in w for w in WARNS): hold.append('금지 표현·횟수 초과')
    if any('(상한' in w for w in WARNS): hold.append('글자 초과')
    if any('4,000자 초과' in w for w in WARNS): hold.append('접힘 4,000자 초과')
    if signals['k200n_pct'] is None: hold.append('야간선물 미확보')
    dv = as_num(dn.get('diverged'), 'data_note.diverged')
    if dv is None or dv > 2: hold.append('종가 대조 불일치 %s건' % ('미기재' if dv is None else int(dv)))
    if any(w.startswith('issue_date') for w in WARNS): hold.append('발행일이 오늘이 아님')
    print('GATE PASS' if not hold else 'GATE HOLD — ' + ' · '.join(hold))
    return 0

if __name__ == '__main__':
    sys.exit(main())
