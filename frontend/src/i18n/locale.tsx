import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react';
import { appCopy } from './app';
import { getStoredLocale, storeLocale, type LandingLocale } from './landing';

interface LocaleContextValue {
  locale: LandingLocale;
  setLocale: (locale: LandingLocale) => void;
  app: (typeof appCopy)['tr'];
}

const LocaleContext = createContext<LocaleContextValue | null>(null);

export function LocaleProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<LandingLocale>(getStoredLocale);

  const setLocale = useCallback((next: LandingLocale) => {
    storeLocale(next);
    setLocaleState(next);
  }, []);

  const value = useMemo(
    () => ({
      locale,
      setLocale,
      app: appCopy[locale],
    }),
    [locale],
  );

  return <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>;
}

export function useLocale() {
  const context = useContext(LocaleContext);
  if (!context) {
    throw new Error('useLocale must be used within LocaleProvider');
  }
  return context;
}
