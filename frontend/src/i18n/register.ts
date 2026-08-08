import type { LandingLocale } from './landing';

export interface RegisterCopy {
  backHome: string;
  backHomeShort: string;
  changeAccountType: string;
  chooseTypeMobile: string;
  signIn: string;
  alreadyHaveAccount: string;
  typeStep: {
    badge: string;
    title: string;
    subtitle: string;
    continue: string;
  };
  accountTypes: {
    individual: {
      title: string;
      description: string;
      highlights: string[];
      badge: string;
      registerBadge: string;
      formSubtitle: string;
      emailLabel: string;
      emailPlaceholder: string;
      termsUsage: string;
    };
    company: {
      title: string;
      description: string;
      highlights: string[];
      badge: string;
      registerBadge: string;
      formSubtitle: string;
      emailLabel: string;
      emailPlaceholder: string;
      termsUsage: string;
    };
  };
  sidebar: {
    individual: {
      title: string;
      subtitle: string;
      footer: string;
      companyOnlyNote: string;
      benefits: { title: string; description: string }[];
    };
    company: {
      title: string;
      subtitle: string;
      footer: string;
      benefits: { title: string; description: string }[];
    };
  };
  form: {
    title: string;
    companyName: string;
    companyNamePlaceholder: string;
    username: string;
    usernameHint: string;
    usernamePlaceholderIndividual: string;
    usernamePlaceholderCompany: string;
    password: string;
    passwordConfirm: string;
    passwordPlaceholder: string;
    passwordConfirmPlaceholder: string;
    passwordHint: string;
    emailHint: string;
    companyEmailHint: string;
    termsPrefix: string;
    termsSuffix: string;
    submit: string;
    submitting: string;
    showPassword: string;
    hidePassword: string;
  };
  passwordRules: {
    length: string;
    upper: string;
    lower: string;
    digit: string;
    special: string;
  };
  passwordStrength: {
    weak: string;
    medium: string;
    strong: string;
  };
  errors: {
    usernameLength: string;
    usernameChars: string;
    passwordRequirements: string;
    passwordMismatch: string;
    personalEmailNotAllowed: string;
    companyNameRequired: string;
    termsRequired: string;
    registerFailed: string;
  };
  verification: {
    title: string;
    message: string;
    resend: string;
    resending: string;
    resent: string;
    backToLogin: string;
  };
}

export const registerCopy: Record<LandingLocale, RegisterCopy> = {
  tr: {
    backHome: 'Ana sayfaya dön',
    backHomeShort: 'Ana sayfa',
    changeAccountType: 'Hesap türünü değiştir',
    chooseTypeMobile: 'Tür seç',
    signIn: 'Giriş yapın',
    alreadyHaveAccount: 'Zaten hesabınız var mı?',
    typeStep: {
      badge: 'Hesap türü seçin',
      title: 'Nasıl kullanacaksınız?',
      subtitle:
        'İhtiyacınıza uygun hesap türünü seçin. Bireysel hesaplarda ekip ve personel özellikleri yer almaz; şirket hesaplarında tüm işletme araçları açıktır.',
      continue: 'Devam et',
    },
    accountTypes: {
      individual: {
        title: 'Bireysel Kullanım',
        description: 'Kişisel müşteri takibi ve satış sürecinizi yönetmek için.',
        highlights: ['Kişisel CRM paneli', 'Kategori & etiket yönetimi', 'Satış hunisi & analizler'],
        badge: 'Bireysel hesap',
        registerBadge: 'Bireysel kayıt',
        formSubtitle:
          'Kişisel müşteri takip paneliniz hazır olacak. Kategorilerinizi ve etiketlerinizi dilediğiniz gibi düzenleyin.',
        emailLabel: 'E-posta',
        emailPlaceholder: 'siz@email.com',
        termsUsage: 'kişisel',
      },
      company: {
        title: 'Şirket Kullanımı',
        description: 'Ekip, personel talepleri ve gelir takibi ile tam işletme yönetimi.',
        highlights: ['Personel & talep akışı', 'Gelir istatistikleri', 'Ekip rolleri (sahip/personel)'],
        badge: 'Şirket hesabı',
        registerBadge: 'Şirket kaydı',
        formSubtitle: 'Şirket sahibi olarak kayıt olun. Ekibinizi ve kategorilerinizi siz yapılandırırsınız.',
        emailLabel: 'İş e-postası',
        emailPlaceholder: 'siz@sirket.com',
        termsUsage: 'iş amaçlı',
      },
    },
    sidebar: {
      individual: {
        title: 'Kişisel müşteri takibiniz için sade arayüz',
        subtitle:
          'Bireysel hesabınızda müşterilerinizi düzenleyin, sürecinizi takip edin. Ekip ve personel özellikleri olmadan odaklanmış bir deneyim.',
        footer: 'BehTech Sales Hub · Bireysel hesap',
        companyOnlyNote:
          'Personel ekleme, talep onayı ve gelir istatistikleri yalnızca şirket hesaplarında kullanılabilir.',
        benefits: [
          { title: 'Kişisel panel', description: 'Müşterilerinizi kategoriler ve etiketlerle düzenleyin.' },
          { title: 'Satış hunisi', description: 'Lead’den müşteriye tüm süreci tek ekranda izleyin.' },
          { title: 'Etiket & kategori', description: 'Kayıtlarınızı kendi yapınıza göre gruplayın.' },
        ],
      },
      company: {
        title: 'İşletmeniz için modern müşteri takip altyapısı',
        subtitle:
          'Ekibinizi yönetin, personel taleplerini onaylayın, gelir performansını ölçün ve satış sürecinizi tek panelden takip edin.',
        footer: 'BehTech Sales Hub · Şirket hesabı',
        benefits: [
          { title: 'Şirket paneli', description: 'Tüm kategoriler ve müşteriler tek merkezden yönetilir.' },
          { title: 'Gelir istatistikleri', description: 'Satış tutarlarını kaydedin, performansı ölçün.' },
          { title: 'Ekip yönetimi', description: 'Personel ekleyin, talepleri onaylayın ve kontrolü elinizde tutun.' },
        ],
      },
    },
    form: {
      title: 'Hesabınızı oluşturun',
      companyName: 'Şirket adı',
      companyNamePlaceholder: 'Örn. Zephyr Labs',
      username: 'Kullanıcı adı',
      usernameHint: '3-30 karakter · harf, rakam, alt çizgi',
      usernamePlaceholderIndividual: 'ahmet_yilmaz',
      usernamePlaceholderCompany: 'ornek_sirket',
      password: 'Şifre',
      passwordConfirm: 'Şifre tekrar',
      passwordPlaceholder: 'Güçlü bir şifre belirleyin',
      passwordConfirmPlaceholder: 'Şifrenizi tekrar girin',
      passwordHint: 'En az 8 karakter, büyük/küçük harf, rakam ve özel karakter',
      emailHint: 'Şifre sıfırlama ve bildirimler için kullanılır',
      companyEmailHint: 'Kurumsal e-posta kullanın (@sirket.com). Gmail, Hotmail vb. kabul edilmez.',
      termsPrefix: 'Hesabımı oluşturarak platformu',
      termsSuffix: 'kullanacağımı ve hesap bilgilerimin güvenli şekilde saklanacağını kabul ediyorum.',
      submit: 'Hesabımı Oluştur',
      submitting: 'Hesap oluşturuluyor...',
      showPassword: 'Şifreyi göster',
      hidePassword: 'Şifreyi gizle',
    },
    passwordRules: {
      length: 'En az 8 karakter',
      upper: 'En az bir büyük harf',
      lower: 'En az bir küçük harf',
      digit: 'En az bir rakam',
      special: 'En az bir özel karakter',
    },
    passwordStrength: {
      weak: 'Zayıf',
      medium: 'Orta',
      strong: 'Güçlü',
    },
    errors: {
      usernameLength: 'Kullanıcı adı 3-30 karakter olmalıdır',
      usernameChars: 'Sadece harf, rakam ve alt çizgi kullanılabilir',
      passwordRequirements: 'Şifre güvenlik gereksinimlerini karşılamıyor',
      passwordMismatch: 'Şifreler eşleşmiyor',
      personalEmailNotAllowed: 'Şirket hesapları için kurumsal e-posta kullanın (Gmail, Hotmail vb. kabul edilmez)',
      companyNameRequired: 'Şirket adı gereklidir',
      termsRequired: 'Devam etmek için kullanım koşullarını kabul etmelisiniz',
      registerFailed: 'Kayıt başarısız',
    },
    verification: {
      title: 'E-postanızı doğrulayın',
      message: 'Hesabınız oluşturuldu. Giriş yapmadan önce {email} adresine gönderilen doğrulama bağlantısına tıklayın.',
      resend: 'Doğrulama e-postasını tekrar gönder',
      resending: 'Gönderiliyor...',
      resent: 'Doğrulama e-postası tekrar gönderildi.',
      backToLogin: 'Giriş sayfasına dön',
    },
  },
  en: {
    backHome: 'Back to home',
    backHomeShort: 'Home',
    changeAccountType: 'Change account type',
    chooseTypeMobile: 'Change type',
    signIn: 'Sign in',
    alreadyHaveAccount: 'Already have an account?',
    typeStep: {
      badge: 'Choose account type',
      title: 'How will you use BehTech Sales Hub?',
      subtitle:
        'Pick the account type that fits your needs. Individual accounts exclude team features; company accounts unlock the full business toolkit.',
      continue: 'Continue',
    },
    accountTypes: {
      individual: {
        title: 'Individual Use',
        description: 'For personal customer tracking and managing your own sales pipeline.',
        highlights: ['Personal CRM dashboard', 'Category & tag management', 'Sales funnel & analytics'],
        badge: 'Individual account',
        registerBadge: 'Individual signup',
        formSubtitle:
          'Your personal tracking dashboard will be ready. Organize categories and tags however you like.',
        emailLabel: 'Email',
        emailPlaceholder: 'you@email.com',
        termsUsage: 'personal',
      },
      company: {
        title: 'Company Use',
        description: 'Full business management with team access, staff requests, and revenue tracking.',
        highlights: ['Staff & request workflow', 'Revenue insights', 'Team roles (owner/staff)'],
        badge: 'Company account',
        registerBadge: 'Company signup',
        formSubtitle: 'Register as company owner. You configure your team, categories, and workflow.',
        emailLabel: 'Work email',
        emailPlaceholder: 'you@company.com',
        termsUsage: 'business',
      },
    },
    sidebar: {
      individual: {
        title: 'A focused interface for personal customer tracking',
        subtitle:
          'Organize customers and track your pipeline without team or staff features — a streamlined solo experience.',
        footer: 'BehTech Sales Hub · Individual account',
        companyOnlyNote: 'Staff management, request approvals, and revenue insights are available on company accounts only.',
        benefits: [
          { title: 'Personal dashboard', description: 'Organize customers with categories and tags.' },
          { title: 'Sales funnel', description: 'Track the full journey from lead to customer in one view.' },
          { title: 'Tags & categories', description: 'Group records in a structure that works for you.' },
        ],
      },
      company: {
        title: 'Modern customer tracking for your business',
        subtitle:
          'Manage your team, approve staff requests, measure revenue performance, and run your sales process from one hub.',
        footer: 'BehTech Sales Hub · Company account',
        benefits: [
          { title: 'Company dashboard', description: 'All categories and customers managed from one place.' },
          { title: 'Revenue insights', description: 'Log deal values and measure performance.' },
          { title: 'Team management', description: 'Add staff, approve requests, and stay in control.' },
        ],
      },
    },
    form: {
      title: 'Create your account',
      companyName: 'Company name',
      companyNamePlaceholder: 'e.g. Zephyr Labs',
      username: 'Username',
      usernameHint: '3–30 characters · letters, numbers, underscore',
      usernamePlaceholderIndividual: 'john_doe',
      usernamePlaceholderCompany: 'acme_corp',
      password: 'Password',
      passwordConfirm: 'Confirm password',
      passwordPlaceholder: 'Choose a strong password',
      passwordConfirmPlaceholder: 'Re-enter your password',
      passwordHint: 'At least 8 characters with upper/lowercase, a number, and a special character',
      emailHint: 'Used for password reset and notifications',
      companyEmailHint: 'Use a company email (@company.com). Gmail, Hotmail, etc. are not accepted.',
      termsPrefix: 'By creating my account I agree to use the platform for',
      termsSuffix: 'purposes and that my account details will be stored securely.',
      submit: 'Create My Account',
      submitting: 'Creating account...',
      showPassword: 'Show password',
      hidePassword: 'Hide password',
    },
    passwordRules: {
      length: 'At least 8 characters',
      upper: 'At least one uppercase letter',
      lower: 'At least one lowercase letter',
      digit: 'At least one number',
      special: 'At least one special character',
    },
    passwordStrength: {
      weak: 'Weak',
      medium: 'Fair',
      strong: 'Strong',
    },
    errors: {
      usernameLength: 'Username must be 3–30 characters',
      usernameChars: 'Only letters, numbers, and underscore are allowed',
      passwordRequirements: 'Password does not meet security requirements',
      passwordMismatch: 'Passwords do not match',
      personalEmailNotAllowed: 'Company accounts require a business email (Gmail, Hotmail, etc. are not accepted)',
      companyNameRequired: 'Company name is required',
      termsRequired: 'You must accept the terms to continue',
      registerFailed: 'Registration failed',
    },
    verification: {
      title: 'Verify your email',
      message: 'Your account was created. Before signing in, click the verification link sent to {email}.',
      resend: 'Resend verification email',
      resending: 'Sending...',
      resent: 'Verification email sent again.',
      backToLogin: 'Back to sign in',
    },
  },
};
