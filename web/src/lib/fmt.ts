import type { Ent } from '../types'

export const nf = (v: number, d = 0) => v.toLocaleString('ko-KR', { minimumFractionDigits: d, maximumFractionDigits: d })
export const sg = (p: number) => (p > 0 ? '+' : p < 0 ? '−' : '') + Math.abs(p).toFixed(2) + '%'
export const tk = (e: Ent, v: number) => (e.tick ? Math.round(v / e.tick) * e.tick : Math.round(v))
export const money = (e: Ent, v: number) => (e.approx ? '≈' : '') + nf(tk(e, v), 0) + (e.unit || '')
export const dir = (p: number | null | undefined) => (p == null ? '' : p < 0 ? 'text-dn' : p > 0 ? 'text-up' : '')
export const arrow = (p: number) => (p < 0 ? '▼ ' : p > 0 ? '▲ ' : '')
export const hm = (t: number) => {
  const d = new Date(t + 9 * 3600e3)
  return ('0' + d.getUTCHours()).slice(-2) + ':' + ('0' + d.getUTCMinutes()).slice(-2)
}
export const kstDay = (t: number) => {
  const d = new Date(t + 9 * 3600e3)
  return d.getUTCFullYear() + '-' + ('0' + (d.getUTCMonth() + 1)).slice(-2) + '-' + ('0' + d.getUTCDate()).slice(-2)
}
export const md = (iso: string) => `${+iso.slice(5, 7)}/${+iso.slice(8, 10)}`
