// 차트 크게 보기(2026-11-27, 사용자 결정 "Lightweight Charts 1단계").
// 앤트위키처럼 TradingView 의 오픈소스 Lightweight Charts(Apache-2.0)에 우리 데이터를 넣는다. 유료 위젯이 아니다.
// 라이브러리는 이 창을 열 때만 불러온다(첫 화면 번들에 넣지 않는다). 출처 표기는 차트 안 TradingView 로고(attributionLogo)로 한다.
// 1단계는 지금 받는 값(1분봉 종가 %, 20거래일 종가와 예상 구간)만 쓴다. 캔들은 중계기가 1분봉 시가, 고가, 저가를 줄 때(2단계).
import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import type { K20Row, Pt } from '../../types'
import { md, nf, sg } from '../../lib/fmt'
import { Button } from './ui/button'

export type BigSpec =
  | { kind: 'line'; title: string; note?: string | null
      pts: Pt[]; x0?: number; x1?: number   // 시간축 범위(ms). 카드 차트와 같은 범위(예: 09:00~15:30)를 비워서라도 보인다
      band?: { lo: number; hi: number } | null; pin?: { t: number; p: number; label: string } | null
      level?: (p: number) => string }   // % → 지수나 원(없으면 % 만)
  | { kind: 'k20'; title: string; note?: string | null; rows: K20Row[] }

const KST = 9 * 3600

/** CSS 변수 값을 차트가 읽는 rgba() 로 바꾼다. 몽타주 토큰은 #RRGGBBAA 라 캔버스에 한 번 칠해 정규화한다 */
function colorOf(name: string, alpha = 1) {
  const raw = getComputedStyle(document.documentElement).getPropertyValue(name).trim() || '#888'
  const c = document.createElement('canvas').getContext('2d')!
  c.fillStyle = raw; c.fillRect(0, 0, 1, 1)
  const [r, g, b, a] = c.getImageData(0, 0, 1, 1).data
  return `rgba(${r},${g},${b},${((a / 255) * alpha).toFixed(3)})`
}
/** 카드 바탕 위에 반투명 색을 칠한 결과(불투명). 차트 글자색은 불투명이어야 또렷하다 */
function solidOn(fg: string, bg: string) {
  const c = document.createElement('canvas').getContext('2d')!
  c.fillStyle = bg; c.fillRect(0, 0, 1, 1); c.fillStyle = fg; c.fillRect(0, 0, 1, 1)
  const [r, g, b] = c.getImageData(0, 0, 1, 1).data
  return `rgb(${r},${g},${b})`
}
const two = (n: number) => String(n).padStart(2, '0')
/** 시각(ms) → 차트 시각. 차트는 UTC 로 그리므로 9시간을 더해 KST 로 보이게 한다 */
const ts = (t: number) => Math.floor(t / 1000) + KST
const hhmm = (sec: number) => { const d = new Date(sec * 1000); return `${two(d.getUTCHours())}:${two(d.getUTCMinutes())}` }

export function ChartSheet({ spec, onClose }: { spec: BigSpec; onClose: () => void }) {
  const box = useRef<HTMLDivElement>(null)
  const closeBtn = useRef<HTMLButtonElement>(null)
  const [legend, setLegend] = useState<string>('')
  const [err, setErr] = useState('')

  // 뒤로 가기, Esc 로 닫기. 열 때 기록을 하나 쌓고, 닫기 단추와 Esc 는 그 기록을 되돌린다(popstate 가 onClose 를 부른다)
  useEffect(() => {
    const back = document.activeElement as HTMLElement | null
    try { history.pushState({ jjChart: 1 }, '') } catch { /* 무시 */ }
    const onPop = () => onClose()
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') { e.preventDefault(); history.back() } }
    window.addEventListener('popstate', onPop); window.addEventListener('keydown', onKey)
    const ov = document.body.style.overflow; document.body.style.overflow = 'hidden'
    closeBtn.current?.focus()
    return () => {
      window.removeEventListener('popstate', onPop); window.removeEventListener('keydown', onKey)
      document.body.style.overflow = ov; back?.focus?.()
    }
  }, [onClose])

  // 차트. spec 이 바뀌면(실시간 값) 다시 그린다 — 1분에 몇 번이라 다시 만드는 비용은 작다
  const key = JSON.stringify(spec.kind === 'line' ? [spec.title, spec.pts.length, spec.pts[spec.pts.length - 1], spec.band, spec.pin] : [spec.title, spec.rows.length])
  useEffect(() => {
    let dead = false, dispose = () => {}
    import('lightweight-charts').then((lc) => {
      if (dead || !box.current) return
      const card = colorOf('--mt-surface-elevated-primary')
      const txt = solidOn(colorOf('--mt-foreground-neutral-secondary'), card)
      const grid = colorOf('--mt-line-neutral-primary', 0.6)
      const up = colorOf('--mt-fin-up'), down = colorOf('--mt-fin-down')
      const bandLine = colorOf('--mt-foreground-cautionary-primary'), bandFill = colorOf('--mt-foreground-cautionary-primary', 0.28)
      const chart = lc.createChart(box.current, {
        autoSize: true,
        layout: { background: { type: lc.ColorType.Solid, color: card }, textColor: txt, fontSize: 12,
          fontFamily: getComputedStyle(document.body).fontFamily, attributionLogo: true },
        grid: { vertLines: { color: grid }, horzLines: { color: grid } },
        rightPriceScale: { borderVisible: false, scaleMargins: { top: 0.12, bottom: 0.08 } },
        timeScale: { borderVisible: false, timeVisible: true, secondsVisible: false, rightOffset: 2,
          tickMarkFormatter: (t: unknown) => (typeof t === 'number' ? hhmm(t) : typeof t === 'string' ? md(t) : `${(t as { month: number }).month}/${(t as { day: number }).day}`) },
        crosshair: { mode: lc.CrosshairMode.Normal },
        localization: { locale: 'ko-KR', timeFormatter: (t: unknown) => (typeof t === 'number' ? hhmm(t) : typeof t === 'string' ? md(t) : '') },
      })
      dispose = () => chart.remove()

      if (spec.kind === 'line') {
        // 같은 시각이 두 번 오면(실시간 꼬리) 뒤의 값을 쓴다. 차트는 시각이 겹치면 오류를 낸다
        const m = new Map<number, number>()
        for (const [t, p] of [...spec.pts].sort((a, b) => a[0] - b[0])) m.set(ts(t), p)
        const data = [...m].map(([time, value]) => ({ time: time as never, value }))
        const last = data[data.length - 1]?.value ?? 0
        const col = last < 0 ? down : up
        const s = chart.addSeries(lc.AreaSeries, {
          lineColor: col, topColor: col.replace(/[\d.]+\)$/, '0.16)'), bottomColor: col.replace(/[\d.]+\)$/, '0)'), lineWidth: 2,
          priceLineVisible: false, lastValueVisible: true,
          priceFormat: { type: 'custom', minMove: 0.01, formatter: (p: number) => sg(p) },
          // 세로 범위에 기준 0%, 전망 구간, 시가를 넣는다(가격선은 기본 자동 범위에 들지 않아 위아래가 잘렸다)
          autoscaleInfoProvider: (orig: () => { priceRange: { minValue: number; maxValue: number } } | null) => {
            const r = orig(), ex = [0, ...(spec.band ? [spec.band.lo, spec.band.hi] : []), ...(spec.pin ? [spec.pin.p] : [])]
            const lo = Math.min(...ex, r?.priceRange.minValue ?? 0), hi = Math.max(...ex, r?.priceRange.maxValue ?? 0)
            return { priceRange: { minValue: lo, maxValue: hi }, margins: { above: 24, below: 16 } }
          },
        })
        // 데이터 앞뒤 빈 시각을 데이터 간격대로 채워 시간축을 x0~x1 로 편다. 이 차트는 점 개수로 가로 간격을 정해서
        // 빈 시각을 한 점만 넣으면 06:00 까지 몇 시간이 한 칸에 붙는다(2026-11-27 1440px 사진). 값이 없는 점은 그리지 않는다
        const T = data.map((d) => d.time as unknown as number)
        const gaps = T.slice(1).map((t, i) => t - T[i]).sort((a, b) => a - b)
        const step = Math.max(60, gaps.length ? gaps[gaps.length >> 1] : 60)
        const fill = (a: number, b: number) => { const o: { time: never }[] = []; for (let t = a; t < b && o.length < 2000; t += step) o.push({ time: t as never }); return o }
        const head = spec.x0 != null && T.length && ts(spec.x0) < T[0] ? fill(ts(spec.x0), T[0]) : []
        const tail = spec.x1 != null && T.length && ts(spec.x1) > T[T.length - 1] ? fill(T[T.length - 1] + step, ts(spec.x1) + 1) : []
        const all = [...head, ...data, ...tail]
        s.setData(all)
        s.createPriceLine({ price: 0, color: txt, lineWidth: 1, lineStyle: lc.LineStyle.Dashed, axisLabelVisible: false, title: '기준 0%' })
        if (spec.band) {
          s.createPriceLine({ price: spec.band.hi, color: bandLine, lineWidth: 2, lineStyle: lc.LineStyle.Solid, axisLabelVisible: true, title: '07:45 전망 상단' })
          s.createPriceLine({ price: spec.band.lo, color: bandLine, lineWidth: 2, lineStyle: lc.LineStyle.Solid, axisLabelVisible: true, title: '하단' })
        }
        if (spec.pin && data.length) {
          lc.createSeriesMarkers(s, [{ time: ts(spec.pin.t) as never, position: 'atPriceMiddle', price: spec.pin.p, shape: 'circle',
            color: colorOf('--mt-foreground-brand-primary'), text: spec.pin.label, size: 1 }])
        }
        // fitContent 는 뒤쪽 빈 시각을 화면 밖으로 밀어낸다. 점 번호로 처음부터 끝까지를 직접 잡는다
        chart.timeScale().setVisibleLogicalRange({ from: 0, to: Math.max(1, all.length - 1) })
        const fmt = (time: number, p: number) => `${hhmm(time)}  ${sg(p)}${spec.level ? `  ${spec.level(p)}` : ''}`
        const idle = last != null && data.length ? fmt(data[data.length - 1].time as unknown as number, last) : '값 없음'
        setLegend(idle)
        chart.subscribeCrosshairMove((pr) => {
          const v = pr.time != null ? (pr.seriesData.get(s) as { value?: number } | undefined)?.value : undefined
          setLegend(v != null ? fmt(pr.time as number, v) : idle)
        })
      } else {
        const rows = spec.rows.filter((r) => r.close != null || (r.low != null && r.high != null))
        // 예상 구간 막대: 캔들 몸통을 구간(시가=상단, 종가=하단)으로 쓴다. 오늘만 띠 색
        const box2 = chart.addSeries(lc.CandlestickSeries, {
          upColor: grid, downColor: grid, borderVisible: true, borderUpColor: grid, borderDownColor: grid, wickVisible: false,
          priceLineVisible: false, lastValueVisible: false, priceFormat: { type: 'price', precision: 0, minMove: 1 },
        })
        box2.setData(rows.filter((r) => r.low != null && r.high != null).map((r) => ({
          time: r.date as never, open: r.high as number, high: r.high as number, low: r.low as number, close: r.low as number,
          ...(r.today ? { color: bandFill, borderColor: bandLine } : {}),
        })))
        const line = chart.addSeries(lc.LineSeries, {
          color: solidOn(colorOf('--mt-foreground-neutral-primary'), card), lineWidth: 2, priceLineVisible: false, lastValueVisible: true,
          priceFormat: { type: 'price', precision: 2, minMove: 0.01 },
        })
        line.setData(rows.filter((r) => r.close != null).map((r) => ({ time: r.date as never, value: r.close as number })))
        const pos = colorOf('--mt-foreground-positive-primary')
        lc.createSeriesMarkers(line, rows.filter((r) => r.open != null).map((r) => ({
          time: r.date as never, position: 'atPriceMiddle' as const, price: r.open as number, shape: 'circle' as const,
          color: r.in_range ? pos : txt, size: 1,
        })))
        chart.timeScale().fitContent()
        const byDate = new Map(rows.map((r) => [r.date, r]))
        const fmt = (r: K20Row) => [md(r.date), r.close != null ? `종가 ${nf(r.close, 2)}` : null,
          r.low != null && r.high != null ? `${r.today ? '오늘 전망' : '전망'} ${nf(r.low)}~${nf(r.high)}` : null,
          r.open != null ? `시초가 ${nf(r.open, 2)} ${r.in_range ? '적중' : '구간 밖'}` : null].filter(Boolean).join('  ')
        const idle = rows.length ? fmt(rows[rows.length - 1]) : ''
        setLegend(idle)
        chart.subscribeCrosshairMove((pr) => {
          const r = typeof pr.time === 'string' ? byDate.get(pr.time) : pr.time && typeof pr.time === 'object'
            ? byDate.get(`${(pr.time as { year: number }).year}-${two((pr.time as { month: number }).month)}-${two((pr.time as { day: number }).day)}`) : undefined
          setLegend(r ? fmt(r) : idle)
        })
      }
    }, () => { if (!dead) setErr('차트를 불러오지 못했습니다. 네트워크를 확인하고 다시 열어 주세요.') })
    return () => { dead = true; dispose() }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key])

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-stretch justify-center bg-scrim lg:items-center lg:p-8" onClick={() => history.back()}>
      <div role="dialog" aria-modal="true" aria-label={`${spec.title} 크게 보기`} onClick={(e) => e.stopPropagation()}
        className="flex h-full w-full flex-col bg-card lg:h-[min(680px,88vh)] lg:max-w-[1040px] lg:rounded-lg lg:shadow-xs">
        <div className="flex items-start justify-between gap-3 px-4 pb-2 pt-4 sm:px-6">
          <div className="min-w-0">
            <h2 className="text-headline1 font-bold text-fg">{spec.title}</h2>
            <p className="num mt-0.5 min-h-5 truncate text-label2 font-semibold text-fg-2" aria-live="polite">{legend}</p>
          </div>
          <Button ref={closeBtn} variant="assistive" size="small" onClick={() => history.back()} className="shrink-0">닫기</Button>
        </div>
        <div className="relative min-h-0 flex-1 px-2 sm:px-4">
          <div ref={box} className="absolute inset-0 mx-2 sm:mx-4" />
          {err && <p className="absolute inset-0 flex items-center justify-center text-body2 text-fg-2">{err}</p>}
        </div>
        <p className="px-4 pb-4 pt-2 text-caption1 leading-snug text-fg-2 sm:px-6">
          {spec.note ? <>{spec.note}<br /></> : null}
          두 손가락이나 휠로 확대, 끌어서 이동. 차트 그림은 TradingView Lightweight Charts 입니다.
        </p>
      </div>
    </div>,
    document.body,
  )
}
