export const SITE_URL = (import.meta.env.VITE_SITE_URL || 'https://saleshub.behtechlabs.com').replace(/\/$/, '');
export const SITE_NAME = 'BehTech Sales Hub';
export const DEFAULT_OG_IMAGE = `${SITE_URL}/og-image.png`;

export type SeoRoute =
  | 'landing'
  | 'register'
  | 'login'
  | 'verify-email'
  | 'reset-password'
  | 'app';

export interface SeoMeta {
  title: string;
  description: string;
  path: string;
  robots: string;
  ogType?: string;
}

export const seoCopy = {
  tr: {
    landing: {
      title: 'BehTech Sales Hub | Müşteri Takip ve Satış CRM Yazılımı',
      description:
        'Müşteri adaylarını tek panelden yönetin. Satış hunisi, kategori takibi, ekip yönetimi ve gelir analizi. Küçük işletmeler ve saha ekipleri için BehTech Sales Hub.',
    },
    register: {
      title: 'Ücretsiz Hesap Oluştur | BehTech Sales Hub',
      description:
        'BehTech Sales Hub ile ücretsiz CRM hesabınızı açın. Müşteri takibi, satış süreci ve ekip iş birliği dakikalar içinde hazır.',
    },
    login: {
      title: 'Giriş Yap | BehTech Sales Hub',
      description: 'BehTech Sales Hub müşteri takip panelinize giriş yapın.',
    },
    verifyEmail: {
      title: 'E-posta Doğrulama | BehTech Sales Hub',
      description: 'BehTech Sales Hub hesabınızı doğrulayın.',
    },
    resetPassword: {
      title: 'Şifre Sıfırlama | BehTech Sales Hub',
      description: 'BehTech Sales Hub hesap şifrenizi güvenle sıfırlayın.',
    },
    app: {
      title: 'Panel | BehTech Sales Hub',
      description: 'BehTech Sales Hub müşteri takip paneli.',
    },
  },
  en: {
    landing: {
      title: 'BehTech Sales Hub | Customer Tracking & Sales CRM',
      description:
        'Manage leads from one dashboard. Sales funnel, category tracking, team management and revenue analytics. Built for small businesses and field sales teams.',
    },
    register: {
      title: 'Create Free Account | BehTech Sales Hub',
      description:
        'Open your free BehTech Sales Hub CRM account. Customer tracking, sales pipeline and team collaboration in minutes.',
    },
    login: {
      title: 'Sign In | BehTech Sales Hub',
      description: 'Sign in to your BehTech Sales Hub customer tracking dashboard.',
    },
    verifyEmail: {
      title: 'Email Verification | BehTech Sales Hub',
      description: 'Verify your BehTech Sales Hub account.',
    },
    resetPassword: {
      title: 'Reset Password | BehTech Sales Hub',
      description: 'Securely reset your BehTech Sales Hub account password.',
    },
    app: {
      title: 'Dashboard | BehTech Sales Hub',
      description: 'BehTech Sales Hub customer tracking dashboard.',
    },
  },
} as const;

export function getSeoMeta(
  route: SeoRoute,
  locale: 'tr' | 'en',
): SeoMeta {
  const copy = seoCopy[locale];
  const indexable = route === 'landing' || route === 'register';

  const metaByRoute: Record<SeoRoute, { title: string; description: string; path: string }> = {
    landing: { ...copy.landing, path: '/' },
    register: { ...copy.register, path: '/register' },
    login: { ...copy.login, path: '/login' },
    'verify-email': { ...copy.verifyEmail, path: '/verify-email' },
    'reset-password': { ...copy.resetPassword, path: '/reset-password' },
    app: { ...copy.app, path: '' },
  };

  const meta = metaByRoute[route];

  return {
    ...meta,
    robots: indexable ? 'index, follow' : 'noindex, nofollow',
    ogType: route === 'landing' ? 'website' : 'website',
  };
}
