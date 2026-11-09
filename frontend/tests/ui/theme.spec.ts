import { expect, test, type Page } from '@playwright/test';
import { serveFixture } from './helpers/fixture-server';

const url = serveFixture('desk');

test.use({ viewport: { width: 1440, height: 900 } });

test.beforeEach(async ({ page }) => {
  await page.goto(url());
  await page.waitForFunction(() => (window as any).deskFixture);
  await page.evaluate(() => document.fonts.ready);
});

function setTheme(page: Page, theme: 'light' | 'dark') {
  return page.evaluate(
    (value) => document.documentElement.setAttribute('data-theme', value),
    theme
  );
}

function background(page: Page, selector: string) {
  return page
    .locator(selector)
    .first()
    .evaluate((element) => getComputedStyle(element).backgroundColor);
}

for (const theme of ['light', 'dark'] as const) {
  test(`the sidebar is indigo and the totals are colored in ${theme} mode`, async ({
    page,
  }) => {
    await setTheme(page, theme);
    const sidebar = page.locator('.books-sidebar');
    await expect(sidebar).toBeVisible();
    // Light: #1c1640. Dark: a deeper indigo; never the page's own background.
    expect(await background(page, '.books-sidebar')).not.toBe(
      await page.evaluate(() => getComputedStyle(document.body).backgroundColor)
    );

    const active = page.locator(
      ".books-sidebar [data-slot='sidebar-item'][data-state='active']"
    );
    await expect(active).toContainText('Dashboard');
    expect(await background(page, ".books-sidebar [data-state='active']")).toBe(
      'rgb(60, 199, 149)'
    );

    // One color per total, in the order the dashboard shows them.
    const cards = page.locator('.books-kpi');
    await expect(cards).toHaveCount(4);
    await expect(cards.first()).toContainText('5,36,642.87');
    const colors = await cards.evaluateAll((elements) =>
      elements.map((element) => getComputedStyle(element).backgroundColor)
    );
    expect(new Set(colors).size).toBe(4);

    await page.screenshot({ path: test.info().outputPath(`desk-${theme}.png`) });
  });
}

test('the brand colors solid controls, and tooltips stay neutral', async ({
  page,
}) => {
  const link = page.getByRole('link', { name: 'View paid invoices' }).first();
  await link.hover();
  const bubble = page.locator("[data-slot='bubble']");
  await expect(bubble).toBeVisible();
  expect(
    await bubble.evaluate((element) => getComputedStyle(element).backgroundColor)
  ).not.toBe('rgb(0, 106, 78)');
  expect(
    await page.evaluate(() =>
      getComputedStyle(document.documentElement)
        .getPropertyValue('--surface-gray-10')
        .trim()
    )
  ).toBe('#006a4e');
});
