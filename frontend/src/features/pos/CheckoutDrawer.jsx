import { useEffect, useMemo, useState } from "react";
import {
  X, ChevronRight, ChevronLeft, Users, UserPlus, PackageCheck, Receipt,
  AlertTriangle, Layers, ShieldAlert, ShieldCheck, XCircle, MapPin, CreditCard, CheckCircle2,
} from "lucide-react";
import axios, { API } from "../../services/apiClient";
import { formatCurrency, formatQty } from "../../utils/formatters";
import { computeOrderPreview } from "../../utils/pricing";
import { convFactor } from "../../utils/uom";
import { FulfillmentInfo } from "../../components/FulfillmentInfo";
import { MixedLotConfirmModal } from "../../components/MixedLotConfirmModal";
import KNSelect from "../../components/KNSelect";
import CreateCustomerModal from "./CreateCustomerModal";
import { SalesTeamEditor, salesTeamError } from "./SalesTeamEditor";

const STEPS = [
  { n: 1, label: "Customer & Alamat", icon: Users },
  { n: 2, label: "Term & Lot", icon: Layers },
  { n: 3, label: "Review", icon: CheckCircle2 },
];

/** EPIC5 — Checkout stepper 3 langkah. Memakai ulang preview ATP/lot/harga-khusus + gate kredit. */
export default function CheckoutDrawer({
  open, onClose, cart, setCart, customers = [],
  selectedCustomer, setSelectedCustomer, selectedAddress, setSelectedAddress,
  onCreateCustomer, onSubmitOrder, settings = {}, paymentTerms = [], selectedEntity = "all", onShowDetail,
}) {
  const [step, setStep] = useState(1);
  const [orderDiscount, setOrderDiscount] = useState(0);
  const [paymentTerm, setPaymentTerm] = useState("");
  const [allowBackorder, setAllowBackorder] = useState(false);
  const [showMixedConfirm, setShowMixedConfirm] = useState(false);
  const [showCreateCustomer, setShowCreateCustomer] = useState(false);
  const [allocation, setAllocation] = useState({ map: {}, loading: false, entityId: "" });
  const [transferRequests, setTransferRequests] = useState({});
  const [lotPlan, setLotPlan] = useState({ requires_confirmation: false, lines: [], policy: {}, loading: false });
  const [specialMap, setSpecialMap] = useState({});
  const [credit, setCredit] = useState(null);
  const [salesTeam, setSalesTeam] = useState([]);
  const teamErr = salesTeamError(salesTeam);

  const defaultTerm = settings?.finance?.default_payment_term_code || "";
  useEffect(() => { if (!paymentTerm && defaultTerm) setPaymentTerm(defaultTerm); }, [defaultTerm]); // eslint-disable-line
  useEffect(() => { if (open) setStep(1); }, [open]);

  const allowItemDiscount = settings?.sales?.allow_item_discount !== false;
  const allowOrderDiscount = settings?.sales?.allow_order_discount !== false;
  const addresses = selectedCustomer?.addresses || [];
  const entityFor = selectedEntity && selectedEntity !== "all" ? selectedEntity : (selectedCustomer?.entity_id || "");

  // Harga khusus (special price) per item — debounced.
  useEffect(() => {
    if (!open || !cart.length || !selectedCustomer?.id) { setSpecialMap({}); return undefined; }
    let cancelled = false;
    const timer = setTimeout(async () => {
      try {
        const results = await Promise.all(cart.map((i) =>
          axios.get(`${API}/price-approvals/effective`, {
            params: { customer_id: selectedCustomer.id, product_id: i.product.id, entity_id: entityFor, quantity: i.quantity },
          }).then((r) => ({ pid: i.product.id, data: r.data })).catch(() => ({ pid: i.product.id, data: { has_special: false } }))
        ));
        if (cancelled) return;
        const map = {};
        results.forEach(({ pid, data }) => { if (data && data.has_special) map[pid] = data; });
        setSpecialMap(map);
      } catch { if (!cancelled) setSpecialMap({}); }
    }, 400);
    return () => { cancelled = true; clearTimeout(timer); };
  }, [open, cart, entityFor, selectedCustomer]); // eslint-disable-line

  // ATP / alokasi preview — debounced.
  useEffect(() => {
    if (!open || !cart.length) { setAllocation({ map: {}, loading: false, entityId: "" }); return undefined; }
    let cancelled = false;
    setAllocation((a) => ({ ...a, loading: true }));
    const timer = setTimeout(async () => {
      try {
        const res = await axios.post(`${API}/sales-orders/preview-allocation`, {
          entity_id: entityFor, customer_id: selectedCustomer?.id || "",
          items: cart.map((i) => ({ product_id: i.product.id, quantity: i.quantity, unit: i.unit })),
        });
        if (cancelled) return;
        const map = {};
        (res.data.lines || []).forEach((l) => { map[l.product_id] = l; });
        setAllocation({ map, loading: false, entityId: res.data.entity_id || entityFor });
      } catch { if (!cancelled) setAllocation({ map: {}, loading: false, entityId: "" }); }
    }, 350);
    return () => { cancelled = true; clearTimeout(timer); };
  }, [open, cart, entityFor, selectedCustomer]); // eslint-disable-line

  // Lot plan (mixed-lot confirmation) — debounced.
  useEffect(() => {
    if (!open || !cart.length || !selectedCustomer?.id) { setLotPlan({ requires_confirmation: false, lines: [], policy: {}, loading: false }); return undefined; }
    let cancelled = false;
    setLotPlan((lp) => ({ ...lp, loading: true }));
    const timer = setTimeout(async () => {
      try {
        const res = await axios.post(`${API}/sales-orders/preview-lots`, {
          entity_id: entityFor, customer_id: selectedCustomer?.id || "",
          items: cart.map((i) => ({ product_id: i.product.id, quantity: i.quantity, unit: i.unit })),
        });
        if (cancelled) return;
        setLotPlan({ requires_confirmation: !!res.data.requires_confirmation, lines: res.data.lines || [], policy: res.data.policy || {}, loading: false });
      } catch { if (!cancelled) setLotPlan({ requires_confirmation: false, lines: [], policy: {}, loading: false }); }
    }, 400);
    return () => { cancelled = true; clearTimeout(timer); };
  }, [open, cart, entityFor, selectedCustomer]); // eslint-disable-line

  const cartPriced = cart.map((item) => {
    const sp = specialMap[item.product.id];
    const factor = convFactor(item.product, item.unit || item.product.base_unit) ?? 1;
    const scaled = Math.round((item.product.price || 0) * factor * 100) / 100;
    const price = sp && sp.has_special ? Number(sp.requested_price) : scaled;
    return { ...item, product: { ...item.product, price } };
  });
  const p = useMemo(() => computeOrderPreview(cartPriced, orderDiscount, settings), [cartPriced, orderDiscount, settings]);

  // Gate kredit live.
  useEffect(() => {
    const cid = selectedCustomer?.id;
    if (!open || !cid || cart.length === 0) { setCredit(null); return undefined; }
    let active = true;
    const t = setTimeout(() => {
      axios.get(`${API}/customers/${cid}/credit-status`, { params: { amount: p.grand } })
        .then((r) => { if (active) setCredit(r.data); }).catch(() => { if (active) setCredit(null); });
    }, 350);
    return () => { active = false; clearTimeout(t); };
  }, [open, selectedCustomer, p.grand, cart.length]); // eslint-disable-line

  const backorderQtyTotal = Object.values(allocation.map || {}).reduce((s, l) => s + (Number(l?.breakdown?.backorder) || 0), 0);
  const hasBackorderLine = backorderQtyTotal > 0;
  const mixedLotLines = (lotPlan?.lines || []).filter((l) => l.requires_confirmation);
  const requiresLotConfirmation = !!lotPlan?.requires_confirmation && mixedLotLines.length > 0;
  const creditBlocked = !!credit && credit.blocked && !credit.has_approved_override;

  const updateQty = (id, q) => setCart(cart.map((it) => it.product.id === id ? { ...it, quantity: Number(q) || 0 } : it));
  const updateDiscount = (id, d) => setCart(cart.map((it) => it.product.id === id ? { ...it, discount_percent: Math.max(0, Math.min(100, Number(d) || 0)) } : it));
  const remove = (id) => setCart(cart.filter((it) => it.product.id !== id));

  const doSubmit = (confirmMixed) => {
    onSubmitOrder({
      order_discount_percent: orderDiscount, payment_term_code: paymentTerm,
      allow_backorder: allowBackorder, special_prices: specialMap, confirm_mixed_lot: !!confirmMixed,
      sales_team: salesTeam,
    });
    onClose();
  };
  const handleSubmitClick = () => { if (requiresLotConfirmation) setShowMixedConfirm(true); else doSubmit(false); };

  const handleRequestTransfer = async (line) => {
    const source = (line.cross_entity || [])[0];
    const destEntity = allocation.entityId || entityFor;
    const qty = line.breakdown?.inter_company || 0;
    if (!source || !destEntity || qty <= 0) return;
    setTransferRequests((t) => ({ ...t, [line.product_id]: "requesting" }));
    try {
      await axios.post(`${API}/transfers/inter-company`, {
        source_entity_id: source.entity_id, dest_entity_id: destEntity,
        items: [{ product_id: line.product_id, quantity: qty, unit: line.unit }],
        notes: "Permintaan dari POS checkout (Fulfillment Assistant)",
      });
      setTransferRequests((t) => ({ ...t, [line.product_id]: "requested" }));
    } catch { setTransferRequests((t) => ({ ...t, [line.product_id]: "error" })); }
  };

  if (!open) return null;
  const canNext1 = !!selectedCustomer && !!selectedAddress;
  const canNext2 = cart.length > 0 && !lotPlan.loading;

  return (
    <div className="fixed inset-0 z-[110] flex justify-end bg-black/40" data-testid="checkout-drawer">
      <div className="flex h-full w-full max-w-[520px] flex-col bg-[#F7F8FA] shadow-2xl">
        {/* Header + stepper */}
        <div className="border-b border-[#EFF0F2] bg-white px-4 py-3">
          <div className="flex items-center justify-between">
            <h2 className="text-[15px] font-bold">Checkout</h2>
            <button data-testid="checkout-close" className="icon-button" onClick={onClose} aria-label="Tutup"><X size={18} /></button>
          </div>
          <div className="mt-3 flex items-center">
            {STEPS.map((s, i) => {
              const Icon = s.icon;
              const active = step === s.n, done = step > s.n;
              return (
                <div key={s.n} className="flex flex-1 items-center">
                  <div data-testid={`checkout-step-indicator-${s.n}`} className={`flex items-center gap-1.5 ${active ? "text-[#0058CC]" : done ? "text-[#126E2C]" : "text-[#9A9BA3]"}`}>
                    <span className={`flex h-6 w-6 items-center justify-center rounded-full text-[11px] font-bold ${active ? "bg-[#0058CC] text-white" : done ? "bg-[#126E2C] text-white" : "bg-[#E5E5EA] text-[#6B6B73]"}`}>
                      {done ? <CheckCircle2 size={14} /> : s.n}
                    </span>
                    <span className="hidden text-[11px] font-semibold sm:inline">{s.label}</span>
                  </div>
                  {i < STEPS.length - 1 && <div className={`mx-1.5 h-0.5 flex-1 ${done ? "bg-[#126E2C]" : "bg-[#E5E5EA]"}`} />}
                </div>
              );
            })}
          </div>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-4">
          {step === 1 && (
            <div data-testid="checkout-step-1" className="space-y-3">
              <div className="section-card">
                <div className="section-head"><div className="flex items-center gap-2"><Users size={14} className="text-[#0058CC]" /><h2 className="text-[13px]">Pilih Customer</h2></div></div>
                <div className="section-body space-y-3">
                  <KNSelect data-testid="checkout-customer-select" className="field w-full" value={selectedCustomer?.id || ""}
                    onValueChange={(id) => { setSelectedCustomer(customers.find((c) => c.id === id)); setSelectedAddress(""); }}
                    placeholder="-- Pilih customer --"
                    options={[{ value: "", label: "-- Pilih customer --" }, ...customers.map((c) => ({ value: c.id, label: `${c.name} — ${c.city}` }))]} />
                  <button data-testid="checkout-new-customer-button" className="secondary-button w-full" onClick={() => setShowCreateCustomer(true)}><UserPlus size={14} /> Customer Baru</button>
                  {selectedCustomer && (
                    <div className="rounded-md border border-[#EFF0F2] bg-[#FAFBFC] p-2.5">
                      <p data-testid="checkout-selected-customer" className="text-[12.5px] font-semibold">{selectedCustomer.name}</p>
                      <p className="text-[11px] text-[#3C3C43]">{selectedCustomer.pic_name} • {selectedCustomer.phone}</p>
                    </div>
                  )}
                  {selectedCustomer && (
                    <div data-testid="checkout-address-select">
                      <label className="mb-1 flex items-center gap-1 text-[10px] font-bold uppercase tracking-wide text-[#6B6B73]"><MapPin size={11} /> Alamat Pengiriman</label>
                      <KNSelect className="field w-full" value={selectedAddress || ""} onValueChange={setSelectedAddress}
                        placeholder="-- Pilih alamat --"
                        options={[{ value: "", label: "-- Pilih alamat --" }, ...addresses.map((a) => ({ value: a.id, label: `${a.label} — ${a.city}` }))]} />
                    </div>
                  )}
                </div>
              </div>

              {cart.length > 0 && (
                <div className="section-card" data-testid="checkout-step1-items">
                  <div className="section-head"><div className="flex items-center gap-2"><PackageCheck size={14} className="text-[#0058CC]" /><h2 className="text-[13px]">Item Pesanan ({cart.length})</h2></div></div>
                  <div className="section-body space-y-1.5">
                    {cart.map((it) => (
                      <div key={it.product.id} data-testid={`step1-item-${it.product.id}`} className="flex items-center justify-between gap-2 rounded-md border border-[#EFF0F2] bg-[#FAFBFC] px-2.5 py-1.5">
                        <div className="min-w-0">
                          <p className="text-[12px] font-semibold truncate">{it.product.name}</p>
                          <p className="text-[10.5px] text-[#6B6B73]">{it.product.sku} · {formatQty(it.quantity)} {it.product.base_unit || "meter"}</p>
                        </div>
                        <p className="shrink-0 text-[12px] font-semibold tabular-nums">{formatCurrency((it.product.price || 0) * (it.quantity || 0))}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {step === 2 && (
            <div data-testid="checkout-step-2" className="space-y-2">
              {cart.length === 0 && <p data-testid="checkout-empty" className="rounded-md border border-dashed border-[#E5E5EA] bg-white p-3 text-[12px] text-[#6B6B73]">Keranjang kosong.</p>}
              {cart.map((item) => {
                const sp = specialMap[item.product.id];
                const isSpecial = !!(sp && sp.has_special);
                const baseUnit = item.product.base_unit || "meter";  // F2 — 1 produk = 1 satuan dasar
                const rollCount = Number(item.product.roll_count || 0);
                const unitPrice = isSpecial ? Number(sp.requested_price) : Number(item.product.price || 0);
                const lineSubtotal = unitPrice * (item.quantity || 0);
                const dp = allowItemDiscount ? Number(item.discount_percent || 0) : 0;
                const lineTotal = lineSubtotal - (lineSubtotal * dp) / 100;
                return (
                  <div data-testid={`cart-item-${item.product.id}`} key={item.product.id} className="rounded-md border border-[#EFF0F2] bg-white p-2.5">
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <p className="text-[10.5px] font-bold uppercase tracking-wide text-[#0058CC]">{item.product.sku}</p>
                        <p data-testid={`cart-item-name-${item.product.id}`} className="text-[12.5px] font-semibold truncate">{item.product.name}</p>
                        {isSpecial && <p data-testid={`cart-item-special-${item.product.id}`} className="mt-0.5 inline-flex items-center gap-1 rounded-full bg-[#F3E9FA] px-2 py-0.5 text-[9.5px] font-bold text-[#6B219A]">Harga khusus {formatCurrency(unitPrice)} <span className="font-normal text-[#8E8E93] line-through">{formatCurrency(sp.normal_price)}</span></p>}
                      </div>
                      <button data-testid={`remove-cart-item-button-${item.product.id}`} className="icon-button" onClick={() => remove(item.product.id)} aria-label="Hapus"><XCircle size={14} /></button>
                    </div>
                    <div className="mt-2">
                      <label className="text-[9px] font-bold uppercase tracking-wide text-[#8E8E93]">Qty ({baseUnit})</label>
                      <input data-testid={`cart-item-qty-input-${item.product.id}`} className="field" type="number" min="1" value={item.quantity} onChange={(e) => updateQty(item.product.id, e.target.value)} />
                      <p data-testid={`cart-item-rolls-${item.product.id}`} className="mt-1 text-[10px] text-[#9A9BA3]">{rollCount} roll tersedia · dijual per {baseUnit}</p>
                    </div>
                    {allowItemDiscount && (
                      <div className="mt-2 grid grid-cols-[64px_1fr] items-end gap-2">
                        <div>
                          <label className="text-[9px] font-bold uppercase tracking-wide text-[#8E8E93]">Disc %</label>
                          <input data-testid={`cart-item-discount-input-${item.product.id}`} className="field" type="number" min="0" max="100" value={item.discount_percent || 0} onChange={(e) => updateDiscount(item.product.id, e.target.value)} />
                        </div>
                        <div className="text-right">
                          <p className="text-[9px] font-bold uppercase tracking-wide text-[#8E8E93]">Subtotal</p>
                          <p className="text-[12px] font-semibold tabular-nums">{formatCurrency(lineTotal)}{dp > 0 && <span className="ml-1 text-[10px] text-[#8E8E93] line-through">{formatCurrency(lineSubtotal)}</span>}</p>
                        </div>
                      </div>
                    )}
                    <FulfillmentInfo line={allocation.map[item.product.id]} loading={allocation.loading} reqStatus={transferRequests[item.product.id]} onRequestTransfer={handleRequestTransfer} />
                  </div>
                );
              })}

              {cart.length > 0 && (
                <div className="grid gap-2 rounded-md border border-[#EFF0F2] bg-white p-2.5">
                  <div>
                    <label className="text-[9px] font-bold uppercase tracking-wide text-[#8E8E93]">Term Pembayaran</label>
                    <KNSelect data-testid="payment-term-select" className="field" value={paymentTerm} onValueChange={setPaymentTerm}
                      options={paymentTerms.length === 0 ? [{ value: "", label: "Default" }] : paymentTerms.map((t) => ({ value: t.code, label: t.name }))} />
                  </div>
                  {allowOrderDiscount && (
                    <div>
                      <label className="text-[9px] font-bold uppercase tracking-wide text-[#8E8E93]">Diskon Order (%)</label>
                      <input data-testid="order-discount-input" className="field" type="number" min="0" max="100" value={orderDiscount} onChange={(e) => setOrderDiscount(Math.max(0, Math.min(100, Number(e.target.value) || 0)))} />
                    </div>
                  )}
                </div>
              )}

              {cart.length > 0 && (
                <SalesTeamEditor value={salesTeam} onChange={setSalesTeam} />
              )}

              {hasBackorderLine && (
                <div data-testid="backorder-option-card" className="rounded-md border border-[#F5C9A6] bg-[#FFF7EF] p-2.5">
                  <div className="flex items-start gap-2">
                    <AlertTriangle size={14} className="mt-0.5 shrink-0 text-[#A8221A]" />
                    <div>
                      <p className="text-[11.5px] font-semibold text-[#8C4A00]">Stok entitas tidak cukup untuk {formatQty(backorderQtyTotal)} meter.</p>
                      <label className="mt-1.5 flex cursor-pointer items-center gap-2">
                        <input data-testid="allow-backorder-checkbox" type="checkbox" className="h-3.5 w-3.5 accent-[#0058CC]" checked={allowBackorder} onChange={(e) => setAllowBackorder(e.target.checked)} />
                        <span className="text-[11.5px] font-medium text-[#1C1C1E]">Izinkan backorder (reservasi stok tersedia, sisanya menunggu barang masuk)</span>
                      </label>
                    </div>
                  </div>
                </div>
              )}
              {requiresLotConfirmation && (
                <div data-testid="mixed-lot-warning-card" className="rounded-md border border-[#D9C2EE] bg-[#F7F2FE] p-2.5">
                  <div className="flex items-start gap-2">
                    <Layers size={14} className="mt-0.5 shrink-0 text-[#6B219A]" />
                    <div>
                      <p className="text-[11.5px] font-semibold text-[#5B1A86]">{mixedLotLines.length} item akan dipenuhi dari beberapa lot (mixed lot).</p>
                      <p className="mt-0.5 text-[10.5px] text-[#6B219A]">Konfirmasi diperlukan saat membuat order — warna/dye-lot bisa berbeda antar lot.</p>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {step === 3 && (
            <div data-testid="checkout-step-3" className="space-y-3">
              <div className="rounded-md border border-[#EFF0F2] bg-white p-3">
                <p className="text-[11px] font-bold uppercase tracking-wide text-[#6B6B73]">Kirim ke</p>
                <p className="text-[13px] font-semibold">{selectedCustomer?.name}</p>
                <p className="text-[11.5px] text-[#6B6B73]">{(addresses.find((a) => a.id === selectedAddress) || {}).label} — {(addresses.find((a) => a.id === selectedAddress) || {}).city}</p>
              </div>
              <div className="rounded-md bg-black p-3 text-white">
                <div className="flex items-center gap-1.5"><Receipt size={12} className="text-white/70" /><p className="text-[10.5px] font-bold uppercase tracking-wide text-white/70">Ringkasan ({cart.length} item)</p></div>
                <div className="mt-1.5 space-y-1 text-[11.5px]">
                  <Row label="Subtotal (bruto)" value={formatCurrency(p.gross)} />
                  {p.discountTotal > 0 && <Row label="Diskon" value={`- ${formatCurrency(p.discountTotal)}`} />}
                  {p.ppn > 0 && <Row label={`PPN ${p.ppnRate}%`} value={formatCurrency(p.ppn)} />}
                  {p.isPkp === false && <Row label="PPN" value="Non-PKP (0)" muted />}
                  <Row label="Term" value={paymentTerm || "Default"} />
                </div>
                <div className="mt-2 flex items-end justify-between border-t border-white/15 pt-2">
                  <p className="text-[10.5px] font-bold uppercase tracking-wide text-white/70">Grand Total</p>
                  <p data-testid="cart-grand-total" className="text-[18px] font-bold">{formatCurrency(p.grand)}</p>
                </div>
              </div>

              {credit && credit.level !== "ok" && (
                <div data-testid="credit-status-banner" className={`rounded-md border p-2.5 ${creditBlocked ? "border-[#F1B0AB] bg-[#FDECEA]" : credit.has_approved_override ? "border-[#A7D8B0] bg-[#EAF7EE]" : "border-[#F5C9A6] bg-[#FFF7EF]"}`}>
                  <div className="flex items-start gap-2">
                    {creditBlocked ? <ShieldAlert size={14} className="mt-0.5 shrink-0 text-[#C0392B]" /> : <ShieldCheck size={14} className="mt-0.5 shrink-0 text-[#9A5B00]" />}
                    <div className="min-w-0 text-[11px]">
                      <p className={`font-semibold ${creditBlocked ? "text-[#9B1C13]" : "text-[#8C4A00]"}`}>
                        {creditBlocked ? "Kredit terblokir — order tidak bisa dibuat" : credit.has_approved_override ? "Kredit terblokir, tapi ada Override disetujui" : "Peringatan kredit (mendekati limit / ada tunggakan)"}
                      </p>
                      {(credit.reasons || []).map((r, i) => <p key={i} className="text-[10.5px] text-[#6B6B73]">• {r}</p>)}
                      <p className="mt-0.5 text-[10px] text-[#9A9BA3] tabular-nums">AR {formatCurrency(credit.credit?.ar_outstanding)} / limit {credit.credit?.credit_limit > 0 ? formatCurrency(credit.credit.credit_limit) : "∞"} · proyeksi {formatCurrency(credit.projected_ar)}</p>
                    </div>
                  </div>
                </div>
              )}
              {credit && credit.level === "ok" && (
                <div className="flex items-center gap-2 rounded-md border border-[#A7D8B0] bg-[#EAF7EE] p-2.5 text-[11.5px] text-[#126E2C]"><ShieldCheck size={14} /> Kredit OK · ATP & alokasi tervalidasi.</div>
              )}

              <div className="rounded-md border border-[#EFF0F2] bg-white p-3 text-[11.5px] text-[#6B6B73]">
                <div className="flex items-center gap-1.5 text-[#1C1C1E]"><CreditCard size={13} /><span className="font-semibold">Pemenuhan</span></div>
                <p className="mt-1">{hasBackorderLine ? (allowBackorder ? "Sebagian via backorder (disetujui)." : "Ada baris kurang stok — aktifkan backorder di langkah 2.") : "Semua baris dapat dipenuhi dari stok entitas."}</p>
                {requiresLotConfirmation && <p className="mt-0.5 text-[#6B219A]">{mixedLotLines.length} item mixed-lot — konfirmasi saat submit.</p>}
              </div>
            </div>
          )}
        </div>

        {/* Footer nav */}
        <div className="border-t border-[#EFF0F2] bg-white px-4 py-3">
          <div className="flex items-center justify-between gap-2">
            {step > 1 ? (
              <button data-testid="checkout-back" className="secondary-button" onClick={() => setStep(step - 1)}><ChevronLeft size={14} /> Kembali</button>
            ) : <span />}
            {step < 3 ? (
              <button data-testid="checkout-next" className="primary-button" disabled={step === 1 ? !canNext1 : !canNext2} onClick={() => setStep(step + 1)}>
                Lanjut <ChevronRight size={14} />
              </button>
            ) : (
              <button data-testid="checkout-submit" className="primary-button" disabled={!selectedCustomer || !selectedAddress || cart.length === 0 || lotPlan.loading || creditBlocked || !!teamErr} onClick={handleSubmitClick}>
                <PackageCheck size={14} /> {creditBlocked ? "Terblokir Kredit" : requiresLotConfirmation ? "Tinjau Lot & Buat" : "Buat Sales Order"}
              </button>
            )}
          </div>
        </div>
      </div>

      <CreateCustomerModal open={showCreateCustomer} onClose={() => setShowCreateCustomer(false)} onCreateCustomer={onCreateCustomer} />
      <MixedLotConfirmModal open={showMixedConfirm} lines={mixedLotLines} policy={lotPlan?.policy || {}} onCancel={() => setShowMixedConfirm(false)} onConfirm={() => { setShowMixedConfirm(false); doSubmit(true); }} />
    </div>
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
