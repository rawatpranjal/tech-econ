// Vitest config for tech-econ JS unit tests.
//
// Tests live under tests/js/**/*.test.js. They run in jsdom by default so
// modules that touch document/localStorage are testable. Source modules
// stay in static/js/ where Hugo serves them.

import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    include: ['tests/js/**/*.test.js'],
    environment: 'jsdom',
    globals: false,
    reporters: 'default',
    coverage: {
      provider: 'v8',
      include: ['static/js/**/*.js'],
      exclude: ['static/js/**/*.min.js'],
    },
  },
});
