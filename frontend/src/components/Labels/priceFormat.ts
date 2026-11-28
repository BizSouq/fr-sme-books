import { formatNumber } from 'fyo/utils/format';
import { fyo } from 'src/initFyo';
import type { PriceFormat } from 'src/utils/labels';

/** Prices in the shop's number format and currency, like ৳1,250 for a Bangladeshi shop. */
export function getPriceFormat(): PriceFormat {
  const currency = fyo.singles.SystemSettings?.currency as string | undefined;
  return {
    formatNumber: (value, precision) => formatNumber(value, fyo, precision),
    symbol: currency ? fyo.currencySymbols[currency] : undefined,
  };
}
