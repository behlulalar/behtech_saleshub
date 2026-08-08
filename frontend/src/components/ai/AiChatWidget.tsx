import { useCallback, useEffect, useRef, useState } from 'react';
import { Loader2, MessageCircle, Send, Sparkles, X } from 'lucide-react';
import { api } from '../../api';
import { useLocale } from '../../i18n/locale';
import type { AiStatusResponse } from '../../types';

type ChatTurn = { role: 'user' | 'assistant'; content: string };

export default function AiChatWidget() {
  const { app, locale } = useLocale();
  const t = app.chat;
  const [open, setOpen] = useState(false);
  const [available, setAvailable] = useState(false);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const scrollRef = useRef<HTMLDivElement>(null);

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
  }, [turns, open, loading, streaming]);

  const send = useCallback(async () => {
    const text = input.trim();
    if (!text || loading) return;
    setInput('');
    setError(null);
    const userTurn: ChatTurn = { role: 'user', content: text };
    setTurns((prev) => [...prev, userTurn, { role: 'assistant', content: '' }]);
    setLoading(true);
    setStreaming(false);
    let sawDelta = false;
    try {
      const history = turns.map((x) => ({ role: x.role, content: x.content }));
      let accumulated = '';
      await api.streamAiChat(
        {
          message: text,
          history,
          locale: locale === 'en' ? 'en' : 'tr',
        },
        (delta) => {
          if (!sawDelta) {
            sawDelta = true;
            setStreaming(true);
          }
          accumulated += delta;
          const snapshot = accumulated;
          setTurns((prev) => {
            const copy = [...prev];
            copy[copy.length - 1] = { role: 'assistant', content: snapshot };
            return copy;
          });
        },
      );
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
    }
  }, [input, loading, locale, t.sendFailed, turns]);

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
              <button
                type="button"
                onClick={() => setOpen(false)}
                className="rounded-lg p-2 text-surface-800/50 hover:bg-white"
                aria-label={t.close}
              >
                <X size={18} />
              </button>
            </div>

            <div ref={scrollRef} className="min-h-0 flex-1 space-y-3 overflow-y-auto px-4 py-3">
              {turns.length === 0 ? (
                <p className="text-sm leading-relaxed text-surface-800/55">{t.emptyHint}</p>
              ) : null}
              {turns.map((turn, idx) => {
                if (turn.role === 'assistant' && !turn.content.trim() && loading) {
                  return null;
                }
                return (
                <div
                  key={`${idx}-${turn.role}`}
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
                  {t.thinking}
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
                      send();
                    }
                  }}
                />
                <button
                  type="button"
                  disabled={loading || !input.trim()}
                  onClick={send}
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
