// 첫 카드의 시간대 판단(2026-11-26, 시험 화면). 기준은 day.json 발행일(issue)과 그날 정규장 시각(t_open, t_close).
// 회차가 없는 날(휴장, 발행 전, 실패)은 day.json 이 지난 회차 것이라 시각만으로 단계를 정한다.
import type { DayCfg } from '../types'

export type Phase = 'pre' | 'live' | 'closed' | 'night' | 'dawn' | 'weekend' | 'late'

const H = 3600e3
const DOW = ['일', '월', '화', '수', '목', '금', '토']

/** 발행일 + add 일 hh:mm (KST) 의 ms */
export const at = (issue: string, add: number, hhmm: string) => {
  const [y, m, d] = issue.split('-').map(Number), [h, mi] = hhmm.split(':').map(Number)
  return Date.UTC(y, m - 1, d + add, h - 9, mi)
}
const kdow = (t: number) => new Date(t + 9 * H).getUTCDay()
export const dayLabel = (t: number) => { const d = new Date(t + 9 * H); return `${d.getUTCMonth() + 1}/${d.getUTCDate()}(${DOW[d.getUTCDay()]})` }

/** 미국 서머타임(3월 둘째 일요일 ~ 11월 첫째 일요일) — 정규장 개장이 KST 22:30, 아니면 23:30 */
function usDst(y: number, m: number, d: number) {
  const sun = (mon: number, n: number) => { const first = new Date(Date.UTC(y, mon - 1, 1)).getUTCDay(); return 1 + ((7 - first) % 7) + 7 * (n - 1) }
  const v = m * 100 + d
  return v >= 300 + sun(3, 2) && v < 1100 + sun(11, 1)
}

export interface Frame {
  phase: Phase
  base: number          // 밤 추종가 기준 = 발행일 정규장 마감(t_close)
  nightStart: number    // 발행일 18:00
  nightEnd: number      // 다음 날 06:00 (금요일은 토 06:00)
  usOpen: number        // 그 밤 미국 정규장 개장(KST)
  nextDay: number       // 다음 영업일 00:00 KST (주말만 건너뜀, 휴장일은 모른다)
  nextBrief: number     // 다음 영업일 07:45
  lateAt: number        // 이 시각까지 회차가 안 오면 '전망 없음'으로 본다(07:45 발행 + Pages 반영 여유)
}

export function frame(D: DayCfg, now: number): Frame {
  const add = kdow(at(D.issue, 0, '12:00')) === 5 ? 3 : 1
  const night0 = at(D.issue, 0, '18:00')
  const [y, m, d] = D.issue.split('-').map(Number)
  const f: Frame = {
    phase: 'late', base: D.t_close, nightStart: night0, nightEnd: at(D.issue, 1, '06:00'),
    usOpen: at(D.issue, 0, usDst(y, m, d) ? '22:30' : '23:30'),
    nextDay: at(D.issue, add, '00:00'), nextBrief: at(D.issue, add, '07:45'), lateAt: at(D.issue, add, '08:10'),
  }
  f.phase = now < D.t_open ? 'pre' : now < D.t_close ? 'live' : now < night0 ? 'closed' : now < f.nightEnd ? 'night'
    : now < at(D.issue, add, '06:00') ? 'weekend' : now < f.lateAt ? 'dawn' : 'late'
  return f
}

export const minsTo = (t: number, now: number) => Math.max(0, Math.ceil((t - now) / 6e4))
export const inMin = (m: number) => (m >= 60 ? `${Math.floor(m / 60)}시간 ${m % 60}분` : `${m}분`)
