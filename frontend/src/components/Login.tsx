import { useEffect, useMemo, useState } from 'react';
import {
  BarChart3,
  Eye,
  EyeOff,
  LayoutDashboard,
  Lock,
  LogIn,
  Mail,
  ShieldCheck,
  User,
} from 'lucide-react';
import { api, saveAuth } from '../api';
import {
  getUsername,
  getSavedPassword,
  getRememberPreference,
  setRememberPreference,
  persistRememberCredentials,
  clearRememberCredentials,
  setUsername as persistUsername,
  setSavedPassword,
} from '../auth';
import { authCopy } from '../i18n/auth';
import { useLocale } from '../i18n/locale';
import AuthShell, { type AuthBenefit } from './AuthShell';
import PageTransition, { transitionVariant } from './PageTransition';
import RegisterPage from './RegisterPage';

type AuthView = 'login' | 'register' | 'forgot';

interface Props {
  onLogin: () => void;
  initialView?: AuthView;
  onViewChange?: (view: AuthView) => void;
  onHome?: () => void;
}

const LOGIN_BENEFIT_ICONS = [LayoutDashboard, BarChart3, ShieldCheck] as const;
const FORGOT_BENEFIT_ICONS = [Mail, ShieldCheck, LogIn] as const;

function AuthCard({ children }: { children: React.ReactNode }) {
  return (
    <div className="motion-fade-up rounded-2xl border border-surface-200/80 bg-white/90 p-6 shadow-xl shadow-brand-500/5 backdrop-blur-sm sm:p-8">
      {children}
    </div>
  );
}

export default function Login({ onLogin, initialView = 'login', onViewChange, onHome }: Props) {
  const [view, setView] = useState<AuthView>(initialView);
  const { locale } = useLocale();
  const [username, setUsername] = useState(() => getUsername() || '');
  const [password, setPassword] = useState(() => (getRememberPreference() ? getSavedPassword() || '' : ''));
  const [rememberMe, setRememberMe] = useState(() => getRememberPreference());
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [transitionDir, setTransitionDir] = useState<'forward' | 'back'>('forward');

  const t = authCopy[locale];

  useEffect(() => {
    setView(initialView);
  }, [initialView]);

  useEffect(() => {
    if (!getRememberPreference()) return;
    setRememberMe(true);
    const savedUser = getUsername();
    const savedPass = getSavedPassword();
    if (savedUser) setUsername(savedUser);
    if (savedPass) setPassword(savedPass);
  }, []);

  const switchView = (v: AuthView) => {
    setTransitionDir(v === 'login' ? 'back' : 'forward');
    setView(v);
    setError('');
    onViewChange?.(v);
  };

  const loginBenefits = useMemo<AuthBenefit[]>(
    () =>
      t.login.benefits.map((item, index) => ({
        ...item,
        icon: LOGIN_BENEFIT_ICONS[index],
      })),
    [t.login.benefits],
  );

  const handleRememberChange = (checked: boolean) => {
    setRememberMe(checked);
    setRememberPreference(checked);
    if (checked) {
      persistRememberCredentials(username, password);
    } else {
      clearRememberCredentials();
      setPassword('');
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const res = await api.login(username.trim(), password, rememberMe);
      saveAuth(res, rememberMe, password);
      onLogin();
    } catch (err) {
      setError(err instanceof Error ? err.message : t.login.loginFailed);
    } finally {
      setLoading(false);
    }
  };

  if (view === 'register') {
    return <RegisterPage onSuccess={onLogin} onBack={() => switchView('login')} onHome={onHome} />;
  }

  if (view === 'forgot') {
    return (
      <PageTransition transitionKey="auth-forgot" variant={transitionVariant(transitionDir)}>
        <ForgotForm onBack={() => switchView('login')} />
      </PageTransition>
    );
  }

  return (
    <PageTransition transitionKey="auth-login" variant={transitionVariant(transitionDir)}>
      <AuthShell
      onHome={onHome}
      backLabel={t.backHome}
      sidebarTitle={t.login.sidebarTitle}
      sidebarSubtitle={t.login.sidebarSubtitle}
      sidebarFooter={t.login.sidebarFooter}
      benefits={loginBenefits}
    >
      <AuthCard>
        <div className="mb-8">
          <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-brand-200 bg-brand-50 px-3 py-1 text-xs font-semibold text-brand-600">
            <LogIn size={14} />
            {t.login.badge}
          </div>
          <h1 className="text-2xl font-bold text-surface-900 sm:text-3xl">{t.login.title}</h1>
          <p className="mt-2 text-sm text-surface-800/60">{t.login.subtitle}</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-5" noValidate>
          <div>
            <label htmlFor="login-username" className="label-field">
              {t.login.username}
            </label>
            <div className="relative">
              <User size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-surface-800/40" />
              <input
                id="login-username"
                className="input-field pl-9"
                value={username}
                onChange={(e) => {
                  const next = e.target.value;
                  setUsername(next);
                  if (rememberMe && next.trim()) persistUsername(next.trim());
                }}
                placeholder={t.login.usernamePlaceholder}
                autoComplete="username"
                autoFocus
                required
              />
            </div>
          </div>

          <div>
            <label htmlFor="login-password" className="label-field">
              {t.login.password}
            </label>
            <div className="relative">
              <Lock size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-surface-800/40" />
              <input
                id="login-password"
                type={showPassword ? 'text' : 'password'}
                className="input-field pl-9 pr-10"
                value={password}
                onChange={(e) => {
                  const next = e.target.value;
                  setPassword(next);
                  if (rememberMe && next) setSavedPassword(next);
                }}
                placeholder={t.login.passwordPlaceholder}
                autoComplete="current-password"
                required
              />
              <button
                type="button"
                onClick={() => setShowPassword((prev) => !prev)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-surface-800/40 transition hover:text-surface-800/70"
                aria-label={showPassword ? t.login.hidePassword : t.login.showPassword}
              >
                {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </div>

          <div className="flex items-center justify-between gap-3">
            <label className="flex cursor-pointer items-center gap-2 text-sm text-surface-800/70">
              <input
                type="checkbox"
                checked={rememberMe}
                onChange={(e) => handleRememberChange(e.target.checked)}
                className="h-4 w-4 rounded border-surface-200 text-brand-500 focus:ring-brand-500"
              />
              {t.login.rememberMe}
            </label>
            <button
              type="button"
              onClick={() => switchView('forgot')}
              className="text-sm font-medium text-brand-500 transition hover:text-brand-600"
            >
              {t.login.forgotPassword}
            </button>
          </div>

          {error ? (
            <p className="rounded-xl border border-red-100 bg-red-50 px-4 py-3 text-sm text-red-600">{error}</p>
          ) : null}

          <button type="submit" disabled={loading} className="btn-primary w-full justify-center py-3 text-base">
            <LogIn size={18} />
            {loading ? t.login.submitting : t.login.submit}
          </button>
        </form>

        <div className="mt-6 border-t border-surface-200 pt-6 text-center">
          <p className="text-sm text-surface-800/60">
            {t.login.noAccount}{' '}
            <button
              type="button"
              onClick={() => switchView('register')}
              className="font-semibold text-brand-500 transition hover:text-brand-600"
            >
              {t.login.createAccount}
            </button>
          </p>
        </div>
      </AuthCard>
    </AuthShell>
    </PageTransition>
  );
}

function ForgotForm({ onBack }: { onBack: () => void }) {
  const { locale } = useLocale();
  const [identifier, setIdentifier] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const t = authCopy[locale];

  const forgotBenefits = useMemo<AuthBenefit[]>(
    () =>
      t.forgot.benefits.map((item, index) => ({
        ...item,
        icon: FORGOT_BENEFIT_ICONS[index],
      })),
    [t.forgot.benefits],
  );

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setMessage('');
    setLoading(true);
    try {
      const res = await api.forgotPassword(identifier.trim());
      setMessage(res.message);
    } catch (err) {
      setError(err instanceof Error ? err.message : t.forgot.requestFailed);
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthShell
      onBack={onBack}
      backLabel={t.forgot.backToLogin}
      sidebarTitle={t.forgot.sidebarTitle}
      sidebarSubtitle={t.forgot.sidebarSubtitle}
      sidebarFooter={t.forgot.sidebarFooter}
      benefits={forgotBenefits}
    >
      <AuthCard>
        <div className="mb-8">
          <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-brand-200 bg-brand-50 px-3 py-1 text-xs font-semibold text-brand-600">
            <Mail size={14} />
            {t.forgot.badge}
          </div>
          <h1 className="text-2xl font-bold text-surface-900 sm:text-3xl">{t.forgot.title}</h1>
          <p className="mt-2 text-sm text-surface-800/60">{t.forgot.subtitle}</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-5" noValidate>
          <div>
            <label htmlFor="forgot-identifier" className="label-field">
              {t.forgot.identifier}
            </label>
            <div className="relative">
              <User size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-surface-800/40" />
              <input
                id="forgot-identifier"
                className="input-field pl-9"
                value={identifier}
                onChange={(e) => setIdentifier(e.target.value)}
                placeholder={t.forgot.identifierPlaceholder}
                autoComplete="username"
                autoFocus
                required
              />
            </div>
          </div>

          {message ? (
            <p className="rounded-xl border border-emerald-100 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
              {message}
            </p>
          ) : null}
          {error ? (
            <p className="rounded-xl border border-red-100 bg-red-50 px-4 py-3 text-sm text-red-600">{error}</p>
          ) : null}

          <button type="submit" disabled={loading} className="btn-primary w-full justify-center py-3 text-base">
            <Mail size={18} />
            {loading ? t.forgot.submitting : t.forgot.submit}
          </button>
        </form>

        <div className="mt-6 border-t border-surface-200 pt-6 text-center">
          <button
            type="button"
            onClick={onBack}
            className="text-sm font-semibold text-brand-500 transition hover:text-brand-600"
          >
            {t.forgot.backToLogin}
          </button>
        </div>
      </AuthCard>
    </AuthShell>
  );
}
