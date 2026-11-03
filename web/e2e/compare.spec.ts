import { test, expect } from '@playwright/test'

test('add two programs, see the tray, compare in two columns', async ({ page }) => {
  await page.goto('/zh/programs/101')
  await page.getByRole('button', { name: '加入比較' }).click()
  await page.goto('/zh/programs/1002')
  await page.getByRole('button', { name: '加入比較' }).click()
  await expect(page.getByText('已選 2 個校系')).toBeVisible()
  await page.getByRole('link', { name: '開始比較' }).click()
  await expect(page).toHaveURL(/\/zh\/compare\?ids=101,1002$/)
  await expect(page.locator('thead th[scope="col"]')).toHaveCount(3) // blank corner + 2
})

test('one id asks for a second', async ({ page }) => {
  await page.goto('/zh/compare?ids=101')
  await expect(page.getByText('請至少選擇 2 個校系才能比較。')).toBeVisible()
})

test('duplicate and invalid ids collapse to two columns', async ({ page }) => {
  await page.goto('/zh/compare?ids=101,101,abc,1002')
  await expect(page.locator('thead th[scope="col"]')).toHaveCount(3)
})
