import { useEffect, useState, type ReactNode } from 'react';
import {
  Sparkles,
  CalendarDays,
  ChevronDown,
  CircleDollarSign,
  ClipboardList,
  Clock,
  Compass,
  FileBarChart,
  Filter,
  LayoutDashboard,
  Layers,
  MapPin,
  MessageCircle,
  MessageSquareText,
  Percent,
  Settings,
  Stethoscope,
  Tag,
  User,
  Users,
  Zap,
  X,
} from 'lucide-react';
import BrandLogo from './BrandLogo';
import { useLocale } from '../i18n/locale';
import type { AnalyticsView, AccountType, Category, IntelligenceView, UserRole } from '../types';
import { CategoryIcon } from '../icons';

const ANALYTICS_ICONS: { id: AnalyticsView; icon: typeof Filter }[] = [
  { id: 'satis-hunisi', icon: Filter },
  { id: 'analiz-donusum', icon: Percent },
  { id: 'analiz-sehir', icon: MapPin },
  { id: 'analiz-kategori', icon: Layers },
  { id: 'analiz-saat', icon: Clock },
  { id: 'analiz-gun', icon: CalendarDays },
  { id: 'analiz-gunluk-iletisim', icon: MessageCircle },
];

const ANALYTICS_IDS = new Set(ANALYTICS_ICONS.map((item) => item.id));

const INTELLIGENCE_ICONS: { id: IntelligenceView; icon: typeof Sparkles }[] = [
  { id: 'intel-overview', icon: Sparkles },
  { id: 'intel-diagnoses', icon: Stethoscope },
  { id: 'intel-actions', icon: Zap },
  { id: 'intel-assistant', icon: MessageSquareText },
];

const INTELLIGENCE_IDS = new Set(INTELLIGENCE_ICONS.map((item) => item.id));
const STORAGE_PREFIX = 'crm-sidebar-section-';

function readSectionOpen(sectionId: string, defaultOpen: boolean) {
  const stored = localStorage.getItem(`${STORAGE_PREFIX}${sectionId}`);
  if (stored === '1') return true;
  if (stored === '0') return false;
  return defaultOpen;
}

function writeSectionOpen(sectionId: string, open: boolean) {
  localStorage.setItem(`${STORAGE_PREFIX}${sectionId}`, open ? '1' : '0');
}

function useSidebarSection(sectionId: string, defaultOpen: boolean, forceOpen: boolean) {
  const [open, setOpen] = useState(() => readSectionOpen(sectionId, defaultOpen));

  useEffect(() => {
    if (forceOpen) {
      setOpen(true);
      writeSectionOpen(sectionId, true);
    }
  }, [forceOpen, sectionId]);

  const toggle = () => {
    setOpen((prev) => {
      const next = !prev;
      writeSectionOpen(sectionId, next);
      return next;
    });
  };

  return [open, toggle] as const;
}

interface SidebarSectionProps {
  sectionId: string;
  title: string;
  children: ReactNode;
  defaultOpen?: boolean;
  forceOpen?: boolean;
  className?: string;
  expandLabel: string;
  collapseLabel: string;
}

function SidebarCollapsibleSection({
  sectionId,
  title,
  children,
  defaultOpen = true,
  forceOpen = false,
  className = '',
  expandLabel,
  collapseLabel,
}: SidebarSectionProps) {
  const [open, toggle] = useSidebarSection(sectionId, defaultOpen, forceOpen);
  const panelId = `sidebar-section-${sectionId}`;

  return (
    <div className={className}>
      <button
        type="button"
        onClick={toggle}
        aria-expanded={open}
        aria-controls={panelId}
        className="flex w-full items-center gap-1 rounded-lg px-2 py-2 text-left transition hover:bg-brand-50"
      >
        <span className="min-w-0 flex-1 truncate px-1 text-[10px] font-semibold uppercase tracking-wider text-surface-500">
          {title}
        </span>
        <ChevronDown
          size={14}
          className={`sidebar-section-chevron shrink-0 text-surface-400 ${open ? 'open' : ''}`}
          aria-hidden
        />
        <span className="sr-only">{open ? collapseLabel : expandLabel}</span>
      </button>

      <div className={`sidebar-collapse ${open ? 'open' : ''}`}>
        <div className="sidebar-collapse-inner">
          <div id={panelId} className="sidebar-collapse-content space-y-0.5 pb-0.5">
            {children}
          </div>
        </div>
      </div>
    </div>
  );
}

interface Props {
  categories: Category[];
  active: string;
  role: UserRole;
  accountType: AccountType;
  companyName?: string | null;
  pendingRequestCount?: number;
  mobileOpen?: boolean;
  onMobileClose?: () => void;
  onSelectDashboard: () => void;
  onSelectRevenue: () => void;
  onSelectReports: () => void;
  onSelectLeadDiscovery?: () => void;
  onSelectRequests: () => void;
  onSelectAnalytics: (view: AnalyticsView) => void;
  onSelectIntelligence: (view: IntelligenceView) => void;
  onSelect: (id: string) => void;
  onManageCategories: () => void;
  onManageTags: () => void;
  onManageEmployees: () => void;
  onManageAccount: () => void;
}

function SidebarPanel({
  categories,
  active,
  role,
  accountType,
  companyName,
  pendingRequestCount,
  onNavigate,
  onSelectDashboard,
  onSelectRevenue,
  onSelectReports,
  onSelectLeadDiscovery,
  onSelectRequests,
  onSelectAnalytics,
  onSelectIntelligence,
  onSelect,
  onManageCategories,
  onManageTags,
  onManageEmployees,
  onManageAccount,
  showClose,
  onClose,
}: Props & { onNavigate?: () => void; showClose?: boolean; onClose?: () => void }) {
  const { app } = useLocale();
  const isOwner = role === 'owner';
  const isCompanyAccount = accountType === 'company';
  const showCompanyFeatures = isOwner && isCompanyAccount;
  const isDashboard = active === 'dashboard';
  const isRevenue = active === 'gelir';
  const isReports = active === 'raporlar';
  const isRequests = active === 'talepler';
  const isAnalyticsActive = ANALYTICS_IDS.has(active as AnalyticsView);
  const isIntelligenceActive = INTELLIGENCE_IDS.has(active as IntelligenceView);
  const isCategoryActive = categories.some((cat) => cat.id === active);

  const go = (action: () => void) => () => {
    action();
    onNavigate?.();
  };

  const sectionLabels = {
    expand: app.sidebar.expandSection,
    collapse: app.sidebar.collapseSection,
  };

  return (
    <>
      <div className="flex shrink-0 items-center gap-2 border-b border-surface-200 px-3 py-3">
        <BrandLogo className="h-9 shrink-0" showTagline={false} />
        {companyName ? (
          <div className="min-w-0 flex-1 border-l border-surface-200 pl-2">
            <p className="truncate text-xs font-semibold leading-tight text-surface-900 lg:text-sm" title={companyName}>
              {companyName}
            </p>
          </div>
        ) : (
          <div className="flex-1" />
        )}
        {showClose && onClose ? (
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-2 text-surface-800/60 hover:bg-surface-100 lg:hidden"
            aria-label={app.header.closeMenu}
          >
            <X size={20} />
          </button>
        ) : null}
      </div>

      <nav className="min-h-0 flex-1 space-y-0.5 overflow-y-auto overscroll-contain p-2">
        {isOwner && (
          <>
            <button
              onClick={go(onSelectDashboard)}
              className={`flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2.5 text-left text-xs font-medium transition lg:text-sm ${
                isDashboard ? 'nav-active' : 'nav-inactive'
              }`}
            >
              <LayoutDashboard size={18} />
              {app.sidebar.dashboard}
            </button>

            <SidebarCollapsibleSection
              sectionId="intelligence"
              title={app.sidebar.intelligence}
              forceOpen={isIntelligenceActive}
              expandLabel={sectionLabels.expand}
              collapseLabel={sectionLabels.collapse}
              className="pt-1"
            >
              {INTELLIGENCE_ICONS.map((item) => {
                const isActive = active === item.id;
                const Icon = item.icon;
                const label = app.sidebar.intelligenceItems[item.id];

                return (
                  <button
                    key={item.id}
                    onClick={go(() => onSelectIntelligence(item.id))}
                    className={`flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2.5 text-left text-xs font-medium transition lg:text-sm ${
                      isActive ? 'nav-active' : 'nav-inactive'
                    }`}
                  >
                    <Icon size={18} />
                    <span className="truncate">{label}</span>
                  </button>
                );
              })}
            </SidebarCollapsibleSection>

            {showCompanyFeatures && (
              <>
                <button
                  onClick={go(onSelectRevenue)}
                  className={`flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2.5 text-left text-xs font-medium transition lg:text-sm ${
                    isRevenue ? 'nav-active' : 'nav-inactive'
                  }`}
                >
                  <CircleDollarSign size={18} />
                  {app.sidebar.revenue}
                </button>

                <button
                  onClick={go(onSelectRequests)}
                  className={`flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2.5 text-left text-xs font-medium transition lg:text-sm ${
                    isRequests ? 'nav-active' : 'nav-inactive'
                  }`}
                >
                  <ClipboardList size={18} />
                  <span className="truncate">{app.sidebar.requests}</span>
                  {(pendingRequestCount ?? 0) > 0 && (
                    <span className="ml-auto rounded-full bg-amber-500 px-1.5 py-0.5 text-[10px] font-bold text-white">
                      {pendingRequestCount}
                    </span>
                  )}
                </button>
              </>
            )}

            <button
              onClick={go(onSelectReports)}
              className={`flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2.5 text-left text-xs font-medium transition lg:text-sm ${
                isReports ? 'nav-active' : 'nav-inactive'
              }`}
            >
              <FileBarChart size={18} />
              {app.sidebar.reports}
            </button>

            {onSelectLeadDiscovery ? (
              <button
                onClick={go(onSelectLeadDiscovery)}
                className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2.5 text-left text-xs font-medium transition nav-inactive lg:text-sm"
              >
                <Compass size={18} />
                {app.sidebar.leadDiscovery}
              </button>
            ) : null}

            <SidebarCollapsibleSection
              sectionId="analytics"
              title={app.sidebar.analytics}
              forceOpen={isAnalyticsActive}
              expandLabel={sectionLabels.expand}
              collapseLabel={sectionLabels.collapse}
              className="pt-2"
            >
              {ANALYTICS_ICONS.map((item) => {
                const isActive = active === item.id;
                const Icon = item.icon;
                const label = app.sidebar.analyticsItems[item.id];

                return (
                  <button
                    key={item.id}
                    onClick={go(() => onSelectAnalytics(item.id))}
                    className={`flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2.5 text-left text-xs font-medium transition lg:text-sm ${
                      isActive ? 'nav-active' : 'nav-inactive'
                    }`}
                  >
                    <Icon size={18} />
                    <span className="truncate">{label}</span>
                  </button>
                );
              })}
            </SidebarCollapsibleSection>
          </>
        )}

        {!isOwner && (
          <button
            onClick={go(onSelectRequests)}
            className={`flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2.5 text-left text-xs font-medium transition lg:text-sm ${
              isRequests ? 'nav-active' : 'nav-inactive'
            }`}
          >
            <ClipboardList size={18} />
            {app.sidebar.myRequests}
          </button>
        )}

        <SidebarCollapsibleSection
          sectionId="categories"
          title={app.sidebar.categories}
          forceOpen={isCategoryActive}
          expandLabel={sectionLabels.expand}
          collapseLabel={sectionLabels.collapse}
          className="pt-2"
        >
          {categories.length === 0 ? (
            <p className="px-3 py-2 text-xs text-surface-500 lg:text-sm">
              {isOwner ? app.sidebar.noCategoriesOwner : app.sidebar.noCategoriesEmployee}
            </p>
          ) : (
            categories.map((cat) => {
              const isActive = active === cat.id;

              return (
                <button
                  key={cat.id}
                  onClick={go(() => onSelect(cat.id))}
                  className={`flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2.5 text-left text-xs font-medium transition lg:text-sm ${
                    isActive ? 'nav-active' : 'nav-inactive'
                  }`}
                >
                  <CategoryIcon
                    name={cat.icon}
                    size={18}
                    className={isActive ? 'text-white' : undefined}
                  />
                  <span className="truncate">{cat.label}</span>
                </button>
              );
            })
          )}
        </SidebarCollapsibleSection>
      </nav>

      {isOwner && (
        <div className="shrink-0 border-t border-surface-200 p-2">
          <SidebarCollapsibleSection
            sectionId="organization"
            title={showCompanyFeatures ? app.sidebar.organization : app.sidebar.settings}
            defaultOpen={false}
            expandLabel={sectionLabels.expand}
            collapseLabel={sectionLabels.collapse}
          >
            <div className="space-y-1.5">
              <button
                onClick={go(onManageCategories)}
                className="btn-secondary w-full justify-center py-2 text-xs"
              >
                <Settings size={14} />
                {app.sidebar.manageCategories}
              </button>
              <button onClick={go(onManageTags)} className="btn-secondary w-full justify-center py-2 text-xs">
                <Tag size={14} />
                {app.sidebar.manageTags}
              </button>
              {showCompanyFeatures && (
                <button
                  onClick={go(onManageEmployees)}
                  className="btn-secondary w-full justify-center py-2 text-xs"
                >
                  <Users size={14} />
                  {app.sidebar.manageEmployees}
                </button>
              )}
            </div>
          </SidebarCollapsibleSection>
        </div>
      )}

      <div className={`shrink-0 border-t border-surface-200 p-2 ${isOwner ? 'pt-0' : ''}`}>
        <button onClick={go(onManageAccount)} className="btn-secondary w-full justify-center py-2 text-xs">
          <User size={14} />
          {app.sidebar.accountSettings}
        </button>
      </div>
    </>
  );
}

export default function Sidebar(props: Props) {
  const { mobileOpen, onMobileClose, ...panelProps } = props;
  const { app } = useLocale();

  return (
    <>
      <aside className="hidden h-full w-56 shrink-0 flex-col border-r border-surface-200 bg-white lg:flex xl:w-60">
        <SidebarPanel {...panelProps} />
      </aside>

      {mobileOpen ? (
        <div className="fixed inset-0 z-50 overflow-hidden touch-none lg:hidden">
          <button
            type="button"
            className="absolute inset-0 bg-black/40"
            aria-label={app.header.closeMenu}
            onClick={onMobileClose}
          />
          <aside className="app-content relative flex h-full w-[min(100%,288px)] max-w-[85vw] flex-col overflow-hidden bg-white shadow-2xl">
            <SidebarPanel {...panelProps} showClose onClose={onMobileClose} onNavigate={onMobileClose} />
          </aside>
        </div>
      ) : null}
    </>
  );
}
