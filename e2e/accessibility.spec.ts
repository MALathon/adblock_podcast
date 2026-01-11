import { test, expect } from '@playwright/test';

test.describe('Accessibility', () => {
  test('home page should have proper heading structure', async ({ page }) => {
    await page.goto('/');
    const h1 = page.getByRole('heading', { level: 1 });
    await expect(h1).toBeVisible();
  });

  test('search page should have proper heading structure', async ({ page }) => {
    await page.goto('/search');
    const h1 = page.getByRole('heading', { level: 1 });
    await expect(h1).toBeVisible();
  });

  test('links should be focusable', async ({ page }) => {
    await page.goto('/');
    const searchLink = page.getByRole('link', { name: /search/i });
    await searchLink.focus();
    await expect(searchLink).toBeFocused();
  });

  test('search input should be accessible', async ({ page }) => {
    await page.goto('/search');
    const input = page.getByRole('searchbox');
    await expect(input).toBeVisible();
    await input.focus();
    await expect(input).toBeFocused();
  });

  test('back link should be accessible', async ({ page }) => {
    await page.goto('/search');
    const backLink = page.getByRole('link', { name: /back to library/i });
    await expect(backLink).toBeVisible();
    await backLink.focus();
    await expect(backLink).toBeFocused();
  });

  test('keyboard navigation should work', async ({ page }) => {
    await page.goto('/');
    // Tab to search link
    await page.keyboard.press('Tab');
    const focusedElement = await page.evaluate(() => document.activeElement?.tagName);
    expect(focusedElement).toBe('A');
  });
});
