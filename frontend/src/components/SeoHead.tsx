import { useEffect } from 'react';
import { DEFAULT_OG_IMAGE, SITE_NAME, SITE_URL, type SeoMeta } from '../seo/config';

function upsertMeta(name: string, content: string, attribute: 'name' | 'property' = 'name') {
  if (!content) return;

  let element = document.head.querySelector(`meta[${attribute}="${name}"]`) as HTMLMetaElement | null;
  if (!element) {
    element = document.createElement('meta');
    element.setAttribute(attribute, name);
    document.head.appendChild(element);
  }
  element.setAttribute('content', content);
}

function upsertLink(rel: string, href: string) {
  if (!href) return;

  let element = document.head.querySelector(`link[rel="${rel}"]`) as HTMLLinkElement | null;
  if (!element) {
    element = document.createElement('link');
    element.setAttribute('rel', rel);
    document.head.appendChild(element);
  }
  element.setAttribute('href', href);
}

function upsertJsonLd(id: string, data: Record<string, unknown> | null) {
  const selector = `script[data-seo-id="${id}"]`;
  const existing = document.head.querySelector(selector);
  existing?.remove();
  if (!data) return;

  const script = document.createElement('script');
  script.type = 'application/ld+json';
  script.setAttribute('data-seo-id', id);
  script.textContent = JSON.stringify(data);
  document.head.appendChild(script);
}

interface Props {
  meta: SeoMeta;
  locale?: 'tr' | 'en';
  includeStructuredData?: boolean;
}

export default function SeoHead({ meta, locale = 'tr', includeStructuredData = false }: Props) {
  useEffect(() => {
    const url = meta.path ? `${SITE_URL}${meta.path}` : SITE_URL;

    document.documentElement.lang = locale;

    document.title = meta.title;
    upsertMeta('description', meta.description);
    upsertMeta('robots', meta.robots);
    upsertMeta('og:title', meta.title, 'property');
    upsertMeta('og:description', meta.description, 'property');
    upsertMeta('og:type', meta.ogType || 'website', 'property');
    upsertMeta('og:url', url, 'property');
    upsertMeta('og:site_name', SITE_NAME, 'property');
    upsertMeta('og:locale', locale === 'tr' ? 'tr_TR' : 'en_US', 'property');
    upsertMeta('og:image', DEFAULT_OG_IMAGE, 'property');
    upsertMeta('twitter:card', 'summary_large_image');
    upsertMeta('twitter:title', meta.title);
    upsertMeta('twitter:description', meta.description);
    upsertMeta('twitter:image', DEFAULT_OG_IMAGE);

    if (meta.robots.includes('index')) {
      upsertLink('canonical', url);
    } else {
      document.head.querySelector('link[rel="canonical"]')?.remove();
    }

    if (includeStructuredData && meta.path === '/') {
      upsertJsonLd('organization', {
        '@context': 'https://schema.org',
        '@type': 'Organization',
        name: SITE_NAME,
        url: SITE_URL,
        logo: `${SITE_URL}/favicon.png`,
      });
      upsertJsonLd('software', {
        '@context': 'https://schema.org',
        '@type': 'SoftwareApplication',
        name: SITE_NAME,
        applicationCategory: 'BusinessApplication',
        operatingSystem: 'Web',
        offers: {
          '@type': 'Offer',
          price: '0',
          priceCurrency: 'TRY',
        },
        url: SITE_URL,
        description: meta.description,
      });
    } else {
      upsertJsonLd('organization', null);
      upsertJsonLd('software', null);
    }
  }, [meta, locale, includeStructuredData]);

  return null;
}
