/**
 * Convert grams to US pounds and ounces for display.
 * 1 oz = 28.3495 g, 1 lb = 16 oz.
 */

const GRAMS_PER_OZ = 28.3495;
const OZ_PER_LB = 16;

/**
 * @param {number} grams - weight in grams
 * @returns {{ lbs: number, oz: number }}
 */
export function gramsToLbsOz(grams) {
  if (grams == null || Number.isNaN(grams)) return { lbs: 0, oz: 0 };
  const totalOz = grams / GRAMS_PER_OZ;
  const lbs = Math.floor(totalOz / OZ_PER_LB);
  const oz = Math.round((totalOz % OZ_PER_LB) * 10) / 10; // 1 decimal
  return { lbs, oz };
}

/**
 * Format weight for display, e.g. "8 lb 5.2 oz" or "12.3 oz"
 * @param {number} grams - weight in grams
 * @returns {string}
 */
export function formatWeightLbsOz(grams) {
  if (grams == null || Number.isNaN(grams)) return "–";
  const { lbs, oz } = gramsToLbsOz(grams);
  if (lbs === 0) return `${oz} oz`;
  if (oz === 0) return `${lbs} lb`;
  return `${lbs} lb ${oz} oz`;
}

/**
 * Convert grams to pounds (decimal) for charts.
 * @param {number} grams
 * @returns {number}
 */
export function gramsToLbs(grams) {
  if (grams == null || Number.isNaN(grams)) return 0;
  return Math.round((grams / GRAMS_PER_OZ / OZ_PER_LB) * 100) / 100;
}
