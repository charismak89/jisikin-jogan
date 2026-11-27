// 관심종목 탭(2026-11-27 실험실, 사용자 결정 "관심종목 계획대로 실험실에 진행").
// 키움 관심종목 화면처럼 종목명, 현재가, 등락(대비), 거래량 4열만 보인다. 종목 상세(다음 뎁스)는 아직 없다.
//  - 종목 목록은 중계기 /v1/stocks(토스 코스피, 코스닥 상장 종목). 이름이나 6자리 코드로 찾는다.
//  - 시세는 중계기 /v1/quotes 를 10초마다(이 탭을 보고 있고 창이 보일 때만). 최대 20종목.
//  - 목록은 로그인 없이 이 브라우저에 저장한다(localStorage jj-watch2, 그룹 여러 개). 다른 브라우저로는 '링크 복사'(#w=코드,코드)로 지금 그룹을 옮긴다.
//  - 2026-11-27 사용자 요청: 그룹 여러 개(최대 10), 미국 종목(NYSE, NASDAQ, AMEX — 검색 창을 열 때 목록을 받는다).
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { createPortal } from 'react-dom'
import type { DayData } from '../types'
import { nf } from '../lib/fmt'
import { tone } from './lib/tone'
import { Card, Cap } from './components/ui/card'
import { Button } from './components/ui/button'
import { cn } from './lib/cn'

export const WATCH_MAX = 20
export const GROUP_MAX = 10
const KEY = 'jj-watch2', OLD_KEY = 'jj-watch'
const POLL = 10e3

type Item = [string, string, string?]   // [코드, 이름, 시장]
type Stock = [string, string, string]   // [코드, 이름, 시장]
interface Group { n: string; items: Item[] }
interface Store { g: Group[]; cur: number }
interface Quote { last: number | null; t?: string; cur?: string | null; base: number | null; base_src: string | null; vol: number | null; amt?: number | null; ref: string | null; chg?: number; pct?: number }

const items0 = (v: unknown): Item[] => (Array.isArray(v) ? v.filter((x) => Array.isArray(x) && typeof x[0] === 'string').slice(0, WATCH_MAX) : [])
/** 저장된 그룹. 옛 단일 목록(jj-watch)은 '관심 1' 로 옮긴다 */
export const loadStore = (): Store => {
  try {
    const v = JSON.parse(localStorage.getItem(KEY) || 'null')
    if (v && Array.isArray(v.g) && v.g.length) {
      const g = v.g.slice(0, GROUP_MAX).map((x: Group, i: number) => ({ n: String(x?.n || `관심 ${i + 1}`).slice(0, 12), items: items0(x?.items) }))
      return { g, cur: Math.min(Math.max(0, +v.cur || 0), g.length - 1) }
    }
    return { g: [{ n: '관심 1', items: items0(JSON.parse(localStorage.getItem(OLD_KEY) || '[]')) }], cur: 0 }
  } catch { return { g: [{ n: '관심 1', items: [] }], cur: 0 } }
}
const saveStore = (v: Store) => { try { localStorage.setItem(KEY, JSON.stringify(v)) } catch { /* 저장 불가 */ } }
export const isKr = (c: string) => c.length === 6 && /^\d/.test(c)
const CODE_RE = /^[0-9A-Z][0-9A-Z.-]{0,9}$/
/** 주소 #w=005930,NVDA 의 코드 */
export const hashCodes = () => {
  const m = /(?:^#|&)w=([0-9A-Za-z.,-]+)/.exec(location.hash)
  return m ? [...new Set(m[1].toUpperCase().split(',').filter((c) => CODE_RE.test(c)))] : []
}
const MK_L: Record<string, string> = { KOSPI: '코스피', KOSDAQ: '코스닥', NYSE: 'NYSE', NASDAQ: '나스닥', AMEX: 'AMEX' }
const norm = (s: string) => s.replace(/\s+/g, '').toLowerCase()
const two = (n: number) => String(n).padStart(2, '0')
const hms = (t: number) => { const d = new Date(t + 9 * 3600e3); return `${two(d.getUTCHours())}:${two(d.getUTCMinutes())}:${two(d.getUTCSeconds())}` }
/** 거래대금(2026-11-27 실험실). 중계기 amt 가 없거나 거래량 × 현재가와 3배 넘게 어긋나면 어림값(approx) */
const amtOf = (k: Quote | undefined): { v: number; approx: boolean } | null => {
  if (!k || k.vol == null || k.last == null) return k?.amt != null ? { v: k.amt, approx: false } : null
  const est = k.vol * k.last
  if (k.amt != null && (!(est > 0) || (k.amt / est > 1 / 3 && k.amt / est < 3))) return { v: k.amt, approx: false }
  return est > 0 ? { v: est, approx: true } : null
}
/** 원은 조, 억, 만. 달러는 B, M, K */
const money = (v: number, kr: boolean) => {
  const a = Math.abs(v)
  if (kr) return a >= 1e12 ? `${nf(a / 1e12, a >= 1e13 ? 0 : 1)}조` : a >= 1e8 ? `${nf(Math.round(a / 1e8))}억` : `${nf(Math.round(a / 1e4))}만`
  return a >= 1e9 ? `$${nf(a / 1e9, 1)}B` : a >= 1e6 ? `$${nf(Math.round(a / 1e6))}M` : `$${nf(Math.round(a / 1e3))}K`
}
const sgn = (v: number, s: string) => (v > 0 ? '+' : v < 0 ? '−' : '') + s

export function Watch({ data }: { data: DayData }) {
  const relay = data.day.relay
  const [store, setStore] = useState<Store>(loadStore)
  const items = store.g[store.cur].items
  const [stocks, setStocks] = useState<Stock[] | null>(null)
  const [us, setUs] = useState<Stock[] | null>(null)
  const [stocksErr, setStocksErr] = useState(false)
  const [q, setQ] = useState('')
  const [edit, setEdit] = useState(false)
  const [adding, setAdding] = useState(false)
  const closeAdd = useCallback(() => { setAdding(false); setQ('') }, [])
  const [quotes, setQuotes] = useState<Record<string, Quote>>({})
  const [okAt, setOkAt] = useState<number | null>(null)
  const [fail, setFail] = useState(false)
  const [msg, setMsg] = useState('')
  const pending = useRef<string[]>(hashCodes())

  const setS = useCallback((f: (v: Store) => Store) => setStore((v) => { const n = f(v); saveStore(n); return n }), [])
  const update = useCallback((f: (v: Item[]) => Item[]) => setS((v) => ({ ...v, g: v.g.map((x, i) => (i === v.cur ? { ...x, items: f(x.items).slice(0, WATCH_MAX) } : x)) })), [setS])

  // 미국 종목 목록은 검색 창을 열 때(또는 링크에 미국 종목이 있을 때) 받는다
  const needUs = adding || pending.current.some((c) => !isKr(c))
  useEffect(() => {
    if (!relay || !needUs || us) return
    fetch(relay + '/v1/stocks?mk=us').then((r) => { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json() })
      .then((j: { items: Stock[] }) => setUs(j.items), () => setUs([]))
  }, [relay, needUs, us])
  const all = useMemo(() => (stocks ? [...stocks, ...(us || [])] : null), [stocks, us])

  // 종목 목록. 응답이 크니(약 100KB) 브라우저 캐시를 쓴다(중계기가 max-age 1시간)
  useEffect(() => {
    if (!relay) return
    let dead = false
    fetch(relay + '/v1/stocks').then((r) => { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json() })
      .then((j: { items: Stock[] }) => { if (!dead) setStocks(j.items) }, () => { if (!dead) setStocksErr(true) })
    return () => { dead = true }
  }, [relay])

  // 링크로 받은 목록(#w=)은 종목 목록이 오면 이름을 붙여 지금 목록 뒤에 더한다
  useEffect(() => {
    if (!all || !pending.current.length || (pending.current.some((c) => !isKr(c)) && !us)) return
    const by = new Map(all.map((s) => [s[0], s]))
    const add = pending.current.filter((c) => by.has(c)).map((c) => { const s = by.get(c)!; return [c, s[1], s[2]] as Item })
    pending.current = []
    if (add.length) {
      update((v) => [...v, ...add.filter((a) => !v.some((x) => x[0] === a[0]))])
      setMsg(`링크의 종목 ${add.length}개를 목록에 넣었습니다.`)
    }
    try { history.replaceState(null, '', location.pathname + location.search + '#watch') } catch { /* 무시 */ }
  }, [all, us, update])

  const codes = items.map((i) => i[0]).join(',')
  useEffect(() => {
    if (!relay || !codes) return
    let dead = false, busy = false, timer: number | undefined
    const tick = () => {
      window.clearTimeout(timer)
      if (busy) return   // 받는 중이면 끝난 뒤 다음 타이머가 건다(창을 다시 볼 때 루프가 둘이 되지 않게)
      if (document.hidden) { timer = window.setTimeout(tick, POLL); return }
      busy = true
      fetch(relay + '/v1/quotes?symbols=' + codes, { cache: 'no-store' }).then((r) => { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json() })
        .then((j: { items: Record<string, Quote> }) => { if (dead) return; setQuotes((o) => ({ ...o, ...j.items })); setOkAt(Date.now()); setFail(false) },
          () => { if (!dead) setFail(true) })
        .finally(() => { busy = false; if (!dead) timer = window.setTimeout(tick, POLL) })
    }
    tick()
    const vis = () => { if (!document.hidden) tick() }
    document.addEventListener('visibilitychange', vis)
    return () => { dead = true; window.clearTimeout(timer); document.removeEventListener('visibilitychange', vis) }
  }, [relay, codes])

  const hits = useMemo(() => {
    const k = norm(q)
    if (!k || !all) return []
    const up = k.toUpperCase()
    const out: Stock[] = []
    // 코드(티커) 같음, 코드 앞자리, 이름 앞부분, 이름 안 순서로
    for (const pass of [(s: Stock) => s[0] === up, (s: Stock) => s[0].startsWith(up), (s: Stock) => norm(s[1]).startsWith(k), (s: Stock) => norm(s[1]).includes(k)]) {
      for (const s of all) { if (out.length >= 8) break; if (pass(s) && !out.includes(s)) out.push(s) }
    }
    return out
  }, [q, all])

  const add = (s: Stock) => {
    if (items.some((i) => i[0] === s[0])) { setMsg(`${s[1]}은(는) 이미 목록에 있습니다.`); return }
    if (items.length >= WATCH_MAX) { setMsg(`최대 ${WATCH_MAX}종목까지 넣을 수 있습니다.`); return }
    update((v) => [...v, [s[0], s[1], s[2]]]); setQ(''); setMsg(`${s[1]}을(를) 넣었습니다.`)
  }
  const del = (c: string) => update((v) => v.filter((i) => i[0] !== c))
  const move = (i: number, d: -1 | 1) => update((v) => { const n = [...v], j = i + d; if (j < 0 || j >= n.length) return v; [n[i], n[j]] = [n[j], n[i]]; return n })
  const pick = (i: number) => { setS((v) => ({ ...v, cur: i })); setQuotes({}); setOkAt(null); setMsg('') }
  const addGroup = () => {
    if (store.g.length >= GROUP_MAX) { setMsg(`그룹은 ${GROUP_MAX}개까지 만들 수 있습니다.`); return }
    const n = (window.prompt('새 그룹 이름(12자까지)', `관심 ${store.g.length + 1}`) || '').trim().slice(0, 12)
    if (!n) return
    setS((v) => ({ g: [...v.g, { n, items: [] }], cur: v.g.length })); setQuotes({}); setOkAt(null); setMsg(`'${n}' 그룹을 만들었습니다.`)
  }
  const renameGroup = () => {
    const n = (window.prompt('그룹 이름(12자까지)', store.g[store.cur].n) || '').trim().slice(0, 12)
    if (n) setS((v) => ({ ...v, g: v.g.map((x, i) => (i === v.cur ? { ...x, n } : x)) }))
  }
  const delGroup = () => {
    if (store.g.length < 2) { setMsg('그룹이 하나뿐이라 지울 수 없습니다.'); return }
    if (!window.confirm(`'${store.g[store.cur].n}' 그룹과 그 안의 종목 ${items.length}개를 지웁니다.`)) return
    setS((v) => ({ g: v.g.filter((_, i) => i !== v.cur), cur: 0 })); setEdit(false)
  }
  const copy = () => {
    const url = location.origin + location.pathname + '#w=' + codes
    const done = () => setMsg('목록 링크를 복사했습니다. 다른 브라우저 주소창에 붙여 넣으세요.')
    navigator.clipboard?.writeText(url).then(done, () => window.prompt('이 주소를 복사하세요', url))
      ?? window.prompt('이 주소를 복사하세요', url)
  }

  if (!relay) return <Card className="text-center text-body2 text-fg-2">이 회차는 KRX 중계기 주소가 없어 관심종목 시세를 받을 수 없습니다.</Card>

  const anyApprox = items.some(([c]) => amtOf(quotes[c])?.approx)
  const status = fail ? `시세를 못 받음${okAt ? ` · 마지막 ${hms(okAt)}` : ''}` : okAt ? `${hms(okAt)} 기준 · 10초마다 갱신` : '시세 받는 중…'
  return (
    <div className="space-y-4">
      {/* 목록이 맨 위(2026-11-27 사용자 피드백). 기능 단추는 카드 머리에, 갱신 시각은 맨 아래 */}
      <Card aria-label="관심종목" className="px-0 sm:px-0">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2 px-4 sm:px-6">
          <h2 className="text-headline1 font-bold text-fg">관심종목</h2>
          <span className="flex shrink-0 gap-1.5">
            <Button variant="assistive" size="small" onClick={() => { setAdding(true); setEdit(false); setMsg('') }}>+ 추가</Button>
            <Button variant="assistive" size="small" onClick={() => setEdit((e) => !e)} aria-pressed={edit}>{edit ? '완료' : '편집'}</Button>
            {items.length > 0 && <Button variant="assistive" size="small" onClick={copy}>링크 복사</Button>}
          </span>
        </div>
        <div className="mb-3 flex gap-1.5 overflow-x-auto px-4 pb-1 sm:px-6" role="group" aria-label="관심 그룹">
          {store.g.map((g, i) => (
            <button key={i} type="button" aria-pressed={i === store.cur} onClick={() => pick(i)}
              className={cn('min-h-9 shrink-0 rounded-full px-3 text-label2 font-semibold', i === store.cur ? 'bg-inverse text-fg-inverse' : 'bg-fill text-fg-2')}>
              {g.n} <span className="num">{g.items.length}</span>
            </button>
          ))}
          {store.g.length < GROUP_MAX && <button type="button" onClick={addGroup} className="min-h-9 shrink-0 rounded-full bg-fill px-3 text-label2 font-semibold text-fg-2" aria-label="그룹 추가">+ 그룹</button>}
        </div>
        {edit && <div className="mb-3 flex gap-1.5 px-4 sm:px-6">
          <Button variant="assistive" size="small" onClick={renameGroup}>그룹 이름 바꾸기</Button>
          <Button variant="assistive" size="small" onClick={delGroup}>그룹 삭제</Button>
        </div>}
        {msg && !adding && <p role="status" className="mb-2 px-4 text-caption1 text-fg-2 sm:px-6">{msg}</p>}
        {items.length > 0 ? (
          <table className="w-full table-fixed text-right">
            <thead>
              <tr className="border-y border-line text-caption1 text-fg-2">
                <th scope="col" className={'w-[37%] py-2 pl-4 text-left font-semibold sm:pl-6'}>종목명</th>
                {edit ? <th scope="col" className="py-2 pr-4 font-semibold sm:pr-6">순서, 삭제</th> : <>
                  <th scope="col" className={'w-[20%] py-2 font-semibold'}>현재가</th>
                  <th scope="col" className="w-[19%] py-2 font-semibold">등락</th>
                  <th scope="col" className={cn("py-2 pr-4 font-semibold sm:pr-6", !edit && "whitespace-nowrap pl-2")}>거래대금{anyApprox && '*'}</th></>}
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {items.map(([c, n, mk], i) => {
                const k = quotes[c], p = k?.pct ?? null, kr = isKr(c), dp = kr ? 0 : 2
                return (
                  <tr key={c}>
                    <th scope="row" className="py-2.5 pl-4 text-left font-normal sm:pl-6">
                      <div className={'line-clamp-2 break-all text-label2 font-semibold leading-tight text-fg sm:text-body2'}>{n}</div>
                      <div className="num text-caption1 text-fg-2">{c}{!kr && ` · ${MK_L[mk || ''] || '미국'}`}</div>
                    </th>
                    {!edit && <>
                      <td className={cn('num py-2.5 text-caption1 font-semibold sm:text-body2', tone(p))}>{k?.last != null ? nf(k.last, dp) : '—'}</td>
                      <td className={cn('num py-2.5', tone(p))}>
                        <div className={'text-caption1 font-semibold sm:text-body2'}>{p != null ? sgn(p, Math.abs(p).toFixed(2) + '%') : '—'}</div>
                        <div className="text-caption1">{k?.chg != null ? sgn(k.chg, nf(Math.abs(k.chg), dp)) : ''}</div>
                      </td></>}
                    <td className={cn('num py-2.5 pr-4 sm:pr-6 sm:text-body2', !edit ? 'pl-2 text-caption1 text-fg-2' : 'text-label2 text-fg')}>
                      {edit ? (
                        <span className="inline-flex gap-1.5">
                          <button type="button" aria-label={`${n} 위로`} disabled={i === 0} onClick={() => move(i, -1)} className="size-9 rounded-sm bg-fill text-fg disabled:opacity-40">↑</button>
                          <button type="button" aria-label={`${n} 아래로`} disabled={i === items.length - 1} onClick={() => move(i, 1)} className="size-9 rounded-sm bg-fill text-fg disabled:opacity-40">↓</button>
                          <button type="button" aria-label={`${n} 삭제`} onClick={() => del(c)} className="size-9 rounded-sm bg-fill font-bold text-negative">×</button>
                        </span>
                      ) : (() => { const a = amtOf(k); return a ? money(a.v, kr) : '—' })()}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        ) : (
          <div className="border-t border-line px-4 pt-6 text-center sm:px-6">
            <p className="text-body2 text-fg-2">'+ 추가'로 종목을 넣으세요.</p>
          </div>
        )}
        <div className="border-t border-line px-4 sm:px-6">
          {items.length > 0 && <p className={cn('mt-3 text-caption1 font-semibold', fail ? 'text-negative' : 'text-fg-2')}>{status}</p>}
          <Cap>KRX+NXT 통합 · 등락은 전일 KRX 종가 대비{Object.values(quotes).some((x) => x.base_src === 'nxt-1d') ? '(일부 통합 종가)' : ''}{anyApprox ? ' · * 거래량×현재가 어림' : ''}</Cap>
        </div>
      </Card>

      {adding && <AddSheet onClose={closeAdd}>
        <label className="sr-only" htmlFor="watch-q">종목 이름이나 코드</label>
        <input id="watch-q" autoFocus value={q} onChange={(e) => setQ(e.target.value)} autoComplete="off" inputMode="search"
          placeholder={stocksErr ? '종목 목록을 받지 못했습니다' : stocks ? '종목 이름, 6자리 코드, 미국 티커' : '종목 목록 받는 중…'} disabled={!stocks}
          className="h-11 w-full rounded-10 bg-fill px-3 text-body2 text-fg placeholder:text-fg-2 focus:outline-none focus:ring-2 focus:ring-focus" />
        {msg && <p role="status" className="mt-2 text-caption1 text-fg-2">{msg}</p>}
        {hits.length > 0 && (
          <ul className="mt-2 divide-y divide-line" aria-label="검색 결과">
            {hits.map((s) => {
              const has = items.some((i) => i[0] === s[0])
              return (
                <li key={s[0]}>
                  <button type="button" onClick={() => add(s)} disabled={has} className="flex min-h-11 w-full items-center justify-between gap-2 px-1 text-left disabled:opacity-50">
                    <span className="min-w-0 truncate text-body2 font-semibold text-fg">{s[1]}</span>
                    <span className="num shrink-0 text-caption1 text-fg-2">{has ? '목록에 있음' : `${s[0]} · ${MK_L[s[2]] || s[2]}`}</span>
                  </button>
                </li>
              )
            })}
          </ul>
        )}
        {q && stocks && !us && <p className="mt-2 text-caption1 text-fg-2">미국 종목 목록 받는 중…</p>}
        {q && stocks && !hits.length && <p className="mt-2 text-caption1 text-fg-2">맞는 종목이 없습니다.</p>}
      </AddSheet>}
    </div>
  )
}

/** 종목 추가 창: 모바일은 아래에서 올라오는 시트, 넓은 화면은 가운데 창. Esc, 바깥 누르기, 닫기 단추로 닫는다 */
function AddSheet({ onClose, children }: { onClose: () => void; children: ReactNode }) {
  const box = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const back = document.activeElement as HTMLElement | null
    // 입력창이 아직 꺼져 있으면(종목 목록 받는 중) autoFocus 가 안 먹으니 창 자체로
    if (!box.current?.contains(document.activeElement)) box.current?.focus()
    const k = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
      if (e.key === 'Tab' && box.current) {   // Tab 은 창 안에서만 돈다
        const f = [...box.current.querySelectorAll<HTMLElement>('button:not([disabled]), input:not([disabled])')]
        if (!f.length) return
        const i = f.indexOf(document.activeElement as HTMLElement)
        e.preventDefault(); f[(i + (e.shiftKey ? -1 : 1) + f.length) % f.length].focus()
      }
    }
    window.addEventListener('keydown', k)
    const ov = document.body.style.overflow; document.body.style.overflow = 'hidden'
    return () => { window.removeEventListener('keydown', k); document.body.style.overflow = ov; back?.focus?.() }
  }, [onClose])
  return createPortal(
    // 바깥을 '눌렀을 때'만 닫는다(입력창에서 끌어 선택하다 바깥에서 놓아도 닫히지 않게)
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-scrim sm:items-center sm:p-8" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose() }}>
      <div ref={box} tabIndex={-1} role="dialog" aria-modal="true" aria-label="관심종목 추가"
        className="flex max-h-[85dvh] w-full outline-none flex-col rounded-t-lg bg-card px-4 pb-6 pt-4 shadow-xs sm:max-w-[480px] sm:rounded-lg sm:px-6">
        <div className="mb-3 flex items-center justify-between gap-2">
          <h2 className="text-headline1 font-bold text-fg">관심종목 추가</h2>
          <Button variant="assistive" size="small" onClick={onClose}>닫기</Button>
        </div>
        <div className="min-h-0 overflow-y-auto">{children}</div>
      </div>
    </div>,
    document.body,
  )
}
