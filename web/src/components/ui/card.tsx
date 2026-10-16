import type { HTMLAttributes } from 'react'
import { cn } from '../../lib/cn'

export function Card({ className, ...p }: HTMLAttributes<HTMLElement>) {
  return <section className={cn('rounded-3xl bg-card p-5 shadow-[var(--shadow)] sm:p-6', className)} {...p} />
}
export function CardHead({ title, right }: { title: string; right?: React.ReactNode }) {
  return (
    <div className="mb-3 flex items-baseline justify-between gap-3">
      <h2 className="text-[17px] font-bold text-tx">{title}</h2>
      {right != null && <span className="text-[13px] text-tx3">{right}</span>}
    </div>
  )
}
export const Cap = ({ children }: { children: React.ReactNode }) => (
  <p className="mt-3 text-[12px] leading-relaxed text-tx3">{children}</p>
)
