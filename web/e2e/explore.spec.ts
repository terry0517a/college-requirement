import { test, expect } from '@playwright/test'

const cards = (page: import('@playwright/test').Page) => page.locator('main ul > li')

test('keyword 資訊工程 matches only NTU', async ({ page }) => {
  await page.goto('/zh/explore?q=' + encodeURIComponent('資訊工程'))
  await expect(cards(page)).toHaveCount(1)
  await expect(cards(page).first()).toContainText('國立臺灣大學')
})

test('region=us shows 2 cards', async ({ page }) => {
  await page.goto('/zh/explore?region=us')
  await expect(cards(page)).toHaveCount(2)
})

test('page 2 has 9 cards', async ({ page }) => {
  await page.goto('/zh/explore?page=2')
  await expect(cards(page)).toHaveCount(9)
})

test('garbage params still render a 200 page', async ({ page }) => {
  const res = await page.goto('/zh/explore?page=-1&field=xyz&q=%25')
  expect(res?.status()).toBe(200)
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
})

test('English UI shows the Chinese program name on a card', async ({ page }) => {
  await page.goto('/en/explore?q=' + encodeURIComponent('資訊工程'))
  await expect(cards(page).first()).toContainText('資訊工程學系')
})
