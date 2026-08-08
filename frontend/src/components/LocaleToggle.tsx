import { useLocale } from '../i18n/locale';
import type { LandingLocale } from '../i18n/landing';

interface Props {
  className?: string;
}

export default function LocaleToggle({ className = '' }: Props) {
  const { locale, setLocale } = useLocale();

  const switchLocale = (next: LandingLocale) => {
    setLocale(next);
  };

  return (
    <div className={`flex rounded-lg border border-surface-200 bg-white p-0.5 text-xs font-semibold ${className}`.trim()}>
      <button
        type="button"
        onClick={() => switchLocale('tr')}
        className={`rounded-md px-2.5 py-1.5 transition ${locale === 'tr' ? 'bg-brand-500 text-white' : 'text-surface-800/60'}`}
      >
        TR
      </button>
      <button
        type="button"
        onClick={() => switchLocale('en')}
        className={`rounded-md px-2.5 py-1.5 transition ${locale === 'en' ? 'bg-brand-500 text-white' : 'text-surface-800/60'}`}
      >
        EN
      </button>
    </div>
  );
}
