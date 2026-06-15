import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';

export default defineConfig({
  site: 'https://dailybreadeth-sketch.github.io',
  base: '/antigravity-blog',
  integrations: [sitemap()],
});
