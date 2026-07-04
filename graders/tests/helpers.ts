import { Page, APIRequestContext, expect } from '@playwright/test'

export const API_URL = process.env.API_URL!
export const CONTROL_URL = process.env.CONTROL_URL!
// The item text field's public name: 'label' in the base fixture, 'title'
// after the t3 rename (t3/t5 grade the post-rename shape).
export const FIELD = process.env.ITEM_FIELD || 'label'

export async function control(path: string): Promise<any> {
  const res = await fetch(CONTROL_URL + path, { method: 'POST' })
  if (!res.ok) throw new Error(`control ${path} → ${res.status}`)
  const text = await res.text()
  try {
    return JSON.parse(text)
  } catch {
    return text
  }
}

export async function createItem(request: APIRequestContext, value: string) {
  const res = await request.post(`${API_URL}/api/items`, { data: { [FIELD]: value } })
  expect(res.status(), `POST /api/items should create (body field '${FIELD}')`).toBe(201)
  return res.json()
}

export async function listItems(request: APIRequestContext): Promise<any[]> {
  const res = await request.get(`${API_URL}/api/items`)
  expect(res.status()).toBe(200)
  return res.json()
}

/** Track full page loads/navigations so "without a reload" is checkable. */
export function trackNavigations(page: Page): { count: () => number } {
  let navs = 0
  page.on('framenavigated', frame => {
    if (frame === page.mainFrame()) navs += 1
  })
  return { count: () => navs }
}

export const UP_VOCAB = /\b(up|healthy|alive|running|active|ok|online|live)\b/i
export const DOWN_VOCAB =
  /\b(down|stale|stopped|dead|unhealthy|offline|inactive|unavailable|lost|not running|no recent|missing)\b/i

/**
 * The innermost visible element(s) mentioning the worker, joined as one text
 * region. Solution-independent: any UI that "shows a worker status indicator"
 * must render worker-labeled text somewhere.
 */
export async function workerRegionText(page: Page): Promise<string> {
  const texts = await page
    .getByText(/worker/i)
    .evaluateAll(els =>
      els.map(el => (el.parentElement ? el.parentElement.innerText : (el as HTMLElement).innerText)),
    )
  return texts.join(' | ')
}
