// 실험실(labs, 처음 이름 stg) 앱. 메인 App.tsx 를 바탕으로 첫 화면만 바꾼다(2026-11-26).
//  - 머리말을 한 줄로 줄여 첫 카드가 첫 화면 위쪽에 오게 한다(390px 에서 메인은 카드가 약 230px 아래).
//  - 첫 카드(NowCard)는 시간대마다 바뀐다. 기존 전망 카드는 '오늘 브리핑 요약'으로 줄여 아래에 둔다.
//  - '예측 → 실시간' 카드(LiveChart)는 뺐다. 종목 선택과 종목별 전망 구간, 시가 채점은 첫 카드로 옮겼다(2026-11-26)
import { useEffect, useMemo, useState } from 'react'
import * as Tabs from '@radix-ui/react-tabs'
import type { DayData } from '../types'
import { Live, dropOldKey } from '../lib/live'
import { K20Chart } from '../components/K20Chart'
import { Market } from '../components/Market'
import { BriefTab } from '../components/BriefTab'
import { Feedback } from '../components/Feedback'
import { Card } from '../components/ui/card'
import { site, versions, vlabel } from '../lib/site'
import { dir, kstDay, md, sg } from '../lib/fmt'
import { NowCard } from './NowCard'
import { NightFeed } from './night'
import { frame } from './clock'

type Mode = 'system' | 'light' | 'dark'
const MODES: Mode[] = ['system', 'light', 'dark']
const MODE_L: Record<Mode, string> = { system: '시스템', light: '라이트', dark: '다크' }
const applyTheme = (m: Mode) => {
  const d = m === 'dark' || (m === 'system' && matchMedia('(prefers-color-scheme: dark)').matches)
  document.documentElement.setAttribute('data-jj', d ? 'dark' : 'light')
  document.documentElement.setAttribute('data-jj-mode', m)
}

/** 테마는 버튼 하나로 돌린다(시스템 → 라이트 → 다크). 메인의 세 칸 스위치가 모바일 머리말 오른쪽을 차지해서 줄였다 */
function ThemeButton() {
  const [m, setM] = useState<Mode>(() => (document.documentElement.getAttribute('data-jj-mode') as Mode) || 'system')
  useEffect(() => {
    const mq = matchMedia('(prefers-color-scheme: dark)'), on = () => m === 'system' && applyTheme('system')
    mq.addEventListener('change', on)
    return () => mq.removeEventListener('change', on)
  }, [m])
  const next = () => { const v = MODES[(MODES.indexOf(m) + 1) % 3]; setM(v); try { localStorage.setItem('jj-theme', v) } catch { /* 저장 불가 */ } applyTheme(v) }
  return (
    <button type="button" onClick={next} aria-label={`화면 테마: ${MODE_L[m]} (누르면 바뀜)`}
      className="rounded-full bg-card px-2.5 py-1.5 text-[12px] font-semibold text-tx2 shadow-[var(--shadow)]">테마 {MODE_L[m]}</button>
  )
}

/** 기존 전망 카드의 나머지(결론 3줄, 신호 칩, 브리핑 링크) */
function Summary({ data, onBrief }: { data: DayData; onBrief: () => void }) {
  const s = data.signals
  const chips: [string, number | null][] = [['야간선물', s.k200n_pct], ['EWY 시사', s.ewy_implied_pct], ['ADR 시사', s.adr_implied_pct]]
  return (
    <Card aria-label="오늘 브리핑 요약">
      <div className="mb-2 flex items-baseline justify-between gap-2">
        <h2 className="text-[17px] font-bold text-tx">오늘 브리핑 요약</h2>
        <span className="text-[12px] text-tx3">{md(data.issue)} 07:45</span>
      </div>
      <ol className="space-y-2.5">
        {data.concl.map((c, i) => (
          <li key={i} className="flex gap-3 text-[15px] leading-snug text-tx">
            <span className="mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full bg-brand-soft text-[12px] font-bold text-brand">{i + 1}</span>
            <span className="font-semibold">{c.h}</span>
          </li>
        ))}
      </ol>
      <div className="mt-4 flex flex-wrap gap-x-3 gap-y-1 border-t border-line pt-3 text-[12px] text-tx3">
        {chips.map(([l, v]) => <span key={l}>{l} <b className={`num ${dir(v)}`}>{v == null ? '미확보' : sg(v)}</b></span>)}
        <span>시사 = 미국에 상장된 한국 상품 등락을 코스피로 옮긴 값</span>
      </div>
      <button type="button" onClick={onBrief} className="mt-3 text-[13px] font-bold text-brand">근거와 시나리오는 브리핑에서 →</button>
    </Card>
  )
}

export default function App() {
  const [data, setData] = useState<DayData | null>(null)
  const [err, setErr] = useState('')
  const [tab, setTab] = useState(() => (location.hash === '#brief' ? 'brief' : 'dash'))

  useEffect(() => {
    fetch(site('day.json'), { cache: 'no-store' }).then((r) => { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json() })
      .then(setData, () => setErr('오늘 데이터(day.json)가 아직 없습니다. 다음 회차(평일 07:45) 발행부터 보입니다.'))
  }, [])
  useEffect(dropOldKey, [])
  const live = useMemo(() => (data ? new Live(data.day) : null), [data])
  useEffect(() => (live ? live.start() : undefined), [live])
  // 밤 추종가는 정규장 마감 뒤에만 받는다(장중과 장 전에는 부르지 않는다)
  // 페이지를 장중에 열어 두어도 마감 뒤 1분 안에 받기 시작한다
  const [feed, setFeed] = useState<NightFeed | null>(null)
  useEffect(() => {
    if (!data) return
    const chk = () => { if (Date.now() >= data.day.t_close) setFeed((f) => f ?? new NightFeed(data.day, frame(data.day, Date.now()).base)) }
    chk(); const id = window.setInterval(chk, 60e3)
    return () => window.clearInterval(id)
  }, [data])
  useEffect(() => (feed ? feed.start() : undefined), [feed])
  const past = !!data && kstDay(Date.now()) > data.issue
  const go = (v: string) => { setTab(v); try { history.replaceState(null, '', v === 'brief' ? '#brief' : location.pathname + location.search) } catch { /* 무시 */ } window.scrollTo(0, 0) }

  return (
    <>
      {/* 실험실 띠: 버전과 메인과의 관계. 두 버전이 같으면 메인과 같은 화면이다(web/versions.json) */}
      <div role="note" className="bg-tx px-4 py-1 text-center text-[11px] font-semibold text-bg">
        실험실 {vlabel(versions.labs)} · {versions.labs === versions.main ? '메인과 같은 화면입니다' : `개발 중인 화면이라 메인(${vlabel(versions.main)})과 다릅니다`}
      </div>
      <div className="mx-auto w-full max-w-[1120px] px-4 pb-16 pt-3 sm:px-6">
        <header className="mb-3 flex items-center justify-between gap-2">
          <div className="min-w-0">
            <div className="text-[17px] font-extrabold tracking-tight text-tx">지식인 조간</div>
            {data && <h1 className="truncate text-[12px] font-semibold text-tx3">제 {data.issue_no} 호 · {data.date_label}</h1>}
          </div>
          <div className="flex shrink-0 items-center gap-1.5">
            {live && live.KRX && <Feedback live={live} tab={tab} />}
            <ThemeButton />
          </div>
        </header>
        {!data ? (
          <Card className="text-center text-[15px] text-tx2">{err || '불러오는 중…'}<div className="mt-3"><a className="font-bold text-brand" href={site('archive/')}>지난 회차 보기 →</a></div></Card>
        ) : (
          <Tabs.Root value={tab} onValueChange={go}>
            <div className="mb-3 flex items-end gap-2 border-b border-line">
            <Tabs.List aria-label="보기 전환" className="flex gap-1">
              {[['dash', '대시보드'], ['brief', '브리핑 전문']].map(([v, l]) => (
                <Tabs.Trigger key={v} value={v} className="-mb-px border-b-2 border-transparent px-3 py-2 text-[15px] font-bold text-tx3 data-[state=active]:border-tx data-[state=active]:text-tx">{l}</Tabs.Trigger>
              ))}
            </Tabs.List>
              <a href={site('')} className="mb-1.5 ml-auto shrink-0 rounded-full bg-card px-2.5 py-1 text-[13px] font-bold text-tx2 shadow-[var(--shadow)]">메인으로</a>
            </div>
            <Tabs.Content value="dash">
              <div className="grid gap-4 lg:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)] lg:items-start">
                <div className="space-y-4">
                  {live && <NowCard data={data} live={live} feed={feed} onBrief={() => go('brief')} />}
                  <Summary data={data} onBrief={() => go('brief')} />
                </div>
                <div className="space-y-4">
                  <K20Chart data={data} />
                  <Market data={data} />
                  <p className="px-2 text-[12px] leading-relaxed text-tx3">{data.stock_note}</p>
                </div>
              </div>
            </Tabs.Content>
            <Tabs.Content value="brief"><BriefTab data={data} /></Tabs.Content>
            {past && <p className="mt-4 px-2 text-center text-[12px] text-tx3">{md(data.issue)} 회차가 마지막 발행입니다.</p>}
            <p className="mt-6 px-2 text-center text-[12px] leading-relaxed text-tx3">개인 학습용 기록입니다. 투자 자문이나 매매 권유가 아니며, 모든 판단과 책임은 열람자 본인에게 있습니다. · <a className="underline" href={site('archive/')}>지난 회차</a> · 실험실 {vlabel(versions.labs)}</p>
          </Tabs.Root>
        )}
      </div>
    </>
  )
}
