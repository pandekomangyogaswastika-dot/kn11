import { useEffect, useState } from "react";
import { Plus, XCircle, Sparkles, AlertTriangle, Receipt, Scale } from "lucide-react";
import { formatCurrency } from "../../../utils/formatters";
import axios, { API } from "../../../services/apiClient";
import KNSelect from "../../../components/KNSelect";

/**
 * POCreateForm — form buat Purchase Order baru (collapsible).
 * Props: formData, setFormData, newItem, setNewItem,
 *        products, warehouses, onSubmit, onCancel, onAddItem, onRemoveItem
 * Depth #3 — auto-isi harga & unit dari price-list supplier saat produk dipilih.
 */
export default function POCreateForm({
  formData, setFormData,
  newItem, setNewItem,
  products, warehouses, suppliers = [],
  onSubmit, onCancel,
  onAddItem, onRemoveItem,
  submitting = false,
}) {
  const activeSuppliers = suppliers.filter((s) => s.status !== "inactive");
  const [priceHint, setPriceHint] = useState("");
  const [priceRef, setPriceRef] = useState(0);   // harga price-list acuan (untuk warning deviasi)
  // P0-1 — config pajak efektif (PPN Masukan) untuk estimasi breakdown live.
  const [taxCfg, setTaxCfg] = useState({ ppn_rate: 11, ppn_mode: "excluded", is_pkp: true });

  useEffect(() => {
    let alive = true;
    axios.get(`${API}/settings/effective`)
      .then((res) => {
        const t = res.data?.tax || {};
        if (alive) setTaxCfg({
          ppn_rate: Number(t.ppn_rate ?? 11),
          ppn_mode: t.ppn_mode || "excluded",
          is_pkp: t.is_pkp !== false,
        });
      })
      .catch(() => { /* default 11% excluded */ });
    return () => { alive = false; };
  }, []);

  const round2 = (n) => Math.round((Number(n) + Number.EPSILON) * 100) / 100;
  const clampPct = (v) => Math.min(Math.max(Number(v) || 0, 0), 100);

  // P0-1 — estimasi breakdown harga PO (mirror compute_order_pricing backend).
  const pricing = (() => {
    let gross = 0, itemDisc = 0;
    for (const it of formData.items) {
      const sub = round2((Number(it.price) || 0) * (Number(it.quantity) || 0));
      const da = round2(sub * clampPct(it.discount_percent) / 100);
      gross += sub; itemDisc += da;
    }
    gross = round2(gross); itemDisc = round2(itemDisc);
    const afterItem = round2(gross - itemDisc);
    const odp = clampPct(formData.order_discount_percent);
    const oda = round2(afterItem * odp / 100);
    const net = round2(afterItem - oda);
    const discTotal = round2(itemDisc + oda);
    const rate = Number(taxCfg.ppn_rate) || 0;
    const mode = taxCfg.ppn_mode || "excluded";
    const noTax = formData.tax_mode === "non_ppn" || !taxCfg.is_pkp || rate <= 0;
    let dpp = net, ppn = 0, grand = net;
    if (!noTax) {
      if (mode === "included") { dpp = round2(net / (1 + rate / 100)); ppn = round2(net - dpp); grand = net; }
      else { dpp = net; ppn = round2(net * rate / 100); grand = round2(net + ppn); }
    }
    return { gross, itemDisc, oda, discTotal, net, dpp, ppn, grand, rate: noTax ? 0 : rate, mode, noTax };
  })();

  function handleSupplierSelect(v) {
    if (v) {
      const s = suppliers.find((x) => x.id === v);
      setFormData({
        ...formData, supplier_id: v,
        supplier_name: s?.name || "",
        supplier_contact: s ? [s.pic_name, s.phone].filter(Boolean).join(" · ") : formData.supplier_contact,
      });
    } else {
      setFormData({ ...formData, supplier_id: "", supplier_name: "" });
    }
    setPriceHint(""); setPriceRef(0);
  }

  // Depth #3 — resolusi harga supplier untuk auto-isi item (per produk & qty).
  async function resolveItemPrice(productId, qty, baseUnit) {
    if (!productId) { setPriceHint(""); setPriceRef(0); return; }
    try {
      const res = await axios.get(`${API}/supplier-price-list/resolve`, {
        params: { supplier_id: formData.supplier_id || "", product_id: productId, qty: qty || 0 },
      });
      const r = res.data || {};
      setPriceRef(r.source === "price_list" ? Number(r.price) || 0 : 0);
      if (r.price > 0) {
        setNewItem((cur) => ({ ...cur, price: r.price, unit: r.unit || cur.unit || baseUnit }));
        setPriceHint(
          r.source === "price_list"
            ? `Harga price-list supplier: ${formatCurrency(r.price)} / ${r.unit}${r.lead_time_days ? ` · lead ${r.lead_time_days} hari` : ""}`
            : `Harga acuan produk: ${formatCurrency(r.price)} / ${r.unit} (belum ada price-list supplier)`
        );
      } else {
        setPriceHint("");
      }
    } catch (_) { /* diam: auto-isi opsional */ }
  }

  function handleItemProductSelect(v) {
    const prod = products.find((p) => p.id === v);
    const baseUnit = prod?.base_unit || newItem.unit || "meter";
    setNewItem({ ...newItem, product_id: v, unit: baseUnit });
    if (!v) { setPriceHint(""); return; }
    resolveItemPrice(v, newItem.quantity, baseUnit);
  }

  // Fase 8 (Catch-weight) — faktor kg per base unit & opsi satuan order per item.
  const selProduct = products.find((p) => p.id === newItem.product_id);
  const selBaseUnit = selProduct?.base_unit || "meter";
  const selKgPerM = selProduct
    ? (Number(selProduct.kg_per_meter) > 0
        ? Number(selProduct.kg_per_meter)
        : (Number(selProduct.gramasi || 0) * Number(selProduct.lebar || 0)) / 1000)
    : 0;
  const catchWeight = selKgPerM > 0;
  const unitOptions = (() => {
    const opts = [{ value: selBaseUnit, label: selBaseUnit }];
    if (catchWeight && selBaseUnit !== "kg") opts.push({ value: "kg", label: "kg (berat)" });
    // pertahankan unit lain bila sudah terlanjur dipilih (mis. yard via konversi variabel)
    if (newItem.unit && !opts.some((o) => o.value === newItem.unit)) opts.push({ value: newItem.unit, label: newItem.unit });
    return opts;
  })();
  const uomHint = (() => {
    const qty = Number(newItem.quantity) || 0;
    const u = (newItem.unit || "").toLowerCase();
    if (!catchWeight || qty <= 0 || u === selBaseUnit.toLowerCase()) {
      if (catchWeight && u === selBaseUnit.toLowerCase() && qty > 0)
        return `≈ ${round2(qty * selKgPerM)} kg (berat estimasi · ${selKgPerM.toFixed(3)} kg/${selBaseUnit})`;
      return "";
    }
    if (u === "kg") return `≈ ${round2(qty / selKgPerM)} ${selBaseUnit} stok (1 kg ≈ ${round2(1 / selKgPerM)} ${selBaseUnit})`;
    return "";
  })();

  function handleItemQtyChange(e) {
    const qty = parseFloat(e.target.value) || 0;
    setNewItem({ ...newItem, quantity: qty });
    if (newItem.product_id) {
      const prod = products.find((p) => p.id === newItem.product_id);
      resolveItemPrice(newItem.product_id, qty, prod?.base_unit || newItem.unit || "meter");
    }
  }
  return (
    <div data-testid="create-po-form" className="section-card mb-3">
      <div className="section-head">
        <h2 className="text-[13px] font-bold">Buat Purchase Order Baru</h2>
      </div>
      <div className="section-body space-y-3">
        {/* Header fields */}
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-[10.5px] font-semibold text-[#6B6B73] mb-1">Supplier (Master)</label>
            <KNSelect data-testid="supplier-master-select" value={formData.supplier_id || ""}
              onValueChange={handleSupplierSelect}
              className="field" placeholder="Pilih dari master / isi manual"
              options={[
                { value: "", label: "— Isi manual / tanpa master —" },
                ...activeSuppliers.map((s) => ({ value: s.id, label: `${s.code} · ${s.name}` })),
              ]}
            />
          </div>
          <div>
            <label className="block text-[10.5px] font-semibold text-[#6B6B73] mb-1">
              Nama Supplier {!formData.supplier_id && <span className="req">*</span>}
            </label>
            <input data-testid="supplier-name-input" type="text" value={formData.supplier_name}
              disabled={!!formData.supplier_id}
              onChange={(e) => setFormData({ ...formData, supplier_name: e.target.value })}
              className="field disabled:bg-gray-100 disabled:text-gray-500" placeholder="PT Supplier Textile" />
          </div>
          <div>
            <label className="block text-[10.5px] font-semibold text-[#6B6B73] mb-1">Kontak Supplier</label>
            <input data-testid="supplier-contact-input" type="text" value={formData.supplier_contact}
              onChange={(e) => setFormData({ ...formData, supplier_contact: e.target.value })}
              className="field" placeholder="081234567890" />
          </div>
          <div>
            <label className="block text-[10.5px] font-semibold text-[#6B6B73] mb-1">Warehouse *</label>
            <KNSelect data-testid="warehouse-select" value={formData.warehouse_id}
              onValueChange={v => setFormData({ ...formData, warehouse_id: v })}
              className="field" placeholder="Pilih Warehouse"
              options={[
                { value: "", label: "Pilih Warehouse" },
                ...warehouses.map(wh => ({ value: wh.id, label: `${wh.name} (${wh.code})` })),
              ]}
            />
          </div>
          <div>
            <label className="block text-[10.5px] font-semibold text-[#6B6B73] mb-1">Expected Delivery</label>
            <input data-testid="delivery-date-input" type="date" value={formData.expected_delivery_date}
              onChange={(e) => setFormData({ ...formData, expected_delivery_date: e.target.value })}
              className="field" />
          </div>
        </div>

        <div>
          <label className="block text-[10.5px] font-semibold text-[#6B6B73] mb-1">Notes</label>
          <textarea data-testid="po-notes-input" value={formData.notes}
            onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
            className="field" rows="2" placeholder="Catatan tambahan..." />
        </div>

        {/* Add Item row */}
        <div className="bg-[#FAFBFC] rounded-md border border-[#EFF0F2] p-2.5">
          <p className="text-[10.5px] font-bold uppercase text-[#6B6B73] mb-2">Tambah Item</p>
          <div className="grid grid-cols-[1fr_68px_50px_88px_56px_auto] gap-2">
            <KNSelect data-testid="item-product-select" value={newItem.product_id}
              onValueChange={handleItemProductSelect}
              className="field" placeholder="Pilih Produk"
              options={[
                { value: "", label: "Pilih Produk" },
                ...products.map(p => ({ value: p.id, label: `${p.sku} - ${p.name}` })),
              ]}
            />
            <input data-testid="item-qty-input" type="number" placeholder="Qty"
              value={newItem.quantity}
              onChange={handleItemQtyChange}
              className="field" />
            <KNSelect data-testid="item-unit-select" value={newItem.unit || selBaseUnit}
              onValueChange={(v) => setNewItem({ ...newItem, unit: v })}
              className="field" placeholder="Unit"
              options={unitOptions} />
            <input data-testid="item-price-input" type="number" placeholder="Harga"
              value={newItem.price}
              onChange={(e) => setNewItem({ ...newItem, price: parseFloat(e.target.value) || 0 })}
              className="field" />
            <input data-testid="item-discount-input" type="number" placeholder="Disc%" min="0" max="100"
              title="Diskon item (%)"
              value={newItem.discount_percent}
              onChange={(e) => setNewItem({ ...newItem, discount_percent: parseFloat(e.target.value) || 0 })}
              className="field" />
            <button data-testid="add-item-button" onClick={onAddItem}
              className="primary-button !px-3">
              <Plus size={13} />
            </button>
          </div>
          {uomHint && (
            <p data-testid="po-uom-hint" className="mt-1.5 text-[10.5px] text-[#0058CC] flex items-center gap-1">
              <Scale size={11} /> {uomHint}{Number(newItem.price) > 0 ? ` · harga per ${newItem.unit}` : ""}
            </p>
          )}
          {priceHint && (
            <p data-testid="po-price-hint" className="mt-1.5 text-[10.5px] text-[#0058CC] flex items-center gap-1">
              <Sparkles size={11} /> {priceHint}
            </p>
          )}
          {priceRef > 0 && Number(newItem.price) > priceRef && (
            <p data-testid="po-price-warning" className="mt-1 text-[10.5px] text-[#A8221A] flex items-center gap-1">
              <AlertTriangle size={11} /> Harga di atas price-list ({formatCurrency(priceRef)}) — PO mungkin butuh approval.
            </p>
          )}
        </div>

        {/* Items list + ringkasan pajak/diskon (P0-1) */}
        {formData.items.length > 0 && (
          <>
          <div className="rounded-md border border-[#EFF0F2] overflow-hidden">
            <div className="grid grid-cols-[1fr_72px_84px_52px_88px_28px] px-2.5 py-1.5 bg-[#FAFBFC] text-[10px] font-bold uppercase text-[#6B6B73] border-b border-[#EFF0F2]">
              <span>Produk</span><span>Qty</span><span>Harga</span><span>Disc</span><span className="text-right">Subtotal</span><span></span>
            </div>
            {formData.items.map((item, i) => {
              const p = products.find((pr) => pr.id === item.product_id);
              const sub = round2((Number(item.price) || 0) * (Number(item.quantity) || 0));
              const lt = round2(sub - sub * clampPct(item.discount_percent) / 100);
              return (
                <div key={i} data-testid={`po-item-row-${i}`}
                  className="grid grid-cols-[1fr_72px_84px_52px_88px_28px] items-center px-2.5 py-1.5 border-b border-[#EFF0F2] last:border-0 text-[11.5px]">
                  <span className="truncate">{p?.sku} — {p?.name}</span>
                  <span className="font-semibold">{item.quantity} {item.unit}</span>
                  <span className="tabular-nums">{formatCurrency(item.price)}</span>
                  <span data-testid={`po-item-disc-${i}`} className="tabular-nums text-[#6B6B73]">{clampPct(item.discount_percent) > 0 ? `${clampPct(item.discount_percent)}%` : "—"}</span>
                  <span data-testid={`po-item-linetotal-${i}`} className="tabular-nums text-right font-semibold">{formatCurrency(lt)}</span>
                  <button data-testid={`remove-item-${i}`} onClick={() => onRemoveItem(i)}
                    className="text-red-400 hover:text-red-600 justify-self-end">
                    <XCircle size={13} />
                  </button>
                </div>
              );
            })}
          </div>

          {/* Diskon order + mode PPN Masukan */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-[10.5px] font-semibold text-[#6B6B73] mb-1">Diskon Order (%)</label>
              <input data-testid="order-discount-input" type="number" min="0" max="100" placeholder="0"
                value={formData.order_discount_percent}
                onChange={(e) => setFormData({ ...formData, order_discount_percent: parseFloat(e.target.value) || 0 })}
                className="field" />
            </div>
            <div>
              <label className="block text-[10.5px] font-semibold text-[#6B6B73] mb-1">Pajak (PPN Masukan)</label>
              <KNSelect data-testid="po-tax-mode-select" value={formData.tax_mode || ""}
                onValueChange={(v) => setFormData({ ...formData, tax_mode: v })}
                className="field" placeholder="Ikut konfigurasi"
                options={[
                  { value: "", label: taxCfg.is_pkp ? `PPN ${taxCfg.ppn_rate}% (ikut konfigurasi)` : "Tanpa PPN (non-PKP)" },
                  { value: "non_ppn", label: "Non-PPN (supplier non-PKP)" },
                ]}
              />
            </div>
          </div>

          {/* Ringkasan estimasi harga PO */}
          <div data-testid="po-pricing-summary" className="rounded-md border border-[#EFF0F2] bg-[#FAFBFC] p-3 text-[11.5px] space-y-1">
            <p className="flex items-center gap-1.5 text-[10.5px] font-bold uppercase text-[#6B6B73] mb-1.5"><Receipt size={12} /> Ringkasan (Estimasi)</p>
            <div className="flex justify-between"><span className="text-[#6B6B73]">Subtotal</span><span data-testid="summary-subtotal" className="tabular-nums">{formatCurrency(pricing.gross)}</span></div>
            {pricing.itemDisc > 0 && <div className="flex justify-between"><span className="text-[#6B6B73]">Diskon item</span><span data-testid="summary-item-discount" className="tabular-nums text-[#A8221A]">− {formatCurrency(pricing.itemDisc)}</span></div>}
            {pricing.oda > 0 && <div className="flex justify-between"><span className="text-[#6B6B73]">Diskon order</span><span data-testid="summary-order-discount" className="tabular-nums text-[#A8221A]">− {formatCurrency(pricing.oda)}</span></div>}
            <div className="flex justify-between"><span className="text-[#6B6B73]">DPP</span><span data-testid="summary-dpp" className="tabular-nums">{formatCurrency(pricing.dpp)}</span></div>
            <div className="flex justify-between"><span className="text-[#6B6B73]">PPN {pricing.rate > 0 ? `(${pricing.rate}%)` : ""}</span><span data-testid="summary-ppn" className="tabular-nums">{pricing.noTax ? "—" : formatCurrency(pricing.ppn)}</span></div>
            <div className="flex justify-between pt-1.5 mt-1 border-t border-[#E5E6E8] font-bold text-[12.5px]"><span>Total</span><span data-testid="summary-grand-total" className="tabular-nums text-[#007AFF]">{formatCurrency(pricing.grand)}</span></div>
          </div>
          </>
        )}

        <div className="flex gap-2">
          <button data-testid="submit-po-button" onClick={onSubmit} disabled={submitting}
            className="flex-1 primary-button justify-center">
            {submitting ? "Memproses…" : "Buat PO & Auto-create Inbound Tasks"}
          </button>
          <button data-testid="cancel-form-button" onClick={onCancel} disabled={submitting}
            className="secondary-button">
            Batal
          </button>
        </div>
      </div>
    </div>
  );
}
