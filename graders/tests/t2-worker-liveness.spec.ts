import { test, expect } from '@playwright/test'
import { control, trackNavigations, workerRegionText, DOWN_VOCAB } from './helpers'

// Task 2 — worker liveness surfaced in the UI. Behavior-defined and
// solution-independent: with the worker genuinely running, no worker-labeled
// region may read as down; after the grader stops the real worker process,
// some worker-labeled region must read as down/stale within the stated bound
// (17s measured allows UI poll jitter over the 15s requirement) without a
// page reload; and once the worker returns, the down state must clear.
// Driving the real process both ways means a hardcoded or config-based
// indicator cannot pass, and vocabulary choice ("up"/"healthy"/"active") is
// not prescribed — only the down transition's wording is checked, against a
// generous vocabulary.

test('t2.ui.worker-liveness-transition — up while running, down within 15s of stop, recovers on restart, no reload', async ({
  page,
}) => {
  test.setTimeout(150_000)
  // The worker must be genuinely alive and producing evidence.
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

  // Up state: while the worker runs, the worker region must not read down.
  // (Give the UI a few seconds to settle its first status poll.)
  await page.waitForTimeout(5_000)
  const runningText = await workerRegionText(page)
  expect(runningText, 'a worker-labeled region must exist in the UI').not.toBe('')
  expect(runningText, 'the indicator must not read down while the worker runs').not.toMatch(
    DOWN_VOCAB,
  )

  // Stop the real worker; the region must flip within the stated bound,
  // without any navigation.
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

  // Evidence-based recovery: once the worker returns, down must clear.
  await control('/worker/start')
  await expect
    .poll(async () => workerRegionText(page), {
      timeout: 40_000,
      message: 'the indicator should stop reading down once the worker restarts',
    })
    .not.toMatch(DOWN_VOCAB)
})
