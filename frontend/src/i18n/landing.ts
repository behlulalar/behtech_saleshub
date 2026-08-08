export type LandingLocale = 'tr' | 'en';

export interface LandingFeature {
  title: string;
  description: string;
}

export interface LandingCopy {
  nav: {
    features: string;
    workflow: string;
    roles: string;
    faq: string;
    login: string;
    register: string;
  };
  hero: {
    badge: string;
    productName: string;
    title: string;
    highlight: string;
    subtitle: string;
    ctaPrimary: string;
    ctaSecondary: string;
  };
  features: {
    title: string;
    subtitle: string;
    items: LandingFeature[];
  };
  workflow: {
    title: string;
    subtitle: string;
    steps: { title: string; description: string }[];
  };
  roles: {
    title: string;
    subtitle: string;
    owner: { title: string; items: string[] };
    employee: { title: string; items: string[] };
  };
  cta: {
    title: string;
    subtitle: string;
    button: string;
  };
  faq: {
    title: string;
    subtitle: string;
    items: { question: string; answer: string }[];
  };
  footer: {
    tagline: string;
    rights: string;
  };
}

export const landingCopy: Record<LandingLocale, LandingCopy> = {
  tr: {
    nav: {
      features: 'Özellikler',
      workflow: 'Nasıl Çalışır',
      roles: 'Ekip Yönetimi',
      faq: 'SSS',
      login: 'Giriş Yap',
      register: 'Ücretsiz Başla',
    },
    hero: {
      badge: 'BehTech Sales Hub',
      productName: 'BehTech Sales Hub',
      title: 'Satış sürecinizi tek panelden',
      highlight: 'profesyonelce yönetin',
      subtitle:
        'Müşteri adaylarını kategorilere ayırın, satış hunisini takip edin, ekibinizle birlikte büyüyün. Küçük işletmeler ve saha ekipleri için tasarlandı.',
      ctaPrimary: 'Ücretsiz Hesap Oluştur',
      ctaSecondary: 'Giriş Yap',
    },
    features: {
      title: 'İhtiyacınız olan her şey, tek yerde',
      subtitle: 'Pazar araştırmasından satışa, analizden gelir takibine kadar uçtan uca CRM deneyimi.',
      items: [
        {
          title: 'Akıllı Dashboard',
          description: 'Günlük görevler, yaklaşan görüşmeler ve cevap bekleyen müşteriler tek ekranda.',
        },
        {
          title: 'Kategori & Etiketler',
          description: 'Sektöre göre müşterilerinizi gruplayın; VIP, sıcak müşteri gibi etiketlerle önceliklendirin.',
        },
        {
          title: 'Satış Hunisi & Analizler',
          description: 'Dönüşüm oranları, şehir/kategori analizi ve verimli iletişim saatlerini keşfedin.',
        },
        {
          title: 'Gelir İstatistikleri',
          description: 'Satış tutarlarını kaydedin; aylık gelir, kategori dağılımı ve ortalama işlem değerini görün.',
        },
        {
          title: 'Talep & Onay Akışı',
          description: 'Personeliniz pazar araştırması talebi göndersin; siz onaylayınca otomatik kategoriye eklensin.',
        },
        {
          title: 'Aktivite Geçmişi',
          description: 'Her görüşme, demo ve teklif otomatik loglanır; müşteri hikayesi kaybolmaz.',
        },
      ],
    },
    workflow: {
      title: 'Nasıl çalışır?',
      subtitle: 'Dakikalar içinde kurulum, hemen kullanıma hazır.',
      steps: [
        {
          title: 'Hesap oluşturun',
          description: 'Şirket sahibi olarak kayıt olun, kategorilerinizi ve etiketlerinizi tanımlayın.',
        },
        {
          title: 'Müşterileri ekleyin',
          description: 'Lead kayıtlarını girin veya personelinizden gelen talepleri onaylayın.',
        },
        {
          title: 'Satışı büyütün',
          description: 'Huni, analiz ve gelir raporlarıyla kararlarınızı veriye dayandırın.',
        },
      ],
    },
    roles: {
      title: 'Ekip için tasarlandı',
      subtitle: 'Sahip tam kontrolde; personel sadece ihtiyacı olanı görür.',
      owner: {
        title: 'Şirket Sahibi',
        items: [
          'Tüm müşteriler, analizler ve gelir raporları',
          'Personel ekleme ve yetki yönetimi',
          'Talep onaylama / reddetme',
          'Kategori ve etiket yönetimi',
        ],
      },
      employee: {
        title: 'Personel',
        items: [
          'Kategori bazlı müşteri listesi (salt okunur)',
          'Pazar araştırması talebi oluşturma',
          'Kendi taleplerinin durumunu takip',
          'Gelir ve teklif bilgilerine erişim yok',
        ],
      },
    },
    cta: {
      title: 'Satış operasyonunuzu bir üst seviyeye taşıyın',
      subtitle: 'BehTech Sales Hub ile müşterilerinizi kaybetmeden büyüyün. Hemen ücretsiz deneyin.',
      button: 'Hemen Başla — Ücretsiz',
    },
    faq: {
      title: 'Sıkça Sorulan Sorular',
      subtitle: 'Müşteri takip programı ve BehTech Sales Hub hakkında merak edilenler.',
      items: [
        {
          question: 'BehTech Sales Hub nedir?',
          answer:
            'BehTech Sales Hub, küçük işletmeler ve saha satış ekipleri için geliştirilmiş bir müşteri takip ve satış CRM yazılımıdır. Müşteri adaylarını kategorilere ayırmanız, satış hunisini takip etmeniz, ekibinizle birlikte çalışmanız ve gelir analizi yapmanız için tek panel sunar.',
        },
        {
          question: 'Müşteri takip programı ne işe yarar?',
          answer:
            'Müşteri takip programı; potansiyel müşterilerinizi kaydetmenizi, görüşme ve demo süreçlerini izlemenizi, teklif aşamasını yönetmenizi ve satışa dönüşen müşterileri raporlamanızı sağlar. Excel veya not defteri yerine tüm süreci merkezi bir sistemde yönetirsiniz.',
        },
        {
          question: 'BehTech Sales Hub ücretsiz mi?',
          answer:
            'Evet, hesap oluşturma ücretsizdir. Kayıt olduktan sonra kategorilerinizi tanımlayıp müşteri kayıtlarınızı eklemeye hemen başlayabilirsiniz.',
        },
        {
          question: 'Ekibimle birlikte kullanabilir miyim?',
          answer:
            'Evet. Şirket sahibi olarak personel hesapları oluşturabilir, talep-onay akışı ile pazar araştırması kayıtlarını yönetebilirsiniz. Personel yalnızca yetkili olduğu kategorileri görür; gelir ve teklif bilgilerine erişemez.',
        },
        {
          question: 'Mobil telefonda kullanılabilir mi?',
          answer:
            'Evet. BehTech Sales Hub mobil uyumludur. Telefon veya tabletten müşteri listelerinize, dashboard\'unuza ve taleplerinize erişebilirsiniz.',
        },
        {
          question: 'Hangi sektörler için uygundur?',
          answer:
            'Kuaför, güzellik salonu, restoran, perakende, yazılım satışı, saha satış ekipleri ve B2B satış yapan tüm küçük-orta ölçekli işletmeler için uygundur. Kategori ve etiket sistemi sayesinde sektörünüze göre özelleştirebilirsiniz.',
        },
        {
          question: 'Verilerim güvende mi?',
          answer:
            'Hesaplar şifre korumalıdır, oturum yönetimi ve e-posta doğrulama desteklenir. Verileriniz yalnızca sizin hesabınıza bağlıdır; başka kullanıcılar erişemez.',
        },
        {
          question: 'Nasıl başlarım?',
          answer:
            'Ücretsiz hesap oluştur butonuna tıklayın, kayıt formunu doldurun ve e-posta doğrulamasını tamamlayın. Ardından kategorilerinizi oluşturup ilk müşteri kaydınızı ekleyebilirsiniz.',
        },
      ],
    },
    footer: {
      tagline: 'Beyond The Code',
      rights: 'BehTech. Tüm hakları saklıdır.',
    },
  },
  en: {
    nav: {
      features: 'Features',
      workflow: 'How It Works',
      roles: 'Team Access',
      faq: 'FAQ',
      login: 'Sign In',
      register: 'Get Started',
    },
    hero: {
      badge: 'BehTech Sales Hub',
      productName: 'BehTech Sales Hub',
      title: 'Run your entire sales pipeline',
      highlight: 'from one modern hub',
      subtitle:
        'Organize leads by category, track your funnel, and scale with your team. Built for small businesses and field sales teams.',
      ctaPrimary: 'Create Free Account',
      ctaSecondary: 'Sign In',
    },
    features: {
      title: 'Everything you need in one place',
      subtitle: 'End-to-end CRM from prospecting to revenue — analytics included.',
      items: [
        {
          title: 'Smart Dashboard',
          description: 'Daily tasks, upcoming meetings, and leads awaiting follow-up on one screen.',
        },
        {
          title: 'Categories & Tags',
          description: 'Group customers by industry; prioritize with VIP, hot lead, and custom tags.',
        },
        {
          title: 'Funnel & Analytics',
          description: 'Conversion rates, city/category insights, and best outreach times.',
        },
        {
          title: 'Revenue Insights',
          description: 'Log deal values; view monthly revenue, category breakdown, and average deal size.',
        },
        {
          title: 'Request & Approval',
          description: 'Staff submit market research requests; you approve and they land in the right category.',
        },
        {
          title: 'Activity Timeline',
          description: 'Every call, demo, and quote logged automatically — full customer history.',
        },
      ],
    },
    workflow: {
      title: 'How it works',
      subtitle: 'Set up in minutes. Ready to use immediately.',
      steps: [
        {
          title: 'Create your account',
          description: 'Register as company owner and set up categories and tags.',
        },
        {
          title: 'Add your leads',
          description: 'Enter prospects manually or approve submissions from your team.',
        },
        {
          title: 'Grow revenue',
          description: 'Use funnel, analytics, and revenue reports to make data-driven decisions.',
        },
      ],
    },
    roles: {
      title: 'Built for teams',
      subtitle: 'Owners stay in control; staff see only what they need.',
      owner: {
        title: 'Company Owner',
        items: [
          'Full access to customers, analytics & revenue',
          'Add and manage staff accounts',
          'Approve or reject lead requests',
          'Manage categories and tags',
        ],
      },
      employee: {
        title: 'Staff',
        items: [
          'Category-based customer list (read-only)',
          'Submit market research requests',
          'Track own request status',
          'No access to revenue or offer amounts',
        ],
      },
    },
    cta: {
      title: 'Take your sales operation to the next level',
      subtitle: 'Grow without losing track of customers. Try BehTech Sales Hub free today.',
      button: 'Get Started — Free',
    },
    faq: {
      title: 'Frequently Asked Questions',
      subtitle: 'Common questions about customer tracking and BehTech Sales Hub.',
      items: [
        {
          question: 'What is BehTech Sales Hub?',
          answer:
            'BehTech Sales Hub is a customer tracking and sales CRM built for small businesses and field sales teams. It gives you one dashboard to organize leads by category, track your sales funnel, collaborate with staff, and analyze revenue.',
        },
        {
          question: 'What does a customer tracking system do?',
          answer:
            'A customer tracking system lets you record prospects, follow meetings and demos, manage quotes, and report on closed deals. Instead of spreadsheets or notes, you run the entire sales process from one central hub.',
        },
        {
          question: 'Is BehTech Sales Hub free?',
          answer:
            'Yes — creating an account is free. After registration you can set up categories and start adding customer records right away.',
        },
        {
          question: 'Can I use it with my team?',
          answer:
            'Yes. As company owner you can create staff accounts and manage a request-and-approval flow for market research leads. Staff only see authorized categories and cannot access revenue or offer amounts.',
        },
        {
          question: 'Does it work on mobile?',
          answer:
            'Yes. BehTech Sales Hub is mobile-friendly. You can access customer lists, your dashboard, and requests from phone or tablet.',
        },
        {
          question: 'Which industries is it suitable for?',
          answer:
            'Salons, restaurants, retail, software sales, field sales teams, and any SMB doing B2B or B2C outreach. Categories and tags let you tailor the CRM to your industry.',
        },
        {
          question: 'Is my data secure?',
          answer:
            'Accounts are password-protected with session management and email verification. Your data belongs only to your account — other users cannot access it.',
        },
        {
          question: 'How do I get started?',
          answer:
            'Click Create Free Account, complete the registration form, and verify your email. Then create your categories and add your first customer record.',
        },
      ],
    },
    footer: {
      tagline: 'Beyond The Code',
      rights: 'BehTech. All rights reserved.',
    },
  },
};

export const LOCALE_STORAGE_KEY = 'behtech_landing_locale';

export function getStoredLocale(): LandingLocale {
  const stored = localStorage.getItem(LOCALE_STORAGE_KEY);
  return stored === 'en' ? 'en' : 'tr';
}

export function storeLocale(locale: LandingLocale) {
  localStorage.setItem(LOCALE_STORAGE_KEY, locale);
}
