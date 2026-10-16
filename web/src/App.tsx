import { useEffect, useMemo, useState } from 'react'
import * as Tabs from '@radix-ui/react-tabs'
import type { DayData } from './types'
import { Live, readRelayKey } from './lib/live'
import { Hero } from './components/Hero'
import { LiveChart } from './components/LiveChart'
import { K20Chart } from './components/K20Chart'
import { Market } from './components/Market'
import { BriefTab } from './components/BriefTab'
import { Feedback } from './components/Feedback'
import { Card } from './components/ui/card'

type Mode = 'system' | 'light' | 'dark'
const applyTheme = (m: Mode) => {
  const d = m === 'dark' || (m === 'system' && matchMedia('(prefers-color-scheme: dark)').matches)
  document.documentElement.setAttribute('data-jj', d ? 'dark' : 'light')
  document.documentElement.setAttribute('data-jj-mode', m)
}

function ThemeSwitch() {
  const [m, setM] = useState<Mode>(() => (document.documentElement.getAttribute('data-jj-mode') as Mode) || 'system')
  useEffect(() => {
    const mq = matchMedia('(prefers-color-scheme: dark)'), on = () => m === 'system' && applyTheme('system')
    mq.addEventListener('change', on)
    return () => mq.removeEventListener('change', on)
  }, [m])
  const set = (v: Mode) => { setM(v); try { localStorage.setItem('jj-theme', v) } catch { /* 저장 불가 */ } applyTheme(v) }
  return (
    <div role="group" aria-label="화면 테마" className="flex rounded-full bg-card p-0.5 text-[12px] font-semibold shadow-[var(--shadow)]">
      {([['system', '시스템'], ['light', '라이트'], ['dark', '다크']] as [Mode, string][]).map(([v, l]) => (
        <button key={v} type="button" aria-pressed={m === v} onClick={() => set(v)}
          className={`rounded-full px-2.5 py-1 ${m === v ? 'bg-brand text-white' : 'text-tx2'}`}>{l}</button>
      ))}
    </div>
  )
}

export default function App() {
  const [data, setData] = useState<DayData | null>(null)
  const [err, setErr] = useState('')
  const [tab, setTab] = useState(() => (location.hash === '#brief' ? 'brief' : 'dash'))

  useEffect(() => {
    fetch('../day.json', { cache: 'no-store' }).then((r) => { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json() })
      .then(setData, () => setErr('오늘 데이터(day.json)가 아직 없습니다. 다음 회차(평일 07:45) 발행부터 보입니다. 지금은 기존 화면을 이용해 주세요.'))
  }, [])
  const live = useMemo(() => (data ? new Live(data.day, readRelayKey()) : null), [data])
  useEffect(() => (live ? live.start() : undefined), [live])
  const go = (v: string) => { setTab(v); try { history.replaceState(null, '', v === 'brief' ? '#brief' : location.pathname + location.search) } catch { /* 무시 */ } window.scrollTo(0, 0) }

  return (
    <div className="mx-auto w-full max-w-[1120px] px-4 pb-16 pt-5 sm:px-6">
      <header className="mb-4 flex items-center justify-between gap-3">
        <div>
          <div className="text-[19px] font-extrabold tracking-tight text-tx">지식인 조간</div>
          <div className="text-[12px] text-tx3">반도체 · 메모리 개장 전 브리핑</div>
        </div>
        <ThemeSwitch />
      </header>
      {!data ? (
        <Card className="text-center text-[15px] text-tx2">{err || '불러오는 중…'}<div className="mt-3"><a className="font-bold text-brand" href="../">기존 화면으로 →</a></div></Card>
      ) : (
        <Tabs.Root value={tab} onValueChange={go}>
          <div className="mb-4 flex items-end justify-between gap-3">
            <div>
              <div className="text-[13px] font-semibold text-brand">제 {data.issue_no} 호 · 07:45 발행</div>
              <h1 className="text-[22px] font-extrabold tracking-tight text-tx">{data.date_label}</h1>
            </div>
            <div className="flex items-center gap-2">{live && live.KRX && <Feedback live={live} tab={tab} />}</div>
          </div>
          <Tabs.List aria-label="보기 전환" className="mb-4 flex gap-1 border-b border-line">
            {[['dash', '대시보드'], ['brief', '브리핑 전문']].map(([v, l]) => (
              <Tabs.Trigger key={v} value={v} className="-mb-px border-b-2 border-transparent px-3 py-2.5 text-[15px] font-bold text-tx3 data-[state=active]:border-tx data-[state=active]:text-tx">{l}</Tabs.Trigger>
            ))}
          </Tabs.List>
          <Tabs.Content value="dash">
            {/* 모바일은 한 열, PC(1024px~)는 2단: 왼쪽 전망·실시간, 오른쪽 20거래일·간밤 시장 */}
            <div className="grid gap-4 lg:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)] lg:items-start">
              <div className="space-y-4">
                <Hero data={data} onBrief={() => go('brief')} />
                {live && <LiveChart live={live} />}
              </div>
              <div className="space-y-4">
                <K20Chart data={data} />
                <Market data={data} />
                <p className="px-2 text-[12px] leading-relaxed text-tx3">{data.stock_note}</p>
              </div>
            </div>
          </Tabs.Content>
          <Tabs.Content value="brief"><BriefTab data={data} /></Tabs.Content>
          <p className="mt-6 px-2 text-center text-[12px] leading-relaxed text-tx3">개인 학습용 기록입니다. 투자 자문이나 매매 권유가 아니며, 모든 판단과 책임은 열람자 본인에게 있습니다. · <a className="underline" href="../">기존 화면(v5)</a></p>
        </Tabs.Root>
      )}
    </div>
  )
}
