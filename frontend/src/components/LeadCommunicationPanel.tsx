import { useState } from 'react';
import {
  Check,
  Copy,
  ExternalLink,
  Instagram,
  Mail,
  MessageCircle,
  Phone,
} from 'lucide-react';
import type { Lead, UserRole } from '../types';
import { useLocale } from '../i18n/locale';
import {
  buildTemplateVars,
  getMessageTemplates,
  resolveSenderDisplayName,
} from '../messageTemplates';
import {
  fillMessageTemplate,
  toInstagramUrl,
  toMailtoUrl,
  toTelUrl,
  toWhatsAppUrl,
} from '../utils';
import type { MessageTemplateId } from '../messageTemplates';
import AiSuggestMessageButton from './ai/AiSuggestMessageButton';

interface Props {
  leadId: number;
  lead: Pick<Lead, 'isletme_adi' | 'yetkili' | 'sehir' | 'instagram' | 'whatsapp' | 'eposta'>;
  category: string;
  role: UserRole;
  senderDisplayName?: string;
  senderUsername?: string;
}

export default function LeadCommunicationPanel({
  leadId,
  lead,
  category,
  role,
  senderDisplayName,
  senderUsername,
}: Props) {
  const { app } = useLocale();
  const c = app.communication;
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [aiDrafts, setAiDrafts] = useState<Partial<Record<MessageTemplateId, string>>>({});

  const instagramUrl = lead.instagram ? toInstagramUrl(lead.instagram) : null;
  const phone = lead.whatsapp?.trim() || '';
  const telUrl = phone ? toTelUrl(phone) : null;
  const whatsAppUrl = phone ? toWhatsAppUrl(phone) : null;
  const email = lead.eposta?.trim() || '';

  const resolvedSenderName = resolveSenderDisplayName(senderDisplayName, senderUsername);
  const templateVars = buildTemplateVars({
    yetkili: lead.yetkili,
    isletme_adi: lead.isletme_adi,
    sehir: lead.sehir,
    senderDisplayName: resolvedSenderName,
  });

  const { templates, regionLabel } = getMessageTemplates({
    category,
    role,
    sehir: lead.sehir,
    senderDisplayName: resolvedSenderName,
    labels: {
      intro: c.templateIntro,
      followUp: c.templateFollowUp,
      demo: c.templateDemo,
      meeting: c.templateMeeting,
    },
    fallbackBodies: {
      intro: c.templateIntroBody,
      followUp: c.templateFollowUpBody,
      demo: c.templateDemoBody,
      meeting: c.templateMeetingBody,
    },
  });

  const handleCopy = async (id: string, text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedId(id);
      window.setTimeout(() => setCopiedId((current) => (current === id ? null : current)), 2000);
    } catch {
      /* ignore */
    }
  };

  const openExternal = (url: string) => {
    window.open(url, '_blank', 'noopener,noreferrer');
  };

  const actions = [
    {
      key: 'whatsapp',
      label: c.whatsapp,
      icon: MessageCircle,
      enabled: !!whatsAppUrl,
      onClick: () => whatsAppUrl && openExternal(whatsAppUrl),
      className: 'border-emerald-200 bg-emerald-50 text-emerald-800 hover:bg-emerald-100',
    },
    {
      key: 'call',
      label: c.call,
      icon: Phone,
      enabled: !!telUrl,
      onClick: () => telUrl && openExternal(telUrl),
      className: 'border-blue-200 bg-blue-50 text-blue-800 hover:bg-blue-100',
    },
    {
      key: 'instagram',
      label: c.instagram,
      icon: Instagram,
      enabled: !!instagramUrl,
      onClick: () => instagramUrl && openExternal(instagramUrl),
      className: 'border-pink-200 bg-pink-50 text-pink-800 hover:bg-pink-100',
    },
    {
      key: 'email',
      label: c.email,
      icon: Mail,
      enabled: true,
      onClick: () => {
        const subject = fillMessageTemplate(c.emailSubject, templateVars);
        openExternal(toMailtoUrl({ email, subject }));
      },
      className: 'border-amber-200 bg-amber-50 text-amber-900 hover:bg-amber-100',
    },
  ];

  const hasAnyChannel = actions.some((action) => action.enabled);

  return (
    <section className="rounded-xl border border-brand-100 bg-brand-50/30 p-4">
      <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-surface-900">
        <MessageCircle size={16} className="text-brand-500" />
        {c.title}
      </h3>

      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        {actions.map((action) => (
          <button
            key={action.key}
            type="button"
            disabled={!action.enabled}
            onClick={action.onClick}
            className={`flex items-center justify-center gap-2 rounded-lg border px-3 py-2.5 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-40 ${action.className}`}
          >
            <action.icon size={16} />
            {action.label}
          </button>
        ))}
      </div>

      {!hasAnyChannel && (
        <p className="mt-2 text-xs text-surface-800/50">{c.unavailable}</p>
      )}

      <div className="mt-4">
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <p className="text-xs font-semibold uppercase tracking-wide text-surface-800/50">
            {c.readyMessages}
          </p>
          {regionLabel ? (
            <span className="rounded-full bg-brand-100 px-2.5 py-0.5 text-[11px] font-semibold text-brand-800">
              {regionLabel}
            </span>
          ) : null}
        </div>
        <div className="space-y-4">
          {templates.map((template) => {
            const defaultMessage = fillMessageTemplate(template.body, templateVars);
            const aiMessage = aiDrafts[template.id];
            const defaultCopyId = `${template.id}-template`;
            const aiCopyId = `${template.id}-ai`;
            const waDefault = phone ? toWhatsAppUrl(phone, defaultMessage) : null;
            const waAi = aiMessage && phone ? toWhatsAppUrl(phone, aiMessage) : null;

            const renderBubbleActions = (
              copyId: string,
              text: string,
              waUrl: string | null,
            ) => (
              <div className="flex w-full flex-wrap gap-2 sm:w-auto sm:justify-end">
                <button
                  type="button"
                  onClick={() => handleCopy(copyId, text)}
                  className="btn-secondary min-h-[40px] flex-1 justify-center gap-2 px-3 py-2 text-sm sm:min-h-0 sm:flex-none sm:px-3 sm:py-2"
                >
                  {copiedId === copyId ? <Check size={16} /> : <Copy size={16} />}
                  {copiedId === copyId ? c.copied : c.copy}
                </button>
                {waUrl ? (
                  <button
                    type="button"
                    onClick={() => openExternal(waUrl)}
                    className="btn-secondary min-h-[40px] flex-1 justify-center gap-2 px-3 py-2 text-sm sm:min-h-0 sm:flex-none sm:px-3 sm:py-2"
                    title={c.openWhatsApp}
                  >
                    <ExternalLink size={16} />
                    {c.openWhatsApp}
                  </button>
                ) : null}
              </div>
            );

            return (
              <div
                key={template.id}
                className="rounded-xl border border-surface-200 bg-white p-4 sm:p-5"
              >
                <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <p className="text-sm font-medium text-surface-900 sm:text-base">{template.label}</p>
                  <AiSuggestMessageButton
                    leadId={leadId}
                    templateId={template.id}
                    onSuggested={(text) =>
                      setAiDrafts((prev) => ({ ...prev, [template.id]: text }))
                    }
                  />
                </div>

                <div className="space-y-3">
                  <div className="rounded-xl border border-surface-200 bg-surface-50/80 p-4 sm:p-4">
                    <div className="mb-3 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between sm:gap-3">
                      <p className="text-[11px] font-semibold uppercase tracking-wide text-surface-800/45">
                        {app.ai.templateDraftLabel}
                      </p>
                      {renderBubbleActions(defaultCopyId, defaultMessage, waDefault)}
                    </div>
                    <p className="whitespace-pre-wrap text-sm leading-relaxed text-surface-800/80">
                      {defaultMessage}
                    </p>
                  </div>

                  {aiMessage ? (
                    <div className="rounded-xl border border-brand-200 bg-brand-50/60 p-4 sm:p-4">
                      <div className="mb-3 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between sm:gap-3">
                        <p className="text-[11px] font-semibold uppercase tracking-wide text-brand-700">
                          {app.ai.aiDraftLabel}
                        </p>
                        {renderBubbleActions(aiCopyId, aiMessage, waAi)}
                      </div>
                      <p className="whitespace-pre-wrap text-sm leading-relaxed text-surface-900/85">
                        {aiMessage}
                      </p>
                    </div>
                  ) : null}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
