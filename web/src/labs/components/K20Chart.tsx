import { useCallback, useEffect, useRef, useState } from 'react'
import type { DayData, DayOhlc } from '../../types'
import { md, nf, sg } from '../../lib/fmt'
import { Card, CardHeader, Cap } from './ui/card'
import { tone } from '../lib/tone'
import { ChartSheet } from './ChartSheet'
import { ZoomButton } from './ui/zoom-button'
import { LAB } from '../lab'

/** 코스피 일봉(중계기 /v1/kospi-daily, 2026-11-27 실험실). 오늘 봉이 장중에 바뀌니 화면이 보일 때 1분마다 다시 받는다 */
function useKospiDaily(relay: string | null) {
  const [m, setM] = useState<Record<string, DayOhlc>>({})
  useEffect(() => {
    if (!LAB || !relay) return
    let dead = false
    const get = () => {
      if (document.hidden) return
      fetch(relay + '/v1/kospi-daily', { cache: 'no-store' }).then((r) => { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json() })
        .then((j: { items: DayOhlc[] }) => { if (!dead) setM(Object.fromEntries(j.items.map((x) => [x[0], x]))) }, () => { /* 못 받으면 선으로 그린다 */ })
    }
    get(); const id = window.setInterval(get, 60e3)
    return () => { dead = true; window.clearInterval(id) }
  }, [relay])
  return m
}

// 오른쪽 여백은 마지막 막대와 날짜 글자만큼만 — 그래프가 카드 폭 끝까지 닿게(2026-10-22). '오늘' 글자는 마지막 막대 위에 둔다
const W = 360, H = 210, L = 40, R = 14, T = 14, B = 24

export function K20Chart({ data }: { data: DayData }) {
  const rows = data.k20.rows
  const closes = rows.filter((r) => r.close != null)
  const svgRef = useRef<SVGSVGElement>(null)
  const [tip, setTip] = useState<number | null>(null)
  const [big, setBig] = useState(false)
  const closeBig = useCallback(() => setBig(false), [])
  const daily = useKospiDaily(data.day.relay)
  if (closes.length < 2) return null
  // 캔들(실험실): 중계기 일봉이 있는 날은 봉으로 그린다. 한 날이라도 있으면 종가 선은 감춘다
  const ohlc = rows.map((r) => daily[r.date] ?? null)
  const useC = ohlc.some(Boolean)
  const vals: number[] = closes.map((r) => r.close as number)
  ohlc.forEach((k) => { if (k) vals.push(k[2], k[3]) })
  rows.forEach((r) => { if (r.low != null && r.high != null) vals.push(r.low, r.high); if (r.open != null) vals.push(r.open) })
  const span = Math.max(...vals) - Math.min(...vals), raw = span / 4, mag = 10 ** Math.floor(Math.log10(raw || 1))
  const stp = Math.min(...[1, 2, 2.5, 5, 10].map((s) => s * mag).filter((v) => v >= raw))
  const y0 = Math.floor(Math.min(...vals) / stp) * stp, y1 = Math.ceil(Math.max(...vals) / stp) * stp
  const X = (i: number) => L + i * (W - L - R) / (rows.length - 1)
  const Y = (v: number) => T + (y1 - v) / (y1 - y0) * (H - T - B)
  const grid: number[] = []
  for (let g = y0; g <= y1 + 1e-9; g += stp) grid.push(g)
  const line = rows.map((r, i) => (r.close != null ? `${X(i).toFixed(1)},${Y(r.close).toFixed(1)}` : null)).filter(Boolean).join(' ')
  const labelIdx = [...new Set([0, Math.floor((closes.length - 1) / 2), closes.length - 1])]
  const t = tip != null ? rows[tip] : null
  const onMove = (ev: React.PointerEvent) => {
    const r = svgRef.current!.getBoundingClientRect(), sx = (ev.clientX - r.left) * W / r.width
    setTip(Math.max(0, Math.min(rows.length - 1, Math.round((sx - L) / ((W - L - R) / (rows.length - 1))))))
  }
  return (
    <Card aria-label="코스피 최근 20거래일과 예측 기록">
      <CardHeader title="코스피 20거래일 · 예측 기록" aside={<span className="inline-flex items-center gap-2">{data.k20.close != null && <span className="num">{nf(data.k20.close, 2)} <b className={tone(data.k20.pct)}>{data.k20.pct != null ? sg(data.k20.pct) : ''}</b></span>}<ZoomButton onClick={() => setBig(true)} /></span>} />
      {big && <ChartSheet onClose={closeBig} spec={{ kind: 'k20', title: '코스피 20거래일과 예측 기록', rows, ohlc: useC ? rows.map((r) => daily[r.date]).filter(Boolean) as DayOhlc[] : null,
        note: `${useC ? '봉은 코스피 일봉' : '선은 종가'}, 회색 막대는 그날 아침 예상 구간(띠 색이 오늘), 점은 실제 시초가(초록: 구간 안)` }} />}
      <div className="relative">
        <svg ref={svgRef} viewBox={`0 0 ${W} ${H}`} className="viz block w-full touch-pan-y" role="img" onPointerMove={onMove} onPointerLeave={() => setTip(null)}
          aria-label={`코스피 최근 ${closes.length}거래일 종가와 회차별 예상 구간, 실제 시초가`}>
          {grid.map((g) => <g key={g}><line x1={L} x2={W - 2} y1={Y(g)} y2={Y(g)} stroke="var(--mt-line-neutral-primary)" />
            <text x={L - 6} y={Y(g) + 3.5} textAnchor="end" fontSize={9} fill="var(--mt-foreground-neutral-secondary)">{nf(g, 0)}</text></g>)}
          {rows.map((r, i) => r.low != null && r.high != null && (
            <rect key={r.date} x={X(i) - (useC ? 5 : 3.5)} y={Y(r.high)} width={useC ? 10 : 7} height={Math.max(2, Y(r.low) - Y(r.high))} rx={2}
              className={r.today ? 'fill-band stroke-band-line' : 'fill-line'} />))}
          {useC ? ohlc.map((k, i) => {
            if (!k) return null
            const [, o, h, l, c] = k, col = c >= o ? 'var(--mt-fin-up)' : 'var(--mt-fin-down)', top = Y(Math.max(o, c))
            return <g key={k[0]}><line x1={X(i)} x2={X(i)} y1={Y(h)} y2={Y(l)} stroke={col} strokeWidth={1} />
              <rect x={X(i) - 2.5} y={top} width={5} height={Math.max(1, Y(Math.min(o, c)) - top)} fill={col} /></g>
          }) : <polyline points={line} fill="none" stroke="var(--mt-foreground-neutral-primary)" strokeWidth={1.8} strokeLinejoin="round" />}
          {rows.map((r, i) => r.open != null && (
            <circle key={r.date} cx={X(i)} cy={Y(r.open)} r={4} fill={r.in_range ? 'var(--mt-foreground-positive-primary)' : 'var(--mt-surface-elevated-primary)'} stroke={r.in_range ? 'var(--mt-foreground-positive-primary)' : 'var(--mt-foreground-neutral-secondary)'} strokeWidth={1.8} />))}
          {data.forecast.low != null && data.forecast.high != null && <text x={X(rows.length - 1)} y={Math.max(10, Y(Math.max(data.forecast.low, data.forecast.high)) - 5)} textAnchor="middle" fontSize={10} fontWeight={700} fill="var(--mt-foreground-neutral-secondary)">오늘</text>}
          {labelIdx.map((i) => <text key={i} x={X(rows.findIndex((r) => r === closes[i]))} y={H - 6} textAnchor="middle" fontSize={9} fill="var(--mt-foreground-neutral-secondary)">{md(closes[i].date)}</text>)}
          {tip != null && <line x1={X(tip)} x2={X(tip)} y1={T} y2={H - B} stroke="var(--mt-foreground-neutral-secondary)" strokeWidth={0.8} />}
        </svg>
        {t && tip != null && (
          <div className="pointer-events-none absolute -top-1.5 -translate-x-1/2 -translate-y-full whitespace-nowrap rounded-md bg-inverse px-2.5 py-1.5 text-caption1 leading-snug text-fg-inverse"
            style={{ left: `${Math.max(64, Math.min(W - 64, X(tip))) / W * 100}%` }}>
            <b>{md(t.date)}</b>{ohlc[tip] ? <><br />시 {nf(ohlc[tip]![1], 2)} 고 {nf(ohlc[tip]![2], 2)}<br />저 {nf(ohlc[tip]![3], 2)} 종 {nf(ohlc[tip]![4], 2)}</> : t.close != null && <><br />종가 {nf(t.close, 2)}</>}
            {t.low != null && t.high != null && <><br />{t.today ? '오늘 전망' : '전망'} {nf(t.low, 0)}~{nf(t.high, 0)}</>}
            {t.open != null && <><br />시초가 {nf(t.open, 2)} · {t.in_range ? '적중' : '구간 밖'}</>}
          </div>
        )}
      </div>
      <Cap>{useC ? '봉 — 코스피 일봉(오르면 빨강, 내리면 파랑)' : '선 — 종가'} · 막대 — 그날 아침 예상 구간(노란색이 오늘) · 점 — 실제 시초가(채움: 구간 안, 테두리: 구간 밖) · {data.k20.cap}</Cap>
    </Card>
  )
}
