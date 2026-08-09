import type { LandingLocale } from './landing';

export interface AuthCopy {
  backHome: string;
  login: {
    badge: string;
    title: string;
    subtitle: string;
    username: string;
    usernamePlaceholder: string;
    password: string;
    passwordPlaceholder: string;
    rememberMe: string;
    rememberMeHint: string;
    forgotPassword: string;
    submit: string;
    submitting: string;
    noAccount: string;
    createAccount: string;
    showPassword: string;
    hidePassword: string;
    sidebarTitle: string;
    sidebarSubtitle: string;
    sidebarFooter: string;
    benefits: { title: string; description: string }[];
    loginFailed: string;
  };
  forgot: {
    badge: string;
    title: string;
    subtitle: string;
    identifier: string;
    identifierPlaceholder: string;
    submit: string;
    submitting: string;
    backToLogin: string;
    sidebarTitle: string;
    sidebarSubtitle: string;
    sidebarFooter: string;
    benefits: { title: string; description: string }[];
    requestFailed: string;
  };
  verifyLink: {
    badge: string;
    title: string;
    subtitle: string;
    verifying: string;
    redirecting: string;
    successDefault: string;
    failed: string;
    invalidToken: string;
    backToLogin: string;
    sidebarTitle: string;
    sidebarSubtitle: string;
    sidebarFooter: string;
    benefits: { title: string; description: string }[];
  };
}

export const authCopy: Record<LandingLocale, AuthCopy> = {
  tr: {
    backHome: 'Ana sayfaya dön',
    login: {
      badge: 'Hoş geldiniz',
      title: 'Hesabınıza giriş yapın',
      subtitle: 'Müşteri takip panelinize erişmek için bilgilerinizi girin.',
      username: 'Kullanıcı adı',
      usernamePlaceholder: 'kullaniciadi',
      password: 'Şifre',
      passwordPlaceholder: 'Şifrenizi girin',
      rememberMe: 'Beni hatırla',
      rememberMeHint: '30 gün oturum açık kalır; güvenli oturum çerezi kullanılır (şifre kaydedilmez).',
      forgotPassword: 'Şifremi unuttum',
      submit: 'Giriş Yap',
      submitting: 'Giriş yapılıyor...',
      noAccount: 'Hesabınız yok mu?',
      createAccount: 'Kayıt Ol',
      showPassword: 'Şifreyi göster',
      hidePassword: 'Şifreyi gizle',
      sidebarTitle: 'Müşteri takibinize kaldığınız yerden devam edin',
      sidebarSubtitle:
        'Lead’lerinizi, satış huninizi ve günlük görevlerinizi tek panelden yönetin. Güvenli giriş ile verileriniz korunur.',
      sidebarFooter: 'BehTech Sales Hub · Güvenli oturum',
      benefits: [
        { title: 'Akıllı dashboard', description: 'Günlük görevler ve yaklaşan görüşmeler tek ekranda.' },
        { title: 'Satış hunisi', description: 'Müşteri adaylarından satışa tüm süreci takip edin.' },
        { title: 'Güvenli erişim', description: 'Oturum yönetimi ve şifre sıfırlama ile korumalı giriş.' },
      ],
      loginFailed: 'Kullanıcı adınız veya şifreniz yanlış',
    },
    forgot: {
      badge: 'Şifre sıfırlama',
      title: 'Şifrenizi mi unuttunuz?',
      subtitle: 'Kullanıcı adınızı veya e-posta adresinizi girin. Kayıtlıysa sıfırlama bağlantısı gönderilir.',
      identifier: 'Kullanıcı adı veya e-posta',
      identifierPlaceholder: 'kullaniciadi veya siz@email.com',
      submit: 'Sıfırlama Bağlantısı Gönder',
      submitting: 'Gönderiliyor...',
      backToLogin: 'Giriş sayfasına dön',
      sidebarTitle: 'Hesabınıza tekrar erişin',
      sidebarSubtitle:
        'E-posta adresinize güvenli bir sıfırlama bağlantısı gönderilir. Bağlantı sınırlı süre geçerlidir.',
      sidebarFooter: 'BehTech Sales Hub · Hesap kurtarma',
      benefits: [
        { title: 'Hızlı kurtarma', description: 'Kayıtlı e-posta ile birkaç adımda şifrenizi yenileyin.' },
        { title: 'Güvenli süreç', description: 'Tek kullanımlık bağlantılar ve süre sınırı ile koruma.' },
        { title: 'Kesintisiz devam', description: 'Şifrenizi güncelledikten sonra hemen giriş yapabilirsiniz.' },
      ],
      requestFailed: 'İşlem başarısız',
    },
    verifyLink: {
      badge: 'E-posta doğrulama',
      title: 'Hesabınız doğrulanıyor',
      subtitle: 'Güvenliğiniz için e-posta adresinizi onaylamanız gerekiyor. Bu işlem otomatik olarak tamamlanır.',
      verifying: 'Doğrulama bağlantınız kontrol ediliyor...',
      redirecting: 'Giriş sayfasına yönlendiriliyorsunuz...',
      successDefault: 'E-posta adresiniz başarıyla doğrulandı.',
      failed: 'Doğrulama başarısız',
      invalidToken: 'Geçersiz veya eksik doğrulama bağlantısı.',
      backToLogin: 'Giriş sayfasına dön',
      sidebarTitle: 'Hesabınızı güvenle etkinleştirin',
      sidebarSubtitle:
        'Doğrulama bağlantısı tek kullanımlıktır ve sınırlı süre geçerlidir. İşlem tamamlandığında panele giriş yapabilirsiniz.',
      sidebarFooter: 'BehTech Sales Hub · Hesap güvenliği',
      benefits: [
        { title: 'Güvenli aktivasyon', description: 'Yalnızca size ait e-posta ile hesap doğrulaması yapılır.' },
        { title: 'Hızlı işlem', description: 'Bağlantıya tıkladığınızda doğrulama birkaç saniye içinde tamamlanır.' },
        { title: 'Kesintisiz erişim', description: 'Doğrulama sonrası tüm CRM özelliklerine erişim açılır.' },
      ],
    },
  },
  en: {
    backHome: 'Back to home',
    login: {
      badge: 'Welcome back',
      title: 'Sign in to your account',
      subtitle: 'Enter your credentials to access your customer tracking dashboard.',
      username: 'Username',
      usernamePlaceholder: 'username',
      password: 'Password',
      passwordPlaceholder: 'Enter your password',
      rememberMe: 'Remember me',
      rememberMeHint: 'Stay signed in for 30 days via a secure session cookie (password is never stored).',
      forgotPassword: 'Forgot password?',
      submit: 'Sign In',
      submitting: 'Signing in...',
      noAccount: "Don't have an account?",
      createAccount: 'Create Account',
      showPassword: 'Show password',
      hidePassword: 'Hide password',
      sidebarTitle: 'Pick up right where you left off',
      sidebarSubtitle:
        'Manage leads, your sales funnel, and daily tasks from one hub. Your data stays protected with secure sign-in.',
      sidebarFooter: 'BehTech Sales Hub · Secure session',
      benefits: [
        { title: 'Smart dashboard', description: 'Daily tasks and upcoming meetings on one screen.' },
        { title: 'Sales funnel', description: 'Track the full journey from lead to customer.' },
        { title: 'Secure access', description: 'Protected sign-in with session management and password reset.' },
      ],
      loginFailed: 'Your username or password is incorrect',
    },
    forgot: {
      badge: 'Password reset',
      title: 'Forgot your password?',
      subtitle: 'Enter your username or email. If registered, we will send a reset link.',
      identifier: 'Username or email',
      identifierPlaceholder: 'username or you@email.com',
      submit: 'Send Reset Link',
      submitting: 'Sending...',
      backToLogin: 'Back to sign in',
      sidebarTitle: 'Regain access to your account',
      sidebarSubtitle:
        'A secure reset link will be sent to your registered email. Links expire after a limited time.',
      sidebarFooter: 'BehTech Sales Hub · Account recovery',
      benefits: [
        { title: 'Quick recovery', description: 'Reset your password in a few steps via registered email.' },
        { title: 'Secure process', description: 'One-time links with expiration for your protection.' },
        { title: 'Seamless return', description: 'Sign in immediately after updating your password.' },
      ],
      requestFailed: 'Request failed',
    },
    verifyLink: {
      badge: 'Email verification',
      title: 'Verifying your account',
      subtitle: 'For your security, we need to confirm your email address. This completes automatically.',
      verifying: 'Checking your verification link...',
      redirecting: 'Redirecting you to sign in...',
      successDefault: 'Your email address was verified successfully.',
      failed: 'Verification failed',
      invalidToken: 'Invalid or missing verification link.',
      backToLogin: 'Back to sign in',
      sidebarTitle: 'Activate your account securely',
      sidebarSubtitle:
        'Verification links are single-use and expire after a limited time. Once complete, you can sign in to your dashboard.',
      sidebarFooter: 'BehTech Sales Hub · Account security',
      benefits: [
        { title: 'Secure activation', description: 'Your account is verified only through your own email address.' },
        { title: 'Fast process', description: 'Verification completes within seconds after you open the link.' },
        { title: 'Full access', description: 'After verification, all CRM features become available.' },
      ],
    },
  },
};
