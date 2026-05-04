import { RootProvider } from 'fumadocs-ui/provider/next';
import { defineI18nUI } from 'fumadocs-ui/i18n';
import { i18n } from '@/lib/i18n';

const { provider } = defineI18nUI(i18n, {
  translations: {
    en: { displayName: 'English' },
    'zh-cn': { displayName: '简体中文', search: '搜索文档' },
  },
});

const basePath = process.env.NEXT_PUBLIC_BASE_PATH || '';

export default async function LangLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ lang: string }>;
}) {
  const { lang } = await params;
  return (
    <RootProvider
      i18n={provider(lang)}
      search={{
        options: {
          type: 'static',
          api: `${basePath}/api/search`,
        },
      }}
    >
      {children}
    </RootProvider>
  );
}

export function generateStaticParams() {
  return i18n.languages.map((lang) => ({ lang }));
}
