import * as React from 'react';
import { cn } from '../../lib/cn';

export const Card = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn('rounded-lg bg-card p-5 shadow-xs ring-1 ring-line-2 sm:p-6', className)} {...props} />
  ),
);
Card.displayName = 'Card';

export function CardHeader({ title, aside }: { title: React.ReactNode; aside?: React.ReactNode }) {
  return (
    <div className="mb-4 flex items-baseline justify-between gap-3">
      <h2 className="text-headline1 font-bold text-fg">{title}</h2>
      {aside ? <span className="text-label2 text-fg-2">{aside}</span> : null}
    </div>
  );
}

// 카드 아래 캡션(이 저장소에서 더한 것). 정보가 되는 글자라 text-fg-2 다(DESIGN.md 1절 대비)
export const Cap = ({ children }: { children: React.ReactNode }) => (
  <p className="mt-3 text-caption1 text-fg-2">{children}</p>
)
