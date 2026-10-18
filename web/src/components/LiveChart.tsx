import { useEffect, useMemo, useRef, useState, useSyncExternalStore } from 'react'
import type { Bar, Pt } from '../types'
import { band, type Live } from '../lib/live'
import { arrow, dir, hm, money, nf, sg, tk } from '../lib/fmt'
import { Card, CardHead, Cap } from './ui/card'
import { cn } from '../lib/cn'

const L = 34, R = 58, T = 20, B = 22
// 차트 좌표계(viewBox). 평소 360×236. 크게 보기에서는 PC(720px~)는 가로로 넓게, 모바일은 세로로 길게 다시 그린다 — 글자 크기는 그대로 두고 그릴 칸을 늘린다
const dimsOf = (exp: boolean, vw: number) => (!exp ? { W: 360, H: 236 } : vw >= 720 ? { W: 760, H: 360 } : { W: 360, H: 460 })
const ExpandIcon = ({ open }: { open: boolean }) => (
  <svg viewBox="0 0 24 24" width={16} height={16} fill="none" stroke="currentColor" strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round" aria-hidden>
    {open ? <><path d="M4 14h6v6" /><path d="M20 10h-6V4" /><path d="M14 10l7-7" /><path d="M3 21l7-7" /></>
      : <><path d="M15 3h6v6" /><path d="M9 21H3v-6" /><path d="M21 3l-7 7" /><path d="M3 21l7-7" /></>}
  </svg>
)
const BAND_CLS: Record<string, string> = { 안: 'bg-brand-soft text-brand', 아래: 'bg-dn/10 text-dn', 위: 'bg-up/10 text-up' }

export function LiveChart({ live }: { live: Live }) {
  const ver = useSyncExternalStore((fn) => live.subscribe(fn), () => live.version)
  const D = live.D
  const [sel, setSel] = useState(0)
  const [[zA, zB], setZ] = useState<[number, number]>([0, 1])
  const [tip, setTip] = useState<{ x: number; t: string; p: number } | null>(null)
  const svgRef = useRef<SVGSVGElement>(null)
  const drag = useRef<{ x: number; a: number; b: number; moved: boolean } | null>(null)
  const e = D.ent[sel]
  const [exp, setExp] = useState(false)
  const [vw, setVw] = useState(() => window.innerWidth)
  const { W, H } = dimsOf(exp, vw), PW = W - L - R
  const dims = useRef({ W, PW }); dims.current = { W, PW }

  // 크게 보기 — 화면 전체를 덮는다. Esc 로 닫고, 그동안 뒤 화면 스크롤은 막는다
  useEffect(() => {
    if (!exp) return
    const onKey = (ev: KeyboardEvent) => { if (ev.key === 'Escape') setExp(false) }
    const onResize = () => setVw(window.innerWidth)
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'; onResize()
    window.addEventListener('keydown', onKey); window.addEventListener('resize', onResize)
    return () => { document.body.style.overflow = prev; window.removeEventListener('keydown', onKey); window.removeEventListener('resize', onResize) }
  }, [exp])

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
  }, [ver, sel, zA, zB, live, e, D, W, H, PW])

  // 휠 확대(PC 마우스만) — 터치 화면은 스크롤을 건드리지 않는다
  useEffect(() => {
    const svg = svgRef.current
    if (!svg || !window.matchMedia('(pointer:fine)').matches) return
    const frac = (ev: MouseEvent) => {
      const r = svg.getBoundingClientRect(), { W, PW } = dims.current
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

  // 오른쪽 위 +/− 버튼 — 지금 보이는 구간의 가운데를 기준으로 확대·축소(터치 화면에서도 된다)
  const zoomBy = (k: number) => setZ(([a, b]) => {
    const c = (a + b) / 2, w = Math.max(0.08, Math.min(1, (b - a) * k))
    const na = Math.max(0, Math.min(1 - w, c - w / 2))
    return [na, na + w]
  })

  const { X, Y, inX, pre, tail, ses, last, grid, tips, op } = view
  const zoomed = zB - zA < 0.999
  const xo = X(D.t_open), xe = X(D.t_close)
  const col = last != null && last < 0 ? 'var(--dn)' : 'var(--up)'
  const poly = (pts: (Bar | Pt)[]) => pts.map((p) => X(p[0]).toFixed(1) + ',' + Y(p[1]).toFixed(1)).join(' ')
  const kx = live.useKrx(e), now = Date.now()
  const afterClose = kx && e.key !== 'KOSPI' && now > D.t_close + 6e4 && ses.length > 0

  const showTip = (clientX: number) => {
    const r = svgRef.current!.getBoundingClientRect(), sx = (clientX - r.left) * W / r.width
    let best = null as (typeof tips)[number] | null, dd = 1e9
    for (const t of tips) { const v = Math.abs(t.x - sx); if (v < dd) { dd = v; best = t } }
    setTip(best)
  }
  const onMove = (ev: React.PointerEvent<SVGSVGElement>) => {
    const g = drag.current
    if (g) {   // 확대한 상태에서 끌면 좌우 이동(마우스·터치 모두). 3px 안쪽 움직임은 탭으로 본다
      if (!g.moved && Math.abs(ev.clientX - g.x) <= 3) return
      g.moved = true
      const r = svgRef.current!.getBoundingClientRect()
      const d = (ev.clientX - g.x) * W / r.width / PW * (g.b - g.a)
      const w = g.b - g.a, na = Math.max(0, Math.min(1 - w, g.a - d))
      setTip(null); setZ([na, na + w]); return
    }
    showTip(ev.clientX)
  }

  return (
    <Card aria-label="예측과 실시간">
      <div className={exp ? 'fixed inset-0 z-50 overflow-y-auto bg-bg p-3 sm:p-6' : ''} role={exp ? 'dialog' : undefined} aria-modal={exp || undefined} aria-label={exp ? '예측 → 실시간 크게 보기' : undefined}>
      <div className={exp ? 'mx-auto w-full max-w-[1240px] rounded-3xl bg-card p-4 shadow-[var(--shadow)] sm:p-6' : ''}>
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
      <div className="mb-1.5 flex items-center justify-end gap-1.5" role="group" aria-label="차트 확대·축소">
        {zoomed && <span className="num mr-0.5 text-[12px] font-semibold text-tx3">{(1 / (zB - zA)).toFixed(1)}배</span>}
        {zoomed && <button type="button" onClick={() => setZ([0, 1])} className="h-9 rounded-full border border-line bg-card px-3 text-[12px] font-semibold text-tx2">전체</button>}
        <button type="button" aria-label="확대" title="확대" onClick={() => zoomBy(0.6)} disabled={zB - zA <= 0.081}
          className="grid size-9 place-items-center rounded-full border border-line bg-card text-[18px] font-bold leading-none text-tx2 disabled:opacity-40">+</button>
        <button type="button" aria-label="축소" title="축소" onClick={() => zoomBy(1 / 0.6)} disabled={!zoomed}
          className="grid size-9 place-items-center rounded-full border border-line bg-card text-[18px] font-bold leading-none text-tx2 disabled:opacity-40">−</button>
        <span className="mx-0.5 h-5 w-px bg-line" aria-hidden />
        <button type="button" onClick={() => setExp((v) => !v)} aria-pressed={exp}
          aria-label={exp ? '차트 원래 크기로' : '차트 크게 보기'} title={exp ? '원래 크기로 (Esc)' : '크게 보기'}
          className={cn('grid h-9 place-items-center rounded-full border text-tx2', exp ? 'grid-flow-col gap-1.5 border-tx bg-tx px-3 text-[12px] font-semibold text-bg' : 'size-9 border-line bg-card')}>
          <ExpandIcon open={exp} />{exp && '원래 크기'}
        </button>
      </div>
      <div className="relative">
        <svg ref={svgRef} viewBox={`0 0 ${W} ${H}`} className="viz block w-full touch-pan-y select-none" role="img"
          aria-label={`${e.name}${e.lo != null && e.hi != null ? ` 예측 구간 ${sg(e.lo)} ~ ${sg(e.hi)}` : ''}${last != null ? `, 현재 ${sg(last)}` : ''}`}
          onPointerMove={onMove} onPointerLeave={() => setTip(null)} onDoubleClick={() => setZ([0, 1])}
          onPointerDown={(ev) => { if (zoomed) { drag.current = { x: ev.clientX, a: zA, b: zB, moved: false }; ev.currentTarget.setPointerCapture(ev.pointerId) } }}
          onPointerUp={(ev) => { const g = drag.current; drag.current = null; if (g && !g.moved) showTip(ev.clientX) }}
          onPointerCancel={() => { drag.current = null }}>
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
          {([[D.t_open, '09:00'], [D.t_prev, '15:30'], [D.t_night, '05:00'], [D.t_open + 108e5, '12:00'], [D.t_close, '15:30']] as [number, string][])
            .filter(([t]) => inX(X(t)))
            .filter(([t], i, arr) => arr.slice(0, i).every(([u]) => Math.abs(X(u) - X(t)) >= 26))   // 겹치는 시각 글자는 뒤의 것을 뺀다(09:00 우선)
            .map(([t, s]) => <text key={s + t} x={X(t)} y={H - 6} textAnchor="middle" fontSize={9} fill="var(--tx3)">{s}</text>)}
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
        오른쪽 위 + · − 로 확대·축소하고, 확대한 뒤에는 좌우로 끌어 옮깁니다. PC 는 마우스 휠도 되고, 더블클릭하면 원래대로 돌아갑니다.
        맨 오른쪽 버튼은 차트를 화면 가득 크게 보여 줍니다(Esc 또는 같은 버튼으로 닫기).
      </Cap>
      </div>
      </div>
    </Card>
  )
}
