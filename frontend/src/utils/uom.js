/**
 * Sub-fase 1.13 — util konversi UOM sisi frontend (DISPLAY/preview saja).
 * Sumber kebenaran tetap backend (services/uom_service.py). Faktor FIXED disamakan.
 */
export const FIXED_LENGTH_FACTORS = { meter: 1, m: 1, yard: 0.9144, yd: 0.9144, cm: 0.01, inch: 0.0254, in: 0.0254 };

const norm = (u) => String(u || "").trim().toLowerCase();
const round2 = (n) => Math.round(n * 100) / 100;

/** Faktor meter per 1 unit (tanpa pembulatan). null bila tak diketahui. */
export function convFactor(product, unit) {
  const base = norm(product?.base_unit || "meter");
  const u = norm(unit || base);
  if (u === base) return 1;
  const ff = FIXED_LENGTH_FACTORS;
  if (ff[u] != null && ff[base] != null) return ff[u] / ff[base];
  for (const c of product?.uom_conversions || []) {
    const cf = norm(c.from_unit), ct = norm(c.to_unit), fac = Number(c.factor);
    if (!fac) continue;
    if (cf === u && ct === base) return fac;
    if (ct === u && cf === base) return 1 / fac;
  }
  // Sub-fase 1.13 — catch-weight kg → base: meter per 1 kg = 1 / (gramasi×lebar/1000)
  const gsm = Number(product?.gramasi) || 0;
  const width = Number(product?.lebar) || 0;
  const kgPerBase = (gsm * width) / 1000;
  if (kgPerBase > 0 && u === "kg" && base === "meter") return 1 / kgPerBase;
  return null;
}

/** Konversi qty (unit) → base unit produk. null bila tak diketahui. */
export function toBase(product, qty, unit) {
  const f = convFactor(product, unit);
  return f == null ? null : round2((Number(qty) || 0) * f);
}

/** Daftar unit yang valid untuk produk: base + length FIXED + unit dari uom_conversions. */
export function unitOptions(product) {
  const base = norm(product?.base_unit || "meter");
  const seen = new Set([base, "yard", "cm", "inch"]);
  (product?.uom_conversions || []).forEach((c) => {
    if (c.from_unit) seen.add(norm(c.from_unit));
    if (c.to_unit) seen.add(norm(c.to_unit));
  });
  // Sub-fase 1.13 — kg tersedia bila gramasi & lebar terisi (catch-weight)
  if ((Number(product?.gramasi) || 0) > 0 && (Number(product?.lebar) || 0) > 0) seen.add("kg");
  return Array.from(seen).map((u) => ({ value: u, label: u.charAt(0).toUpperCase() + u.slice(1) }));
}
