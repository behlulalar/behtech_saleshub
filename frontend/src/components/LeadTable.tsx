import { ChevronDown, ChevronUp, Compass, Edit2, FileSpreadsheet, Plus, Search, Trash2 } from 'lucide-react';
import { useState, type MouseEvent } from 'react';
import type { Lead, Tag } from '../types';
import { DURUM_STATUSES, ONCELIK_OPTIONS } from '../types';
import { useLocale } from '../i18n/locale';
import PriorityBadge from './PriorityBadge';
import StatusBadge from './StatusBadge';

interface Props {
  leads: Lead[];
  tags: Tag[];
  loading: boolean;
  search: string;
  durumFilter: string;
  tagFilter: string;
  oncelikFilter: string;
  sehirFilter: string;
  cities: string[];
  page: number;
  totalPages: number;
  total: number;
  onSearchChange: (v: string) => void;
  onDurumChange: (v: string) => void;
  onTagChange: (v: string) => void;
  onOncelikChange: (v: string) => void;
  onSehirChange: (v: string) => void;
  onPageChange: (page: number) => void;
  onAdd: () => void;
  onImport?: () => void;
  onDiscover?: () => void;
  onView: (lead: Lead) => void;
  onEdit: (lead: Lead) => void;
  onDelete: (lead: Lead) => void;
  readOnly?: boolean;
  addButtonLabel?: string;
}

function MinimalLeadCard({
  lead,
  readOnly,
  onView,
  onEdit,
  onDelete,
}: {
  lead: Lead;
  readOnly: boolean;
  onView: (lead: Lead) => void;
  onEdit: (lead: Lead) => void;
  onDelete: (lead: Lead) => void;
}) {
  const subtitle = [lead.sehir, lead.yetkili].filter(Boolean).join(' · ');

  return (
    <article
      role="button"
      tabIndex={0}
      onClick={() => onView(lead)}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onView(lead);
        }
      }}
      className="group flex cursor-pointer items-center gap-2 border-b border-surface-100 px-3 py-2.5 transition hover:bg-brand-50/40 active:bg-brand-50/60 sm:px-4"
    >
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-surface-900">{lead.isletme_adi}</p>
        {subtitle ? (
          <p className="mt-0.5 truncate text-xs text-surface-800/55">{subtitle}</p>
        ) : null}
      </div>
      <div className="flex shrink-0 items-center gap-1.5">
        <StatusBadge durum={lead.durum} size="xs" />
        <PriorityBadge oncelik={lead.oncelik || 'orta'} size="xs" />
      </div>
      {!readOnly ? (
        <div
          className="flex shrink-0 items-center gap-0.5 opacity-100 sm:opacity-0 sm:group-hover:opacity-100 sm:group-focus-within:opacity-100"
          onClick={(e: MouseEvent) => e.stopPropagation()}
          onKeyDown={(e) => e.stopPropagation()}
        >
          <button
            type="button"
            onClick={() => onEdit(lead)}
            className="rounded-md p-1.5 text-surface-800/50 hover:bg-brand-50 hover:text-brand-600"
            title="Düzenle"
            aria-label="Düzenle"
          >
            <Edit2 size={14} />
          </button>
          <button
            type="button"
            onClick={() => onDelete(lead)}
            className="rounded-md p-1.5 text-surface-800/50 hover:bg-red-50 hover:text-red-600"
            title="Sil"
            aria-label="Sil"
          >
            <Trash2 size={14} />
          </button>
        </div>
      ) : null}
    </article>
  );
}

export default function LeadTable({
  leads,
  tags,
  loading,
  search,
  durumFilter,
  tagFilter,
  oncelikFilter,
  sehirFilter,
  cities,
  page,
  totalPages,
  total,
  onSearchChange,
  onDurumChange,
  onTagChange,
  onOncelikChange,
  onSehirChange,
  onPageChange,
  onAdd,
  onImport,
  onDiscover,
  onView,
  onEdit,
  onDelete,
  readOnly = false,
  addButtonLabel,
}: Props) {
  const { app } = useLocale();
  const c = app.common;
  const discoverLabel = app.leadDiscovery.discoverLeads;
  const activeFilterCount = [durumFilter, tagFilter, oncelikFilter, sehirFilter].filter(Boolean).length;
  const hasActiveSearch = Boolean(search.trim()) || activeFilterCount > 0;
  const [searchPanelOpen, setSearchPanelOpen] = useState(hasActiveSearch);

  const filterSelects = (
    <>
      <select
        className="input-field min-w-0 max-w-full py-1.5 text-sm"
        value={durumFilter}
        onChange={(e) => {
          onDurumChange(e.target.value);
          onPageChange(1);
        }}
      >
        <option value="">{c.allStatuses}</option>
        {DURUM_STATUSES.map((status) => (
          <option key={status.value} value={status.value}>
            {app.statuses[status.value] ?? status.label}
          </option>
        ))}
      </select>
      <select
        className="input-field min-w-0 max-w-full py-1.5 text-sm"
        value={tagFilter}
        onChange={(e) => {
          onTagChange(e.target.value);
          onPageChange(1);
        }}
      >
        <option value="">{c.allTags}</option>
        {tags.map((tag) => (
          <option key={tag.id} value={tag.id}>
            {tag.label}
          </option>
        ))}
      </select>
      <select
        className="input-field min-w-0 max-w-full py-1.5 text-sm"
        value={oncelikFilter}
        onChange={(e) => {
          onOncelikChange(e.target.value);
          onPageChange(1);
        }}
      >
        <option value="">{c.allPriorities}</option>
        {ONCELIK_OPTIONS.map((option) => (
          <option key={option.value} value={option.value}>
            {app.priorities[option.value] ?? option.label}
          </option>
        ))}
      </select>
      <select
        className="input-field min-w-0 max-w-full py-1.5 text-sm"
        value={sehirFilter}
        onChange={(e) => {
          onSehirChange(e.target.value);
          onPageChange(1);
        }}
      >
        <option value="">{c.allCities}</option>
        {cities.map((city) => (
          <option key={city} value={city}>
            {city}
          </option>
        ))}
      </select>
    </>
  );

  const actionButtons = (
    <>
      <button onClick={onAdd} className="btn-primary min-h-9 shrink-0 justify-center px-3 py-2 text-sm lg:py-1.5">
        <Plus size={16} className="lg:hidden" />
        <span className="hidden lg:inline-flex lg:items-center lg:gap-1.5">
          <Plus size={15} />
          {addButtonLabel ?? c.newLead}
        </span>
      </button>
      {onImport ? (
        <button
          onClick={onImport}
          className="btn-secondary min-h-9 shrink-0 px-3 py-2 lg:py-1.5"
          aria-label={c.importExcel}
          title={c.importExcel}
        >
          <FileSpreadsheet size={16} />
          <span className="hidden lg:ml-1.5 lg:inline">{c.importExcel}</span>
        </button>
      ) : null}
      {onDiscover ? (
        <button
          onClick={onDiscover}
          className="btn-secondary min-h-9 shrink-0 px-3 py-2 lg:py-1.5"
          aria-label={discoverLabel}
          title={discoverLabel}
        >
          <Compass size={16} />
          <span className="hidden lg:ml-1.5 lg:inline">{discoverLabel}</span>
        </button>
      ) : null}
    </>
  );

  return (
    <div className="card flex min-h-0 flex-1 flex-col overflow-hidden max-lg:min-w-0 max-lg:rounded-none max-lg:border-x-0 max-lg:shadow-none">
      <div className="shrink-0 border-b border-surface-200 p-2.5 sm:p-3">
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setSearchPanelOpen((open) => !open)}
            className={`flex min-w-0 flex-1 items-center gap-2 rounded-lg border px-3 py-2 text-left text-sm transition ${
              searchPanelOpen
                ? 'border-brand-200 bg-brand-50/40'
                : 'border-surface-200 bg-surface-50/80 hover:bg-surface-50'
            }`}
            aria-expanded={searchPanelOpen}
          >
            {searchPanelOpen ? (
              <ChevronUp size={16} className="shrink-0 text-surface-800/50" />
            ) : (
              <ChevronDown size={16} className="shrink-0 text-surface-800/50" />
            )}
            <span className="min-w-0 flex-1 truncate font-medium text-surface-800">{c.searchAndFilters}</span>
            {hasActiveSearch ? (
              <span className="shrink-0 rounded-full bg-brand-100 px-2 py-0.5 text-xs font-medium text-brand-800">
                {search.trim() ? `${activeFilterCount + 1}` : String(activeFilterCount)}
              </span>
            ) : null}
            {!searchPanelOpen && search.trim() ? (
              <span className="hidden max-w-[40%] truncate text-xs text-surface-800/50 sm:inline">
                “{search.trim()}”
              </span>
            ) : null}
          </button>
          <div className="flex shrink-0 items-center gap-1.5">{actionButtons}</div>
        </div>

        {searchPanelOpen ? (
          <div className="mt-2 space-y-2 rounded-lg border border-surface-200 bg-white p-3">
            <div className="relative">
              <Search size={15} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-surface-800/40" />
              <input
                className="input-field py-1.5 pl-8 text-sm"
                placeholder={c.search}
                value={search}
                onChange={(e) => {
                  onSearchChange(e.target.value);
                  onPageChange(1);
                }}
              />
            </div>
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-4">
              {filterSelects}
            </div>
          </div>
        ) : null}
      </div>

      <div className="mobile-scroll-pane min-h-0 flex-1 overflow-auto bg-white">
        {!loading && total > 0 ? (
          <div className="sticky top-0 z-10 border-b border-surface-200 bg-surface-50 px-3 py-1.5 text-xs font-medium text-surface-800/70 sm:px-4">
            {app.stats.total}: {total}
          </div>
        ) : null}
        {loading ? (
          <p className="px-3 py-10 text-center text-sm text-surface-800/50">{c.loading}</p>
        ) : leads.length === 0 ? (
          <p className="px-3 py-10 text-center text-sm text-surface-800/50">{c.noRecords}</p>
        ) : (
          <div className="lg:grid lg:grid-cols-2 lg:gap-0 xl:grid-cols-3">
            {leads.map((lead) => (
              <MinimalLeadCard
                key={lead.id}
                lead={lead}
                readOnly={readOnly}
                onView={onView}
                onEdit={onEdit}
                onDelete={onDelete}
              />
            ))}
          </div>
        )}
      </div>

      {totalPages > 1 && (
        <div className="flex shrink-0 items-center justify-between gap-2 border-t border-surface-200 px-3.5 py-2.5 text-xs max-lg:safe-bottom">
          <span className="text-surface-800/50">
            {c.page.replace('{page}', String(page)).replace('{total}', String(totalPages))}
            {total > 0 ? ` · ${total}` : ''}
          </span>
          <div className="flex items-center gap-1.5">
            <button
              type="button"
              disabled={page <= 1 || loading}
              onClick={() => onPageChange(page - 1)}
              className="btn-secondary px-2.5 py-1.5 text-xs disabled:opacity-40"
            >
              {c.previousPage}
            </button>
            <button
              type="button"
              disabled={page >= totalPages || loading}
              onClick={() => onPageChange(page + 1)}
              className="btn-secondary px-2.5 py-1.5 text-xs disabled:opacity-40"
            >
              {c.nextPage}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
