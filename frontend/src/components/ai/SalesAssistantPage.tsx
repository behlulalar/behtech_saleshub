/**
 * DE-6.3-B / DE-6.8 — Full-screen Sales Assistant workspace.
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
  formatRelativeConversationTime,
  isSnakeToolName,
  sanitizeAssistantDisplayText,
  splitAssistantContentBlocks,
  titlePreview,
  type ConversationDateGroup,
} from './assistantConversationUi';

type ChatTurn = { role: 'user' | 'assistant'; content: string; id?: number };

const GROUP_ORDER: ConversationDateGroup[] = ['today', 'yesterday', 'last7', 'older'];

function AssistantMessageBody({ content }: { content: string }) {
  const blocks = splitAssistantContentBlocks(content);
  if (!blocks.length) return null;
  return (
    <div className="space-y-2.5">
      {blocks.map((block, idx) => {
        if (block.type === 'list') {
          return (
            <ul key={idx} className="list-disc space-y-1 pl-4 marker:text-surface-800/40">
              {block.items.map((item, j) => (
                <li key={j} className="leading-relaxed">
                  {item}
                </li>
              ))}
            </ul>
          );
        }
        return (
          <p key={idx} className="whitespace-pre-wrap leading-relaxed">
            {block.text}
          </p>
        );
      })}
    </div>
  );
}

function TypingDots() {
  return (
    <span className="inline-flex items-center gap-1" aria-hidden="true">
      <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-surface-800/35 [animation-delay:0ms]" />
      <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-surface-800/35 [animation-delay:150ms]" />
      <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-surface-800/35 [animation-delay:300ms]" />
    </span>
  );
}

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
  const sendLockRef = useRef(false);

  const preferredSuggestions = useMemo(
    () => [t.emptySuggestion1, t.emptySuggestion2, t.emptySuggestion3, t.emptySuggestion4],
    [t.emptySuggestion1, t.emptySuggestion2, t.emptySuggestion3, t.emptySuggestion4],
  );

  const relativeLabels = useMemo(
    () => ({
      justNow: t.relativeJustNow,
      minutes: t.relativeMinutes,
      hours: t.relativeHours,
      days: t.relativeDays,
    }),
    [t.relativeDays, t.relativeHours, t.relativeJustNow, t.relativeMinutes],
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

  useEffect(() => {
    const el = composerRef.current;
    if (!el) return;
    el.style.height = '0px';
    el.style.height = `${Math.min(Math.max(el.scrollHeight, 52), 160)}px`;
  }, [input]);

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
    if (sending || sendLockRef.current) return;
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
    if (conversationId == null) return null;
    const found = conversations.find((c) => c.id === conversationId);
    return titlePreview(found?.title, t.untitled);
  }, [conversationId, conversations, t.untitled]);

  const activityLabel = useMemo(() => {
    if (!sending) return null;
    if (streaming && !toolStatus) return t.toolPreparing;
    if (toolStatus) return toolStatus;
    if (streaming) return t.toolPreparing;
    return t.toolWorking;
  }, [sending, streaming, t.toolPreparing, t.toolWorking, toolStatus]);

  const sendMessage = useCallback(
    async (rawText: string) => {
      const text = rawText.trim();
      if (!text || sending || historyLoading || sendLockRef.current) return;
      sendLockRef.current = true;
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
          setChatError(t.createFailed);
          sendLockRef.current = false;
          return;
        }
      }

      setTurns((prev) => [...prev, { role: 'user', content: text }, { role: 'assistant', content: '' }]);
      setSending(true);
      setStreaming(false);
      setToolStatus(t.toolWorking);

      let sawDelta = false;
      let accumulated = '';
      try {
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
            if (isSnakeToolName(status)) {
              setToolStatus(t.toolWorking);
              return;
            }
            const lowered = status.toLowerCase();
            if (lowered.includes('hazır') || lowered.includes('prepar')) {
              setToolStatus(t.toolPreparing);
            } else if (lowered.includes('kontrol') || lowered.includes('verif') || lowered.includes('check')) {
              setToolStatus(t.toolChecking);
            } else {
              setToolStatus(t.toolWorking);
            }
          },
        );
        if (!sawDelta && !accumulated.trim()) {
          setChatError(t.streamInterrupted);
          setTurns((prev) => {
            if (prev.length && prev[prev.length - 1].role === 'assistant' && !prev[prev.length - 1].content) {
              return prev.slice(0, -1);
            }
            return prev;
          });
        }
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
        setChatError(sawDelta ? t.streamInterrupted : t.sendFailed);
      } finally {
        setSending(false);
        setStreaming(false);
        setToolStatus(null);
        sendLockRef.current = false;
        requestAnimationFrame(() => composerRef.current?.focus());
      }
    },
    [
      conversationId,
      historyLoading,
      locale,
      sending,
      t.createFailed,
      t.sendFailed,
      t.streamInterrupted,
      t.toolChecking,
      t.toolPreparing,
      t.toolWorking,
    ],
  );

  const archiveConversation = useCallback(
    async (id: number) => {
      if (sending || sendLockRef.current) return;
      try {
        await api.archiveAssistantConversation(id);
        setConversations((prev) => prev.filter((c) => c.id !== id));
        if (conversationId === id) startDraft();
      } catch {
        setChatError(t.archiveFailed);
      }
    },
    [conversationId, sending, startDraft, t.archiveFailed],
  );

  if (available === null) {
    return (
      <div className="flex h-full min-h-[320px] items-center justify-center text-sm text-surface-800/50">
        <Loader2 size={18} className="mr-2 animate-spin" aria-hidden="true" />
        {app.common.loading}
      </div>
    );
  }

  if (available === false) {
    return (
      <div className="card flex h-full min-h-[280px] flex-col items-center justify-center gap-2 p-8 text-center">
        <MessageSquareText className="text-surface-800/35" size={28} aria-hidden="true" />
        <p className="text-sm font-medium text-surface-900">{t.unavailableTitle}</p>
        <p className="max-w-sm text-sm text-surface-800/55">{t.unavailableBody}</p>
      </div>
    );
  }

  const showEmptyWorkspace = conversationId == null && turns.length === 0 && !historyLoading;
  const showComposerChips = turns.length === 0 && !historyLoading && !showEmptyWorkspace;

  const sidebar = (
    <aside
      className="flex h-full w-full flex-col border-r border-surface-200 bg-surface-50/40 lg:w-[300px] lg:shrink-0 lg:bg-white"
      aria-label={t.pastChats}
    >
      <div className="flex items-center gap-2 border-b border-surface-100 p-3">
        <button
          type="button"
          onClick={startDraft}
          disabled={sending}
          className="btn-primary min-h-[40px] flex-1 justify-center text-sm focus-visible:ring-2 focus-visible:ring-brand-500"
          aria-label={t.newChat}
        >
          <Plus size={16} aria-hidden="true" />
          {t.newChat}
        </button>
        <button
          type="button"
          className="rounded-lg p-2 text-surface-800/50 hover:bg-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 lg:hidden"
          onClick={() => setSidebarOpen(false)}
          aria-label={t.closeSidebar}
        >
          <PanelLeftClose size={18} aria-hidden="true" />
        </button>
      </div>

      <div className="border-b border-surface-100 px-3 py-2.5">
        <label className="sr-only" htmlFor="assistant-search">
          {t.searchChats}
        </label>
        <div className="relative">
          <Search
            size={14}
            className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-surface-800/40"
            aria-hidden="true"
          />
          <input
            id="assistant-search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder={t.searchChats}
            className="input-field py-2 pl-8 text-sm focus-visible:ring-2 focus-visible:ring-brand-500/30"
          />
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-2 py-2">
        {listLoading ? (
          <div className="flex items-center gap-2 px-2 py-3 text-sm text-surface-800/50">
            <Loader2 size={14} className="animate-spin" aria-hidden="true" />
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
              <p className="px-2.5 pb-1.5 text-[11px] font-semibold uppercase tracking-wide text-surface-800/40">
                {groupLabel(g)}
              </p>
              <ul className="space-y-0.5">
                {items.map((c) => {
                  const active = c.id === conversationId;
                  const when = formatRelativeConversationTime(c.updated_at, relativeLabels);
                  return (
                    <li key={c.id} className="group relative">
                      <button
                        type="button"
                        disabled={sending || historyLoading}
                        onClick={() => void loadConversation(c.id)}
                        className={
                          active
                            ? 'w-full rounded-lg bg-brand-500/10 px-2.5 py-2.5 pr-9 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500'
                            : 'w-full rounded-lg px-2.5 py-2.5 pr-9 text-left hover:bg-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 lg:hover:bg-surface-50'
                        }
                        aria-current={active ? 'true' : undefined}
                      >
                        <span
                          className={
                            active
                              ? 'line-clamp-2 text-sm font-medium text-brand-800'
                              : 'line-clamp-2 text-sm text-surface-800/85'
                          }
                        >
                          {titlePreview(c.title, t.untitled)}
                        </span>
                        {when ? (
                          <span className="mt-0.5 block text-[11px] text-surface-800/40">{when}</span>
                        ) : null}
                      </button>
                      <button
                        type="button"
                        disabled={sending}
                        onClick={(e) => {
                          e.stopPropagation();
                          void archiveConversation(c.id);
                        }}
                        className="absolute right-1.5 top-1/2 -translate-y-1/2 rounded-md p-1.5 text-surface-800/0 opacity-0 transition hover:bg-rose-50 hover:text-rose-600 focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 group-hover:text-surface-800/45 group-hover:opacity-100 group-focus-within:opacity-100"
                        aria-label={t.archiveChat}
                        title={t.archiveChat}
                      >
                        <Archive size={14} aria-hidden="true" />
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
      <div className="hidden h-full lg:flex">{sidebar}</div>

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

      <section className="flex min-w-0 flex-1 flex-col" aria-label={t.pageTitle}>
        <header className="flex items-start gap-2 border-b border-surface-100 px-3 py-3 sm:px-5">
          <button
            type="button"
            className="mt-0.5 rounded-lg p-2 text-surface-800/60 hover:bg-surface-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 lg:hidden"
            onClick={() => setSidebarOpen(true)}
            aria-label={t.openSidebar}
          >
            <Menu size={18} aria-hidden="true" />
          </button>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-1.5">
              <Sparkles size={16} className="shrink-0 text-brand-600" aria-hidden="true" />
              <h1 className="truncate text-base font-semibold text-surface-900 sm:text-lg">{t.pageTitle}</h1>
            </div>
            <p className="mt-0.5 max-w-2xl text-[12px] leading-snug text-surface-800/55 sm:text-[13px]">
              {t.pageSubtitle}
            </p>
            {activeTitle ? (
              <p className="mt-1 truncate text-[11px] text-surface-800/40">{activeTitle}</p>
            ) : null}
          </div>
          {conversationId != null ? (
            <button
              type="button"
              onClick={() => void archiveConversation(conversationId)}
              disabled={sending}
              className="mt-0.5 rounded-lg p-2 text-surface-800/45 hover:bg-surface-50 hover:text-rose-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 disabled:opacity-40"
              aria-label={t.archiveChat}
              title={t.archiveChat}
            >
              <Archive size={16} aria-hidden="true" />
            </button>
          ) : null}
        </header>

        <div ref={scrollRef} className="min-h-0 flex-1 overflow-x-hidden overflow-y-auto px-3 py-4 sm:px-6">
          <div className="mx-auto flex w-full max-w-3xl flex-col gap-3.5">
            {historyLoading ? (
              <div className="flex items-center gap-2 text-sm text-surface-800/50">
                <Loader2 size={16} className="animate-spin" aria-hidden="true" />
                {t.loadingHistory}
              </div>
            ) : null}

            {historyError ? (
              <div className="space-y-2 rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700" role="alert">
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
              <div className="flex flex-col items-center px-1 py-10 text-center sm:py-16">
                <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-brand-50 text-brand-700">
                  <MessageSquareText size={22} aria-hidden="true" />
                </div>
                <h2 className="text-xl font-semibold tracking-tight text-surface-900 sm:text-2xl">
                  {t.welcomeTitle}
                </h2>
                <p className="mt-2 max-w-md text-sm leading-relaxed text-surface-800/60">{t.welcomeBody}</p>
                <div className="mt-7 flex w-full max-w-xl flex-wrap justify-center gap-2">
                  {preferredSuggestions.map((s) => (
                    <button
                      key={s}
                      type="button"
                      disabled={sending}
                      onClick={() => void sendMessage(s)}
                      className="max-w-full rounded-full border border-surface-200 bg-white px-3.5 py-2 text-left text-sm text-surface-800/80 shadow-sm transition hover:border-brand-300 hover:bg-brand-50/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 sm:text-center"
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            ) : null}

            {!showEmptyWorkspace
              ? turns.map((turn, idx) => {
                  const isLast = idx === turns.length - 1;
                  const isEmptyAssistant = turn.role === 'assistant' && !turn.content.trim();
                  if (isEmptyAssistant && sending && isLast) {
                    return (
                      <div
                        key={turn.id ?? `${idx}-typing`}
                        className="mr-auto flex max-w-[min(100%,42rem)] items-center gap-2.5 rounded-2xl bg-surface-50 px-3.5 py-3 text-sm text-surface-800/55 ring-1 ring-surface-100"
                        aria-live="polite"
                      >
                        <TypingDots />
                        <span>{activityLabel || t.thinking}</span>
                      </div>
                    );
                  }
                  if (isEmptyAssistant) return null;
                  if (turn.role === 'user') {
                    return (
                      <div
                        key={turn.id ?? `${idx}-user`}
                        className="ml-auto max-w-[min(92%,36rem)] break-words rounded-2xl bg-brand-600 px-3.5 py-2.5 text-sm leading-relaxed text-white shadow-sm"
                      >
                        <p className="whitespace-pre-wrap">{turn.content}</p>
                      </div>
                    );
                  }
                  return (
                    <div
                      key={turn.id ?? `${idx}-assistant`}
                      className="mr-auto max-w-[min(100%,42rem)] break-words rounded-2xl bg-surface-50 px-3.5 py-3 text-sm text-surface-800/95 ring-1 ring-surface-100"
                      aria-live={isLast && streaming ? 'polite' : undefined}
                    >
                      <AssistantMessageBody content={turn.content} />
                      {isLast && streaming ? (
                        <span className="ml-0.5 inline-block h-3.5 w-0.5 animate-pulse bg-brand-500 align-middle" />
                      ) : null}
                    </div>
                  );
                })
              : null}

            {sending && streaming && activityLabel ? (
              <div className="flex items-center gap-2 text-xs text-surface-800/45" aria-live="polite">
                <Loader2 size={13} className="animate-spin" aria-hidden="true" />
                {activityLabel}
              </div>
            ) : null}

            {chatError ? (
              <div className="space-y-2 rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700" role="alert">
                <p>{chatError}</p>
                <button type="button" className="btn-secondary text-xs" onClick={() => setChatError(null)}>
                  {t.retry}
                </button>
              </div>
            ) : null}
          </div>
        </div>

        <div className="sticky bottom-0 border-t border-surface-100 bg-white/95 px-3 py-3 backdrop-blur-sm sm:px-6">
          <div className="mx-auto w-full max-w-3xl">
            {showComposerChips ? (
              <div className="-mx-1 mb-2.5 flex gap-2 overflow-x-auto px-1 pb-0.5 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
                {preferredSuggestions.map((s) => (
                  <button
                    key={s}
                    type="button"
                    disabled={sending || historyLoading}
                    onClick={() => void sendMessage(s)}
                    className="shrink-0 rounded-full border border-surface-200 bg-surface-50 px-3 py-1.5 text-xs text-surface-800/70 transition hover:border-brand-300 hover:bg-brand-50/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 disabled:opacity-50"
                  >
                    {s}
                  </button>
                ))}
              </div>
            ) : null}

            <div className="flex items-end gap-2 rounded-2xl border border-surface-200 bg-white p-2 shadow-sm focus-within:border-brand-400 focus-within:ring-2 focus-within:ring-brand-500/15">
              <label className="sr-only" htmlFor="assistant-composer">
                {t.composerLabel}
              </label>
              <textarea
                id="assistant-composer"
                ref={composerRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                rows={1}
                disabled={sending || historyLoading}
                placeholder={t.composerPlaceholder}
                className="max-h-40 min-h-[52px] flex-1 resize-none border-0 bg-transparent px-2.5 py-3 text-sm leading-relaxed text-surface-900 outline-none placeholder:text-surface-800/40 disabled:opacity-60"
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
                className="btn-primary mb-0.5 h-11 w-11 shrink-0 justify-center rounded-xl px-0 focus-visible:ring-2 focus-visible:ring-brand-500"
                aria-label={t.send}
              >
                {sending ? (
                  <Loader2 size={18} className="animate-spin" aria-hidden="true" />
                ) : (
                  <Send size={18} aria-hidden="true" />
                )}
              </button>
            </div>
            <p className="mt-2 text-[10px] leading-snug text-surface-800/40">{t.disclaimer}</p>
          </div>
        </div>
      </section>
    </div>
  );
}
