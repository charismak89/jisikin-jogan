import type { DayData } from '../../types'
import { nf, sg } from '../../lib/fmt'
import { Card, CardHeader } from './ui/card'
import { tone } from '../lib/tone'

// 간밤 시장(2026-11-27 압축): 큰 숫자 타일 6개 → 3×3 작은 칸. 이름, 등락률(굵게), 종가 순.
// 순서는 render.py MARKET_ORDER(야간선물, SOX, 원달러 / 엔비디아, 마이크론, TSMC / DRAM, 앤트로픽, EWY).
// 등락률이 비고 asof 가 있으면(미국 휴장 뒤 참고 시세) '11/25 종가'처럼 그 날짜를 쓴다
export function Market({ data }: { data: DayData }) {
  return (
    <Card aria-label="간밤 시장">
      <CardHeader title="간밤 시장" aside={data.global_tag} />
      <div className="grid grid-cols-3 gap-1.5">
        {data.market.map((m) => {
          const has = m.close != null && m.pct != null
          return (
            <div key={m.key} className="min-w-0 rounded-md px-2.5 py-2 ring-1 ring-line-2">
              <div className="truncate text-caption1 font-semibold text-fg-2" title={m.key === 'K200N' && m.asof ? `${m.label} ${m.asof}` : m.label}>{m.label}</div>
              <div className={`num text-label1 font-bold ${tone(has ? m.pct : null)}`}>{has ? sg(m.pct as number) : m.close != null && m.asof ? m.asof : '미확보'}</div>
              <div className="num truncate text-caption1 text-fg-2">{m.close != null ? nf(m.close, 2) : '—'}</div>
            </div>
          )
        })}
      </div>
      {data.market.some((m) => m.key === 'K200N' && m.asof) && <p className="mt-2 text-caption1 text-fg-2">K200 야간 {data.market.find((m) => m.key === 'K200N')?.asof} 마감 · 미국 종목은 직전 미국장 종가</p>}
    </Card>
  )
}
