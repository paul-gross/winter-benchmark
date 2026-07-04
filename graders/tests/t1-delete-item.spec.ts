import { test, expect } from '@playwright/test'
import { API_URL, control, createItem, listItems, trackNavigations } from './helpers'

// Task 1 — delete an item. Solution-independent: grades the stated observable
// requirements (204/404 semantics, exact-row removal, per-row UI control, no
// reload), not any implementation shape.

test('t1.api.delete-204-removes — deleting an existing item returns 204 and removes it', async ({
  request,
}) => {
  const value = `grader-t1-del-${Date.now()}`
  const created = await createItem(request, value)
  const res = await request.delete(`${API_URL}/api/items/${created.id}`)
  expect(res.status()).toBe(204)
  const items = await listItems(request)
  expect(items.some(i => i.id === created.id)).toBe(false)
})

test('t1.api.delete-missing-404 — deleting a missing id returns 404', async ({ request }) => {
  const res = await request.delete(`${API_URL}/api/items/999999999`)
  expect(res.status()).toBe(404)
  // Deleting an id twice: second delete is also a missing id.
  const created = await createItem(request, `grader-t1-twice-${Date.now()}`)
  expect((await request.delete(`${API_URL}/api/items/${created.id}`)).status()).toBe(204)
  expect((await request.delete(`${API_URL}/api/items/${created.id}`)).status()).toBe(404)
})

test('t1.db.only-target-removed — deletion removes exactly the target row (worker rows survive)', async ({
  request,
}) => {
  const keep = await createItem(request, `grader-t1-keep-${Date.now()}`)
  const kill = await createItem(request, `grader-t1-kill-${Date.now()}`)
  const workerBefore = (await control('/db/items-count?source=worker')).count
  expect(workerBefore, 'worker rows must exist before the deletion check').toBeGreaterThan(0)

  expect((await request.delete(`${API_URL}/api/items/${kill.id}`)).status()).toBe(204)

  const items = await listItems(request)
  expect(items.some(i => i.id === keep.id), 'sibling user row must survive').toBe(true)
  const workerAfter = (await control('/db/items-count?source=worker')).count
  expect(workerAfter, 'worker rows must not be deleted').toBeGreaterThanOrEqual(workerBefore)
})

test('t1.ui.row-delete-no-reload — every row offers a delete control; list updates without reload', async ({
  page,
  request,
}) => {
  const value = `grader-t1-ui-${Date.now()}`
  await createItem(request, value)
  await page.goto('/')
  const nav = trackNavigations(page)

  const row = page.locator('tr, li, [role="row"]').filter({ hasText: value }).first()
  await expect(row, 'the created item must appear in the list').toBeVisible({ timeout: 15_000 })

  const deleteControl = row
    .locator('button, a, [role="button"], input[type="button"], input[type="submit"]')
    .filter({ hasText: /delete|remove|×|✕|✖|🗑|trash|del\b/i })
    .or(row.getByRole('button', { name: /delete|remove|trash/i }))
    .first()
  await expect(deleteControl, 'each row must offer a delete control').toBeVisible()

  page.on('dialog', d => d.accept())
  await deleteControl.click()

  await expect(page.getByText(value), 'row must disappear after delete').toBeHidden({
    timeout: 15_000,
  })
  expect(nav.count(), 'the list must update without a full page reload').toBe(0)

  const items = await listItems(request)
  expect(items.some(i => Object.values(i).includes(value))).toBe(false)
})
