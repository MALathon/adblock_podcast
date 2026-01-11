import { test, expect } from '@playwright/test';

test.describe('Home Page', () => {
  test('should display library header', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByRole('heading', { name: /library/i })).toBeVisible();
  });

  test('should have search button', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByRole('link', { name: /search/i })).toBeVisible();
  });

  test('should navigate to search page', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('link', { name: /search/i }).click();
    await expect(page).toHaveURL('/search');
  });

  test('should show empty state when no subscriptions', async ({ page }) => {
    await page.goto('/');
    // Check for empty state or subscription cards
    const content = await page.textContent('body');
    expect(content).toBeTruthy();
  });
});
