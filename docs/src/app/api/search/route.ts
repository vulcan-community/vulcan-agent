import { source } from '@/lib/source';
import { createFromSource } from 'fumadocs-core/search/server';

// Force static generation for `output: 'export'` (GitHub Pages).
// `staticGET` serializes the search index at build time so the client can
// fetch it as a static JSON file.
export const dynamic = 'force-static';
export const revalidate = false;

const server = createFromSource(source, {
  // https://docs.orama.com/docs/orama-js/supported-languages
  language: 'english',
  // Orama has no native Chinese tokenizer; fall back to english (char-level).
  localeMap: {
    en: 'english',
    'zh-cn': 'english',
  },
});

export const { staticGET: GET } = server;
