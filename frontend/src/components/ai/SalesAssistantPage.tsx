/**
 * DE-6.3-B — Full-screen Sales Assistant workspace.
 * Uses the same conversation + stream APIs as AiChatWidget (no backend changes).
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Archive,
  Loader2,
  Menu,
  MessageSquareText,
  PanelLeftClose,
  Plus,
  Search,
  Send,
  Sparkles,
} from 'lucide-react';
import { api } from '../../api';
import { useLocale } from '../../i18n/locale';
import type { AssistantConversation, AiStatusResponse } from '../../types';
import {
  conversationDateGroup,
  isSnakeToolName,
  sanitizeAssistantDisplayText,
  titlePreview,
  type ConversationDateGroup,
} from './assistantConversationUi';

type ChatTurn = { role: 'user' | 'assistant'; content: string; id?: number };

const GROUP_ORDER: ConversationDateGroup[] = ['today', 'yesterday', 'last7', 'older'];

export default function SalesAssistantPage() {
  const { app, locale } = useLocale();
  const t = app.chat;

  const [available, setAvailable] = useState<boolean | null>(null);
  const [conversations, setConversations] = useState<AssistantConversation[]>([]);
  const [listLoading, setListLoading] = useState(true);
  const [listError, setListError] = useState<string | null>(null);

  /** null = draft new chat (no DB row until first send) */
  const [conversationId, setConversationId] = useState<number | null>(null);
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState<string | null>(null);

  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const [toolStatus, setToolStatus] = useState<string | null>(null);
  const [chatError, setChatError] = useState<string | null>(null);

  const [search, setSearch] = useState('');
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const scrollRef = useRef<HTMLDivElement>(null);
  const composerRef = useRef<HTMLTextAreaElement>(null);
  const listFetchGen = useRef(0);
  const historyFetchGen = useRef(0);

  const suggestions = useMemo(
    () => [
      t.suggestionToday,
      t.suggestionCritical,
      t.suggestionPendingOffers,
      t.suggestionFollowups,
      t.suggestionSales,
      t.suggestionOffer,
    ],
    [
      t.suggestionCritical,
      t.suggestionFollowups,
      t.suggestionOffer,
      t.suggestionPendingOffers,
      t.suggestionSales,
      t.suggestionToday,
    ],
  );

  const emptySuggestions = useMemo(
    () => [t.emptySuggestion1, t.emptySuggestion2, t.emptySuggestion3],
    [t.emptySuggestion1, t.emptySuggestion2, t.emptySuggestion3],
  );

  useEffect(() => {
    let cancelled = false;
    api
      .getAiStatus()
      .then((status: AiStatusResponse) => {
        if (!cancelled) setAvailable(Boolean(status.chat_available));
      })
      .catch(() => {
        if (!cancelled) setAvailable(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const loadList = useCallback(async () => {
    const gen = ++listFetchGen.current;
    setListLoading(true);
    setListError(null);
    try {
      const res = await api.listAssistantConversations();
      if (gen !== listFetchGen.current) return;
      setConversations(res.items);
    } catch {
      if (gen !== listFetchGen.current) return;
      setListError(t.listFailed);
    } finally {
      if (gen === listFetchGen.current) setListLoading(false);
    }
  }, [t.listFailed]);

  useEffect(() => {
    if (available !== true) return;
    void loadList();
  }, [available, loadList]);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [turns, sending, streaming, toolStatus]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setSidebarOpen(false);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  const loadConversation = useCallback(
    async (id: number) => {
      const gen = ++historyFetchGen.current;
      setHistoryLoading(true);
      setHistoryError(null);
      setChatError(null);
      try {
        const detail = await api.getAssistantConversation(id);
        if (gen !== historyFetchGen.current) return;
        setConversationId(detail.conversation.id);
        setTurns(
          detail.messages
            .map((m) => ({
              id: m.id,
              role: (m.role === 'assistant' ? 'assistant' : 'user') as 'user' | 'assistant',
              content: sanitizeAssistantDisplayText(m.content),
            }))
            .filter((m) => m.content.length > 0 || m.role === 'user'),
        );
        setSidebarOpen(false);
        requestAnimationFrame(() => composerRef.current?.focus());
      } catch {
        if (gen !== historyFetchGen.current) return;
        setHistoryError(t.historyFailed);
      } finally {
        if (gen === historyFetchGen.current) setHistoryLoading(false);
      }
    },
    [t.historyFailed],
  );

  const startDraft = useCallback(() => {
    if (sending) return;
    historyFetchGen.current += 1;
    setConversationId(null);
    setTurns([]);
    setHistoryError(null);
    setChatError(null);
    setToolStatus(null);
    setSidebarOpen(false);
    requestAnimationFrame(() => composerRef.current?.focus());
  }, [sending]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return conversations;
    return conversations.filter((c) => (c.title || '').toLowerCase().includes(q));
  }, [conversations, search]);

  const grouped = useMemo(() => {
    const map: Record<ConversationDateGroup, AssistantConversation[]> = {
      today: [],
      yesterday: [],
      last7: [],
      older: [],
    };
    for (const c of filtered) {
      map[conversationDateGroup(c.updated_at)].push(c);
    }
    return map;
  }, [filtered]);

  const groupLabel = (g: ConversationDateGroup) => {
    if (g === 'today') return t.groupToday;
    if (g === 'yesterday') return t.groupYesterday;
    if (g === 'last7') return t.groupLast7;
    return t.groupOlder;
  };

  const activeTitle = useMemo(() => {
    if (conversationId == null) return t.newChat;
    const found = conversations.find((c) => c.id === conversationId);
    return titlePreview(found?.title, t.untitled);
  }, [conversationId, conversations, t.newChat, t.untitled]);

  const sendMessage = useCallback(
    async (rawText: string) => {
      const text = rawText.trim();
      if (!text || sending || historyLoading) return;
      setInput('');
      setChatError(null);
      setHistoryError(null);

      let activeId = conversationId;
      if (activeId == null) {
        try {
          const created = await api.createAssistantConversation();
          activeId = created.id;
          setConversationId(created.id);
          setConversations((prev) => [created, ...prev.filter((c) => c.id !== created.id)]);
        } catch {
          setChatError(t.sendFailed);
          return;
        }
      }

      setTurns((prev) => [...prev, { role: 'user', content: text }, { role: 'assistant', content: '' }]);
      setSending(true);
      setStreaming(false);
      setToolStatus(null);

      let sawDelta = false;
      try {
        let accumulated = '';
        await api.streamAiChat(
          {
            message: text,
            conversation_id: activeId,
            locale: locale === 'en' ? 'en' : 'tr',
          },
          (delta) => {
            if (!sawDelta) {
              sawDelta = true;
              setStreaming(true);
              setToolStatus(null);
            }
            accumulated += delta;
            const snapshot = sanitizeAssistantDisplayText(accumulated) || accumulated;
            setTurns((prev) => {
              const copy = [...prev];
              copy[copy.length - 1] = { role: 'assistant', content: snapshot };
              return copy;
            });
          },
          (status) => {
            if (!status) {
              setToolStatus(null);
              return;
            }
            setToolStatus(isSnakeToolName(status) ? t.toolWorking : status);
          },
        );
        // Refresh titles/order only — not every conversation's messages.
        void api
          .listAssistantConversations()
          .then((list) => setConversations(list.items))
          .catch(() => {});
      } catch {
        setTurns((prev) => {
          if (prev.length && prev[prev.length - 1].role === 'assistant' && !prev[prev.length - 1].content) {
            return prev.slice(0, -1);
          }
          return prev;
        });
        setChatError(t.sendFailed);
      } finally {
        setSending(false);
        setStreaming(false);
        setToolStatus(null);
        requestAnimationFrame(() => composerRef.current?.focus());
      }
    },
    [conversationId, historyLoading, locale, sending, t.sendFailed, t.toolWorking],
  );

  const archiveActive = useCallback(async () => {
    if (conversationId == null || sending) return;
    try {
      await api.archiveAssistantConversation(conversationId);
      setConversations((prev) => prev.filter((c) => c.id !== conversationId));
      startDraft();
    } catch {
      setChatError(t.archiveFailed);
    }
  }, [conversationId, sending, startDraft, t.archiveFailed]);

  if (available === null) {
    return (
      <div className="flex h-full min-h-[320px] items-center justify-center text-sm text-surface-800/50">
        <Loader2 size={18} className="mr-2 animate-spin" />
        {app.common.loading}
      </div>
    );
  }

  if (available === false) {
    return (
      <div className="card flex h-full min-h-[280px] flex-col items-center justify-center gap-2 p-8 text-center">
        <MessageSquareText className="text-surface-800/35" size={28} />
        <p className="text-sm font-medium text-surface-900">{t.unavailableTitle}</p>
        <p className="max-w-sm text-sm text-surface-800/55">{t.unavailableBody}</p>
      </div>
    );
  }

  const showEmptyWorkspace = conversationId == null && turns.length === 0 && !historyLoading;

  const sidebar = (
    <aside
      className="flex h-full w-full flex-col border-r border-surface-200 bg-white lg:w-[280px] lg:shrink-0"
      aria-label={t.pastChats}
    >
      <div className="flex items-center gap-2 border-b border-surface-100 p-3">
        <button
          type="button"
          onClick={startDraft}
          disabled={sending}
          className="btn-primary min-h-[40px] flex-1 justify-center text-sm"
          aria-label={t.newChat}
        >
          <Plus size={16} />
          {t.newChat}
        </button>
        <button
          type="button"
          className="rounded-lg p-2 text-surface-800/50 hover:bg-surface-50 lg:hidden"
          onClick={() => setSidebarOpen(false)}
          aria-label={t.closeSidebar}
        >
          <PanelLeftClose size={18} />
        </button>
      </div>

      <div className="border-b border-surface-100 px-3 py-2">
        <label className="sr-only" htmlFor="assistant-search">
          {t.searchChats}
        </label>
        <div className="relative">
          <Search
            size={14}
            className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-surface-800/40"
          />
          <input
            id="assistant-search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder={t.searchChats}
            className="input-field py-2 pl-8 text-sm"
          />
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-2 py-2">
        {listLoading ? (
          <div className="flex items-center gap-2 px-2 py-3 text-sm text-surface-800/50">
            <Loader2 size={14} className="animate-spin" />
            {app.common.loading}
          </div>
        ) : null}
        {listError ? (
          <div className="space-y-2 px-2 py-3">
            <p className="text-sm text-rose-600">{listError}</p>
            <button type="button" className="btn-secondary text-xs" onClick={() => void loadList()}>
              {t.retry}
            </button>
          </div>
        ) : null}
        {!listLoading && !listError && filtered.length === 0 ? (
          <p className="px-2 py-3 text-sm text-surface-800/45">{t.noConversations}</p>
        ) : null}
        {GROUP_ORDER.map((g) => {
          const items = grouped[g];
          if (!items.length) return null;
          return (
            <div key={g} className="mb-3">
              <p className="px-2 pb-1 text-[11px] font-semibold uppercase tracking-wide text-surface-800/45">
                {groupLabel(g)}
              </p>
              <ul className="space-y-0.5">
                {items.map((c) => {
                  const active = c.id === conversationId;
                  return (
                    <li key={c.id}>
                      <button
                        type="button"
                        disabled={sending || historyLoading}
                        onClick={() => void loadConversation(c.id)}
                        className={
                          active
                            ? 'w-full rounded-lg bg-brand-500/10 px-2.5 py-2 text-left text-sm font-medium text-brand-800'
                            : 'w-full rounded-lg px-2.5 py-2 text-left text-sm text-surface-800/80 hover:bg-surface-50'
                        }
                        aria-current={active ? 'true' : undefined}
                      >
                        <span className="line-clamp-2">{titlePreview(c.title, t.untitled)}</span>
                      </button>
                    </li>
                  );
                })}
              </ul>
            </div>
          );
        })}
      </div>
    </aside>
  );

  return (
    <div className="flex h-full min-h-0 overflow-hidden rounded-xl border border-surface-200 bg-white shadow-sm">
      {/* Desktop sidebar */}
      <div className="hidden h-full lg:flex">{sidebar}</div>

      {/* Mobile drawer */}
      {sidebarOpen ? (
        <div className="fixed inset-0 z-40 lg:hidden" role="presentation">
          <button
            type="button"
            className="absolute inset-0 bg-black/30"
            aria-label={t.closeSidebar}
            onClick={() => setSidebarOpen(false)}
          />
          <div className="absolute inset-y-0 left-0 flex w-[min(100%,320px)] shadow-xl">{sidebar}</div>
        </div>
      ) : null}

      {/* Chat panel */}
      <section className="flex min-w-0 flex-1 flex-col" aria-label={t.title}>
        <header className="flex items-center gap-2 border-b border-surface-100 px-3 py-2.5 sm:px-4">
          <button
            type="button"
            className="rounded-lg p-2 text-surface-800/60 hover:bg-surface-50 lg:hidden"
            onClick={() => setSidebarOpen(true)}
            aria-label={t.openSidebar}
          >
            <Menu size={18} />
          </button>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-1.5">
              <Sparkles size={16} className="shrink-0 text-brand-600" />
              <h1 className="truncate text-sm font-semibold text-surface-900 sm:text-base">{activeTitle}</h1>
            </div>
            <p className="truncate text-[11px] text-surface-800/50">{t.subtitle}</p>
          </div>
          {conversationId != null ? (
            <button
              type="button"
              onClick={() => void archiveActive()}
              disabled={sending}
              className="rounded-lg p-2 text-surface-800/45 hover:bg-surface-50 hover:text-rose-600 disabled:opacity-40"
              aria-label={t.archiveChat}
              title={t.archiveChat}
            >
              <Archive size={16} />
            </button>
          ) : null}
        </header>

        <div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto px-3 py-4 sm:px-6">
          <div className="mx-auto flex w-full max-w-3xl flex-col gap-3">
            {historyLoading ? (
              <div className="flex items-center gap-2 text-sm text-surface-800/50">
                <Loader2 size={16} className="animate-spin" />
                {t.loadingHistory}
              </div>
            ) : null}

            {historyError ? (
              <div className="space-y-2 rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">
                <p>{historyError}</p>
                {conversationId != null ? (
                  <button
                    type="button"
                    className="btn-secondary text-xs"
                    onClick={() => void loadConversation(conversationId)}
                  >
                    {t.retry}
                  </button>
                ) : null}
              </div>
            ) : null}

            {showEmptyWorkspace ? (
              <div className="flex flex-col items-center px-2 py-10 text-center sm:py-16">
                <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-brand-50 text-brand-700">
                  <MessageSquareText size={22} />
                </div>
                <h2 className="text-xl font-semibold text-surface-900 sm:text-2xl">{t.pageTitle}</h2>
                <p className="mt-2 max-w-md text-sm leading-relaxed text-surface-800/60">{t.pageSubtitle}</p>
                <div className="mt-6 flex w-full max-w-lg flex-col gap-2 sm:flex-row sm:flex-wrap sm:justify-center">
                  {emptySuggestions.map((s) => (
                    <button
                      key={s}
                      type="button"
                      disabled={sending}
                      onClick={() => void sendMessage(s)}
                      className="rounded-xl border border-surface-200 bg-surface-50 px-3 py-2.5 text-left text-sm text-surface-800/80 transition hover:border-brand-300 hover:bg-brand-50/40 sm:text-center"
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            ) : null}

            {!showEmptyWorkspace &&
              turns.map((turn, idx) => {
                if (turn.role === 'assistant' && !turn.content.trim() && sending) return null;
                return (
                  <div
                    key={turn.id ?? `${idx}-${turn.role}`}
                    className={
                      turn.role === 'user'
                        ? 'ml-auto max-w-[92%] rounded-2xl bg-brand-500/10 px-3.5 py-2.5 text-sm text-surface-900 sm:max-w-[80%]'
                        : 'mr-auto max-w-[92%] rounded-2xl bg-surface-50 px-3.5 py-2.5 text-sm leading-relaxed text-surface-800/90 ring-1 ring-surface-100 sm:max-w-[85%]'
                    }
                  >
                    {turn.content}
                  </div>
                );
              })}

            {sending && !streaming ? (
              <div className="flex items-center gap-2 text-sm text-surface-800/50">
                <Loader2 size={16} className="animate-spin" />
                {toolStatus || t.thinking}
              </div>
            ) : null}
            {sending && streaming && toolStatus ? (
              <div className="flex items-center gap-2 text-sm text-surface-800/50">
                <Loader2 size={16} className="animate-spin" />
                {toolStatus}
              </div>
            ) : null}

            {chatError ? (
              <div className="space-y-2 rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">
                <p>{chatError}</p>
                <button type="button" className="btn-secondary text-xs" onClick={() => setChatError(null)}>
                  {t.retry}
                </button>
              </div>
            ) : null}
          </div>
        </div>

        <div className="sticky bottom-0 border-t border-surface-100 bg-white px-3 py-3 sm:px-6">
          <div className="mx-auto w-full max-w-3xl">
            {turns.length === 0 && conversationId != null && !historyLoading ? (
              <div className="mb-2 flex gap-2 overflow-x-auto pb-1">
                {suggestions.map((s) => (
                  <button
                    key={s}
                    type="button"
                    disabled={sending}
                    onClick={() => void sendMessage(s)}
                    className="shrink-0 rounded-full border border-surface-200 bg-surface-50 px-3 py-1.5 text-xs text-surface-800/70 hover:border-brand-300"
                  >
                    {s}
                  </button>
                ))}
              </div>
            ) : null}

            <div className="flex gap-2">
              <label className="sr-only" htmlFor="assistant-composer">
                {t.composerLabel}
              </label>
              <textarea
                id="assistant-composer"
                ref={composerRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                rows={2}
                disabled={sending || historyLoading}
                placeholder={t.composerPlaceholder}
                className="input-field min-h-[48px] max-h-36 flex-1 resize-none text-sm"
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    void sendMessage(input);
                  }
                }}
              />
              <button
                type="button"
                disabled={sending || historyLoading || !input.trim()}
                onClick={() => void sendMessage(input)}
                className="btn-primary shrink-0 self-end px-3 py-2.5"
                aria-label={t.send}
              >
                {sending ? <Loader2 size={18} className="animate-spin" /> : <Send size={18} />}
              </button>
            </div>
            <p className="mt-2 text-[10px] text-surface-800/45">{t.disclaimer}</p>
          </div>
        </div>
      </section>
    </div>
  );
}
