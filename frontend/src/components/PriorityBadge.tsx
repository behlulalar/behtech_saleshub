import { getOncelikBadgeClass, getOncelikOption } from '../types';
import { useLocale } from '../i18n/locale';

interface Props {
  oncelik: string;
  size?: 'xs' | 'sm' | 'md';
  showIcon?: boolean;
}

export default function PriorityBadge({ oncelik, size = 'sm', showIcon = true }: Props) {
  const { app } = useLocale();
  const option = getOncelikOption(oncelik);
  const label = app.priorities[oncelik] ?? option?.label ?? app.priorities.orta;
  const sizeClass =
    size === 'xs'
      ? 'px-2 py-0.5 text-[10px]'
      : size === 'md'
        ? 'px-3 py-1 text-sm'
        : 'px-2.5 py-0.5 text-xs';

  return (
    <span className={`inline-flex items-center gap-1 rounded-full font-medium ${sizeClass} ${getOncelikBadgeClass(oncelik)}`}>
      {showIcon && <span className="font-bold leading-none">{option?.icon || '→'}</span>}
      {label}
    </span>
  );
}
