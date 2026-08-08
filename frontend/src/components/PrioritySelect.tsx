import { ONCELIK_OPTIONS } from '../types';

interface Props {
  value: string;
  onChange: (value: string) => void;
}

export default function PrioritySelect({ value, onChange }: Props) {
  return (
    <div className="grid grid-cols-3 gap-2">
      {ONCELIK_OPTIONS.map((option) => {
        const selected = value === option.value;
        return (
          <button
            key={option.value}
            type="button"
            onClick={() => onChange(option.value)}
            className={`flex flex-col items-center rounded-lg border px-3 py-3 text-center transition ${
              selected
                ? `border-brand-500 ring-2 ${option.ringClass} ${option.bgClass} ${option.textClass}`
                : 'border-surface-200 bg-white text-surface-800 hover:bg-surface-50'
            }`}
          >
            <span className="text-lg font-bold leading-none">{option.icon}</span>
            <span className="mt-1 text-sm font-semibold">{option.label}</span>
            <span className="mt-0.5 text-[10px] opacity-70">{option.description}</span>
          </button>
        );
      })}
    </div>
  );
}
