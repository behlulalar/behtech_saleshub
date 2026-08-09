import { useEffect, useRef } from 'react';
import { clearSessionExpired, getIdleTimeoutMs } from '../auth';

export function useIdleTimeout(onTimeout: () => void, enabled: boolean) {
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const onTimeoutRef = useRef(onTimeout);

  useEffect(() => {
    onTimeoutRef.current = onTimeout;
  }, [onTimeout]);

  useEffect(() => {
    if (!enabled) return;

    const reset = () => {
      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => {
        clearSessionExpired();
        onTimeoutRef.current();
      }, getIdleTimeoutMs());
    };

    const events = ['mousedown', 'keydown', 'touchstart', 'scroll', 'click', 'pointerdown'];
    events.forEach((e) => window.addEventListener(e, reset, { passive: true }));

    const onVisibility = () => {
      if (document.visibilityState === 'visible') reset();
    };
    document.addEventListener('visibilitychange', onVisibility);

    reset();

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
      events.forEach((e) => window.removeEventListener(e, reset));
      document.removeEventListener('visibilitychange', onVisibility);
    };
  }, [enabled]);
}
