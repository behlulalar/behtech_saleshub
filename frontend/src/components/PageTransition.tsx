import type { ReactNode } from 'react';

export type TransitionVariant = 'fade-up' | 'fade' | 'slide-forward' | 'slide-back';

const VARIANT_CLASS: Record<TransitionVariant, string> = {
  'fade-up': 'motion-fade-up',
  fade: 'motion-fade',
  'slide-forward': 'motion-slide-forward',
  'slide-back': 'motion-slide-back',
};

interface Props {
  transitionKey: string;
  variant?: TransitionVariant;
  className?: string;
  children: ReactNode;
}

export default function PageTransition({
  transitionKey,
  variant = 'fade-up',
  className = '',
  children,
}: Props) {
  return (
    <div key={transitionKey} className={`${VARIANT_CLASS[variant]} ${className}`.trim()}>
      {children}
    </div>
  );
}

export function transitionVariant(
  direction: 'forward' | 'back',
  fallback: TransitionVariant = 'fade-up',
): TransitionVariant {
  if (direction === 'forward') return 'slide-forward';
  if (direction === 'back') return 'slide-back';
  return fallback;
}
