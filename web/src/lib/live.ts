// v5 대시보드 스크립트(template-v5.html)의 실시간 부분을 옮긴 것. 동작은 같다.
//  - 해외 24시간 추종가: 브라우저가 Hyperliquid info API 를 15초마다 직접 부른다.
//  - KRX 실제 시세: 지인 링크(#k=키)로 한 번 열면 브라우저가 키를 기억하고 중계기에서 받는다. 실패하면 추종가로 그린다.
import type { Bar, DayCfg, Ent, Pt } from '../types'

interface Krx { pts: Bar[]; open: number | null; last?: number }
interface St { pts: Bar[]; openPx: number | null; openT?: number; base: number | null; path: Pt[]; krx: Krx | null }
type Iv = [string, number] | null

const now = () => Date.now()
const pctOf = (st: St, px: number) => (px / (st.base as number) - 1) * 100
const ivFor = (age: number): Iv => (age < 3.2 * 864e5 ? ['1m', 6e4] : age < 16 * 864e5 ? ['5m', 3e5] : age < 50 * 864e5 ? ['15m', 9e5] : null)

export function readRelayKey(): string | null {
  let rk: string | null = null
  try {
    const m = location.hash.match(/(?:^#|&)k=([A-Za-z0-9_\-]+)/)
    if (m) {
      rk = m[1]
      try { localStorage.setItem('jj-relay-key', rk) } catch { /* 저장 불가 환경 */ }
      history.replaceState(null, '', location.pathname + location.search)
    }
    if (!rk) rk = localStorage.getItem('jj-relay-key')
  } catch { /* 저장소 접근 불가 */ }
  return rk
}

export class Live {
  S: Record<string, St> = {}
  liveOK: boolean | null = null
  krxOK: boolean | null = null
  readonly isToday: boolean
  readonly isPast: boolean
  private lastIntra = 0
  private lastFull = 0
  private iv0: Iv
  private timer: number | undefined
  private listeners = new Set<() => void>()
  version = 0

  constructor(public D: DayCfg, public RK: string | null) {
    const today = new Date(now() + 9 * 3600e3).toISOString().slice(0, 10)
    this.isToday = today === D.issue
    this.isPast = today > D.issue
    this.iv0 = ivFor(now() - D.t_snap)
    D.ent.forEach((e) => { this.S[e.key] = { pts: [], openPx: null, base: e.base, path: e.path || [], krx: null } })
  }
  get KRX() { return !!(this.RK && this.D.relay) }
  subscribe(fn: () => void) { this.listeners.add(fn); return () => { this.listeners.delete(fn) } }
  private emit() { this.version++; this.listeners.forEach((f) => f()) }

  private post(body: unknown) {
    return fetch(this.D.api, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
      .then((r) => { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json() })
  }
  relayGet(path: string) {
    const D = this.D
    return fetch(D.relay + path + (path.indexOf('?') < 0 ? '?' : '&') + 'k=' + encodeURIComponent(this.RK as string), { cache: 'no-store' })
      .then((r) => { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json() })
  }

  private fetchBase(e: Ent) {
    const st = this.S[e.key], D = this.D
    if (st.base && st.path.length) return Promise.resolve()
    return this.post({ type: 'candleSnapshot', req: { coin: e.coin, interval: '15m', startTime: D.t_prev - 18e5, endTime: Math.min(now(), D.t_snap) } }).then((cs: { t: number; c: string }[]) => {
      const b = cs.filter((c) => c.t + 9e5 <= D.t_prev)
      if (!b.length) throw new Error('기준 없음')
      st.base = parseFloat(b[b.length - 1].c)
      st.path = cs.filter((c) => c.t + 9e5 >= D.t_prev && c.t + 9e5 <= D.t_snap).map((c) => [c.t + 9e5, pctOf(st, parseFloat(c.c))] as Pt)
    })
  }
  private fetchRange(e: Ent, from: number, iv: [string, number]) {
    const st = this.S[e.key], D = this.D, end = Math.min(now(), D.t_close + 6e4)
    return this.post({ type: 'candleSnapshot', req: { coin: e.coin, interval: iv[0], startTime: from, endTime: end } }).then((cs: { t: number; o: string; c: string }[]) => {
      const m: Record<number, Bar> = {}
      st.pts.forEach((p) => { m[p[2]] = p })
      cs.forEach((c) => {
        const t = Math.min(c.t + iv[1], now())
        m[c.t] = [t, pctOf(st, parseFloat(c.c)), c.t]
        if (c.t >= D.t_open && (st.openT == null || c.t < st.openT)) { st.openT = c.t; st.openPx = parseFloat(c.o) }
      })
      st.pts = Object.keys(m).map((k) => m[+k]).sort((a, b) => a[0] - b[0])
    })
  }
  private load(full: boolean) {
    if (!this.iv0) return Promise.reject(new Error('기록 보관 기간 지남'))
    const iv = this.iv0
    return Promise.all(this.D.ent.map((e) => this.fetchBase(e).then(() => {
      const st = this.S[e.key]
      const from = (full || !st.pts.length) ? this.D.t_snap : st.pts[st.pts.length - 1][2] - 2 * iv[1]
      return this.fetchRange(e, from, iv)
    })))
  }
  private loadKrx() {
    if (!this.KRX) return Promise.resolve()
    const D = this.D, jobs: Promise<unknown>[] = []
    const fresh = this.isToday && now() < D.t_close + 12e5
    if (!this.lastIntra || (fresh && now() - this.lastIntra > 6e4)) {
      jobs.push(this.relayGet('/v1/intraday?date=' + D.issue).then((r) => {
        this.lastIntra = now()
        D.ent.forEach((e) => {
          const it = (r.items || {})[e.key]
          if (!it) return
          const k = this.S[e.key].krx || (this.S[e.key].krx = { pts: [], open: null })
          k.pts = (it.bars || []).map((b: number[]) => [b[0], (b[1] / e.prev - 1) * 100, b[0]] as Bar)
          k.open = it.open != null ? (it.open / e.prev - 1) * 100 : null
        })
      }))
    }
    if (fresh) {
      jobs.push(this.relayGet('/v1/live').then((r) => {
        D.ent.forEach((e) => {
          const it = (r.items || {})[e.key]
          if (!it) return
          const k = this.S[e.key].krx || (this.S[e.key].krx = { pts: [], open: null })
          k.last = (it.last / e.prev - 1) * 100
        })
      }))
    }
    return Promise.all(jobs).then(() => { this.krxOK = true }, () => { this.krxOK = false })
  }

  tick = () => {
    if (document.hidden) return
    const full = now() - this.lastFull > 5 * 6e4
    if (full) this.lastFull = now()
    return Promise.all([
      this.load(full).then(() => { this.liveOK = true }, () => { this.liveOK = false }),
      this.loadKrx(),
    ]).then(() => this.emit())
  }
  start() {
    this.tick()
    if (this.isToday && now() < this.D.t_close + 12e5) {
      this.timer = window.setInterval(this.tick, 15000)
      document.addEventListener('visibilitychange', this.onVis)
    }
    return () => { window.clearInterval(this.timer); document.removeEventListener('visibilitychange', this.onVis) }
  }
  private onVis = () => { if (!document.hidden) this.tick() }

  // ---- 읽기 ----
  krxOf(e: Ent): Krx | null { const k = this.S[e.key].krx; return (this.KRX && this.krxOK !== false && k && k.pts) ? k : null }
  useKrx(e: Ent) {
    const k = this.krxOf(e), D = this.D
    return !!(k && (k.open != null || (k.last != null && (e.key !== 'KOSPI' || now() >= D.t_open)) || k.pts.some((p) => p[0] <= D.t_open)))
  }
  sessPts(e: Ent): Bar[] {
    const k = this.krxOf(e), D = this.D
    if (k) { const a = k.pts.filter((p) => p[0] > D.t_open && p[0] <= D.t_close + 6e4); if (a.length) return a }
    return this.S[e.key].pts.filter((p) => p[2] >= D.t_open && p[2] < D.t_close)
  }
  tailPts(e: Ent): (Bar | Pt)[] {
    const D = this.D
    let hl: Bar[] = this.S[e.key].pts.filter((p) => p[2] < D.t_open && p[0] > D.t_snap)
    const k = this.krxOf(e)
    if (k) {
      const pre = k.pts.filter((p) => p[0] <= D.t_open)   // NXT 프리마켓(08:00~) 실제가
      if (pre.length) hl = hl.filter((p) => p[0] < pre[0][0]).concat(pre)
    }
    return hl
  }
  lastPct(e: Ent): number | null {
    const st = this.S[e.key], k = this.krxOf(e), D = this.D
    if (k) {
      if (now() > D.t_close + 6e4) { const s = this.sessPts(e); if (s.length) return s[s.length - 1][1] }
      else if (k.last != null && (e.key !== 'KOSPI' || now() >= D.t_open)) return k.last
    }
    if (st.pts.length) return st.pts[st.pts.length - 1][1]
    if (st.path.length) return st.path[st.path.length - 1][1]
    return null
  }
  openPct(e: Ent): number | null {
    const st = this.S[e.key], k = this.krxOf(e)
    if (k && k.open != null) return k.open
    return st.openPx != null && st.base ? pctOf(st, st.openPx) : null
  }
}

export const band = (e: Ent, p: number) => ((e.lo as number) > p ? '아래' : (e.hi as number) < p ? '위' : '안')
