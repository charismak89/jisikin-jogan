// 밤 추종가(해외 24시간 추종가, Hyperliquid) — 발행일 정규장 마감(15:30) 대비 등락. 시험 화면 첫 카드용(2026-11-26).
// 실제 야간선물 시세가 아니다. 06:00 마감 시점 대조 29회(10/16~11/25)에서 평균 0.36%p, 최대 1.00%p 차이, 방향 27회 일치.
// 한국투자증권 API 로 실제 야간선물을 받게 되면 이 파일만 바꾼다(카드는 같은 Series 를 그린다).
import type { DayCfg, Pt } from '../types'

export interface Series { base: number | null; pts: Pt[]; last: number | null; lastT: number | null }

const POLL = 30e3

export class NightFeed {
  S: Record<string, Series> = {}
  ok: boolean | null = null
  version = 0
  private iv: [string, number]
  private next: Record<string, number> = {}
  private timer: number | undefined
  private listeners = new Set<() => void>()

  constructor(private D: DayCfg, readonly from: number) {
    // 하루 안이면 1분봉, 주말처럼 길면 5분봉(Hyperliquid 는 봉 5,000개까지 준다)
    this.iv = Date.now() - from < 30 * 3600e3 ? ['1m', 6e4] : ['5m', 3e5]
    D.ent.forEach((e) => { this.S[e.key] = { base: null, pts: [], last: null, lastT: null } })
  }
  subscribe(fn: () => void) { this.listeners.add(fn); return () => { this.listeners.delete(fn) } }
  private emit() { this.version++; this.listeners.forEach((f) => f()) }

  private load(key: string, coin: string) {
    const st = this.S[key], [name, ms] = this.iv, end = Date.now()
    const start = this.next[key] ?? this.from - 2 * ms
    return fetch(this.D.api, { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ type: 'candleSnapshot', req: { coin, interval: name, startTime: start, endTime: end } }) })
      .then((r) => { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json() })
      .then((cs: { t: number; c: string }[]) => {
        if (!Array.isArray(cs) || !cs.length) return
        if (st.base == null) {
          const b = cs.filter((c) => c.t + ms <= this.from)
          if (!b.length) throw new Error('기준 봉 없음')
          st.base = parseFloat(b[b.length - 1].c)
        }
        const base = st.base
        const m = new Map<number, Pt>(st.pts.map((p) => [p[0], p]))
        cs.filter((c) => c.t + ms > this.from).forEach((c) => {
          const t = Math.min(c.t + ms, end)
          m.delete(c.t + ms); m.set(t, [t, (parseFloat(c.c) / base - 1) * 100])
        })
        st.pts = [...m.values()].sort((a, b) => a[0] - b[0])
        const l = st.pts[st.pts.length - 1]
        if (l) { st.last = l[1]; st.lastT = l[0] }
        this.next[key] = cs[cs.length - 1].t   // 마지막 봉(진행 중)부터 다시 받는다
      })
  }
  tick = () => {
    if (document.hidden) return
    return Promise.all(this.D.ent.map((e) => this.load(e.key, e.coin)))
      .then(() => { this.ok = true }, () => { this.ok = false })
      .then(() => this.emit())
  }
  start() {
    this.tick()
    this.timer = window.setInterval(this.tick, POLL)
    const vis = () => { if (!document.hidden) this.tick() }
    document.addEventListener('visibilitychange', vis)
    return () => { window.clearInterval(this.timer); document.removeEventListener('visibilitychange', vis) }
  }
  /** t 시각 이전 마지막 값(야간선물 마감 06:00 시점 값 등) */
  at(key: string, t: number): number | null {
    const p = this.S[key].pts.filter((x) => x[0] <= t)
    return p.length ? p[p.length - 1][1] : null
  }
}
