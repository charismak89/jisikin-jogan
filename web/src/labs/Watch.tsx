// 관심종목 탭(2026-11-27 실험실, 사용자 결정 "관심종목 계획대로 실험실에 진행").
// 키움 관심종목 화면처럼 종목명, 현재가, 등락(대비), 거래량 4열만 보인다. 종목 상세(다음 뎁스)는 아직 없다.
//  - 종목 목록은 중계기 /v1/stocks(토스 코스피, 코스닥 상장 종목). 이름이나 6자리 코드로 찾는다.
//  - 시세는 중계기 /v1/quotes 를 10초마다(이 탭을 보고 있고 창이 보일 때만). 최대 20종목.
//  - 목록은 로그인 없이 이 브라우저에 저장한다(localStorage jj-watch). 다른 브라우저로는 '목록 링크 복사'(#w=코드,코드)로 옮긴다.
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { DayData } from '../types'
import { nf } from '../lib/fmt'
import { tone } from './lib/tone'
import { Card, CardHeader, Cap } from './components/ui/card'
import { Button } from './components/ui/button'
import { cn } from './lib/cn'

export const WATCH_MAX = 20
const KEY = 'jj-watch'
const POLL = 10e3

type Item = [string, string]   // [코드, 이름]
type Stock = [string, string, string]   // [코드, 이름, 시장]
interface Quote { last: number | null; t?: string; base: number | null; base_src: string | null; vol: number | null; ref: string | null; chg?: number; pct?: number }

const load = (): Item[] => {
  try {
    const v = JSON.parse(localStorage.getItem(KEY) || '[]')
    return Array.isArray(v) ? v.filter((x) => Array.isArray(x) && typeof x[0] === 'string').slice(0, WATCH_MAX) : []
  } catch { return [] }
}
const save = (v: Item[]) => { try { localStorage.setItem(KEY, JSON.stringify(v)) } catch { /* 저장 불가 */ } }
/** 주소 #w=005930,000660 의 코드 */
export const hashCodes = () => {
  const m = /(?:^#|&)w=([0-9A-Za-z,]+)/.exec(location.hash)
  return m ? [...new Set(m[1].toUpperCase().split(',').filter((c) => /^[0-9A-Z]{6}$/.test(c)))] : []
}
const norm = (s: string) => s.replace(/\s+/g, '').toLowerCase()
const two = (n: number) => String(n).padStart(2, '0')
const hms = (t: number) => { const d = new Date(t + 9 * 3600e3); return `${two(d.getUTCHours())}:${two(d.getUTCMinutes())}:${two(d.getUTCSeconds())}` }
const sgn = (v: number, s: string) => (v > 0 ? '+' : v < 0 ? '−' : '') + s

export function Watch({ data }: { data: DayData }) {
  const relay = data.day.relay
  const [items, setItems] = useState<Item[]>(load)
  const [stocks, setStocks] = useState<Stock[] | null>(null)
  const [stocksErr, setStocksErr] = useState(false)
  const [q, setQ] = useState('')
  const [edit, setEdit] = useState(false)
  const [quotes, setQuotes] = useState<Record<string, Quote>>({})
  const [okAt, setOkAt] = useState<number | null>(null)
  const [fail, setFail] = useState(false)
  const [msg, setMsg] = useState('')
  const pending = useRef<string[]>(hashCodes())

  const update = useCallback((f: (v: Item[]) => Item[]) => setItems((v) => { const n = f(v).slice(0, WATCH_MAX); save(n); return n }), [])

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
    if (!stocks || !pending.current.length) return
    const by = new Map(stocks.map((s) => [s[0], s[1]]))
    const add = pending.current.filter((c) => by.has(c)).map((c) => [c, by.get(c) as string] as Item)
    pending.current = []
    if (add.length) {
      update((v) => [...v, ...add.filter((a) => !v.some((x) => x[0] === a[0]))])
      setMsg(`링크의 종목 ${add.length}개를 목록에 넣었습니다.`)
    }
    try { history.replaceState(null, '', location.pathname + location.search + '#watch') } catch { /* 무시 */ }
  }, [stocks, update])

  const codes = items.map((i) => i[0]).join(',')
  useEffect(() => {
    if (!relay || !codes) return
    let dead = false, timer: number | undefined
    const tick = () => {
      if (document.hidden) { timer = window.setTimeout(tick, POLL); return }
      fetch(relay + '/v1/quotes?symbols=' + codes, { cache: 'no-store' }).then((r) => { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json() })
        .then((j: { items: Record<string, Quote> }) => { if (dead) return; setQuotes((o) => ({ ...o, ...j.items })); setOkAt(Date.now()); setFail(false) },
          () => { if (!dead) setFail(true) })
        .finally(() => { if (!dead) timer = window.setTimeout(tick, POLL) })
    }
    tick()
    const vis = () => { if (!document.hidden) { window.clearTimeout(timer); tick() } }
    document.addEventListener('visibilitychange', vis)
    return () => { dead = true; window.clearTimeout(timer); document.removeEventListener('visibilitychange', vis) }
  }, [relay, codes])

  const hits = useMemo(() => {
    const k = norm(q)
    if (!k || !stocks) return []
    const up = k.toUpperCase()
    const out: Stock[] = []
    // 코드 앞자리, 이름 앞부분, 이름 안 순서로
    for (const pass of [(s: Stock) => s[0].startsWith(up), (s: Stock) => norm(s[1]).startsWith(k), (s: Stock) => norm(s[1]).includes(k)]) {
      for (const s of stocks) { if (out.length >= 8) break; if (pass(s) && !out.includes(s)) out.push(s) }
    }
    return out
  }, [q, stocks])

  const add = (s: Stock) => {
    if (items.some((i) => i[0] === s[0])) { setMsg(`${s[1]}은(는) 이미 목록에 있습니다.`); return }
    if (items.length >= WATCH_MAX) { setMsg(`최대 ${WATCH_MAX}종목까지 넣을 수 있습니다.`); return }
    update((v) => [...v, [s[0], s[1]]]); setQ(''); setMsg(`${s[1]}을(를) 넣었습니다.`)
  }
  const del = (c: string) => update((v) => v.filter((i) => i[0] !== c))
  const move = (i: number, d: -1 | 1) => update((v) => { const n = [...v], j = i + d; if (j < 0 || j >= n.length) return v; [n[i], n[j]] = [n[j], n[i]]; return n })
  const copy = () => {
    const url = location.origin + location.pathname + '#w=' + codes
    const done = () => setMsg('목록 링크를 복사했습니다. 다른 브라우저 주소창에 붙여 넣으세요.')
    navigator.clipboard?.writeText(url).then(done, () => window.prompt('이 주소를 복사하세요', url))
      ?? window.prompt('이 주소를 복사하세요', url)
  }

  if (!relay) return <Card className="text-center text-body2 text-fg-2">이 회차는 KRX 중계기 주소가 없어 관심종목 시세를 받을 수 없습니다.</Card>

  return (
    <div className="space-y-4">
      <Card aria-label="관심종목 검색">
        <CardHeader title="관심종목" aside={<span>{items.length}/{WATCH_MAX}</span>} />
        <label className="sr-only" htmlFor="watch-q">종목 이름이나 코드</label>
        <input id="watch-q" value={q} onChange={(e) => setQ(e.target.value)} autoComplete="off" inputMode="search"
          placeholder={stocksErr ? '종목 목록을 받지 못했습니다' : stocks ? '종목 이름이나 6자리 코드' : '종목 목록 받는 중…'} disabled={!stocks}
          className="h-11 w-full rounded-10 bg-fill px-3 text-body2 text-fg placeholder:text-fg-2 focus:outline-none focus:ring-2 focus:ring-focus" />
        {hits.length > 0 && (
          <ul className="mt-2 divide-y divide-line" aria-label="검색 결과">
            {hits.map((s) => (
              <li key={s[0]}>
                <button type="button" onClick={() => add(s)} className="flex min-h-11 w-full items-center justify-between gap-2 px-1 text-left">
                  <span className="min-w-0 truncate text-body2 font-semibold text-fg">{s[1]}</span>
                  <span className="num shrink-0 text-caption1 text-fg-2">{s[0]} · {s[2] === 'KOSPI' ? '코스피' : '코스닥'}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
        {q && stocks && !hits.length && <p className="mt-2 text-caption1 text-fg-2">맞는 종목이 없습니다.</p>}
        {msg && <p role="status" className="mt-2 text-caption1 text-fg-2">{msg}</p>}
      </Card>

      {items.length > 0 && (
        <Card aria-label="관심종목 시세" className="px-0 sm:px-0">
          <div className="mb-2 flex items-center justify-between gap-2 px-4 sm:px-6">
            <span className={cn('text-caption1', fail ? 'text-negative' : 'text-fg-2')}>
              {fail ? `시세를 못 받음${okAt ? ` · 마지막 ${hms(okAt)}` : ''}` : okAt ? `${hms(okAt)} 기준 · 10초마다` : '시세 받는 중…'}
            </span>
            <span className="flex shrink-0 gap-1.5">
              <Button variant="assistive" size="small" onClick={copy}>목록 링크 복사</Button>
              <Button variant="assistive" size="small" onClick={() => setEdit((e) => !e)} aria-pressed={edit}>{edit ? '완료' : '편집'}</Button>
            </span>
          </div>
          <table className="w-full table-fixed text-right">
            <thead>
              <tr className="border-y border-line text-caption1 text-fg-2">
                <th scope="col" className="w-[30%] py-2 pl-4 text-left font-semibold sm:pl-6">종목명</th>
                {edit ? <th scope="col" className="py-2 pr-4 font-semibold sm:pr-6">순서, 삭제</th> : <>
                  <th scope="col" className="w-[24%] py-2 font-semibold">현재가</th>
                  <th scope="col" className="w-[21%] py-2 font-semibold">등락(대비)</th>
                  <th scope="col" className="py-2 pr-4 font-semibold sm:pr-6">거래량</th></>}
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {items.map(([c, n], i) => {
                const k = quotes[c], p = k?.pct ?? null
                return (
                  <tr key={c}>
                    <th scope="row" className="py-2.5 pl-4 text-left font-normal sm:pl-6">
                      <div className="truncate text-label1 font-semibold text-fg sm:text-body2">{n}</div>
                      <div className="num text-caption1 text-fg-2">{c}</div>
                    </th>
                    {!edit && <>
                      <td className={cn('num py-2.5 text-label2 font-semibold sm:text-body2', tone(p))}>{k?.last != null ? nf(k.last) : '—'}</td>
                      <td className={cn('num py-2.5', tone(p))}>
                        <div className="text-label2 font-semibold sm:text-body2">{p != null ? sgn(p, Math.abs(p).toFixed(2) + '%') : '—'}</div>
                        <div className="text-caption1">{k?.chg != null ? sgn(k.chg, nf(Math.abs(k.chg))) : ''}</div>
                      </td></>}
                    <td className="num py-2.5 pr-4 text-label2 text-fg sm:pr-6 sm:text-body2">
                      {edit ? (
                        <span className="inline-flex gap-1.5">
                          <button type="button" aria-label={`${n} 위로`} disabled={i === 0} onClick={() => move(i, -1)} className="size-9 rounded-sm bg-fill text-fg disabled:opacity-40">↑</button>
                          <button type="button" aria-label={`${n} 아래로`} disabled={i === items.length - 1} onClick={() => move(i, 1)} className="size-9 rounded-sm bg-fill text-fg disabled:opacity-40">↓</button>
                          <button type="button" aria-label={`${n} 삭제`} onClick={() => del(c)} className="size-9 rounded-sm bg-fill font-bold text-negative">×</button>
                        </span>
                      ) : k?.vol != null ? nf(k.vol) : '—'}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
          <div className="px-4 sm:px-6">
            <Cap>현재가와 거래량은 KRX와 NXT 통합 값입니다. 등락(대비)은 직전 거래일 KRX 종가 기준입니다{Object.values(quotes).some((x) => x.base_src === 'nxt-1d') ? '(* 일부 종목은 KRX 종가를 못 받아 통합 종가 기준)' : ''}. 목록은 이 브라우저에만 저장됩니다. 다른 기기에서는 '목록 링크 복사'로 옮기세요.</Cap>
          </div>
        </Card>
      )}
      {!items.length && <Card className="text-center text-body2 text-fg-2">위에서 종목을 찾아 넣으면 현재가와 등락을 한눈에 봅니다.</Card>}
    </div>
  )
}
