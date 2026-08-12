import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Bot, ChevronLeft, Loader2, MessageSquarePlus, PanelLeft, Send, Sparkles } from 'lucide-react';
import { api } from '../../api';
import { useLocale } from '../../i18n/locale';

type Message = { role: 'user' | 'assistant'; content: string };
type Conversation = {
  id: string;
  title: string;
  messages: Message[];
  createdAt: string;
  updatedAt: string;
};

const STORAGE_KEY = 'behtech-sales-assistant-conversations-v1';
const MAX_CONVERSATIONS = 30;

function makeId() {
  return `c_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

function makeTitle(text: string) {
  const clean = text.trim().replace(/\s+/g, ' ');
  return clean.length > 42 ? `${clean.slice(0, 42)}…` : clean || 'Yeni sohbet';
}

function loadConversations(): Conversation[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((item) => item && typeof item.id === 'string' && Array.isArray(item.messages));
  } catch {
    return [];
  }
}

function persist(conversations: Conversation[]) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(conversations.slice(0, MAX_CONVERSATIONS)));
  } catch {
    // Storage is an enhancement; the active conversation must keep working.
  }
}

export default function SalesAssistantPage() {
  const { locale } = useLocale();
  const isEnglish = locale === 'en';
  const [conversations, setConversations] = useState<Conversation[]>(loadConversations);
  const [activeId, setActiveId] = useState<string | null>(() => loadConversations()[0]?.id ?? null);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  const active = useMemo(
    () => conversations.find((conversation) => conversation.id === activeId) ?? null,
    [activeId, conversations],
  );

  useEffect(() => {
    persist(conversations);
  }, [conversations]);

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [active?.messages.length, loading]);

  const createConversation = useCallback(() => {
    const now = new Date().toISOString();
    const conversation: Conversation = {
      id: makeId(),
      title: isEnglish ? 'New chat' : 'Yeni sohbet',
      messages: [],
      createdAt: now,
      updatedAt: now,
    };
    setConversations((prev) => [conversation, ...prev].slice(0, MAX_CONVERSATIONS));
    setActiveId(conversation.id);
    setInput('');
    setError(null);
  }, [isEnglish]);

  const ensureActiveConversation = useCallback(() => {
    if (activeId && conversations.some((conversation) => conversation.id === activeId)) return activeId;
    const now = new Date().toISOString();
    const conversation: Conversation = {
      id: makeId(),
      title: isEnglish ? 'New chat' : 'Yeni sohbet',
      messages: [],
      createdAt: now,
      updatedAt: now,
    };
    setConversations((prev) => [conversation, ...prev].slice(0, MAX_CONVERSATIONS));
    setActiveId(conversation.id);
    return conversation.id;
  }, [activeId, conversations, isEnglish]);

  const send = useCallback(async () => {
    const text = input.trim();
    if (!text || loading) return;
    const conversationId = ensureActiveConversation();
    const conversation = conversations.find((item) => item.id === conversationId);
    if (!conversation) return;

    const history = conversation.messages;
    const userMessage: Message = { role: 'user', content: text };
    const assistantMessage: Message = { role: 'assistant', content: '' };
    const now = new Date().toISOString();

    setInput('');
    setError(null);
    setLoading(true);
    setConversations((prev) =>
      prev.map((item) =>
        item.id === conversationId
          ? {
              ...item,
              title: item.messages.length === 0 ? makeTitle(text) : item.title,
              messages: [...item.messages, userMessage, assistantMessage],
              updatedAt: now,
            }
          : item,
      ),
    );

    try {
      let accumulated = '';
      await api.streamAiChat(
        {
          message: text,
          history: history.slice(-8),
          locale: isEnglish ? 'en' : 'tr',
        },
        (delta) => {
          accumulated += delta;
          const snapshot = accumulated;
          setConversations((prev) =>
            prev.map((item) => {
              if (item.id !== conversationId) return item;
              const messages = [...item.messages];
              messages[messages.length - 1] = { role: 'assistant', content: snapshot };
              return { ...item, messages, updatedAt: new Date().toISOString() };
            }),
          );
        },
      );
    } catch (err) {
      setConversations((prev) =>
        prev.map((item) => {
          if (item.id !== conversationId) return item;
          const messages = [...item.messages];
          if (messages[messages.length - 1]?.role === 'assistant' && !messages[messages.length - 1].content) {
            messages.pop();
          }
          return { ...item, messages };
        }),
      );
      setError(err instanceof Error ? err.message : (isEnglish ? 'Could not get a response.' : 'Yanıt alınamadı.'));
    } finally {
      setLoading(false);
    }
  }, [conversations, ensureActiveConversation, input, isEnglish, loading]);

  return (
    <div className="flex h-full min-h-0 overflow-hidden rounded-2xl border border-surface-200 bg-white shadow-sm">
      <aside
        className={`${sidebarOpen ? 'w-72' : 'w-0'} flex shrink-0 flex-col overflow-hidden border-r border-surface-200 bg-surface-50/70 transition-[width] duration-200`}
      >
        <div className="flex h-14 shrink-0 items-center justify-between border-b border-surface-200 px-3">
          <div className="flex items-center gap-2 font-semibold text-surface-900">
            <Sparkles size={17} className="text-brand-600" />
            {isEnglish ? 'Sales Assistant' : 'Satış Asistanı'}
          </div>
          <button
            type="button"
            onClick={createConversation}
            className="rounded-lg p-2 text-surface-700 hover:bg-white hover:text-brand-600"
            title={isEnglish ? 'New chat' : 'Yeni sohbet'}
          >
            <MessageSquarePlus size={18} />
          </button>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto p-2">
          {conversations.length === 0 ? (
            <div className="px-3 py-6 text-xs leading-relaxed text-surface-500">
              {isEnglish ? 'Your conversations will appear here.' : 'Sohbetlerin burada görünecek.'}
            </div>
          ) : (
            <div className="space-y-1">
              {conversations.map((conversation) => (
                <button
                  key={conversation.id}
                  type="button"
                  onClick={() => {
                    setActiveId(conversation.id);
                    setError(null);
                  }}
                  className={`flex w-full items-start gap-2 rounded-xl px-3 py-2.5 text-left text-sm transition ${
                    conversation.id === activeId
                      ? 'bg-white text-surface-900 shadow-sm ring-1 ring-surface-200'
                      : 'text-surface-700 hover:bg-white/80'
                  }`}
                >
                  <MessageSquarePlus size={15} className="mt-0.5 shrink-0 opacity-50" />
                  <span className="min-w-0 flex-1 truncate">{conversation.title}</span>
                </button>
              ))}
            </div>
          )}
        </div>
      </aside>

      <section className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 shrink-0 items-center gap-2 border-b border-surface-200 px-3 sm:px-5">
          <button
            type="button"
            onClick={() => setSidebarOpen((open) => !open)}
            className="rounded-lg p-2 text-surface-600 hover:bg-surface-100"
            title={isEnglish ? 'Toggle conversations' : 'Sohbetleri göster/gizle'}
          >
            {sidebarOpen ? <ChevronLeft size={18} /> : <PanelLeft size={18} />}
          </button>
          <div className="min-w-0">
            <h2 className="truncate text-sm font-semibold text-surface-900 sm:text-base">
              {active?.title || (isEnglish ? 'Sales Assistant' : 'Satış Asistanı')}
            </h2>
            <p className="text-[11px] text-surface-500">
              {isEnglish ? 'Read-only CRM intelligence' : 'CRM verileri üzerinden read-only satış zekâsı'}
            </p>
          </div>
          <button
            type="button"
            onClick={createConversation}
            className="btn-secondary ml-auto px-2.5 py-2 text-xs"
          >
            <MessageSquarePlus size={15} />
            <span className="hidden sm:inline">{isEnglish ? 'New chat' : 'Yeni sohbet'}</span>
          </button>
        </header>

        <div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto px-3 py-5 sm:px-8 lg:px-16">
          <div className="mx-auto flex min-h-full max-w-3xl flex-col justify-end">
            {!active || active.messages.length === 0 ? (
              <div className="mx-auto w-full max-w-2xl py-10 text-center sm:py-16">
                <div className="mx-auto mb-5 flex h-14 w-14 items-center justify-center rounded-2xl bg-brand-50 text-brand-600">
                  <Bot size={28} />
                </div>
                <h3 className="text-2xl font-bold tracking-tight text-surface-900">
                  {isEnglish ? 'What do you want to know?' : 'Bugün neyi öğrenmek istiyorsun?'}
                </h3>
                <p className="mx-auto mt-2 max-w-xl text-sm leading-relaxed text-surface-500">
                  {isEnglish
                    ? 'Ask about leads, offers, activities, sales and diagnosis data. Answers are grounded in your CRM.'
                    : 'Lead, teklif, aktivite, satış ve diagnosis verilerini sor. Cevaplar doğrudan CRM kayıtlarına dayanır.'}
                </p>
                <div className="mt-6 grid gap-2 text-left sm:grid-cols-2">
                  {(isEnglish
                    ? ['What did we offer Roof Tattoo Sakarya?', 'Which leads need follow-up?', 'What happened this month?', 'Why are sales slowing down?']
                    : ['Roof Tattoo Sakarya\'ya ne teklif vermiştik?', 'Hangi lead\'leri takip etmeliyiz?', 'Bu ay satışlarda ne oldu?', 'Satışlar neden yavaşlıyor?']
                  ).map((prompt) => (
                    <button
                      key={prompt}
                      type="button"
                      onClick={() => setInput(prompt)}
                      className="rounded-xl border border-surface-200 bg-white px-4 py-3 text-left text-sm text-surface-700 transition hover:border-brand-300 hover:bg-brand-50/30"
                    >
                      {prompt}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              <div className="space-y-5 pb-6">
                {active.messages.map((message, index) => (
                  <div key={`${active.id}-${index}`} className={message.role === 'user' ? 'flex justify-end' : 'flex justify-start'}>
                    <div
                      className={
                        message.role === 'user'
                          ? 'max-w-[85%] rounded-2xl rounded-br-md bg-brand-600 px-4 py-3 text-sm leading-relaxed text-white shadow-sm'
                          : 'max-w-[92%] rounded-2xl rounded-bl-md bg-surface-50 px-4 py-3 text-sm leading-7 text-surface-800 ring-1 ring-surface-100'
                      }
                    >
                      {message.content || (loading && index === active.messages.length - 1 ? <Loader2 size={16} className="animate-spin" /> : null)}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="border-t border-surface-200 bg-white px-3 py-3 sm:px-8 sm:py-4 lg:px-16">
          <div className="mx-auto max-w-3xl">
            {error ? <p className="mb-2 text-xs text-rose-600">{error}</p> : null}
            <div className="flex items-end gap-2 rounded-2xl border border-surface-300 bg-white p-2 shadow-sm focus-within:border-brand-400 focus-within:ring-2 focus-within:ring-brand-100">
              <textarea
                value={input}
                onChange={(event) => setInput(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' && !event.shiftKey) {
                    event.preventDefault();
                    send();
                  }
                }}
                rows={1}
                placeholder={isEnglish ? 'Ask about your CRM…' : 'CRM hakkında bir şey sor…'}
                className="min-h-[42px] max-h-32 flex-1 resize-none border-0 bg-transparent px-2 py-2 text-sm outline-none placeholder:text-surface-400"
              />
              <button
                type="button"
                onClick={send}
                disabled={loading || !input.trim()}
                className="btn-primary h-10 w-10 shrink-0 rounded-xl p-0"
                aria-label={isEnglish ? 'Send' : 'Gönder'}
              >
                {loading ? <Loader2 size={18} className="animate-spin" /> : <Send size={18} />}
              </button>
            </div>
            <p className="mt-2 text-center text-[10px] text-surface-400">
              {isEnglish ? 'AI answers are grounded in CRM data. Verify critical information.' : 'AI yanıtları CRM verilerine dayanır. Kritik bilgileri kayıt üzerinden doğrula.'}
            </p>
          </div>
        </div>
      </section>
    </div>
  );
}
