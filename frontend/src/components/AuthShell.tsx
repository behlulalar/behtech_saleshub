import { useEffect, type ReactNode } from 'react';
import { ArrowLeft, type LucideIcon } from 'lucide-react';
import BrandLogo from './BrandLogo';
import LocaleToggle from './LocaleToggle';

export interface AuthBenefit {
  icon: LucideIcon;
  title: string;
  description: string;
}

interface Props {
  onHome?: () => void;
  backLabel?: string;
  onBack?: () => void;
  sidebarTitle: string;
  sidebarSubtitle: string;
  sidebarFooter: string;
  benefits: AuthBenefit[];
  children: ReactNode;
}

export default function AuthShell({
  onHome,
  backLabel,
  onBack,
  sidebarTitle,
  sidebarSubtitle,
  sidebarFooter,
  benefits,
  children,
}: Props) {
  useEffect(() => {
    document.body.classList.add('landing-scroll');
    return () => document.body.classList.remove('landing-scroll');
  }, []);

  return (
    <div className="min-h-screen bg-[#fafbff] text-surface-900">
      <div className="pointer-events-none fixed inset-0 overflow-hidden">
        <div className="absolute -left-32 top-0 h-96 w-96 rounded-full bg-brand-200/40 blur-3xl" />
        <div className="absolute right-0 top-32 h-[28rem] w-[28rem] rounded-full bg-brand-500/10 blur-3xl" />
      </div>

      <div className="relative flex min-h-screen flex-col lg:flex-row">
        <aside className="relative hidden w-full flex-col justify-between overflow-hidden border-r border-white/60 bg-white/70 p-10 backdrop-blur-lg lg:flex lg:w-[42%] xl:w-[44%]">
          <div className="absolute inset-0 bg-gradient-to-br from-brand-500/5 via-transparent to-indigo-500/10" />
          <div className="relative">
            {onBack ? (
              <button
                type="button"
                onClick={onBack}
                className="mb-8 inline-flex items-center gap-2 text-sm text-surface-800/55 transition hover:text-brand-500"
              >
                <ArrowLeft size={16} />
                {backLabel}
              </button>
            ) : onHome ? (
              <button
                type="button"
                onClick={onHome}
                className="mb-8 inline-flex items-center gap-2 text-sm text-surface-800/55 transition hover:text-brand-500"
              >
                <ArrowLeft size={16} />
                {backLabel}
              </button>
            ) : null}
            <BrandLogo className="h-10" showTagline />
            <h1 className="mt-8 max-w-md text-3xl font-bold leading-tight text-surface-900">{sidebarTitle}</h1>
            <p className="mt-4 max-w-md text-sm leading-relaxed text-surface-800/60">{sidebarSubtitle}</p>
          </div>

          <ul className="relative mt-10 space-y-4 motion-stagger">
            {benefits.map((item) => {
              const Icon = item.icon;
              return (
                <li
                  key={item.title}
                  className="flex gap-4 rounded-2xl border border-surface-200/80 bg-white/80 p-4 shadow-sm"
                >
                  <div className="brand-icon-box h-10 w-10 shrink-0">
                    <Icon size={18} />
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-surface-900">{item.title}</p>
                    <p className="mt-0.5 text-xs leading-relaxed text-surface-800/55">{item.description}</p>
                  </div>
                </li>
              );
            })}
          </ul>

          <p className="relative mt-8 text-xs text-surface-800/45">{sidebarFooter}</p>
        </aside>

        <main className="relative flex flex-1 items-center justify-center px-4 py-10 sm:px-6 lg:px-10">
          <div className="w-full max-w-lg">
            <div className="mb-6 flex items-center justify-between lg:hidden">
              {onBack ? (
                <button
                  type="button"
                  onClick={onBack}
                  className="inline-flex items-center gap-2 text-sm text-surface-800/55 transition hover:text-brand-500"
                >
                  <ArrowLeft size={16} />
                  {backLabel}
                </button>
              ) : onHome ? (
                <button
                  type="button"
                  onClick={onHome}
                  className="inline-flex items-center gap-2 text-sm text-surface-800/55 transition hover:text-brand-500"
                >
                  <ArrowLeft size={16} />
                  {backLabel}
                </button>
              ) : (
                <span />
              )}
              <div className="flex items-center gap-3">
                <LocaleToggle />
                <BrandLogo className="h-8" />
              </div>
            </div>

            <div className="hidden justify-end lg:mb-4 lg:flex">
              <LocaleToggle />
            </div>

            {children}
          </div>
        </main>
      </div>
    </div>
  );
}
