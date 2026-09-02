import { useCallback, useEffect, useRef, useState } from 'react';
import { LogOut, Menu, User } from 'lucide-react';
import { api, saveAuth } from './api';
import { clearAuth, getIdleTimeoutMinutes, getUsername, isAuthenticated, isRememberMe, setIdleTimeoutMinutes } from './auth';
import { useIdleTimeout } from './hooks/useIdleTimeout';
import { useConfirmDialog } from './hooks/useConfirmDialog';
import AnalyticsPage from './components/AnalyticsPage';
import LandingPage from './components/LandingPage';
import Login from './components/Login';
import ResetPassword from './components/ResetPassword';
import VerifyEmail from './components/VerifyEmail';
import CategoryManager from './components/CategoryManager';
import TagManager from './components/TagManager';
import Dashboard from './components/Dashboard';
import IntelligencePage from './components/IntelligencePage';
import LeadDetail from './components/LeadDetail';
import LeadForm from './components/LeadForm';
import LeadImportModal from './components/LeadImportModal';
import LeadDiscoveryModal from './components/LeadDiscoveryModal';
import AiChatWidget from './components/ai/AiChatWidget';
import LeadTable from './components/LeadTable';
import QuickTaskForm, {
  applyQuickTaskToExistingLead,
  quickTaskToLeadData,
  type QuickTaskData,
  type TaskType,
} from './components/QuickTaskForm';
import EmployeeManager from './components/EmployeeManager';
import AccountSettings from './components/AccountSettings';
import RequestForm from './components/RequestForm';
import RequestsPage from './components/RequestsPage';
import ReportsPage from './components/ReportsPage';
import {
  addDays,
  addMonths,
  currentMonthIso,
  isCurrentMonth,
  isCurrentWeek,
  todayIso,
} from './utils/reportPeriod';
import RevenuePage from './components/RevenuePage';
import PageTransition, { transitionVariant } from './components/PageTransition';
import LocaleToggle from './components/LocaleToggle';
import Sidebar from './components/Sidebar';
import StatsCards from './components/StatsCards';
import SeoHead from './components/SeoHead';
import { useLocale } from './i18n/locale';
import { getSeoMeta } from './seo/config';
import type {
  AccountType,
  AnalyticsData,
  AnalyticsView,
  Category,
  CategoryFormData,
  DashboardData,
  DeleteAccountData,
  Employee,
  EmployeeFormData,
  Lead,
  LeadFormData,
  LeadRequest,
  LeadRequestFormData,
  RevenueData,
  ReportData,
  ReportPeriod,
  IntelligenceView,
  Stats,
  Tag,
  TagFormData,
  UpdateProfileData,
  UserProfile,
  UserRole,
} from './types';
import { ANALYTICS_VIEWS, INTELLIGENCE_VIEWS } from './types';
import { getPublicRoute, navigateTo, type PublicRoute } from './utils/navigation';

function isAnalyticsView(view: string): view is AnalyticsView {
  return ANALYTICS_VIEWS.includes(view as AnalyticsView);
}

function isIntelligenceView(view: string): view is IntelligenceView {
  return INTELLIGENCE_VIEWS.includes(view as IntelligenceView);
}

function isCategoryView(view: string, categories: Category[]) {
  return categories.some((category) => category.id === view);
}

const PUBLIC_ROUTE_ORDER: Record<PublicRoute, number> = {
  landing: 0,
  login: 1,
  register: 2,
};

function App() {
  const { app, locale } = useLocale();
  const { confirm, dialog: confirmDialog } = useConfirmDialog();
  const path = window.location.pathname.replace(/\/$/, '') || '/';
  const urlToken = new URLSearchParams(window.location.search).get('token');
  const verifyToken = path === '/verify-email' ? urlToken : null;
  const resetToken = path === '/reset-password' ? urlToken : null;
  const [authenticated, setAuthenticated] = useState(isAuthenticated());
  const [authRestoring, setAuthRestoring] = useState(() => !isAuthenticated());
  const [username, setUsername] = useState(getUsername() || '');
  const [userEmail, setUserEmail] = useState('');
  const [userProfile, setUserProfile] = useState<UserProfile | null>(null);
  const [userRole, setUserRole] = useState<UserRole>('owner');
  const [accountType, setAccountType] = useState<AccountType>('company');
  const [categories, setCategories] = useState<Category[]>([]);
  const [tags, setTags] = useState<Tag[]>([]);
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [requests, setRequests] = useState<LeadRequest[]>([]);
  const [requestsLoading, setRequestsLoading] = useState(false);
  const [pendingRequestCount, setPendingRequestCount] = useState(0);
  const [activeView, setActiveView] = useState('dashboard');
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [dashboardLoading, setDashboardLoading] = useState(false);
  const [dashboardError, setDashboardError] = useState<string | null>(null);
  const [analytics, setAnalytics] = useState<AnalyticsData | null>(null);
  const [analyticsLoading, setAnalyticsLoading] = useState(false);
  const [revenue, setRevenue] = useState<RevenueData | null>(null);
  const [revenueLoading, setRevenueLoading] = useState(false);
  const [reportData, setReportData] = useState<ReportData | null>(null);
  const [reportLoading, setReportLoading] = useState(false);
  const [reportPeriod, setReportPeriod] = useState<ReportPeriod>('weekly');
  const [reportWeekDate, setReportWeekDate] = useState(() => todayIso());
  const [reportMonth, setReportMonth] = useState(() => currentMonthIso());
  const [leads, setLeads] = useState<Lead[]>([]);
  const [leadsPage, setLeadsPage] = useState(1);
  const [leadsTotalPages, setLeadsTotalPages] = useState(1);
  const [leadsTotal, setLeadsTotal] = useState(0);
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState('');
  const [durumFilter, setDurumFilter] = useState('');
  const [tagFilter, setTagFilter] = useState('');
  const [oncelikFilter, setOncelikFilter] = useState('');
  const [sehirFilter, setSehirFilter] = useState('');
  const [showForm, setShowForm] = useState(false);
  const [showRequestForm, setShowRequestForm] = useState(false);
  const [showQuickTask, setShowQuickTask] = useState(false);
  const [quickTaskDefaults, setQuickTaskDefaults] = useState<{ type?: TaskType; date?: string }>({});
  const [formCategory, setFormCategory] = useState('');
  const [showCategoryManager, setShowCategoryManager] = useState(false);
  const [showTagManager, setShowTagManager] = useState(false);
  const [showEmployeeManager, setShowEmployeeManager] = useState(false);
  const [showLeadImport, setShowLeadImport] = useState(false);
  const [showLeadDiscovery, setShowLeadDiscovery] = useState(false);
  const [showAccountSettings, setShowAccountSettings] = useState(false);
  const [editingLead, setEditingLead] = useState<Lead | null>(null);
  const [viewingLead, setViewingLead] = useState<Lead | null>(null);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [idleMessage, setIdleMessage] = useState('');
  const [publicRoute, setPublicRoute] = useState<PublicRoute>(() => getPublicRoute());
  const [publicTransition, setPublicTransition] = useState<'forward' | 'back'>('forward');
  const prevPublicRouteRef = useRef(publicRoute);
  const loadDataRequestRef = useRef(0);

  useEffect(() => {
    setMobileNavOpen(false);
  }, [activeView]);

  useEffect(() => {
    if (!mobileNavOpen) return;
    if (window.matchMedia('(min-width: 1024px)').matches) return;

    const scrollY = window.scrollY;
    const { style: bodyStyle } = document.body;
    const { style: htmlStyle } = document.documentElement;
    const prevBody = {
      overflow: bodyStyle.overflow,
      position: bodyStyle.position,
      top: bodyStyle.top,
      width: bodyStyle.width,
    };
    const prevHtmlOverflow = htmlStyle.overflow;

    bodyStyle.overflow = 'hidden';
    bodyStyle.position = 'fixed';
    bodyStyle.top = `-${scrollY}px`;
    bodyStyle.width = '100%';
    htmlStyle.overflow = 'hidden';

    return () => {
      bodyStyle.overflow = prevBody.overflow;
      bodyStyle.position = prevBody.position;
      bodyStyle.top = prevBody.top;
      bodyStyle.width = prevBody.width;
      htmlStyle.overflow = prevHtmlOverflow;
      window.scrollTo(0, scrollY);
    };
  }, [mobileNavOpen]);

  useEffect(() => {
    const syncRoute = () => setPublicRoute(getPublicRoute());
    window.addEventListener('popstate', syncRoute);
    return () => window.removeEventListener('popstate', syncRoute);
  }, []);

  useEffect(() => {
    const prev = prevPublicRouteRef.current;
    if (prev !== publicRoute) {
      setPublicTransition(
        PUBLIC_ROUTE_ORDER[publicRoute] >= PUBLIC_ROUTE_ORDER[prev] ? 'forward' : 'back',
      );
      prevPublicRouteRef.current = publicRoute;
    }
  }, [publicRoute]);

  const handleLogout = useCallback(async (reason?: string) => {
    try {
      await api.logout();
    } catch {
      /* ignore */
    }
    clearAuth();
    setAuthenticated(false);
    if (reason) setIdleMessage(reason);
    navigateTo('landing');
  }, []);

  useEffect(() => {
    if (authenticated) {
      setAuthRestoring(false);
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const res = await api.refreshSession();
        if (cancelled) return;
        saveAuth(res, true);
        setAuthenticated(true);
      } catch {
        /* no persistent session */
      } finally {
        if (!cancelled) setAuthRestoring(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [authenticated]);

  useIdleTimeout(
    () =>
      handleLogout(
        app.session.idleLogout.replace('{minutes}', String(getIdleTimeoutMinutes())),
      ),
    authenticated && !isRememberMe(),
  );

  useEffect(() => {
    if (!authenticated) return;
    api.getPublicConfig()
      .then((config) => setIdleTimeoutMinutes(config.idle_timeout_minutes))
      .catch(() => undefined);
  }, [authenticated]);

  const loadCategories = useCallback(async () => {
    const data = await api.getCategories();
    setCategories(data);
  }, []);

  const loadTags = useCallback(async () => {
    const data = await api.getTags();
    setTags(data);
  }, []);

  const loadDashboard = useCallback(async () => {
    setDashboardLoading(true);
    setDashboardError(null);
    try {
      setDashboard(await api.getDashboard());
    } catch (err) {
      setDashboardError(err instanceof Error ? err.message : 'Dashboard yüklenemedi');
      console.error(err);
    } finally {
      setDashboardLoading(false);
    }
  }, []);

  const loadAnalytics = useCallback(async () => {
    setAnalyticsLoading(true);
    try {
      setAnalytics(await api.getAnalytics());
    } catch (err) {
      console.error(err);
    } finally {
      setAnalyticsLoading(false);
    }
  }, []);

  const isOwner = userRole === 'owner';
  const isCompanyAccount = accountType === 'company';

  const loadRequests = useCallback(async () => {
    setRequestsLoading(true);
    try {
      setRequests(await api.getLeadRequests());
    } catch (err) {
      console.error(err);
    } finally {
      setRequestsLoading(false);
    }
  }, []);

  const loadPendingCount = useCallback(async () => {
    if (!isOwner || !isCompanyAccount) return;
    try {
      const result = await api.getPendingRequestCount();
      setPendingRequestCount(result.count);
    } catch (err) {
      console.error(err);
    }
  }, [isOwner, isCompanyAccount]);

  const loadEmployees = useCallback(async () => {
    if (!isOwner || !isCompanyAccount) return;
    try {
      setEmployees(await api.getEmployees());
    } catch (err) {
      console.error(err);
    }
  }, [isOwner, isCompanyAccount]);

  const loadRevenue = useCallback(async () => {
    setRevenueLoading(true);
    try {
      setRevenue(await api.getRevenue());
    } catch (err) {
      console.error(err);
    } finally {
      setRevenueLoading(false);
    }
  }, []);

  const loadReports = useCallback(
    async (
      period: ReportPeriod = reportPeriod,
      anchors?: { weekDate?: string; month?: string },
    ) => {
      setReportLoading(true);
      try {
        const weekDate = anchors?.weekDate ?? reportWeekDate;
        const month = anchors?.month ?? reportMonth;
        const data =
          period === 'monthly'
            ? await api.getMonthlyReport(month)
            : await api.getWeeklyReport(weekDate);
        setReportData(data);
      } catch (err) {
        console.error(err);
      } finally {
        setReportLoading(false);
      }
    },
    [reportPeriod, reportWeekDate, reportMonth],
  );

  const loadData = useCallback(async () => {
    if (
      activeView === 'dashboard'
      || activeView === 'gelir'
      || activeView === 'talepler'
      || activeView === 'raporlar'
      || isAnalyticsView(activeView)
      || isIntelligenceView(activeView)
      || !isCategoryView(activeView, categories)
    ) {
      return;
    }

    const requestId = ++loadDataRequestRef.current;
    const category = activeView;
    setLoading(true);
    try {
      const [leadsData, statsData] = await Promise.all([
        api.getLeads(
          category,
          search || undefined,
          durumFilter || undefined,
          tagFilter || undefined,
          oncelikFilter || undefined,
          sehirFilter || undefined,
          leadsPage,
        ),
        api.getStats(category),
      ]);
      if (requestId !== loadDataRequestRef.current) return;
      setLeads(leadsData.items);
      setLeadsTotal(leadsData.total);
      setLeadsTotalPages(leadsData.total_pages);
      setStats(statsData);
    } catch (err) {
      if (requestId === loadDataRequestRef.current) {
        console.error(err);
      }
    } finally {
      if (requestId === loadDataRequestRef.current) {
        setLoading(false);
      }
    }
  }, [activeView, search, durumFilter, tagFilter, oncelikFilter, sehirFilter, leadsPage, categories]);

  const refreshAfterLeadChange = useCallback(async () => {
    await loadCategories();
    await loadTags();
    if (isOwner) {
      await loadDashboard();
      if (isCompanyAccount) await loadPendingCount();
    }
    if (isAnalyticsView(activeView)) await loadAnalytics();
    if (activeView === 'gelir' && isOwner && isCompanyAccount) await loadRevenue();
    if (activeView === 'talepler' && isCompanyAccount) await loadRequests();
    if (activeView === 'raporlar' && isOwner) await loadReports();
    if (isCategoryView(activeView, categories)) await loadData();
  }, [
    activeView,
    categories,
    isOwner,
    isCompanyAccount,
    loadCategories,
    loadTags,
    loadDashboard,
    loadAnalytics,
    loadRevenue,
    loadData,
    loadPendingCount,
    loadRequests,
    loadReports,
  ]);

  const syncProfile = useCallback((profile: UserProfile) => {
    setUsername(profile.username);
    setUserEmail(profile.email);
    setUserRole(profile.role);
    setAccountType(profile.account_type || 'company');
    setUserProfile(profile);
  }, []);

  useEffect(() => {
    if (!authenticated) return;
    api.getMe()
      .then((profile) => {
        syncProfile(profile);
        if (profile.role === 'employee') {
          setActiveView((current) => (current === 'dashboard' ? '' : current));
        }
      })
      .catch(() => handleLogout());
    loadCategories().catch(console.error);
    loadTags().catch(console.error);
    if (isOwner) {
      loadDashboard().catch(console.error);
      loadPendingCount().catch(console.error);
    }
  }, [authenticated, handleLogout, isOwner, loadCategories, loadTags, loadDashboard, loadPendingCount, syncProfile]);

  useEffect(() => {
    if (!authenticated || isCompanyAccount) return;
    if (activeView === 'gelir' || activeView === 'talepler') {
      setActiveView('dashboard');
    }
  }, [authenticated, isCompanyAccount, activeView]);

  useEffect(() => {
    if (!authenticated || userRole !== 'employee') return;
    if (categories.length === 0) return;
    if (activeView === 'talepler') return;
    if (!activeView || activeView === 'dashboard' || !isCategoryView(activeView, categories)) {
      setActiveView(categories[0].id);
    }
  }, [authenticated, userRole, categories, activeView]);

  useEffect(() => {
    setLeadsPage(1);
  }, [activeView]);

  useEffect(() => {
    if (!authenticated) return;
    if (activeView === 'dashboard' && isOwner) {
      loadDashboard().catch(console.error);
      return;
    }
    if (activeView === 'gelir' && isOwner && isCompanyAccount) {
      loadRevenue().catch(console.error);
      return;
    }
    if (activeView === 'talepler' && isCompanyAccount) {
      loadRequests().catch(console.error);
      return;
    }
    if (activeView === 'raporlar' && isOwner) {
      loadReports().catch(console.error);
      return;
    }
    if (isAnalyticsView(activeView) && isOwner) {
      loadAnalytics().catch(console.error);
      return;
    }
    if (isCategoryView(activeView, categories)) {
      const timer = setTimeout(loadData, search ? 300 : 0);
      return () => clearTimeout(timer);
    }
  }, [
    authenticated,
    activeView,
    categories,
    isOwner,
    isCompanyAccount,
    loadData,
    loadDashboard,
    loadRevenue,
    loadAnalytics,
    loadRequests,
    loadReports,
    search,
  ]);

  const handleLogin = async () => {
    setIdleMessage('');
    setAuthenticated(true);
    setUsername(getUsername() || '');
    window.history.replaceState({}, '', '/');
    try {
      const profile = await api.getMe();
      syncProfile(profile);
      setActiveView(profile.role === 'employee' ? '' : 'dashboard');
    } catch {
      setUserRole('owner');
      setAccountType('company');
      setActiveView('dashboard');
    }
  };

  const handleSaveProfile = async (data: UpdateProfileData) => {
    const updated = await api.updateProfile(data);
    syncProfile(updated);
    return updated;
  };

  const handleResendVerification = async () => {
    if (!userEmail) return;
    await api.resendVerification(userEmail);
  };

  const handleDeleteAccount = async (data: DeleteAccountData) => {
    await api.deleteAccount(data);
    setShowAccountSettings(false);
    handleLogout();
  };

  const handleSaveLead = async (data: LeadFormData) => {
    if (editingLead) {
      await api.updateLead(editingLead.id, data);
    } else {
      const category = formCategory || (activeView !== 'dashboard' && activeView !== 'gelir' && !isAnalyticsView(activeView) && !isIntelligenceView(activeView) ? activeView : '');
      await api.createLead(category, data);
    }
    await refreshAfterLeadChange();
  };

  const handleSaveRequest = async (data: LeadRequestFormData) => {
    await api.createLeadRequest(data);
    await loadRequests();
    if (isOwner) await loadPendingCount();
  };

  const handleApproveRequest = async (request: LeadRequest) => {
    await api.approveLeadRequest(request.id);
    await loadRequests();
    await loadPendingCount();
    await loadCategories();
    if (isCategoryView(request.category, categories)) await loadData();
  };

  const handleRejectRequest = async (request: LeadRequest, note: string) => {
    await api.rejectLeadRequest(request.id, note);
    await loadRequests();
    await loadPendingCount();
  };

  const handleSaveEmployee = async (data: EmployeeFormData) => {
    await api.createEmployee(data);
    await loadEmployees();
  };

  const handleUpdateEmployeeDisplayName = async (employee: Employee, displayName: string) => {
    await api.updateEmployee(employee.id, { display_name: displayName });
    await loadEmployees();
  };

  const handleDeleteEmployee = async (employee: Employee) => {
    const ok = await confirm({
      title: app.confirm.title,
      message: app.confirm.deleteEmployee.replace('{name}', employee.username),
      confirmLabel: app.confirm.delete,
      cancelLabel: app.confirm.cancel,
    });
    if (!ok) return;
    await api.deleteEmployee(employee.id);
    await loadEmployees();
  };

  const handleEditFromDashboard = async (leadId: number) => {
    try {
      const lead = await api.getLead(leadId);
      setViewingLead(lead);
    } catch (err) {
      console.error(err);
    }
  };

  const handleOpenEdit = (lead: Lead) => {
    setViewingLead(null);
    setEditingLead(lead);
    setFormCategory(lead.category);
    setShowForm(true);
  };

  const handleViewLead = async (lead: Lead) => {
    try {
      const fresh = await api.getLead(lead.id);
      setViewingLead(fresh);
    } catch {
      setViewingLead(lead);
    }
  };

  const handleAddLeadPayment = async (amount: number) => {
    if (!viewingLead) return;
    const updated = await api.addLeadPayment(viewingLead.id, amount);
    setViewingLead(updated);
    setLeads((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
    if (isOwner && isCompanyAccount) {
      loadRevenue().catch(console.error);
    }
  };

  const handleAddTask = (type?: TaskType, date?: string) => {
    setQuickTaskDefaults({ type, date });
    setShowQuickTask(true);
  };

  const handleSaveQuickTask = async (task: QuickTaskData) => {
    if (task.lead_id) {
      const existing = await api.getLead(task.lead_id);
      await api.updateLead(task.lead_id, applyQuickTaskToExistingLead(existing, task));
    } else {
      await api.createLead(task.category, quickTaskToLeadData(task));
    }
    await refreshAfterLeadChange();
  };

  const handleDeleteLead = async (lead: Lead) => {
    const ok = await confirm({
      title: app.confirm.title,
      message: app.confirm.deleteLead.replace('{name}', lead.isletme_adi),
      confirmLabel: app.confirm.delete,
      cancelLabel: app.confirm.cancel,
    });
    if (!ok) return;
    await api.deleteLead(lead.id);
    await refreshAfterLeadChange();
  };

  const handleSaveCategory = async (data: CategoryFormData, editingId?: string) => {
    if (editingId) {
      const updated = await api.updateCategory(editingId, data);
      if (activeView === editingId && updated.id !== editingId) {
        setActiveView(updated.id);
      }
    } else {
      const created = await api.createCategory(data);
      setActiveView(created.id);
    }
    await refreshAfterLeadChange();
  };

  const handleDeleteCategory = async (category: Category) => {
    await api.deleteCategory(category.id);
    if (activeView === category.id) setActiveView('dashboard');
    await loadCategories();
    await loadDashboard();
  };

  const handleSaveTag = async (data: TagFormData, editingId?: string) => {
    if (editingId) {
      await api.updateTag(editingId, data);
    } else {
      await api.createTag(data);
    }
    await loadTags();
    if (isCategoryView(activeView, categories)) await loadData();
  };

  const handleDeleteTag = async (tag: Tag) => {
    await api.deleteTag(tag.id);
    if (tagFilter === tag.id) setTagFilter('');
    await loadTags();
    if (isCategoryView(activeView, categories)) await loadData();
  };

  const goToCategory = (categoryId: string) => {
    if (activeView === categoryId) {
      loadData();
      return;
    }

    loadDataRequestRef.current += 1;
    setActiveView(categoryId);
    setSearch('');
    setDurumFilter('');
    setTagFilter('');
    setOncelikFilter('');
    setSehirFilter('');
    setLeadsPage(1);
    setLeads([]);
    setStats(null);
  };

  const goToReports = () => {
    setActiveView('raporlar');
    setSearch('');
    setDurumFilter('');
    setTagFilter('');
    setOncelikFilter('');
    setSehirFilter('');
  };

  const goToRevenue = () => {
    setActiveView('gelir');
    setSearch('');
    setDurumFilter('');
    setTagFilter('');
    setOncelikFilter('');
    setSehirFilter('');
  };

  const goToRequests = () => {
    setActiveView('talepler');
    setSearch('');
    setDurumFilter('');
    setTagFilter('');
    setOncelikFilter('');
    setSehirFilter('');
  };

  const goToAnalytics = (view: AnalyticsView) => {
    setActiveView(view);
    setSearch('');
    setDurumFilter('');
    setTagFilter('');
    setOncelikFilter('');
    setSehirFilter('');
  };

  const goToIntelligence = (view: IntelligenceView) => {
    setActiveView(view);
    setSearch('');
    setDurumFilter('');
    setTagFilter('');
    setOncelikFilter('');
    setSehirFilter('');
  };

  if (verifyToken) {
    return (
      <>
        <SeoHead meta={getSeoMeta('verify-email', locale)} locale={locale} />
        <VerifyEmail
        token={verifyToken}
        onSuccess={() => {
          window.history.replaceState({}, '', '/login');
          navigateTo('login');
        }}
        onBackToLogin={() => {
          window.history.replaceState({}, '', '/login');
          navigateTo('login');
        }}
        />
      </>
    );
  }

  if (resetToken) {
    return (
      <>
        <SeoHead meta={getSeoMeta('reset-password', locale)} locale={locale} />
        <ResetPassword
        token={resetToken}
        onSuccess={() => {
          window.history.replaceState({}, '', '/');
          handleLogout();
        }}
        />
      </>
    );
  }

  if (authRestoring) {
    return (
      <>
        <SeoHead meta={getSeoMeta('app', locale)} locale={locale} />
        <div className="flex min-h-dvh items-center justify-center bg-surface-50 text-sm text-surface-800/50">
          {app.dashboard.loading}
        </div>
      </>
    );
  }

  if (!authenticated) {
    const publicSeoRoute =
      publicRoute === 'register' ? 'register' : publicRoute === 'login' ? 'login' : 'landing';

    const publicContent =
      publicRoute === 'landing' ? (
        <LandingPage
          onLogin={() => navigateTo('login')}
          onRegister={() => navigateTo('register')}
        />
      ) : (
        <Login
          onLogin={handleLogin}
          initialView={publicRoute === 'register' ? 'register' : 'login'}
          onHome={() => navigateTo('landing')}
          onViewChange={(view) => {
            if (view === 'register') navigateTo('register');
            else if (view === 'login') navigateTo('login');
          }}
        />
      );

    return (
      <>
        <SeoHead
          meta={getSeoMeta(publicSeoRoute, locale)}
          locale={locale}
          includeStructuredData={publicSeoRoute === 'landing'}
        />
        {idleMessage && (
          <div className="fixed left-0 right-0 top-0 z-50 bg-amber-50 px-4 py-3 text-center text-sm text-amber-800">
            {idleMessage}
          </div>
        )}
        <PageTransition
          transitionKey={`public-${publicRoute}`}
          variant={transitionVariant(publicTransition, 'fade-up')}
          className="min-h-screen"
        >
          {publicContent}
        </PageTransition>
      </>
    );
  }

  const isDashboard = activeView === 'dashboard';
  const isRevenue = activeView === 'gelir';
  const isRequests = activeView === 'talepler';
  const isReports = activeView === 'raporlar';
  const analyticsView = isAnalyticsView(activeView) ? activeView : null;
  const intelligenceView = isIntelligenceView(activeView) ? activeView : null;
  const activeLabel = isDashboard
    ? app.views.dashboard.title
    : isRevenue
      ? app.views.revenue.title
      : isRequests
        ? isOwner ? app.views.requests.title : app.views.myRequests.title
        : isReports
          ? app.views.reports.title
          : intelligenceView
            ? app.views.intelligence[intelligenceView].title
            : analyticsView
          ? app.views.analytics[analyticsView].title
          : categories.find((c) => c.id === activeView)?.label || (isOwner ? app.views.selectCategory : app.views.customers);

  const activeDescription = isDashboard
    ? app.views.dashboard.description
    : isRevenue
      ? app.views.revenue.description
      : isRequests
        ? isOwner ? app.views.requests.description : app.views.myRequests.description
        : isReports
          ? app.views.reports.description
          : intelligenceView
            ? app.views.intelligence[intelligenceView].description
            : analyticsView
          ? app.views.analytics[analyticsView].description
          : isOwner
            ? app.views.categoryTracking
            : app.views.categoryReadOnly;

  return (
    <>
      <SeoHead meta={getSeoMeta('app', locale)} locale={locale} />
      <PageTransition transitionKey={`app-shell-${locale}`} variant="fade-up" className="flex h-full max-lg:h-dvh max-lg:max-h-dvh overflow-hidden">
      <Sidebar
        categories={categories}
        active={activeView}
        role={userRole}
        accountType={accountType}
        companyName={userProfile?.company_name}
        pendingRequestCount={pendingRequestCount}
        mobileOpen={mobileNavOpen}
        onMobileClose={() => setMobileNavOpen(false)}
        onSelectDashboard={() => {
          setActiveView('dashboard');
          setSearch('');
          setDurumFilter('');
          setTagFilter('');
          setOncelikFilter('');
          setSehirFilter('');
        }}
        onSelectRevenue={goToRevenue}
        onSelectReports={goToReports}
        onSelectLeadDiscovery={isOwner ? () => setShowLeadDiscovery(true) : undefined}
        onSelectRequests={goToRequests}
        onSelectAnalytics={goToAnalytics}
        onSelectIntelligence={goToIntelligence}
        onSelect={goToCategory}
        onManageCategories={() => setShowCategoryManager(true)}
        onManageTags={() => setShowTagManager(true)}
        onManageEmployees={() => {
          loadEmployees().catch(console.error);
          setShowEmployeeManager(true);
        }}
        onManageAccount={() => setShowAccountSettings(true)}
      />

      <div className="flex min-w-0 flex-1 flex-col overflow-hidden max-lg:overflow-x-hidden">
        <header className="flex shrink-0 items-center justify-between gap-2 border-b border-surface-200 bg-white px-3 py-2.5 sm:px-5 sm:py-3 max-lg:min-w-0">
          <div className="flex min-w-0 items-center gap-2">
            <button
              type="button"
              onClick={() => setMobileNavOpen(true)}
              className="rounded-lg p-2 text-surface-800/70 hover:bg-surface-100 lg:hidden"
              aria-label={app.header.openMenu}
            >
              <Menu size={20} />
            </button>
            <div className="min-w-0">
              <h1 className="truncate text-sm font-bold text-surface-900 lg:text-lg">{activeLabel}</h1>
              <p className="truncate text-[11px] text-surface-800/50 lg:text-xs lg:line-clamp-1">
                {activeDescription}
              </p>
            </div>
          </div>
          <div className="flex shrink-0 items-center gap-1.5 sm:gap-3">
            <LocaleToggle />
            <button
              type="button"
              onClick={() => setShowAccountSettings(true)}
              className="flex items-center gap-1.5 rounded-lg p-2 text-sm text-surface-800/60 transition hover:bg-surface-100 sm:px-2 sm:py-1"
              title={app.header.accountSettings}
            >
              <User size={14} />
              <span className="hidden max-w-[100px] truncate sm:inline md:max-w-none">{username}</span>
              {!isOwner && <span className="hidden text-xs text-surface-800/40 md:inline">· {app.header.employee}</span>}
              {isOwner && !isCompanyAccount && (
                <span className="hidden text-xs text-surface-800/40 md:inline">· {app.header.individual}</span>
              )}
            </button>
            <button onClick={() => handleLogout()} className="btn-secondary px-2.5 py-2 sm:px-4">
              <LogOut size={16} />
              <span className="hidden sm:inline">{app.header.logout}</span>
            </button>
          </div>
        </header>

        <main className="app-content min-h-0 flex-1 overflow-hidden p-3 sm:p-4 max-lg:p-2 max-lg:min-w-0 max-lg:overflow-x-hidden">
          <PageTransition transitionKey={activeView} variant="fade" className="h-full min-h-0 max-lg:overflow-hidden">
          {isDashboard ? (
            <div className="mobile-scroll-pane h-full lg:overflow-y-auto">
            <Dashboard
              data={dashboard}
              loading={dashboardLoading}
              error={dashboardError}
              onRetry={() => loadDashboard().catch(console.error)}
              hasCategories={categories.length > 0}
              onSelectCategory={goToCategory}
              onAddCategory={() => setShowCategoryManager(true)}
              onEditLead={handleEditFromDashboard}
              onAddTask={handleAddTask}
            />
            </div>
          ) : intelligenceView ? (
            intelligenceView === 'intel-assistant' ? (
              <div className="h-full min-h-0 overflow-hidden">
                <IntelligencePage
                  view={intelligenceView}
                  isOwner={isOwner}
                  onEditLead={handleEditFromDashboard}
                />
              </div>
            ) : (
              <div className="mobile-scroll-pane h-full lg:overflow-y-auto">
                <IntelligencePage
                  view={intelligenceView}
                  isOwner={isOwner}
                  onEditLead={handleEditFromDashboard}
                />
              </div>
            )
          ) : isRequests ? (
            <RequestsPage
              requests={requests}
              tags={tags}
              loading={requestsLoading}
              role={userRole}
              onApprove={isOwner ? handleApproveRequest : undefined}
              onReject={isOwner ? handleRejectRequest : undefined}
            />
          ) : isReports ? (
            <div className="mobile-scroll-pane h-full lg:overflow-y-auto">
            <ReportsPage
              accountType={accountType}
              loading={reportLoading}
              data={reportData}
              period={reportPeriod}
              canGoNext={
                reportPeriod === 'weekly'
                  ? !isCurrentWeek(reportWeekDate)
                  : !isCurrentMonth(reportMonth)
              }
              onPeriodChange={(period) => {
                setReportPeriod(period);
                loadReports(period).catch(console.error);
              }}
              onPrevPeriod={() => {
                if (reportPeriod === 'weekly') {
                  const weekDate = addDays(reportWeekDate, -7);
                  setReportWeekDate(weekDate);
                  loadReports('weekly', { weekDate }).catch(console.error);
                } else {
                  const month = addMonths(reportMonth, -1);
                  setReportMonth(month);
                  loadReports('monthly', { month }).catch(console.error);
                }
              }}
              onNextPeriod={() => {
                if (reportPeriod === 'weekly') {
                  if (isCurrentWeek(reportWeekDate)) return;
                  const weekDate = addDays(reportWeekDate, 7);
                  setReportWeekDate(weekDate);
                  loadReports('weekly', { weekDate }).catch(console.error);
                } else {
                  if (isCurrentMonth(reportMonth)) return;
                  const month = addMonths(reportMonth, 1);
                  setReportMonth(month);
                  loadReports('monthly', { month }).catch(console.error);
                }
              }}
              onCurrentPeriod={() => {
                if (reportPeriod === 'weekly') {
                  const weekDate = todayIso();
                  setReportWeekDate(weekDate);
                  loadReports('weekly', { weekDate }).catch(console.error);
                } else {
                  const month = currentMonthIso();
                  setReportMonth(month);
                  loadReports('monthly', { month }).catch(console.error);
                }
              }}
              onReload={() => loadReports().catch(console.error)}
            />
            </div>
          ) : isRevenue ? (
            <div className="mobile-scroll-pane h-full lg:overflow-y-auto">
              <RevenuePage data={revenue} loading={revenueLoading} />
            </div>
          ) : analyticsView ? (
            <div className="mobile-scroll-pane h-full lg:overflow-y-auto">
            <AnalyticsPage view={analyticsView} data={analytics} loading={analyticsLoading} />
            </div>
          ) : (
            <div className="flex h-full min-h-0 flex-col max-lg:gap-0 max-lg:min-w-0 max-lg:overflow-hidden">
              <StatsCards stats={stats} />
              <LeadTable
                leads={leads}
                tags={tags}
                loading={loading}
                search={search}
                durumFilter={durumFilter}
                tagFilter={tagFilter}
                oncelikFilter={oncelikFilter}
                sehirFilter={sehirFilter}
                cities={stats?.cities ?? []}
                page={leadsPage}
                totalPages={leadsTotalPages}
                total={leadsTotal}
                onSearchChange={setSearch}
                onDurumChange={setDurumFilter}
                onTagChange={setTagFilter}
                onOncelikChange={setOncelikFilter}
                onSehirChange={setSehirFilter}
                onPageChange={setLeadsPage}
                onAdd={() => {
                  if (isOwner) {
                    setEditingLead(null);
                    setFormCategory(activeView);
                    setShowForm(true);
                  } else {
                    setFormCategory(activeView);
                    setShowRequestForm(true);
                  }
                }}
                onImport={isOwner ? () => setShowLeadImport(true) : undefined}
                onDiscover={isOwner ? () => setShowLeadDiscovery(true) : undefined}
                onView={handleViewLead}
                onEdit={handleOpenEdit}
                onDelete={handleDeleteLead}
                readOnly={!isOwner}
                addButtonLabel={isOwner ? app.common.newLead : app.common.createRequest}
              />
            </div>
          )}
          </PageTransition>
        </main>
      </div>

      {viewingLead && (
        <LeadDetail
          lead={viewingLead}
          categoryLabel={categories.find((c) => c.id === viewingLead.category)?.label}
          userRole={userProfile?.role ?? 'owner'}
          senderDisplayName={userProfile?.display_name}
          senderUsername={userProfile?.username}
          onEdit={() => handleOpenEdit(viewingLead)}
          onClose={() => setViewingLead(null)}
          onAddPayment={isOwner ? handleAddLeadPayment : undefined}
          readOnly={!isOwner}
        />
      )}

      {showRequestForm && (
        <RequestForm
          categories={categories}
          tags={tags}
          defaultCategory={formCategory || (isCategoryView(activeView, categories) ? activeView : '')}
          onSave={handleSaveRequest}
          onClose={() => {
            setShowRequestForm(false);
            setFormCategory('');
          }}
        />
      )}

      {showForm && isOwner && (
        <LeadForm
          lead={editingLead}
          tags={tags}
          onSave={handleSaveLead}
          onClose={() => {
            setShowForm(false);
            setEditingLead(null);
            setFormCategory('');
          }}
        />
      )}

      {showQuickTask && (
        <QuickTaskForm
          categories={categories}
          defaultCategoryId={
            isCategoryView(activeView, categories) ? activeView : categories[0]?.id || ''
          }
          onSave={handleSaveQuickTask}
          onClose={() => {
            setShowQuickTask(false);
            setQuickTaskDefaults({});
          }}
          initialType={quickTaskDefaults.type}
          initialDate={quickTaskDefaults.date}
        />
      )}

      {showCategoryManager && (
        <CategoryManager
          categories={categories}
          onSave={handleSaveCategory}
          onDelete={handleDeleteCategory}
          onClose={() => setShowCategoryManager(false)}
        />
      )}

      {showTagManager && (
        <TagManager
          tags={tags}
          onSave={handleSaveTag}
          onDelete={handleDeleteTag}
          onClose={() => setShowTagManager(false)}
        />
      )}

      {showLeadImport && isOwner && (
        <LeadImportModal
          categories={categories}
          defaultCategoryId={isCategoryView(activeView, categories) ? activeView : categories[0]?.id || ''}
          onClose={() => setShowLeadImport(false)}
          onSuccess={() => {
            loadData().catch(console.error);
            loadDashboard().catch(console.error);
          }}
        />
      )}

      {showLeadDiscovery && isOwner && (
        <LeadDiscoveryModal
          categories={categories}
          defaultCategoryId={isCategoryView(activeView, categories) ? activeView : categories[0]?.id || ''}
          onClose={() => setShowLeadDiscovery(false)}
          onSuccess={() => {
            refreshAfterLeadChange().catch(console.error);
          }}
        />
      )}

      {showEmployeeManager && isCompanyAccount && (
        <EmployeeManager
          employees={employees}
          companyEmailDomains={userProfile?.company_email_domains ?? ['behtechlabs.com']}
          onSave={handleSaveEmployee}
          onUpdateDisplayName={handleUpdateEmployeeDisplayName}
          onDelete={handleDeleteEmployee}
          onClose={() => setShowEmployeeManager(false)}
        />
      )}

      {showAccountSettings && userProfile && (
        <AccountSettings
          profile={userProfile}
          onSave={handleSaveProfile}
          onResendVerification={handleResendVerification}
          onDeleteAccount={handleDeleteAccount}
          onClose={() => setShowAccountSettings(false)}
        />
      )}

      {confirmDialog}
      <AiChatWidget />
      </PageTransition>
    </>
  );
}

export default App;
