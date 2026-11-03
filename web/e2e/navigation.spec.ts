import { test, expect } from '@playwright/test'

test.describe('root redirect', () => {
  test.use({ locale: 'zh-TW' })
  test('/ redirects to /zh', async ({ page }) => {
    await page.goto('/')
    await expect(page).toHaveURL(/\/zh$/)
  })
})

test.describe('root redirect (English browser)', () => {
  test.use({ locale: 'en-US' })
  test('/ redirects to /en', async ({ page }) => {
    await page.goto('/')
    await expect(page).toHaveURL(/\/en$/)
  })
})

test('language switch keeps path and query', async ({ page }) => {
  await page.goto('/zh/explore?region=us')
  await expect(page.locator('html')).toHaveAttribute('lang', 'zh-Hant-TW')
  await page.getByRole('link', { name: 'English' }).click()
  await expect(page).toHaveURL(/\/en\/explore\?region=us$/)
  await expect(page.locator('html')).toHaveAttribute('lang', 'en')
})

test('no horizontal page scroll on home and school pages', async ({ page }) => {
  for (const path of ['/zh', '/zh/schools/1', '/zh/schools/10', '/en/about']) {
    await page.goto(path)
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)
    expect(overflow, path).toBeLessThanOrEqual(0)
  }
})
