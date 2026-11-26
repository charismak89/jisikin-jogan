// 첫 카드(시험 화면, 2026-11-26). 앤트위키 홈 첫 카드처럼 시간대마다 문구, 배경, 차트가 바뀐다.
// 앤트위키에 없는 것: 07:45 예측 구간 띠, 시가 채점, 야간선물 마감(06:00) 뒤 움직임, 주말 추종가.
import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import type { DayData, Ent, Pt } from '../types'
import type { Live } from '../lib/live'
import { band } from '../lib/live'
import { arrow, dir, hm, md, nf, sg, tk } from '../lib/fmt'
import { dayLabel, frame, inMin, minsTo, type Frame, type Phase } from './clock'
import type { NightFeed } from './night'

type View = 'session' | 'overnight' | 'proxy'
type Sky = 'dawn' | 'day' | 'dusk' | 'night'
interface Mark { t: number; label: string }
interface Model {
  sky: Sky; status: string; dot: 'live' | 'calm' | 'night'
  label: string; big: string; bigDir: number | null; level?: string
  note?: string | null; foot?: string | null
  lines: Pt[]; x0: number; x1: number; band?: { lo: number; hi: number; from: number; to?: number } | null
  marks: Mark[]; pin?: { t: number; p: number; label: string } | null
  stocks: { name: string; p: number | null; px: string | null; tag?: string | null }[]
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
const px = (e: Ent, p: number | null, base?: number) => (p == null ? null : (e.approx ? '≈' : '') + nf(tk(e, (base ?? e.prev) * (1 + p / 100)), 0) + (e.unit || ''))

function build(view: View, ph: Phase, F: Frame, data: DayData, live: Live, feed: NightFeed | null, now: number): Model {
  const D = data.day, K = D.ent.find((e) => e.key === KEY)!, stocks = D.ent.filter((e) => e.key !== KEY)
  const S = D.sess ?? { open: '09:00', close: '15:30', prev_close: '15:30', why: null }
  const status = {
    pre: `${S.open} 개장까지 ${inMin(minsTo(D.t_open, now))}${S.why ? ` · ${S.why}` : ''}`,
    live: `정규장 · ${S.close}까지`,
    closed: `오늘 정규장 마감 · 야간선물 ${inMin(minsTo(F.nightStart, now))} 뒤 시작`,
    night: '야간 시간 · 06:00까지',
    dawn: now < F.nextBrief ? `야간선물 마감 · ${hm(F.nextBrief)} 전망 준비 중` : `${hm(F.nextBrief)} 전망 올리는 중`,
    weekend: `주말 · ${dayLabel(F.nextBrief)} ${hm(F.nextBrief)} 전망`,
    late: '오늘 전망 없음 · 발행 전이거나 휴장일',
  }[ph]
  // 주말과 회차 없는 날은 시계로 하늘을 정한다(18:00~06:00 밤)
  const hr = new Date(now + 9 * 3600e3).getUTCHours()
  const sky: Sky = ph === 'weekend' || ph === 'late' ? (hr >= 18 || hr < 6 ? 'night' : 'day') : SKY[ph]
  const dot = ph === 'live' ? 'live' : sky === 'night' ? 'night' : 'calm'
  const base = { sky, status, dot } as const

  if (view === 'overnight') {
    const f = data.forecast, s = data.signals, c = f.low_pct != null && f.high_pct != null ? (f.low_pct + f.high_pct) / 2 : null
    const lines = [...K.path, ...live.tailPts(K).map((b) => [b[0], b[1]] as Pt)]
    return { ...base,
      label: `${md(data.issue)} ${S.open} 코스피 시초가 전망`, big: c != null ? `${sg(c)} 안팎` : '전망 없음', bigDir: c,
      level: f.low != null && f.high != null ? `${nf(f.low)} ~ ${nf(f.high)}` : undefined,
      note: s.k200n_pct != null ? `야간선물 ${sg(s.k200n_pct)}${s.k200n_asof ? ` · ${s.k200n_asof} 마감` : ''}` : '야간선물 미확보',
      foot: data.post_note?.text ?? null,
      lines, x0: D.t_prev, x1: D.t_open,
      band: K.lo != null && K.hi != null ? { lo: K.lo, hi: K.hi, from: D.t_open - (D.t_open - D.t_prev) * 0.06 } : null,
      marks: [{ t: D.t_prev, label: `${S.prev_close} 마감` }, { t: D.t_night, label: `야간 ${hm(D.t_night)}` }, { t: D.t_open, label: `${S.open} 개장` }],
      pin: K.night != null ? { t: D.t_night, p: K.night, label: '야간선물' } : null,
      stocks: stocks.map((e) => ({ name: e.name, p: e.lo != null && e.hi != null ? (e.lo + e.hi) / 2 : null, px: e.lo_v != null && e.hi_v != null ? `${nf(e.lo_v)}~${nf(e.hi_v)}` : null, tag: '전망' })),
      fresh: `${data.signals.perp_asof ?? '07:45'} 회차`,
    }
  }
  if (view === 'session') {
    const p = live.preOpen(K) ? null : live.lastPct(K), o = live.openPct(K), krx = live.useKrx(K)
    const done = now >= D.t_close
    return { ...base,
      label: done ? `코스피 · ${md(data.issue)} 마감` : '코스피 · 실시간', big: p == null ? '—' : sg(p), bigDir: p,
      level: p == null ? undefined : (krx ? '' : '≈') + nf(K.prev * (1 + p / 100), 2),
      note: o != null && K.lo != null ? `시가 ${sg(o)} · 07:45 전망 구간 ${band(K, o)}` : `07:45 전망 ${K.lo != null && K.hi != null ? `${sg(K.lo)} ~ ${sg(K.hi)}` : '없음'}`,
      foot: krx ? null : '토스 시세 연결 전 · 해외 추종가로 대신 그림',
      lines: live.sessPts(K).map((b) => [b[0], b[1]] as Pt), x0: D.t_open, x1: D.t_close,
      band: K.lo != null && K.hi != null ? { lo: K.lo, hi: K.hi, from: D.t_open, to: D.t_open + (D.t_close - D.t_open) * 0.1 } : null,
      marks: [{ t: D.t_open, label: `${S.open} 개장` }, { t: D.t_open + 3 * 3600e3, label: '정오' }, { t: D.t_close, label: `${S.close} 마감` }],
      pin: o != null ? { t: D.t_open + 6e4, p: o, label: '시가' } : null,
      stocks: stocks.map((e) => { const q = live.lastPct(e); return { name: e.name, p: q, px: px(e, q), tag: live.useKrx(e) ? null : '추종가' } }),
      fresh: done ? null : krx ? '15초마다' : null,
    }
  }
  // proxy — 발행일 마감 대비 밤 추종가
  const st = feed?.S[KEY], q = st?.last ?? null
  const kClose = closePct(live, K)
  const x1 = ph === 'night' || ph === 'closed' ? F.nightEnd : Math.max(now, F.nightEnd)
  const post = feed && (ph === 'dawn' || ph === 'weekend' || ph === 'late') ? (() => { const a = feed.at(KEY, F.nightEnd); return a != null && q != null ? q - a : null })() : null
  return { ...base,
    label: `코스피200 추종가 · ${md(data.issue)} ${S.close} 대비`, big: q == null ? (feed?.ok === false ? '미확보' : '—') : sg(q), bigDir: q,
    level: q != null && kClose != null ? '≈' + nf(K.prev * (1 + kClose / 100) * (1 + q / 100), 2) : undefined,
    note: post != null ? `야간선물 마감(${now - F.nightEnd > 864e5 / 2 ? dayLabel(F.nightEnd) + ' ' : ''}${hm(F.nightEnd)}) 뒤 ${sg(post)}` : '야간선물 아님 · 해외 24시간 추종가',
    foot: ph === 'night' ? '06:00 마감 대조 평균 0.36%p 차이(29회). 내일 07:45 전망에서 실제 야간선물로 바꿔 씁니다' : null,
    lines: st?.pts ?? [], x0: F.base, x1,
    band: null,
    marks: [{ t: F.base, label: `${S.close} 마감` }, { t: F.nightStart, label: '야간 개장' }, { t: F.usOpen, label: `미국장 ${hm(F.usOpen)}` }, { t: F.nightEnd, label: '야간 마감' },
      ...(x1 > F.nightEnd + 3600e3 ? [{ t: x1, label: '지금' }] : [])],
    pin: null,
    stocks: stocks.map((e) => { const v = feed?.S[e.key].last ?? null, c = closePct(live, e); return { name: e.name, p: v, px: c != null ? px(e, v, e.prev * (1 + c / 100)) : null, tag: '추종가' } }),
    fresh: st?.lastT ? `${hm(st.lastT)} 기준` : null,
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
  const M = build(view, ph, F, data, live, feed, now)
  const name = (v: View) => (v === 'overnight' ? '밤사이' : v === 'proxy' ? '밤 추종가' : ph === 'live' ? '코스피' : '낮 코스피')
  const otherLabel = alt ? name(flip ? primary : alt) : ''

  return (
    <section aria-label="지금 시장" data-sky={M.sky} className="sky relative overflow-hidden rounded-3xl p-4 shadow-[var(--shadow)] sm:p-5">
      <div className="flex items-center justify-between gap-2">
        <div className="flex min-w-0 items-center gap-1.5 text-[13px] font-semibold text-tx2">
          <span aria-hidden className={`sky-dot sky-dot-${M.dot} size-2 shrink-0 rounded-full`} />
          <span className="truncate">{M.status}</span>
        </div>
        {alt && (
          <button type="button" onClick={() => setFlip((v) => !v)} aria-pressed={flip}
            className="shrink-0 rounded-full bg-card2 px-2.5 py-1 text-[12px] font-semibold text-tx2" aria-label={`${otherLabel} 보기`}>⇆ {otherLabel}</button>
        )}
      </div>

      <div className="mt-2 text-[12px] font-semibold text-tx3">{M.label}</div>
      <div className="flex flex-wrap items-baseline gap-x-2">
        <span className={`num text-[30px] font-extrabold leading-tight tracking-tight ${M.bigDir == null ? 'text-tx' : dir(M.bigDir)}`}>
          {M.bigDir != null && view !== 'overnight' && <span className="text-[18px]">{arrow(M.bigDir)}</span>}{M.big}
        </span>
        {M.level && <span className="num text-[15px] font-bold text-tx2">{M.level}</span>}
      </div>
      {M.note && <div className="text-[13px] font-semibold text-tx2">{M.note}</div>}

      <Chart M={M} now={now} />

      <ul className="mt-3 grid grid-cols-2 gap-2">
        {M.stocks.map((s) => (
          <li key={s.name} className="rounded-2xl bg-card2 px-3 py-2">
            <div className="flex items-center justify-between text-[12px] text-tx3"><span className="font-semibold text-tx2">{s.name}</span>{s.tag && <span>{s.tag}</span>}</div>
            <div className="flex items-baseline justify-between gap-1">
              <b className={`num text-[16px] ${dir(s.p)}`}>{s.p == null ? '—' : sg(s.p)}</b>
              {s.px && <span className="num truncate text-[12px] text-tx3">{s.px}</span>}
            </div>
          </li>
        ))}
      </ul>

      {M.foot && <p className="mt-2 text-[12px] leading-snug text-tx3">{M.foot}</p>}
      <div className="mt-3 flex items-center justify-between gap-2">
        <span className="text-[11px] text-tx3">{M.fresh ?? ''}</span>
        <button type="button" onClick={onBrief} className="rounded-full bg-card px-3 py-1.5 text-[13px] font-bold text-tx shadow-[var(--shadow)]">브리핑 보기 ›</button>
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
  const col = last ? (last[1] < 0 ? 'var(--dn)' : 'var(--up)') : 'var(--tx3)'
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
            fill="var(--band)" stroke="var(--band-line)" strokeWidth={1} rx={3} opacity={0.9} />
        )}
        {M.band && M.band.to && <text x={X(M.band.to) + 4} y={Y(M.band.hi) + 10} fontSize={11} fill="var(--tx3)">07:45 전망 구간</text>}
        <line x1={0} x2={W - 8} y1={Y(0)} y2={Y(0)} stroke="var(--tx3)" strokeOpacity={0.5} strokeDasharray="3 3" />
        <text x={W - 10} y={Y(0) - 4} fontSize={11} fill="var(--tx3)" textAnchor="end">기준 0%</text>
        {ticks.slice(1, -1).map((t) => <line key={t.t} x1={t.x} x2={t.x} y1={T} y2={H - B} stroke="var(--line)" />)}
        {path && <path d={path + `L${X(last[0]).toFixed(1)} ${Y(lo)}L${X(pts[0][0]).toFixed(1)} ${Y(lo)}Z`} fill={col} opacity={0.08} />}
        {path && <path d={path} fill="none" stroke={col} strokeWidth={2} strokeLinejoin="round" />}
        {mx && mn && mx !== mn && (<>
          <text x={Math.min(Math.max(X(mx[0]), 30), W - 40)} y={Y(mx[1]) - 5} fontSize={11} fill="var(--tx3)" textAnchor="middle">최고 {lbl(mx[1])}</text>
          <text x={Math.min(Math.max(X(mn[0]), 30), W - 40)} y={Y(mn[1]) + 13} fontSize={11} fill="var(--tx3)" textAnchor="middle">최저 {lbl(mn[1])}</text>
        </>)}
        {M.pin && <g><circle cx={X(M.pin.t)} cy={Y(M.pin.p)} r={4} fill="var(--brand)" stroke="var(--card)" strokeWidth={2} /></g>}
        {last && <circle className="sky-pulse" cx={X(last[0])} cy={Y(last[1])} r={4} fill={col} />}
        {!pts.length && <text x={(W - 8) / 2} y={H / 2} fontSize={13} fill="var(--tx3)" textAnchor="middle">시세를 받는 중</text>}
      </svg>
      <div className="relative mt-1 h-[2px] rounded bg-line" style={{ width: W - 8 }}>
        <div className="absolute inset-y-0 left-0 rounded bg-tx3" style={{ width: `${prog * 100}%` }} />
        {ticks.map((t) => <span key={t.t} className="absolute top-1/2 size-1.5 -translate-x-1/2 -translate-y-1/2 rounded-full bg-tx3" style={{ left: t.x }} />)}
        {now > M.x0 && now < M.x1 && <span className="absolute top-1/2 size-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-card bg-tx" style={{ left: nowX }} />}
      </div>
      <div className="relative mt-1 h-4 text-[11px] text-tx3" style={{ width: W - 8 }}>
        {shown.map((t, i) => (
          <span key={t.t} className={`absolute whitespace-nowrap ${i === 0 && t.x < 30 ? '' : t.x > W - 60 ? '-translate-x-full' : '-translate-x-1/2'}`} style={{ left: t.x }}>{t.label}</span>
        ))}
      </div>
    </div>
  )
}
