import type { DayData } from '../../types'
import { arrow, nf, sg } from '../../lib/fmt'
import { Card, CardHeader } from './ui/card'
import { tone } from '../lib/tone'

export function Market({ data }: { data: DayData }) {
  return (
    <Card aria-label="간밤 시장">
      <CardHeader title="간밤 시장" aside={data.global_tag} />
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
        {data.market.map((m) => (
          <div key={m.key} className="rounded-md p-3 ring-1 ring-line-2">
            <div className="text-caption1 font-semibold text-fg-2">{m.label}{m.asof && <small className="ml-1 text-fg-2">{m.asof}</small>}</div>
            <div className="num mt-0.5 text-headline1 font-bold text-fg">{m.close != null ? nf(m.close, m.key === 'USDKRW' ? 2 : 2) : '—'}</div>
            <div className={`num text-caption1 font-semibold ${tone(m.close != null ? m.pct : null)}`}>{m.close != null && m.pct != null ? arrow(m.pct) + sg(m.pct) : '미확보'}</div>
          </div>
        ))}
      </div>
    </Card>
  )
}
