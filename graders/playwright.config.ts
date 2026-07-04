import { defineConfig } from '@playwright/test'

// The grading stack's endpoints are injected by grade.py. Tests run strictly
// sequentially: several checks mutate shared state (worker stop/start, item
// rows) and their order is part of the check design.
export default defineConfig({
  testDir: './tests',
  workers: 1,
  fullyParallel: false,
  retries: 0,
  timeout: 60_000,
  expect: { timeout: 10_000 },
  reporter: [['json', { outputFile: process.env.GRADE_REPORT || 'playwright-report.json' }]],
  use: {
    baseURL: process.env.WEB_URL,
    headless: true,
  },
})
