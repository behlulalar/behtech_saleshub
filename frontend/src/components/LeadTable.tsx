import { Compass, Edit2, ExternalLink, FileSpreadsheet, Filter, Instagram, Mail, MessageCircle, Phone, Plus, Search, Trash2 } from 'lucide-react';
import { useState, type MouseEvent } from 'react';
import type { Lead, Tag } from '../types';
import { DURUM_STATUSES, ONCELIK_OPTIONS } from '../types';
import { useLocale } from '../i18n/locale';
import { toInstagramUrl, toMailtoUrl, toTelUrl, toWhatsAppUrl } from '../utils';
import PriorityBadge from './PriorityBadge';
import StatusBadge from './StatusBadge';
import TagBadges from './TagBadges';

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

function ContactQuickActions({
  lead,
  stopPropagation,
}: {
  lead: Lead;
  stopPropagation: (e: MouseEvent) => void;
}) {
  const { app } = useLocale();
  const c = app.communication;
  const instagramUrl = lead.instagram ? toInstagramUrl(lead.instagram) : null;
  const whatsAppUrl = lead.whatsapp ? toWhatsAppUrl(lead.whatsapp) : null;
  const telUrl = lead.whatsapp ? toTelUrl(lead.whatsapp) : null;
  const mailUrl = toMailtoUrl({
    email: lead.eposta,
    subject: `${lead.isletme_adi} — BehTech Sales Hub`,
  });

  const btn =
    'rounded-md p-1 text-surface-800/50 hover:bg-surface-100 hover:text-brand-500 disabled:opacity-30';

  return (
    <div className="mt-1 flex items-center gap-0.5">
      <button
        type="button"
        disabled={!whatsAppUrl}
        title={c.whatsapp}
        className={btn}
        onClick={(e) => {
          stopPropagation(e);
          if (whatsAppUrl) window.open(whatsAppUrl, '_blank', 'noopener,noreferrer');
        }}
      >
        <MessageCircle size={13} />
      </button>
      <button
        type="button"
        disabled={!telUrl}
        title={c.call}
        className={btn}
        onClick={(e) => {
          stopPropagation(e);
          if (telUrl) window.open(telUrl, '_blank', 'noopener,noreferrer');
        }}
      >
        <Phone size={13} />
      </button>
      <button
        type="button"
        disabled={!instagramUrl}
        title={c.instagram}
        className={btn}
        onClick={(e) => {
          stopPropagation(e);
          if (instagramUrl) window.open(instagramUrl, '_blank', 'noopener,noreferrer');
        }}
      >
        <Instagram size={13} />
      </button>
      <button
        type="button"
        title={c.email}
        className={btn}
        onClick={(e) => {
          stopPropagation(e);
          window.open(mailUrl, '_blank', 'noopener,noreferrer');
        }}
      >
        <Mail size={13} />
      </button>
    </div>
  );
}

function ProcessSummary({ lead, hideOffer = false }: { lead: Lead; hideOffer?: boolean }) {
  const parts: string[] = [];
  if (lead.demo_gonderildi) parts.push(`Demo: ${lead.demo_tarihi || '✓'}`);
  if (lead.gorusme_tarihi) {
    parts.push(`Görüşme: ${lead.gorusme_tarihi}${lead.gorusme_saati ? ` ${lead.gorusme_saati}` : ''}`);
  }
  if (!hideOffer && lead.teklif) parts.push(`Teklif: ${lead.teklif}`);

  if (!parts.length) return <span className="text-surface-800/40">—</span>;

  return (
    <div className="space-y-0.5 text-xs text-surface-800/70">
      {parts.map((part) => (
        <p key={part} className="truncate" title={part}>{part}</p>
      ))}
    </div>
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
  const [mobileFiltersOpen, setMobileFiltersOpen] = useState(false);
  const activeFilterCount = [durumFilter, tagFilter, oncelikFilter, sehirFilter].filter(Boolean).length;

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
          <option key={status.value} value={status.value}>{app.statuses[status.value] ?? status.label}</option>
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
          <option key={tag.id} value={tag.id}>{tag.label}</option>
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
          <option key={option.value} value={option.value}>{app.priorities[option.value] ?? option.label}</option>
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
          <option key={city} value={city}>{city}</option>
        ))}
      </select>
    </>
  );

  return (
    <div className="card flex min-h-0 flex-1 flex-col overflow-hidden max-lg:min-w-0 max-lg:rounded-none max-lg:border-x-0 max-lg:shadow-none">
      <div className="shrink-0 border-b border-surface-200 p-3 max-lg:p-2.5">
        <div className="flex flex-col gap-2 lg:flex-row lg:items-center">
          <div className="relative min-w-0 flex-1">
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

          <div className="flex items-center gap-2 lg:hidden">
            <button
              type="button"
              onClick={() => setMobileFiltersOpen((open) => !open)}
              className={`btn-secondary min-h-9 flex-1 justify-center py-2 text-xs ${
                activeFilterCount > 0 ? 'border-brand-500 text-brand-600' : ''
              }`}
            >
              <Filter size={14} />
              {c.filters}
              {activeFilterCount > 0 ? ` (${activeFilterCount})` : ''}
            </button>
            <button onClick={onAdd} className="btn-primary min-h-9 shrink-0 px-3 py-2" aria-label={addButtonLabel ?? c.newLead}>
              <Plus size={16} />
            </button>
            {onImport ? (
              <button onClick={onImport} className="btn-secondary min-h-9 shrink-0 px-3 py-2" aria-label={c.importExcel}>
                <FileSpreadsheet size={16} />
              </button>
            ) : null}
            {onDiscover ? (
              <button onClick={onDiscover} className="btn-secondary min-h-9 shrink-0 px-3 py-2" aria-label={discoverLabel}>
                <Compass size={16} />
              </button>
            ) : null}
          </div>

          {mobileFiltersOpen ? (
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:hidden">
              {filterSelects}
            </div>
          ) : null}

          <div className="hidden min-w-0 max-w-full flex-wrap items-center gap-2 lg:flex lg:w-auto">
            {filterSelects}
            <button onClick={onAdd} className="btn-primary justify-center py-1.5 text-sm">
              <Plus size={15} />
              {addButtonLabel ?? c.newLead}
            </button>
            {onImport ? (
              <button onClick={onImport} className="btn-secondary justify-center py-1.5 text-sm">
                <FileSpreadsheet size={15} />
                {c.importExcel}
              </button>
            ) : null}
            {onDiscover ? (
              <button onClick={onDiscover} className="btn-secondary justify-center py-1.5 text-sm">
                <Compass size={15} />
                {discoverLabel}
              </button>
            ) : null}
          </div>
        </div>
      </div>

      <div className="mobile-scroll-pane bg-white lg:hidden">
        {!loading && total > 0 ? (
          <div className="sticky top-0 z-10 border-b border-surface-200 bg-surface-50 px-3.5 py-2 text-xs font-medium text-surface-800/70">
            {app.stats.total}: {total}
          </div>
        ) : null}
        {loading ? (
          <p className="px-3 py-10 text-center text-sm text-surface-800/50">{c.loading}</p>
        ) : leads.length === 0 ? (
          <p className="px-3 py-10 text-center text-sm text-surface-800/50">{c.noRecords}</p>
        ) : (
          <div className="divide-y divide-surface-200">
            {leads.map((lead) => {
              const contactLine = lead.whatsapp || lead.instagram || lead.eposta || null;

              return (
                <article
                  key={lead.id}
                  onClick={() => onView(lead)}
                  className="cursor-pointer px-3.5 py-3 transition active:bg-brand-50/50"
                >
                  <div className="flex items-start gap-2.5">
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-semibold leading-snug text-surface-900 line-clamp-2">
                        {lead.isletme_adi}
                      </p>
                      {(lead.yetkili || lead.sehir) ? (
                        <p className="mt-0.5 text-xs leading-relaxed text-surface-800/65">
                          {[lead.yetkili, lead.sehir].filter(Boolean).join(' · ')}
                        </p>
                      ) : (
                        <p className="mt-0.5 text-xs text-surface-800/45">#{lead.id}</p>
                      )}
                      <div className="mt-2 flex flex-wrap items-center gap-1.5">
                        <StatusBadge durum={lead.durum} size="xs" />
                        <PriorityBadge oncelik={lead.oncelik || 'orta'} size="xs" />
                        <TagBadges tags={lead.tags || []} />
                      </div>
                      {contactLine ? (
                        <p className="mt-1.5 truncate text-xs text-surface-800/60">{contactLine}</p>
                      ) : null}
                    </div>
                    {!readOnly && (
                      <div className="flex shrink-0 flex-col gap-0.5">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            onEdit(lead);
                          }}
                          className="rounded-lg p-2 text-surface-800/60 hover:bg-brand-50 hover:text-brand-500"
                          title="Düzenle"
                        >
                          <Edit2 size={15} />
                        </button>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            onDelete(lead);
                          }}
                          className="rounded-lg p-2 text-surface-800/60 hover:bg-red-50 hover:text-red-600"
                          title="Sil"
                        >
                          <Trash2 size={15} />
                        </button>
                      </div>
                    )}
                  </div>
                </article>
              );
            })}
          </div>
        )}
      </div>

      <div className="hidden min-h-0 flex-1 overflow-auto lg:block">
        <table className="w-full text-left text-sm">
          <thead className="sticky top-0 z-10 bg-surface-50 shadow-sm">
            <tr className="border-b border-surface-200 text-[11px] font-medium uppercase tracking-wide text-surface-800/50">
              <th className="px-3 py-2">{c.business}</th>
              <th className="hidden px-3 py-2 md:table-cell">{c.tag}</th>
              <th className="px-3 py-2">{c.priority}</th>
              <th className="px-3 py-2">{c.status}</th>
              <th className="hidden px-3 py-2 lg:table-cell">{c.contact}</th>
              <th className="hidden px-3 py-2 xl:table-cell">{c.process}</th>
              <th className="w-16 px-2 py-2 text-center">{readOnly ? '' : c.actions}</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={7} className="px-3 py-10 text-center text-surface-800/50">
                  {c.loading}
                </td>
              </tr>
            ) : leads.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-3 py-10 text-center text-surface-800/50">
                  {c.noRecords}
                </td>
              </tr>
            ) : (
              leads.map((lead) => {
                const instagramUrl = lead.instagram ? toInstagramUrl(lead.instagram) : null;

                return (
                  <tr
                    key={lead.id}
                    onClick={() => onView(lead)}
                    className="cursor-pointer border-b border-surface-100 transition hover:bg-brand-50/40"
                  >
                    <td className="max-w-[220px] px-3 py-2">
                      <p className="truncate font-medium text-surface-900" title={lead.isletme_adi}>
                        {lead.isletme_adi}
                      </p>
                      <p className="truncate text-xs text-surface-800/50">
                        {[lead.yetkili, lead.sehir].filter(Boolean).join(' · ') || `#${lead.id}`}
                      </p>
                      <div className="mt-1 flex flex-wrap gap-1 md:hidden">
                        <TagBadges tags={lead.tags || []} />
                      </div>
                    </td>
                    <td className="hidden max-w-[130px] px-3 py-2 md:table-cell">
                      <TagBadges tags={lead.tags || []} />
                    </td>
                    <td className="whitespace-nowrap px-3 py-2">
                      <PriorityBadge oncelik={lead.oncelik || 'orta'} size="xs" />
                    </td>
                    <td className="px-3 py-2">
                      <StatusBadge durum={lead.durum} size="xs" />
                    </td>
                    <td className="hidden max-w-[140px] px-3 py-2 lg:table-cell">
                      <div className="space-y-0.5 text-xs">
                        {lead.instagram ? (
                          instagramUrl ? (
                            <a
                              href={instagramUrl}
                              target="_blank"
                              rel="noopener noreferrer"
                              onClick={(e) => e.stopPropagation()}
                              className="inline-flex max-w-full items-center gap-1 truncate text-brand-500 hover:underline"
                            >
                              {lead.instagram}
                              <ExternalLink size={10} />
                            </a>
                          ) : (
                            <span className="truncate">{lead.instagram}</span>
                          )
                        ) : null}
                        {lead.whatsapp && (
                          <p className="truncate text-surface-800/60">{lead.whatsapp}</p>
                        )}
                        {!lead.instagram && !lead.whatsapp && !lead.eposta && '—'}
                        <ContactQuickActions lead={lead} stopPropagation={(e) => e.stopPropagation()} />
                      </div>
                    </td>
                    <td className="hidden max-w-[160px] px-3 py-2 xl:table-cell">
                      <ProcessSummary lead={lead} hideOffer={readOnly} />
                    </td>
                    <td className="px-2 py-2">
                      {!readOnly && (
                        <div className="flex items-center justify-center gap-0.5">
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              onEdit(lead);
                            }}
                            className="rounded-lg p-1.5 text-surface-800/60 hover:bg-brand-50 hover:text-brand-500"
                            title="Düzenle"
                          >
                            <Edit2 size={14} />
                          </button>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              onDelete(lead);
                            }}
                            className="rounded-lg p-1.5 text-surface-800/60 hover:bg-red-50 hover:text-red-600"
                            title="Sil"
                          >
                            <Trash2 size={14} />
                          </button>
                        </div>
                      )}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
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
