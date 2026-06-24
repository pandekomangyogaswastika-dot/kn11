import { useEffect, useMemo, useState } from "react";
import { X, Plus, Minus, ShoppingBag, Printer, ChevronDown, Boxes, Layers } from "lucide-react";
import axios, { API } from "../services/apiClient";
import { formatCurrency, formatQty } from "../utils/formatters";
import { variantLabel } from "../utils/variants";
import LabelPrinterModal from "./LabelPrinterModal";

/**
 * ProductQuickView — popup (desktop) detail produk + pemilih varian.
 * Klik kartu / "Tambah" / "Detail" membuka popup ini. Semua detail (stok,
 * harga, lot per gudang), pemilihan varian & qty ada di sini. Satuan FIXED ke
 * base_unit (F2 UoM SSOT — POS tidak memilih satuan). z-[140].
 */
export default function ProductQuickView({ open, group, specialMap = {}, onAdd, onClose, initialExpanded = false }) {
  const variants = useMemo(() => group?.variants || [], [group]);
  const [selectedId, setSelectedId] = useState(null);
  const [qty, setQty] = useState(1);
  const [expanded, setExpanded] = useState(false);
  const [breakdown, setBreakdown] = useState(null);
  const [loadingBd, setLoadingBd] = useState(false);
  const [showLabel, setShowLabel] = useState(false);

  // Pilih varian default saat popup dibuka.
  useEffect(() => {
    if (!open || variants.length === 0) return;
    const firstAvail = variants.find((v) => Number(v.available_qty || 0) > 0) || variants[0];
    setSelectedId(firstAvail.id);
    setQty(1);
    setExpanded(!!initialExpanded);
    setBreakdown(null);
  }, [open, group]); // eslint-disable-line

  const selected = useMemo(
    () => variants.find((v) => v.id === selectedId) || variants[0] || null,
    [variants, selectedId]
  );

  // Fetch stok per gudang saat "Lanjutan" dibuka / varian berubah.
  useEffect(() => {
    if (!open || !expanded || !selected) return undefined;
    let cancelled = false;
    setLoadingBd(true); setBreakdown(null);
    axios.get(`${API}/products/${selected.id}/stock-breakdown`)
      .then((r) => { if (!cancelled) setBreakdown(r.data); })
      .catch(() => { if (!cancelled) setBreakdown({ balances: [], ownership_matrix: [] }); })
      .finally(() => { if (!cancelled) setLoadingBd(false); });
    return () => { cancelled = true; };
  }, [open, expanded, selectedId]); // eslint-disable-line

  if (!open || !selected) return null;

  const special = specialMap[selected.id];
  const isSpecial = !!(special && special.has_special);
  const baseUnit = selected.base_unit || "meter";
  const unitPrice = isSpecial ? Number(special.requested_price) : Number(selected.price || 0);
  const avail = Number(selected.available_qty || 0);
  const reserved = Number(selected.reserved_qty || 0);
  const rollCount = Number(selected.roll_count || 0);
  // F3 — deskripsi ikut varian terpilih; fallback ke deskripsi grup (rep).
  const description = (selected.description || group.description || "").trim();
  const availState = avail <= 0 ? "habis" : avail <= 40 ? "low" : "ready";
  const availPill = { habis: "status-cancelled", low: "status-waiting_approval", ready: "status-confirmed" }[availState];
  const availLabel = { habis: "Habis", low: "Stok rendah", ready: "Tersedia" }[availState];
  const lineTotal = unitPrice * (Number(qty) || 0);
  const step = (d) => setQty((q) => Math.max(1, Number(q || 1) + d));

  return (
    <div data-testid="product-quickview" className="fixed inset-0 z-[140] flex items-center justify-center bg-black/50 p-4" onClick={onClose}>
      <div className="flex max-h-[90vh] w-full max-w-[560px] flex-col overflow-hidden rounded-xl bg-white shadow-2xl" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="flex items-start justify-between gap-3 border-b border-[#EFF0F2] px-4 py-3">
          <div className="min-w-0">
            <p className="text-[10.5px] font-bold uppercase tracking-wide text-[#0058CC]">
              {group.category}{group.isMulti ? ` · ${variants.length} varian` : ""}
            </p>
            <h2 data-testid="quickview-product-name" className="text-[16px] font-bold leading-tight">{group.name}</h2>
          </div>
          <button data-testid="quickview-close" className="icon-button" onClick={onClose} aria-label="Tutup"><X size={18} /></button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          <div className="grid gap-3 sm:grid-cols-[180px_1fr]">
            <div className="relative">
              <img data-testid="quickview-image" src={selected.image} alt={group.name} className="aspect-[4/3] w-full rounded-lg border border-[#EFF0F2] object-cover" />
              <span className={`status-pill ${availPill} absolute left-2 top-2`}>{availLabel}</span>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 content-start">
              <Stat label="Tersedia" value={formatQty(avail)} tone="#126E2C" testId="quickview-available" />
              <Stat label="Roll" value={`${rollCount} roll`} tone="#1C1C1E" testId="quickview-roll-count" />
              <Stat label="Reserved" value={formatQty(reserved)} tone="#6B219A" testId="quickview-reserved" />
              <Stat label={`Harga/${baseUnit}`} value={formatCurrency(selected.price)} tone="#1C1C1E" small testId="quickview-base-price" />
            </div>
          </div>

          {/* Pemilih varian */}
          <div>
            <label className="mb-1 flex items-center gap-1 text-[10px] font-bold uppercase tracking-wide text-[#6B6B73]"><Layers size={11} /> Pilih Varian</label>
            <div className="flex flex-wrap gap-2" data-testid="quickview-variant-list">
              {variants.map((v) => {
                const va = Number(v.available_qty || 0);
                const active = v.id === selected.id;
                return (
                  <button key={v.id} data-testid={`quickview-variant-${v.id}`} onClick={() => setSelectedId(v.id)}
                    className={`rounded-lg border px-2.5 py-1.5 text-left transition ${active ? "border-[#0058CC] bg-[#EAF2FF] ring-1 ring-[#0058CC]" : "border-[#E5E5EA] bg-white hover:border-[#9A9BA3]"}`}>
                    <span className="block text-[12px] font-semibold text-[#1C1C1E]">{variantLabel(v)}</span>
                    <span className={`block text-[10px] ${va <= 0 ? "text-[#A8221A]" : "text-[#6B6B73]"}`}>
                      {va <= 0 ? "Habis" : `Stok ${formatQty(va)}`} · {formatCurrency(v.price)}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>

          {isSpecial && (
            <p data-testid="quickview-special" className="inline-flex items-center gap-1 rounded-full bg-[#F3E9FA] px-2 py-0.5 text-[10.5px] font-bold text-[#6B219A]">
              Harga khusus {formatCurrency(unitPrice)} <span className="font-normal text-[#8E8E93] line-through">{formatCurrency(special.normal_price)}</span>
            </p>
          )}
          <p className="text-[11.5px] text-[#3C3C43]">
            <span data-testid="quickview-sku" className="font-semibold text-[#0058CC]">{selected.sku}</span> · {selected.color} • {selected.motif} • Grade {selected.grade}
          </p>

          {/* F3 — Deskripsi produk (ikut varian terpilih) */}
          {description && (
            <div data-testid="quickview-description" className="rounded-lg border border-[#EFF0F2] bg-[#FAFBFC] p-2.5 text-[11.5px] leading-relaxed text-[#3C3C43] whitespace-pre-line">
              {description}
            </div>
          )}

          {/* Qty + Satuan (FIXED ke base_unit — F2 UoM SSOT: POS tidak memilih satuan) */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1 block text-[10px] font-bold uppercase tracking-wide text-[#8E8E93]">Jumlah (Qty)</label>
              <div className="flex items-center rounded-md border border-[#E5E5EA]">
                <button data-testid="quickview-qty-minus" className="px-3 py-2 text-[#6B6B73] hover:bg-[#F5F5F7]" onClick={() => step(-1)} aria-label="Kurangi"><Minus size={14} /></button>
                <input data-testid="quickview-qty-input" type="number" min="1" className="w-full border-x border-[#E5E5EA] bg-transparent py-2 text-center text-[14px] outline-none" value={qty} onChange={(e) => setQty(Math.max(1, Number(e.target.value) || 1))} />
                <button data-testid="quickview-qty-plus" className="px-3 py-2 text-[#6B6B73] hover:bg-[#F5F5F7]" onClick={() => step(1)} aria-label="Tambah"><Plus size={14} /></button>
              </div>
            </div>
            <div className="min-w-0">
              <label className="mb-1 block text-[10px] font-bold uppercase tracking-wide text-[#8E8E93]">Satuan</label>
              <div data-testid="quickview-unit-fixed" className="field flex items-center bg-[#F5F5F7] font-semibold text-[#3C3C43]">{baseUnit}</div>
              <p className="mt-1 text-[10px] text-[#9A9BA3]">{rollCount} roll · panjang per roll bervariasi</p>
            </div>
          </div>

          {/* Lanjutan — stok per gudang/lot */}
          <button data-testid="quickview-detail-toggle" onClick={() => setExpanded((v) => !v)} className="flex w-full items-center justify-between rounded-md border border-[#EFF0F2] bg-[#FAFBFC] px-3 py-2 text-[11.5px] font-semibold text-[#3C3C43]">
            <span className="flex items-center gap-1.5"><Boxes size={13} /> Lanjutan — stok per gudang, lot & entitas</span>
            <ChevronDown size={14} className={`transition ${expanded ? "rotate-180" : ""}`} />
          </button>
          {expanded && (
            <div data-testid="quickview-breakdown" className="overflow-hidden rounded-md border border-[#EFF0F2]">
              <div className="grid grid-cols-5 bg-[#FAFBFC] px-3 py-1.5 text-[10px] font-bold uppercase tracking-wide text-[#6B6B73]">
                <span>Gudang</span><span>Kota</span><span className="text-right">On Hand</span><span className="text-right">Reserved</span><span className="text-right">Available</span>
              </div>
              {loadingBd && <div className="px-3 py-3 text-center text-[11.5px] text-[#6B6B73] animate-pulse">Memuat stok…</div>}
              {!loadingBd && (breakdown?.balances || []).length === 0 && <div className="px-3 py-3 text-center text-[11.5px] text-[#6B6B73]">Belum ada data stok per gudang.</div>}
              {!loadingBd && (breakdown?.balances || []).map((row) => (
                <div key={row.warehouse_id} className="grid grid-cols-5 border-t border-[#EFF0F2] px-3 py-1.5 text-[11px]">
                  <span className="truncate font-semibold">{row.warehouse_name}</span>
                  <span className="truncate">{row.warehouse_city}</span>
                  <span className="text-right">{formatQty(row.on_hand_qty)}</span>
                  <span className="text-right text-[#FF9500]">{formatQty(row.reserved_qty)}</span>
                  <span className="text-right text-[#126E2C]">{formatQty(row.available_qty)}</span>
                </div>
              ))}
              {!loadingBd && (breakdown?.ownership_matrix || []).length > 0 && (
                <div className="border-t border-[#E0E7FF]">
                  <div className="bg-[#EEF2FF] px-3 py-1.5 text-[10px] font-bold uppercase tracking-wide text-[#4338CA]">Kepemilikan · Lot · Gudang</div>
                  {(breakdown.ownership_matrix || []).map((cell, i) => (
                    <div key={i} className="grid grid-cols-4 border-t border-[#EFF0F2] px-3 py-1.5 text-[11px]">
                      <span className="truncate font-semibold text-[#4338CA]">{cell.owner_entity_name}</span>
                      <span className="truncate">{cell.warehouse_name}</span>
                      <span className="font-mono text-[10px]">{cell.lot}</span>
                      <span className="text-right font-semibold text-[#126E2C]">{formatQty(cell.available_qty)}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="border-t border-[#EFF0F2] px-4 py-3">
          <div className="mb-2 flex items-center justify-between">
            <span className="text-[11px] font-bold uppercase tracking-wide text-[#6B6B73]">Subtotal ({qty} {baseUnit})</span>
            <span data-testid="quickview-line-total" className="text-[16px] font-bold tabular-nums">{formatCurrency(lineTotal)}</span>
          </div>
          <div className="flex gap-2">
            <button data-testid="quickview-add-button" className="primary-button flex-1 justify-center py-2.5" disabled={avail <= 0} onClick={() => { onAdd(selected, qty, baseUnit); onClose(); }}>
              <ShoppingBag size={15} /> {avail <= 0 ? "Stok Habis" : "Tambah ke Keranjang"}
            </button>
            <button data-testid="quickview-print-button" className="secondary-button px-3" onClick={() => setShowLabel(true)} aria-label="Print Label"><Printer size={15} /></button>
          </div>
        </div>

        {showLabel && <LabelPrinterModal product={selected} warehouse={null} onClose={() => setShowLabel(false)} />}
      </div>
    </div>
  );
}

function Stat({ label, value, tone, testId, small }) {
  return (
    <div className="rounded-md border border-[#EFF0F2] bg-[#FAFBFC] p-2">
      <p className="text-[9.5px] font-bold uppercase text-[#6B6B73]">{label}</p>
      <p data-testid={testId} className={`${small ? "text-[12px]" : "text-[15px]"} font-bold leading-tight`} style={{ color: tone }}>{value}</p>
    </div>
  );
}
