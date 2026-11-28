/**
 * Barcodes drawn as bars, for labels: EAN-13, UPC-A and EAN-8 for numeric
 * retail codes with a valid check digit, Code 128 for anything else a scanner
 * reads as typed. Every handheld scanner reads all of these.
 */

export type BarcodeFormat = 'EAN-13' | 'UPC-A' | 'EAN-8' | 'Code 128';

export interface EncodedBarcode {
  format: BarcodeFormat;
  /** One character per module, `1` a bar and `0` a space, quiet zones included. */
  modules: string;
  /** The digits or text printed under the bars. */
  text: string;
}

// Code 128 symbols 0 to 106, as the widths of their bars and spaces.
// prettier-ignore
const CODE128 = [
  '212222', '222122', '222221', '121223', '121322', '131222', '122213',
  '122312', '132212', '221213', '221312', '231212', '112232', '122132',
  '122231', '113222', '123122', '123221', '223211', '221132', '221231',
  '213212', '223112', '312131', '311222', '321122', '321221', '312212',
  '322112', '322211', '212123', '212321', '232121', '111323', '131123',
  '131321', '112313', '132113', '132311', '211313', '231113', '231311',
  '112133', '112331', '132131', '113123', '113321', '133121', '313121',
  '211331', '231131', '213113', '213311', '213131', '311123', '311321',
  '331121', '312113', '312311', '332111', '314111', '221411', '431111',
  '111224', '111422', '121124', '121421', '141122', '141221', '112214',
  '112412', '122114', '122411', '142112', '142211', '241211', '221114',
  '413111', '241112', '134111', '111242', '121142', '121241', '114212',
  '124112', '124211', '411212', '421112', '421211', '212141', '214121',
  '412121', '111143', '111341', '131141', '114113', '114311', '411113',
  '411311', '113141', '114131', '311141', '411131', '211412', '211214',
  '211232',
];
const CODE128_STOP = '2331112';
const START_B = 104;
const START_C = 105;
const CODE_B = 100;
const CODE_C = 99;

// EAN's left-hand odd (L) digit patterns; the even (G) and right (R) ones follow from them.
// prettier-ignore
const EAN_L = [
  '0001101', '0011001', '0010011', '0111101', '0100011',
  '0110001', '0101111', '0111011', '0110111', '0001011',
];
const EAN_R = EAN_L.map((code) =>
  code.replace(/./g, (bit) => (bit === '1' ? '0' : '1'))
);
const EAN_G = EAN_R.map((code) => code.split('').reverse().join(''));
// Which of an EAN-13's first six digits are G, by its leading digit.
// prettier-ignore
const EAN13_PARITY = [
  'LLLLLL', 'LLGLGG', 'LLGGLG', 'LLGGGL', 'LGLLGG',
  'LGGLLG', 'LGGGLL', 'LGLGLG', 'LGLGGL', 'LGGLGL',
];

/** The GS1 check digit of the digits before it, as EAN, UPC and GTIN use. */
export function gs1CheckDigit(digits: string): number {
  let sum = 0;
  // From the right, the digits weigh 3, 1, 3, 1…
  for (let i = 0; i < digits.length; i++) {
    const digit = Number(digits[digits.length - 1 - i]);
    sum += i % 2 === 0 ? digit * 3 : digit;
  }

  return (10 - (sum % 10)) % 10;
}

/** Whether the code is all digits and its last one checks the rest. */
export function hasValidCheckDigit(code: string): boolean {
  if (!/^\d{8,14}$/.test(code)) {
    return false;
  }

  return gs1CheckDigit(code.slice(0, -1)) === Number(code.slice(-1));
}

/** Whether Code 128 can draw the text: printable ASCII only. */
export function isCode128Encodable(text: string): boolean {
  return text.length > 0 && /^[\x20-\x7e]+$/.test(text);
}

/**
 * Draws a code in the format that fits it: EAN-13, UPC-A or EAN-8 when it is
 * one with a valid check digit, else Code 128. Undefined when it can't be
 * drawn, like a code with Bangla letters.
 */
export function encodeBarcode(code: string): EncodedBarcode | undefined {
  const value = code.trim();
  if (hasValidCheckDigit(value)) {
    if (value.length === 13) {
      return { format: 'EAN-13', modules: encodeEAN13(value), text: value };
    }

    if (value.length === 12) {
      // A UPC-A is an EAN-13 that starts with 0.
      return {
        format: 'UPC-A',
        modules: encodeEAN13(`0${value}`),
        text: value,
      };
    }

    if (value.length === 8) {
      return { format: 'EAN-8', modules: encodeEAN8(value), text: value };
    }
  }

  if (!isCode128Encodable(value)) {
    return undefined;
  }

  return { format: 'Code 128', modules: encodeCode128(value), text: value };
}

export function encodeEAN13(code: string): string {
  const digits = code.split('').map(Number);
  const parity = EAN13_PARITY[digits[0]];
  let left = '';
  for (let i = 1; i <= 6; i++) {
    const table = parity[i - 1] === 'L' ? EAN_L : EAN_G;
    left += table[digits[i]];
  }

  const right = digits
    .slice(7)
    .map((digit) => EAN_R[digit])
    .join('');
  return `${quiet(11)}101${left}01010${right}101${quiet(7)}`;
}

export function encodeEAN8(code: string): string {
  const digits = code.split('').map(Number);
  const left = digits
    .slice(0, 4)
    .map((digit) => EAN_L[digit])
    .join('');
  const right = digits
    .slice(4)
    .map((digit) => EAN_R[digit])
    .join('');
  return `${quiet(7)}101${left}01010${right}101${quiet(7)}`;
}

/**
 * Code 128 symbols for the text: set C, two digits a symbol, for runs of
 * four or more digits, set B for the rest.
 */
export function getCode128Symbols(text: string): number[] {
  const symbols: number[] = [];
  let set: 'B' | 'C' | undefined;
  let i = 0;
  while (i < text.length) {
    let run = /^\d*/.exec(text.slice(i))![0].length;
    const isWhole = i === 0 && run === text.length;
    // A run of digits is worth set C when it saves more than the switches cost.
    const minRun = i === 0 || i + run === text.length ? 4 : 6;
    if (run >= minRun || (isWhole && run % 2 === 0)) {
      if (run % 2) {
        // Set C takes pairs; an odd run's first digit goes in set B.
        symbols.push(...switchTo('B'), text.charCodeAt(i) - 32);
        i += 1;
        run -= 1;
      }

      symbols.push(...switchTo('C'));
      for (const end = i + run; i < end; i += 2) {
        symbols.push(Number(text.slice(i, i + 2)));
      }
      continue;
    }

    symbols.push(...switchTo('B'), text.charCodeAt(i) - 32);
    i += 1;
  }

  const [start, ...rest] = symbols;
  const checksum =
    rest.reduce((sum, symbol, index) => sum + symbol * (index + 1), start) %
    103;
  return [...symbols, checksum];

  function switchTo(next: 'B' | 'C'): number[] {
    if (set === next) {
      return [];
    }

    const first = set === undefined;
    set = next;
    if (first) {
      return [next === 'B' ? START_B : START_C];
    }

    return [next === 'B' ? CODE_B : CODE_C];
  }
}

export function encodeCode128(text: string): string {
  const widths = getCode128Symbols(text).map((symbol) => CODE128[symbol]);
  widths.push(CODE128_STOP);
  let modules = '';
  for (const pattern of widths) {
    pattern.split('').forEach((width, index) => {
      modules += (index % 2 === 0 ? '1' : '0').repeat(Number(width));
    });
  }

  return `${quiet(10)}${modules}${quiet(10)}`;
}

/** The bars as runs: where each starts and how many modules wide it is. */
export function getBars(modules: string): { x: number; width: number }[] {
  const bars: { x: number; width: number }[] = [];
  for (const match of modules.matchAll(/1+/g)) {
    bars.push({ x: match.index, width: match[0].length });
  }

  return bars;
}

function quiet(width: number): string {
  return '0'.repeat(width);
}
