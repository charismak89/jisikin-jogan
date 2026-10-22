import { useRef, useState } from 'react'
import type { DayData } from '../types'
import { md, nf, dir, sg } from '../lib/fmt'
import { Card, CardHead, Cap } from './ui/card'

// 오른쪽 여백은 마지막 막대와 날짜 글자만큼만 — 그래프가 카드 폭 끝까지 닿게(2026-10-22). '오늘' 글자는 마지막 막대 위에 둔다
const W = 360, H = 210, L = 40, R = 14, T = 14, B = 24

export function K20Chart({ data }: { data: DayData }) {
  const rows = data.k20.rows
  const closes = rows.filter((r) => r.close != null)
  const svgRef = useRef<SVGSVGElement>(null)
  const [tip, setTip] = useState<number | null>(null)
  if (closes.length < 2) return null
  const vals: number[] = closes.map((r) => r.close as number)
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
      <CardHead title="코스피 20거래일 · 예측 기록" right={data.k20.close != null && <span className="num">{nf(data.k20.close, 2)} <b className={dir(data.k20.pct)}>{data.k20.pct != null ? sg(data.k20.pct) : ''}</b></span>} />
      <div className="relative">
        <svg ref={svgRef} viewBox={`0 0 ${W} ${H}`} className="viz block w-full touch-pan-y" role="img" onPointerMove={onMove} onPointerLeave={() => setTip(null)}
          aria-label={`코스피 최근 ${closes.length}거래일 종가와 회차별 예상 구간, 실제 시초가`}>
          {grid.map((g) => <g key={g}><line x1={L} x2={W - 2} y1={Y(g)} y2={Y(g)} stroke="var(--line)" />
            <text x={L - 6} y={Y(g) + 3.5} textAnchor="end" fontSize={9} fill="var(--tx3)">{nf(g, 0)}</text></g>)}
          {rows.map((r, i) => r.low != null && r.high != null && (
            <rect key={r.date} x={X(i) - 3.5} y={Y(r.high)} width={7} height={Math.max(2, Y(r.low) - Y(r.high))} rx={2}
              fill={r.today ? 'var(--band)' : 'var(--line)'} stroke={r.today ? 'var(--band-line)' : 'none'} />))}
          <polyline points={line} fill="none" stroke="var(--tx)" strokeWidth={1.8} strokeLinejoin="round" />
          {rows.map((r, i) => r.open != null && (
            <circle key={r.date} cx={X(i)} cy={Y(r.open)} r={4} fill={r.in_range ? 'var(--ok)' : 'var(--card)'} stroke={r.in_range ? 'var(--ok)' : 'var(--tx2)'} strokeWidth={1.8} />))}
          {data.forecast.low != null && data.forecast.high != null && <text x={X(rows.length - 1)} y={Math.max(10, Y(Math.max(data.forecast.low, data.forecast.high)) - 5)} textAnchor="middle" fontSize={10} fontWeight={700} fill="var(--tx2)">오늘</text>}
          {labelIdx.map((i) => <text key={i} x={X(rows.findIndex((r) => r === closes[i]))} y={H - 6} textAnchor="middle" fontSize={9} fill="var(--tx3)">{md(closes[i].date)}</text>)}
          {tip != null && <line x1={X(tip)} x2={X(tip)} y1={T} y2={H - B} stroke="var(--tx3)" strokeWidth={0.8} />}
        </svg>
        {t && tip != null && (
          <div className="pointer-events-none absolute -top-1.5 -translate-x-1/2 -translate-y-full whitespace-nowrap rounded-xl bg-tx px-2.5 py-1.5 text-[12px] leading-snug text-bg"
            style={{ left: `${Math.max(64, Math.min(W - 64, X(tip))) / W * 100}%` }}>
            <b>{md(t.date)}</b>{t.close != null && <><br />종가 {nf(t.close, 2)}</>}
            {t.low != null && t.high != null && <><br />{t.today ? '오늘 전망' : '전망'} {nf(t.low, 0)}~{nf(t.high, 0)}</>}
            {t.open != null && <><br />시초가 {nf(t.open, 2)} · {t.in_range ? '적중' : '구간 밖'}</>}
          </div>
        )}
      </div>
      <Cap>선 — 종가 · 막대 — 그날 아침 예상 구간(노란색이 오늘) · 점 — 실제 시초가(채움: 구간 안, 테두리: 구간 밖) · {data.k20.cap}</Cap>
    </Card>
  )
}
