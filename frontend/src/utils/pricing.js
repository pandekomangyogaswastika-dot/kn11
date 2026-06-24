// Fase 1B — preview pricing di sisi klien (CERMIN backend services/config_service.compute_order_pricing).
// Tujuan: tampilkan ringkasan diskon + PPN sebelum order dibuat. Backend tetap
// otoritatif saat menyimpan; util ini hanya untuk preview UX.

export function computeOrderPreview(items, orderDiscountPercent, settings) {
  const sales = (settings && settings.sales) || {};
  const tax = (settings && settings.tax) || {};
  const allowItem = sales.allow_item_discount !== false;
  const allowOrder = sales.allow_order_discount !== false;
  const isPkp = tax.is_pkp !== false;
  const rate = isPkp ? Number(tax.ppn_rate || 0) : 0;
  const mode = tax.ppn_mode || "excluded";

  let gross = 0;
  let itemsDisc = 0;
  (items || []).forEach((it) => {
    const price = Number((it.product && it.product.price) || it.price || 0);
    const qty = Number(it.quantity || 0);
    const subtotal = price * qty;
    const dp = allowItem ? Math.max(0, Math.min(100, Number(it.discount_percent || 0))) : 0;
    gross += subtotal;
    itemsDisc += (subtotal * dp) / 100;
  });

  const afterItem = gross - itemsDisc;
  const odp = allowOrder ? Math.max(0, Math.min(100, Number(orderDiscountPercent || 0))) : 0;
  const orderDisc = (afterItem * odp) / 100;
  const net = afterItem - orderDisc;

  let dpp;
  let ppn;
  let grand;
  if (!isPkp || rate <= 0) {
    dpp = net; ppn = 0; grand = net;
  } else if (mode === "included") {
    dpp = net / (1 + rate / 100); ppn = net - dpp; grand = net;
  } else {
    dpp = net; ppn = (net * rate) / 100; grand = net + ppn;
  }

  return {
    gross,
    itemsDisc,
    orderDisc,
    discountTotal: itemsDisc + orderDisc,
    net,
    dpp,
    ppnRate: rate,
    ppn,
    grand,
    mode,
    isPkp,
    allowItem,
    allowOrder,
  };
}
