// Generated portal shell — do not edit in .cache/portal/; edit the kit's .camarones/portal/ instead.
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';
import mermaid from 'astro-mermaid';
import fs from 'node:fs';

const cfg = JSON.parse(fs.readFileSync(new URL('./portal.config.json', import.meta.url), 'utf8'));
const exists = (p) => fs.existsSync(new URL(`./src/content/docs/${p}`, import.meta.url));
const dir = (label, directory) => (exists(directory) ? [{ label, collapsed: true, items: [{ autogenerate: { directory } }] }] : []);

export default defineConfig({
  site: cfg.site || undefined,
  integrations: [
    mermaid({ theme: 'default', autoTheme: true }),
    starlight({
      title: cfg.name,
      favicon: '/favicon.svg',
      customCss: ['./src/styles/custom.css'],
      defaultLocale: 'root',
      locales: {
        root: { label: 'English', lang: 'en' },
        ...Object.fromEntries(cfg.translations.map((l) => [l, { label: cfg.localeLabels[l] || l, lang: l }])),
      },
      sidebar: [
        { label: 'Explore', translations: { es: 'Explorar' }, items: [
          { label: 'Architecture (C4, interactive)', translations: { es: 'Arquitectura (C4, interactiva)' }, link: '/architecture/', attrs: { target: '_blank' } },
          { label: 'Code graph (all repos)', translations: { es: 'Grafo de código (todos los repos)' }, link: '/code-graph/', attrs: { target: '_blank' } },
          ...cfg.repos.filter((r) => r.wikiGraph).map((r) => ({ label: `Wiki graph: ${r.name}`, link: `/wiki-graph/${r.name}/`, attrs: { target: '_blank' } })),
          { label: 'Doc status', translations: { es: 'Estado de la doc' }, link: '/status/' },
        ] },
        ...dir('Overview', 'overview'),
        ...dir('Architecture', 'architecture'),
        ...dir('Domain', 'domain'),
        ...dir('Business flows', 'flows'),
        ...dir('Data', 'data'),
        ...dir('Deployment', 'deployment'),
        ...dir('Decisions (ADR)', 'decisions'),
        ...dir('Quality & debt', 'quality'),
        ...dir('Security', 'security'),
        { label: 'Repositories', translations: { es: 'Repositorios' }, items: cfg.repos.flatMap((r) => dir(r.name, `repos/${r.name}`)) },
        ...dir('Guides', 'guides'),
      ],
    }),
  ],
});
