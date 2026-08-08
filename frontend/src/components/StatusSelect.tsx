import { DURUM_STATUSES } from '../types';

interface Props {
  value: string;
  onChange: (value: string) => void;
}

export default function StatusSelect({ value, onChange }: Props) {
  return (
    <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
      {DURUM_STATUSES.map((status) => {
        const selected = value === status.value;
        return (
          <button
            key={status.value}
            type="button"
            onClick={() => onChange(status.value)}
            className={`flex items-center gap-2 rounded-lg border px-3 py-2 text-left text-sm transition ${
              selected
                ? `border-brand-500 ring-2 ${status.ringClass} ${status.bgClass} ${status.textClass}`
                : 'border-surface-200 bg-white text-surface-800 hover:bg-surface-50'
            }`}
          >
            <span className={`h-2.5 w-2.5 shrink-0 rounded-full ${status.barClass}`} />
            <span className="font-medium">{status.label}</span>
          </button>
        );
      })}
    </div>
  );
}
