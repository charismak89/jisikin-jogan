// 일정 탭(2026-11-27 실험실, 사용자 결정 "캘린더 1단계 계획대로, 간결하게").
// 토스증권(주 단위 줄 + 날짜별 목록 + 분류 칩), 앤트위키(분류, 출처 표기), 네이버(MY 종목만)를 참고해 줄였다.
//  - 시장 일정: 휴장(holidays.json), 장 시간 변경(market_hours.json), 코스피200 만기(둘째 목요일, 휴장이면 앞 영업일). 회차가 이미 쓰는 파일이다.
//  - 종목 일정: 중계기 /v1/events(DART 공시: IR 개최, 잠정실적, 배당 기준일과 지급일). 관심 그룹 전체의 국내 종목 + 삼성전자, SK하이닉스.
//  - 경제지표 발표 일정은 아직 없다(무료 소스 미정, 2단계).
import { useEffect, useMemo, useState } from 'react'
import type { DayData } from '../types'
import { kstDay } from '../lib/fmt'
import { site } from '../lib/site'
import { Card, Cap } from './components/ui/card'
import { Button } from './components/ui/button'
import { cn } from './lib/cn'
import { isKr, loadStore } from './Watch'
import { LAB } from './lab'

type Kind = 'MKT' | 'IR' | 'EARN' | 'DIV'
interface Ev { date: string; kind: Kind; title: string; name?: string; code?: string; rcept_no?: string; approx?: boolean }
type Filter = 'all' | 'mkt' | 'ir' | 'div'

const DOW = ['일', '월', '화', '수', '목', '금', '토']
const FILTERS: [Filter, string][] = [['all', '전체'], ['mkt', '시장'], ['ir', '실적·IR'], ['div', '배당']]
const match = (f: Filter, k: Kind) => f === 'all' || (f === 'mkt' ? k === 'MKT' : f === 'ir' ? k === 'IR' || k === 'EARN' : k === 'DIV')
// 분류 색: 시장은 브랜드, 실적·IR 은 주의색, 배당은 긍정색(DESIGN.md 의 등락색 빨강, 파랑은 쓰지 않는다)
const DOT: Record<Kind, string> = { MKT: 'bg-brand', IR: 'bg-cautionary', EARN: 'bg-cautionary', DIV: 'bg-positive' }
const KIND_L: Record<Kind, string> = { MKT: '시장', IR: '실적·IR', EARN: '실적·IR', DIV: '배당' }
const BASE_CODES = ['005930', '000660']

const toD = (s: string) => new Date(s + 'T00:00:00Z')
const iso = (d: Date) => d.toISOString().slice(0, 10)
const addDays = (s: string, n: number) => { const d = toD(s); d.setUTCDate(d.getUTCDate() + n); return iso(d) }
const dow = (s: string) => toD(s).getUTCDay()
const monday = (s: string) => addDays(s, -((dow(s) + 6) % 7))
/** 그달 몇째 주인지(월요일이 든 달 기준) */
const weekLabel = (mon: string) => { const d = toD(mon); return `${d.getUTCMonth() + 1}월 ${Math.floor((d.getUTCDate() - 1) / 7) + 1}주차` }

/** 그달 1일, 달 이동 */
const month1 = (s: string) => s.slice(0, 8) + '01'
const addMonths = (s: string, n: number) => { const d = toD(month1(s)); d.setUTCMonth(d.getUTCMonth() + n, 1); return iso(d) }

/** 시장 일정: 휴장, 장 시간 변경, 만기(둘째 목요일, 휴장이면 앞 영업일) */
function marketEvents(hol: Record<string, string>, hrs: Record<string, { open: string; close: string; why?: string }>, from: string, to: string): Ev[] {
  const out: Ev[] = []
  const isHol = (s: string) => dow(s) === 0 || dow(s) === 6 || s in hol
  for (const [d, v] of Object.entries(hol)) if (!d.startsWith('_') && d >= from && d <= to && dow(d) > 0 && dow(d) < 6) out.push({ date: d, kind: 'MKT', title: '국내 휴장' + (typeof v === 'string' && v.length < 20 && !v.includes('자동') ? ` (${v})` : '') })
  for (const [d, v] of Object.entries(hrs)) if (!d.startsWith('_') && d >= from && d <= to) out.push({ date: d, kind: 'MKT', title: `장 시간 변경 ${v.open}~${v.close}${v.why ? ` (${v.why})` : ''}` })
  for (let m = toD(from); m <= toD(to); m.setUTCMonth(m.getUTCMonth() + 1, 1)) {
    const first = iso(new Date(Date.UTC(m.getUTCFullYear(), m.getUTCMonth(), 1)))
    let e = addDays(first, ((4 - dow(first) + 7) % 7) + 7)   // 둘째 목요일
    while (isHol(e)) e = addDays(e, -1)
    const mm = toD(e).getUTCMonth() + 1
    if (e >= from && e <= to) out.push({ date: e, kind: 'MKT', title: [3, 6, 9, 12].includes(mm) ? '코스피200 선물, 옵션 동시 만기' : '코스피200 옵션 만기' })
  }
  return out
}

export function Schedule({ data }: { data: DayData }) {
  const relay = data.day.relay
  const today = kstDay(Date.now())
  const [mon, setMon] = useState(() => monday(today))
  // 주/월 전환(2026-11-27 실험실, 사용자 요청 '기본은 주간'). 월간은 날짜를 누르면 그날 일정만 아래에 보인다
  const [mode, setMode] = useState<'week' | 'month'>('week')
  const [ym, setYm] = useState(() => month1(today))
  const [sel, setSel] = useState(today)
  const [f, setF] = useState<Filter>('all')
  const [mkt, setMkt] = useState<Ev[]>([])
  const [dart, setDart] = useState<Ev[] | null>(null)
  const [dartErr, setDartErr] = useState('')

  // 관심 그룹 전체의 국내 종목(최대 30) — 이 탭을 열 때 한 번 읽는다
  const codes = useMemo(() => {
    const s = loadStore()
    return [...new Set([...BASE_CODES, ...s.g.flatMap((g) => g.items.map((i) => i[0]).filter(isKr))])].slice(0, 30)
  }, [])

  useEffect(() => {
    let dead = false
    const j = (p: string) => fetch(site(p), { cache: 'no-store' }).then((r) => (r.ok ? r.json() : {})).catch(() => ({}))
    Promise.all([j('holidays.json'), j('market_hours.json')]).then(([h, m]) => {
      if (!dead) setMkt(marketEvents(h, m, addDays(today, -60), addDays(today, 120)))
    })
    return () => { dead = true }
  }, [today])

  useEffect(() => {
    if (!relay) { setDart([]); setDartErr('중계기 주소가 없어 종목 일정을 받지 못했습니다.'); return }
    let dead = false
    fetch(relay + '/v1/events?symbols=' + codes.join(','), { cache: 'no-store' })
      .then((r) => { if (!r.ok) throw new Error(r.status === 503 ? 'DART 키가 중계기에 없습니다.' : 'HTTP ' + r.status); return r.json() })
      .then((j: { items: Ev[] }) => { if (!dead) setDart(j.items) }, (e: Error) => { if (!dead) { setDart([]); setDartErr('종목 일정을 받지 못했습니다' + (e.message.startsWith('DART') ? `(${e.message})` : '') + '.') } })
    return () => { dead = true }
  }, [relay, codes])

  const days = [0, 1, 2, 3, 4].map((i) => addDays(mon, i))
  const all = useMemo(() => [...mkt, ...(dart || [])], [mkt, dart])
  const inWeek = (d: string) => d >= days[0] && d <= days[4]
  const shown = all.filter((e) => inWeek(e.date) && match(f, e.kind))
  const byDay = days.map((d) => ({ d, evs: shown.filter((e) => e.date === d) }))
  const thisWeek = mon === monday(today)
  const isMonth = LAB && mode === 'month'
  // 월간 칸: 그달 1일이 든 주 월요일부터 마지막 날이 든 주 일요일까지
  const cells = useMemo(() => {
    if (!isMonth) return []
    const end = addDays(addMonths(ym, 1), -1), out: string[] = []
    for (let d = addDays(ym, -((dow(ym) + 6) % 7)); d <= end || dow(d) !== 1; d = addDays(d, 1)) out.push(d)
    return out
  }, [isMonth, ym])
  const selEvs = all.filter((e) => e.date === sel && match(f, e.kind))
  const goMonth = (n: number) => { const m = addMonths(ym, n); setYm(m); setSel(m === month1(today) ? today : m) }
  const setView = (m: 'week' | 'month') => {
    setMode(m)
    if (m === 'month') { const base = thisWeek ? today : mon; setYm(month1(base)); setSel(base) }
    else setMon(monday(sel))
  }

  return (
    <Card aria-label={isMonth ? '월간 일정' : '이번 주 일정'} className="px-0 sm:px-0">
      <div className="mb-3 flex items-center justify-between gap-2 px-4 sm:px-6">
        <h2 className="min-w-0 text-headline1 font-bold text-fg">{isMonth ? `${+ym.slice(5, 7)}월 일정` : `${weekLabel(mon)} 일정`}</h2>
        <span className="flex shrink-0 items-center gap-1.5">
          {LAB && (
            <span role="group" aria-label="보기" className="flex rounded-full bg-fill p-0.5">
              {(['week', 'month'] as const).map((m) => (
                <button key={m} type="button" aria-pressed={mode === m} onClick={() => setView(m)}
                  className={cn('min-h-8 rounded-full px-3 text-label2 font-semibold', mode === m ? 'bg-card text-fg shadow-xs' : 'text-fg-2')}>{m === 'week' ? '주' : '월'}</button>
              ))}
            </span>
          )}
          {isMonth ? <>
            <Button variant="assistive" size="small" aria-label="지난달" onClick={() => goMonth(-1)}>‹</Button>
            <Button variant="assistive" size="small" aria-label="다음 달" onClick={() => goMonth(1)}>›</Button>
          </> : <>
            <Button variant="assistive" size="small" aria-label="지난주" onClick={() => setMon(addDays(mon, -7))}>‹</Button>
            {!thisWeek && !LAB && <Button variant="assistive" size="small" onClick={() => setMon(monday(today))}>이번 주</Button>}
            <Button variant="assistive" size="small" aria-label="다음 주" onClick={() => setMon(addDays(mon, 7))}>›</Button>
          </>}
        </span>
      </div>
      {LAB && ((isMonth && ym !== month1(today)) || (!isMonth && !thisWeek)) && (
        <div className="-mt-1 mb-2 px-4 sm:px-6">
          <button type="button" className="text-label2 font-semibold text-fg-2 underline" onClick={() => { if (isMonth) { setYm(month1(today)); setSel(today) } else setMon(monday(today)) }}>{isMonth ? '이번 달로' : '이번 주로'}</button>
        </div>
      )}
      {isMonth && (
        <div className="border-y border-line px-2 py-2 sm:px-4">
          <div className="grid grid-cols-7 text-center text-caption1 text-fg-2">{['월', '화', '수', '목', '금', '토', '일'].map((x) => <span key={x}>{x}</span>)}</div>
          <div className="grid grid-cols-7">
            {cells.map((d) => {
              const out = d.slice(0, 7) !== ym.slice(0, 7)
              const ks = [...new Set(all.filter((e) => e.date === d && match(f, e.kind)).map((e) => DOT[e.kind]))]
              return (
                <button key={d} type="button" onClick={() => setSel(d)} aria-pressed={d === sel}
                  aria-label={`${+d.slice(5, 7)}월 ${+d.slice(8)}일 일정 ${ks.length ? '있음' : '없음'}`}
                  className={cn('flex flex-col items-center gap-0.5 py-1', out && 'opacity-40')}>
                  <span className={cn('num flex size-8 items-center justify-center rounded-full text-label1 font-semibold',
                    d === sel ? 'bg-inverse text-fg-inverse' : d === today ? 'ring-1 ring-fg text-fg' : dow(d) === 0 || dow(d) === 6 ? 'text-fg-2' : 'text-fg')}>{+d.slice(8)}</span>
                  <span className="flex h-1.5 gap-0.5">{ks.map((k) => <span key={k} className={cn('size-1.5 rounded-full', k)} />)}</span>
                </button>
              )
            })}
          </div>
        </div>
      )}
      {/* 주 단위 줄: 날짜마다 분류 점(앤트위키처럼). 누르면 그 날짜로 내려간다 */}
      {!isMonth && <div className="grid grid-cols-5 border-y border-line px-2 py-2 sm:px-4">
        {days.map((d) => {
          const ks = [...new Set(all.filter((e) => e.date === d && match(f, e.kind)).map((e) => DOT[e.kind]))]
          return (
            <a key={d} href={`#day-${d}`} onClick={(e) => { e.preventDefault(); document.getElementById(`day-${d}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' }) }}
              className="flex flex-col items-center gap-1 py-1" aria-label={`${+d.slice(8)}일 ${DOW[dow(d)]}요일 일정 ${ks.length ? '있음' : '없음'}`}>
              <span className="text-caption1 text-fg-2">{d === today ? '오늘' : DOW[dow(d)]}</span>
              <span className={cn('flex size-9 items-center justify-center rounded-full text-body2 font-bold num', d === today ? 'bg-inverse text-fg-inverse' : 'text-fg')}>{+d.slice(8)}</span>
              <span className="flex h-1.5 gap-1">{ks.map((k) => <span key={k} className={cn('size-1.5 rounded-full', k)} />)}</span>
            </a>
          )
        })}
      </div>}
      <div className="flex gap-1.5 overflow-x-auto px-4 py-3 sm:px-6" role="group" aria-label="분류">
        {FILTERS.map(([v, l]) => (
          <button key={v} type="button" aria-pressed={f === v} onClick={() => setF(v)}
            className={cn('min-h-9 shrink-0 rounded-full px-3 text-label2 font-semibold', f === v ? 'bg-inverse text-fg-inverse' : 'bg-fill text-fg-2')}>{l}</button>
        ))}
      </div>
      <div className="px-4 sm:px-6">
        {(isMonth ? [{ d: sel, evs: selEvs }] : byDay.filter((x) => x.evs.length || x.d === today)).map(({ d, evs }) => (
          <section key={d} id={`day-${d}`} className="scroll-mt-4 border-t border-line py-3 first:border-t-0">
            <h3 className="mb-2 flex items-center gap-2 text-label1 font-bold text-fg-2">
              {+d.slice(5, 7)}/{+d.slice(8)} {DOW[dow(d)]}{d === today && <span className="rounded bg-fill px-1.5 py-px text-caption1 font-semibold">오늘</span>}
            </h3>
            {!evs.length ? <p className="text-body2 text-fg-2">일정이 없어요</p> : (
              <ul className="space-y-2.5">
                {evs.map((e, i) => (
                  <li key={i} className="flex gap-2.5">
                    <span className={cn('mt-1.5 size-2 shrink-0 rounded-full', DOT[e.kind])} aria-hidden />
                    <div className="min-w-0">
                      <p className="text-body2 font-semibold text-fg">{e.name ? `${e.name} ` : ''}{e.title}{e.approx && <span className="font-normal text-fg-2">{LAB ? ' (공시일)' : ' (공시일, 날짜는 원문 확인)'}</span>}</p>
                      <p className="text-caption1 text-fg-2">{KIND_L[e.kind]}{e.rcept_no && <> · <a className="underline" href={`https://dart.fss.or.kr/dsaf001/main.do?rcpNo=${e.rcept_no}`} target="_blank" rel="noopener noreferrer">DART 공시</a></>}</p>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>
        ))}
        {!isMonth && !shown.length && !byDay.some((x) => x.d === today) && <p className="border-t border-line py-4 text-body2 text-fg-2">이번 주 일정이 없어요</p>}
        {dart == null && <p className="py-2 text-caption1 text-fg-2">종목 일정 받는 중…</p>}
        {dartErr && <p className="py-2 text-caption1 text-negative">{dartErr}</p>}
        {!LAB && <Cap>시장 일정은 휴장, 장 시간 변경, 코스피200 만기입니다. 종목 일정은 삼성전자, SK하이닉스와 관심 그룹의 국내 종목(최대 30)의 DART 공시에서 뽑았습니다(IR 개최, 잠정실적, 배당 기준일과 지급일). 날짜는 공시 원문에서 자동으로 읽어 틀릴 수 있으니 원문을 확인하세요. 경제지표 발표 일정은 아직 없습니다.</Cap>}
      </div>
    </Card>
  )
}
