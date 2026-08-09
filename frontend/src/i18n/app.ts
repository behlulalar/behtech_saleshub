import type { AnalyticsView, IntelligenceView } from '../types';
import type { LandingLocale } from './landing';

export interface AppCopy {
  sidebar: {
    dashboard: string;
    revenue: string;
    requests: string;
    myRequests: string;
    reports: string;
    leadDiscovery: string;
    analytics: string;
    intelligence: string;
    categories: string;
    noCategoriesOwner: string;
    noCategoriesEmployee: string;
    organization: string;
    settings: string;
    manageCategories: string;
    manageTags: string;
    manageEmployees: string;
    accountSettings: string;
    expandSection: string;
    collapseSection: string;
    analyticsItems: Record<AnalyticsView, string>;
    intelligenceItems: Record<IntelligenceView, string>;
  };
  header: {
    logout: string;
    employee: string;
    individual: string;
    accountSettings: string;
    openMenu: string;
    closeMenu: string;
  };
  accountSettings: {
    title: string;
    subtitle: string;
    profileSection: string;
    passwordSection: string;
    username: string;
    email: string;
    companyName: string;
    accountType: string;
    role: string;
    emailStatus: string;
    verified: string;
    unverified: string;
    resendVerification: string;
    resending: string;
    verificationSent: string;
    currentPassword: string;
    newPassword: string;
    confirmPassword: string;
    save: string;
    saving: string;
    saved: string;
    owner: string;
    employee: string;
    company: string;
    individual: string;
    passwordHint: string;
    emailChangeNote: string;
    deleteSection: string;
    deleteWarningOwner: string;
    deleteWarningEmployee: string;
    deletePassword: string;
    confirmUsername: string;
    confirmUsernameHint: string;
    deleteAccount: string;
    deleting: string;
    deleteConfirmOwner: string;
    deleteConfirmEmployee: string;
  };
  views: {
    dashboard: { title: string; description: string };
    revenue: { title: string; description: string };
    reports: { title: string; description: string };
    requests: { title: string; description: string };
    myRequests: { title: string; description: string };
    selectCategory: string;
    customers: string;
    categoryTracking: string;
    categoryReadOnly: string;
    analytics: Record<AnalyticsView, { title: string; description: string }>;
    intelligence: Record<IntelligenceView, { title: string; description: string }>;
  };
  reports: {
    weekly: string;
    monthly: string;
    weeklyDesc: string;
    monthlyDesc: string;
    loading: string;
    loadFailed: string;
    retry: string;
    exportFailed: string;
    downloading: string;
    creating: string;
    csv: string;
    excel: string;
    pdf: string;
    newLeads: string;
    newCustomers: string;
    conversionRate: string;
    funnelEndRate: string;
    periodRevenue: string;
    salesCount: string;
    avgSale: string;
    previousPeriod: string;
    prevPeriod: string;
    nextPeriod: string;
    currentPeriod: string;
    statusBreakdown: string;
    noLeadsThisPeriod: string;
    categorySummary: string;
    noCategoryData: string;
    category: string;
    customer: string;
    periodSales: string;
    business: string;
    city: string;
    amount: string;
    date: string;
  };
  session: {
    idleLogout: string;
  };
  confirm: {
    title: string;
    cancel: string;
    delete: string;
    deleteLead: string;
    deleteEmployee: string;
    deleteCategory: string;
    deleteTag: string;
    deleteAccount: string;
    deleteImportBatch: string;
  };
  common: {
    loading: string;
    edit: string;
    add: string;
    addTask: string;
    days: string;
    daysNoResponse: string;
    last: string;
    noRecords: string;
    newLead: string;
    createRequest: string;
    search: string;
    allStatuses: string;
    allTags: string;
    allPriorities: string;
    allCities: string;
    actions: string;
    contact: string;
    process: string;
    business: string;
    tag: string;
    priority: string;
    status: string;
    page: string;
    previousPage: string;
    nextPage: string;
    importExcel: string;
    filters: string;
  };
  dashboard: {
    loading: string;
    loadFailed: string;
    retry: string;
    title: string;
    subtitle: string;
    totalLeads: string;
    activeFollowUp: string;
    todayTasks: string;
    awaitingReply: string;
    addedThisWeek: string;
    noReplyAlert: string;
    noReplyHint: string;
    empty: string;
    emptyNoLeads: string;
    addCategory: string;
    awaitingCustomers: string;
    todayTasksTitle: string;
    noTasksToday: string;
    upcomingFollowUps: string;
    noUpcomingFollowUps: string;
    recentMeetings: string;
    noRecentMeetings: string;
    recentCustomers: string;
    noRecentCustomers: string;
    automationTitle: string;
    noAutomationNotifications: string;
    dailySummaryTitle: string;
    dailyNewLeads: string;
    dailyNewCustomers: string;
    dailySales: string;
    dailyRevenue: string;
    dailyContacts: string;
    dailyContactsByCategory: string;
    dailyContactsEmpty: string;
    contactCount: string;
  };
  communication: {
    title: string;
    whatsapp: string;
    call: string;
    instagram: string;
    email: string;
    readyMessages: string;
    copy: string;
    copied: string;
    openWhatsApp: string;
    unavailable: string;
    templateIntro: string;
    templateFollowUp: string;
    templateDemo: string;
    templateMeeting: string;
    templateIntroBody: string;
    templateFollowUpBody: string;
    templateDemoBody: string;
    templateMeetingBody: string;
    emailSubject: string;
  };
  ai: {
    suggestButton: string;
    suggestLoading: string;
    suggestHint: string;
    suggestFailed: string;
    aiDraftLabel: string;
    templateDraftLabel: string;
    summarizeTitle: string;
    summarizeButton: string;
    summarizeLoading: string;
    summarizeShow: string;
    summarizeHide: string;
    summarizeFailed: string;
    prioritiesTitle: string;
    prioritiesHint: string;
    prioritiesLoading: string;
    prioritiesRefresh: string;
    prioritiesFailed: string;
    prioritiesEmpty: string;
    prioritiesOpenLead: string;
    scoreLabel: string;
    batchScoreTitle: string;
    batchScoreHint: string;
    batchScoreButton: string;
    batchScoreRunning: string;
    batchScoreDone: string;
    batchScoreFailed: string;
    agentTitle: string;
    agentPlaceholder: string;
    agentAsk: string;
    agentRunning: string;
    agentFailed: string;
    proposalsTitle: string;
    proposalsHint: string;
    proposalsEmpty: string;
    proposalsApprove: string;
    proposalsReject: string;
    proposalsQueue: string;
    proposalsQueued: string;
    proposalsActionAccept: string;
    de4ActionsTitle: string;
    de4ActionsHint: string;
    de4ActionsEmpty: string;
    de4ActionsStatusProposed: string;
    de4ActionsSourceDiagnosis: string;
    de4ActionsSuggestedAt: string;
    de4ActionsExecuteSoon: string;
    de4ActionsApprove: string;
    de4ActionsExecute: string;
    de4ActionsExecuting: string;
    de4ActionsExecuted: string;
    de4ActionsFailed: string;
    de4ActionsCancelled: string;
    de4ActionsExpired: string;
    de4ActionsStatusApproved: string;
    de4ActionsConfirmExecuteTitle: string;
    de4ActionsConfirmExecuteBody: string;
    de4ActionsConfirmCancel: string;
    de4ActionsConfirmOk: string;
    de4ActionsErrorGeneric: string;
    runHistoryTitle: string;
    runHistoryEmpty: string;
    runHistoryShow: string;
    runHistoryHide: string;
    runTypeBatch: string;
    runTypeAgent: string;
    runStatusDone: string;
    runStatusFailed: string;
    diagnosisInterpretButton: string;
    diagnosisInterpretLoading: string;
    diagnosisInterpretUnavailable: string;
    diagnosisInterpretNotFound: string;
    diagnosisInterpretQuota: string;
    diagnosisInterpretInvalidOutput: string;
    diagnosisInterpretGenericError: string;
    diagnosisInterpretCachedBadge: string;
    diagnosisInterpretSummary: string;
    diagnosisInterpretWhy: string;
    diagnosisInterpretFindings: string;
    diagnosisInterpretActions: string;
    diagnosisInterpretBridgeTitle: string;
    diagnosisInterpretBridgeHint: string;
    diagnosisInterpretBridgeLoading: string;
    diagnosisInterpretBridgeReason: string;
    de4ActionTypeLogActivity: string;
    de4ActionTypeNoteAppend: string;
    de4ActionTypeFollowUp: string;
    de4ActionTypeStatusChange: string;
    de4ActionTypePriorityChange: string;
    diagnosisInterpretConfidence: string;
    diagnosisInterpretHide: string;
    diagnosisInterpretDisabledTitle: string;
    diagnosisInterpretStatusLoading: string;
  };
  salesDiagnoses: {
    title: string;
    subtitle: string;
    loadFailed: string;
    empty: string;
    noLeadPriorityList: string;
    impactDistribution: string;
    impactHigh: string;
    impactMedium: string;
    impactLow: string;
    openLead: string;
    scoreLabel: string;
    daysSuffix: string;
    offerAgeSuffix: string;
    diagnosisModifierSuffix: string;
  };
  companyIntel: {
    title: string;
    subtitle: string;
    refresh: string;
    loadFailed: string;
    period: string;
    newLeads: string;
    newCustomers: string;
    conversion: string;
    awaitingReply: string;
    todayTasks: string;
    totalLeads: string;
    lostStalled: string;
    bestSource: string;
    updatedAt: string;
  };
  chat: {
    title: string;
    subtitle: string;
    open: string;
    close: string;
    placeholder: string;
    send: string;
    sendFailed: string;
    thinking: string;
    emptyHint: string;
    disclaimer: string;
  };
  leadImport: {
    title: string;
    subtitle: string;
    category: string;
    downloadTemplate: string;
    selectFile: string;
    import: string;
    importing: string;
    close: string;
    success: string;
    partial: string;
    failed: string;
    errorsTitle: string;
    row: string;
    fileHint: string;
    historyTitle: string;
    historyEmpty: string;
    historyFile: string;
    historyCreated: string;
    historyFailed: string;
    historyRemaining: string;
    deleteBatch: string;
    deleteBatchConfirm: string;
    deleteBatchSuccess: string;
  };
  leadDiscovery: {
    title: string;
    subtitle: string;
    city: string;
    cityHint: string;
    district: string;
    districtOptional: string;
    sectorKeyword: string;
    sectorPlaceholder: string;
    category: string;
    radius: string;
    scan: string;
    scanning: string;
    close: string;
    usageRemaining: string;
    usageWarning: string;
    usageLoadFailed: string;
    requiredFields: string;
    categoryRequired: string;
    scanFailed: string;
    quotaTitle: string;
    quotaConfirm: string;
    resultsTitle: string;
    alreadyAdded: string;
    lowDigital: string;
    noAddress: string;
    noPhone: string;
    rating: string;
    selectAll: string;
    deselectAll: string;
    noSelection: string;
    importSelected: string;
    importing: string;
    importSuccess: string;
    importFailed: string;
    discoverLeads: string;
  };
  stats: {
    total: string;
    active: string;
    demo: string;
    customer: string;
  };
  salesFunnel: {
    title: string;
    conversion: string;
  };
  statuses: Record<string, string>;
  priorities: Record<string, string>;
  requestsPage: {
    pending: string;
    approved: string;
    rejected: string;
    all: string;
    statusPending: string;
    statusApproved: string;
    statusRejected: string;
    loading: string;
    emptyOwner: string;
    emptyEmployee: string;
    business: string;
    category: string;
    priority: string;
    status: string;
    submittedAt: string;
    actions: string;
    review: string;
  };
  analyticsPage: {
    loading: string;
    noFunnelData: string;
    stageSuccessRates: string;
    records: string;
    fromPreviousStage: string;
    toNextStage: string;
    withinTotal: string;
    topCity: string;
    sales: string;
    noCityData: string;
    topCategory: string;
    noCategoryData: string;
    topHour: string;
    messages: string;
    noHourData: string;
    topDay: string;
    noDayData: string;
    responseRate: string;
    dailyContactTitle: string;
    dailyContactTotal: string;
    dailyContactHint: string;
    dailyContactEmpty: string;
    dailyContactPeople: string;
    pickDate: string;
  };
  revenue: {
    loading: string;
    notFound: string;
    totalRevenue: string;
    thisMonth: string;
    thisYear: string;
    avgSale: string;
    salesCount: string;
    monthlyRevenue: string;
    noSalesYet: string;
    categoryRevenue: string;
    noCategorySales: string;
    sales: string;
    recentSales: string;
    noRecentSales: string;
    business: string;
    category: string;
    city: string;
    amount: string;
    date: string;
  };
}

export const appCopy: Record<LandingLocale, AppCopy> = {
  tr: {
    sidebar: {
      dashboard: 'Dashboard',
      revenue: 'Gelir İstatistikleri',
      requests: 'Talepler',
      myRequests: 'Taleplerim',
      reports: 'Raporlama',
      leadDiscovery: 'Lead Keşfi',
      analytics: 'Analizler',
      intelligence: 'Intelligence',
      categories: 'Kategoriler',
      noCategoriesOwner: 'Kategori eklemek için alttaki butonu kullanın.',
      noCategoriesEmployee: 'Henüz kategori yok.',
      organization: 'Organizasyon',
      settings: 'Ayarlar',
      manageCategories: 'Kategoriler',
      manageTags: 'Etiketler',
      manageEmployees: 'Personeller',
      accountSettings: 'Hesap Ayarları',
      expandSection: 'Bölümü aç',
      collapseSection: 'Bölümü kapat',
      analyticsItems: {
        'satis-hunisi': 'Satış Hunisi',
        'analiz-donusum': 'Dönüşüm Oranları',
        'analiz-sehir': 'Şehir Analizi',
        'analiz-kategori': 'Kategori Analizi',
        'analiz-saat': 'Saat Analizi',
        'analiz-gun': 'Gün Analizi',
        'analiz-gunluk-iletisim': 'Günlük İletişim',
      },
      intelligenceItems: {
        'intel-overview': 'Özet',
        'intel-diagnoses': 'Teşhisler',
        'intel-actions': 'Aksiyonlar',
        'intel-assistant': 'Asistan',
      },
    },
    header: {
      logout: 'Çıkış',
      employee: 'Personel',
      individual: 'Bireysel',
      accountSettings: 'Hesap Ayarları',
      openMenu: 'Menüyü aç',
      closeMenu: 'Menüyü kapat',
    },
    accountSettings: {
      title: 'Hesap Ayarları',
      subtitle: 'Profil bilgilerinizi ve şifrenizi yönetin',
      profileSection: 'Profil',
      passwordSection: 'Şifre Değiştir',
      username: 'Kullanıcı Adı',
      email: 'E-posta',
      companyName: 'Şirket Adı',
      accountType: 'Hesap Türü',
      role: 'Rol',
      emailStatus: 'E-posta Durumu',
      verified: 'Doğrulandı',
      unverified: 'Doğrulanmadı',
      resendVerification: 'Doğrulama mailini tekrar gönder',
      resending: 'Gönderiliyor...',
      verificationSent: 'Doğrulama e-postası gönderildi.',
      currentPassword: 'Mevcut Şifre',
      newPassword: 'Yeni Şifre',
      confirmPassword: 'Yeni Şifre (Tekrar)',
      save: 'Kaydet',
      saving: 'Kaydediliyor...',
      saved: 'Ayarlar kaydedildi.',
      owner: 'Hesap Sahibi',
      employee: 'Personel',
      company: 'Şirket',
      individual: 'Bireysel',
      passwordHint: 'Şifre değiştirmek istemiyorsanız bu alanları boş bırakın.',
      emailChangeNote: 'E-posta değişirse yeni adrese doğrulama maili gönderilir.',
      deleteSection: 'Hesabı Sil',
      deleteWarningOwner:
        'Hesabınızı sildiğinizde tüm müşteri kayıtları, kategoriler, etiketler, personel hesapları ve diğer verileriniz kalıcı olarak silinir. Bu işlem geri alınamaz.',
      deleteWarningEmployee:
        'Hesabınızı sildiğinizde oturumunuz kapanır ve hesabınıza bağlı veriler kalıcı olarak silinir. Bu işlem geri alınamaz.',
      deletePassword: 'Şifreniz',
      confirmUsername: 'Kullanıcı adınızı yazın',
      confirmUsernameHint: 'Onaylamak için kullanıcı adınızı tam olarak yazın.',
      deleteAccount: 'Hesabımı Sil',
      deleting: 'Siliniyor...',
      deleteConfirmOwner:
        'Hesabınızı ve tüm organizasyon verilerinizi kalıcı olarak silmek istediğinize emin misiniz?',
      deleteConfirmEmployee: 'Hesabınızı kalıcı olarak silmek istediğinize emin misiniz?',
    },
    views: {
      dashboard: {
        title: 'Dashboard',
        description: 'Günlük satış sürecinizin özeti',
      },
      revenue: {
        title: 'Gelir İstatistikleri',
        description: 'Satışlardan elde ettiğiniz gelir özeti',
      },
      reports: {
        title: 'Raporlama',
        description: 'Haftalık ve aylık performans raporları · CSV, Excel ve PDF dışa aktarma',
      },
      requests: {
        title: 'Talepler',
        description: 'Personel taleplerini onaylayın veya reddedin',
      },
      myRequests: {
        title: 'Taleplerim',
        description: 'Gönderdiğiniz müşteri taleplerinin durumu',
      },
      selectCategory: 'Kategori seçin',
      customers: 'Müşteriler',
      categoryTracking: 'Müşteri takip ve pazar araştırması',
      categoryReadOnly: 'Müşteri durumlarını görüntüleyin ve talep oluşturun',
      analytics: {
        'satis-hunisi': {
          title: 'Satış Hunisi',
          description: 'Satış sürecindeki dönüşüm oranları',
        },
        'analiz-donusum': {
          title: 'Dönüşüm Oranları',
          description: 'Her satış aşamasındaki başarı yüzdesi',
        },
        'analiz-sehir': {
          title: 'Şehir Analizi',
          description: 'En başarılı şehirlerin performansı',
        },
        'analiz-kategori': {
          title: 'Kategori Analizi',
          description: 'Sektör bazlı performans analizi',
        },
        'analiz-saat': {
          title: 'Saat Analizi',
          description: 'En verimli mesaj saatleri',
        },
        'analiz-gun': {
          title: 'Gün Analizi',
          description: 'Haftanın en başarılı günleri',
        },
        'analiz-gunluk-iletisim': {
          title: 'Günlük İletişim Analizi',
          description: 'Seçilen günde kategori bazında iletişime geçilen kişi sayısı',
        },
      },
      intelligence: {
        'intel-overview': {
          title: 'Intelligence · Özet',
          description: 'Şirket KPI özeti ve bugün önce ara listesi',
        },
        'intel-diagnoses': {
          title: 'Intelligence · Teşhisler',
          description: 'Deterministik satış teşhisleri ve AI yorumu',
        },
        'intel-actions': {
          title: 'Intelligence · Aksiyonlar',
          description: 'DE-4 aksiyon önerileri ve onay kuyruğu',
        },
        'intel-assistant': {
          title: 'Intelligence · Asistan',
          description: 'Toplu skor güncelleme ve satış asistanı',
        },
      },
    },
    reports: {
      weekly: 'Haftalık Rapor',
      monthly: 'Aylık Rapor',
      weeklyDesc: 'Haftalık satış performansını, yeni kayıtları ve dönüşüm oranlarını özetler.',
      monthlyDesc: 'Aylık müşteri kazanımı, dönüşüm oranları ve kategori performansını gösterir.',
      loading: 'Rapor yükleniyor...',
      loadFailed: 'Rapor verisi alınamadı.',
      retry: 'Tekrar dene',
      exportFailed: 'Dışa aktarma başarısız',
      downloading: 'İndiriliyor...',
      creating: 'Oluşturuluyor...',
      csv: 'CSV',
      excel: 'Excel',
      pdf: 'PDF Rapor',
      newLeads: 'Yeni Kayıt',
      newCustomers: 'Yeni Müşteri',
      conversionRate: 'Dönüşüm Oranı',
      funnelEndRate: 'Huni sonuç oranı',
      periodRevenue: 'Dönem Geliri',
      salesCount: 'satış',
      avgSale: 'Ort.',
      previousPeriod: 'Önceki dönem',
      prevPeriod: 'Önceki dönem',
      nextPeriod: 'Sonraki dönem',
      currentPeriod: 'Bu dönem',
      statusBreakdown: 'Durum Dağılımı',
      noLeadsThisPeriod: 'Bu dönemde yeni kayıt yok.',
      categorySummary: 'Kategori Özeti',
      noCategoryData: 'Kategori verisi yok.',
      category: 'Kategori',
      customer: 'Müşteri',
      periodSales: 'Dönem Satışları',
      business: 'İşletme',
      city: 'Şehir',
      amount: 'Tutar',
      date: 'Tarih',
    },
    session: {
      idleLogout: '{minutes} dakika boyunca işlem yapılmadığı için oturumunuz kapatıldı.',
    },
    confirm: {
      title: 'Emin misiniz?',
      cancel: 'İptal',
      delete: 'Sil',
      deleteLead: '"{name}" kaydını silmek istediğinize emin misiniz? Bu işlem geri alınamaz.',
      deleteEmployee: '"{name}" personelini silmek istediğinize emin misiniz?',
      deleteCategory: '"{name}" kategorisini silmek istediğinize emin misiniz? İçindeki müşteri kayıtları da silinir.',
      deleteTag: '"{name}" etiketini silmek istediğinize emin misiniz?',
      deleteAccount: 'Hesabı Sil',
      deleteImportBatch: 'İçe Aktarmayı Sil',
    },
    common: {
      loading: 'Yükleniyor...',
      edit: 'Düzenle',
      add: 'Ekle',
      addTask: 'Görev Ekle',
      days: 'gün',
      daysNoResponse: 'gün cevap yok',
      last: 'Son',
      noRecords: 'Henüz kayıt yok.',
      newLead: 'Yeni',
      createRequest: 'Talep Oluştur',
      search: 'Ara...',
      allStatuses: 'Tüm Durumlar',
      allTags: 'Tüm Etiketler',
      allPriorities: 'Tüm Öncelikler',
      allCities: 'Tüm Şehirler',
      actions: 'İşlem',
      contact: 'İletişim',
      process: 'Süreç',
      business: 'İşletme',
      tag: 'Etiket',
      priority: 'Öncelik',
      status: 'Durum',
      page: 'Sayfa {page} / {total}',
      previousPage: 'Önceki',
      nextPage: 'Sonraki',
      importExcel: 'Excel',
      filters: 'Filtreler',
    },
    dashboard: {
      loading: 'Dashboard yükleniyor...',
      loadFailed: 'Dashboard verileri yüklenemedi.',
      retry: 'Tekrar Dene',
      title: 'Dashboard',
      subtitle: 'Günlük satış sürecinizin özeti',
      totalLeads: 'Toplam Kayıt',
      activeFollowUp: 'Aktif Takip',
      todayTasks: 'Bugünkü Görevler',
      awaitingReply: 'Cevap Bekleyen',
      addedThisWeek: 'Bu Hafta Eklenen',
      noReplyAlert: '{count} müşteri {days} gündür cevap vermiyor',
      noReplyHint: 'Bu müşterilere takip mesajı göndermeyi veya durumlarını güncellemeyi unutmayın.',
      empty: 'Henüz kayıt yok. Bir kategori oluşturup müşteri ekleyerek başlayın.',
      emptyNoLeads: 'Henüz müşteri kaydı yok. Görev ekleyerek veya kategorilerden müşteri ekleyerek başlayın.',
      addCategory: 'Kategori Ekle',
      awaitingCustomers: 'Cevap Bekleyen Müşteriler',
      todayTasksTitle: 'Bugünkü Görevler',
      noTasksToday: 'Bugün için planlanmış görev yok',
      upcomingFollowUps: 'Yaklaşan Takipler',
      noUpcomingFollowUps: 'Yaklaşan takip bulunmuyor',
      recentMeetings: 'Son Görüşmeler',
      noRecentMeetings: 'Henüz görüşme kaydı yok',
      recentCustomers: 'Son Müşteriler',
      noRecentCustomers: 'Henüz müşteri kaydı yok',
      automationTitle: 'Otomasyon Bildirimleri',
      noAutomationNotifications: 'Şu an otomasyon bildirimi yok',
      dailySummaryTitle: 'Bugünün Özeti',
      dailyNewLeads: 'Yeni kayıt',
      dailyNewCustomers: 'Yeni müşteri',
      dailySales: 'Satış',
      dailyRevenue: 'Gelir',
      dailyContacts: 'İletişim',
      dailyContactsByCategory: 'Kategori bazında bugünkü iletişim',
      dailyContactsEmpty: 'Bugün için kayıtlı iletişim yok. İlk mesaj tarihi veya aktivite ekleyin.',
      contactCount: 'kişi',
    },
    communication: {
      title: 'İletişim Yönetimi',
      whatsapp: 'WhatsApp',
      call: 'Ara',
      instagram: 'Instagram',
      email: 'E-posta',
      readyMessages: 'Hazır Mesajlar',
      copy: 'Kopyala',
      copied: 'Kopyalandı',
      openWhatsApp: 'WhatsApp',
      unavailable: 'Bu kanal için bilgi yok',
      templateIntro: 'İlk tanışma',
      templateFollowUp: 'Takip mesajı',
      templateDemo: 'Demo bildirimi',
      templateMeeting: 'Görüşme teklifi',
      templateIntroBody:
        'Merhaba {yetkili}, ben BehTech ekibinden. {isletme_adi} için dijital çözümlerimiz hakkında kısaca bilgi paylaşmak isterim. Uygun olduğunuz bir zamanda yazabilir misiniz?',
      templateFollowUpBody:
        'Merhaba {yetkili}, {isletme_adi} için daha önce ilettiğimiz mesaja istinaden kısa bir dönüş alabilir miyiz? Size uygun bir zamanı paylaşırsanız sevinirim.',
      templateDemoBody:
        'Merhaba {yetkili}, {isletme_adi} için hazırladığımız demo/linki paylaşıyorum. İnceledikten sonra geri bildiriminizi almak isteriz.',
      templateMeetingBody:
        'Merhaba {yetkili}, {isletme_adi} için kısa bir online görüşme planlayabilir miyiz? Size en uygun gün ve saati yazarsanız hemen ayarlayalım.',
      emailSubject: '{isletme_adi} — BehTech Sales Hub',
    },
    ai: {
      suggestButton: 'AI öner',
      suggestLoading: 'Öneriliyor…',
      suggestHint: 'Lead bağlamına göre mesaj taslağı (yapay zeka)',
      suggestFailed: 'Öneri alınamadı',
      aiDraftLabel: 'AI taslağı',
      templateDraftLabel: 'Hazır şablon',
      summarizeTitle: 'AI lead özeti',
      summarizeButton: 'Özet oluştur',
      summarizeLoading: 'Özetleniyor…',
      summarizeShow: 'Göster',
      summarizeHide: 'Gizle',
      summarizeFailed: 'Özet alınamadı',
      prioritiesTitle: 'Bugün önce ara (AI)',
      prioritiesHint:
        'Lead detayındaki “AI lead özeti”nden farklıdır. Liste gün içinde sabit kalır; yenilemek için butona basın.',
      prioritiesLoading: 'Liste hazırlanıyor…',
      prioritiesRefresh: 'Listeyi yenile',
      prioritiesFailed: 'Öncelik listesi alınamadı',
      prioritiesEmpty: 'Şu an öncelikli lead yok.',
      prioritiesOpenLead: 'Lead detayını aç',
      scoreLabel: 'Skor',
      batchScoreTitle: 'Toplu skor güncelleme',
      batchScoreHint:
        'Her lead için 0–100 takip skorunu yeniden hesaplar (son iletişim, durum, öncelik, yaklaşan görüşme…). Yapay zeka kullanmaz. “Bugün önce ara” listesi bu skora dayanır; gece 02:00’de sistem de otomatik günceller.',
      batchScoreButton: 'Skorları güncelle',
      batchScoreRunning: 'Güncelleniyor…',
      batchScoreDone: 'Tamamlandı: {count} lead skorlandı.',
      batchScoreFailed: 'Toplu güncelleme başarısız',
      agentTitle: 'Satış asistanı (sınırlı)',
      agentPlaceholder: 'Örn: Bu hafta hangi lead’lere öncelik vermeliyim?',
      agentAsk: 'Sor',
      agentRunning: 'Yanıt hazırlanıyor…',
      agentFailed: 'Asistan yanıt veremedi',
      proposalsTitle: 'Onay bekleyen AI aksiyonları',
      proposalsHint:
        'Onay: öneriyi kabul eder, lead için bugün/yarın takip veya görüşme planlar, aktiviteye yazar ve müşteri kartını açar. Red: sadece kuyruktan kaldırır.',
      proposalsEmpty: 'Bekleyen onay yok.',
      proposalsApprove: 'Onayla',
      proposalsReject: 'Reddet',
      proposalsQueue: 'Onaya gönder',
      proposalsQueued: 'Onay kuyruğuna eklendi',
      proposalsActionAccept: 'Öncelik planını uygula',
      de4ActionsTitle: 'AI aksiyon önerileri (DE-4)',
      de4ActionsHint: 'Onay sonrası yalnızca seçili aksiyonlar CRM\'e yazılır (v1: aktivite kaydı).',
      de4ActionsEmpty: 'Gösterilecek DE-4 aksiyonu yok.',
      de4ActionsStatusProposed: 'Önerildi',
      de4ActionsSourceDiagnosis: 'Kaynak teşhis',
      de4ActionsSuggestedAt: 'Önerildiği tarih',
      de4ActionsExecuteSoon: 'Bu tür henüz uygulanamaz',
      de4ActionsApprove: 'Onayla',
      de4ActionsExecute: 'Uygula',
      de4ActionsExecuting: 'Uygulanıyor…',
      de4ActionsExecuted: 'Uygulandı',
      de4ActionsFailed: 'Başarısız',
      de4ActionsCancelled: 'İptal',
      de4ActionsExpired: 'Süresi doldu',
      de4ActionsStatusApproved: 'Onaylandı',
      de4ActionsConfirmExecuteTitle: 'Aksiyonu uygula',
      de4ActionsConfirmExecuteBody:
        'Bu aksiyon lead kaydında onayladığınız değişikliği uygular. Devam etmek istediğinize emin misiniz?',
      de4ActionsConfirmCancel: 'Vazgeç',
      de4ActionsConfirmOk: 'Evet, uygula',
      de4ActionsErrorGeneric: 'İşlem tamamlanamadı. Lütfen tekrar deneyin.',
      runHistoryTitle: 'Son AI işleri',
      runHistoryEmpty: 'Henüz kayıtlı run yok.',
      runHistoryShow: 'Listeyi göster',
      runHistoryHide: 'Listeyi gizle',
      runTypeBatch: 'Toplu skor',
      runTypeAgent: 'Asistan',
      runStatusDone: 'Tamamlandı',
      runStatusFailed: 'Başarısız',
      diagnosisInterpretButton: 'AI Yorumu',
      diagnosisInterpretLoading: 'AI yorumu hazırlanıyor…',
      diagnosisInterpretUnavailable: 'AI yorumu şu anda kullanılamıyor.',
      diagnosisInterpretNotFound: 'Bu teşhis artık mevcut değil.',
      diagnosisInterpretQuota: 'AI kullanım kotası dolmuş.',
      diagnosisInterpretInvalidOutput:
        'AI yorumu oluşturulamadı. Teşhis verileri yine kullanılabilir.',
      diagnosisInterpretGenericError: 'AI yorumu oluşturulurken bir hata oluştu.',
      diagnosisInterpretCachedBadge: 'Önbellekten',
      diagnosisInterpretSummary: 'Özet',
      diagnosisInterpretWhy: 'Neden önemli?',
      diagnosisInterpretFindings: 'Öne çıkan bulgular',
      diagnosisInterpretActions: 'Önerilen aksiyonlar',
      diagnosisInterpretBridgeTitle: 'Önerilen aksiyon (DE-4)',
      diagnosisInterpretBridgeHint:
        'Onay sonrası «Uygula» ile CRM\'e yazılır. AI otomatik işlem yapmaz.',
      diagnosisInterpretBridgeLoading: 'Aksiyonlar yükleniyor…',
      diagnosisInterpretBridgeReason: 'Neden',
      de4ActionTypeLogActivity: 'Takip aktivitesi oluştur',
      de4ActionTypeNoteAppend: 'Lead notuna ekle',
      de4ActionTypeFollowUp: 'Takip görevi',
      de4ActionTypeStatusChange: 'Durum değişikliği',
      de4ActionTypePriorityChange: 'Öncelik değişikliği',
      diagnosisInterpretConfidence: 'Güven seviyesi',
      diagnosisInterpretHide: 'Yorumu gizle',
      diagnosisInterpretDisabledTitle: 'AI yorumu şu anda kullanılamıyor',
      diagnosisInterpretStatusLoading: 'AI durumu kontrol ediliyor…',
    },
    salesDiagnoses: {
      title: 'Satış teşhisleri',
      subtitle:
        'Deterministik kurallar (LLM yok). Öncelik: mevcut lead skoru + lead\'e özel teşhis.',
      loadFailed: 'Teşhisler yüklenemedi',
      empty: 'Şu an tetiklenen teşhis yok — veriler normal görünüyor.',
      noLeadPriorityList: 'Bu teşhis için lead bazlı öncelik listesi yok.',
      impactDistribution: 'Öncelik dağılımı:',
      impactHigh: 'yüksek',
      impactMedium: 'orta',
      impactLow: 'düşük',
      openLead: 'Aç',
      scoreLabel: 'Skor',
      daysSuffix: 'gün',
      offerAgeSuffix: 'teklif',
      diagnosisModifierSuffix: 'teşhis',
    },
    companyIntel: {
      title: 'Şirket özeti (Intelligence)',
      subtitle:
        'Bu ayki KPI’lar, takip yükü ve kaynak performansı — sohbet hafızası değil, raporlardan üretilir.',
      refresh: 'Yenile',
      loadFailed: 'Özet yüklenemedi',
      period: 'Dönem',
      newLeads: 'Yeni kayıt',
      newCustomers: 'Yeni müşteri',
      conversion: 'Satış dönüşüm',
      awaitingReply: 'Cevap bekleyen',
      todayTasks: 'Bugünkü görev',
      totalLeads: 'Toplam lead',
      lostStalled: 'Olumsuz / takılmış',
      bestSource:
        'En verimli kaynak (≥3 lead): {label} — %{rate} müşteri ({n} lead örneği)',
      updatedAt: 'Güncelleme',
    },
    chat: {
      title: 'Satış asistanı',
      subtitle: 'KPI ve lead özetine dayalı — salt okunur',
      open: 'Asistanı aç',
      close: 'Kapat',
      placeholder: 'Sorunuzu yazın… (Enter gönderir)',
      send: 'Gönder',
      sendFailed: 'Yanıt alınamadı',
      thinking: 'Düşünüyor…',
      emptyHint: 'Örn: “Bu hafta hangi lead’lere öncelik vermeliyim?” veya “Cevap bekleyenler ne durumda?”',
      disclaimer: 'AI yanıtı bilgilendirme amaçlıdır; kayıtları panelden doğrulayın.',
    },
    leadImport: {
      title: 'Excel ile Toplu Ekle',
      subtitle: 'Şablonu indirin, doldurun ve seçtiğiniz kategoriye aktarın.',
      category: 'Kategori',
      downloadTemplate: 'Excel Şablonunu İndir',
      selectFile: 'Excel Dosyası Seç',
      import: 'İçe Aktar',
      importing: 'Aktarılıyor...',
      close: 'Kapat',
      success: '{count} müşteri başarıyla eklendi.',
      partial: '{created} eklendi, {failed} satırda hata oluştu.',
      failed: 'Hiçbir kayıt eklenemedi. Hataları kontrol edin.',
      errorsTitle: 'Hatalı satırlar',
      row: 'Satır',
      fileHint: 'Yalnızca .xlsx · en fazla 500 satır',
      historyTitle: 'İçe aktarma geçmişi',
      historyEmpty: 'Henüz kayıtlı içe aktarma yok.',
      historyFile: 'Dosya',
      historyCreated: '{count} eklendi',
      historyFailed: '{count} hatalı satır',
      historyRemaining: '{count} müşteri kaldı',
      deleteBatch: 'Toplu sil',
      deleteBatchConfirm:
        'Bu içe aktarmadan eklenen {count} müşteri kalıcı olarak silinecek. Devam edilsin mi?',
      deleteBatchSuccess: '{count} müşteri silindi.',
    },
    leadDiscovery: {
      title: 'Lead Keşfi',
      subtitle: 'Google Places ile bölgedeki gerçek işletmeleri tarayın ve CRM\'e aktarın.',
      city: 'Şehir',
      cityHint: 'Tüm Türkiye — il veya ilçe adı Google ile konumlandırılır (ör. Sakarya, Adapazarı, Denizli)',
      district: 'İlçe',
      districtOptional: 'Opsiyonel',
      sectorKeyword: 'Sektör anahtar kelimesi',
      sectorPlaceholder: 'örn. berber, kuaför, dövme stüdyosu',
      category: 'CRM kategorisi',
      radius: 'Tarama yarıçapı (metre)',
      scan: 'Tara',
      scanning: 'Taranıyor...',
      close: 'Kapat',
      usageRemaining: '{remaining}/{quota} sorgu kaldı',
      usageWarning: 'Kota uyarısı',
      usageLoadFailed: 'Kota bilgisi yüklenemedi',
      requiredFields: 'Şehir ve sektör zorunludur',
      categoryRequired: 'Kategori seçin',
      scanFailed: 'Tarama başarısız',
      quotaTitle: 'Kota Onayı',
      quotaConfirm: 'Devam Et',
      resultsTitle: '{count} işletme bulundu',
      alreadyAdded: 'Zaten ekli',
      lowDigital: 'Düşük dijital varlık',
      noAddress: 'Adres yok',
      noPhone: 'Telefon yok',
      rating: 'Puan',
      selectAll: 'Tümünü seç',
      deselectAll: 'Seçimi kaldır',
      noSelection: 'Aktarılacak kayıt seçin',
      importSelected: 'Seçilenleri Aktar ({count})',
      importing: 'Aktarılıyor...',
      importSuccess: '{created} eklendi, {updated} güncellendi',
      importFailed: 'Aktarma başarısız',
      discoverLeads: 'Lead Keşfi',
    },
    stats: {
      total: 'Toplam',
      active: 'Aktif',
      demo: 'Demo',
      customer: 'Müşteri',
    },
    salesFunnel: {
      title: 'Satış Hunisi',
      conversion: 'dönüşüm',
    },
    statuses: {
      Yeni: 'Yeni',
      'İletişime Geçildi': 'İletişime Geçildi',
      'Takip Bekliyor': 'Takip Bekliyor',
      'Demo Gönderildi': 'Demo Gönderildi',
      'Görüşme Planlandı': 'Görüşme Planlandı',
      'Teklif Verildi': 'Teklif Verildi',
      Müşteri: 'Müşteri',
      Olumsuz: 'Olumsuz',
      'Cevap Yok': 'Cevap Yok',
    },
    priorities: {
      yuksek: 'Yüksek',
      orta: 'Orta',
      dusuk: 'Düşük',
    },
    requestsPage: {
      pending: 'Bekleyen',
      approved: 'Onaylanan',
      rejected: 'Reddedilen',
      all: 'Tümü',
      statusPending: 'Bekliyor',
      statusApproved: 'Onaylandı',
      statusRejected: 'Reddedildi',
      loading: 'Talepler yükleniyor...',
      emptyOwner: 'Bu filtrede talep yok.',
      emptyEmployee: 'Henüz talep göndermediniz.',
      business: 'İşletme',
      category: 'Kategori',
      priority: 'Öncelik',
      status: 'Durum',
      submittedAt: 'Gönderim',
      actions: 'İşlem',
      review: 'İncele',
    },
    analyticsPage: {
      loading: 'Analiz yükleniyor...',
      noFunnelData: 'Henüz yeterli veri yok. Müşteri ekledikçe satış hunisi oluşacak.',
      stageSuccessRates: 'Aşama Başarı Oranları',
      records: 'kayıt',
      fromPreviousStage: 'Önceki aşamadan',
      toNextStage: 'Sonraki aşamaya',
      withinTotal: 'Toplam içinde',
      topCity: 'En başarılı şehir',
      sales: 'satış',
      noCityData: 'Şehir verisi bulunamadı. Müşteri kayıtlarına şehir ekleyin.',
      topCategory: 'En başarılı kategori',
      noCategoryData: 'Kategori verisi bulunamadı.',
      topHour: 'En verimli saat',
      messages: 'mesaj',
      noHourData: 'Saat verisi bulunamadı.',
      topDay: 'En verimli gün',
      noDayData: 'Gün verisi bulunamadı.',
      responseRate: 'cevap oranı',
      dailyContactTitle: 'Günlük iletişim',
      dailyContactTotal: 'Toplam iletişim',
      dailyContactHint: 'İlk mesaj tarihi veya mesaj / telefon / demo aktivitesi olan kayıtlar sayılır.',
      dailyContactEmpty: 'Bu tarihte iletişim kaydı yok.',
      dailyContactPeople: 'kişi',
      pickDate: 'Tarih',
    },
    revenue: {
      loading: 'Gelir verileri yükleniyor...',
      notFound: 'Gelir verisi bulunamadı.',
      totalRevenue: 'Toplam Gelir',
      thisMonth: 'Bu Ay',
      thisYear: 'Bu Yıl',
      avgSale: 'Ortalama Satış',
      salesCount: 'Satış Sayısı',
      monthlyRevenue: 'Aylık Gelir (Son 12 Ay)',
      noSalesYet: 'Henüz kayıtlı satış geliri yok.',
      categoryRevenue: 'Kategori Bazlı Gelir',
      noCategorySales: 'Kategori bazlı satış verisi yok.',
      sales: 'satış',
      recentSales: 'Son Satışlar',
      noRecentSales: 'Henüz satış kaydı yok.',
      business: 'İşletme',
      category: 'Kategori',
      city: 'Şehir',
      amount: 'Tutar',
      date: 'Tarih',
    },
  },
  en: {
    sidebar: {
      dashboard: 'Dashboard',
      revenue: 'Revenue Insights',
      requests: 'Requests',
      myRequests: 'My Requests',
      reports: 'Reports',
      leadDiscovery: 'Lead Discovery',
      analytics: 'Analytics',
      intelligence: 'Intelligence',
      categories: 'Categories',
      noCategoriesOwner: 'Use the button below to add categories.',
      noCategoriesEmployee: 'No categories yet.',
      organization: 'Organization',
      settings: 'Settings',
      manageCategories: 'Categories',
      manageTags: 'Tags',
      manageEmployees: 'Staff',
      accountSettings: 'Account Settings',
      expandSection: 'Expand section',
      collapseSection: 'Collapse section',
      analyticsItems: {
        'satis-hunisi': 'Sales Funnel',
        'analiz-donusum': 'Conversion Rates',
        'analiz-sehir': 'City Analysis',
        'analiz-kategori': 'Category Analysis',
        'analiz-saat': 'Hour Analysis',
        'analiz-gun': 'Day Analysis',
        'analiz-gunluk-iletisim': 'Daily Contact',
      },
      intelligenceItems: {
        'intel-overview': 'Overview',
        'intel-diagnoses': 'Diagnoses',
        'intel-actions': 'Actions',
        'intel-assistant': 'Assistant',
      },
    },
    header: {
      logout: 'Sign Out',
      employee: 'Staff',
      individual: 'Individual',
      accountSettings: 'Account Settings',
      openMenu: 'Open menu',
      closeMenu: 'Close menu',
    },
    accountSettings: {
      title: 'Account Settings',
      subtitle: 'Manage your profile and password',
      profileSection: 'Profile',
      passwordSection: 'Change Password',
      username: 'Username',
      email: 'Email',
      companyName: 'Company Name',
      accountType: 'Account Type',
      role: 'Role',
      emailStatus: 'Email Status',
      verified: 'Verified',
      unverified: 'Not verified',
      resendVerification: 'Resend verification email',
      resending: 'Sending...',
      verificationSent: 'Verification email sent.',
      currentPassword: 'Current Password',
      newPassword: 'New Password',
      confirmPassword: 'Confirm New Password',
      save: 'Save',
      saving: 'Saving...',
      saved: 'Settings saved.',
      owner: 'Account Owner',
      employee: 'Staff',
      company: 'Company',
      individual: 'Individual',
      passwordHint: 'Leave password fields empty if you do not want to change it.',
      emailChangeNote: 'If you change your email, a verification link will be sent to the new address.',
      deleteSection: 'Delete Account',
      deleteWarningOwner:
        'Deleting your account permanently removes all customer records, categories, tags, staff accounts, and other organization data. This cannot be undone.',
      deleteWarningEmployee:
        'Deleting your account permanently removes your profile and related data. This cannot be undone.',
      deletePassword: 'Your password',
      confirmUsername: 'Type your username',
      confirmUsernameHint: 'Enter your username exactly to confirm.',
      deleteAccount: 'Delete My Account',
      deleting: 'Deleting...',
      deleteConfirmOwner:
        'Are you sure you want to permanently delete your account and all organization data?',
      deleteConfirmEmployee: 'Are you sure you want to permanently delete your account?',
    },
    views: {
      dashboard: {
        title: 'Dashboard',
        description: 'Your daily sales pipeline at a glance',
      },
      revenue: {
        title: 'Revenue Insights',
        description: 'Summary of revenue from closed deals',
      },
      reports: {
        title: 'Reports',
        description: 'Weekly and monthly performance · CSV, Excel and PDF export',
      },
      requests: {
        title: 'Requests',
        description: 'Approve or reject staff lead requests',
      },
      myRequests: {
        title: 'My Requests',
        description: 'Status of lead requests you submitted',
      },
      selectCategory: 'Select a category',
      customers: 'Customers',
      categoryTracking: 'Customer tracking and market research',
      categoryReadOnly: 'View customer status and submit requests',
      analytics: {
        'satis-hunisi': {
          title: 'Sales Funnel',
          description: 'Conversion rates across your sales process',
        },
        'analiz-donusum': {
          title: 'Conversion Rates',
          description: 'Success percentage at each sales stage',
        },
        'analiz-sehir': {
          title: 'City Analysis',
          description: 'Top-performing cities',
        },
        'analiz-kategori': {
          title: 'Category Analysis',
          description: 'Performance by industry category',
        },
        'analiz-saat': {
          title: 'Hour Analysis',
          description: 'Most effective outreach hours',
        },
        'analiz-gun': {
          title: 'Day Analysis',
          description: 'Best days of the week for outreach',
        },
        'analiz-gunluk-iletisim': {
          title: 'Daily Contact Analysis',
          description: 'Contacts by category for the selected day',
        },
      },
      intelligence: {
        'intel-overview': {
          title: 'Intelligence · Overview',
          description: 'Company KPI summary and call-first-today list',
        },
        'intel-diagnoses': {
          title: 'Intelligence · Diagnoses',
          description: 'Deterministic sales diagnoses and AI commentary',
        },
        'intel-actions': {
          title: 'Intelligence · Actions',
          description: 'DE-4 action proposals and approval queue',
        },
        'intel-assistant': {
          title: 'Intelligence · Assistant',
          description: 'Batch score refresh and sales assistant',
        },
      },
    },
    reports: {
      weekly: 'Weekly Report',
      monthly: 'Monthly Report',
      weeklyDesc: 'Summarizes weekly sales performance, new leads, and conversion rates.',
      monthlyDesc: 'Shows monthly customer acquisition, conversion rates, and category performance.',
      loading: 'Loading report...',
      loadFailed: 'Could not load report data.',
      retry: 'Try again',
      exportFailed: 'Export failed',
      downloading: 'Downloading...',
      creating: 'Generating...',
      csv: 'CSV',
      excel: 'Excel',
      pdf: 'PDF Report',
      newLeads: 'New Leads',
      newCustomers: 'New Customers',
      conversionRate: 'Conversion Rate',
      funnelEndRate: 'Funnel close rate',
      periodRevenue: 'Period Revenue',
      salesCount: 'sales',
      avgSale: 'Avg.',
      previousPeriod: 'Previous period',
      prevPeriod: 'Previous period',
      nextPeriod: 'Next period',
      currentPeriod: 'Current period',
      statusBreakdown: 'Status Breakdown',
      noLeadsThisPeriod: 'No new leads in this period.',
      categorySummary: 'Category Summary',
      noCategoryData: 'No category data.',
      category: 'Category',
      customer: 'Customer',
      periodSales: 'Period Sales',
      business: 'Business',
      city: 'City',
      amount: 'Amount',
      date: 'Date',
    },
    session: {
      idleLogout: 'Your session was closed after {minutes} minutes of inactivity.',
    },
    confirm: {
      title: 'Are you sure?',
      cancel: 'Cancel',
      delete: 'Delete',
      deleteLead: 'Delete "{name}"? This action cannot be undone.',
      deleteEmployee: 'Delete staff member "{name}"?',
      deleteCategory: 'Delete category "{name}"? All customer records in this category will be removed.',
      deleteTag: 'Delete tag "{name}"?',
      deleteAccount: 'Delete Account',
      deleteImportBatch: 'Delete Import',
    },
    common: {
      loading: 'Loading...',
      edit: 'Edit',
      add: 'Add',
      addTask: 'Add Task',
      days: 'days',
      daysNoResponse: 'days no reply',
      last: 'Last',
      noRecords: 'No records yet.',
      newLead: 'New',
      createRequest: 'Create Request',
      search: 'Search...',
      allStatuses: 'All Statuses',
      allTags: 'All Tags',
      allPriorities: 'All Priorities',
      allCities: 'All Cities',
      actions: 'Actions',
      contact: 'Contact',
      process: 'Process',
      business: 'Business',
      tag: 'Tag',
      priority: 'Priority',
      status: 'Status',
      page: 'Page {page} / {total}',
      previousPage: 'Previous',
      nextPage: 'Next',
      importExcel: 'Excel',
      filters: 'Filters',
    },
    dashboard: {
      loading: 'Loading dashboard...',
      loadFailed: 'Could not load dashboard data.',
      retry: 'Retry',
      title: 'Dashboard',
      subtitle: 'Your daily sales pipeline at a glance',
      totalLeads: 'Total Leads',
      activeFollowUp: 'Active Follow-up',
      todayTasks: "Today's Tasks",
      awaitingReply: 'Awaiting Reply',
      addedThisWeek: 'Added This Week',
      noReplyAlert: '{count} customers with no reply for {days} days',
      noReplyHint: 'Remember to send follow-up messages or update their status.',
      empty: 'No records yet. Create a category and add customers to get started.',
      emptyNoLeads: 'No customer records yet. Add a task or add customers from your categories.',
      addCategory: 'Add Category',
      awaitingCustomers: 'Customers Awaiting Reply',
      todayTasksTitle: "Today's Tasks",
      noTasksToday: 'No tasks scheduled for today',
      upcomingFollowUps: 'Upcoming Follow-ups',
      noUpcomingFollowUps: 'No upcoming follow-ups',
      recentMeetings: 'Recent Meetings',
      noRecentMeetings: 'No meeting records yet',
      recentCustomers: 'Recent Customers',
      noRecentCustomers: 'No customer records yet',
      automationTitle: 'Automation Alerts',
      noAutomationNotifications: 'No automation alerts right now',
      dailySummaryTitle: "Today's Summary",
      dailyNewLeads: 'New leads',
      dailyNewCustomers: 'New customers',
      dailySales: 'Sales',
      dailyRevenue: 'Revenue',
      dailyContacts: 'Contacts',
      dailyContactsByCategory: 'Today’s contacts by category',
      dailyContactsEmpty: 'No contacts logged today. Add first message date or an activity.',
      contactCount: 'people',
    },
    communication: {
      title: 'Communication Hub',
      whatsapp: 'WhatsApp',
      call: 'Call',
      instagram: 'Instagram',
      email: 'Email',
      readyMessages: 'Quick Messages',
      copy: 'Copy',
      copied: 'Copied',
      openWhatsApp: 'WhatsApp',
      unavailable: 'No contact info for this channel',
      templateIntro: 'Introduction',
      templateFollowUp: 'Follow-up',
      templateDemo: 'Demo notice',
      templateMeeting: 'Meeting request',
      templateIntroBody:
        'Hi {yetkili}, I am from BehTech. I would like to share how we can help {isletme_adi}. Could you let me know a good time to connect?',
      templateFollowUpBody:
        'Hi {yetkili}, following up on our previous message about {isletme_adi}. Could you share a convenient time for a quick reply?',
      templateDemoBody:
        'Hi {yetkili}, sharing the demo/link we prepared for {isletme_adi}. We would love your feedback after you review it.',
      templateMeetingBody:
        'Hi {yetkili}, can we schedule a short online meeting for {isletme_adi}? Please share your preferred day and time.',
      emailSubject: '{isletme_adi} — BehTech Sales Hub',
    },
    ai: {
      suggestButton: 'AI suggest',
      suggestLoading: 'Suggesting…',
      suggestHint: 'Draft message from lead context (AI)',
      suggestFailed: 'Could not get suggestion',
      aiDraftLabel: 'AI draft',
      templateDraftLabel: 'Template',
      summarizeTitle: 'AI lead summary',
      summarizeButton: 'Generate summary',
      summarizeLoading: 'Summarizing…',
      summarizeShow: 'Show',
      summarizeHide: 'Hide',
      summarizeFailed: 'Could not load summary',
      prioritiesTitle: 'Call first today (AI)',
      prioritiesHint:
        'Not the same as “AI lead summary” on lead detail. List stays stable today; use refresh to recalculate.',
      prioritiesLoading: 'Loading list…',
      prioritiesRefresh: 'Refresh list',
      prioritiesFailed: 'Could not load priorities',
      prioritiesEmpty: 'No priority leads right now.',
      prioritiesOpenLead: 'Open lead detail',
      scoreLabel: 'Score',
      batchScoreTitle: 'Batch score refresh',
      batchScoreHint:
        'Recomputes each lead’s 0–100 follow-up score (last contact, status, priority, upcoming meetings…). No LLM. The “call first today” list uses these scores; the server also refreshes them nightly at 02:00.',
      batchScoreButton: 'Update scores',
      batchScoreRunning: 'Updating…',
      batchScoreDone: 'Done: {count} leads scored.',
      batchScoreFailed: 'Batch update failed',
      agentTitle: 'Sales assistant (limited)',
      agentPlaceholder: 'e.g. Which leads should I prioritize this week?',
      agentAsk: 'Ask',
      agentRunning: 'Generating answer…',
      agentFailed: 'Assistant could not respond',
      proposalsTitle: 'Pending AI actions',
      proposalsHint:
        'Approve: accepts the plan, schedules follow-up/meeting on the lead, logs activity, and opens the lead card. Reject: removes from queue only.',
      proposalsEmpty: 'No pending approvals.',
      proposalsApprove: 'Approve',
      proposalsReject: 'Reject',
      proposalsQueue: 'Send for approval',
      proposalsQueued: 'Added to approval queue',
      proposalsActionAccept: 'Apply priority plan',
      de4ActionsTitle: 'AI action proposals (DE-4)',
      de4ActionsHint: 'After approval, only selected actions write to CRM (v1: activity log).',
      de4ActionsEmpty: 'No DE-4 actions to show.',
      de4ActionsStatusProposed: 'Proposed',
      de4ActionsSourceDiagnosis: 'Source diagnosis',
      de4ActionsSuggestedAt: 'Suggested at',
      de4ActionsExecuteSoon: 'This type cannot be executed yet',
      de4ActionsApprove: 'Approve',
      de4ActionsExecute: 'Execute',
      de4ActionsExecuting: 'Executing…',
      de4ActionsExecuted: 'Executed',
      de4ActionsFailed: 'Failed',
      de4ActionsCancelled: 'Cancelled',
      de4ActionsExpired: 'Expired',
      de4ActionsStatusApproved: 'Approved',
      de4ActionsConfirmExecuteTitle: 'Execute action',
      de4ActionsConfirmExecuteBody:
        'This will apply the approved change on the lead record. Are you sure you want to continue?',
      de4ActionsConfirmCancel: 'Cancel',
      de4ActionsConfirmOk: 'Yes, execute',
      de4ActionsErrorGeneric: 'Could not complete the action. Please try again.',
      runHistoryTitle: 'Recent AI runs',
      runHistoryEmpty: 'No runs yet.',
      runHistoryShow: 'Show list',
      runHistoryHide: 'Hide list',
      runTypeBatch: 'Batch score',
      runTypeAgent: 'Assistant',
      runStatusDone: 'Done',
      runStatusFailed: 'Failed',
      diagnosisInterpretButton: 'AI insight',
      diagnosisInterpretLoading: 'Preparing AI insight…',
      diagnosisInterpretUnavailable: 'AI insight is not available right now.',
      diagnosisInterpretNotFound: 'This diagnosis is no longer available.',
      diagnosisInterpretQuota: 'AI usage quota exceeded.',
      diagnosisInterpretInvalidOutput:
        'Could not generate AI insight. Diagnosis data is still available.',
      diagnosisInterpretGenericError: 'Something went wrong while generating AI insight.',
      diagnosisInterpretCachedBadge: 'From cache',
      diagnosisInterpretSummary: 'Summary',
      diagnosisInterpretWhy: 'Why it matters',
      diagnosisInterpretFindings: 'Key findings',
      diagnosisInterpretActions: 'Recommended actions',
      diagnosisInterpretBridgeTitle: 'Suggested action (DE-4)',
      diagnosisInterpretBridgeHint:
        'After approval, use Execute to write to CRM. AI does not mutate CRM automatically.',
      diagnosisInterpretBridgeLoading: 'Loading actions…',
      diagnosisInterpretBridgeReason: 'Reason',
      de4ActionTypeLogActivity: 'Create follow-up activity',
      de4ActionTypeNoteAppend: 'Append lead note',
      de4ActionTypeFollowUp: 'Follow-up task',
      de4ActionTypeStatusChange: 'Status change',
      de4ActionTypePriorityChange: 'Priority change',
      diagnosisInterpretConfidence: 'Confidence',
      diagnosisInterpretHide: 'Hide insight',
      diagnosisInterpretDisabledTitle: 'AI insight is not available right now',
      diagnosisInterpretStatusLoading: 'Checking AI availability…',
    },
    salesDiagnoses: {
      title: 'Sales diagnoses',
      subtitle:
        'Deterministic rules (no LLM). Priority: existing lead score + diagnosis-specific signal.',
      loadFailed: 'Could not load diagnoses',
      empty: 'No active diagnoses — data looks normal.',
      noLeadPriorityList: 'No lead-level priority list for this diagnosis.',
      impactDistribution: 'Priority mix:',
      impactHigh: 'high',
      impactMedium: 'medium',
      impactLow: 'low',
      openLead: 'Open',
      scoreLabel: 'Score',
      daysSuffix: 'd',
      offerAgeSuffix: 'offer',
      diagnosisModifierSuffix: 'diagnosis',
    },
    companyIntel: {
      title: 'Company snapshot (Intelligence)',
      subtitle: 'Monthly KPIs, follow-up load, and source performance — from reports, not chat memory.',
      refresh: 'Refresh',
      loadFailed: 'Could not load snapshot',
      period: 'Period',
      newLeads: 'New leads',
      newCustomers: 'New customers',
      conversion: 'Sales conversion',
      awaitingReply: 'Awaiting reply',
      todayTasks: "Today's tasks",
      totalLeads: 'Total leads',
      lostStalled: 'Lost / stalled',
      bestSource: 'Best source (≥3 leads): {label} — {rate}% won ({n} sample)',
      updatedAt: 'Updated',
    },
    chat: {
      title: 'Sales assistant',
      subtitle: 'Based on KPI & lead snapshot — read-only',
      open: 'Open assistant',
      close: 'Close',
      placeholder: 'Type your question… (Enter to send)',
      send: 'Send',
      sendFailed: 'Could not get a reply',
      thinking: 'Thinking…',
      emptyHint: 'e.g. “Which leads should I prioritize this week?”',
      disclaimer: 'AI replies are informational; verify records in the app.',
    },
    leadImport: {
      title: 'Bulk Import from Excel',
      subtitle: 'Download the template, fill it in, and import into the selected category.',
      category: 'Category',
      downloadTemplate: 'Download Excel Template',
      selectFile: 'Choose Excel File',
      import: 'Import',
      importing: 'Importing...',
      close: 'Close',
      success: '{count} customers added successfully.',
      partial: '{created} added, {failed} rows had errors.',
      failed: 'No records were imported. Check the errors below.',
      errorsTitle: 'Failed rows',
      row: 'Row',
      fileHint: '.xlsx only · up to 500 rows',
      historyTitle: 'Import history',
      historyEmpty: 'No import batches yet.',
      historyFile: 'File',
      historyCreated: '{count} added',
      historyFailed: '{count} failed rows',
      historyRemaining: '{count} customers remaining',
      deleteBatch: 'Delete batch',
      deleteBatchConfirm:
        'This will permanently delete {count} customers from this import. Continue?',
      deleteBatchSuccess: '{count} customers deleted.',
    },
    leadDiscovery: {
      title: 'Lead Discovery',
      subtitle: 'Scan real businesses in a region via Google Places and import them into the CRM.',
      city: 'City',
      cityHint: 'All of Turkey — city or district is resolved via Google (e.g. Sakarya, Denizli)',
      district: 'District',
      districtOptional: 'Optional',
      sectorKeyword: 'Sector keyword',
      sectorPlaceholder: 'e.g. barber, hair salon, tattoo studio',
      category: 'CRM category',
      radius: 'Scan radius (meters)',
      scan: 'Scan',
      scanning: 'Scanning...',
      close: 'Close',
      usageRemaining: '{remaining}/{quota} queries left',
      usageWarning: 'Quota warning',
      usageLoadFailed: 'Could not load quota info',
      requiredFields: 'City and sector are required',
      categoryRequired: 'Select a category',
      scanFailed: 'Scan failed',
      quotaTitle: 'Quota Confirmation',
      quotaConfirm: 'Continue',
      resultsTitle: '{count} businesses found',
      alreadyAdded: 'Already added',
      lowDigital: 'Low digital presence',
      noAddress: 'No address',
      noPhone: 'No phone',
      rating: 'Rating',
      selectAll: 'Select all',
      deselectAll: 'Clear selection',
      noSelection: 'Select records to import',
      importSelected: 'Import Selected ({count})',
      importing: 'Importing...',
      importSuccess: '{created} added, {updated} updated',
      importFailed: 'Import failed',
      discoverLeads: 'Lead Discovery',
    },
    stats: {
      total: 'Total',
      active: 'Active',
      demo: 'Demo',
      customer: 'Customer',
    },
    salesFunnel: {
      title: 'Sales Funnel',
      conversion: 'conversion',
    },
    statuses: {
      Yeni: 'New',
      'İletişime Geçildi': 'Contacted',
      'Takip Bekliyor': 'Follow-up Pending',
      'Demo Gönderildi': 'Demo Sent',
      'Görüşme Planlandı': 'Meeting Scheduled',
      'Teklif Verildi': 'Quote Sent',
      Müşteri: 'Customer',
      Olumsuz: 'Negative',
      'Cevap Yok': 'No Response',
    },
    priorities: {
      yuksek: 'High',
      orta: 'Medium',
      dusuk: 'Low',
    },
    requestsPage: {
      pending: 'Pending',
      approved: 'Approved',
      rejected: 'Rejected',
      all: 'All',
      statusPending: 'Pending',
      statusApproved: 'Approved',
      statusRejected: 'Rejected',
      loading: 'Loading requests...',
      emptyOwner: 'No requests in this filter.',
      emptyEmployee: 'You have not submitted any requests yet.',
      business: 'Business',
      category: 'Category',
      priority: 'Priority',
      status: 'Status',
      submittedAt: 'Submitted',
      actions: 'Actions',
      review: 'Review',
    },
    analyticsPage: {
      loading: 'Loading analytics...',
      noFunnelData: 'Not enough data yet. The sales funnel will appear as you add customers.',
      stageSuccessRates: 'Stage Success Rates',
      records: 'records',
      fromPreviousStage: 'From previous stage',
      toNextStage: 'To next stage',
      withinTotal: 'Within total',
      topCity: 'Top city',
      sales: 'sales',
      noCityData: 'No city data found. Add cities to customer records.',
      topCategory: 'Top category',
      noCategoryData: 'No category data found.',
      topHour: 'Most effective hour',
      messages: 'messages',
      noHourData: 'No hour data found.',
      topDay: 'Most effective day',
      noDayData: 'No day data found.',
      responseRate: 'response rate',
      dailyContactTitle: 'Daily contacts',
      dailyContactTotal: 'Total contacts',
      dailyContactHint: 'Counts leads with first message date or message / call / demo activity on that day.',
      dailyContactEmpty: 'No contact records for this date.',
      dailyContactPeople: 'people',
      pickDate: 'Date',
    },
    revenue: {
      loading: 'Loading revenue data...',
      notFound: 'Revenue data not found.',
      totalRevenue: 'Total Revenue',
      thisMonth: 'This Month',
      thisYear: 'This Year',
      avgSale: 'Average Sale',
      salesCount: 'Sales Count',
      monthlyRevenue: 'Monthly Revenue (Last 12 Months)',
      noSalesYet: 'No recorded sales revenue yet.',
      categoryRevenue: 'Revenue by Category',
      noCategorySales: 'No category sales data.',
      sales: 'sales',
      recentSales: 'Recent Sales',
      noRecentSales: 'No sales records yet.',
      business: 'Business',
      category: 'Category',
      city: 'City',
      amount: 'Amount',
      date: 'Date',
    },
  },
};
