/** Where the console's data comes from. Normally the console server (`just console`, `just console-replay`).
 *  A static build (`just console-static`, VITE_STATIC=1) is the hosted Replay: the same app, reading the files
 *  that crosswire_console.export_static wrote next to it. No server, no Switch, no Run button. */
export const STATIC = import.meta.env.VITE_STATIC === '1';

export const api = {
  config: () => (STATIC ? 'static/config.json' : '/api/config'),
  replay: (name: string) => (STATIC ? `static/replays/${encodeURIComponent(name)}.json` : `/api/replay?name=${encodeURIComponent(name)}`),
  security: () => (STATIC ? 'static/security.json' : '/api/security'),
};
