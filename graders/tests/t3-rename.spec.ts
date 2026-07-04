import { test, expect } from '@playwright/test'
import { API_URL, control, listItems } from './helpers'

// Task 3 — label→title rename, the contract-boundary layers observable from
// here: API JSON shape, the published message payload, and the web UI. The
// DB column + data-preservation checks run in grade.py (they need psql and
// the pre-boot seed).

test('t3.api.title-shape — API request/response JSON uses title, no label', async ({
  request,
}) => {
  const value = `grader-t3-${Date.now()}`
  const res = await request.post(`${API_URL}/api/items`, { data: { title: value } })
  expect(res.status(), 'POST with {title} must create').toBe(201)
  const created = await res.json()
  expect(created.title).toBe(value)
  expect('label' in created, 'response must not expose label').toBe(false)

  const items = await listItems(request)
  expect(items.length).toBeGreaterThan(0)
  for (const item of items) {
    expect('title' in item, 'every listed item must expose title').toBe(true)
    expect('label' in item, 'no listed item may expose label').toBe(false)
  }
})

test('t3.broker.payload-title — published heartbeat payload uses title, no label', async ({}) => {
  await control('/worker/start')
  const msg = await control('/broker/consume-one')
  expect(msg.found, 'a heartbeat message must be publishable/consumable').toBe(true)
  expect('title' in msg.body, 'message payload must use title').toBe(true)
  expect('label' in msg.body, 'message payload must not use label').toBe(false)
})

test('t3.ui.title-visible — the web UI uses title on its public surface', async ({
  page,
  request,
}) => {
  const value = `grader-t3-ui-${Date.now()}`
  await request.post(`${API_URL}/api/items`, { data: { title: value } })
  await page.goto('/')
  await expect(page.getByText(value).first()).toBeVisible({ timeout: 15_000 })
  const text = (await page.locator('body').innerText()).toLowerCase()
  expect(text.includes('title'), 'the UI should name the field title').toBe(true)
  expect(text.includes('label'), 'the UI must not still say label').toBe(false)
})
