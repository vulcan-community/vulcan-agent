import { createMDX } from 'fumadocs-mdx/next';

const withMDX = createMDX();

// Allow disabling static export (e.g. for local `next dev`) via env vars.
// In CI / when building for GitHub Pages, set NEXT_PUBLIC_BASE_PATH=/vulcan-agent
// and (optionally) STATIC_EXPORT=true.
const basePath = process.env.NEXT_PUBLIC_BASE_PATH || '';
const isStaticExport =
  process.env.STATIC_EXPORT === 'true' || process.env.NODE_ENV === 'production';

/** @type {import('next').NextConfig} */
const config = {
  reactStrictMode: true,
  ...(isStaticExport ? { output: 'export' } : {}),
  ...(basePath
    ? {
        basePath,
        assetPrefix: `${basePath}/`,
      }
    : {}),
  images: {
    unoptimized: true,
  },
};

export default withMDX(config);
