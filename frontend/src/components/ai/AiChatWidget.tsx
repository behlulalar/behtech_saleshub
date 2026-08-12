import { useCallback, useEffect, useRef, useState } from 'react';
import { Loader2, MessageCircle, Plus, Send, Sparkles, X } from 'lucide-react';
import { api } from '../../api';
import { useLocale } from '../../i18n/locale';
import type { AiStatusResponse, AssistantConversation } from '../../types';

type ChatTurn = { role: 'user' | 'assistant'; content: string; id?: number };

export default function AiChatWidget() {
  const { app, locale } = useLocale();
  const t = app.chat;
  const [open, setOpen] = useState(false);
  const [available, setAvailable] = useState(false);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const [bootLoading, setBootLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [conversationId, setConversationId] = useState<number | null>(null);
  const [conversations, setConversations] = useState<AssistantConversation[]>([]);
  const [toolStatus, setToolStatus] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const bootRef = useRef(false);

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

  useEffect(() => {
    if (open && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [turns, open, loading, streaming, toolStatus]);

  const loadConversation = useCallback(
    async (id: number) => {
      const detail = await api.getAssistantConversation(id);
      setConversationId(detail.conversation.id);
      setTurns(
        detail.messages.map((m) => ({
          id: m.id,
          role: m.role === 'assistant' ? 'assistant' : 'user',
          content: m.content,
        })),
      );
    },
    [],
  );

  const bootstrap = useCallback(async () => {
    setBootLoading(true);
    setError(null);
    try {
      const list = await api.listAssistantConversations();
      setConversations(list.items);
      if (list.items.length > 0) {
        await loadConversation(list.items[0].id);
      } else {
        const created = await api.createAssistantConversation();
        setConversations([created]);
        setConversationId(created.id);
        setTurns([]);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : t.loadFailed);
    } finally {
      setBootLoading(false);
    }
  }, [loadConversation, t.loadFailed]);

  useEffect(() => {
    if (!open || !available) return;
    if (bootRef.current) return;
    bootRef.current = true;
    void bootstrap();
  }, [open, available, bootstrap]);

  const startNewConversation = useCallback(async () => {
    if (loading) return;
    setError(null);
    setBootLoading(true);
    try {
      const created = await api.createAssistantConversation();
      setConversations((prev) => [created, ...prev]);
      setConversationId(created.id);
      setTurns([]);
    } catch (err) {
      setError(err instanceof Error ? err.message : t.loadFailed);
    } finally {
      setBootLoading(false);
    }
  }, [loading, t.loadFailed]);

  const send = useCallback(async () => {
    const text = input.trim();
    if (!text || loading || bootLoading) return;
    setInput('');
    setError(null);

    let activeId = conversationId;
    if (activeId == null) {
      try {
        const created = await api.createAssistantConversation();
        activeId = created.id;
        setConversationId(created.id);
        setConversations((prev) => [created, ...prev]);
      } catch (err) {
        setError(err instanceof Error ? err.message : t.sendFailed);
        return;
      }
    }

    const userTurn: ChatTurn = { role: 'user', content: text };
    setTurns((prev) => [...prev, userTurn, { role: 'assistant', content: '' }]);
    setLoading(true);
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
          const snapshot = accumulated;
          setTurns((prev) => {
            const copy = [...prev];
            copy[copy.length - 1] = { role: 'assistant', content: snapshot };
            return copy;
          });
        },
        (status) => setToolStatus(status),
      );
      // Refresh title / ordering from server (non-blocking).
      void api.listAssistantConversations().then((list) => setConversations(list.items)).catch(() => {});
    } catch (err) {
      setTurns((prev) => {
        if (prev.length && prev[prev.length - 1].role === 'assistant' && !prev[prev.length - 1].content) {
          return prev.slice(0, -1);
        }
        return prev;
      });
      setError(err instanceof Error ? err.message : t.sendFailed);
    } finally {
      setLoading(false);
      setStreaming(false);
      setToolStatus(null);
    }
  }, [bootLoading, conversationId, input, loading, locale, t.sendFailed]);

  if (!available) return null;

  return (
    <>
      {!open ? (
        <button
          type="button"
          onClick={() => setOpen(true)}
          className="fixed bottom-4 right-4 z-40 flex h-14 w-14 items-center justify-center rounded-full text-white shadow-lg transition hover:scale-105 active:scale-95 sm:bottom-6 sm:right-6"
          style={{
            backgroundImage: 'linear-gradient(90deg, #000000 0%, #3432c7 100%)',
          }}
          aria-label={t.open}
        >
          <MessageCircle size={24} />
        </button>
      ) : null}

      {open ? (
        <div
          className="fixed inset-0 z-50 flex items-end justify-end bg-black/30 p-0 sm:items-center sm:p-4"
          role="presentation"
          onClick={() => setOpen(false)}
        >
          <div
            className="flex h-[min(85dvh,640px)] w-full flex-col overflow-hidden rounded-t-2xl border border-surface-200 bg-white shadow-xl sm:h-[min(70vh,620px)] sm:max-w-md sm:rounded-2xl"
            role="dialog"
            aria-label={t.title}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between gap-2 border-b border-surface-100 bg-brand-50/40 px-4 py-3">
              <div className="flex items-center gap-2">
                <Sparkles size={18} className="text-brand-600" />
                <div>
                  <p className="text-sm font-semibold text-surface-900">{t.title}</p>
                  <p className="text-[11px] text-surface-800/55">{t.subtitle}</p>
                </div>
              </div>
              <div className="flex items-center gap-1">
                <button
                  type="button"
                  onClick={() => void startNewConversation()}
                  disabled={loading || bootLoading}
                  className="rounded-lg p-2 text-surface-800/50 hover:bg-white disabled:opacity-40"
                  aria-label={t.newChat}
                  title={t.newChat}
                >
                  <Plus size={18} />
                </button>
                <button
                  type="button"
                  onClick={() => setOpen(false)}
                  className="rounded-lg p-2 text-surface-800/50 hover:bg-white"
                  aria-label={t.close}
                >
                  <X size={18} />
                </button>
              </div>
            </div>

            {conversations.length > 1 ? (
              <div className="flex gap-1 overflow-x-auto border-b border-surface-100 px-3 py-2">
                {conversations.slice(0, 8).map((c) => (
                  <button
                    key={c.id}
                    type="button"
                    disabled={loading || bootLoading}
                    onClick={() => {
                      void loadConversation(c.id).catch((err) => {
                        setError(err instanceof Error ? err.message : t.loadFailed);
                      });
                    }}
                    className={
                      c.id === conversationId
                        ? 'shrink-0 rounded-lg bg-brand-500/10 px-2.5 py-1 text-[11px] font-medium text-brand-700'
                        : 'shrink-0 rounded-lg px-2.5 py-1 text-[11px] text-surface-800/60 hover:bg-surface-50'
                    }
                  >
                    {(c.title || t.untitled).slice(0, 28)}
                  </button>
                ))}
              </div>
            ) : null}

            <div ref={scrollRef} className="min-h-0 flex-1 space-y-3 overflow-y-auto px-4 py-3">
              {bootLoading && turns.length === 0 ? (
                <div className="flex items-center gap-2 text-sm text-surface-800/50">
                  <Loader2 size={16} className="animate-spin" />
                  {t.loadingHistory}
                </div>
              ) : null}
              {!bootLoading && turns.length === 0 ? (
                <p className="text-sm leading-relaxed text-surface-800/55">{t.emptyHint}</p>
              ) : null}
              {turns.map((turn, idx) => {
                if (turn.role === 'assistant' && !turn.content.trim() && loading) {
                  return null;
                }
                return (
                  <div
                    key={turn.id ?? `${idx}-${turn.role}`}
                    className={
                      turn.role === 'user'
                        ? 'ml-8 rounded-xl bg-brand-500/10 px-3 py-2 text-sm text-surface-900'
                        : 'mr-4 rounded-xl bg-surface-50 px-3 py-2 text-sm leading-relaxed text-surface-800/90 ring-1 ring-surface-100'
                    }
                  >
                    {turn.content}
                  </div>
                );
              })}
              {loading && !streaming ? (
                <div className="flex items-center gap-2 text-sm text-surface-800/50">
                  <Loader2 size={16} className="animate-spin" />
                  {toolStatus || t.thinking}
                </div>
              ) : null}
              {loading && streaming && toolStatus ? (
                <div className="flex items-center gap-2 text-sm text-surface-800/50">
                  <Loader2 size={16} className="animate-spin" />
                  {toolStatus}
                </div>
              ) : null}
              {error ? <p className="text-sm text-rose-600">{error}</p> : null}
            </div>

            <div className="border-t border-surface-100 p-3">
              <div className="flex gap-2">
                <textarea
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  rows={2}
                  placeholder={t.placeholder}
                  className="input-field min-h-[44px] flex-1 resize-none text-sm"
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault();
                      void send();
                    }
                  }}
                />
                <button
                  type="button"
                  disabled={loading || bootLoading || !input.trim()}
                  onClick={() => void send()}
                  className="btn-primary shrink-0 self-end px-3 py-2.5"
                  aria-label={t.send}
                >
                  {loading ? <Loader2 size={18} className="animate-spin" /> : <Send size={18} />}
                </button>
              </div>
              <p className="mt-2 text-[10px] text-surface-800/45">{t.disclaimer}</p>
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}
