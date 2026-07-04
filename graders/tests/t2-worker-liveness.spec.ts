import { test, expect } from '@playwright/test'
import {
  control,
  trackNavigations,
  workerRegionText,
  UP_VOCAB,
  DOWN_VOCAB,
} from './helpers'

// Task 2 — worker liveness surfaced in the UI. Behavior-defined and
// solution-independent: some visible worker-labeled region must read as up
// while the worker runs and transition to down/stale within the stated bound
// after the worker stops, all without a page reload. The grader controls the
// real worker process, so a configuration-based fake cannot pass the
// transition.

test('t2.ui.worker-liveness-transition — indicator present, up while running, down within 15s of stop, no reload', async ({
  page,
}) => {
  test.setTimeout(120_000)
  // Ensure the worker is running and producing evidence.
  await control('/worker/start')
  const before = (await control('/db/items-count?source=worker')).count
  await expect
    .poll(async () => (await control('/db/items-count?source=worker')).count, {
      timeout: 20_000,
      message: 'worker must be writing heartbeat rows while running',
    })
    .toBeGreaterThan(before)

  await page.goto('/')
  const nav = trackNavigations(page)

  // t2.ui.indicator-present + t2.ui.up-while-running
  await expect
    .poll(async () => workerRegionText(page), {
      timeout: 30_000,
      message: 'a visible worker-labeled region must exist and read as up while the worker runs',
    })
    .toMatch(UP_VOCAB)

  // Stop the worker; the indicator must flip within 15s (17s measured allows
  // UI polling jitter over the stated bound) without any navigation.
  await control('/worker/stop')
  const stoppedAt = Date.now()
  await expect
    .poll(async () => workerRegionText(page), {
      timeout: 17_000,
      message: 'the worker region must read as down/stale within 15s of the worker stopping',
    })
    .toMatch(DOWN_VOCAB)
  const elapsedMs = Date.now() - stoppedAt

  expect(nav.count(), 'the indicator must update without a page reload').toBe(0)
  test.info().annotations.push({ type: 'transition-ms', description: String(elapsedMs) })

  // Symmetry: evidence-based status must recover when the worker returns.
  await control('/worker/start')
  await expect
    .poll(async () => workerRegionText(page), {
      timeout: 30_000,
      message: 'the indicator should report up again once the worker restarts',
    })
    .toMatch(UP_VOCAB)
})
