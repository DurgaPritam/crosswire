import type { Config } from 'tailwindcss';
import crosswire from './src/design/tailwind.preset';

export default {
  presets: [crosswire],
  content: ['./index.html', './src/**/*.{ts,tsx}'],
} satisfies Config;
