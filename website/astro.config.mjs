import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';

export default defineConfig({
  site: 'https://detrin.github.io',
  base: '/brow',
  integrations: [
    starlight({
      title: 'brow',
      social: {
        github: 'https://github.com/detrin/brow',
      },
      sidebar: [
        { label: 'Getting Started', link: '/getting-started/' },
        {
          label: 'CLI Reference',
          items: [
            { label: 'Overview', link: '/cli/' },
            { label: 'Daemon', link: '/cli/daemon/' },
            { label: 'Sessions', link: '/cli/sessions/' },
            { label: 'Navigation', link: '/cli/navigation/' },
            { label: 'Interaction', link: '/cli/interaction/' },
            { label: 'Observation', link: '/cli/observation/' },
            { label: 'Actions & Replay', link: '/cli/actions-replay/' },
          ],
        },
        {
          label: 'HTTP API',
          items: [
            { label: 'Overview', link: '/api/' },
            { label: 'Sessions', link: '/api/sessions/' },
            { label: 'Browser Actions', link: '/api/browser/' },
            { label: 'Pages', link: '/api/pages/' },
            { label: 'Profiles & States', link: '/api/profiles/' },
            { label: 'Eval', link: '/api/eval/' },
          ],
        },
        {
          label: 'Tutorials',
          items: [
            { label: 'Persistent Login', link: '/tutorials/persistent-login/' },
            { label: 'API Scouting', link: '/tutorials/api-scouting/' },
            { label: 'Playbook & Script Generation', link: '/tutorials/playbook-writer/' },
          ],
        },
        { label: 'Concepts', link: '/concepts/' },
      ],
    }),
  ],
});
