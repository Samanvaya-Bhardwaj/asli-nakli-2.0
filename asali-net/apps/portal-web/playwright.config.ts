import { defineConfig } from '@playwright/test'

// Runs against the simulation network on this computer: start it and seed it first (infra/scripts/sim_rebuild.sh).
export default defineConfig({
  testDir: './e2e',
  timeout: 120_000,
  expect: { timeout: 20_000 },
  workers: 1,
  reporter: [['list'], ['json', { outputFile: '../../docs/evidence/ui/e2e-raw.json' }]],
  use: { headless: true, viewport: { width: 1280, height: 800 }, locale: 'en-IN' },
})
