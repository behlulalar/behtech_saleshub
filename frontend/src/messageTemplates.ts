import type { UserRole } from './types';

export type MessageTemplateId = 'intro' | 'followUp' | 'demo' | 'meeting';

export interface MessageTemplateItem {
  id: MessageTemplateId;
  label: string;
  body: string;
}

export interface ResolvedMessageTemplates {
  templates: MessageTemplateItem[];
  regionLabel: string | null;
}

export interface MessageTemplateContext {
  category: string;
  role: UserRole;
  sehir: string;
  senderDisplayName: string;
  labels: {
    intro: string;
    followUp: string;
    demo: string;
    meeting: string;
  };
  fallbackBodies: {
    intro: string;
    followUp: string;
    demo: string;
    meeting: string;
  };
}

const OWNER_SAKARYA_INTRO =
  "{hitap}, selamlar! Ben BehTech'in kurucusu Behlül. Sakaryada Kuaför ve berberlere özel randevu & yönetim sistemi geliştiriyorum. Sistem tamamen size ait çalışıyor — müşterileriniz kendi markanız üzerinden randevu alıyor, KolayRandevu gibi platformlara bağımlılık yok. Sakarya'da kullanan müşterilerim de mevcut. Kısa bir tanıtım videosu gönderebilirim ya da uygun bir zamanda yüz yüze gösterebilirim.";

const OWNER_SAKARYA_FOLLOWUP =
  '{hitap}, merhaba! Geçen hafta yazmıştım, dönüş yapamadıysanız sorun değil. Sistemi yerinde göstermek için kısa bir ziyaret ayarlayabilir miyiz?';

const EMPLOYEE_SAKARYA_INTRO =
  'Merhaba! Ben BehTech ekibinden {personel_adi}. Kuaför ve berberlere özel randevu & yönetim sistemi geliştiriyoruz. Sistem tamamen size ait çalışıyor — müşterileriniz kendi markanız üzerinden randevu alıyor, KolayRandevu gibi platformlara bağımlılık yok. Sakarya\'da kullanan müşterilerimiz de mevcut. Kısa bir tanıtım videosu göndereyim mi, ya da uygun bir zamanda yüz yüze gösterebiliriz.';

const EMPLOYEE_SAKARYA_FOLLOWUP =
  'Merhaba! Geçen hafta BehTech ekibinden yazmıştık, dönüş yapamadıysanız sorun değil. Sistemi yerinde göstermek için kısa bir ziyaret ayarlayabilir miyiz?';

const OWNER_OUTSIDE_INTRO =
  "{salamlama}! Ben BehTech'in kurucusu Behlül. Kuaför ve berberlere özel randevu & yönetim sistemi geliştiriyorum. Sistem tamamen size ait çalışıyor — müşterileriniz kendi markanız üzerinden randevu alıyor, KolayRandevu.com gibi platformlara bağımlılık yok. Kısa bir tanıtım videosu hazırladım, izlemek ister misiniz?";

const OWNER_OUTSIDE_FOLLOWUP =
  'Merhaba! Geçen hafta yazmıştım, dönüş yapamadıysanız sorun değil. Tanıtım videosunu göndereyim mi, kısa bir bakış atmak yeterli olur.';

const EMPLOYEE_OUTSIDE_INTRO =
  'Merhaba! Ben BehTech ekibinden {personel_adi}. Kuaför ve berberlere özel randevu & yönetim sistemi geliştiriyoruz. Sistem tamamen size ait çalışıyor — müşterileriniz kendi markanız üzerinden randevu alıyor, Fresha gibi platformlara bağımlılık yok. Kısa bir tanıtım videosu hazırladık, izlemek ister misiniz?';

const EMPLOYEE_OUTSIDE_FOLLOWUP =
  'Merhaba! Geçen hafta BehTech ekibinden yazmıştık, dönüş yapamadıysanız sorun değil. Tanıtım videosunu göndereyim mi, kısa bir bakış atmak yeterli olur.';

const REGION_SAKARYA = '🏙️ SAKARYA İÇİ';
const REGION_OUTSIDE = '🌍 ŞEHİR DIŞI';

export function formatHitap(yetkili: string, isletmeAdi: string): string {
  const raw = yetkili.trim();
  if (!raw) {
    const fallback = isletmeAdi.trim();
    return fallback || 'Merhaba';
  }

  const withoutBey = raw.replace(/\s+bey$/i, '').trim();
  const firstName = (withoutBey.split(/\s+/)[0] || withoutBey).trim();
  if (!firstName) return 'Merhaba';

  const normalized =
    firstName.charAt(0).toLocaleUpperCase('tr-TR') +
    firstName.slice(1).toLocaleLowerCase('tr-TR');
  return `${normalized} bey`;
}

/** Kurucu şehir dışı mesajları: "İsmail Bey" */
export function formatHitapBey(yetkili: string, isletmeAdi: string): string {
  const hitap = formatHitap(yetkili, isletmeAdi);
  if (hitap === 'Merhaba') return '';
  return hitap.replace(/\sbey$/i, ' Bey');
}

export function formatOwnerOutsideSalamlama(yetkili: string, isletmeAdi: string): string {
  const hitapBey = formatHitapBey(yetkili, isletmeAdi);
  if (!hitapBey) return 'Merhaba';
  return `Merhaba ${hitapBey}`;
}

export function isSakaryaCity(sehir: string): boolean {
  return sehir.trim().toLocaleLowerCase('tr-TR').includes('sakarya');
}

export function resolveSenderDisplayName(displayName?: string | null, username?: string | null): string {
  const fromProfile = displayName?.trim();
  if (fromProfile) return fromProfile;

  const fromUsername = username?.trim();
  if (!fromUsername) return 'BehTech ekibi';

  return fromUsername.charAt(0).toLocaleUpperCase('tr-TR') + fromUsername.slice(1).toLocaleLowerCase('tr-TR');
}

export function buildTemplateVars(input: {
  yetkili: string;
  isletme_adi: string;
  sehir: string;
  senderDisplayName: string;
}) {
  return {
    yetkili: input.yetkili || input.isletme_adi,
    isletme_adi: input.isletme_adi,
    sehir: input.sehir,
    hitap: formatHitap(input.yetkili, input.isletme_adi),
    salamlama: formatOwnerOutsideSalamlama(input.yetkili, input.isletme_adi),
    personel_adi: input.senderDisplayName,
  };
}

export function getMessageTemplates(context: MessageTemplateContext): ResolvedMessageTemplates {
  const baseTemplates: MessageTemplateItem[] = [
    { id: 'intro', label: context.labels.intro, body: context.fallbackBodies.intro },
    { id: 'followUp', label: context.labels.followUp, body: context.fallbackBodies.followUp },
    { id: 'demo', label: context.labels.demo, body: context.fallbackBodies.demo },
    { id: 'meeting', label: context.labels.meeting, body: context.fallbackBodies.meeting },
  ];

  if (context.category !== 'berber') {
    return { templates: baseTemplates, regionLabel: null };
  }

  const demoMeeting = [
    { id: 'demo' as const, label: context.labels.demo, body: context.fallbackBodies.demo },
    { id: 'meeting' as const, label: context.labels.meeting, body: context.fallbackBodies.meeting },
  ];

  if (isSakaryaCity(context.sehir)) {
    if (context.role === 'owner') {
      return {
        regionLabel: null,
        templates: [
          { id: 'intro', label: context.labels.intro, body: OWNER_SAKARYA_INTRO },
          { id: 'followUp', label: context.labels.followUp, body: OWNER_SAKARYA_FOLLOWUP },
          ...demoMeeting,
        ],
      };
    }

    return {
      regionLabel: REGION_SAKARYA,
      templates: [
        { id: 'intro', label: context.labels.intro, body: EMPLOYEE_SAKARYA_INTRO },
        { id: 'followUp', label: context.labels.followUp, body: EMPLOYEE_SAKARYA_FOLLOWUP },
        ...demoMeeting,
      ],
    };
  }

  if (context.role === 'owner') {
    return {
      regionLabel: REGION_OUTSIDE,
      templates: [
        { id: 'intro', label: context.labels.intro, body: OWNER_OUTSIDE_INTRO },
        { id: 'followUp', label: context.labels.followUp, body: OWNER_OUTSIDE_FOLLOWUP },
        ...demoMeeting,
      ],
    };
  }

  return {
    regionLabel: REGION_OUTSIDE,
    templates: [
      { id: 'intro', label: context.labels.intro, body: EMPLOYEE_OUTSIDE_INTRO },
      { id: 'followUp', label: context.labels.followUp, body: EMPLOYEE_OUTSIDE_FOLLOWUP },
      ...demoMeeting,
    ],
  };
}
