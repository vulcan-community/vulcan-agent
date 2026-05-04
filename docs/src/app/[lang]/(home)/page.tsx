import Image from 'next/image';
import Link from 'next/link';

const basePath = process.env.NEXT_PUBLIC_BASE_PATH || '';

const copy = {
  en: {
    tagline:
      'An agent virtual machine with pluggable runtime backends. OpenAI-compatible on the outside; Claude Code, Codex, Google ADK on the inside.',
    getStarted: 'Get Started',
  },
  'zh-cn': {
    tagline:
      '一个支持可插拔运行时的 Agent 虚拟机。对外 OpenAI 兼容,对内对接 Claude Code、Codex、Google ADK。',
    getStarted: '开始使用',
  },
} as const;

export default async function HomePage({
  params,
}: {
  params: Promise<{ lang: string }>;
}) {
  const { lang } = await params;
  const t = copy[lang as keyof typeof copy] ?? copy.en;

  return (
    <div className="flex flex-col items-center justify-center text-center flex-1 px-6 py-16">
      <Image
        src={`${basePath}/logo.svg`}
        alt="Vulcan"
        width={120}
        height={120}
        priority
      />
      <h1 className="text-4xl font-bold mt-8 mb-3">Vulcan Agent</h1>
      <p className="text-lg text-fd-muted-foreground max-w-2xl">{t.tagline}</p>
      <div className="flex gap-3 mt-8">
        <Link
          href={`/${lang}/docs`}
          className="px-5 py-2 rounded-md bg-fd-primary text-fd-primary-foreground font-medium hover:opacity-90"
        >
          {t.getStarted}
        </Link>
        <a
          href="https://github.com/fangyaozheng/vulcan-agent"
          className="px-5 py-2 rounded-md border border-fd-border font-medium hover:bg-fd-muted"
        >
          GitHub
        </a>
      </div>
    </div>
  );
}
