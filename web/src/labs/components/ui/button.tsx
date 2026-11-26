import * as React from 'react';
import { Slot } from '@radix-ui/react-slot';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '../../lib/cn';

// 몽타주 Button 규격: large 48px, medium 40px, small 32px, 모서리 12/10/8px.
const buttonVariants = cva(
  'inline-flex items-center justify-center gap-1.5 whitespace-nowrap font-semibold transition-colors disabled:pointer-events-none disabled:bg-fill disabled:text-fg-disabled',
  {
    variants: {
      variant: {
        primary: 'bg-brand-btn text-on-brand hover:bg-brand-btn-hover',
        secondary: 'bg-card text-brand-fg border border-line hover:bg-brand-subtle',
        assistive: 'bg-card text-fg border border-line hover:bg-fill',
      },
      size: {
        large: 'h-12 px-5 rounded-md text-body1',
        medium: 'h-10 px-4 rounded-10 text-body2',
        small: 'h-8 px-3 rounded-sm text-label2',
      },
    },
    defaultVariants: { variant: 'primary', size: 'medium' },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

// React 18 고정(DESIGN.md 0절): ref 는 forwardRef 로 넘긴다. shadcn 최신 코드(React 19, ref 를 prop 으로)와 다르다.
export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : 'button';
    return <Comp ref={ref} className={cn(buttonVariants({ variant, size }), className)} {...props} />;
  },
);
Button.displayName = 'Button';
