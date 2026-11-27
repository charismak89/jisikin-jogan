#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""render.py — 지식인 조간 v5 렌더러 (2026-10-15 — 첫 화면 대시보드 + 브리핑 탭)

fill.json(v2: 값과 문장만) + template-v5.html + state.json(직전 회차) + calibration.json + perp.json·relay.json(있으면)
  -> out/index.html, out/state.json(이번 회차), out/calibration.json(복사), out/day.json, out/datalog.json
perp.json 은 fetch_perp.py 가 만든다(해외 24시간 추종가). 없어도 렌더한다 — 대시보드 장외 구간만 브라우저가 직접 받는다.
relay.json 은 fetch_relay.py 가 만든다(토스 중계기). fill.json 의 빈 시세·시가·수급을 채우고, 회차 값과 다르면 경고한다(2026-10-21).
입력 파일은 고치지 않으므로 몇 번을 다시 돌려도 안전하다.

회차(LLM)는 HTML 을 쓰지 않는다. 태그·화살표·색·등락률·시사 갭·채점 표시·차트는 전부 여기서 만든다.

사용법
  python3 render.py            렌더 + 검증 + out/ 에 결과물 3개
  python3 render.py --check    렌더·검증만 (out/ 을 쓰지 않음)
  python3 render.py --today    오늘(KST)이 거래일이면 OPEN, 아니면 HOLIDAY <사유> 를 출력

종료 코드 0 = OK (경고가 있어도 0). 1 = FAIL (플레이스홀더 누락·타입 오류·구간 역전 등)
"""
import html, io, json, re, subprocess, sys, os, math
from datetime import datetime, timedelta, timezone, date

KST = timezone(timedelta(hours=9))
HERE = os.path.dirname(os.path.abspath(__file__)) or '.'
TEMPLATE = os.path.join(HERE, 'template-v5.html')   # v4 로 되돌리려면 이 줄만 바꾼다
CONTEXT = os.path.join(HERE, 'CONTEXT.md')
HOLIDAYS = os.path.join(HERE, 'holidays.json')
MARKET_HOURS = os.path.join(HERE, 'market_hours.json')
FIRST_ISSUE = date(2026, 8, 21)   # 제1호

# 표기명·코드. CONTEXT.md 의 "표기용 종목명" 표가 있으면 그 표기가 우선한다.
NAMES = {
    'K200N':  ('K200 야간선물', '야간 · 06:00'),
    'SOX':    ('SOX', 'PHLX'),
    'NVDA':   ('엔비디아', 'NVDA'),
    'MU':     ('마이크론', 'MU'),
    'EWY':    ('MSCI 한국 ETF', 'EWY'),
    'SKHY':   ('SK하이닉스 ADR', 'SKHY'),
    'K200F':  ('코스피200 선물', 'K200F · 주간'),
    'TSM':    ('TSMC', 'TSM'),
    'DRAM':   ('DRAM', '메모리 ETF'),
    'ANT':    ('앤트로픽', 'ANT'),
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
# 간밤 표(해설 cm 이 붙는 줄). 2026-11-27 사용자 결정: 주간선물(K200F)은 야간선물 등락률 기준이라 줄에서 빼고 야간선물 줄에 적는다.
# EWY 는 시사 갭 오차가 야간선물의 두 배가 넘어(47회차 MAE 2.12 vs 0.92) 해설 없는 참고 시세로 내렸다. 두 값 모두 수집은 그대로다
GLOBAL_ORDER = ['K200N', 'SOX', 'NVDA', 'MU', 'SKHY', 'USDKRW']
# 참고 시세(해설 없음). EWY 를 뺀 셋은 중계기 일봉(fetch_relay.py REF)으로만 채운다 — 회차가 받지 않는다
REF_ORDER = ['TSM', 'DRAM', 'ANT', 'EWY']
REF_RELAY = ['TSM', 'DRAM', 'ANT']
# 대시보드 '간밤 시장'(3×3)과 지난 회차 화면 타일
MARKET_ORDER = ['K200N', 'SOX', 'USDKRW', 'NVDA', 'MU', 'TSM', 'DRAM', 'ANT', 'EWY']
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

def night_session_skipped(d):
    """직전 영업일~발행일 사이(양끝 제외)에 holidays.json 휴장일이 있으면 그 목록. 없으면 [].
    휴장 전날 밤에는 야간선물 세션이 없어서 이런 회차는 야간선물을 못 받는 게 정상이다.
    주말만 끼면 [] 다 — 평범한 월요일은 금요일 밤 세션이 있다."""
    cur = d - timedelta(days=1)
    while holiday_of(cur): cur -= timedelta(days=1)
    out, x = [], cur + timedelta(days=1)
    while x < d:
        h = holiday_of(x)
        if h and h != '주말': out.append('%s %s' % (x.isoformat(), h))
        x += timedelta(days=1)
    return out

def prev_business_day(d):
    x = d - timedelta(days=1)
    while holiday_of(x): x -= timedelta(days=1)
    return x

def kst_ms(d, h, m):
    return int(datetime(d.year, d.month, d.day, h, m, tzinfo=KST).timestamp() * 1000)

DEFAULT_SESSION = ('09:00', '15:30')

def session_of(d):
    """그날 KRX 정규장 {'open': (시, 분), 'close': (시, 분), 'open_hm': 'HH:MM', 'close_hm': 'HH:MM', 'why': 사유 또는 None}.
    market_hours.json(sync_market_hours 자동 기록, 사람이 공지로 고침)에 없는 날은 09:00~15:30. 수능일은 10:00~16:30, 새해 첫 거래일은 10:00 개장(2026-11-19)."""
    try:
        r = json.load(io.open(MARKET_HOURS, encoding='utf-8')).get(d.isoformat()) or {}
    except Exception:
        r = {}
    out = {'why': r.get('why')}
    for k, dv in zip(('open', 'close'), DEFAULT_SESSION):
        hm = str(r.get(k) or dv)
        try:
            h, m = (int(x) for x in hm.split(':'))
        except Exception:
            hm = dv; h, m = (int(x) for x in dv.split(':'))
        out[k], out[k + '_hm'] = (h, m), '%02d:%02d' % (h, m)
    out['changed'] = (out['open_hm'], out['close_hm']) != DEFAULT_SESSION
    return out

def next_business_day(d):
    x = d + timedelta(days=1)
    while holiday_of(x): x += timedelta(days=1)
    return x

AUTO_SRC = '토스 장 달력 자동 기록'
_synced = {}

def write_market_hours(data):
    """market_hours.json 을 사람이 읽기 좋게 쓴다. '_' 로 시작하는 키 먼저, 날짜는 한 줄에 하나씩 오름차순."""
    head = [k for k in data if k.startswith('_')]
    days = sorted(k for k in data if not k.startswith('_'))
    lines = ['  %s: %s' % (json.dumps(k, ensure_ascii=False), json.dumps(data[k], ensure_ascii=False)) for k in head + days]
    tmp = MARKET_HOURS + '.tmp'
    with io.open(tmp, 'w', encoding='utf-8', newline='\n') as f: f.write('{\n' + ',\n'.join(lines) + '\n}\n')
    os.replace(tmp, MARKET_HOURS)   # 쓰다 만 파일이 남지 않게

def sync_market_hours(issue=None, cal=None, verbose=False):
    """예외를 밖으로 내지 않는다(07:45 회차를 막지 않게). verbose 면 토스와 일치한 변경일도 한 줄 낸다(render --today 만)."""
    try:
        return _sync_market_hours(issue, cal, verbose)
    except Exception as e:
        return ['장 시간 자동 기록 실패 — %s. market_hours.json 그대로 쓴다' % str(e)[:80]]

def _sync_market_hours(issue, cal, verbose):
    """토스 장 달력(중계기 /v1/calendar)으로 holidays.json(_sync_holidays)과 market_hours.json(_sync_hours)을 자동으로 채운다(2026-11-19 사용자 결정 "자동화").
    실제 오늘(KST) 날짜로 조회한 전일, 당일, 익일만 쓴다 — 토스는 기준일이 오늘보다 뒤면 모레 이후를 오늘 장 시간으로 채운다.
    평소(09:00~15:30)와 다른 날이 파일에 없으면 적고, 자동 기록 줄이 토스와 다르면 고친다. 사람이 적은 줄은 고치지 않고 불일치만 알린다.
    반환: 출력할 줄 목록. 중계기 키가 없거나 실패하면 []. 한 프로세스에서 한 번만 조회한다."""
    d = issue or kst_today()
    if d != kst_today(): return []
    if d in _synced: return []
    if cal is None:
        try:
            from fetch_relay import get
            base, key = os.environ.get('JJ_RELAY_URL', '').strip(), os.environ.get('JJ_RELAY_TOKEN', '').strip()
            if not (base and key): return []
            cal = get(base, key, '/v1/calendar?date=%s' % d.isoformat(), timeout=15)
        except Exception as e:
            return ['장 시간 — 토스 장 달력 조회 실패(%s). market_hours.json 그대로 쓴다' % str(e)[:80]]
    kr = (cal or {}).get('kr') or {}
    if (kr.get('today') or {}).get('date') != d.isoformat(): return []
    _synced[d] = True
    out = []
    for fn in (_sync_holidays, _sync_hours):   # 휴장일 먼저 — 장 시간의 전일, 익일 판단이 휴장일 파일에 기대지는 않지만 회차 순서대로 둔다
        try: out += fn(d, kr, verbose)
        except Exception as e: out.append('%s 자동 기록 실패 — %s' % ('휴장일' if fn is _sync_holidays else '장 시간', str(e)[:80]))
    return out

HOL_AUTO = '휴장(토스 장 달력 자동 기록'

def _sync_holidays(d, kr, verbose):
    """휴장일 자동 기록(2026-11-19 사용자 결정). 실제 오늘 날짜 조회의 전 영업일 ~ 다음 영업일 사이에 빠진 평일과,
    오늘이 휴장(open false)이면 오늘을 holidays.json 에 적는다. 10/8 조회의 다음 영업일 10/12 → 10/9 한글날, 9/23 → 9/28 → 추석 9/24, 9/25 로 확인했다.
    자동 기록 줄은 토스가 그날을 개장으로 답하면 지운다. 사람이 적은 줄은 고치지 않고 불일치만 알린다."""
    t, pv, nx = kr.get('today') or {}, kr.get('previousBusinessDay') or {}, kr.get('nextBusinessDay') or {}
    try:
        pd_, nd_ = date.fromisoformat(str(pv.get('date'))), date.fromisoformat(str(nx.get('date')))
    except ValueError:
        return []
    # 전, 다음 영업일은 오늘에서 14일 안만 믿는다(설, 추석 연휴에 주말이 붙어도 그 안이다)
    if not (d - timedelta(days=14) <= pd_ < d < nd_ <= d + timedelta(days=14)) or not (pv.get('open') and nx.get('open')):
        return ['휴장일 — 토스 장 달력의 전, 다음 영업일(%s, %s)이 이상해 자동 기록을 건너뜀' % (pv.get('date'), nx.get('date'))]
    today_open = t.get('open')
    closed, opened = [], [pd_, nd_] + ([d] if today_open else [])
    x = pd_ + timedelta(days=1)
    while x < nd_:
        if x.weekday() < 5 and (x != d or today_open is False): closed.append(x)
        x += timedelta(days=1)
    if len(closed) > 5:   # 실제 연휴는 평일 5일 안쪽이다. 더 많으면 토스 응답 오류로 보고 적지 않는다
        return ['휴장일 — 토스 장 달력이 평일 %d일을 한꺼번에 휴장으로 줬다(%s~%s). 자동 기록을 건너뜀. 관리 세션이 확인할 것' % (len(closed), closed[0], closed[-1])]
    if os.path.exists(HOLIDAYS):
        try:
            data = json.load(io.open(HOLIDAYS, encoding='utf-8'))
            if not isinstance(data, dict): raise ValueError('최상위가 객체가 아님')
        except Exception as e:
            return ['휴장일 — holidays.json 을 읽지 못해 자동 기록을 건너뜀(%s). 관리 세션이 파일을 고칠 것' % str(e)[:80]]
    else:
        data = {}
    out, dirty = [], False
    for x in closed:
        iso, e = x.isoformat(), data.get(x.isoformat())
        if e is None:
            data[iso] = '%s %s 조회)' % (HOL_AUTO, d.isoformat()); dirty = True
            out.append('휴장일 자동 기록 — %s(%s, 토스 장 달력). holidays.json 에 적었다' % (iso, '월화수목금'[x.weekday()]))
        elif verbose:
            out.append('휴장일 — %s %s(토스 달력 일치)' % (iso, e))
    for x in opened:
        iso, e = x.isoformat(), data.get(x.isoformat())
        if e is None: continue
        if str(e).startswith(HOL_AUTO):
            data.pop(iso); dirty = True
            out.append('휴장일 자동 기록 삭제 — %s 토스 장 달력은 개장' % iso)
        else:
            out.append('휴장일 불일치 — %s holidays.json 은 휴장(%s)인데 토스 장 달력은 개장(사람 기록, 그대로 둠). 관리 세션이 한국거래소 공지로 확인할 것' % (iso, e))
    if dirty: write_holidays(data)
    return out

def write_holidays(data):
    """holidays.json 을 키 순서를 지켜 쓴다. 새 날짜는 그보다 뒤 날짜 키 바로 앞에 넣는다('_note' 류 위치는 그대로)."""
    try:
        old = list(json.load(io.open(HOLIDAYS, encoding='utf-8')).keys())
    except Exception:
        old = []
    keys = [k for k in old if k in data]
    for k in sorted(k for k in data if k not in keys):
        i = next((j for j, o in enumerate(keys) if not o.startswith('_') and o > k), len(keys))
        keys.insert(i, k)
    tmp = HOLIDAYS + '.tmp'
    with io.open(tmp, 'w', encoding='utf-8', newline='\n') as f:
        f.write(json.dumps({k: data[k] for k in keys}, ensure_ascii=False, indent=2) + '\n')
    os.replace(tmp, HOLIDAYS)

def _sync_hours(d, kr, verbose):
    if os.path.exists(MARKET_HOURS):
        try:
            data = json.load(io.open(MARKET_HOURS, encoding='utf-8'))
            if not isinstance(data, dict): raise ValueError('최상위가 객체가 아님')
        except Exception as e:   # 깨진 파일을 뼈대로 덮으면 사람 줄이 사라진다 — 쓰지 않고 알린다
            return ['장 시간 — market_hours.json 을 읽지 못해 자동 기록을 건너뜀(%s). 관리 세션이 파일을 고칠 것' % str(e)[:80]]
    else:
        data = {'_note': '한국거래소 정규장 시간이 평소(09:00~15:30)와 다른 날', '_default': {'open': DEFAULT_SESSION[0], 'close': DEFAULT_SESSION[1]}}
    out, dirty = [], False
    for k in ('previousBusinessDay', 'today', 'nextBusinessDay'):
        day = kr.get(k) or {}
        h, iso = day.get('hours'), str(day.get('date') or '')
        if not (day.get('open') and isinstance(h, dict) and h.get('open') and h.get('close')): continue   # 휴장, 옛 VM(시각 없음), 이상한 값
        try: dd = date.fromisoformat(iso)
        except ValueError: continue
        # 전일은 오늘 전 7일 안, 익일은 오늘 뒤 7일 안만 믿는다 — 토스가 먼 날짜를 오늘 값으로 채우는 류의 오류를 막는다
        if (k == 'previousBusinessDay' and not (d - timedelta(days=7) <= dd < d)) or (k == 'nextBusinessDay' and not (d < dd <= d + timedelta(days=7))): continue
        got, e = (h['open'], h['close']), data.get(iso)
        if e is not None and not isinstance(e, dict): continue
        auto = {'open': got[0], 'close': got[1], 'why': '장 시간 변경', 'src': '%s(%s 조회)' % (AUTO_SRC, d.isoformat())}
        if not e:
            if got != DEFAULT_SESSION:
                data[iso] = auto; dirty = True
                out.append('장 시간 자동 기록 — %s 정규장 %s~%s(토스 장 달력). market_hours.json 에 적었다' % (iso, got[0], got[1]))
        elif (e.get('open'), e.get('close')) != got:
            if str(e.get('src') or '').startswith(AUTO_SRC):
                if got == DEFAULT_SESSION: data.pop(iso)
                else: data[iso] = auto
                dirty = True
                out.append('장 시간 자동 기록 수정 — %s 정규장 %s~%s → %s~%s(토스 장 달력)' % (iso, e.get('open'), e.get('close'), got[0], got[1]))
            else:
                out.append('장 시간 불일치 — %s 토스 장 달력 %s~%s, market_hours.json %s~%s(사람 기록, 그대로 둠). 관리 세션이 한국거래소 공지로 확인할 것' % (
                    iso, got[0], got[1], e.get('open'), e.get('close')))
        elif got != DEFAULT_SESSION and verbose:
            out.append('장 시간 — %s 정규장 %s~%s(%s, 토스 달력 일치)' % (iso, got[0], got[1], e.get('why') or 'market_hours.json'))
    if dirty: write_market_hours(data)
    return out

NIGHT_CLOSE = (6, 0)   # KRX 야간 파생상품시장 18:00 ~ 익일 06:00 (2025-06-09 부터. 그 전 유렉스 연계는 05:00)

def news_html(d):
    """news.json(fetch_news.py) → 브리핑 '밤사이 뉴스' 시각표(접힌 details). 제목은 매체가 단 그대로라
    금지 표현, 내부 용어 검사와 글자수에서 뺀다(class="news"). 06:00 야간선물 마감과 날짜가 바뀌는 곳에 표시 줄을 끼운다(2026-11-27)"""
    try: n = json.load(io.open('news.json', encoding='utf-8'))
    except FileNotFoundError:
        warn('news.json 없음 — 턴 0 에서 fetch_news.py 를 돌리지 않았다. 밤사이 뉴스 시각표만 빠진다 (게이트 무관)'); return ''
    except Exception as e:
        warn('news.json 을 읽지 못함 — %s (게이트 무관)' % e); return ''
    if n.get('issue_date') != d.isoformat():
        warn('news.json 이 %s 것 — 오늘 것이 아니라 쓰지 않는다 (fetch_news.py 를 다시 돌릴 것, 게이트 무관)' % n.get('issue_date')); return ''
    items = [x for x in n.get('items') or [] if x.get('t') and x.get('ms')]
    if not items:
        warn('밤사이 뉴스 없음 — %s (게이트 무관)' % ('; '.join(n.get('errors') or []) or '조회 창 안 기사 없음')); return ''
    try: items = sorted(((datetime.fromtimestamp(int(x['ms']) / 1000, KST), x) for x in items), key=lambda p: p[0])
    except (TypeError, ValueError, OverflowError) as e:
        warn('news.json 시각을 읽지 못함 — %s (게이트 무관)' % e); return ''
    nc = night_close_ms(d)
    rows, day, marked = [], None, False
    for t, x in items:
        if not marked and int(x['ms']) >= nc:
            nt = datetime.fromtimestamp(nc / 1000, KST)
            rows.append('<li class="nmk">%d/%d %s 야간선물 마감</li>' % (nt.month, nt.day, nt.strftime('%H:%M'))); marked = True
            day = nt.date()
        if t.date() != day:
            rows.append('<li class="ndt">%d/%d</li>' % (t.month, t.day)); day = t.date()
        url = str(x.get('url') or '')
        title = esc(x['t'])
        # 링크는 https 이고 공백, 따옴표, 꺾쇠가 없을 때만 건다(속성 밖으로 빠져나가지 않게, 2026-11-27 검수). 속성값은 따옴표까지 바꾼다
        if re.fullmatch(r'https://[^\s"\'<>`]+', url):
            title = '<a href="%s" target="_blank" rel="noopener noreferrer">%s</a>' % (esc(url).replace('"', '&quot;').replace("'", '&#39;'), title)
        rows.append('<li><span class="nt num">%s</span><span class="nb">%s<span class="ns">%s</span></span></li>' % (t.strftime('%H:%M'), title, esc(x.get('src') or '매체 미상')))
    span = ('%s 이후' % n['first']) if n.get('first') else '%s~%s' % (n.get('from') or '', (n.get('to') or '')[-5:])   # 창 앞부분을 못 받았으면 실제 시작을 쓴다
    return ('<details class="news"><summary>밤사이 뉴스 %d건(%s)</summary><div class="dbody"><ol class="nl">%s</ol>'
            '<p class="nn">Google 뉴스 검색으로 모은 제목입니다. 매체가 단 제목 그대로이고 내용은 확인하지 않았습니다.</p></div></details>') % (
        len(items), esc(span), ''.join(rows))

def expiry_day(y, m):
    """코스피200 선물, 옵션 만기일: 그달 둘째 목요일, 휴장이면 앞 영업일"""
    x = date(y, m, 1)
    x += timedelta(days=(3 - x.weekday()) % 7 + 7)
    while x.weekday() >= 5 or holiday_of(x): x -= timedelta(days=1)
    return x

def agenda_html(d, rel_cal, items_in):
    """브리핑 '오늘 일정'. 스크립트가 아는 것(만기일, 장 시간 변경, 오늘 밤 미국 휴장)과 회차가 읽은 기사에서 본 일정(fill.agenda, 3건까지)"""
    DOWK = '월화수목금토일'
    lab = lambda x: '오늘' if x == d else '%d/%d(%s)' % (x.month, x.day, DOWK[x.weekday()])
    out = []
    # 만기: 오늘부터 5영업일 안
    lim = d
    for _ in range(5): lim = next_business_day(lim)
    for y, m in ((d.year, d.month), (d.year + (d.month == 12), d.month % 12 + 1)):
        e = expiry_day(y, m)
        if d <= e <= lim:
            out.append((lab(e), '코스피200 선물, 옵션 동시 만기' if m in (3, 6, 9, 12) else '코스피200 옵션 만기'))
    for x in (d, next_business_day(d)):
        s = session_of(x)
        if s['changed']: out.append((lab(x), '정규장 %s~%s%s' % (s['open_hm'], s['close_hm'], '(%s)' % s['why'] if s['why'] else '')))
    us = ((rel_cal or {}).get('us') or {}).get('today') or {}
    if us.get('date') == d.isoformat() and us.get('open') is False: out.append(('오늘 밤', '미국 증시 휴장'))
    seen = 0
    for it in items_in or []:
        if not isinstance(it, dict) or not it.get('t'): continue
        seen += 1
        if seen > 3: warn('agenda 는 3건까지 — 나머지는 뺀다'); break
        check_len('agenda.t', it.get('t'), 40)
        out.append((str(it.get('when') or '오늘'), str(it['t'])))
    if not out: return ''
    return '<div class="agenda"><div class="rh">오늘과 다가오는 일정</div><ul class="ag">%s</ul></div>' % ''.join(
        '<li><b class="num">%s</b><span>%s</span></li>' % (esc(w), esc_keep(t)) for w, t in out)

def night_close_ms(d):
    """발행일 d 회차가 보는 야간선물 세션이 끝난 시각(ms). 직전 영업일 밤 세션 → 그다음 날 06:00.
    화~금은 발행일 06:00, 월요일은 토 06:00 (일요일 밤 세션은 없다). 2026-11-09 전에는 발행일 05:00 으로 재서
    월요일에 주말 움직임이 빠지고 평일에는 05:00~06:00 이 야간선물과 겹쳤다(CALIBRATION.md H2)."""
    return kst_ms(prev_business_day(d) + timedelta(days=1), *NIGHT_CLOSE)

def us_fut_basis(d):
    """07:45 KST 에 미국 지수선물(ES·NQ) 페이지의 등락률이 무엇을 뜻하는가.
    'post_close'   — 새 세션이 열린 뒤(미국 서머타임 기간, 07:45 KST = 18:45 ET). 직전 마감 뒤 ~ 지금의 움직임.
    'prev_session' — CME 일일 휴장(17:00~18:00 ET)·주말 휴장 중(미국 표준시 기간, 07:45 KST = 17:45 ET).
                     페이지는 방금 끝난 세션 전체의 등락을 보여 준다 — 야간선물 마감 뒤 움직임이 아니다.
    2026-11-02 회차부터 기록 시각이 07:36 → 06:59 로, |ES| 평균이 0.19% → 1.57% 로 바뀐 원인이다(2026-11-10 점검).
    판정 못 하면 None."""
    try:
        from zoneinfo import ZoneInfo
        et = datetime(d.year, d.month, d.day, 7, 45, tzinfo=KST).astimezone(ZoneInfo('America/New_York'))
    except Exception:
        return None
    wd, h = et.weekday(), et.hour   # CME Globex: 일 18:00 ~ 금 17:00 ET, 매일 17:00~18:00 휴장
    closed = h == 17 or (wd == 4 and h >= 17) or wd == 5 or (wd == 6 and h < 18)
    return 'prev_session' if closed else 'post_close'

NIGHT_XCHECK_PP, NIGHT_XCHECK_REL = 1.5, 0.2   # 야간선물 등락률 vs 같은 시각 추종가(pnight). 10/16~11/9 17회 |차이| 중앙 0.44·최대 1.00%p
POST_NOTE_PCT = 1.0   # 야간선물 마감 뒤 코스피200 추종가 변화가 이 % 이상이면 화면에 경고 줄(2026-11-18, 엔비디아 실적 06:23 KST)

def post_night_note(k200n, post, lo_pct, hi_pct, night_at, asof, widened=False, post_k=None):
    """예상 구간 경고 줄 — 06:00 뒤 움직임이 구간 중심에 다 들어 있지 않다. 큰 움직임이 있었으면 그 방향을 알린다.
    post_k 는 calibration.json rule.center_post_k(2026-11-21 H2 채택) — 중심에 이 배수만큼 들어 있다. 없으면 중심은 야간선물 그대로.
    규칙, 채점, 게이트는 건드리지 않는다. widened 는 월요일 확장(반폭에 |변화|를 더함)이 적용된 날 — 구간이 이미 담고 있어 뺀다. 조건이 아니면 None."""
    if widened or None in (k200n, post, lo_pct, hi_pct) or abs(post) < POST_NOTE_PCT:
        return None
    implied = ((1 + k200n / 100) * (1 + post / 100) - 1) * 100
    side = '위' if post > 0 else '아래'
    tail = ('시초가가 구간 %s로 벗어날 수 있습니다' % side) if not (lo_pct <= implied <= hi_pct) else ('시초가가 구간 %s쪽에서 나올 수 있습니다' % side)
    part = '이 움직임이 들어 있지 않아' if not post_k else ('이 움직임의 절반만 들어 있어' if abs(post_k - 0.5) < 1e-9 else '이 움직임의 %d%%만 들어 있어' % round(post_k * 100))
    text = '야간선물 마감(%s) 뒤 코스피200 추종가가 %s%.2f%% 움직였습니다(%s 기준). 예상 구간 중심에는 %s %s.' % (
        night_at, '+' if post > 0 else '−', abs(post), asof, part, tail)
    return {'post_pct': round(post, 2), 'implied_pct': round(implied, 2), 'side': side, 'night_at': night_at, 'asof': asof, 'text': text}

def stock_post_note(items, has_kospi, night_at, asof):
    """종목 경고 문장(2026-11-18 사용자 요청). items = [(이름, 06:00 뒤 변화 %)], 이미 조건(|변화| ≥ POST_NOTE_PCT, 평균 중심, 월요일 확장 아님)을 거른 것.
    종목 중심은 야간선물과 07:45 추종가의 평균이라 이 변화의 절반이 들어 있다. 방향은 말하지 않는다 — 삼성전자는 큰 날에도 잔차 부호가 반반이었다(CALIBRATION.md H9 행)."""
    if not items:
        return None
    moves = ', '.join('%s %s%.2f%%' % (n, '+' if p > 0 else '−', abs(p)) for n, p in items)
    if has_kospi:
        return '같은 시각 종목 추종가는 %s 움직였고, 종목 구간 중심에는 이 움직임의 절반만 들어 있습니다.' % moves
    return '야간선물 마감(%s) 뒤 종목 추종가는 %s 움직였습니다(%s 기준). 종목 구간 중심에는 이 움직임의 절반만 들어 있습니다.' % (night_at, moves, asof)

def state_before(iso):
    """발행일 iso 의 발행 커밋(brief: <iso> 발행) 직전 state.json. git 이 없거나 못 찾으면 None."""
    try:
        sha = subprocess.run(['git', 'log', '-1', '--format=%H', '--grep=^brief: %s ' % iso], capture_output=True, text=True, timeout=20).stdout.strip()
        if not sha: return None
        r = subprocess.run(['git', 'show', '%s~1:state.json' % sha], capture_output=True, text=True, timeout=20)
        return json.loads(r.stdout) if r.returncode == 0 else None
    except Exception:
        return None

def read_state(d=None):
    """state.json → (state, 상태). render.py·score.py 가 같이 쓴다.
    state.closes 는 '직전 영업일 회차가 남긴 종가'여야 등락률 기준이 된다(2026-11-10 재연: 아니면 틀린 등락률이 GATE PASS 로 나갔다).
      ok        직전 영업일 회차의 기록
      none      파일 없음
      recovered 같은 날 다시 돌린 경우 — state.json 이 이미 오늘 것이라 발행 커밋 직전 것을 git 에서 읽었다
      stale     직전 영업일 회차가 없다(건너뛴 날) — closes 를 등락률 기준으로 쓰면 안 된다"""
    try:
        st = json.load(io.open('state.json', encoding='utf-8'))
    except Exception:
        return {}, 'none'
    got = str(st.get('issue_date') or '')
    if d is None or not got: return st, 'ok'
    want = prev_business_day(d).isoformat()
    if got == want: return st, 'ok'
    if got == d.isoformat():
        old = state_before(got)
        if old: return old, ('recovered' if str(old.get('issue_date') or '') == want else 'stale')
    return st, 'stale'

def relay_closed_today(d):
    """holidays.json 에 없는 휴장일을 토스 장 달력(중계기 /v1/calendar)으로 한 번 더 본다. 휴장이면 사유, 아니거나 못 물으면 None.
    달력 응답이 깨졌을 때 멀쩡한 거래일을 휴장으로 보지 않도록, 오늘은 닫히고 다음 영업일은 열린다고 답할 때만 믿는다."""
    try:
        from fetch_relay import get
        base, key = os.environ.get('JJ_RELAY_URL', '').strip(), os.environ.get('JJ_RELAY_TOKEN', '').strip()
        if not (base and key): return None
        kr = (get(base, key, '/v1/calendar?date=%s' % d.isoformat(), timeout=15) or {}).get('kr') or {}
        t, n = kr.get('today') or {}, kr.get('nextBusinessDay') or {}
        if t.get('date') == d.isoformat() and t.get('open') is False and n.get('open') is True and str(n.get('date') or '') > d.isoformat():
            return '토스 장 달력 휴장(holidays.json 에 없던 날 — 다음 줄에서 자동 기록)'
    except Exception:
        pass
    return None

def perp_post_night(perp, d, t_snap=None):
    """perp.json → {key: {'pnight', 'snap', 'post'}}. pnight·snap 은 직전 영업일 15:30 대비 %,
    post 는 야간선물 마감 뒤 스냅샷까지 변화 %. 스냅샷은 fetched_ms(08:59 상한). 못 구한 키는 값이 None."""
    items = (perp or {}).get('items') or {}
    if t_snap is None:
        t_snap = min(int((perp or {}).get('fetched_ms') or kst_ms(d, 7, 45)), kst_ms(d, 8, 59))
    t_n = night_close_ms(d)
    out = {}
    for key, it in items.items():
        b, cs = it.get('base'), it.get('candles') or []
        def at(t):
            v = [c for tt, c in cs if tt <= t]
            return v[-1] if (v and b) else None
        n, s = at(t_n), at(t_snap)
        out[key] = {'pnight': None if n is None else round((n / b - 1) * 100, 2),
                    'snap': None if s is None else round((s / b - 1) * 100, 2),
                    'post': None if (n is None or s is None) else round((s / n - 1) * 100, 2)}
    return out

def issue_window(d):
    """CONTEXT.md '조회 창' — 직전 영업일 종가 시각(평소 15:30) ~ 발행일 07:45 (KST). 월요일·연휴 뒤도 prev_business_day 가 마지막 영업일을 준다."""
    p = prev_business_day(d)
    h, m = session_of(p)['close']   # 수능일처럼 늦게 닫은 날은 그 종료 시각부터(2026-11-19)
    return datetime(p.year, p.month, p.day, h, m, tzinfo=KST), datetime(d.year, d.month, d.day, 7, 45, tzinfo=KST)

def parse_at(s, d):
    """기사 시각 'M/D HH:mm'(KST) → datetime. 연도는 발행일 기준(발행일보다 뒤 달이면 전년). 못 읽으면 None."""
    m = re.match(r'^\s*(\d{1,2})/(\d{1,2})\s+(\d{1,2}):(\d{2})\s*$', str(s or ''))
    if not m: return None
    mo, dd, hh, mi = (int(x) for x in m.groups())
    try:
        return datetime(d.year - (1 if mo > d.month else 0), mo, dd, hh, mi, tzinfo=KST)
    except ValueError:
        return None

def issue_sources(src, d):
    """checks.issue.src(B6 출처 3분류 + D3 기사 시각) → (details HTML, day.json 목록, 미확인 건수). 경고만 내고 게이트에는 넣지 않는다.
    origin·at 은 회차가 실제로 읽은 기사의 매체와 시각이다(2026-11-10 — '최초 보도'로 적게 했더니 조회 창 안 재보도를 최초로 적었다).
    그 재료의 첫 보도가 더 이르다는 걸 알면 first 에 따로 적는다(예: "11/9 05:12 CNBC")."""
    if not src:
        warn('checks.issue.src 없음 — 이슈마다 최초 보도·확산·확인 출처와 기사 시각(at)을 적을 것 (게이트 무관)')
        return '', [], 0
    w0, w1 = issue_window(d)
    items, rows, unv = [], [], 0
    for x in src if isinstance(src, list) else []:
        if not isinstance(x, dict) or not x.get('t'): continue
        t, origin, at = str(x.get('t')), x.get('origin') or '', x.get('at')
        mom, ver = x.get('momentum') or '', x.get('verify') or ''
        dt = parse_at(at, d)
        if not at: warn('이슈 출처 "%s" 기사 시각(at) 없음 (게이트 무관)' % t)
        elif dt is None: warn('이슈 출처 "%s" 기사 시각 %r 형식 오류 — "M/D HH:mm" (게이트 무관)' % (t, at))
        elif not (w0 <= dt <= w1):
            warn('이슈 출처 "%s" 기사 시각 %s 가 조회 창(%s ~ %s) 밖 — 묵은 기사인지 확인 (게이트 무관)' % (
                t, at, '%d/%d %s' % (w0.month, w0.day, w0.strftime('%H:%M')), '%d/%d %s' % (w1.month, w1.day, w1.strftime('%H:%M'))))
        if not ver: unv += 1
        parts = ['%s — 출처 %s%s' % (t, origin or '미기재', ' (%s)' % at if at else '')]
        if x.get('first'): parts.append('첫 보도 %s' % x.get('first'))
        if mom: parts.append('확산 %s' % mom)
        parts.append('확인 %s' % ver if ver else '확인 출처 없음(미확인)')
        items.append(' · '.join(parts))
        rows.append({'t': t, 'origin': origin, 'at': at, 'verify': ver or None})
    head = '이슈 출처 %d건%s' % (len(rows), ' · 미확인 %d건' % unv if unv else '')
    return details(head, items), rows, unv

def krx_tick(p):
    """KRX 호가단위 (2023-01 개편 기준)."""
    for lim, t in ((2000, 1), (5000, 5), (20000, 10), (50000, 50), (200000, 100), (500000, 500)):
        if p < lim: return t
    return 1000

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

def load_internal_terms():
    """CONTEXT.md '내부 용어' 절의 표 첫 열 — 절차 문서·스크립트에서만 쓰는 말. 독자 화면에 나가면 경고한다(게이트 무관)."""
    pats = []
    for m in re.finditer(r'^\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*$', context_section('내부 용어'), re.M):
        left = m.group(1)
        if left in ('쓰지 말 것', '---') or left.startswith('-'): continue
        pats += [x.strip() for x in left.split('/') if len(x.strip()) >= 2]
    return pats

# ---------- 본체 ----------
def main():
    if '--today' in sys.argv:
        d = kst_today()
        h = holiday_of(d) or relay_closed_today(d)
        print(('HOLIDAY %s' % h) if h else 'OPEN', d.isoformat())
        for line in sync_market_hours(d, verbose=True): print(line)   # 휴장일, 장 시간 자동 기록(2026-11-19). 첫 줄(OPEN/HOLIDAY)은 그대로
        return 0

    check_only = '--check' in sys.argv
    tpl = io.open(TEMPLATE, encoding='utf-8').read()
    fill = json.load(io.open('fill.json', encoding='utf-8'))
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
    prev, prev_status = read_state(d)
    base_ok = prev_status != 'stale'   # False 면 state.closes 를 등락률 기준으로 쓰지 않는다
    if prev_status == 'none':
        warn('state.json 없음 — 등락률은 fill.json 의 pct_screen 을 쓴다')
    elif prev_status == 'recovered':
        warn('같은 날 다시 돌림 — state.json 이 이미 %s 것이라 발행 커밋 직전 기록(%s 회차)을 git 에서 읽었다 (게이트 무관)' % (issue_date, prev.get('issue_date')))
    elif prev_status == 'stale':
        warn('직전 회차 기록이 %s 것 — 직전 영업일(%s) 회차가 없다. 등락률은 화면값(pct_screen)을 쓰고 EWY·ADR 시사 갭은 비운다. '
             'pct_screen 이 빠진 종목은 등락률이 미확보로 나가니 모두 채울 것 (게이트 무관)' % (prev.get('issue_date'), prev_business_day(d).isoformat()))
    sess, psess = session_of(d), session_of(prev_business_day(d))
    if sess['changed']:
        print('장 시간 — 오늘 정규장 %s~%s(%s). 화면 제목과 장중 차트가 이 시각을 쓴다' % (sess['open_hm'], sess['close_hm'], sess['why'] or 'market_hours.json'))
    if psess['changed']:
        print('장 시간 — 직전 영업일(%s) 정규장 %s~%s(%s). 종가와 추종가 기준이 %s 다' % (prev_business_day(d).isoformat(), psess['open_hm'], psess['close_hm'], psess['why'] or 'market_hours.json', psess['close_hm']))
    nsess = session_of(next_business_day(d))
    if nsess['changed']:
        print('장 시간 — 다음 영업일(%s) 정규장 %s~%s(%s). 응답에 한 줄로 옮긴다' % (next_business_day(d).isoformat(), nsess['open_hm'], nsess['close_hm'], nsess['why'] or 'market_hours.json'))
    made_at = datetime.now(KST)
    if d == made_at.date() and (made_at.hour, made_at.minute) >= sess['open']:
        warn('개장(%s) 뒤에 만든 회차 — %s. 전망이 시초가를 본 뒤의 값일 수 있다. state.forecast.made_at 에 남긴다 (게이트 무관)' % (sess['open_hm'], made_at.strftime('%H:%M')))
    DOW = '월화수목금토일'
    V = {}
    V['GENERATED'] = '%sT07:45+09:00' % issue_date
    V['ISSUE'] = str(weekday_ordinal(d))
    V['DATE_LABEL'] = '%d년 %d월 %d일 (%s)' % (d.year, d.month, d.day, DOW[d.weekday()])
    V['SUBTITLE'] = '07:45 KST · 전일 종가 &amp; 간밤 미국장 반영'
    V['OPEN_HM'] = sess['open_hm']
    V['CLOSE_HM'], V['PREV_CLOSE_HM'] = sess['close_hm'], psess['close_hm']
    V['SESS_SPAN'] = '%s → %s' % (sess['open_hm'], sess['close_hm'])
    V['SESS_NOTE'] = ('' if not sess['changed'] else ' <small class="sessn">(%s, 정규장 %s~%s)</small>' % (esc(sess['why'] or '장 시간 변경'), sess['open_hm'], sess['close_hm']))

    # ----- 중계기(토스) 보완 — relay.json 으로 빈칸을 채우고 회차 값과 다르면 알린다. 입력 파일은 고치지 않는다 -----
    try:
        from fetch_relay import merge_into
        relay_state, relay_filled, relay_diff = merge_into(fill)
    except Exception as e:
        relay_state, relay_filled, relay_diff = 'fail', [], []
        warn('중계기 보완 실패 — %s' % e)
    if relay_filled: print('중계기 보완 %d건 — %s' % (len(relay_filled), ', '.join(relay_filled)))
    for m in relay_diff: warn('회차 값과 중계기 값이 다름 — %s. 문장·data_note 에 회차 값을 썼으면 고칠 것' % m)
    if relay_state == 'stale': warn('relay.json 이 오늘 것이 아님 — fetch_relay.py 를 다시 돌릴 것 (게이트 무관)')
    elif relay_state == 'absent': warn('relay.json 없음 — 턴 0 에서 fetch_relay.py 를 돌리지 않았다 (게이트 무관)')
    elif relay_state == 'fail': warn('중계기 실패 — 웹에서 받은 값만 쓴다 (게이트 무관)')

    # ----- 시세 -----
    prices = fill.get('prices') or {}
    # 채점용 시가 — 없으면 다음 회차가 아니라 이번 회차 채점이 빠진다. 값을 채웠으면 score.py 부터 다시 돌린다
    sf_prev, pf_prev = prev.get('stock_forecast') or {}, prev.get('forecast') or {}
    for code in sorted(sf_prev.get('items') or {}):
        p = prices.get(code) or {}
        if p.get('open') in (None, '') or p.get('open_date') != sf_prev.get('date'):
            warn('종목 시초가 미확보 — %s (전망 %s, open_date %s) · 종목 채점이 빠진다. fetch_relay.py 출력의 시가를 prices.%s.open·open_date 에 적고 score.py 부터 다시 돌릴 것' % (
                code, sf_prev.get('date'), p.get('open_date'), code))
    kp = prices.get('KOSPI') or {}
    if pf_prev.get('date') and not (fill.get('score') or {}).get('actual_open') and (
            kp.get('open') in (None, '') or (kp.get('open_date') and kp.get('open_date') != pf_prev['date'])):
        warn('코스피 시초가 미확보 — 직전 전망(%s) 채점이 빠진다. prices.KOSPI.open 을 채우고 score.py 부터 다시 돌릴 것' % pf_prev['date'])
    prev_closes = (prev.get('closes') or {})
    pct = {}      # 계산 등락률
    close = {}
    for k in STATE_KEYS + ['K200N']:
        p = prices.get(k) or {}
        c = as_num(p.get('close'), 'prices.%s.close' % k)
        close[k] = c
        scr = as_num(p.get('pct_screen'), 'prices.%s.pct_screen' % k)
        base = as_num(prev_closes.get(k), 'state.closes.%s' % k) if (k != 'K200N' and base_ok) else None
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
            if base is None and base_ok: warn('%s 기준값이 state.json 에 없어 화면 등락률을 씀' % k)
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
        cd2 = ''   # 야간선물 기준(주간선물 종가)은 둘째 줄 — 한 줄이면 360px 에서 등락 칸이 밀린다(2026-11-27)
        if k == 'K200N' and close.get('K200F') is not None:
            cd2 = '<span class="cd">주간 %s 대비</span>' % num(close['K200F'], 2)
        if c is None:
            pr = '<td class="pr num">—</td><td class="ch na">미확보</td>'
        else:
            cc = cls(q)
            pr = '<td class="pr num%s">%s</td><td class="ch %snum">%s</td>' % (
                (' ' + cc) if cc else '', num(c, DECIMALS.get(k, 2)), (cc + ' ') if cc else '', pct_str(q))
        return ('<tbody class="st"><tr><td class="nm">%s<span class="cd">%s</span>%s</td>%s</tr>'
                '<tr><td class="cm" colspan="3">%s%s</td></tr></tbody>' % (
                    esc(nm), esc_keep(cd), cd2, pr, esc_keep(cm), details('근거', p.get('more'))))

    V['GLOBAL_ROWS'] = ''.join(row(k) for k in GLOBAL_ORDER)

    # 참고 시세 — 중계기 일봉(마지막 봉과 그 앞 봉). 마지막 봉이 직전 미국 거래일보다 이르면(미국 휴장, 중계기 지연) 등락률을 비운다
    us_exp = d - timedelta(days=1)
    while us_exp.weekday() >= 5: us_exp -= timedelta(days=1)
    ref_at = {}
    for k in REF_RELAY:
        r = (fill.get('ref') or {}).get(k) or {}
        c = as_num(r.get('close'), 'ref.%s.close' % k)
        if c is None: continue
        close[k] = c
        stale = str(r.get('date') or '') < us_exp.isoformat()
        pct[k] = None if stale else as_num(r.get('pct'), 'ref.%s.pct' % k)
        if stale:
            try: rd = date.fromisoformat(str(r.get('date'))[:10]); ref_at[k] = '%d/%d 종가' % (rd.month, rd.day)
            except ValueError: ref_at[k] = '지난 종가'
    def mlabel_ref(k):
        return 'EWY' if k == 'EWY' else names[k][0]
    def refcell(k):
        c, q = close.get(k), pct.get(k)
        cc = cls(q) if (c is not None and q is not None) else 'na'
        return ('<div><span class="fk">%s</span><span class="fv num %s">%s</span><span class="fc num">%s</span></div>' % (
            esc(mlabel_ref(k)), cc, pct_str(q).replace('▲ ', '').replace('▼ ', '') if q is not None else (ref_at.get(k) or '미확보'), num(c, 2)))   # 좁은 칸이라 화살표 없이 부호만
    got = [k for k in REF_ORDER if close.get(k) is not None]
    V['GLOBAL_REF'] = ('<div class="refs"><div class="rh">참고 시세</div><div class="fgrid">%s</div></div>' % ''.join(refcell(k) for k in got)) if got else ''
    if not any(k in got for k in REF_RELAY): warn('참고 시세(TSMC, DRAM, 앤트로픽) 없음 — 중계기 일봉을 못 받았다. fetch_relay.py 의 일부 실패 줄을 9단계 못 구한 데이터에 옮긴다(웹에서 받지 않는다, 게이트 무관)')
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
    # 미국 종가가 직전 기록과 똑같으면 미국 휴장(또는 값 재사용)이다. 그대로 계산하면 한국 쪽 움직임만
    # 뒤집혀 허위 갭이 나오므로 그 시사 갭은 뺀다.
    us_same = [k for k in ('EWY', 'SKHY')
               if base_ok and close.get(k) is not None and prev_closes.get(k) is not None and close[k] == prev_closes.get(k)]
    for k in us_same: warn('%s 종가가 직전 기록과 같음 — 미국 휴장으로 보고 시사 갭에서 제외' % k)
    def implied(fx_key, us_key, kr_key):
        if us_key in us_same or not base_ok: return None   # 기준이 묵은 날은 미국 휴장을 가려낼 수 없어 시사 갭을 내지 않는다
        a, b, c = pct.get(us_key), pct.get(fx_key), pct.get(kr_key)
        if a is None or b is None or c is None: return None
        return ((1 + a / 100) * (1 + b / 100) / (1 + c / 100) - 1) * 100
    sig_in = fill.get('signals') or {}
    uf = sig_in.get('us_fut') or {}
    es_pct, nq_pct = as_num(uf.get('es_pct'), 'signals.us_fut.es_pct'), as_num(uf.get('nq_pct'), 'signals.us_fut.nq_pct')
    signals = {
        'k200n_pct': pct.get('K200N'),
        'k200n_close': close.get('K200N'),
        'k200n_asof': (prices.get('K200N') or {}).get('asof'),
        'k200f_close': close.get('K200F'),
        'ewy_implied_pct': implied('USDKRW', 'EWY', 'KOSPI'),
        'adr_implied_pct': implied('USDKRW', 'SKHY', '000660'),
        'news_flag': sig_in.get('news_flag'),
        'night_skipped': night_session_skipped(d),
        'us_holiday': len(us_same) == 2,
        # 미국 지수선물(ES·NQ) 직전 정산가 대비 — 야간선물 마감 뒤 ~ 회차 시점의 움직임. 기록만 하고 게이트·전망에 쓰지 않는다
        'es_pct': es_pct,
        'nq_pct': nq_pct,
        'us_fut_asof': uf.get('asof'),
        'us_fut_basis': us_fut_basis(d),   # post_close | prev_session — analyze.py 가 post_close 만 후보 3 에 쓴다
        'base_stale': not base_ok,         # True 면 등락률이 화면값이고 시사 갭이 비어 있다
    }
    if es_pct is None and nq_pct is None:
        warn('미국 지수선물(signals.us_fut) 미확보 — 기록만 비운다(게이트 무관)')
    for k, v in (('ES', es_pct), ('NQ', nq_pct)):
        if v is not None and abs(v) > 5: warn('%s 선물 %+.2f%% — 등락률이 아니라 포인트 변화를 넣었는지 확인' % (k, v))
    for k in ('ewy_implied_pct', 'adr_implied_pct'):
        if signals[k] is not None: signals[k] = round(signals[k], 2)
    if signals['k200n_pct'] is None:
        if signals['night_skipped']:
            warn('야간선물(K200N) 미확보 — 휴장(%s) 뒤 회차라 야간 세션이 없다. 게이트에서 제외' % ', '.join(signals['night_skipped']))
        else:
            warn('야간선물(K200N) 미확보 — 자동 발행 게이트에 걸린다')
    # 야간선물은 구간 중심인데 경로가 하나뿐이다(sources.json). 기준 시각이 직전 야간 세션 마감일인지 본다 — 묵은 값이면 게이트에 건다
    night_flags = []
    if signals['k200n_pct'] is not None and not signals['night_skipped']:
        n_close = datetime.fromtimestamp(night_close_ms(d) / 1000, KST)
        n_at = parse_at(signals['k200n_asof'], d)
        if n_at is None:
            warn('야간선물 기준 시각(prices.K200N.asof) %r 을 읽지 못함 — "M/D HH:mm" 으로 적을 것 (게이트 무관)' % signals['k200n_asof'])
        elif n_at.date() != n_close.date():
            night_flags.append('기준 시각')
            warn('야간선물 기준 시각 %s 가 직전 야간 세션 마감(%d/%d %s)과 날짜가 다름 — 묵은 값인지 sonmul 에서 다시 확인. 자동 발행 게이트에 걸린다' % (
                signals['k200n_asof'], n_close.month, n_close.day, n_close.strftime('%H:%M')))
    if signals['k200n_pct'] is not None and close.get('K200N') and close.get('K200F'):
        calc = (close['K200N'] / close['K200F'] - 1) * 100
        if abs(calc - signals['k200n_pct']) >= 0.05:
            warn('야간선물 등락률 페이지값 %+.2f%% 와 (야간종가/주간종가) 계산값 %+.2f%% 가 다름' % (signals['k200n_pct'], calc))
    def chip(label, p, note=''):
        if p is None: return '<span class="na">%s 미확보</span>' % label
        return '<span class="%s">%s %s%s</span>' % (cls(p) or '', label, pct_str(p), ('<small>%s</small>' % esc(note)) if note else '')
    V['SIGNAL_STRIP'] = (chip('야간선물', signals['k200n_pct'], signals['k200n_asof'] or '') +
                         (chip('EWY 시사', signals['ewy_implied_pct']) if signals['k200n_pct'] is None else '') +   # 2026-11-27 야간선물이 없는 날만
                         chip('ADR 시사', signals['adr_implied_pct']) +
                         (chip('미국선물 ES', es_pct, uf.get('asof') or '') if (es_pct is not None and signals['us_fut_basis'] != 'prev_session') else ''))

    # ----- 전망 -----
    # 전망은 구간(low·high)만. 방향 3분류(갭상승·보합·갭하락)는 2026-10-21 폐지 — fill 에 dir 가 남아 있어도 읽지 않는다
    fc = fill.get('forecast') or {}
    low, high = as_num(fc.get('low'), 'forecast.low'), as_num(fc.get('high'), 'forecast.high')
    kospi_close = close.get('KOSPI')
    lo_p = hi_p = None
    if low is None or high is None: fail('forecast.low/high 없음')
    elif low >= high: fail('forecast.low >= high')
    elif kospi_close:
        lo_p, hi_p = (low / kospi_close - 1) * 100, (high / kospi_close - 1) * 100
        if hi_p - lo_p < 1.0: warn('구간 폭 %.2f%%p — 최근 |갭| 중앙값(1.3%%) 보다 좁다' % (hi_p - lo_p))
    else:
        warn('코스피 종가가 없어 구간 % 를 계산하지 못함')
    center_p = None if lo_p is None else (lo_p + hi_p) / 2
    V['OPEN_FORECAST'] = ((('+' if center_p > 0 else '−' if center_p < 0 else '') + '%.2f%% 안팎 출발' % abs(center_p)) if center_p is not None
                          else ('구간 전망' if low and high else '전망 없음'))
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
        for key, lab in (('k200n_pct', '야간'),) + ((('ewy_implied_pct', 'EWY'),) if signals['k200n_pct'] is None else ()):
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
        strip.append('<div class="s %s">%s</div>' % ('hit' if r.get('in_range') else 'miss', md(r.get('date', ''))))
    while len(strip) < 10: strip.append('<div class="s">—</div>')
    V['SCORE_STRIP'] = ''.join(strip)

    sc = fill.get('score') or {}
    if today_scored:
        V['VERDICT_CLASS'] = 'hit' if last.get('in_range') else 'miss'
        V['VERDICT'] = '%s 회차 — %s' % (md(last['date']), '적중' if last.get('in_range') else '빗나감')
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
        bws = [r['band_width_pct'] for r in recs if r.get('band_width_pct') is not None]
        V['COVERAGE'] = '누적 %d회차 — 적중(구간 안) %.1f%% (%d/%d, 목표 80%%) · 평균 구간폭 %.2f%%p' % (
            len(recs), cov * 100, sum(1 for r in scored if r['in_range']), len(scored),
            (sum(bws) / len(bws)) if bws else 0)
        last10 = scored[-10:]
        errs = []
        for r in last10:
            if r.get('low') is not None and r.get('prev_close'):
                c = ((r['low'] + r['high']) / 2 / r['prev_close'] - 1) * 100
                errs.append(abs(r['gap_pct'] - c))
        errs.sort()
        med = errs[len(errs) // 2] if errs else None
        V['CONF_LINE'] = '최근 %d회 — 구간 안 %d · 중심 오차 중앙 %s' % (
            len(last10), sum(1 for r in last10 if r['in_range']), ('%.2f%%p' % med) if med is not None else '—')
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
    if len(why) != 4: warn('why 는 4개 문단 (아래로 미는 힘 / 위로 받치는 힘 / 왜 이 중심 / 구간 폭 근거), 지금 %d개' % len(why))
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
    src_html, issue_src, _ = issue_sources((chks.get('issue') or {}).get('src'), d)
    V['ISSUE_CHK'] += src_html   # details 안이라 접힘 4,000자에 들지 않는다
    V['NEWS'] = news_html(d)
    try: rel_cal = (json.load(io.open('relay.json', encoding='utf-8')) or {}).get('calendar')
    except Exception: rel_cal = None
    V['AGENDA'] = agenda_html(d, rel_cal, fill.get('agenda'))

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

    # ----- v5 대시보드 (첫 화면). 회차(LLM)가 쓰는 값은 없다 — 전부 위에서 만든 값과 perp.json 으로 만든다 -----
    pday = prev_business_day(d)
    t_prev, t_open, t_close = kst_ms(pday, *psess['close']), kst_ms(d, *sess['open']), kst_ms(d, *sess['close'])   # 수능일 등은 market_hours.json
    t_night, t_0500 = night_close_ms(d), kst_ms(d, 5, 0)   # 차트 야간 표식은 실제 마감(평일 06:00, 월요일은 토 06:00). 05:00 은 옛 p0500 기록용
    try:
        perp = json.load(io.open('perp.json', encoding='utf-8'))
    except Exception:
        perp = {}
    if perp and perp.get('issue_date') != issue_date:
        warn('perp.json 이 %s 것 — 오늘 것이 아니라 쓰지 않는다 (fetch_perp.py 를 다시 돌릴 것)' % perp.get('issue_date')); perp = {}
    pitems = perp.get('items') or {}
    if not pitems:
        warn('해외 24시간 추종가(perp.json) 미확보 — 종목 구간은 야간선물만으로, 장외 차트는 브라우저가 직접 받는다 (게이트 무관)')
    for e in perp.get('errors') or []: warn('추종가 일부 실패 — %s' % e)
    t_snap = min(int(perp.get('fetched_ms') or kst_ms(d, 7, 45)), kst_ms(d, 8, 59)) if pitems else kst_ms(d, 7, 45)
    def perp_path(key):
        it = pitems.get(key) or {}
        b = it.get('base')
        if not b: return None, []
        return b, [[t, round((c / b - 1) * 100, 3)] for t, c in (it.get('candles') or []) if t_prev <= t <= t_snap]
    def perp_at(key, t):
        b, pth = perp_path(key)
        v = [x for x in pth if x[0] <= t]
        return v[-1][1] if v else None
    k200n_now = signals['k200n_pct'] if not signals['night_skipped'] else None   # 휴장 뒤 야간선물은 묵은 값이라 종목 구간에 쓰지 않는다
    srule = cal.get('stock_rule') or {}
    hws = srule.get('half_width_pct') or {}
    stock_fc = {}
    STOCK_KEYS = ('005930', '000660')
    pn = perp_post_night(perp, d, t_snap) if pitems else {}
    # 월요일 확장(2026-11-09 사용자 결정, CALIBRATION.md H6) — 반폭 + |야간선물 마감(토 06:00) 뒤 그 종목 추종가 변화|. 코스피(H5)와 같은 방식.
    # 휴장 뒤 월요일은 빼고(야간선물을 안 쓰는 날), 추종가가 없으면 아래 한쪽 신호 ×1.25 가 이미 넓혀 둔다
    s_monday = d.weekday() == 0 and srule.get('monday_widen') == 'post_night_abs' and not signals['night_skipped']
    for code in STOCK_KEYS:
        pc, pp = close.get(code), perp_at(code, t_snap)
        comps = [x for x in (k200n_now, pp) if x is not None]
        if not pc or not comps:
            warn('%s 예측 구간 못 냄 — 종가 또는 신호(야간선물·추종가) 없음' % code); continue
        c = sum(comps) / len(comps)
        hw = float(hws.get(code, 1.5)) * (1.0 if len(comps) == 2 else 1.25)
        mw = None
        if s_monday:
            post = (pn.get(code) or {}).get('post')
            if post is not None: mw = abs(post)
            elif len(comps) == 2: mw = hw * (float(srule.get('monday_widen_fallback') or 1.25) - 1)
            if mw is not None: hw += mw
        tk = krx_tick(pc)
        lo_v = math.floor(pc * (1 + (c - hw) / 100) / tk) * tk
        hi_v = math.ceil(pc * (1 + (c + hw) / 100) / tk) * tk
        stock_fc[code] = {'low': lo_v, 'high': hi_v, 'prev_close': pc, 'center_pct': round(c, 2), 'half_width_pct': round(hw, 2),
                          'inputs': {'k200n_pct': k200n_now, 'perp_pct': None if pp is None else round(pp, 2)}}
        if mw is not None: stock_fc[code]['monday_widen_pct'] = round(mw, 2)
    # 야간선물 대조 — 같은 시각 코스피200 추종가(pnight)와 크게 다르면 한쪽이 틀렸다. 게이트에 건다
    kpn = (pn.get('KOSPI') or {}).get('pnight')
    if k200n_now is not None and kpn is not None:
        lim = max(NIGHT_XCHECK_PP, NIGHT_XCHECK_REL * abs(k200n_now))
        if abs(k200n_now - kpn) > lim:
            night_flags.append('추종가 대조')
            warn('야간선물 %+.2f%% 와 같은 시각 코스피200 추종가 %+.2f%% 가 %.2f%%p 다름(허용 %.2f%%p) — sonmul 값·기준 시각을 다시 확인. 자동 발행 게이트에 걸린다' % (
                k200n_now, kpn, abs(k200n_now - kpn), lim))
    # 야간선물 마감 뒤(pnight → 스냅샷) 추종가 움직임. 코스피 중심 보정(rule.center_post_k, 2026-11-21 H2 채택)은 score.py 가 계산하고 회차가 forecast 에 옮긴다. 여기서는 기록과 경고 줄만.
    # p0500 은 2026-11-09 전 방식(발행일 05:00) 그대로 남긴다 — 옛 기록과 이어 보기용
    signals['perp'] = {k: {'p0500': None if perp_at(k, t_0500) is None else round(perp_at(k, t_0500), 2),
                           'pnight': (pn.get(k) or {}).get('pnight'),
                           'snap': None if perp_at(k, t_snap) is None else round(perp_at(k, t_snap), 2)} for k in pitems}
    signals['perp_night_at'] = datetime.fromtimestamp(night_close_ms(d) / 1000, KST).strftime('%m/%d %H:%M')
    signals['perp_asof'] = datetime.fromtimestamp(t_snap / 1000, KST).strftime('%m/%d %H:%M') if pitems else None
    # 06:00 뒤 큰 움직임 경고 줄 — 휴장 뒤 회차는 야간선물을 중심에 안 쓰므로 뺀다
    n_dt = datetime.fromtimestamp(night_close_ms(d) / 1000, KST)
    n_at = n_dt.strftime('%H:%M') if n_dt.date() == d else '%d/%d %s' % (n_dt.month, n_dt.day, n_dt.strftime('%H:%M'))
    s_at = datetime.fromtimestamp(t_snap / 1000, KST).strftime('%H:%M')
    k_note = post_night_note(k200n_now, (pn.get('KOSPI') or {}).get('post'),
                             None if (low is None or not kospi_close) else (low / kospi_close - 1) * 100,
                             None if (high is None or not kospi_close) else (high / kospi_close - 1) * 100,
                             n_at, s_at, widened=d.weekday() == 0 and (cal.get('rule') or {}).get('monday_widen') == 'post_night_abs',
                             post_k=(cal.get('rule') or {}).get('center_post_k')) if pitems else None
    if k_note:
        warn('예상 구간 경고 줄 — 06:00 뒤 코스피200 추종가 %+.2f%%, 야간선물 + 변화 %+.2f%% (구간 %+.2f ~ %+.2f%%, 게이트 무관)' % (
            k_note['post_pct'], k_note['implied_pct'], (low / kospi_close - 1) * 100, (high / kospi_close - 1) * 100))
    # 종목 — 중심이 평균(야간선물과 추종가 둘 다)인 날만. 휴장 뒤(추종가만 씀)와 월요일 확장일은 구간이 이미 움직임을 담아 뺀다
    s_items = []
    for code in STOCK_KEYS:
        f = stock_fc.get(code) or {}
        mv = (pn.get(code) or {}).get('post')
        if (not f or None in ((f.get('inputs') or {}).get('k200n_pct'), (f.get('inputs') or {}).get('perp_pct'), mv)
                or 'monday_widen_pct' in f or abs(mv) < POST_NOTE_PCT):
            continue
        s_items.append({'code': code, 'name': names[code][0], 'post_pct': round(mv, 2)})
    s_text = stock_post_note([(x['name'], x['post_pct']) for x in s_items], bool(k_note), n_at, s_at) if pitems else None
    if s_items:
        warn('예상 구간 경고 줄(종목) — 06:00 뒤 추종가 %s (게이트 무관)' % ', '.join('%s %+.2f%%' % (x['name'], x['post_pct']) for x in s_items))
    post_note = ({'text': ' '.join(t for t in ((k_note or {}).get('text'), s_text) if t), 'kospi': k_note, 'stocks': s_items}
                 if (k_note or s_items) else None)
    V['POST_NOTE'] = '<div class="pnw">%s</div>' % esc(post_note['text']) if post_note else ''

    pl = (lambda iso: md(iso))(fill.get('closes_as_of') or pday.isoformat())
    ents = []
    kb, kpath = perp_path('KOSPI')
    ents.append({'key': 'KOSPI', 'name': '코스피', 'coin': (pitems.get('KOSPI') or {}).get('coin') or 'xyz:KR200', 'unit': '', 'approx': True,
                 'tick': 0, 'dec': 2, 'prev': kospi_close, 'prev_label': pl, 'base': kb, 'path': kpath,
                 'lo': None if (low is None or not kospi_close) else round((low / kospi_close - 1) * 100, 3),
                 'hi': None if (high is None or not kospi_close) else round((high / kospi_close - 1) * 100, 3),
                 'lo_v': low, 'hi_v': high, 'night': k200n_now})
    DEFAULT_COIN = {'005930': 'xyz:SMSN', '000660': 'xyz:SKHX'}
    for code in STOCK_KEYS:
        if not close.get(code): continue
        b, pth = perp_path(code); f = stock_fc.get(code) or {}
        ents.append({'key': code, 'name': names[code][0], 'coin': (pitems.get(code) or {}).get('coin') or DEFAULT_COIN[code], 'unit': '원',
                     'approx': False, 'tick': krx_tick(close[code]), 'dec': 0, 'prev': close[code], 'prev_label': pl, 'base': b, 'path': pth,
                     'lo': None if not f else round((f['low'] / close[code] - 1) * 100, 3), 'hi': None if not f else round((f['high'] / close[code] - 1) * 100, 3),
                     'lo_v': f.get('low'), 'hi_v': f.get('high'), 'night': None})
    rm = re.search(r'^- 중계기 주소:\s*`?(https://[^\s`]+)', context_section('KRX 중계기'), re.M)
    day = {'issue': issue_date, 'api': 'https://api.hyperliquid.xyz/info', 'relay': rm.group(1).rstrip('/') if rm else None, 't_prev': t_prev, 't_snap': t_snap,
           't_open': t_open, 't_close': t_close, 't_night': t_night, 'ent': [e for e in ents if e['prev']],
           'sess': {'open': sess['open_hm'], 'close': sess['close_hm'], 'prev_close': psess['close_hm'], 'why': sess['why']}}   # 화면 눈금, 제목(2026-11-19 수능일)
    V['DAY_DATA'] = json.dumps(day, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')

    def sgn(p): return ('+' if p > 0 else '−' if p < 0 else '') + '%.2f%%' % abs(p)
    def tile(e):
        p = e['path'][-1][1] if e['path'] else None
        v = '—' if p is None else (('≈' if e['approx'] else '') + num(round(e['prev'] * (1 + p / 100) / (e['tick'] or 1)) * (e['tick'] or 1), 0))
        b = ''
        if p is not None and e['lo'] is not None:
            w = '아래' if p < e['lo'] else ('위' if p > e['hi'] else '안')
            b = '<span class="b %s">예측 %s</span>' % ({'아래': 'lo', '위': 'hi', '안': 'in'}[w], w)
        return '<button type="button" role="tab" aria-selected="%s"><span class="n">%s</span><span class="v num">%s</span><span class="c num %s">%s</span>%s</button>' % (
            'true' if e['key'] == 'KOSPI' else 'false', esc(e['name']), v, cls(p) if p is not None else 'na', pct_str(p), b)
    V['LIVE_TILES'] = ''.join(tile(e) for e in day['ent'])
    V['CONCL'] = ''.join('<li>%s</li>' % esc_keep(t.get('h')) for t in tl[:3])
    V['OPEN_RANGE5'] = ('%s ~ %s<small>%s ~ %s</small>' % (num(low, 0), num(high, 0), sgn((low / kospi_close - 1) * 100), sgn((high / kospi_close - 1) * 100))
                        if (low and high and kospi_close) else '구간 없음')

    # 코스피 20거래일 — 종가 선 + 회차별 예상 구간 + 실제 시초가 + 오늘 구간
    kcl = {}
    for r in recs:
        try: kcl[prev_business_day(date.fromisoformat(r['date']))] = r['prev_close']
        except Exception: pass
    if kospi_close: kcl[pday] = kospi_close
    rec_by = {r.get('date'): r for r in recs}
    days20 = sorted(x for x in kcl if x <= pday)[-20:]
    slots = days20 + [d]
    tips = []
    if len(days20) >= 2:
        W, H, L, R, T, B = 360, 210, 40, 46, 14, 24
        vals = [kcl[x] for x in days20]
        for x in slots:
            r = rec_by.get(x.isoformat())
            if r and r.get('low') is not None: vals += [r['low'], r['high']] + ([r['actual_open']] if r.get('actual_open') else [])
        if low and high: vals += [low, high]
        span = max(vals) - min(vals); raw = span / 4; mag = 10 ** math.floor(math.log10(raw or 1))
        stp = min(sv * mag for sv in (1, 2, 2.5, 5, 10) if sv * mag >= raw)
        y0, y1 = math.floor(min(vals) / stp) * stp, math.ceil(max(vals) / stp) * stp
        X = lambda i: L + i * (W - L - R) / (len(slots) - 1)
        Y = lambda v: T + (y1 - v) / (y1 - y0) * (H - T - B)
        o = ['<svg viewBox="0 0 %d %d" class="viz" role="img" aria-label="코스피 최근 %d거래일 종가와 회차별 예상 구간, 실제 시초가">' % (W, H, len(days20))]
        g = y0
        while g <= y1 + 1e-9:
            o.append('<line x1="%d" x2="%d" y1="%.1f" y2="%.1f" class="grid"/><text x="%d" y="%.1f" class="tick" text-anchor="end">%s</text>' % (L, W - R + 8, Y(g), Y(g), L - 6, Y(g) + 3.5, num(g, 0)))
            g += stp
        for i, x in enumerate(slots):
            r = rec_by.get(x.isoformat())
            lo_, hi_ = (r['low'], r['high']) if (r and r.get('low') is not None) else ((low, high) if x == d else (None, None))
            if lo_ is None: continue
            o.append('<rect x="%.1f" y="%.1f" width="7" height="%.1f" rx="2" class="%s"/>' % (X(i) - 3.5, Y(hi_), max(2, Y(lo_) - Y(hi_)), 'bandnow' if x == d else 'band'))
        o.append('<polyline points="%s" class="ln"/>' % ' '.join('%.1f,%.1f' % (X(i), Y(kcl[x])) for i, x in enumerate(days20)))
        for i, x in enumerate(slots):
            r = rec_by.get(x.isoformat())
            if r and r.get('actual_open') is not None:
                o.append('<circle cx="%.1f" cy="%.1f" r="4" class="%s"/>' % (X(i), Y(r['actual_open']), 'din' if r.get('in_range') else 'dout'))
            tp = {'x': round(X(i), 1), 't': md(x.isoformat())}
            if x in kcl and x <= pday: tp['c'] = num(kcl[x], 2)
            if r and r.get('low') is not None:
                tp.update(b='%s~%s' % (num(r['low'], 0), num(r['high'], 0)), o=num(r['actual_open'], 2) if r.get('actual_open') else '—',
                          v='적중' if r.get('in_range') else '구간 밖')
            if x == d and low and high: tp.update(b='%s~%s' % (num(low, 0), num(high, 0)), v='오늘 전망')
            tips.append(tp)
        if low and high:
            o.append('<text x="%.1f" y="%.1f" class="lab strong">오늘</text>' % (X(len(slots) - 1) + 7, Y((low + high) / 2) + 4))
        for i in sorted({0, len(days20) // 2, len(days20) - 1}):
            o.append('<text x="%.1f" y="%d" class="tick" text-anchor="middle">%s</text>' % (X(i), H - 6, md(days20[i].isoformat())))
        o.append('<line class="xh" x1="0" x2="0" y1="%d" y2="%d"/></svg>' % (T, H - B))
        V['K20_CHART'] = ''.join(o)
    else:
        V['K20_CHART'] = ''
    V['K20_TIPS'] = esc(json.dumps(tips, ensure_ascii=False)).replace("'", '&#x27;')
    V['K20_HEAD'] = ('%s <b class="%s">%s</b>' % (num(kospi_close, 2), cls(pct.get('KOSPI')), pct_str(pct.get('KOSPI')))) if kospi_close else '—'
    l10 = scored[-10:]
    V['K20_CAP'] = ('최근 %d회 구간 안 %d' % (len(l10), sum(1 for r in l10 if r['in_range']))) if l10 else '채점 기록 없음'

    def mlabel(k):
        return {'K200N': 'K200 야간', 'SOX': 'SOX', 'EWY': 'EWY'}.get(k) or names[k][0]
    def mtile(k, label):
        c, q = close.get(k), pct.get(k)
        sub = ('<small>%s</small>' % esc((prices.get(k) or {}).get('asof') or '')) if k == 'K200N' and (prices.get(k) or {}).get('asof') else ''
        return '<div class="t5"><div class="t5n">%s%s</div><div class="t5v num">%s</div><div class="t5c num %s">%s</div></div>' % (
            esc(label), sub, num(c, DECIMALS.get(k, 2)) if c is not None else '—', cls(q) if c is not None else 'na', pct_str(q) if c is not None else '미확보')
    V['MKT_TILES'] = ''.join(mtile(k, mlabel(k)) for k in MARKET_ORDER)
    hw_txt = ' · '.join('%s ±%.2f%%' % (names[c][0], float(hws.get(c, 1.5))) for c in STOCK_KEYS)
    V['STOCK_NOTE'] = ('종목 예측 구간 = 야간선물과 해외 24시간 추종가(%s)의 평균 ± 최근 오차 80%% 범위(%s). 해외 추종가는 해외 코인거래소의 한국 종목 무기한선물 가격이라 실제 체결가와 다릅니다.' % (
        signals['perp_asof'] or '미확보', hw_txt)) + ('' if pitems else ' 오늘은 추종가를 받지 못해 야간선물만으로 구간을 잡았습니다.')
    mws = [(c, stock_fc[c]['monday_widen_pct']) for c in STOCK_KEYS if 'monday_widen_pct' in (stock_fc.get(c) or {})]
    if mws:
        V['STOCK_NOTE'] += ' 월요일이라 야간선물이 끝난 토 06:00 뒤 추종가가 움직인 만큼 더 넓혔습니다(%s).' % ' · '.join('%s +%.2f%%p' % (names[c][0], w) for c, w in mws)

    # ----- 화면용 JSON (v6 앱이 읽는다. HTML 출력과 별개이고 게이트·글자수에는 영향이 없다) -----
    def plain(x): return html.unescape(re.sub(r'<[^>]+>', '', str(x or ''))).strip()
    k20_rows = []
    for x in slots:
        r = rec_by.get(x.isoformat()) or {}
        row = {'date': x.isoformat(), 'today': x == d, 'close': kcl.get(x) if (x in kcl and x <= pday) else None}
        lo_, hi_ = (r.get('low'), r.get('high')) if r.get('low') is not None else ((low, high) if x == d else (None, None))
        row.update(low=lo_, high=hi_, open=r.get('actual_open'), in_range=r.get('in_range'), verdict=r.get('verdict'))
        k20_rows.append(row)
    day6 = {'schema': 1, 'issue': issue_date, 'issue_no': V['ISSUE'], 'date_label': V['DATE_LABEL'],
            'forecast': {'low': low, 'high': high, 'prev_close': kospi_close, 'night': k200n_now,
                         'low_pct': None if not (low and kospi_close) else round((low / kospi_close - 1) * 100, 3),
                         'high_pct': None if not (high and kospi_close) else round((high / kospi_close - 1) * 100, 3)},
            'concl': [{'h': plain(t.get('h')), 'b': plain(t.get('b'))} for t in tl[:3]],
            'signals': {k: signals.get(k) for k in ('k200n_pct', 'k200n_asof', 'ewy_implied_pct', 'adr_implied_pct', 'es_pct', 'nq_pct', 'perp_asof')},
            'day': day, 'k20': {'rows': k20_rows, 'close': kospi_close, 'pct': pct.get('KOSPI'), 'cap': plain(V['K20_CAP'])},
            'market': [{'key': k, 'label': mlabel(k), 'close': close.get(k), 'pct': pct.get(k),
                        'asof': (prices.get(k) or {}).get('asof') if k == 'K200N' else ref_at.get(k)} for k in MARKET_ORDER],
            'issue_src': issue_src, 'post_note': post_note,
            'global_tag': plain(tags.get('global')), 'stock_note': V['STOCK_NOTE'],
            'brief_html': '', 'footer': {'sources': plain(src), 'data_note': plain(dn.get('lead'))}}

    # ----- 치환 -----
    need = set(re.findall(r'\{\{([A-Z_]+)\}\}', tpl))
    missing = sorted(need - set(V))
    if missing: fail('템플릿 자리를 채우지 못함: %s' % missing)
    out = tpl
    for k, v in V.items(): out = out.replace('{{%s}}' % k, v if v is not None else '')
    left = sorted(set(re.findall(r'\{\{([A-Z_]+)\}\}', out)))
    if left: fail('치환 뒤 남은 자리: %s' % left)
    brief_m = re.search(r'<div data-panel="brief">(.*?)</div><!--/brief-->', out, flags=re.S)   # 브리핑 탭 본문 그대로 — v6 앱이 같은 글을 보여 준다
    if brief_m: day6['brief_html'] = re.sub(r'<div class="bar">.*?</button>\s*</div>\s*</div>', '', brief_m.group(1), count=1, flags=re.S).strip()

    # ----- 사후 검증 -----
    body = re.sub(r'<(style|script).*?</\1>', '', out, flags=re.S)
    body = re.sub(r'<div data-panel="dash">.*?<!--/dash-->', '', body, flags=re.S)   # 대시보드는 스크립트가 만든 화면이라 글자수에서 뺀다
    body = re.sub(r'<svg.*?</svg>', '', body, flags=re.S)
    body = re.sub(r'<details class="news">.*?</details>', '', body, flags=re.S)   # 매체 제목 그대로라 금지 표현, 내부 용어, 글자수에서 뺀다
    body = re.sub(r'<div class="fwide (?:fsig num|fconf)">.*?</div>|<div class="sl">.*?</div>|<div class="pnw">.*?</div>|<div class="legend">.*?</div>', '', body, flags=re.S)  # 스크립트가 만든 문구는 글자수에서 뺀다
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
    for pat in load_internal_terms():
        n = plain.count(pat)
        if n: warn('내부 용어 "%s" %d회 — 절차 문서에서만 쓰는 말이다. 독자용 말로 바꿀 것 (게이트 무관)' % (pat, n))
    n = plain.count('당일')   # 시점어(D3+) — '금일'은 금지 표현 표에 있다. '당일 고가'처럼 우리 문장에도 쓰여 게이트에는 넣지 않는다
    if n: warn("'당일' %d회 — 기사 원문의 '당일'을 옮긴 것이면 날짜로 바꿀 것 (게이트 무관)" % n)
    for pat, lim in (('한 셈입니다', 2), ('반영했습니다', 3)):
        n = plain.count(pat)
        if n > lim: warn('"%s" %d회 (상한 %d)' % (pat, n, lim))

    if FAILS:
        for f in FAILS: print('FAIL', f)
        return 1
    if not check_only:
        os.makedirs('out', exist_ok=True)
        io.open(os.path.join('out', 'index.html'), 'w', encoding='utf-8', newline='').write(out)
        io.open(os.path.join('out', 'day.json'), 'w', encoding='utf-8', newline='\n').write(json.dumps(day6, ensure_ascii=False, separators=(',', ':')) + '\n')
        try:   # 데이터 누락 기록 — datacheck.py 가 최근 회차를 세어 자주 빠지는 필드와 다음 경로를 고른다
            from datacheck import missing_fields, append_entry
            miss = missing_fields(fill, signals, prev_business_day(d).isoformat())
            if signals['night_skipped']: miss = [m for m in miss if m != 'prices.K200N.close']   # 휴장 뒤는 세션이 없는 게 정상
            log = append_entry({'date': issue_date, 'relay': relay_state, 'missing': miss, 'relay_filled': relay_filled, 'mismatch': relay_diff})
            io.open(os.path.join('out', 'datalog.json'), 'w', encoding='utf-8', newline='\n').write(json.dumps(log, ensure_ascii=False, indent=1) + '\n')
            print('데이터 누락 %d건%s' % (len(miss), (' — ' + ', '.join(miss)) if miss else ''))
        except Exception as e:
            warn('datalog 기록 실패 — %s' % e)
        try:
            io.open(os.path.join('out', 'calibration.json'), 'w', encoding='utf-8', newline='\n').write(io.open('calibration.json', encoding='utf-8').read())
        except Exception:
            pass
    print('OK   out/index.html (%d bytes)' % len(out.encode('utf-8')))
    print('접힘 %d자 / 전체 %d자  %s' % (collapsed, full, 'OK' if collapsed <= 4000 else '*** 4,000자 초과'))
    print('전망 %s~%s (%s) · 야간선물 %s · EWY시사 %s · ADR시사 %s' % (
        num(low, 0) if low else '—', num(high, 0) if high else '—', V['OPEN_RANGE'].split('<br>')[-1].strip('()'),
        pct_str(signals['k200n_pct']), pct_str(signals['ewy_implied_pct']), pct_str(signals['adr_implied_pct'])))
    print(V['COVERAGE'])
    print('종목 예측 — ' + (' · '.join('%s %s~%s (중심 %+.2f%%, 반폭 %.2f%%%s)' % (c, num(v['low'], 0), num(v['high'], 0), v['center_pct'], v['half_width_pct'],
          ' — 월요일 +%.2f' % v['monday_widen_pct'] if 'monday_widen_pct' in v else '') for c, v in stock_fc.items()) or '없음')
          + ' · 추종가 %s' % (signals['perp_asof'] or '미확보'))

    # ----- state.json (이번 회차) -----
    if not check_only:
        closes = {'as_of': fill.get('closes_as_of') or (tags.get('domestic') or '').split(' ')[0],
                  'note': '다음 회차의 등락률 계산 기준이 되는 직전 영업일 종가'}
        for k in STATE_KEYS: closes[k] = close.get(k)
        state = {'schema': 2,
                 'note': '회차 간 인수인계 파일. render.py 가 매 회차 통째로 갱신한다. 아카이브 HTML 을 파싱하지 않기 위해 존재한다.',
                 'issue_date': issue_date,
                 'forecast': {'date': issue_date, 'low': low, 'high': high, 'prev_close': kospi_close,
                              'made_at': made_at.strftime('%Y-%m-%dT%H:%M+09:00') if d == made_at.date() else None,   # 실제로 만든 시각(재연이면 null)
                              'note': '다음 회차가 이 전망을 실제 시초가와 대조해 채점한다'},
                 'signals': signals,
                 'stock_forecast': {'date': issue_date, 'items': stock_fc,
                                    'note': '다음 회차가 삼전·하닉 실제 시초가로 채점한다 (score.py → calibration.json stock_records)'},
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
    if signals['k200n_pct'] is None and not signals['night_skipped']: hold.append('야간선물 미확보')
    if night_flags: hold.append('야간선물 대조 불일치(%s)' % '·'.join(night_flags))
    dv = as_num(dn.get('diverged'), 'data_note.diverged')
    if dv is None or dv > 2: hold.append('종가 대조 불일치 %s건' % ('미기재' if dv is None else int(dv)))
    if any(w.startswith('issue_date') for w in WARNS): hold.append('발행일이 오늘이 아님')
    print('GATE PASS' if not hold else 'GATE HOLD — ' + ' · '.join(hold))
    return 0

if __name__ == '__main__':
    sys.exit(main())
