import { useEffect, useMemo, useState } from 'react';
import {
  ArrowLeft,
  BarChart3,
  Building2,
  Check,
  CircleDollarSign,
  Eye,
  EyeOff,
  LayoutDashboard,
  Lock,
  Mail,
  ShieldCheck,
  Tag,
  User,
  UserPlus,
  Users,
  X,
} from 'lucide-react';
import { api, saveAuth, type AuthResponse } from '../api';
import { registerCopy } from '../i18n/register';
import { useLocale } from '../i18n/locale';
import type { AccountType } from '../types';
import { isPersonalEmail, passwordsMatch } from '../utils/validation';
import BrandLogo from './BrandLogo';
import LocaleToggle from './LocaleToggle';
import PageTransition, { transitionVariant } from './PageTransition';

interface Props {
  onSuccess: () => void;
  onBack: () => void;
  onHome?: () => void;
}

type RegisterStep = 'type' | 'form';

const PASSWORD_TESTS = [
  { id: 'length', test: (p: string) => p.length >= 8 },
  { id: 'upper', test: (p: string) => /[A-Z]/.test(p) },
  { id: 'lower', test: (p: string) => /[a-z]/.test(p) },
  { id: 'digit', test: (p: string) => /[0-9]/.test(p) },
  { id: 'special', test: (p: string) => /[^A-Za-z0-9]/.test(p) },
] as const;

const ACCOUNT_ICONS = {
  individual: User,
  company: Building2,
} as const;

const SIDEBAR_ICONS = {
  individual: [LayoutDashboard, BarChart3, Tag],
  company: [LayoutDashboard, CircleDollarSign, ShieldCheck],
} as const;

function validateUsername(
  username: string,
  errors: (typeof registerCopy)['tr']['errors'],
): string | null {
  const value = username.trim();
  if (value.length < 3 || value.length > 30) {
    return errors.usernameLength;
  }
  if (!/^[a-zA-Z0-9_]+$/.test(value)) {
    return errors.usernameChars;
  }
  return null;
}

function passwordStrength(
  password: string,
  labels: (typeof registerCopy)['tr']['passwordStrength'],
) {
  const passed = PASSWORD_TESTS.filter((rule) => rule.test(password)).length;
  if (!password) return { score: 0, label: '', color: 'bg-surface-200' };
  if (passed <= 2) return { score: 1, label: labels.weak, color: 'bg-red-500' };
  if (passed <= 4) return { score: 2, label: labels.medium, color: 'bg-amber-500' };
  return { score: 3, label: labels.strong, color: 'bg-emerald-500' };
}

export default function RegisterPage({ onSuccess, onBack, onHome }: Props) {
  const { locale } = useLocale();
  const [step, setStep] = useState<RegisterStep>('type');
  const [accountType, setAccountType] = useState<AccountType | null>(null);
  const [username, setUsername] = useState('');
  const [companyName, setCompanyName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [passwordConfirm, setPasswordConfirm] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showPasswordConfirm, setShowPasswordConfirm] = useState(false);
  const [acceptedTerms, setAcceptedTerms] = useState(false);
  const [error, setError] = useState('');
  const [verificationEmail, setVerificationEmail] = useState('');
  const [resendMessage, setResendMessage] = useState('');
  const [resending, setResending] = useState(false);
  const [loading, setLoading] = useState(false);
  const [touched, setTouched] = useState({
    username: false,
    companyName: false,
    email: false,
    password: false,
    passwordConfirm: false,
  });
  const [transitionDir, setTransitionDir] = useState<'forward' | 'back'>('forward');

  const t = registerCopy[locale];

  useEffect(() => {
    document.body.classList.add('landing-scroll');
    return () => document.body.classList.remove('landing-scroll');
  }, []);

  const passwordRules = useMemo(
    () =>
      PASSWORD_TESTS.map((rule) => ({
        ...rule,
        label: t.passwordRules[rule.id],
      })),
    [t],
  );

  const sidebar = accountType ? t.sidebar[accountType] : t.sidebar.company;
  const accountCopy = accountType ? t.accountTypes[accountType] : null;
  const usernameError = useMemo(
    () => (touched.username ? validateUsername(username, t.errors) : null),
    [username, touched.username, t.errors],
  );
  const strength = useMemo(() => passwordStrength(password, t.passwordStrength), [password, t.passwordStrength]);
  const passwordReady = passwordRules.every((rule) => rule.test(password));
  const passwordsAligned = passwordsMatch(password, passwordConfirm);
  const companyNameValid = accountType !== 'company' || companyName.trim().length >= 2;
  const emailValid = accountType !== 'company' || !email.trim() || !isPersonalEmail(email);
  const canSubmit =
    !!accountType &&
    !loading &&
    acceptedTerms &&
    !validateUsername(username, t.errors) &&
    companyNameValid &&
    email.trim().length > 0 &&
    emailValid &&
    passwordReady &&
    passwordsAligned;

  const chooseAccountType = (type: AccountType) => {
    setTransitionDir('forward');
    setAccountType(type);
    setStep('form');
    setError('');
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!accountType) return;

    setTouched({
      username: true,
      companyName: true,
      email: true,
      password: true,
      passwordConfirm: true,
    });
    setError('');

    const userErr = validateUsername(username, t.errors);
    if (userErr) {
      setError(userErr);
      return;
    }
    if (accountType === 'company') {
      if (companyName.trim().length < 2) {
        setError(t.errors.companyNameRequired);
        return;
      }
      if (isPersonalEmail(email)) {
        setError(t.errors.personalEmailNotAllowed);
        return;
      }
    }
    if (!passwordReady) {
      setError(t.errors.passwordRequirements);
      return;
    }
    if (!passwordsAligned) {
      setError(t.errors.passwordMismatch);
      return;
    }
    if (!acceptedTerms) {
      setError(t.errors.termsRequired);
      return;
    }

    setLoading(true);
    try {
      const res = await api.register(
        username.trim(),
        email.trim(),
        password,
        passwordConfirm,
        accountType,
        accountType === 'company' ? companyName.trim() : undefined,
      );
      if (res.requires_verification) {
        setVerificationEmail(res.email || email.trim());
        return;
      }
      if (res.access_token && res.username) {
        saveAuth(
          {
            access_token: res.access_token,
            username: res.username,
            role: (res.role as AuthResponse['role']) || 'owner',
            account_type: (res.account_type as AuthResponse['account_type']) || accountType,
            expires_in: res.expires_in || 1800,
          },
          false,
        );
      }
      onSuccess();
    } catch (err) {
      setError(err instanceof Error ? err.message : t.errors.registerFailed);
    } finally {
      setLoading(false);
    }
  };

  const handleResendVerification = async () => {
    if (!verificationEmail) return;
    setResending(true);
    setResendMessage('');
    try {
      await api.resendVerification(verificationEmail);
      setResendMessage(t.verification.resent);
    } catch (err) {
      setResendMessage(err instanceof Error ? err.message : t.errors.registerFailed);
    } finally {
      setResending(false);
    }
  };

  const backToTypeStep = () => {
    setTransitionDir('back');
    setStep('type');
    setError('');
  };

  if (verificationEmail) {
    return (
      <PageTransition transitionKey="register-verify" variant="fade-up">
        <div className="flex min-h-screen items-center justify-center bg-[#fafbff] p-4">
          <div className="w-full max-w-md rounded-2xl border border-surface-200/80 bg-white/90 p-8 shadow-xl shadow-brand-500/5">
            <BrandLogo className="mb-6 h-10" />
            <h1 className="text-2xl font-bold text-surface-900">{t.verification.title}</h1>
            <p className="mt-3 text-sm leading-relaxed text-surface-800/60">
              {t.verification.message.replace('{email}', verificationEmail)}
            </p>
            {resendMessage ? (
              <p className="mt-4 rounded-xl border border-emerald-100 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
                {resendMessage}
              </p>
            ) : null}
            <div className="mt-6 space-y-3">
              <button
                type="button"
                onClick={handleResendVerification}
                disabled={resending}
                className="btn-secondary w-full justify-center"
              >
                <Mail size={16} />
                {resending ? t.verification.resending : t.verification.resend}
              </button>
              <button type="button" onClick={onBack} className="btn-primary w-full justify-center">
                {t.verification.backToLogin}
              </button>
            </div>
          </div>
        </div>
      </PageTransition>
    );
  }

  if (step === 'type') {
    return (
      <PageTransition transitionKey="register-type" variant={transitionVariant(transitionDir)}>
      <div className="min-h-screen bg-[#fafbff] text-surface-900">
        <div className="pointer-events-none fixed inset-0 overflow-hidden">
          <div className="absolute -left-32 top-0 h-96 w-96 rounded-full bg-brand-200/40 blur-3xl" />
          <div className="absolute right-0 top-32 h-[28rem] w-[28rem] rounded-full bg-brand-500/10 blur-3xl" />
        </div>

        <div className="relative mx-auto flex min-h-screen max-w-5xl flex-col px-4 py-10 sm:px-6">
          <div className="mb-8 flex items-center justify-between gap-4">
            {onHome ? (
              <button
                type="button"
                onClick={onHome}
                className="inline-flex items-center gap-2 text-sm text-surface-800/55 transition hover:text-brand-500"
              >
                <ArrowLeft size={16} />
                {t.backHome}
              </button>
            ) : (
              <span />
            )}
            <div className="flex items-center gap-3">
              <LocaleToggle />
              <BrandLogo className="h-9" />
            </div>
          </div>

          <div className="mx-auto w-full max-w-3xl flex-1">
            <div className="text-center">
              <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-brand-200 bg-brand-50 px-3 py-1 text-xs font-semibold text-brand-600">
                <UserPlus size={14} />
                {t.typeStep.badge}
              </div>
              <h1 className="text-3xl font-bold text-surface-900 sm:text-4xl">{t.typeStep.title}</h1>
              <p className="mx-auto mt-3 max-w-xl text-sm text-surface-800/60">{t.typeStep.subtitle}</p>
            </div>

            <div className="mt-10 grid gap-5 sm:grid-cols-2 motion-stagger">
              {(['individual', 'company'] as const).map((type) => {
                const option = t.accountTypes[type];
                const Icon = ACCOUNT_ICONS[type];
                return (
                  <button
                    key={type}
                    type="button"
                    onClick={() => chooseAccountType(type)}
                    className="group rounded-2xl border border-surface-200 bg-white/90 p-6 text-left shadow-sm transition hover:-translate-y-1 hover:border-brand-300 hover:shadow-lg hover:shadow-brand-500/10"
                  >
                    <div className="brand-icon-box mb-4 h-12 w-12">
                      <Icon size={22} />
                    </div>
                    <h2 className="text-xl font-bold text-surface-900">{option.title}</h2>
                    <p className="mt-2 text-sm leading-relaxed text-surface-800/60">{option.description}</p>
                    <ul className="mt-5 space-y-2">
                      {option.highlights.map((item) => (
                        <li key={item} className="flex items-center gap-2 text-xs text-surface-800/70">
                          <Check size={14} className="shrink-0 text-brand-500" />
                          {item}
                        </li>
                      ))}
                    </ul>
                    <span className="mt-6 inline-flex items-center gap-2 text-sm font-semibold text-brand-500 transition-all group-hover:gap-3">
                      {t.typeStep.continue}
                      <ArrowLeft size={14} className="rotate-180" />
                    </span>
                  </button>
                );
              })}
            </div>

            <p className="mt-8 text-center text-sm text-surface-800/60">
              {t.alreadyHaveAccount}{' '}
              <button type="button" onClick={onBack} className="font-semibold text-brand-500 hover:text-brand-600">
                {t.signIn}
              </button>
            </p>
          </div>
        </div>
      </div>
      </PageTransition>
    );
  }

  const sidebarIcons = SIDEBAR_ICONS[accountType!];

  return (
    <PageTransition transitionKey="register-form" variant={transitionVariant(transitionDir)}>
    <div className="min-h-screen bg-[#fafbff] text-surface-900">
      <div className="pointer-events-none fixed inset-0 overflow-hidden">
        <div className="absolute -left-32 top-0 h-96 w-96 rounded-full bg-brand-200/40 blur-3xl" />
        <div className="absolute right-0 top-32 h-[28rem] w-[28rem] rounded-full bg-brand-500/10 blur-3xl" />
      </div>

      <div className="relative flex min-h-screen flex-col lg:flex-row">
        <aside className="relative hidden w-full flex-col justify-between overflow-hidden border-r border-white/60 bg-white/70 p-10 backdrop-blur-lg lg:flex lg:w-[42%] xl:w-[44%]">
          <div className="absolute inset-0 bg-gradient-to-br from-brand-500/5 via-transparent to-indigo-500/10" />
          <div className="relative">
            <button
              type="button"
              onClick={backToTypeStep}
              className="mb-8 inline-flex items-center gap-2 text-sm text-surface-800/55 transition hover:text-brand-500"
            >
              <ArrowLeft size={16} />
              {t.changeAccountType}
            </button>
            <BrandLogo className="h-10" showTagline />
            <div className="mt-6 inline-flex items-center gap-2 rounded-full border border-brand-200 bg-brand-50 px-3 py-1 text-xs font-semibold text-brand-600">
              {accountType === 'individual' ? <User size={14} /> : <Building2 size={14} />}
              {accountCopy?.badge}
            </div>
            <h1 className="mt-6 max-w-md text-3xl font-bold leading-tight text-surface-900">{sidebar.title}</h1>
            <p className="mt-4 max-w-md text-sm leading-relaxed text-surface-800/60">{sidebar.subtitle}</p>
          </div>

          <ul className="relative mt-10 space-y-4 motion-stagger">
            {sidebar.benefits.map((item, index) => {
              const Icon = sidebarIcons[index];
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

          {accountType === 'individual' ? (
            <div className="relative mt-6 rounded-xl border border-surface-200 bg-surface-50/80 px-4 py-3 text-xs text-surface-800/55">
              <Users size={14} className="mb-2 text-brand-500" />
              {t.sidebar.individual.companyOnlyNote}
            </div>
          ) : null}

          <p className="relative mt-8 text-xs text-surface-800/45">{sidebar.footer}</p>
        </aside>

        <main className="relative flex flex-1 items-center justify-center px-4 py-10 sm:px-6 lg:px-10">
          <div className="w-full max-w-lg">
            <div className="mb-6 flex items-center justify-between lg:hidden">
              <button
                type="button"
                onClick={backToTypeStep}
                className="inline-flex items-center gap-2 text-sm text-surface-800/55 transition hover:text-brand-500"
              >
                <ArrowLeft size={16} />
                {t.chooseTypeMobile}
              </button>
              <div className="flex items-center gap-3">
                <LocaleToggle />
                <BrandLogo className="h-8" />
              </div>
            </div>

            <div className="hidden justify-end lg:mb-4 lg:flex">
              <LocaleToggle />
            </div>

            <div className="rounded-2xl border border-surface-200/80 bg-white/90 p-6 shadow-xl shadow-brand-500/5 backdrop-blur-sm sm:p-8">
              <div className="mb-8">
                <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-brand-200 bg-brand-50 px-3 py-1 text-xs font-semibold text-brand-600">
                  <UserPlus size={14} />
                  {accountCopy?.registerBadge}
                </div>
                <h2 className="text-2xl font-bold text-surface-900 sm:text-3xl">{t.form.title}</h2>
                <p className="mt-2 text-sm text-surface-800/60">{accountCopy?.formSubtitle}</p>
              </div>

              <form onSubmit={handleSubmit} className="space-y-5" noValidate>
                {accountType === 'company' ? (
                  <div>
                    <label htmlFor="register-company" className="label-field">
                      {t.form.companyName}
                    </label>
                    <div className="relative">
                      <Building2 size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-surface-800/40" />
                      <input
                        id="register-company"
                        className="input-field pl-9"
                        value={companyName}
                        onChange={(e) => setCompanyName(e.target.value)}
                        onBlur={() => setTouched((prev) => ({ ...prev, companyName: true }))}
                        placeholder={t.form.companyNamePlaceholder}
                        required
                      />
                    </div>
                  </div>
                ) : null}

                <div>
                  <label htmlFor="register-username" className="label-field">
                    {t.form.username}
                  </label>
                  <div className="relative">
                    <User size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-surface-800/40" />
                    <input
                      id="register-username"
                      className={`input-field pl-9 ${usernameError ? 'border-red-300 focus:border-red-400 focus:ring-red-400/20' : ''}`}
                      value={username}
                      onChange={(e) => setUsername(e.target.value)}
                      onBlur={() => setTouched((prev) => ({ ...prev, username: true }))}
                      placeholder={
                        accountType === 'individual'
                          ? t.form.usernamePlaceholderIndividual
                          : t.form.usernamePlaceholderCompany
                      }
                      autoComplete="username"
                      autoFocus
                      required
                    />
                  </div>
                  {usernameError ? (
                    <p className="mt-1.5 text-xs text-red-600">{usernameError}</p>
                  ) : (
                    <p className="mt-1.5 text-xs text-surface-800/40">{t.form.usernameHint}</p>
                  )}
                </div>

                <div>
                  <label htmlFor="register-email" className="label-field">
                    {accountCopy?.emailLabel}
                  </label>
                  <div className="relative">
                    <Mail size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-surface-800/40" />
                    <input
                      id="register-email"
                      type="email"
                      className="input-field pl-9"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      onBlur={() => setTouched((prev) => ({ ...prev, email: true }))}
                      placeholder={accountCopy?.emailPlaceholder}
                      autoComplete="email"
                      required
                    />
                  </div>
                  <p className="mt-1.5 text-xs text-surface-800/40">
                    {accountType === 'company' ? t.form.companyEmailHint : t.form.emailHint}
                  </p>
                  {accountType === 'company' && touched.email && email.trim() && isPersonalEmail(email) ? (
                    <p className="mt-1.5 text-xs text-red-600">{t.errors.personalEmailNotAllowed}</p>
                  ) : null}
                </div>

                <div>
                  <label htmlFor="register-password" className="label-field">
                    {t.form.password}
                  </label>
                  <div className="relative">
                    <Lock size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-surface-800/40" />
                    <input
                      id="register-password"
                      type={showPassword ? 'text' : 'password'}
                      className="input-field pl-9 pr-10"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      onBlur={() => setTouched((prev) => ({ ...prev, password: true }))}
                      placeholder={t.form.passwordPlaceholder}
                      autoComplete="new-password"
                      required
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword((prev) => !prev)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-surface-800/40 transition hover:text-surface-800/70"
                      aria-label={showPassword ? t.form.hidePassword : t.form.showPassword}
                    >
                      {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                    </button>
                  </div>

                  {password ? (
                    <div className="mt-3 space-y-2">
                      <div className="flex items-center gap-3">
                        <div className="flex flex-1 gap-1">
                          {[1, 2, 3].map((segment) => (
                            <div
                              key={segment}
                              className={`h-1.5 flex-1 rounded-full transition-colors ${
                                strength.score >= segment ? strength.color : 'bg-surface-200'
                              }`}
                            />
                          ))}
                        </div>
                        {strength.label ? (
                          <span className="text-xs font-medium text-surface-800/60">{strength.label}</span>
                        ) : null}
                      </div>
                      <ul className="grid gap-1.5 sm:grid-cols-2">
                        {passwordRules.map((rule) => {
                          const ok = rule.test(password);
                          return (
                            <li
                              key={rule.id}
                              className={`flex items-center gap-2 text-xs ${ok ? 'text-emerald-600' : 'text-surface-800/45'}`}
                            >
                              {ok ? <Check size={12} className="shrink-0" /> : <X size={12} className="shrink-0" />}
                              {rule.label}
                            </li>
                          );
                        })}
                      </ul>
                    </div>
                  ) : (
                    <p className="mt-1.5 text-xs text-surface-800/40">{t.form.passwordHint}</p>
                  )}
                </div>

                <div>
                  <label htmlFor="register-password-confirm" className="label-field">
                    {t.form.passwordConfirm}
                  </label>
                  <div className="relative">
                    <Lock size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-surface-800/40" />
                    <input
                      id="register-password-confirm"
                      type={showPasswordConfirm ? 'text' : 'password'}
                      className={`input-field pl-9 pr-10 ${touched.passwordConfirm && passwordConfirm && !passwordsAligned ? 'border-red-300' : ''}`}
                      value={passwordConfirm}
                      onChange={(e) => setPasswordConfirm(e.target.value)}
                      onBlur={() => setTouched((prev) => ({ ...prev, passwordConfirm: true }))}
                      placeholder={t.form.passwordConfirmPlaceholder}
                      autoComplete="new-password"
                      required
                    />
                    <button
                      type="button"
                      onClick={() => setShowPasswordConfirm((prev) => !prev)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-surface-800/40 transition hover:text-surface-800/70"
                      aria-label={showPasswordConfirm ? t.form.hidePassword : t.form.showPassword}
                    >
                      {showPasswordConfirm ? <EyeOff size={16} /> : <Eye size={16} />}
                    </button>
                  </div>
                  {touched.passwordConfirm && passwordConfirm && !passwordsAligned ? (
                    <p className="mt-1.5 text-xs text-red-600">{t.errors.passwordMismatch}</p>
                  ) : null}
                </div>

                <label className="flex cursor-pointer items-start gap-3 rounded-xl border border-surface-200 bg-surface-50/80 px-4 py-3">
                  <input
                    type="checkbox"
                    checked={acceptedTerms}
                    onChange={(e) => setAcceptedTerms(e.target.checked)}
                    className="mt-0.5 h-4 w-4 rounded border-surface-200 text-brand-500 focus:ring-brand-500"
                  />
                  <span className="text-xs leading-relaxed text-surface-800/70">
                    {t.form.termsPrefix}{' '}
                    <strong>{accountCopy?.termsUsage}</strong>{' '}
                    {t.form.termsSuffix}
                  </span>
                </label>

                {error ? (
                  <p className="rounded-xl border border-red-100 bg-red-50 px-4 py-3 text-sm text-red-600">{error}</p>
                ) : null}

                <button
                  type="submit"
                  disabled={!canSubmit}
                  className="btn-primary w-full justify-center py-3 text-base"
                >
                  <UserPlus size={18} />
                  {loading ? t.form.submitting : t.form.submit}
                </button>
              </form>

              <div className="mt-6 border-t border-surface-200 pt-6 text-center">
                <p className="text-sm text-surface-800/60">
                  {t.alreadyHaveAccount}{' '}
                  <button
                    type="button"
                    onClick={onBack}
                    className="font-semibold text-brand-500 transition hover:text-brand-600"
                  >
                    {t.signIn}
                  </button>
                </p>
              </div>
            </div>
          </div>
        </main>
      </div>
    </div>
    </PageTransition>
  );
}
