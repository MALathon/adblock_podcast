import { test, expect } from '@playwright/test';

test.describe('Search Page', () => {
  test('should display search header', async ({ page }) => {
    await page.goto('/search');
    await expect(page.getByRole('heading', { name: /search/i })).toBeVisible();
  });

  test('should have back button to library', async ({ page }) => {
    await page.goto('/search');
    await expect(page.getByRole('link', { name: /back to library/i })).toBeVisible();
  });

  test('should have search input', async ({ page }) => {
    await page.goto('/search');
    await expect(page.getByRole('searchbox')).toBeVisible();
  });

  test('should focus search input on page load', async ({ page }) => {
    await page.goto('/search');
    await expect(page.getByRole('searchbox')).toBeFocused();
  });

  test('should show placeholder text', async ({ page }) => {
    await page.goto('/search');
    const input = page.getByRole('searchbox');
    await expect(input).toHaveAttribute('placeholder', /podcasts/i);
  });

  test('should navigate back to library', async ({ page }) => {
    await page.goto('/search');
    await page.getByRole('link', { name: /back to library/i }).click();
    await expect(page).toHaveURL('/');
  });

  test('should show empty state hint before search', async ({ page }) => {
    await page.goto('/search');
    await expect(page.getByText(/search for podcasts/i)).toBeVisible();
  });
});
