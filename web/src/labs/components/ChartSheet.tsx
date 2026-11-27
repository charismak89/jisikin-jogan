// 차트 크게 보기(2026-11-27, 사용자 결정 "Lightweight Charts 1단계").
// 앤트위키처럼 TradingView 의 오픈소스 Lightweight Charts(Apache-2.0)에 우리 데이터를 넣는다. 유료 위젯이 아니다.
// 라이브러리는 이 창을 열 때만 불러온다(첫 화면 번들에 넣지 않는다). 출처 표기는 차트 안 TradingView 로고(attributionLogo)로 한다.
// 2단계(2026-11-27, 실험실): spec.candles 가 있으면 '선/봉', '1분/5분'을 고른다. 캔들은 중계기가 준 1분봉 시, 고, 저, 종(장중, 야간선물)과
// Hyperliquid 봉(밤 추종가)이다. 메인은 candles 를 넘기지 않아(LAB 플래그) 1단계 그대로다.
// 차트는 창을 열 때 한 번 만들고, 15초 실시간 갱신은 데이터만 바꾼다(확대, 이동 상태를 지키려고. 2026-11-27 검수)
import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import type { IChartApi, IPriceLine, ISeriesApi, ISeriesMarkersPluginApi, SeriesType, Time } from 'lightweight-charts'
import type { K20Row, Ohlc, Pt } from '../../types'
import { md, nf, sg } from '../../lib/fmt'
import { Button } from './ui/button'
import { cn } from '../lib/cn'

export type BigSpec =
  | { kind: 'line'; title: string; note?: string | null
      pts: Pt[]; x0?: number; x1?: number   // 시간축 범위(ms). 카드 차트와 같은 범위(예: 09:00~15:30)를 비워서라도 보인다
      band?: { lo: number; hi: number } | null; pin?: { t: number; p: number; label: string } | null
      level?: (p: number) => string   // % → 지수나 원(없으면 % 만)
      candles?: Ohlc[] | null }       // 1분봉 캔들(%, 봉 끝 시각). 있으면 선/봉을 고른다
  | { kind: 'k20'; title: string; note?: string | null; rows: K20Row[] }

type LC = typeof import('lightweight-charts')
type Mode = 'line' | 'candle'
interface Live {
  lc: LC; chart: IChartApi
  main: ISeriesApi<SeriesType>; box?: ISeriesApi<'Candlestick'>; cand?: ISeriesApi<'Candlestick'>
  markers: ISeriesMarkersPluginApi<Time>; cmarkers?: ISeriesMarkersPluginApi<Time>
  lines: [ISeriesApi<SeriesType>, IPriceLine][]
  col: Record<string, string>; framed: string
}

const KST = 9 * 3600

/** CSS 변수 값을 차트가 읽는 rgba() 로 바꾼다. 몽타주 토큰은 #RRGGBBAA 라 캔버스에 한 번 칠해 정규화한다. 토큰이 없으면 투명(오타가 회색으로 가려지지 않게) */
function colorOf(name: string, alpha = 1) {
  const raw = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
  if (!raw) { console.warn('차트 색 토큰 없음', name); return 'rgba(0,0,0,0)' }
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
const dayKey = (t: unknown) => typeof t === 'string' ? t
  : t && typeof t === 'object' ? `${(t as { year: number }).year}-${two((t as { month: number }).month)}-${two((t as { day: number }).day)}` : ''

/** 데이터 앞뒤 빈 시각을 step 간격으로 채워 시간축을 x0~x1 로 편다. 이 차트는 점 개수로 가로 간격을 정해서
 *  빈 시각을 한 점만 넣으면 06:00 까지 몇 시간이 한 칸에 붙는다(2026-11-27 1440px 사진) */
function pad(T: number[], step: number, x0?: number, x1?: number) {
  const LIM = 5000
  const before = (a: number, b: number) => { const o: number[] = []; for (let t = b - step; t >= a && o.length < LIM; t -= step) o.unshift(t); return o }   // 데이터 쪽부터 채운다
  const after = (a: number, b: number) => { const o: number[] = []; for (let t = a + step; t <= b && o.length < LIM; t += step) o.push(t); return o }
  const head = x0 != null && T.length && ts(x0) < T[0] ? before(ts(x0), T[0]) : []
  const tail = x1 != null && T.length && ts(x1) > T[T.length - 1] ? after(T[T.length - 1], ts(x1)) : []
  return { head: head.map((time) => ({ time })), tail: tail.map((time) => ({ time })) }
}
/** 선 차트 데이터: 시각 정렬, 같은 시각은 뒤의 값 */
function lineData(spec: Extract<BigSpec, { kind: 'line' }>) {
  const m = new Map<number, number>()
  for (const [t, p] of [...spec.pts].sort((a, b) => a[0] - b[0])) m.set(ts(t), p)
  const data = [...m].map(([time, value]) => ({ time, value }))
  const T = data.map((d) => d.time)
  const gaps = T.slice(1).map((t, i) => t - T[i]).sort((a, b) => a - b)
  const { head, tail } = pad(T, Math.max(60, gaps.length ? gaps[gaps.length >> 1] : 60), spec.x0, spec.x1)
  return { data, all: [...head, ...data, ...tail] }
}
/** 캔들 데이터: 1분봉을 iv 분봉으로 묶는다(봉 끝 시각 기준). 같은 봉 끝은 뒤의 값 */
function candleData(spec: Extract<BigSpec, { kind: 'line' }>, iv: number) {
  const W = iv * 60, m = new Map<number, { open: number; high: number; low: number; close: number }>()
  for (const [t, o, h, l, c] of [...(spec.candles || [])].sort((a, b) => a[0] - b[0])) {
    const end = Math.ceil(ts(t) / W) * W
    const k = m.get(end)
    if (!k) m.set(end, { open: o, high: h, low: l, close: c })
    else { k.high = Math.max(k.high, h); k.low = Math.min(k.low, l); k.close = c }
  }
  const data = [...m].map(([time, v]) => ({ time, ...v }))
  const { head, tail } = pad(data.map((d) => d.time), W, spec.x0, spec.x1)
  return { data, all: [...head, ...data, ...tail] }
}

/** 두 칸 고르기 단추(몽타주 Tabs 모양을 작게) */
function Seg<T extends string | number>({ value, items, onChange, label }: { value: T; items: [T, string][]; onChange: (v: T) => void; label: string }) {
  return (
    <div role="group" aria-label={label} className="inline-flex rounded-10 bg-fill p-0.5">
      {items.map(([v, l]) => (
        <button key={String(v)} type="button" aria-pressed={v === value} onClick={() => onChange(v)}
          className={cn('min-h-8 rounded-sm px-2.5 text-caption1 font-bold', v === value ? 'bg-card text-fg shadow-xs' : 'text-fg-2')}>{l}</button>
      ))}
    </div>
  )
}

export function ChartSheet({ spec, onClose }: { spec: BigSpec; onClose: () => void }) {
  const box = useRef<HTMLDivElement>(null)
  const closeBtn = useRef<HTMLButtonElement>(null)
  const panel = useRef<HTMLDivElement>(null)
  const live = useRef<Live | null>(null)
  const specRef = useRef(spec); specRef.current = spec
  const hasCandles = spec.kind === 'line' && !!spec.candles?.length
  const [mode, setMode] = useState<Mode>('candle')
  const [iv, setIv] = useState<1 | 5>(1)
  const viewRef = useRef({ mode: (hasCandles ? 'candle' : 'line') as Mode, iv: 1 as 1 | 5 })
  viewRef.current = { mode: hasCandles ? mode : 'line', iv }
  const [legend, setLegend] = useState('')
  const [err, setErr] = useState('')

  // 뒤로 가기, Esc 로 닫기. 열 때 기록을 하나 쌓고, 닫기 단추와 Esc 는 그 기록을 되돌린다(popstate 가 onClose 를 부른다).
  // 다른 이유로 창이 사라지면(카드가 다시 그려지지 않는 경우 등) 쌓은 기록을 여기서 되돌린다
  useEffect(() => {
    const back = document.activeElement as HTMLElement | null
    let popped = false
    try { history.pushState({ jjChart: 1 }, '') } catch { /* 무시 */ }
    const onPop = () => { popped = true; onClose() }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') { e.preventDefault(); history.back() }
      // Tab 은 창 안 단추 사이만 돈다(뒤 화면으로 나가지 않게)
      if (e.key === 'Tab' && panel.current) {
        const f = [...panel.current.querySelectorAll<HTMLElement>('button')]
        if (!f.length) return
        const i = f.indexOf(document.activeElement as HTMLElement)
        e.preventDefault(); f[(i + (e.shiftKey ? -1 : 1) + f.length) % f.length].focus()
      }
    }
    window.addEventListener('popstate', onPop); window.addEventListener('keydown', onKey)
    const ov = document.body.style.overflow; document.body.style.overflow = 'hidden'
    closeBtn.current?.focus()
    return () => {
      window.removeEventListener('popstate', onPop); window.removeEventListener('keydown', onKey)
      document.body.style.overflow = ov; back?.focus?.()
      if (!popped && (history.state as { jjChart?: number } | null)?.jjChart) { try { history.back() } catch { /* 무시 */ } }
    }
  }, [onClose])

  const lineText = (time: number, p: number) => {
    const s = specRef.current
    return `${hhmm(time)}  ${sg(p)}${s.kind === 'line' && s.level ? `  ${s.level(p)}` : ''}`
  }
  const candleText = (time: number, k: { open: number; high: number; low: number; close: number }) => {
    const s = specRef.current, lv = s.kind === 'line' && s.level ? `  ${s.level(k.close)}` : ''
    return `${hhmm(time)}  시 ${sg(k.open)} 고 ${sg(k.high)} 저 ${sg(k.low)} 종 ${sg(k.close)}${lv}`
  }
  const k20Text = (r: K20Row) => [md(r.date), r.close != null ? `종가 ${nf(r.close, 2)}` : null,
    r.low != null && r.high != null ? `${r.today ? '오늘 전망' : '전망'} ${nf(r.low)}~${nf(r.high)}` : null,
    r.open != null ? `시초가 ${nf(r.open, 2)} ${r.in_range ? '적중' : '구간 밖'}` : null].filter(Boolean).join('  ')

  // 데이터만 바꾼다. 처음과 선/봉, 분 단위를 바꿨을 때만 전체 범위를 잡는다(그 뒤에는 사용자가 확대, 이동한 상태를 둔다)
  const update = () => {
    const L = live.current, s = specRef.current
    if (!L) return
    const { lc, col } = L
    L.lines.forEach(([sr, l]) => sr.removePriceLine(l)); L.lines = []
    if (s.kind === 'line') {
      const v = viewRef.current, useC = v.mode === 'candle' && !!L.cand && !!s.candles?.length
      const { data, all } = lineData(s)
      const last = data[data.length - 1]?.value ?? 0
      const c = last < 0 ? col.down : col.up
      L.main.applyOptions({ visible: !useC, lineColor: c, topColor: c.replace(/[\d.]+\)$/, '0.16)'), bottomColor: c.replace(/[\d.]+\)$/, '0)') } as never)
      // 숨긴 시리즈의 시각도 시간축에 남아 범위가 어긋난다(5분봉이 앞부분만 보였다). 안 쓰는 쪽은 비운다
      L.main.setData((useC ? [] : all) as never)
      let n = all.length
      if (L.cand) {
        L.cand.applyOptions({ visible: useC })
        if (useC) { const cd = candleData(s, v.iv); L.cand.setData(cd.all as never); n = cd.all.length }
        else L.cand.setData([])
      }
      const act = (useC ? L.cand : L.main) as ISeriesApi<SeriesType>
      L.lines.push([act, act.createPriceLine({ price: 0, color: col.txt, lineWidth: 1, lineStyle: lc.LineStyle.Dashed, axisLabelVisible: false, title: '기준 0%' })])
      if (s.band) {
        L.lines.push([act, act.createPriceLine({ price: s.band.hi, color: col.bandLine, lineWidth: 2, lineStyle: lc.LineStyle.Solid, axisLabelVisible: true, title: '07:45 전망 상단' })])
        L.lines.push([act, act.createPriceLine({ price: s.band.lo, color: col.bandLine, lineWidth: 2, lineStyle: lc.LineStyle.Solid, axisLabelVisible: true, title: '하단' })])
      }
      const pin = s.pin && data.length ? [{ time: ts(s.pin.t) as Time, position: 'atPriceMiddle' as const, price: s.pin.p, shape: 'circle' as const, color: col.brand, text: s.pin.label, size: 1 }] : []
      L.markers.setMarkers(useC ? [] : pin)
      L.cmarkers?.setMarkers(useC ? (v.iv === 1 ? pin : []) : [])   // 5분봉에서는 시가 점 시각이 봉 끝과 어긋나 뺀다
      const fk = `${useC ? 'c' : 'l'}${v.iv}`
      if (L.framed !== fk) { L.chart.timeScale().setVisibleLogicalRange({ from: 0, to: Math.max(1, n - 1) }); L.framed = fk }   // fitContent 는 뒤쪽 빈 시각을 화면 밖으로 민다
      setLegend(data.length ? lineText(data[data.length - 1].time, last) : '값 없음')
    } else {
      // 날짜 정렬, 같은 날짜는 뒤의 줄. 차트는 날짜가 겹치거나 거꾸로면 오류를 낸다
      const rows = [...new Map([...s.rows].sort((a, b) => a.date.localeCompare(b.date)).map((r) => [r.date, r])).values()]
      L.box!.setData(rows.filter((r) => r.low != null && r.high != null).map((r) => ({
        time: r.date as Time, open: r.high as number, high: r.high as number, low: r.low as number, close: r.low as number,
        ...(r.today ? { color: col.bandFill, borderColor: col.bandLine } : {}),
      })))
      L.main.setData(rows.filter((r) => r.close != null).map((r) => ({ time: r.date as Time, value: r.close as number })))
      // 시초가 점은 구간 막대에 붙인다(종가가 없는 날도 찍히게)
      L.markers.setMarkers(rows.filter((r) => r.open != null && r.low != null && r.high != null).map((r) => ({
        time: r.date as Time, position: 'atPriceMiddle' as const, price: r.open as number, shape: 'circle' as const,
        color: r.in_range ? col.pos : col.txt, size: 1,
      })))
      if (!L.framed) { L.chart.timeScale().fitContent(); L.framed = 'k20' }
      setLegend(rows.length ? k20Text(rows[rows.length - 1]) : '')
    }
  }

  // 차트 만들기 — 창을 열 때(종류와 제목이 바뀔 때만) 한 번
  useEffect(() => {
    let dead = false, chart: IChartApi | null = null
    setErr('')
    import('lightweight-charts').then((lc) => {
      if (dead || !box.current) return
      try {
        const card = colorOf('--mt-surface-elevated-primary')
        const col: Record<string, string> = {
          card, txt: solidOn(colorOf('--mt-foreground-neutral-secondary'), card), fg: solidOn(colorOf('--mt-foreground-neutral-primary'), card),
          grid: colorOf('--mt-line-neutral-primary', 0.6), up: colorOf('--mt-fin-up'), down: colorOf('--mt-fin-down'),
          bandLine: colorOf('--mt-foreground-cautionary-primary'), bandFill: colorOf('--mt-foreground-cautionary-primary', 0.28),
          brand: colorOf('--mt-foreground-brand-primary'), pos: colorOf('--mt-foreground-positive-primary'),
        }
        chart = lc.createChart(box.current, {
          autoSize: true,
          layout: { background: { type: lc.ColorType.Solid, color: card }, textColor: col.txt, fontSize: 12,
            fontFamily: getComputedStyle(document.body).fontFamily, attributionLogo: true },
          grid: { vertLines: { color: col.grid }, horzLines: { color: col.grid } },
          rightPriceScale: { borderVisible: false, scaleMargins: { top: 0.12, bottom: 0.08 } },
          timeScale: { borderVisible: false, timeVisible: true, secondsVisible: false, rightOffset: 2,
            tickMarkFormatter: (t: unknown) => (typeof t === 'number' ? hhmm(t) : md(dayKey(t))) },
          crosshair: { mode: lc.CrosshairMode.Normal },
          localization: { locale: 'ko-KR', timeFormatter: (t: unknown) => (typeof t === 'number' ? hhmm(t) : md(dayKey(t))) },
        })
        const s0 = specRef.current
        let L: Live
        if (s0.kind === 'line') {
          // 세로 범위에 기준 0%, 전망 구간, 시가를 넣는다(가격선은 기본 자동 범위에 들지 않아 위아래가 잘렸다)
          const auto = (orig: () => { priceRange: { minValue: number; maxValue: number } | null } | null) => {
            const s = specRef.current, r = orig()?.priceRange
            const ex = s.kind === 'line' ? [0, ...(s.band ? [s.band.lo, s.band.hi] : []), ...(s.pin ? [s.pin.p] : [])] : [0]
            return { priceRange: { minValue: Math.min(...ex, r?.minValue ?? 0), maxValue: Math.max(...ex, r?.maxValue ?? 0) }, margins: { above: 24, below: 16 } }
          }
          const fmt = { type: 'custom' as const, minMove: 0.01, formatter: (p: number) => sg(p) }
          const main = chart.addSeries(lc.AreaSeries, { lineWidth: 2, priceLineVisible: false, lastValueVisible: true, priceFormat: fmt, autoscaleInfoProvider: auto })
          // 캔들: 국내 관례대로 오르면 빨강, 내리면 파랑(DESIGN.md 1절 등락색)
          const cand = s0.candles?.length ? chart.addSeries(lc.CandlestickSeries, {
            upColor: col.up, downColor: col.down, borderUpColor: col.up, borderDownColor: col.down, wickUpColor: col.up, wickDownColor: col.down,
            priceLineVisible: false, lastValueVisible: true, priceFormat: fmt, autoscaleInfoProvider: auto, visible: false,
          }) : undefined
          L = { lc, chart, main, cand, markers: lc.createSeriesMarkers(main, []), cmarkers: cand ? lc.createSeriesMarkers(cand, []) : undefined, lines: [], col, framed: '' }
          chart.subscribeCrosshairMove((pr) => {
            if (typeof pr.time === 'number') {
              const k = cand && viewRef.current.mode === 'candle' ? pr.seriesData.get(cand) as { open?: number; high?: number; low?: number; close?: number } | undefined : undefined
              if (k && k.close != null) { setLegend(candleText(pr.time, k as { open: number; high: number; low: number; close: number })); return }
              const v = (pr.seriesData.get(main) as { value?: number } | undefined)?.value
              if (v != null) { setLegend(lineText(pr.time, v)); return }
            }
            const { data } = lineData(specRef.current as Extract<BigSpec, { kind: 'line' }>)
            setLegend(data.length ? lineText(data[data.length - 1].time, data[data.length - 1].value) : '값 없음')
          })
        } else {
          // 예상 구간 막대: 캔들 몸통을 구간(시가=상단, 종가=하단)으로 쓴다. 오늘만 띠 색
          const bx = chart.addSeries(lc.CandlestickSeries, {
            upColor: col.grid, downColor: col.grid, borderVisible: true, borderUpColor: col.grid, borderDownColor: col.grid, wickVisible: false,
            priceLineVisible: false, lastValueVisible: false, priceFormat: { type: 'price', precision: 0, minMove: 1 },
          })
          const main = chart.addSeries(lc.LineSeries, { color: col.fg, lineWidth: 2, priceLineVisible: false, lastValueVisible: true,
            priceFormat: { type: 'price', precision: 2, minMove: 0.01 } })
          L = { lc, chart, main, box: bx, markers: lc.createSeriesMarkers(bx, []), lines: [], col, framed: '' }
          chart.subscribeCrosshairMove((pr) => {
            const s = specRef.current
            if (s.kind !== 'k20') return
            const r = s.rows.find((x) => x.date === dayKey(pr.time)) ?? s.rows[s.rows.length - 1]
            setLegend(r ? k20Text(r) : '')
          })
        }
        live.current = L
        update()
      } catch (e) {
        console.error(e); chart?.remove(); chart = null; live.current = null
        setErr('차트를 그리지 못했습니다. 창을 닫고 다시 열어 주세요.')
      }
    }, () => { if (!dead) setErr('차트를 불러오지 못했습니다. 네트워크를 확인하고 다시 열어 주세요.') })
    return () => { dead = true; live.current = null; chart?.remove() }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [spec.kind, spec.title, hasCandles])

  // 실시간 갱신과 선/봉, 분 단위 전환 — 데이터만 바꾼다
  const dataKey = spec.kind === 'line'
    ? JSON.stringify([spec.pts.length, spec.pts[spec.pts.length - 1], spec.band, spec.pin, spec.x0, spec.x1, spec.candles?.length, spec.candles?.[spec.candles.length - 1], mode, iv])
    : String(spec.rows.length)
  useEffect(() => {
    try { update() } catch (e) { console.error(e); setErr('차트를 새로 그리지 못했습니다. 창을 닫고 다시 열어 주세요.') }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dataKey])

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-stretch justify-center bg-scrim lg:items-center lg:p-8" onClick={() => history.back()}>
      <div ref={panel} role="dialog" aria-modal="true" aria-label={`${spec.title} 크게 보기`} onClick={(e) => e.stopPropagation()}
        className="flex h-full w-full flex-col bg-card lg:h-[min(680px,88vh)] lg:max-w-[1040px] lg:rounded-lg lg:shadow-xs">
        <div className="flex items-start justify-between gap-3 px-4 pb-2 pt-4 sm:px-6">
          <div className="min-w-0">
            <h2 className="text-headline1 font-bold text-fg">{spec.title}</h2>
            <p className="num mt-0.5 min-h-5 truncate text-label2 font-semibold text-fg-2">{legend}</p>
          </div>
          <Button ref={closeBtn} variant="assistive" size="small" onClick={() => history.back()} className="shrink-0">닫기</Button>
        </div>
        {hasCandles && (
          <div className="flex flex-wrap items-center gap-2 px-4 pb-2 sm:px-6">
            <Seg label="차트 모양" value={mode} onChange={setMode} items={[['candle', '봉'], ['line', '선']]} />
            {mode === 'candle' && <Seg label="봉 단위" value={iv} onChange={setIv} items={[[1, '1분'], [5, '5분']]} />}
          </div>
        )}
        <div className="relative min-h-0 flex-1 px-2 sm:px-4">
          <div ref={box} className="absolute inset-0 mx-2 sm:mx-4" />
          {err && <p role="alert" className="absolute inset-0 flex items-center justify-center bg-card px-6 text-center text-body2 text-fg-2">{err}</p>}
        </div>
        <p className="px-4 pb-4 pt-2 text-caption1 leading-snug text-fg-2 sm:px-6">
          {spec.note ? <>{spec.note}<br /></> : null}
          {hasCandles ? '봉은 오르면 빨강, 내리면 파랑. ' : ''}두 손가락이나 휠로 확대, 끌어서 이동. 차트 그림은 TradingView Lightweight Charts 입니다.
        </p>
      </div>
    </div>,
    document.body,
  )
}
