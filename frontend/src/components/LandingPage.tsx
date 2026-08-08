import { useEffect, useState } from 'react';
import {
  ArrowRight,
  BarChart3,
  CheckCircle2,
  ChevronDown,
  CircleDollarSign,
  ClipboardList,
  Globe,
  LayoutDashboard,
  Shield,
  Sparkles,
  Tags,
  Users,
} from 'lucide-react';
import BrandLogo from './BrandLogo';
import LocaleToggle from './LocaleToggle';
import { landingCopy } from '../i18n/landing';
import { useLocale } from '../i18n/locale';
import { SITE_URL } from '../seo/config';

interface Props {
  onLogin: () => void;
  onRegister: () => void;
}

const featureIcons = [
  LayoutDashboard,
  Tags,
  BarChart3,
  CircleDollarSign,
  ClipboardList,
  Sparkles,
];

export default function LandingPage({ onLogin, onRegister }: Props) {
  const { locale } = useLocale();
  const t = landingCopy[locale];
  const [openFaq, setOpenFaq] = useState<number | null>(0);

  useEffect(() => {
    document.body.classList.add('landing-scroll');
    return () => document.body.classList.remove('landing-scroll');
  }, []);

  useEffect(() => {
    const script = document.createElement('script');
    script.type = 'application/ld+json';
    script.setAttribute('data-seo-id', 'faq');
    script.textContent = JSON.stringify({
      '@context': 'https://schema.org',
      '@type': 'FAQPage',
      mainEntity: t.faq.items.map((item) => ({
        '@type': 'Question',
        name: item.question,
        acceptedAnswer: {
          '@type': 'Answer',
          text: item.answer,
        },
      })),
    });
    document.head.appendChild(script);

    return () => {
      document.head.querySelector('script[data-seo-id="faq"]')?.remove();
    };
  }, [locale, t.faq.items]);

  const scrollTo = (id: string) => {
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' });
  };

  return (
    <div className="min-h-screen overflow-y-auto bg-[#fafbff] text-surface-900">
      <div className="pointer-events-none fixed inset-0 overflow-hidden">
        <div className="absolute -left-32 top-0 h-96 w-96 rounded-full bg-brand-200/40 blur-3xl" />
        <div className="absolute right-0 top-32 h-[28rem] w-[28rem] rounded-full bg-brand-500/10 blur-3xl" />
        <div className="absolute bottom-0 left-1/3 h-72 w-72 rounded-full bg-indigo-200/30 blur-3xl" />
      </div>

      <header className="sticky top-0 z-40 border-b border-white/60 bg-white/80 backdrop-blur-lg">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3 sm:px-6">
          <BrandLogo className="h-9" showTagline={false} />
          <nav className="hidden items-center gap-6 text-sm font-medium text-surface-800/70 md:flex">
            <button type="button" onClick={() => scrollTo('features')} className="hover:text-brand-500">
              {t.nav.features}
            </button>
            <button type="button" onClick={() => scrollTo('workflow')} className="hover:text-brand-500">
              {t.nav.workflow}
            </button>
            <button type="button" onClick={() => scrollTo('roles')} className="hover:text-brand-500">
              {t.nav.roles}
            </button>
            <button type="button" onClick={() => scrollTo('faq')} className="hover:text-brand-500">
              {t.nav.faq}
            </button>
          </nav>
          <div className="flex items-center gap-2 sm:gap-3">
            <LocaleToggle />
            <button type="button" onClick={onLogin} className="btn-secondary hidden py-2 sm:inline-flex">
              {t.nav.login}
            </button>
            <button type="button" onClick={onRegister} className="btn-primary py-2">
              {t.nav.register}
            </button>
          </div>
        </div>
      </header>

      <main className="relative">
        <section className="mx-auto max-w-6xl px-4 pb-20 pt-16 sm:px-6 sm:pt-24">
          <div className="grid items-center gap-12 lg:grid-cols-2">
            <div>
              <span className="inline-flex items-center gap-2 rounded-full border border-brand-200 bg-brand-50 px-3 py-1 text-xs font-semibold text-brand-600">
                <Sparkles size={14} />
                {t.hero.badge}
              </span>
              <h1 className="mt-6 text-4xl font-bold leading-tight tracking-tight sm:text-5xl lg:text-[3.25rem]">
                {t.hero.title}{' '}
                <span className="bg-brand-gradient-h bg-clip-text text-transparent">{t.hero.highlight}</span>
              </h1>
              <p className="mt-5 max-w-xl text-base leading-relaxed text-surface-800/65 sm:text-lg">
                {t.hero.subtitle}
              </p>
              <div className="mt-8 flex flex-wrap gap-3">
                <button type="button" onClick={onRegister} className="btn-primary px-6 py-3 text-base">
                  {t.hero.ctaPrimary}
                  <ArrowRight size={18} />
                </button>
                <button type="button" onClick={onLogin} className="btn-secondary px-6 py-3 text-base">
                  {t.hero.ctaSecondary}
                </button>
              </div>
            </div>

            <div className="relative">
              <div className="card overflow-hidden border-brand-100 shadow-xl shadow-brand-500/10">
                <div className="border-b border-surface-100 bg-brand-gradient-h px-4 py-3 text-sm font-medium text-white">
                  {t.hero.productName}
                </div>
                <div className="space-y-3 p-4">
                  {[
                    { label: 'Zephyr Labs', status: 'Demo Gönderildi', color: 'bg-indigo-100 text-indigo-700' },
                    { label: 'Glow Beauty Studio', status: 'Görüşme Planlandı', color: 'bg-violet-100 text-violet-700' },
                    { label: 'Urban Barber', status: 'Yeni', color: 'bg-slate-100 text-slate-700' },
                  ].map((item) => (
                    <div key={item.label} className="flex items-center justify-between rounded-xl border border-surface-100 bg-surface-50 px-3 py-3">
                      <div>
                        <p className="text-sm font-semibold">{item.label}</p>
                        <p className="text-xs text-surface-800/45">İstanbul · Orta öncelik</p>
                      </div>
                      <span className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${item.color}`}>
                        {item.status}
                      </span>
                    </div>
                  ))}
                </div>
                <div className="grid grid-cols-3 gap-2 border-t border-surface-100 bg-white p-4 text-center">
                  <div>
                    <p className="text-lg font-bold text-brand-500">24</p>
                    <p className="text-[10px] text-surface-800/45">Aktif</p>
                  </div>
                  <div>
                    <p className="text-lg font-bold text-emerald-600">8</p>
                    <p className="text-[10px] text-surface-800/45">Müşteri</p>
                  </div>
                  <div>
                    <p className="text-lg font-bold text-amber-600">3</p>
                    <p className="text-[10px] text-surface-800/45">Talep</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section id="features" className="border-y border-surface-200/80 bg-white py-20">
          <div className="mx-auto max-w-6xl px-4 sm:px-6">
            <div className="mx-auto max-w-2xl text-center">
              <h2 className="text-3xl font-bold sm:text-4xl">{t.features.title}</h2>
              <p className="mt-3 text-surface-800/60">{t.features.subtitle}</p>
            </div>
            <div className="mt-12 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
              {t.features.items.map((feature, index) => {
                const Icon = featureIcons[index] || Sparkles;
                return (
                  <article
                    key={feature.title}
                    className="group rounded-2xl border border-surface-200 bg-surface-50/50 p-6 transition hover:-translate-y-1 hover:border-brand-200 hover:bg-white hover:shadow-lg hover:shadow-brand-500/5"
                  >
                    <div className="brand-icon-box mb-4 h-11 w-11">
                      <Icon size={20} />
                    </div>
                    <h3 className="text-lg font-semibold">{feature.title}</h3>
                    <p className="mt-2 text-sm leading-relaxed text-surface-800/65">{feature.description}</p>
                  </article>
                );
              })}
            </div>
          </div>
        </section>

        <section id="workflow" className="py-20">
          <div className="mx-auto max-w-6xl px-4 sm:px-6">
            <div className="mx-auto max-w-2xl text-center">
              <h2 className="text-3xl font-bold sm:text-4xl">{t.workflow.title}</h2>
              <p className="mt-3 text-surface-800/60">{t.workflow.subtitle}</p>
            </div>
            <div className="mt-12 grid gap-6 md:grid-cols-3">
              {t.workflow.steps.map((step, index) => (
                <div key={step.title} className="relative card p-6">
                  <span className="flex h-10 w-10 items-center justify-center rounded-full bg-brand-gradient-h text-sm font-bold text-white">
                    {index + 1}
                  </span>
                  <h3 className="mt-4 text-lg font-semibold">{step.title}</h3>
                  <p className="mt-2 text-sm text-surface-800/65">{step.description}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section id="roles" className="border-y border-surface-200/80 bg-white py-20">
          <div className="mx-auto max-w-6xl px-4 sm:px-6">
            <div className="mx-auto max-w-2xl text-center">
              <h2 className="text-3xl font-bold sm:text-4xl">{t.roles.title}</h2>
              <p className="mt-3 text-surface-800/60">{t.roles.subtitle}</p>
            </div>
            <div className="mt-12 grid gap-6 md:grid-cols-2">
              {[
                { key: 'owner' as const, icon: Shield, accent: 'from-brand-900 to-brand-500' },
                { key: 'employee' as const, icon: Users, accent: 'from-slate-800 to-brand-400' },
              ].map(({ key, icon: Icon, accent }) => (
                <div key={key} className="card overflow-hidden">
                  <div className={`bg-gradient-to-r ${accent} px-6 py-5 text-white`}>
                    <Icon size={24} className="mb-2 opacity-90" />
                    <h3 className="text-xl font-semibold">{t.roles[key].title}</h3>
                  </div>
                  <ul className="space-y-3 p-6">
                    {t.roles[key].items.map((item) => (
                      <li key={item} className="flex items-start gap-2 text-sm text-surface-800/75">
                        <CheckCircle2 size={16} className="mt-0.5 shrink-0 text-emerald-500" />
                        {item}
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section id="faq" className="py-20">
          <div className="mx-auto max-w-3xl px-4 sm:px-6">
            <div className="text-center">
              <h2 className="text-3xl font-bold sm:text-4xl">{t.faq.title}</h2>
              <p className="mt-3 text-surface-800/60">{t.faq.subtitle}</p>
            </div>
            <div className="mt-10 space-y-3">
              {t.faq.items.map((item, index) => {
                const isOpen = openFaq === index;

                return (
                  <article
                    key={item.question}
                    className="overflow-hidden rounded-2xl border border-surface-200 bg-white transition hover:border-brand-200"
                    itemScope
                    itemProp="mainEntity"
                    itemType="https://schema.org/Question"
                  >
                    <button
                      type="button"
                      id={`faq-question-${index}`}
                      aria-expanded={isOpen}
                      aria-controls={`faq-answer-${index}`}
                      onClick={() => setOpenFaq(isOpen ? null : index)}
                      className="flex w-full items-start justify-between gap-4 px-5 py-4 text-left"
                    >
                      <span className="text-base font-semibold text-surface-900" itemProp="name">
                        {item.question}
                      </span>
                      <ChevronDown
                        size={20}
                        className={`mt-0.5 shrink-0 text-surface-800/45 transition-transform ${isOpen ? 'rotate-180' : ''}`}
                      />
                    </button>
                    <div
                      id={`faq-answer-${index}`}
                      role="region"
                      aria-labelledby={`faq-question-${index}`}
                      hidden={!isOpen}
                      className="border-t border-surface-100 px-5 py-4"
                      itemScope
                      itemProp="acceptedAnswer"
                      itemType="https://schema.org/Answer"
                    >
                      <p className="text-sm leading-relaxed text-surface-800/70" itemProp="text">
                        {item.answer}
                      </p>
                    </div>
                  </article>
                );
              })}
            </div>
            <p className="mt-8 text-center text-sm text-surface-800/50">
              {locale === 'tr' ? (
                <>
                  Daha fazla bilgi için{' '}
                  <a href={`${SITE_URL}/register`} className="font-medium text-brand-500 hover:underline">
                    ücretsiz hesap oluşturun
                  </a>
                  .
                </>
              ) : (
                <>
                  Learn more —{' '}
                  <a href={`${SITE_URL}/register`} className="font-medium text-brand-500 hover:underline">
                    create a free account
                  </a>
                  .
                </>
              )}
            </p>
          </div>
        </section>

        <section className="py-20">
          <div className="mx-auto max-w-4xl px-4 sm:px-6">
            <div className="overflow-hidden rounded-3xl bg-brand-gradient-h px-8 py-12 text-center text-white shadow-2xl shadow-brand-500/25 sm:px-12">
              <Globe size={32} className="mx-auto mb-4 opacity-80" />
              <h2 className="text-3xl font-bold sm:text-4xl">{t.cta.title}</h2>
              <p className="mx-auto mt-4 max-w-2xl text-white/80">{t.cta.subtitle}</p>
              <button
                type="button"
                onClick={onRegister}
                className="mt-8 inline-flex items-center gap-2 rounded-xl bg-white px-6 py-3 text-base font-semibold text-brand-600 transition hover:bg-brand-50"
              >
                {t.cta.button}
                <ArrowRight size={18} />
              </button>
            </div>
          </div>
        </section>
      </main>

      <footer className="border-t border-surface-200 bg-white py-8">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 px-4 sm:flex-row sm:px-6">
          <BrandLogo className="h-8" showTagline />
          <p className="text-xs text-surface-800/45">
            © {new Date().getFullYear()} {t.footer.rights}
          </p>
        </div>
      </footer>
    </div>
  );
}
