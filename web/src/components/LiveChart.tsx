import { useEffect, useMemo, useRef, useState, useSyncExternalStore } from 'react'
import type { Bar, Pt } from '../types'
import { band, type Live } from '../lib/live'
import { arrow, dir, hm, money, nf, sg, tk } from '../lib/fmt'
import { Card, CardHead, Cap } from './ui/card'
import { cn } from '../lib/cn'

const W = 360, H = 236, L = 34, R = 58, T = 20, B = 22, PW = W - L - R
const BAND_CLS: Record<string, string> = { 안: 'bg-brand-soft text-brand', 아래: 'bg-dn/10 text-dn', 위: 'bg-up/10 text-up' }

export function LiveChart({ live }: { live: Live }) {
  const ver = useSyncExternalStore((fn) => live.subscribe(fn), () => live.version)
  const D = live.D
  const [sel, setSel] = useState(0)
  const [[zA, zB], setZ] = useState<[number, number]>([0, 1])
  const [tip, setTip] = useState<{ x: number; t: string; p: number } | null>(null)
  const svgRef = useRef<SVGSVGElement>(null)
  const drag = useRef<{ x: number; a: number; b: number } | null>(null)
  const e = D.ent[sel]

  const view = useMemo(() => {
    void ver
    const st = live.S[e.key], xo = L + PW * 0.45
    const X0 = (t: number) => t <= D.t_open ? L + Math.max(0, t - D.t_prev) / (D.t_open - D.t_prev) * (xo - L)
      : xo + (Math.min(t, D.t_close) - D.t_open) / (D.t_close - D.t_open) * (L + PW - xo)
    const X = (t: number) => L + ((X0(t) - L) / PW - zA) / (zB - zA) * PW
    const inX = (x: number) => x >= L - 0.5 && x <= L + PW + 0.5
    const pre = st.path
    let tail = live.tailPts(e) as (Bar | Pt)[]
    const ses = live.sessPts(e), last = live.lastPct(e)
    if (pre.length && tail.length) tail = [pre[pre.length - 1] as Pt, ...tail]
    const ys = [0, ...pre.map((p) => p[1]), ...tail.map((p) => p[1]), ...ses.map((p) => p[1])]
    if (e.lo != null && e.hi != null) ys.push(e.lo, e.hi)
    if (e.night != null) ys.push(e.night)
    let lo = Math.min(...ys) - 0.3, hi = Math.max(...ys) + 0.3
    const sp = hi - lo, step = sp > 12 ? 4 : sp > 8 ? 2 : sp > 4 ? 1 : 0.5
    lo = Math.floor(lo / step) * step; hi = Math.ceil(hi / step) * step
    const Y = (v: number) => T + (hi - v) / (hi - lo) * (H - T - B)
    const grid: number[] = []
    for (let g = lo; g <= hi + 1e-9; g += step) grid.push(g)
    const tips = ([...pre, ...tail.slice(1), ...ses] as (Bar | Pt)[]).map((p) => ({ x: X(p[0]), t: hm(p[0]), p: p[1] })).filter((b) => inX(b.x))
    return { X, Y, inX, pre, tail, ses, last, grid, tips, op: live.openPct(e) }
  }, [ver, sel, zA, zB, live, e, D])

  // 휠 확대(PC 마우스만) — 터치 화면은 스크롤을 건드리지 않는다
  useEffect(() => {
    const svg = svgRef.current
    if (!svg || !window.matchMedia('(pointer:fine)').matches) return
    const frac = (ev: MouseEvent) => {
      const r = svg.getBoundingClientRect()
      return Math.max(0, Math.min(1, ((ev.clientX - r.left) * W / r.width - L) / PW))
    }
    const onWheel = (ev: WheelEvent) => {
      ev.preventDefault()
      setZ(([a, b]) => {
        const f = frac(ev), c = a + f * (b - a), w = Math.max(0.08, Math.min(1, (b - a) * (ev.deltaY < 0 ? 0.8 : 1.25)))
        const na = Math.max(0, Math.min(1 - w, c - f * w))
        return [na, na + w]
      })
    }
    svg.addEventListener('wheel', onWheel, { passive: false })
    return () => svg.removeEventListener('wheel', onWheel)
  }, [])

  const { X, Y, inX, pre, tail, ses, last, grid, tips, op } = view
  const zoomed = zB - zA < 0.999
  const xo = X(D.t_open), xe = X(D.t_close)
  const col = last != null && last < 0 ? 'var(--dn)' : 'var(--up)'
  const poly = (pts: (Bar | Pt)[]) => pts.map((p) => X(p[0]).toFixed(1) + ',' + Y(p[1]).toFixed(1)).join(' ')
  const kx = live.useKrx(e), now = Date.now()
  const afterClose = kx && e.key !== 'KOSPI' && now > D.t_close + 6e4 && ses.length > 0

  const onMove = (ev: React.PointerEvent<SVGSVGElement>) => {
    const svg = svgRef.current!, r = svg.getBoundingClientRect()
    if (drag.current) {
      const d = (ev.clientX - drag.current.x) * W / r.width / PW * (drag.current.b - drag.current.a)
      const w = drag.current.b - drag.current.a, na = Math.max(0, Math.min(1 - w, drag.current.a - d))
      setZ([na, na + w]); return
    }
    const sx = (ev.clientX - r.left) * W / r.width
    let best = null as (typeof tips)[number] | null, dd = 1e9
    for (const t of tips) { const v = Math.abs(t.x - sx); if (v < dd) { dd = v; best = t } }
    setTip(best)
  }

  return (
    <Card aria-label="예측과 실시간">
      <CardHead title="예측 → 실시간" right={
        <span className="inline-flex items-center gap-1.5">
          <i className={cn('inline-block size-2 rounded-full', live.krxOK ? 'bg-[var(--ok)]' : live.liveOK ? 'bg-brand' : 'bg-tx3')} />
          {live.KRX && live.krxOK ? 'KRX' : live.liveOK ? (live.KRX ? 'KRX 연결 실패 · 추종가' : '추종가') : '07:45 값'}
        </span>
      } />
      <div role="tablist" className="mb-3 grid grid-cols-3 gap-2">
        {D.ent.map((x, i) => {
          const p = live.lastPct(x), o = live.openPct(x)
          const w = x.lo != null && p != null ? band(x, o != null ? o : p) : null
          return (
            <button key={x.key} role="tab" aria-selected={i === sel} onClick={() => setSel(i)}
              className={cn('rounded-2xl border p-3 text-left transition-colors', i === sel ? 'border-brand bg-brand-soft' : 'border-line bg-card2')}>
              <div className="text-[12px] font-semibold text-tx2">{x.name}</div>
              <div className="num mt-0.5 text-[17px] font-bold text-tx">{p == null ? '—' : (x.approx && !live.useKrx(x) ? '≈' : '') + nf(tk(x, x.prev * (1 + p / 100)), 0)}</div>
              <div className={cn('num text-[12px] font-semibold', dir(p))}>{p == null ? '미확보' : arrow(p) + sg(p)}</div>
              {w && <span className={cn('mt-1.5 inline-block rounded-full px-2 py-0.5 text-[11px] font-bold', BAND_CLS[w])}>{o != null ? '시가 ' : '예측 '}{w}</span>}
            </button>
          )
        })}
      </div>
      <div className="relative">
        <svg ref={svgRef} viewBox={`0 0 ${W} ${H}`} className="viz block w-full touch-pan-y select-none" role="img"
          aria-label={`${e.name}${e.lo != null && e.hi != null ? ` 예측 구간 ${sg(e.lo)} ~ ${sg(e.hi)}` : ''}${last != null ? `, 현재 ${sg(last)}` : ''}`}
          onPointerMove={onMove} onPointerLeave={() => setTip(null)} onDoubleClick={() => setZ([0, 1])}
          onPointerDown={(ev) => { if (ev.pointerType === 'mouse' && zoomed) { drag.current = { x: ev.clientX, a: zA, b: zB }; ev.currentTarget.setPointerCapture(ev.pointerId) } }}
          onPointerUp={() => { drag.current = null }}>
          <defs><clipPath id="dayClip"><rect x={L} y={T - 8} width={PW} height={H - T + 8 - B} /></clipPath></defs>
          <g clipPath="url(#dayClip)">
            <rect x={xo} y={T} width={Math.max(0, xe - xo)} height={H - T - B} rx={4} fill="var(--card2)" />
            {grid.map((g) => <line key={g} x1={L} x2={L + PW} y1={Y(g)} y2={Y(g)} stroke="var(--line)" strokeDasharray={Math.abs(g) < 1e-9 ? '3 3' : undefined} strokeWidth={Math.abs(g) < 1e-9 ? 1.2 : 1} />)}
            <line x1={X(D.t_night)} x2={X(D.t_night)} y1={T} y2={H - B} stroke="var(--line)" strokeDasharray="2 3" />
            {e.lo != null && e.hi != null && (() => {
              const x1 = X(D.t_snap), x2 = X(D.t_open + 18e5)
              return <g><rect x={x1} y={Y(e.hi)} width={x2 - x1} height={Math.max(2, Y(e.lo) - Y(e.hi))} rx={2} fill="var(--band)" stroke="var(--band-line)" strokeWidth={0.8} />
                <text x={(x1 + x2) / 2} y={Y(e.hi) - 4} textAnchor="middle" fontSize={9} fontWeight={700} fill="var(--tx2)">예측</text></g>
            })()}
            <line x1={xo} x2={xo} y1={T - 6} y2={H - B} stroke="var(--tx3)" strokeDasharray="2 2" />
            {pre.length > 1 && <polyline points={poly(pre)} fill="none" stroke="var(--tx3)" strokeWidth={1.4} />}
            {tail.length > 1 && <polyline points={poly(tail)} fill="none" stroke="var(--tx2)" strokeWidth={1.6} />}
            {e.night != null && (() => { const nx = X(D.t_night), ny = Y(e.night); return <g><path d={`M${nx} ${ny - 5}L${nx + 5} ${ny}L${nx} ${ny + 5}L${nx - 5} ${ny}Z`} fill="var(--brand)" />
              <text x={nx - 7} y={ny + 3.5} textAnchor="end" fontSize={9} fill="var(--tx2)">야간 {sg(e.night)}</text></g> })()}
            {ses.length > 0 ? (() => {
              const ep = ses[ses.length - 1]
              return <g>
                <polyline points={poly(ses)} fill="none" stroke={col} strokeWidth={2} strokeLinejoin="round" />
                {op != null && <circle cx={xo} cy={Y(op)} r={4.5} fill="var(--card)" stroke={col} strokeWidth={2} />}
                <circle cx={X(ep[0])} cy={Y(ep[1])} r={4} fill={col} />
                <text x={X(ep[0]) + 7} y={Y(ep[1]) + 3.5} fontSize={9} fontWeight={700} fill="var(--tx)">{sg(ep[1])}</text>
              </g>
            })() : <text x={(xo + L + PW) / 2} y={(T + H - B) / 2} textAnchor="middle" fontSize={11} fill="var(--tx3)">
              {live.isPast && !live.liveOK ? '장중 기록 없음' : '09:00 개장 후 실시간'}</text>}
            {tip && <line x1={tip.x} x2={tip.x} y1={T} y2={H - B} stroke="var(--tx3)" strokeWidth={0.8} />}
          </g>
          {grid.map((g) => <text key={g} x={L - 5} y={Y(g) + 3.5} textAnchor="end" fontSize={9} fill="var(--tx3)">{Math.abs(g) < 1e-9 ? '0' : (g > 0 ? '+' : '') + g}</text>)}
          <text x={xo - 4} y={T - 8} textAnchor="end" fontSize={9} fill="var(--tx3)">장외</text>
          <text x={xo + 4} y={T - 8} fontSize={9} fill="var(--tx3)">장중</text>
          {([[D.t_prev, '15:30'], [D.t_night, '05:00'], [D.t_open, '09:00'], [D.t_open + 108e5, '12:00'], [D.t_close, '15:30']] as [number, string][])
            .filter(([t]) => inX(X(t))).map(([t, s]) => <text key={s + t} x={X(t)} y={H - 6} textAnchor="middle" fontSize={9} fill="var(--tx3)">{s}</text>)}
          {zoomed && <text x={L + PW} y={T - 8} textAnchor="end" fontSize={9} fill="var(--tx3)">더블클릭: 원래대로</text>}
        </svg>
        {tip && (
          <div className="pointer-events-none absolute -top-1.5 -translate-x-1/2 -translate-y-full whitespace-nowrap rounded-xl bg-tx px-2.5 py-1.5 text-[12px] leading-snug text-bg"
            style={{ left: `${Math.max(64, Math.min(W - 64, tip.x)) / W * 100}%` }}>
            <b>{tip.t}</b><br />{sg(tip.p)} · {money(e, e.prev * (1 + tip.p / 100))}
          </div>
        )}
      </div>
      <p className="mt-3 text-[14px] leading-relaxed text-tx2">
        {e.prev_label} 종가 <b className="num text-tx">{nf(e.prev, e.dec || 0)}</b>
        {e.lo != null && e.hi != null && e.lo_v != null && e.hi_v != null && <> · 예측 <b className="num text-tx">{nf(e.lo_v, 0)} ~ {nf(e.hi_v, 0)}</b> ({sg(e.lo)} ~ {sg(e.hi)})</>}
        {op != null && e.lo != null && <> · 시가{kx ? '' : '(추종가)'} <b className="num text-tx">{sg(op)}</b> → 구간 <b className="text-tx">{band(e, op)}</b></>}
        {op == null && last != null && e.lo != null && <> · {kx ? '지금(NXT)' : live.liveOK ? '지금 추정' : '07:45 추정'} <b className="num text-tx">{sg(last)}</b> → 구간 {band(e, last)}</>}
        {e.approx && !kx && ' · 코스피200 추종가 기준이라 지수와 차이가 있습니다'}
        {afterClose && ' · 종가는 KRX 기준입니다(15:40 이후 NXT 애프터마켓 가격은 반영하지 않음)'}
      </p>
      <Cap>
        왼쪽 — 전일 15:30 ~ 09:00 해외 24시간 추종가 · 노란 막대 — 07:45 예측 구간 · 오른쪽 — 09:00 ~ 15:30 장중(KRX 연결 시 실제 시세, 아니면 추종가) ·
        PC 에서는 마우스 휠로 확대, 드래그로 이동, 더블클릭으로 원래대로.
      </Cap>
    </Card>
  )
}
