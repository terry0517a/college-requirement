import { test, expect } from '@playwright/test'

const DATE = /\d{4}-\d{2}-\d{2}/

test('school pages 1, 10, 11 have every section with source and date', async ({ page }) => {
  for (const id of [1, 10, 11]) {
    await page.goto(`/zh/schools/${id}`)
    for (const h of ['錄取要求', '強項', '費用', '來源'])
      await expect(page.getByRole('heading', { level: 2, name: h }), `school ${id} ${h}`).toBeVisible()
    const main = page.locator('main')
    await expect(main).toContainText('來源')
    await expect(main).toContainText(DATE)
  }
})

test('school 11 SAT block shows the no-data string', async ({ page }) => {
  await page.goto('/zh/schools/11')
  await expect(page.locator('#admissions')).toContainText('資料不足')
})

test('program 101 shows review items and the sieve table', async ({ page }) => {
  await page.goto('/zh/programs/101')
  await expect(page.getByText('審查資料').first()).toBeVisible()
  await expect(page.locator('#sieve table')).toBeVisible()
})

test('program 201 has all three blocks as no-data', async ({ page }) => {
  await page.goto('/zh/programs/201')
  for (const id of ['apply', 'sieve', 'distribution'])
    await expect(page.locator(`#${id}`)).toContainText('資料不足')
})

for (const path of ['/zh/schools/3', '/zh/schools/abc', '/zh/programs/0']) {
  test(`${path} is 404`, async ({ page }) => {
    const res = await page.goto(path)
    expect(res?.status()).toBe(404)
  })
}

test('unmatched URL under a locale gets the branded 404', async ({ page }) => {
  const res = await page.goto('/zh/no-such-page')
  expect(res?.status()).toBe(404)
  await expect(page.getByRole('heading', { level: 1 })).toContainText('找不到頁面 / Page not found')
})

test('about page covers sources, schedule, disclaimer and privacy', async ({ page }) => {
  const res = await page.goto('/zh/about')
  expect(res?.status()).toBe(200)
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
  const main = page.locator('main')
  await expect(main.getByRole('link', { name: /College Scorecard/ })).toBeVisible()
  await expect(main).toContainText('每週')
  await expect(main).toContainText('不做排名')
  await expect(main).toContainText('個人資料')
  await page.goto('/en/about')
  await expect(page.locator('html')).toHaveAttribute('lang', 'en')
  await expect(page.locator('main')).toContainText('once a week')
})

test('titles use the locale site name', async ({ page }) => {
  await page.goto('/zh/about')
  await expect(page).toHaveTitle(/大學資訊整合/)
  await page.goto('/en/about')
  await expect(page).toHaveTitle(/University Finder/)
  await expect(page).not.toHaveTitle(/大學資訊整合/)
})

test('sitemap and robots', async ({ request }) => {
  const sm = await request.get('/sitemap.xml')
  expect(sm.status()).toBe(200)
  const xml = await sm.text()
  expect(xml.match(/<url>/g)?.length ?? 0).toBeGreaterThan(0)
  expect(xml).toContain('/zh/about')
  expect(xml).toContain('/en/schools/1<')
  expect(xml).not.toContain('/schools/3<')
  expect(xml).not.toContain('/schools/12<')
  expect(xml).toContain('/zh/programs/101<')
  expect(xml).not.toContain('/programs/1002<')
  const robots = await (await request.get('/robots.txt')).text()
  expect(robots).toMatch(/Allow: \//)
  expect(robots).toMatch(/Sitemap: .*\/sitemap\.xml/)
})
