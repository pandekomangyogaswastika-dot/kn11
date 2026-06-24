import { useEffect, useState } from "react";
import { ShoppingBag, PackageCheck, XCircle, Receipt, AlertTriangle, Layers, ShieldAlert, ShieldCheck } from "lucide-react";
import { formatCurrency, formatQty } from "../utils/formatters";
import { computeOrderPreview } from "../utils/pricing";
import { MixedLotConfirmModal } from "./MixedLotConfirmModal";
import { FulfillmentInfo } from "./FulfillmentInfo";
import KNSelect from "./KNSelect";
import { unitOptions, toBase, convFactor } from "../utils/uom";
import axios, { API } from "../services/apiClient";

export function CartPanel({
  cart,
  setCart,
  selectedCustomer,
  selectedAddress,
  onSubmitOrder,
  onShowDetail,
  settings = {},
  paymentTerms = [],
  allocationLines = {},
  allocationLoading = false,
  transferRequests = {},
  onRequestTransfer,
  specialPrices = {},
  lotPlan = {},
  lotPlanLoading = false,
}) {
  const [orderDiscount, setOrderDiscount] = useState(0);
  const [paymentTerm, setPaymentTerm] = useState("");
  const [allowBackorder, setAllowBackorder] = useState(false);
  const [showMixedConfirm, setShowMixedConfirm] = useState(false);

  const defaultTerm = settings?.finance?.default_payment_term_code || "";
  useEffect(() => {
    if (!paymentTerm && defaultTerm) setPaymentTerm(defaultTerm);
  }, [defaultTerm]); // eslint-disable-line react-hooks/exhaustive-deps

  // Sub-fase 1.6 — deteksi baris yang akan backorder (stok+incoming entitas kurang)
  const backorderQtyTotal = Object.values(allocationLines || {}).reduce(
    (sum, l) => sum + (Number(l?.breakdown?.backorder) || 0), 0
  );
  const hasBackorderLine = backorderQtyTotal > 0;

  const allowItemDiscount = settings?.sales?.allow_item_discount !== false;
  const allowOrderDiscount = settings?.sales?.allow_order_discount !== false;

  // Mixed-Lot Confirmation (Sub-fase 1.7) — baris yang akan dipenuhi lintas-lot.
  const mixedLotLines = (lotPlan?.lines || []).filter((l) => l.requires_confirmation);
  const requiresLotConfirmation = !!lotPlan?.requires_confirmation && mixedLotLines.length > 0;

  const doSubmit = (confirmMixed) =>
    onSubmitOrder({
      order_discount_percent: orderDiscount,
      payment_term_code: paymentTerm,
      allow_backorder: allowBackorder,
      special_prices: specialPrices,
      confirm_mixed_lot: !!confirmMixed,
    });

  const handleSubmitClick = () => {
    if (requiresLotConfirmation) setShowMixedConfirm(true);
    else doSubmit(false);
  };

  const updateQty = (productId, quantity) =>
    setCart(cart.map((item) =>
      item.product.id === productId ? { ...item, quantity: Number(quantity) || 0 } : item
    ));

  // Sub-fase 1.13 — ubah unit jual per baris (mempengaruhi base_quantity & harga).
  const updateUnit = (productId, unit) =>
    setCart(cart.map((item) =>
      item.product.id === productId ? { ...item, unit } : item
    ));

  const updateDiscount = (productId, discount) =>
    setCart(cart.map((item) =>
      item.product.id === productId
        ? { ...item, discount_percent: Math.max(0, Math.min(100, Number(discount) || 0)) }
        : item
    ));

  const remove = (productId) =>
    setCart(cart.filter((item) => item.product.id !== productId));

  // Sub-fase 1.7 — harga khusus override harga normal untuk preview & display.
  const effectivePrice = (item) => {
    const sp = specialPrices[item.product.id];
    return sp && sp.has_special ? Number(sp.requested_price) : (item.product.price || 0);
  };
  const cartPriced = cart.map((item) => {
    const sp = specialPrices[item.product.id];
    // Sub-fase 1.13 — harga normal di-skala ke unit jual (price/meter × meter-per-unit).
    const factor = convFactor(item.product, item.unit || item.product.base_unit) ?? 1;
    const scaled = Math.round((item.product.price || 0) * factor * 100) / 100;
    const price = sp && sp.has_special ? Number(sp.requested_price) : scaled;
    return { ...item, product: { ...item.product, price } };
  });
  const hasSpecial = cart.some((i) => specialPrices[i.product.id]?.has_special);

  const p = computeOrderPreview(cartPriced, orderDiscount, settings);

  // KN_17 — gate kredit live: ambil status kredit customer terhadap grand total
  const [credit, setCredit] = useState(null);
  useEffect(() => {
    const cid = selectedCustomer?.id;
    if (!cid || cart.length === 0) { setCredit(null); return; }
    let active = true;
    const t = setTimeout(() => {
      axios.get(`${API}/customers/${cid}/credit-status`, { params: { amount: p.grand } })
        .then((r) => { if (active) setCredit(r.data); })
        .catch(() => { if (active) setCredit(null); });
    }, 350);
    return () => { active = false; clearTimeout(t); };
  }, [selectedCustomer, p.grand, cart.length]); // eslint-disable-line

  const creditBlocked = !!credit && credit.blocked && !credit.has_approved_override;

  return (
    <section data-testid="cart-panel" className="section-card">
      <div className="section-head">
        <div className="flex items-center gap-2 min-w-0">
          <ShoppingBag data-testid="cart-panel-icon" size={14} className="text-[#0058CC]" />
          <span className="kicker">Draft Order</span>
          <h2>Reservasi 3 hari</h2>
        </div>
      </div>
      <div className="section-body">
        <div className="grid gap-2">
          {cart.length === 0 && (
            <p
              data-testid="empty-cart-message"
              className="rounded-md border border-dashed border-[#E5E5EA] bg-[#FAFBFC] p-3 text-[12px] text-[#6B6B73]"
            >
              Pilih produk dari grid POS untuk mulai membuat order.
            </p>
          )}
          {cart.map((item) => {
            const sp = specialPrices[item.product.id];
            const isSpecial = !!(sp && sp.has_special);
            const lineFactor = convFactor(item.product, item.unit || item.product.base_unit) ?? 1;
            const unitPrice = isSpecial
              ? Number(sp.requested_price)
              : Math.round((item.product.price || 0) * lineFactor * 100) / 100;
            const lineSubtotal = unitPrice * (item.quantity || 0);
            const baseUnit = item.product.base_unit || "meter";
            const sellUnit = item.unit || baseUnit;
            const baseEq = toBase(item.product, item.quantity || 0, sellUnit);
            const dp = allowItemDiscount ? Number(item.discount_percent || 0) : 0;
            const lineTotal = lineSubtotal - (lineSubtotal * dp) / 100;
            return (
              <div
                data-testid={`cart-item-${item.product.id}`}
                key={item.product.id}
                className="rounded-md border border-[#EFF0F2] bg-[#FAFBFC] p-2.5"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p
                      data-testid={`cart-item-sku-${item.product.id}`}
                      className="text-[10.5px] font-bold uppercase tracking-wide text-[#0058CC]"
                    >
                      {item.product.sku}
                    </p>
                    <p
                      data-testid={`cart-item-name-${item.product.id}`}
                      className="text-[12.5px] font-semibold truncate"
                    >
                      {item.product.name}
                    </p>
                    {isSpecial && (
                      <p
                        data-testid={`cart-item-special-${item.product.id}`}
                        className="mt-0.5 inline-flex items-center gap-1 rounded-full bg-[#F3E9FA] px-2 py-0.5 text-[9.5px] font-bold text-[#6B219A]"
                      >
                        Harga khusus {formatCurrency(unitPrice)}
                        <span className="font-normal text-[#8E8E93] line-through">{formatCurrency(sp.normal_price)}</span>
                      </p>
                    )}
                  </div>
                  <button
                    data-testid={`remove-cart-item-button-${item.product.id}`}
                    className="icon-button"
                    onClick={() => remove(item.product.id)}
                    aria-label="Remove item"
                  >
                    <XCircle size={14} />
                  </button>
                </div>
                <div className="mt-2 grid grid-cols-[1fr_92px] gap-2">
                  <div>
                    <label className="text-[9px] font-bold uppercase tracking-wide text-[#8E8E93]">Qty</label>
                    <input
                      data-testid={`cart-item-qty-input-${item.product.id}`}
                      className="field"
                      type="number"
                      min="1"
                      value={item.quantity}
                      onChange={(e) => updateQty(item.product.id, e.target.value)}
                    />
                  </div>
                  <div>
                    <label className="text-[9px] font-bold uppercase tracking-wide text-[#8E8E93]">Unit</label>
                    <KNSelect
                      data-testid={`cart-item-unit-select-${item.product.id}`}
                      className="field"
                      value={sellUnit}
                      onValueChange={(u) => updateUnit(item.product.id, u)}
                      options={unitOptions(item.product)}
                    />
                  </div>
                </div>
                {sellUnit !== baseUnit && baseEq != null && (
                  <p
                    data-testid={`cart-item-base-eq-${item.product.id}`}
                    className="mt-1 text-[10.5px] text-[#6B6B73]"
                  >
                    ≈ {formatQty(baseEq)} {baseUnit} (base) · {formatCurrency(unitPrice)}/{sellUnit}
                  </p>
                )}
                {allowItemDiscount && (
                  <div className="mt-2 grid grid-cols-[64px_1fr] items-end gap-2">
                    <div>
                      <label className="text-[9px] font-bold uppercase tracking-wide text-[#8E8E93]">Disc %</label>
                      <input
                        data-testid={`cart-item-discount-input-${item.product.id}`}
                        className="field"
                        type="number"
                        min="0"
                        max="100"
                        value={item.discount_percent || 0}
                        onChange={(e) => updateDiscount(item.product.id, e.target.value)}
                      />
                    </div>
                    <div className="text-right">
                      <p className="text-[9px] font-bold uppercase tracking-wide text-[#8E8E93]">Subtotal</p>
                      <p className="text-[12px] font-semibold tabular-nums">
                        {formatCurrency(lineTotal)}
                        {dp > 0 && (
                          <span className="ml-1 text-[10px] text-[#8E8E93] line-through">{formatCurrency(lineSubtotal)}</span>
                        )}
                      </p>
                    </div>
                  </div>
                )}
                <FulfillmentInfo
                  line={allocationLines[item.product.id]}
                  loading={allocationLoading}
                  reqStatus={transferRequests[item.product.id]}
                  onRequestTransfer={onRequestTransfer}
                />
              </div>
            );
          })}
        </div>

        {/* Term pembayaran + diskon order (Fase 1B) */}
        {cart.length > 0 && (
          <div className="mt-3 grid gap-2 rounded-md border border-[#EFF0F2] bg-white p-2.5">
            <div>
              <label className="text-[9px] font-bold uppercase tracking-wide text-[#8E8E93]">Term Pembayaran</label>
              <KNSelect
                data-testid="payment-term-select"
                className="field"
                value={paymentTerm}
                onValueChange={setPaymentTerm}
                options={paymentTerms.length === 0 ? [{ value: "", label: "Default" }] : paymentTerms.map(t => ({ value: t.code, label: t.name }))}
              />
            </div>
            {allowOrderDiscount && (
              <div>
                <label className="text-[9px] font-bold uppercase tracking-wide text-[#8E8E93]">Diskon Order (%)</label>
                <input
                  data-testid="order-discount-input"
                  className="field"
                  type="number"
                  min="0"
                  max="100"
                  value={orderDiscount}
                  onChange={(e) => setOrderDiscount(Math.max(0, Math.min(100, Number(e.target.value) || 0)))}
                />
              </div>
            )}
          </div>
        )}

        {/* Ringkasan pricing (Fase 1B) */}
        {cart.length > 0 && (
          <button
            data-testid="cart-total-card"
            className="interactive-card mt-2 w-full rounded-md bg-black p-3 text-left text-white"
            onClick={() => onShowDetail({
              title: "Ringkasan Sales Order",
              body: "Harga ditangkap saat order dibuat. PPN & diskon mengikuti pengaturan (Admin -> Pengaturan) dan status PKP entitas.",
              facts: [
                { label: "Item", value: cart.length },
                { label: "Subtotal", value: formatCurrency(p.gross) },
                { label: "Diskon", value: formatCurrency(p.discountTotal) },
                { label: `PPN ${p.ppnRate || 0}%`, value: formatCurrency(p.ppn) },
                { label: "Grand Total", value: formatCurrency(p.grand) },
                { label: "Term", value: paymentTerm || "Default" },
              ],
              target: "sales",
              cta: "Kembali ke draft",
            })}
          >
            <div className="flex items-center gap-1.5">
              <Receipt size={12} className="text-white/70" />
              <p className="text-[10.5px] font-bold uppercase tracking-wide text-white/70">Ringkasan</p>
            </div>
            <div className="mt-1.5 space-y-1 text-[11.5px]">
              <Row label="Subtotal (bruto)" value={formatCurrency(p.gross)} />
              {p.discountTotal > 0 && <Row label="Diskon" value={`- ${formatCurrency(p.discountTotal)}`} />}
              {p.discountTotal > 0 && <Row label="Subtotal netto (DPP)" value={formatCurrency(p.net)} />}
              {p.ppn > 0 && <Row label={`PPN ${p.ppnRate}%`} value={formatCurrency(p.ppn)} />}
              {p.isPkp === false && <Row label="PPN" value="Non-PKP (0)" muted />}
            </div>
            <div className="mt-2 flex items-end justify-between border-t border-white/15 pt-2">
              <p className="text-[10.5px] font-bold uppercase tracking-wide text-white/70">Grand Total</p>
              <p data-testid="cart-grand-total" className="text-[18px] font-bold">{formatCurrency(p.grand)}</p>
            </div>
          </button>
        )}

        {/* Sub-fase 1.6 — opsi backorder bila stok entitas tak cukup */}
        {cart.length > 0 && hasBackorderLine && (
          <div
            data-testid="backorder-option-card"
            className="mt-2 rounded-md border border-[#F5C9A6] bg-[#FFF7EF] p-2.5"
          >
            <div className="flex items-start gap-2">
              <AlertTriangle size={14} className="mt-0.5 shrink-0 text-[#A8221A]" />
              <div className="min-w-0">
                <p className="text-[11.5px] font-semibold text-[#8C4A00]">
                  Stok entitas tidak cukup untuk {formatQty(backorderQtyTotal)} meter.
                </p>
                <label className="mt-1.5 flex cursor-pointer items-center gap-2">
                  <input
                    data-testid="allow-backorder-checkbox"
                    type="checkbox"
                    className="h-3.5 w-3.5 accent-[#0058CC]"
                    checked={allowBackorder}
                    onChange={(e) => setAllowBackorder(e.target.checked)}
                  />
                  <span className="text-[11.5px] font-medium text-[#1C1C1E]">
                    Izinkan backorder (reservasi stok tersedia sekarang, sisanya menunggu barang masuk)
                  </span>
                </label>
              </div>
            </div>
          </div>
        )}

        {/* Sub-fase 1.7 — peringatan pemenuhan lintas-lot (mixed lot) */}
        {cart.length > 0 && requiresLotConfirmation && (
          <div data-testid="mixed-lot-warning-card" className="mt-2 rounded-md border border-[#D9C2EE] bg-[#F7F2FE] p-2.5">
            <div className="flex items-start gap-2">
              <Layers size={14} className="mt-0.5 shrink-0 text-[#6B219A]" />
              <div className="min-w-0">
                <p className="text-[11.5px] font-semibold text-[#5B1A86]">
                  {mixedLotLines.length} item akan dipenuhi dari beberapa lot (mixed lot).
                </p>
                <p className="mt-0.5 text-[10.5px] text-[#6B219A]">
                  Konfirmasi diperlukan saat membuat order — warna/dye-lot bisa berbeda antar lot.
                </p>
              </div>
            </div>
          </div>
        )}

        {/* KN_17 — banner status kredit customer (gate SO/POS) */}
        {cart.length > 0 && credit && credit.level !== "ok" && (
          <div data-testid="credit-status-banner"
            className={`mt-2 rounded-md border p-2.5 ${creditBlocked
              ? "border-[#F1B0AB] bg-[#FDECEA]"
              : credit.has_approved_override
                ? "border-[#A7D8B0] bg-[#EAF7EE]"
                : "border-[#F5C9A6] bg-[#FFF7EF]"}`}>
            <div className="flex items-start gap-2">
              {creditBlocked ? <ShieldAlert size={14} className="mt-0.5 shrink-0 text-[#C0392B]" />
                : <ShieldCheck size={14} className="mt-0.5 shrink-0 text-[#9A5B00]" />}
              <div className="min-w-0 text-[11px]">
                <p className={`font-semibold ${creditBlocked ? "text-[#9B1C13]" : "text-[#8C4A00]"}`}>
                  {creditBlocked ? "Kredit terblokir — order tidak bisa dibuat"
                    : credit.has_approved_override ? "Kredit terblokir, tapi ada Override yang disetujui"
                    : "Peringatan kredit (mendekati limit / ada tunggakan)"}
                </p>
                {(credit.reasons || []).map((r, i) => (
                  <p key={i} className="text-[10.5px] text-[#6B6B73]">• {r}</p>
                ))}
                <p className="text-[10px] text-[#9A9BA3] mt-0.5 tabular-nums">
                  AR {formatCurrency(credit.credit?.ar_outstanding)} / limit {credit.credit?.credit_limit > 0 ? formatCurrency(credit.credit.credit_limit) : "∞"} · proyeksi {formatCurrency(credit.projected_ar)}
                </p>
                {creditBlocked && (
                  <p className="text-[10.5px] text-[#9B1C13] mt-1">Ajukan <b>Override Kredit</b> di menu Pelanggan / CRM dan minta persetujuan manager.</p>
                )}
              </div>
            </div>
          </div>
        )}

        <button
          data-testid="submit-sales-order-button"
          className="primary-button mt-2 w-full"
          disabled={!selectedCustomer || !selectedAddress || cart.length === 0 || lotPlanLoading || creditBlocked}
          onClick={handleSubmitClick}
        >
          <PackageCheck size={14} />
          {creditBlocked
            ? "Terblokir Kredit"
            : requiresLotConfirmation
            ? "Tinjau Lot & Buat Order"
            : hasBackorderLine && allowBackorder
            ? "Buat Order + Backorder"
            : "Buat Sales Order & Reserve"}
        </button>
      </div>

      <MixedLotConfirmModal
        open={showMixedConfirm}
        lines={mixedLotLines}
        policy={lotPlan?.policy || {}}
        onCancel={() => setShowMixedConfirm(false)}
        onConfirm={() => { setShowMixedConfirm(false); doSubmit(true); }}
      />
    </section>
  );
}

function Row({ label, value, muted = false }) {
  return (
    <div className="flex items-center justify-between">
      <span className={muted ? "text-white/50" : "text-white/80"}>{label}</span>
      <span className={muted ? "text-white/50" : "font-semibold"}>{value}</span>
    </div>
  );
}
