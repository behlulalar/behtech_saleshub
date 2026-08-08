import {
  Briefcase,
  Building2,
  Car,
  Coffee,
  Flower2,
  Gem,
  Heart,
  Home,
  Palette,
  PenTool,
  Phone,
  Scissors,
  ScissorsLineDashed,
  Sparkles,
  Star,
  Store,
  Users,
  type LucideIcon,
} from 'lucide-react';

export const ICON_MAP: Record<string, LucideIcon> = {
  'pen-tool': PenTool,
  sparkles: Sparkles,
  scissors: Scissors,
  'building-2': Building2,
  store: Store,
  heart: Heart,
  star: Star,
  users: Users,
  briefcase: Briefcase,
  'scissors-line-dashed': ScissorsLineDashed,
  'flower-2': Flower2,
  palette: Palette,
  gem: Gem,
  coffee: Coffee,
  car: Car,
  home: Home,
  phone: Phone,
};

export const ICON_OPTIONS = Object.keys(ICON_MAP).map((id) => ({
  id,
  label: id.replace(/-/g, ' '),
}));

export function CategoryIcon({ name, size = 18, className }: { name: string; size?: number; className?: string }) {
  const Icon = ICON_MAP[name] || Building2;
  return <Icon size={size} className={className} />;
}
