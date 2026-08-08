import { useState } from 'react';
import { CheckCircle2, Clock, Inbox, XCircle } from 'lucide-react';
import type { LeadRequest, Tag, UserRole } from '../types';
import { useLocale } from '../i18n/locale';
import PriorityBadge from './PriorityBadge';
import RequestDetail from './RequestDetail';
import StatusBadge from './StatusBadge';

interface Props {
  requests: LeadRequest[];
  tags: Tag[];
  loading: boolean;
  role: UserRole;
  onApprove?: (request: LeadRequest) => Promise<void>;
  onReject?: (request: LeadRequest, note: string) => Promise<void>;
}

function statusIcon(status: string) {
  if (status === 'pending') return Clock;
  if (status === 'approved') return CheckCircle2;
  return XCircle;
}

export default function RequestsPage({
  requests,
  tags,
  loading,
  role,
  onApprove,
  onReject,
}: Props) {
  const { locale, app } = useLocale();
  const r = app.requestsPage;
  const [filter, setFilter] = useState(role === 'owner' ? 'pending' : '');
  const [viewingRequest, setViewingRequest] = useState<LeadRequest | null>(null);

  const statusFilters = [
    { id: 'pending', label: r.pending },
    { id: 'approved', label: r.approved },
    { id: 'rejected', label: r.rejected },
    { id: '', label: r.all },
  ] as const;

  const requestStatusLabel = (status: string) => {
    if (status === 'pending') return r.statusPending;
    if (status === 'approved') return r.statusApproved;
    if (status === 'rejected') return r.statusRejected;
    return status;
  };

  const filtered = filter
    ? requests.filter((item) => item.status === filter)
    : requests;

  const dateLocale = locale === 'en' ? 'en-US' : 'tr-TR';

  return (
    <div className="flex h-full min-h-0 flex-col gap-3 max-lg:min-w-0 max-lg:overflow-hidden">
      <div className="card flex shrink-0 flex-wrap items-center gap-2 p-3">
        {statusFilters.map((item) => (
          <button
            key={item.id || 'all'}
            onClick={() => setFilter(item.id)}
            className={`rounded-lg px-2.5 py-1.5 text-xs font-medium transition lg:px-3 lg:py-1.5 lg:text-sm ${
              filter === item.id ? 'bg-brand-500 text-white' : 'bg-surface-100 text-surface-800/70 hover:bg-surface-200'
            }`}
          >
            {item.label}
          </button>
        ))}
      </div>

      <div className="card flex min-h-0 flex-1 flex-col overflow-hidden">
        {loading ? (
          <p className="p-8 text-center text-sm text-surface-800/50">{r.loading}</p>
        ) : filtered.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center p-8 text-center">
            <Inbox size={40} className="mb-3 text-surface-300" />
            <p className="text-sm text-surface-800/50">
              {role === 'owner' ? r.emptyOwner : r.emptyEmployee}
            </p>
          </div>
        ) : (
          <>
            <div className="mobile-scroll-pane divide-y divide-surface-100 lg:hidden">
              {filtered.map((request) => {
                const Icon = statusIcon(request.status);

                return (
                  <article
                    key={request.id}
                    onClick={() => setViewingRequest(request)}
                    className="cursor-pointer px-3.5 py-3 transition active:bg-brand-50/40"
                  >
                    <div className="flex items-start gap-2.5">
                      <Icon
                        size={15}
                        className={
                          request.status === 'pending'
                            ? 'mt-0.5 shrink-0 text-amber-500'
                            : request.status === 'approved'
                              ? 'mt-0.5 shrink-0 text-emerald-600'
                              : 'mt-0.5 shrink-0 text-red-500'
                        }
                      />
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-semibold leading-snug text-surface-900 line-clamp-2">{request.isletme_adi}</p>
                        <p className="mt-0.5 text-xs text-surface-800/60">
                          {[request.yetkili, request.sehir, request.category_label].filter(Boolean).join(' · ')}
                        </p>
                        <div className="mt-2 flex flex-wrap items-center gap-1.5">
                          <StatusBadge durum={request.durum} size="xs" />
                          <PriorityBadge oncelik={request.oncelik || 'orta'} size="xs" />
                          <span
                            className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${
                              request.status === 'pending'
                                ? 'bg-amber-100 text-amber-800'
                                : request.status === 'approved'
                                  ? 'bg-emerald-100 text-emerald-800'
                                  : 'bg-red-100 text-red-800'
                            }`}
                          >
                            {requestStatusLabel(request.status)}
                          </span>
                        </div>
                        <p className="mt-1.5 text-xs text-surface-800/50">
                          {request.requested_by_username} · {new Date(request.created_at).toLocaleDateString(dateLocale)}
                        </p>
                      </div>
                    </div>
                  </article>
                );
              })}
            </div>

            <div className="hidden h-full overflow-auto lg:block">
            <table className="w-full text-left text-sm">
              <thead className="sticky top-0 z-10 bg-surface-50 shadow-sm">
                <tr className="border-b border-surface-200 text-[11px] font-medium uppercase tracking-wide text-surface-800/50">
                  <th className="px-4 py-2.5">{r.business}</th>
                  <th className="hidden px-4 py-2.5 md:table-cell">{r.category}</th>
                  <th className="px-4 py-2.5">{r.status}</th>
                  <th className="hidden px-4 py-2.5 lg:table-cell">{r.status}</th>
                  <th className="hidden px-4 py-2.5 sm:table-cell">{r.submittedAt}</th>
                  <th className="px-4 py-2.5">{app.revenue.date}</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((request) => {
                  const Icon = statusIcon(request.status);

                  return (
                    <tr
                      key={request.id}
                      onClick={() => setViewingRequest(request)}
                      className="cursor-pointer border-b border-surface-100 transition hover:bg-brand-50/40"
                    >
                      <td className="max-w-[220px] px-4 py-3">
                        <div className="flex items-center gap-2">
                          <Icon
                            size={14}
                            className={
                              request.status === 'pending'
                                ? 'shrink-0 text-amber-500'
                                : request.status === 'approved'
                                  ? 'shrink-0 text-emerald-600'
                                  : 'shrink-0 text-red-500'
                            }
                          />
                          <div className="min-w-0">
                            <p className="truncate font-medium text-surface-900">{request.isletme_adi}</p>
                            <p className="truncate text-xs text-surface-800/50">
                              {[request.yetkili, request.sehir].filter(Boolean).join(' · ') || `#${request.id}`}
                            </p>
                          </div>
                        </div>
                      </td>
                      <td className="hidden px-4 py-3 text-surface-800/70 md:table-cell">
                        {request.category_label}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex flex-col gap-1">
                          <StatusBadge durum={request.durum} size="xs" />
                          <PriorityBadge oncelik={request.oncelik || 'orta'} size="xs" />
                        </div>
                      </td>
                      <td className="hidden px-4 py-3 lg:table-cell">
                        <span
                          className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${
                            request.status === 'pending'
                              ? 'bg-amber-100 text-amber-800'
                              : request.status === 'approved'
                                ? 'bg-emerald-100 text-emerald-800'
                                : 'bg-red-100 text-red-800'
                          }`}
                        >
                          {requestStatusLabel(request.status)}
                        </span>
                      </td>
                      <td className="hidden px-4 py-3 text-surface-800/70 sm:table-cell">
                        {request.requested_by_username}
                      </td>
                      <td className="whitespace-nowrap px-4 py-3 text-xs text-surface-800/60">
                        {new Date(request.created_at).toLocaleDateString(dateLocale)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            </div>
          </>
        )}
      </div>

      {viewingRequest && (
        <RequestDetail
          request={viewingRequest}
          tags={tags}
          role={role}
          onClose={() => setViewingRequest(null)}
          onApprove={onApprove}
          onReject={onReject}
        />
      )}
    </div>
  );
}
