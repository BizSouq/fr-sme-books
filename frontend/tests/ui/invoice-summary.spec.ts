import { expect, test, type Page } from '@playwright/test';
import { serveFixture } from './helpers/fixture-server';

const url = serveFixture('invoice-summary');

async function open(page: Page) {
  await page.goto(url());
  await page.waitForFunction(
    () => (window as any).formFixture?.form.value?.doc
  );
  await page.evaluate(() => (window as any).formFixture.fillTotals());
}

test.describe('wide window', () => {
  test.use({ viewport: { width: 1440, height: 900 } });

  test('the invoice totals sit in a summary column on the right of the form', async ({
    page,
  }) => {
    await open(page);
    const summary = page.getByRole('complementary', { name: 'Summary' });
    const total = page.getByTestId('form-summary-total');
    await expect(total.locator('[data-fieldname="grand_total"]')).toHaveText(
      /18,457\.50/
    );
    await expect(
      summary.locator('[data-fieldname="outstanding_amount"]')
    ).toContainText('18,457.50');
    await expect(
      summary.locator('[data-fieldname="stock_not_transferred"]')
    ).toBeVisible();

    // The form keeps its fields; only the totals left it.
    const items = page.locator('[data-fieldname="items"]').first();
    await expect(items).toBeVisible();
    await expect(page.locator('[data-fieldname="customer"]')).toBeVisible();
    // The grand total shows once: in the summary, not also in the form.
    await expect(page.locator('[data-fieldname="grand_total"]')).toHaveCount(1);

    const form = (await items.boundingBox())!;
    const side = (await summary.boundingBox())!;
    expect(side.x).toBeGreaterThan(form.x + form.width);

    await page.screenshot({
      path: test.info().outputPath('invoice-summary.png'),
    });
  });
});

test.describe('narrow window', () => {
  test.use({ viewport: { width: 1024, height: 800 } });

  test('the totals stay in the form when there is no room beside it', async ({
    page,
  }) => {
    await open(page);
    await expect(
      page.getByRole('complementary', { name: 'Summary' })
    ).toHaveCount(0);
    await expect(page.locator('[data-fieldname="grand_total"]')).toBeVisible();
  });
});
