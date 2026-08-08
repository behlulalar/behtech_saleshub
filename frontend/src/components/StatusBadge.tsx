import { getDurumBadgeClass } from '../types';
import { useLocale } from '../i18n/locale';

interface Props {
  durum: string;
  size?: 'xs' | 'sm' | 'md';
}

export default function StatusBadge({ durum, size = 'sm' }: Props) {
  const { app } = useLocale();
  const label = app.statuses[durum] ?? durum;
  const sizeClass =
    size === 'xs'
      ? 'px-2 py-0.5 text-[10px]'
      : size === 'md'
        ? 'px-3 py-1 text-sm'
        : 'px-2.5 py-0.5 text-xs';

  return (
    <span className={`inline-block rounded-full font-medium ${sizeClass} ${getDurumBadgeClass(durum)}`}>
      {label}
    </span>
  );
}
