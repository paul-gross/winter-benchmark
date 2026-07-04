import { test, expect } from '@playwright/test'
import { API_URL, FIELD, createItem, listItems } from './helpers'

// Shared regression layer, run for every prompt. Grades that pre-existing
// behavior still works: item create/list via the API and a UI that lists
// items including the worker's rows (the worker-rows trap: a UI that filters
// or breaks on source=worker rows fails here).

test('reg.items-create-list — API create and list still work', async ({ request }) => {
  const value = `grader-reg-${Date.now()}`
  const created = await createItem(request, value)
  expect(created[FIELD]).toBe(value)
  expect(created.source).toBe('api')
  const items = await listItems(request)
  expect(items.some(i => i[FIELD] === value)).toBe(true)
})

test('reg.ui-lists-items — UI lists items including worker rows', async ({ page, request }) => {
  const value = `grader-regui-${Date.now()}`
  await createItem(request, value)
  // The worker writes rows on a 2s cadence; at least one must render in the UI.
  const items = await listItems(request)
  const workerItem = items.find(i => i.source === 'worker')
  expect(workerItem, 'expected worker-written rows in the item list').toBeTruthy()

  await page.goto('/')
  await expect(page.getByText(value).first()).toBeVisible({ timeout: 15_000 })
  await expect(page.getByText(String(workerItem[FIELD])).first()).toBeVisible()
})

test('reg.api-health — health endpoint reports ok/ok', async ({ request }) => {
  const res = await request.get(`${API_URL}/api/health`)
  expect(res.status()).toBe(200)
  const body = await res.json()
  expect(body.status).toBe('ok')
  expect(body.db).toBe('ok')
})
