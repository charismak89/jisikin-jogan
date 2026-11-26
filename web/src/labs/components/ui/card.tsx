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
    // 제목과 오른쪽 값이 한 줄에 안 들어가면 오른쪽 값을 통째로 다음 줄로 내린다(제목, 숫자와 등락이 중간에서 끊기지 않게). 원본에서 바꾼 곳
    <div className="mb-4 flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
      <h2 className="min-w-0 text-headline1 font-bold text-fg">{title}</h2>
      {aside ? <span className="shrink-0 whitespace-nowrap text-label2 text-fg-2">{aside}</span> : null}
    </div>
  );
}

// 카드 아래 캡션(이 저장소에서 더한 것). 정보가 되는 글자라 text-fg-2 다(DESIGN.md 1절 대비)
export const Cap = ({ children }: { children: React.ReactNode }) => (
  <p className="mt-3 text-caption1 text-fg-2">{children}</p>
)
