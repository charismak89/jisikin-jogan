import * as React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '../../lib/cn';

// 상태는 색만으로 전하지 않는다: 점과 글자를 같이 쓴다(DESIGN.md 1절).
// 배지 글자는 12px 라 모두 text-fg 다. 색은 점과 옅은 바탕으로만 나눈다(색 글자는 옅은 바탕 위에서 4.5:1 이 안 나온다).
const badgeVariants = cva('inline-flex items-center gap-1 rounded-sm px-2 py-0.5 text-caption1 font-semibold', {
  variants: {
    tone: {
      neutral: 'bg-fill text-fg-2',
      brand: 'bg-brand-subtle text-fg',
      positive: 'bg-positive-subtle text-fg',
      cautionary: 'bg-cautionary-subtle text-fg',
      negative: 'bg-negative-subtle text-fg',
    },
  },
  defaultVariants: { tone: 'neutral' },
});

const dot: Record<string, string> = {
  neutral: 'bg-fg-3',
  brand: 'bg-brand',
  positive: 'bg-positive',
  cautionary: 'bg-cautionary',
  negative: 'bg-negative',
};

export function Badge({ tone, className, children }: VariantProps<typeof badgeVariants> & { className?: string; children: React.ReactNode }) {
  return (
    <span className={cn(badgeVariants({ tone }), className)}>
      <span aria-hidden className={cn('size-1.5 rounded-full', dot[tone ?? 'neutral'])} />
      {children}
    </span>
  );
}
