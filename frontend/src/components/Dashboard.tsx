import {
  AlertTriangle,
  BarChart3,
  Calendar,
  CalendarClock,
  CheckCircle,
  Bell,
  ClipboardList,
  Edit2,
  LayoutDashboard,
  LucideIcon,
  MessageSquareWarning,
  Plus,
  TrendingUp,
  Users,
} from 'lucide-react';
import { useState } from 'react';
import type { TaskType } from './QuickTaskForm';
import type { DashboardData, DashboardItem, DashboardTaskItem, ReminderItem, AutomationNotification } from '../types';
import { useLocale } from '../i18n/locale';
import StatusBadge from './StatusBadge';
import AiPriorityList from './ai/AiPriorityList';
import AiOpsPanel from './ai/AiOpsPanel';
import CompanyIntelligenceCard from './ai/CompanyIntelligenceCard';
import SalesDiagnosesCard from './ai/SalesDiagnosesCard';
import AiActionProposals from './ai/AiActionProposals';

interface Props {
  data: DashboardData | null;
  loading: boolean;
  error?: string | null;
  onRetry?: () => void;
  onSelectCategory: (categoryId: string) => void;
  onAddCategory: () => void;
  hasCategories?: boolean;
  onEditLead: (leadId: number) => void;
  onAddTask: (type?: TaskType, date?: string) => void;
  isOwner?: boolean;
  onDashboardRefresh?: () => void;
}

const typeColors: Record<string, string> = {
  gorusme: 'text-purple-600 bg-purple-50',
  demo: 'text-blue-600 bg-blue-50',
  takip: 'text-amber-600 bg-amber-50',
  'cevap-bekliyor': 'text-orange-600 bg-orange-50',
  'takip-1': 'text-amber-600 bg-amber-50',
  'takip-2': 'text-amber-600 bg-amber-50',
};

export default function Dashboard({
  data,
  loading,
  error,
  onRetry,
  onSelectCategory,
  onAddCategory,
  hasCategories = false,
  onEditLead,
  onAddTask,
  isOwner = false,
  onDashboardRefresh,
}: Props) {
  const { app } = useLocale();
  const d = app.dashboard;
  const c = app.common;
  const [proposalRefresh, setProposalRefresh] = useState(0);

  if (loading && !data) {
    return (
      <div className="flex items-center justify-center py-24 text-surface-800/50">
        {d.loading}
      </div>
    );
  }

  if (error && !data) {
    return (
      <div className="card flex flex-col items-center justify-center py-16 text-center">
        <p className="text-surface-800/70">{d.loadFailed}</p>
        <p className="mt-2 text-sm text-surface-800/50">{error}</p>
        {onRetry ? (
          <button onClick={onRetry} className="btn-primary mt-4">
            {d.retry}
          </button>
        ) : null}
      </div>
    );
  }

  if (!data) {
    return (
      <div className="flex items-center justify-center py-24 text-surface-800/50">
        {d.loading}
      </div>
    );
  }

  const today = new Date().toISOString().slice(0, 10);

  const safeData: DashboardData = {
    ...data,
    bugunku_gorevler_liste: data.bugunku_gorevler_liste ?? [],
    yaklasan_takipler: data.yaklasan_takipler ?? [],
    son_gorusmeler: data.son_gorusmeler ?? [],
    son_musteriler: data.son_musteriler ?? [],
    cevap_bekleyen_liste: data.cevap_bekleyen_liste ?? [],
    cevap_bekleyen_sayisi: data.cevap_bekleyen_sayisi ?? 0,
    cevap_bekleyen_gun: data.cevap_bekleyen_gun ?? 3,
    otomasyon_bildirimleri: data.otomasyon_bildirimleri ?? [],
    gunluk_ozet: data.gunluk_ozet ?? {
      date: today,
      yeni_kayit: 0,
      yeni_musteri: 0,
      satis_sayisi: 0,
      toplam_gelir: 0,
      donusum_orani: null,
      toplam_iletisim: 0,
      kategori_iletisim: [],
    },
  };

  const isEmpty = safeData.toplam_kayit === 0;
  const summaryCards = [
    { label: d.totalLeads, value: safeData.toplam_kayit, icon: Users, color: 'text-brand-500 bg-brand-50' },
    { label: d.activeFollowUp, value: safeData.aktif_takip, icon: BarChart3, color: 'text-amber-600 bg-amber-50' },
    { label: d.todayTasks, value: safeData.bugunku_gorevler, icon: ClipboardList, color: 'text-rose-600 bg-rose-50' },
    { label: d.awaitingReply, value: safeData.cevap_bekleyen_sayisi, icon: MessageSquareWarning, color: 'text-orange-600 bg-orange-50' },
    { label: d.addedThisWeek, value: safeData.bu_hafta_eklenen, icon: TrendingUp, color: 'text-emerald-600 bg-emerald-50' },
  ];

  return (
    <div className="min-w-0 space-y-6 max-lg:space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <div className="brand-icon-box h-9 w-9 shrink-0 lg:h-10 lg:w-10">
            <LayoutDashboard size={18} />
          </div>
          <div className="min-w-0">
            <h2 className="text-sm font-bold text-surface-900 lg:text-lg">{d.title}</h2>
            <p className="text-xs text-surface-800/50 lg:text-sm">{d.subtitle}</p>
          </div>
        </div>
        <button onClick={() => onAddTask('gorusme', today)} className="btn-primary w-full justify-center sm:w-auto">
          <Plus size={16} />
          {c.addTask}
        </button>
      </div>

      <div className="grid grid-cols-2 gap-2 lg:grid-cols-5 lg:gap-3">
        {summaryCards.map((card) => (
          <div key={card.label} className="card flex items-center gap-2.5 p-3 lg:gap-3 lg:p-4">
            <div className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg lg:h-10 lg:w-10 ${card.color}`}>
              <card.icon size={18} />
            </div>
            <div>
              <p className="text-[11px] text-surface-800/50 lg:text-xs">{card.label}</p>
              <p className="text-lg font-bold text-surface-900 lg:text-2xl">{card.value}</p>
            </div>
          </div>
        ))}
      </div>

      <CompanyIntelligenceCard isOwner={isOwner} />
      <SalesDiagnosesCard />

      <AiPriorityList
        isOwner={isOwner}
        onOpenLead={onEditLead}
        onProposalQueued={() => setProposalRefresh((n) => n + 1)}
      />

      <AiActionProposals
        isOwner={isOwner}
        onOpenLead={onEditLead}
        refreshToken={proposalRefresh}
        onApproved={onDashboardRefresh}
      />

      <AiOpsPanel isOwner={isOwner} />

      {safeData.cevap_bekleyen_sayisi > 0 && (
        <div className="flex items-start gap-2.5 rounded-xl border border-orange-200 bg-orange-50 px-3 py-3 lg:gap-3 lg:px-4 lg:py-4">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-orange-100 text-orange-600 lg:h-10 lg:w-10">
            <AlertTriangle size={18} />
          </div>
          <div>
            <p className="text-sm font-semibold text-orange-900 lg:text-base">
              {d.noReplyAlert
                .replace('{count}', String(safeData.cevap_bekleyen_sayisi))
                .replace('{days}', String(safeData.cevap_bekleyen_gun))}
            </p>
            <p className="mt-1 text-xs text-orange-800/80 lg:text-sm">{d.noReplyHint}</p>
          </div>
        </div>
      )}

      {isEmpty && (
        <div className="card flex flex-col items-center justify-center gap-3 px-4 py-6 text-center sm:flex-row sm:justify-between sm:text-left">
          <p className="text-sm text-surface-800/60">
            {hasCategories ? d.emptyNoLeads : d.empty}
          </p>
          {!hasCategories ? (
            <button onClick={onAddCategory} className="btn-primary shrink-0">
              <Plus size={16} />
              {d.addCategory}
            </button>
          ) : null}
        </div>
      )}

      <div className="card p-4">
        <div className="mb-3 flex items-center gap-2">
          <TrendingUp size={16} className="text-brand-500" />
          <h3 className="text-sm font-semibold text-surface-900">{d.dailySummaryTitle}</h3>
        </div>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <SummaryStat label={d.dailyNewLeads} value={safeData.gunluk_ozet!.yeni_kayit} />
          <SummaryStat label={d.dailyNewCustomers} value={safeData.gunluk_ozet!.yeni_musteri} />
          <SummaryStat
            label={d.dailyContacts}
            value={safeData.gunluk_ozet!.toplam_iletisim ?? 0}
          />
          {safeData.gunluk_ozet!.satis_sayisi != null ? (
            <SummaryStat label={d.dailySales} value={safeData.gunluk_ozet!.satis_sayisi} />
          ) : null}
          {safeData.gunluk_ozet!.toplam_gelir != null ? (
            <SummaryStat
              label={d.dailyRevenue}
              value={`${Math.round(safeData.gunluk_ozet!.toplam_gelir).toLocaleString('tr-TR')} ₺`}
            />
          ) : null}
        </div>
        {(safeData.gunluk_ozet!.kategori_iletisim?.length ?? 0) > 0 ? (
          <div className="mt-4 border-t border-surface-100 pt-4">
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-surface-800/45">
              {d.dailyContactsByCategory}
            </p>
            <ul className="space-y-2">
              {safeData.gunluk_ozet!.kategori_iletisim!.map((item) => (
                <li
                  key={item.category}
                  className="flex items-center justify-between rounded-lg bg-surface-50 px-3 py-2 text-sm"
                >
                  <span className="font-medium text-surface-900">{item.category_label}</span>
                  <span className="text-surface-800/70">
                    {item.iletisim_sayisi} {d.contactCount}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        ) : (
          <p className="mt-3 text-xs text-surface-800/45">{d.dailyContactsEmpty}</p>
        )}
      </div>

      <AutomationList
        title={d.automationTitle}
        items={safeData.otomasyon_bildirimleri}
        emptyText={d.noAutomationNotifications}
        onEdit={onEditLead}
        editTitle={c.edit}
      />

      <div className="grid gap-4 lg:grid-cols-2">
        {safeData.cevap_bekleyen_sayisi > 0 && (
          <div className="lg:col-span-2">
            <ReminderList
              title={d.awaitingCustomers}
              icon={MessageSquareWarning}
              items={safeData.cevap_bekleyen_liste}
              thresholdDays={safeData.cevap_bekleyen_gun}
              onSelect={onSelectCategory}
              onEdit={onEditLead}
              daysLabel={c.days}
              daysNoResponseLabel={c.daysNoResponse}
              lastLabel={c.last}
              editTitle={c.edit}
            />
          </div>
        )}
        <TaskList
          title={d.todayTasksTitle}
          icon={ClipboardList}
          items={safeData.bugunku_gorevler_liste}
          emptyText={d.noTasksToday}
          onSelect={onSelectCategory}
          onEdit={onEditLead}
          onAdd={() => onAddTask('gorusme', today)}
          addLabel={c.add}
          addTaskLabel={c.addTask}
          daysLabel={c.days}
          editTitle={c.edit}
        />
        <TaskList
          title={d.upcomingFollowUps}
          icon={CalendarClock}
          items={safeData.yaklasan_takipler}
          emptyText={d.noUpcomingFollowUps}
          showDays
          onSelect={onSelectCategory}
          onEdit={onEditLead}
          onAdd={() => onAddTask('gorusme')}
          addLabel={c.add}
          addTaskLabel={c.addTask}
          daysLabel={c.days}
          editTitle={c.edit}
        />
        <LeadList
          title={d.recentMeetings}
          icon={Calendar}
          items={safeData.son_gorusmeler}
          emptyText={d.noRecentMeetings}
          onSelect={onSelectCategory}
          onEdit={onEditLead}
          editTitle={c.edit}
        />
        <LeadList
          title={d.recentCustomers}
          icon={CheckCircle}
          items={safeData.son_musteriler}
          emptyText={d.noRecentCustomers}
          onSelect={onSelectCategory}
          onEdit={onEditLead}
          editTitle={c.edit}
        />
      </div>
    </div>
  );
}

function EditButton({ onClick, title }: { onClick: () => void; title: string }) {
  return (
    <button
      onClick={(e) => {
        e.stopPropagation();
        onClick();
      }}
      className="rounded-lg p-1.5 text-surface-800/40 transition hover:bg-brand-50 hover:text-brand-500"
      title={title}
    >
      <Edit2 size={14} />
    </button>
  );
}

function TaskList({
  title,
  icon: Icon,
  items,
  emptyText,
  showDays,
  onSelect,
  onEdit,
  onAdd,
  addLabel,
  addTaskLabel,
  daysLabel,
  editTitle,
}: {
  title: string;
  icon: LucideIcon;
  items: DashboardTaskItem[];
  emptyText: string;
  showDays?: boolean;
  onSelect: (categoryId: string) => void;
  onEdit: (leadId: number) => void;
  onAdd?: () => void;
  addLabel: string;
  addTaskLabel: string;
  daysLabel: string;
  editTitle: string;
}) {
  return (
    <div className="card overflow-hidden">
      <div className="flex items-center gap-2 border-b border-surface-200 px-3 py-2.5 lg:px-4 lg:py-3">
        <Icon size={16} className="text-brand-500" />
        <h3 className="text-xs font-semibold text-surface-900 lg:text-sm">{title}</h3>
        <span className="rounded-full bg-surface-100 px-2 py-0.5 text-xs text-surface-800/60">
          {items.length}
        </span>
        {onAdd && (
          <button
            onClick={onAdd}
            className="ml-auto flex items-center gap-1 rounded-lg px-2 py-1 text-xs font-medium text-brand-500 transition hover:bg-brand-50"
          >
            <Plus size={14} />
            {addLabel}
          </button>
        )}
      </div>
      <div className="divide-y divide-surface-100">
        {items.length === 0 ? (
          <div className="px-4 py-8 text-center">
            <p className="text-sm text-surface-800/40">{emptyText}</p>
            {onAdd && (
              <button onClick={onAdd} className="btn-secondary mx-auto mt-3 text-xs">
                <Plus size={14} />
                {addTaskLabel}
              </button>
            )}
          </div>
        ) : (
          items.map((item) => (
            <div
              key={`${item.id}-${item.type}-${item.date}`}
              className="flex items-start gap-2 px-3.5 py-2.5 transition hover:bg-surface-50 lg:px-4 lg:py-3"
            >
              <button
                onClick={() => onSelect(item.category)}
                className="flex min-w-0 flex-1 items-start gap-3 text-left"
              >
                <div className={`mt-0.5 shrink-0 rounded-md px-2 py-0.5 text-xs font-medium ${typeColors[item.type] || 'bg-surface-100'}`}>
                  {item.type_label}
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-semibold text-surface-900">{item.isletme_adi}</p>
                  <p className="text-xs text-surface-800/50">{item.category_label}</p>
                </div>
                <div className="shrink-0 text-right">
                  <p className="text-xs font-medium text-surface-800">{item.date}</p>
                  {showDays && item.days_until !== undefined && (
                    <p className="text-xs text-brand-500">{item.days_until} {daysLabel}</p>
                  )}
                  <StatusBadge durum={item.durum} size="xs" />
                </div>
              </button>
              <EditButton onClick={() => onEdit(item.id)} title={editTitle} />
            </div>
          ))
        )}
      </div>
    </div>
  );
}

function ReminderList({
  title,
  icon: Icon,
  items,
  thresholdDays,
  onSelect,
  onEdit,
  daysLabel,
  daysNoResponseLabel,
  lastLabel,
  editTitle,
}: {
  title: string;
  icon: LucideIcon;
  items: ReminderItem[];
  thresholdDays: number;
  onSelect: (categoryId: string) => void;
  onEdit: (leadId: number) => void;
  daysLabel: string;
  daysNoResponseLabel: string;
  lastLabel: string;
  editTitle: string;
}) {
  return (
    <div className="card overflow-hidden border-orange-200">
      <div className="flex items-center gap-2 border-b border-orange-100 bg-orange-50 px-3 py-2.5 lg:px-4 lg:py-3">
        <Icon size={16} className="text-orange-600" />
        <h3 className="text-xs font-semibold text-orange-900 lg:text-sm">{title}</h3>
        <span className="rounded-full bg-orange-100 px-2 py-0.5 text-xs font-medium text-orange-700">
          {items.length}
        </span>
        <span className="ml-auto text-xs text-orange-700/70">
          {thresholdDays}+ {daysNoResponseLabel}
        </span>
      </div>
      <div className="divide-y divide-surface-100">
        {items.map((item) => (
          <div
            key={`${item.id}-${item.last_contact_date}`}
            className="flex items-center gap-2 px-3.5 py-2.5 transition hover:bg-orange-50/40 lg:px-4 lg:py-3"
          >
            <button
              onClick={() => onSelect(item.category)}
              className="flex min-w-0 flex-1 items-center gap-3 text-left"
            >
              <div className="min-w-0 flex-1">
                <p className="truncate font-medium text-surface-900">{item.isletme_adi}</p>
                <p className="text-xs text-surface-800/50">
                  {item.category_label}{item.detail ? ` · ${item.detail}` : ''}
                </p>
              </div>
              <div className="shrink-0 text-right">
                <p className="text-sm font-semibold text-orange-600">{item.days_waiting} {daysLabel}</p>
                <p className="text-xs text-surface-800/50">{lastLabel}: {item.last_contact_date}</p>
                <StatusBadge durum={item.durum} size="xs" />
              </div>
            </button>
            <EditButton onClick={() => onEdit(item.id)} title={editTitle} />
          </div>
        ))}
      </div>
    </div>
  );
}

function LeadList({
  title,
  icon: Icon,
  items,
  emptyText,
  onSelect,
  onEdit,
  editTitle,
}: {
  title: string;
  icon: LucideIcon;
  items: DashboardItem[];
  emptyText: string;
  onSelect: (categoryId: string) => void;
  onEdit: (leadId: number) => void;
  editTitle: string;
}) {
  return (
    <div className="card overflow-hidden">
      <div className="flex items-center gap-2 border-b border-surface-200 px-3 py-2.5 lg:px-4 lg:py-3">
        <Icon size={16} className="text-brand-500" />
        <h3 className="text-xs font-semibold text-surface-900 lg:text-sm">{title}</h3>
        <span className="ml-auto rounded-full bg-surface-100 px-2 py-0.5 text-xs text-surface-800/60">
          {items.length}
        </span>
      </div>
      <div className="divide-y divide-surface-100">
        {items.length === 0 ? (
          <p className="px-4 py-8 text-center text-sm text-surface-800/40">{emptyText}</p>
        ) : (
          items.map((item) => (
            <div
              key={`${item.id}-${item.date}`}
              className="flex items-center gap-2 px-3.5 py-2.5 transition hover:bg-surface-50 lg:px-4 lg:py-3"
            >
              <button
                onClick={() => onSelect(item.category)}
                className="flex min-w-0 flex-1 items-center gap-3 text-left"
              >
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-semibold text-surface-900">{item.isletme_adi}</p>
                  <p className="text-xs text-surface-800/50">
                    {item.category_label}{item.detail ? ` · ${item.detail}` : ''}
                  </p>
                </div>
                <div className="shrink-0 text-right">
                  <p className="text-xs text-surface-800">{item.date}</p>
                  <StatusBadge durum={item.durum} size="xs" />
                </div>
              </button>
              <EditButton onClick={() => onEdit(item.id)} title={editTitle} />
            </div>
          ))
        )}
      </div>
    </div>
  );
}

function SummaryStat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-lg bg-surface-50 px-3 py-2">
      <p className="text-[11px] text-surface-800/50">{label}</p>
      <p className="text-base font-semibold text-surface-900 lg:text-lg">{value}</p>
    </div>
  );
}

function AutomationList({
  title,
  items,
  emptyText,
  onEdit,
  editTitle,
}: {
  title: string;
  items: AutomationNotification[];
  emptyText: string;
  onEdit: (leadId: number) => void;
  editTitle: string;
}) {
  return (
    <div className="card overflow-hidden border-brand-100">
      <div className="flex items-center gap-2 border-b border-surface-200 bg-brand-50/40 px-3 py-2.5 lg:px-4 lg:py-3">
        <Bell size={16} className="text-brand-500" />
        <h3 className="text-xs font-semibold text-surface-900 lg:text-sm">{title}</h3>
        <span className="rounded-full bg-white px-2 py-0.5 text-xs text-surface-800/60">{items.length}</span>
      </div>
      <div className="divide-y divide-surface-100">
        {items.length === 0 ? (
          <p className="px-4 py-8 text-center text-sm text-surface-800/40">{emptyText}</p>
        ) : (
          items.map((item) => (
            <div key={`${item.kind}-${item.id}-${item.message}`} className="flex items-start gap-2 px-3.5 py-2.5 lg:px-4 lg:py-3">
              <div className="min-w-0 flex-1">
                <p className="text-sm text-surface-900">{item.message}</p>
                <p className="mt-0.5 text-xs text-surface-800/50">{item.category_label}</p>
              </div>
              <EditButton onClick={() => onEdit(item.id)} title={editTitle} />
            </div>
          ))
        )}
      </div>
    </div>
  );
}
