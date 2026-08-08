import type { Tag } from '../types';
import { TAG_COLOR_CLASSES } from '../types';

interface Props {
  tags: Tag[];
  size?: 'sm' | 'md';
}

export default function TagBadges({ tags, size = 'sm' }: Props) {
  if (!tags.length) return <span className="text-surface-800/40">—</span>;

  const sizeClass = size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-2.5 py-1 text-sm';

  return (
    <div className="flex flex-wrap gap-1">
      {tags.map((tag) => (
        <span
          key={tag.id}
          className={`inline-flex rounded-full font-medium ${sizeClass} ${
            TAG_COLOR_CLASSES[tag.color] || TAG_COLOR_CLASSES.slate
          }`}
        >
          {tag.label}
        </span>
      ))}
    </div>
  );
}
