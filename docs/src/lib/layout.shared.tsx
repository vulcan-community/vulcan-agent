import Image from 'next/image';
import type { BaseLayoutProps } from 'fumadocs-ui/layouts/shared';
import { i18n } from './i18n';
import { appName, gitConfig } from './shared';

const basePath = process.env.NEXT_PUBLIC_BASE_PATH || '';

export function baseOptions(locale: string): BaseLayoutProps {
  return {
    i18n,
    nav: {
      title: (
        <>
          <Image
            src={`${basePath}/logo.svg`}
            alt="Vulcan"
            width={24}
            height={24}
          />
          {appName}
        </>
      ),
    },
    githubUrl: `https://github.com/${gitConfig.user}/${gitConfig.repo}`,
  };
}
