import { useEffect, useMemo, useRef, useState } from 'react';
import { AlertCircle, CheckCircle2, Loader2, LogIn, Mail, ShieldCheck } from 'lucide-react';
import { api } from '../api';
import { authCopy } from '../i18n/auth';
import { useLocale } from '../i18n/locale';
import AuthShell, { type AuthBenefit } from './AuthShell';

type VerifyStatus = 'loading' | 'success' | 'error';

interface Props {
  token: string;
  onSuccess: () => void;
  onBackToLogin: () => void;
}

const VERIFY_BENEFIT_ICONS = [Mail, ShieldCheck, LogIn] as const;

export default function VerifyEmail({ token, onSuccess, onBackToLogin }: Props) {
  const { locale } = useLocale();
  const t = authCopy[locale].verifyLink;

  const [status, setStatus] = useState<VerifyStatus>('loading');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const onSuccessRef = useRef(onSuccess);

  useEffect(() => {
    onSuccessRef.current = onSuccess;
  }, [onSuccess]);

  const benefits = useMemo<AuthBenefit[]>(
    () =>
      t.benefits.map((item, index) => ({
        ...item,
        icon: VERIFY_BENEFIT_ICONS[index],
      })),
    [t.benefits],
  );

  useEffect(() => {
    if (!token) {
      setStatus('error');
      setError(t.invalidToken);
      return;
    }

    let cancelled = false;
    setStatus('loading');
    setMessage('');
    setError('');

    api.verifyEmail(token)
      .then((res) => {
        if (cancelled) return;
        setMessage(res.message || t.successDefault);
        setStatus('success');
        window.setTimeout(() => onSuccessRef.current(), 2500);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : t.failed);
        setStatus('error');
      });

    return () => {
      cancelled = true;
    };
  }, [token, t.failed, t.invalidToken, t.successDefault]);

  return (
    <AuthShell
      onBack={onBackToLogin}
      backLabel={authCopy[locale].forgot.backToLogin}
      sidebarTitle={t.sidebarTitle}
      sidebarSubtitle={t.sidebarSubtitle}
      sidebarFooter={t.sidebarFooter}
      benefits={benefits}
    >
      <div className="motion-fade-up rounded-2xl border border-surface-200/80 bg-white/90 p-6 text-center shadow-xl shadow-brand-500/5 backdrop-blur-sm sm:p-8">
        <div className="mb-5 inline-flex items-center rounded-full border border-brand-200/80 bg-brand-50 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-brand-600">
          {t.badge}
        </div>

        <div
          className={`mx-auto mb-5 flex h-16 w-16 items-center justify-center rounded-2xl ${
            status === 'success'
              ? 'bg-emerald-50 text-emerald-600'
              : status === 'error'
                ? 'bg-red-50 text-red-600'
                : 'bg-brand-50 text-brand-500'
          }`}
        >
          {status === 'loading' ? (
            <Loader2 size={28} className="animate-spin" />
          ) : status === 'success' ? (
            <CheckCircle2 size={28} />
          ) : (
            <AlertCircle size={28} />
          )}
        </div>

        <h1 className="text-2xl font-bold text-surface-900">{t.title}</h1>
        <p className="mt-2 text-sm leading-relaxed text-surface-800/60">
          {status === 'loading' ? t.verifying : status === 'success' ? t.redirecting : t.subtitle}
        </p>

        {status === 'loading' && (
          <div className="mt-6 h-1.5 overflow-hidden rounded-full bg-surface-100">
            <div className="h-full w-1/3 animate-pulse rounded-full bg-brand-500" />
          </div>
        )}

        {status === 'success' && message && (
          <p className="mt-5 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
            {message}
          </p>
        )}

        {status === 'error' && error && (
          <p className="mt-5 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-600">{error}</p>
        )}

        {status === 'error' && (
          <button type="button" onClick={onBackToLogin} className="btn-primary mt-6 w-full justify-center">
            <LogIn size={16} />
            {t.backToLogin}
          </button>
        )}
      </div>
    </AuthShell>
  );
}
