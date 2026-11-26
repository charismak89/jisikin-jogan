// 첫 카드(시험 화면, 2026-11-26). 앤트위키 홈 첫 카드처럼 시간대마다 문구, 배경, 차트가 바뀐다.
// 앤트위키에 없는 것: 07:45 예측 구간 띠, 시가 채점, 야간선물 마감(06:00) 뒤 움직임, 주말 추종가.
import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import type { DayData, Ent, Pt } from '../types'
import type { Live } from '../lib/live'
import { band } from '../lib/live'
import { arrow, hm, md, nf, sg, tk } from '../lib/fmt'
import { dayLabel, frame, inMin, minsTo, type Frame, type Phase } from './clock'
import type { NightFeed } from './night'
import { tone } from './lib/tone'
import { Button } from './components/ui/button'

type View = 'session' | 'overnight' | 'proxy'
type Sky = 'dawn' | 'day' | 'dusk' | 'night'
interface Mark { t: number; label: string }
interface Model {
  sky: Sky; status: string; dot: 'live' | 'calm' | 'night'
  label: string; big: string; bigDir: number | null; level?: string; badge?: string
  note?: string | null; foot?: string | null
  lines: Pt[]; x0: number; x1: number; band?: { lo: number; hi: number; from: number; to?: number } | null
  marks: Mark[]; pin?: { t: number; p: number; label: string } | null
  tiles: { key: string; name: string; p: number | null; tag: string | null }[]
  fresh: string | null
}

const KEY = 'KOSPI'
const SKY: Record<Phase, Sky> = { pre: 'dawn', live: 'day', closed: 'dusk', night: 'night', dawn: 'dawn', weekend: 'dawn', late: 'day' }

function useNow(ms: number) {
  const [n, setN] = useState(() => Date.now())
  useEffect(() => { const id = window.setInterval(() => setN(Date.now()), ms); return () => window.clearInterval(id) }, [ms])
  return n
}
function useVer(src: { subscribe(fn: () => void): () => void } | null) {
  const [, set] = useState(0)
  useEffect(() => (src ? src.subscribe(() => set((v) => v + 1)) : undefined), [src])
}

/** 발행일 정규장 종가(%) — 토스 1분봉 마지막 값, 없으면 추종가 */
const closePct = (live: Live, e: Ent) => { const s = live.sessPts(e); return s.length ? s[s.length - 1][1] : null }

/** 종목 값 표시: 코스피는 지수(소수 2자리), 종목은 호가 단위 원. 추정치는 ≈ */
const lvl = (e: Ent, base: number, p: number, approx: boolean) =>
  (approx ? '≈' : '') + (e.key === KEY ? nf(base * (1 + p / 100), 2) : nf(tk(e, base * (1 + p / 100)), 0) + (e.unit || ''))

function build(view: View, ph: Phase, F: Frame, data: DayData, live: Live, feed: NightFeed | null, now: number, E: Ent): Model {
  const D = data.day, isK = E.key === KEY
  const S = D.sess ?? { open: '09:00', close: '15:30', prev_close: '15:30', why: null }
  // 중계기 /v1/night(한국투자증권 야간선물)가 이 발행일 밤 세션 값을 주는지
  const fu = feed?.fut
  const futOK = !!fu && fu.session === data.issue && (fu.state === 'live' || fu.state === 'closed') && fu.pts.length > 0 && fu.pct != null
    && (ph === 'night' || ph === 'dawn' || ph === 'closed')
  const status = {
    pre: `${S.open} 개장까지 ${inMin(minsTo(D.t_open, now))}${S.why ? ` · ${S.why}` : ''}`,
    live: `정규장 · ${S.close}까지`,
    closed: `오늘 정규장 마감 · 야간선물 ${inMin(minsTo(F.nightStart, now))} 뒤 시작`,
    night: futOK ? '야간선물 거래 중 · 06:00까지' : '밤 · 해외 추종가로 보는 중',
    dawn: now < F.nextBrief ? `야간선물 마감 · ${hm(F.nextBrief)} 전망 준비 중` : `${hm(F.nextBrief)} 전망 올리는 중`,
    weekend: `주말 · ${dayLabel(F.nextBrief)} ${hm(F.nextBrief)} 전망`,
    late: '오늘 전망 없음 · 발행 전이거나 휴장일',
  }[ph]
  // 주말과 회차 없는 날은 시계로 하늘을 정한다(18:00~06:00 밤)
  const hr = new Date(now + 9 * 3600e3).getUTCHours()
  const sky: Sky = ph === 'weekend' || ph === 'late' ? (hr >= 18 || hr < 6 ? 'night' : 'day') : SKY[ph]
  const dot = ph === 'live' ? 'live' : sky === 'night' ? 'night' : 'calm'
  // 코스피 전망 중심은 메인 화면(Hero)과 같은 forecast 값, 종목은 ent 구간
  const center = (e: Ent) => {
    const f = data.forecast
    if (e.key === KEY && f.low_pct != null && f.high_pct != null) return (f.low_pct + f.high_pct) / 2
    return e.lo != null && e.hi != null ? (e.lo + e.hi) / 2 : null
  }
  const tiles = (pick: (e: Ent) => number | null, tag: (e: Ent) => string | null) =>
    D.ent.map((e) => ({ key: e.key, name: e.name, p: pick(e), tag: tag(e) }))
  const base = { sky, status, dot } as const

  if (view === 'overnight') {
    const f = data.forecast, s = data.signals, c = center(E)
    return { ...base,
      label: `${md(data.issue)} ${S.open} ${E.name} 시초가 전망`, big: c != null ? `${sg(c)} 안팎` : '전망 없음', bigDir: c,
      level: isK ? (f.low != null && f.high != null ? `${nf(f.low)} ~ ${nf(f.high)}` : undefined)
        : E.lo_v != null && E.hi_v != null ? `${nf(E.lo_v)} ~ ${nf(E.hi_v)}${E.unit}` : undefined,
      note: isK ? (s.k200n_pct != null ? `야간선물 ${sg(s.k200n_pct)}${s.k200n_asof ? ` · ${s.k200n_asof} 마감` : ''}` : '야간선물 미확보')
        : `${E.prev_label} 종가 ${nf(E.prev)}${E.unit}`,
      foot: data.post_note?.text ?? null,
      lines: [...E.path, ...live.tailPts(E).map((b) => [b[0], b[1]] as Pt)], x0: D.t_prev, x1: D.t_open,
      band: E.lo != null && E.hi != null ? { lo: E.lo, hi: E.hi, from: D.t_open - (D.t_open - D.t_prev) * 0.06 } : null,
      marks: [{ t: D.t_prev, label: `${S.prev_close} 마감` }, { t: D.t_night, label: `야간 ${hm(D.t_night)}` }, { t: D.t_open, label: `${S.open} 개장` }],
      pin: E.night != null ? { t: D.t_night, p: E.night, label: '야간선물' } : null,
      tiles: tiles(center, () => null),
      fresh: `${data.signals.perp_asof ?? '07:45'} 회차`,
    }
  }
  if (view === 'session') {
    // 개장 전 '—' 는 코스피만(지수는 장 전 거래가 없다). 종목은 08:00 부터 NXT 실제가가 있어 그대로 보인다(live.ts preOpen).
    // 코스피 추정치(≈)는 토스 시세가 없을 때(!krx)뿐이다. 종목은 approx 가 아니다
    const p = live.preOpen(E) ? null : live.lastPct(E), o = live.openPct(E), krx = live.useKrx(E)
    const done = now >= D.t_close
    return { ...base,
      label: `${E.name} · ${done ? `${md(data.issue)} 마감` : '실시간'}`, big: p == null ? '—' : sg(p), bigDir: p,
      level: p == null ? undefined : lvl(E, E.prev, p, !krx),
      note: o != null && E.lo != null ? `시가 ${sg(o)} · 07:45 전망 구간 ${band(E, o)}` : `07:45 전망 ${E.lo != null && E.hi != null ? `${sg(E.lo)} ~ ${sg(E.hi)}` : '없음'}`,
      foot: krx ? null : '토스 시세 연결 전 · 해외 추종가로 대신 그림',
      lines: live.sessPts(E).map((b) => [b[0], b[1]] as Pt), x0: D.t_open, x1: D.t_close,
      band: E.lo != null && E.hi != null ? { lo: E.lo, hi: E.hi, from: D.t_open, to: D.t_open + (D.t_close - D.t_open) * 0.1 } : null,
      marks: [{ t: D.t_open, label: `${S.open} 개장` }, { t: D.t_open + 3 * 3600e3, label: '정오' }, { t: D.t_close, label: `${S.close} 마감` }],
      pin: o != null ? { t: D.t_open + 6e4, p: o, label: '시가' } : null,
      tiles: tiles((e) => (live.preOpen(e) ? null : live.lastPct(e)), (e) => (live.useKrx(e) ? null : '추종가')),
      fresh: done ? null : krx ? '15초마다' : null,
    }
  }
  // 코스피 + 야간선물(중계기 /v1/night, 이 발행일 밤 세션)이 있으면 실제 야간선물로 그린다. 주말과 회차 없는 날은 추종가(야간선물이 없는 시간까지 이어서 본다)
  const useFut = isK && futOK
  if (useFut && fu) {
    const x1 = F.nightEnd, done = fu.state === 'closed' && now >= F.nightEnd   // 밤 도중 closed(조기 종료 등)는 '06:00 마감'이라 쓰지 않는다
    const endLabel = (now - F.nightEnd > 864e5 / 2 ? dayLabel(F.nightEnd) + ' ' : '') + hm(F.nightEnd) + ' 마감'   // 월요일 새벽은 토 06:00 에 끝난 금요일 세션
    const postP = feed!.S[E.key].last, at6 = feed!.at(E.key, F.nightEnd)
    const post = done && postP != null && at6 != null ? postP - at6 : null
    return { ...base,
      label: done ? `코스피200 야간선물 · ${endLabel}` : `코스피200 야간선물 · 주간 종가 ${nf(fu.base as number, 2)} 대비`, badge: '야간선물',
      big: sg(fu.pct as number), bigDir: fu.pct, level: nf(fu.last as number, 2),
      note: post != null ? `마감 뒤 해외 추종가 ${sg(post)}p` : done ? `${endLabel}값` : fu.state === 'closed' ? '야간선물 거래가 끝났습니다' : `${fu.name} · 한국거래소 야간시장`,
      foot: ph === 'night' ? `${dayLabel(F.nextBrief)} 07:45 전망은 이 야간선물 마감값으로 시작합니다. 삼성전자, SK하이닉스는 야간시장이 없어 해외 추종가입니다` : null,
      lines: fu.pts, x0: F.nightStart, x1,
      band: null,
      marks: [{ t: F.nightStart, label: '18:00' }, { t: F.usOpen, label: `미국장 ${hm(F.usOpen)}` }, { t: F.nightEnd, label: '06:00' }],
      pin: null,
      tiles: tiles((e) => (e.key === KEY ? fu.pct : feed?.S[e.key].last ?? null), () => null),
      fresh: done ? endLabel : fu.asof ? `${hm(fu.asof)} 기준${fu.state === 'live' ? ' · 10초마다' : ''}` : null,
    }
  }
  // proxy — 발행일 마감 대비 밤 추종가
  const st = feed?.S[E.key], q = st?.last ?? null
  const waiting = isK && fu && fu.session === data.issue && fu.state === 'waiting' && ph === 'night'
  const cl = closePct(live, E)
  const x1 = ph === 'night' || ph === 'closed' ? F.nightEnd : Math.max(now, F.nightEnd)
  const post = feed && (ph === 'dawn' || ph === 'weekend' || ph === 'late') ? (() => { const a = feed.at(E.key, F.nightEnd); return a != null && q != null ? q - a : null })() : null
  return { ...base,
    label: `${isK ? '코스피200' : E.name} 추종가 · ${md(data.issue)} ${S.close} 대비`, badge: '추종가', big: q == null ? (feed?.ok === false ? '미확보' : '—') : sg(q), bigDir: q,
    level: q != null && cl != null ? lvl(E, E.prev * (1 + cl / 100), q, true) : undefined,
    note: post != null ? `야간선물 마감(${now - F.nightEnd > 864e5 / 2 ? dayLabel(F.nightEnd) + ' ' : ''}${hm(F.nightEnd)}) 뒤 ${sg(post)}p`
      : !isK ? `${E.name}는 야간시장이 없어 해외 24시간 추종가입니다` : waiting ? '야간선물 첫 체결 기다리는 중 · 그동안 해외 추종가' : '실제 야간선물 시세가 아닙니다',
    foot: ph === 'night' && isK ? `야간선물(18:00~06:00)과 06:00 마감 대조 평균 0.36%p 차이(29회). ${dayLabel(F.nextBrief)} 07:45 전망에는 실제 야간선물을 씁니다` : null,
    lines: st?.pts ?? [], x0: F.base, x1,
    band: null,
    marks: [{ t: F.base, label: `${S.close} 마감` }, { t: F.nightStart, label: '18:00' }, { t: F.usOpen, label: `미국장 ${hm(F.usOpen)}` }, { t: F.nightEnd, label: '06:00' },
      ...(x1 > F.nightEnd + 3600e3 ? [{ t: x1, label: '지금' }] : [])],
    pin: null,
    tiles: tiles((e) => (e.key === KEY && futOK && fu ? fu.pct : feed?.S[e.key].last ?? null), () => null),
    fresh: st?.lastT ? `${hm(st.lastT)} 기준${feed && feed.fails >= 3 ? ' · 지연' : ''}` : null,
  }
}

export function NowCard({ data, live, feed, onBrief }: { data: DayData; live: Live; feed: NightFeed | null; onBrief: () => void }) {
  const now = useNow(15e3)
  useVer(live); useVer(feed)
  const F = frame(data.day, now), ph = F.phase
  const primary: View = ph === 'pre' ? 'overnight' : ph === 'live' || ph === 'closed' ? 'session' : 'proxy'
  const alt: View | null = ph === 'pre' ? null : primary === 'session' ? 'overnight' : 'session'
  const [flip, setFlip] = useState(false)
  useEffect(() => setFlip(false), [ph])
  const view = flip && alt ? alt : primary
  // 아래 칸에서 고른 종목(코스피가 기본). 새로 고침하면 코스피로 돌아간다
  const [sel, setSel] = useState(KEY)
  const E = data.day.ent.find((e) => e.key === sel) ?? data.day.ent[0]
  const M = build(view, ph, F, data, live, feed, now, E)
  const name = (v: View) => (v === 'overnight' ? '밤사이' : v === 'proxy' ? '밤 추종가' : ph === 'live' ? '코스피' : '낮 코스피')
  const otherLabel = alt ? name(flip ? primary : alt) : ''

  return (
    <section aria-label="지금 시장" data-sky={M.sky} className="sky relative overflow-hidden rounded-lg p-4 shadow-xs ring-1 ring-line-2 sm:p-5">
      <div className="flex items-center justify-between gap-2">
        <div className="flex min-w-0 items-center gap-1.5 text-label2 font-semibold text-fg-2">
          <span aria-hidden className={`sky-dot sky-dot-${M.dot} size-2 shrink-0 rounded-full`} />
          <span className="truncate">{M.status}</span>
        </div>
        {alt && (
          <Button variant="assistive" size="small" onClick={() => setFlip((v) => !v)} aria-pressed={flip}
            className="shrink-0" aria-label={`${otherLabel} 보기`}>⇆ {otherLabel}</Button>
        )}
      </div>

      <div className="mt-2 text-caption1 font-semibold text-fg-2">{M.label}</div>
      <div className="flex flex-wrap items-baseline gap-x-2">
        <span className={`num text-title1 font-bold leading-tight tracking-tight ${M.bigDir == null ? 'text-fg' : tone(M.bigDir)}`}>
          {M.bigDir != null && view !== 'overnight' && <span className="text-headline1">{arrow(M.bigDir)}</span>}{M.big}
        </span>
        {M.level && <span className="num text-body2 font-bold text-fg-2">{M.level}</span>}
        {M.badge && <span className="rounded-full border border-line px-2 py-0.5 text-caption1 font-bold text-fg-2">{M.badge}</span>}
      </div>
      {M.note && <div className="text-label2 font-semibold text-fg-2">{M.note}</div>}

      <Chart M={M} now={now} />

      <div role="group" aria-label="차트 종목 고르기" className="mt-3 grid grid-cols-3 gap-1.5">
        {M.tiles.map((t) => (
          <button key={t.key} type="button" aria-pressed={t.key === E.key} onClick={() => setSel(t.key)}
            className={`min-w-0 rounded-md bg-card px-2.5 py-2 text-left ${t.key === E.key ? 'ring-2 ring-fg' : 'ring-1 ring-line-2'}`}>
            <div className="flex items-center justify-between gap-1 text-caption1"><span className="truncate font-semibold text-fg-2">{t.name}</span>{t.tag && <span className="shrink-0 text-caption1 text-fg-2">{t.tag}</span>}</div>
            <b className={`num block text-body1 ${tone(t.p)}`}>{t.p == null ? '—' : sg(t.p)}</b>
          </button>
        ))}
      </div>

      {M.foot && <p className="mt-2 text-caption1 leading-snug text-fg-2">{M.foot}</p>}
      <div className="mt-3 flex items-center justify-between gap-2">
        <span className="text-caption1 text-fg-2">{M.fresh ?? ''}</span>
        <Button variant="assistive" size="small" onClick={onBrief}>브리핑 보기 ›</Button>
      </div>
    </section>
  )
}

function useWidth() {
  const ref = useRef<HTMLDivElement>(null), [w, setW] = useState(320)
  useLayoutEffect(() => {
    const el = ref.current; if (!el) return
    const ro = new ResizeObserver(() => setW(el.clientWidth || 320)); ro.observe(el); setW(el.clientWidth || 320)
    return () => ro.disconnect()
  }, [])
  return [ref, w] as const
}

function Chart({ M, now }: { M: Model; now: number }) {
  const [ref, W] = useWidth()
  const H = 128, T = 18, B = 16
  const ys = [0, ...M.lines.map((p) => p[1]), ...(M.band ? [M.band.lo, M.band.hi] : []), ...(M.pin ? [M.pin.p] : [])]
  let lo = Math.min(...ys), hi = Math.max(...ys)
  const pad = Math.max(0.15, (hi - lo) * 0.12); lo -= pad; hi += pad
  const X = (t: number) => ((Math.min(Math.max(t, M.x0), M.x1) - M.x0) / (M.x1 - M.x0)) * (W - 8)
  const Y = (p: number) => T + (1 - (p - lo) / (hi - lo)) * (H - T - B)
  const pts = M.lines.filter((p) => p[0] >= M.x0 && p[0] <= M.x1)
  const path = pts.map((p, i) => `${i ? 'L' : 'M'}${X(p[0]).toFixed(1)} ${Y(p[1]).toFixed(1)}`).join('')
  const last = pts[pts.length - 1]
  const mx = pts.length ? pts.reduce((a, b) => (b[1] > a[1] ? b : a)) : null, mn = pts.length ? pts.reduce((a, b) => (b[1] < a[1] ? b : a)) : null
  const col = last ? (last[1] < 0 ? 'var(--mt-fin-down)' : 'var(--mt-fin-up)') : 'var(--mt-foreground-neutral-secondary)'
  const nowX = X(now), prog = Math.max(0, Math.min(1, (now - M.x0) / (M.x1 - M.x0)))
  // 눈금 글자는 64px 안에서 겹치면 앞의 것을 숨긴다(끝 눈금은 항상 보인다)
  const ticks = M.marks.filter((m) => m.t >= M.x0 && m.t <= M.x1).map((m) => ({ ...m, x: X(m.t) })).sort((a, b) => a.x - b.x)
  const shown: typeof ticks = []
  ticks.forEach((t, i) => { const prev = shown[shown.length - 1]; if (!prev || t.x - prev.x >= 64) shown.push(t); else if (i === ticks.length - 1) { shown.pop(); shown.push(t) } })
  const lbl = (v: number) => sg(v)
  return (
    <div ref={ref} className="mt-2">
      <svg className="viz block" width={W} height={H} role="img" aria-label={`${M.label} ${M.big}`}>
        {M.band && (
          <rect x={X(M.band.from)} width={Math.max(4, X(M.band.to ?? M.x1) - X(M.band.from))} y={Y(M.band.hi)} height={Math.max(2, Y(M.band.lo) - Y(M.band.hi))}
            className="fill-band stroke-band-line" strokeWidth={1} rx={3} />
        )}
        {M.band && M.band.to && (() => { const above = Y(M.band.hi) - 5 >= 11; return <text x={X(M.band.from)} y={above ? Y(M.band.hi) - 5 : Y(M.band.lo) + 13} fontSize={12} fill="var(--mt-foreground-neutral-secondary)" stroke="var(--mt-surface-elevated-primary)" strokeWidth={3} paintOrder="stroke">07:45 전망 구간</text> })()}
        <line x1={0} x2={W - 8} y1={Y(0)} y2={Y(0)} stroke="var(--mt-foreground-neutral-secondary)" strokeOpacity={0.5} strokeDasharray="3 3" />
        {/* 기준선 글자: 전망 구간이 오른쪽 끝까지 닿으면(개장 전) 왼쪽에 둔다 */}
        {M.band && !M.band.to ? <text x={2} y={Y(0) - 4} fontSize={12} fill="var(--mt-foreground-neutral-secondary)" stroke="var(--mt-surface-elevated-primary)" strokeWidth={3} paintOrder="stroke">기준 0%</text>
          : <text x={W - 10} y={Y(0) - 4} fontSize={12} fill="var(--mt-foreground-neutral-secondary)" textAnchor="end" stroke="var(--mt-surface-elevated-primary)" strokeWidth={3} paintOrder="stroke">기준 0%</text>}
        {ticks.slice(1, -1).map((t, i) => <line key={i} x1={t.x} x2={t.x} y1={T} y2={H - B} stroke="var(--mt-line-neutral-primary)" />)}
        {path && <path d={path + `L${X(last[0]).toFixed(1)} ${Y(lo)}L${X(pts[0][0]).toFixed(1)} ${Y(lo)}Z`} fill={col} opacity={0.08} />}
        {path && <path d={path} fill="none" stroke={col} strokeWidth={2} strokeLinejoin="round" />}
        {mx && mn && mx !== mn && (<>
          <text x={Math.min(Math.max(X(mx[0]), 42), Math.max(42, W - 50))} y={Y(mx[1]) - 5} fontSize={12} fill="var(--mt-foreground-neutral-secondary)" textAnchor="middle" stroke="var(--mt-surface-elevated-primary)" strokeWidth={3} paintOrder="stroke">최고 {lbl(mx[1])}</text>
          <text x={Math.min(Math.max(X(mn[0]), 42), Math.max(42, W - 50))} y={Y(mn[1]) + 13} fontSize={12} fill="var(--mt-foreground-neutral-secondary)" textAnchor="middle" stroke="var(--mt-surface-elevated-primary)" strokeWidth={3} paintOrder="stroke">최저 {lbl(mn[1])}</text>
        </>)}
        {M.pin && <g><circle cx={X(M.pin.t)} cy={Y(M.pin.p)} r={4} fill="var(--mt-foreground-brand-primary)" stroke="var(--mt-surface-elevated-primary)" strokeWidth={2} /></g>}
        {last && <circle className="sky-pulse" cx={X(last[0])} cy={Y(last[1])} r={4} fill={col} />}
        {!pts.length && <text x={(W - 8) / 2} y={H / 2} fontSize={13} fill="var(--mt-foreground-neutral-secondary)" textAnchor="middle">시세를 받는 중</text>}
      </svg>
      <div className="relative mt-1 h-[2px] rounded bg-line" style={{ width: W - 8 }}>
        <div className="absolute inset-y-0 left-0 rounded bg-fg-3" style={{ width: `${prog * 100}%` }} />
        {ticks.map((t, i) => <span key={i} className="absolute top-1/2 size-1.5 -translate-x-1/2 -translate-y-1/2 rounded-full bg-fg-3" style={{ left: t.x }} />)}
        {now > M.x0 && now < M.x1 && <span className="absolute top-1/2 size-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-card bg-inverse" style={{ left: nowX }} />}
      </div>
      <div className="relative mt-1 h-4 text-caption1 text-fg-2" style={{ width: W - 8 }}>
        {shown.map((t, i) => (
          <span key={i} className={`absolute whitespace-nowrap ${i === 0 && t.x < 30 ? '' : t.x > W - 60 ? '-translate-x-full' : '-translate-x-1/2'}`} style={{ left: t.x }}>{t.label}</span>
        ))}
      </div>
    </div>
  )
}
