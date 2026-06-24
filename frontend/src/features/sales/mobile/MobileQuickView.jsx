import { useEffect, useMemo, useState } from "react";
import { X, Plus, Minus, ShoppingBag, ChevronDown, Boxes } from "lucide-react";
import axios, { API } from "../../../services/apiClient";
import { formatCurrency, formatQty } from "../../../utils/formatters";
import { unitOptions, convFactor } from "../../../utils/uom";
import { variantLabel } from "../../../utils/variants";
import KNSelect from "../../../components/KNSelect";

/** EPIC-VAR — bottom-sheet detail produk + pemilih varian (versi MOBILE). */
export default function MobileQuickView({ group, specialMap = {}, onAdd, onClose }) {
  const variants = useMemo(() => group?.variants || [], [group]);
  const [selectedId, setSelectedId] = useState(null);
  const [qty, setQty] = useState(1);
  const [unit, setUnit] = useState("meter");
  const [expanded, setExpanded] = useState(false);
  const [breakdown, setBreakdown] = useState(null);
  const [loadingBd, setLoadingBd] = useState(false);

  useEffect(() => {
    if (!group || variants.length === 0) return;
    const fa = variants.find((v) => Number(v.available_qty || 0) > 0) || variants[0];
    setSelectedId(fa.id); setQty(1); setUnit(fa.base_unit || "meter"); setExpanded(false); setBreakdown(null);
  }, [group]); // eslint-disable-line

  const selected = useMemo(() => variants.find((v) => v.id === selectedId) || variants[0] || null, [variants, selectedId]);
  useEffect(() => { if (selected) setUnit(selected.base_unit || "meter"); }, [selectedId]); // eslint-disable-line
  useEffect(() => {
    if (!expanded || !selected) return undefined;
    let c = false; setLoadingBd(true); setBreakdown(null);
    axios.get(`${API}/products/${selected.id}/stock-breakdown`)
      .then((r) => { if (!c) setBreakdown(r.data); })
      .catch(() => { if (!c) setBreakdown({ balances: [] }); })
      .finally(() => { if (!c) setLoadingBd(false); });
    return () => { c = true; };
  }, [expanded, selectedId]); // eslint-disable-line

  if (!group || !selected) return null;
  const special = specialMap[selected.id];
  const isSpecial = !!(special && special.has_special);
  const baseUnit = selected.base_unit || "meter";
  const factor = convFactor(selected, unit) ?? 1;
  const unitPrice = isSpecial ? Number(special.requested_price) : Math.round((selected.price || 0) * factor * 100) / 100;
  const avail = Number(selected.available_qty || 0);
  const lineTotal = unitPrice * (Number(qty) || 0);
  const step = (d) => setQty((q) => Math.max(1, Number(q || 1) + d));

  return (
    <div className="m-sheet-wrap" data-testid="mobile-quickview">
      <div className="m-sheet-backdrop" onClick={onClose} />
      <div className="m-sheet">
        <div className="m-sheet-grip" />
        <div className="flex items-center justify-between px-4 pb-1">
          <div className="min-w-0">
            <p className="text-[9.5px] font-bold uppercase tracking-wide text-[#0058CC]">{group.category}{group.isMulti ? ` · ${variants.length} varian` : ""}</p>
            <h3 className="m-section-title truncate">{group.name}</h3>
          </div>
          <button data-testid="mobile-quickview-close" onClick={onClose} aria-label="Tutup" className="text-[#6B6B73]"><X size={18} /></button>
        </div>
        <div className="overflow-y-auto px-4 pb-4" style={{ maxHeight: "74vh" }}>
          <img src={selected.image} alt={group.name} className="h-40 w-full rounded-xl object-cover" />
          <div className="mt-2 flex items-end justify-between">
            <p data-testid="mobile-quickview-price" className="text-[20px] font-bold tabular-nums">{formatCurrency(unitPrice)}<span className="text-[11px] font-medium text-[#8E8E93]">/{unit}</span></p>
            <p className="text-[12px] m-muted">Stok <b className="text-[#126E2C]">{formatQty(avail)}</b> {baseUnit}</p>
          </div>
          {isSpecial && <p className="mt-1 inline-block rounded-full bg-[#F3E9FA] px-2 py-0.5 text-[10.5px] font-bold text-[#6B219A]">Harga khusus · normal {formatCurrency(special.normal_price)}</p>}

          <p className="mt-3 text-[10px] font-bold uppercase tracking-wide text-[#6B6B73]">Pilih Varian</p>
          <div className="mt-1 flex flex-wrap gap-2" data-testid="mobile-quickview-variants">
            {variants.map((v) => {
              const va = Number(v.available_qty || 0); const active = v.id === selected.id;
              return (
                <button key={v.id} data-testid={`mobile-quickview-variant-${v.id}`} onClick={() => setSelectedId(v.id)}
                  className={`rounded-lg border px-2.5 py-1.5 text-left ${active ? "border-[#0058CC] bg-[#EAF2FF]" : "border-[#E5E5EA] bg-white"}`}>
                  <span className="block text-[12px] font-semibold">{variantLabel(v)}</span>
                  <span className={`block text-[10px] ${va <= 0 ? "text-[#A8221A]" : "text-[#6B6B73]"}`}>{va <= 0 ? "Habis" : `Stok ${formatQty(va)}`} · {formatCurrency(v.price)}</span>
                </button>
              );
            })}
          </div>

          <div className="mt-3 grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1 block text-[10px] font-bold uppercase tracking-wide text-[#8E8E93]">Qty</label>
              <div className="flex items-center rounded-lg border border-[#E5E5EA]">
                <button data-testid="mobile-quickview-qty-minus" className="px-3 py-2.5 text-[#6B6B73]" onClick={() => step(-1)} aria-label="Kurangi"><Minus size={15} /></button>
                <input data-testid="mobile-quickview-qty-input" type="number" min="1" className="w-full border-x border-[#E5E5EA] bg-transparent py-2 text-center text-[15px] outline-none" value={qty} onChange={(e) => setQty(Math.max(1, Number(e.target.value) || 1))} />
                <button data-testid="mobile-quickview-qty-plus" className="px-3 py-2.5 text-[#6B6B73]" onClick={() => step(1)} aria-label="Tambah"><Plus size={15} /></button>
              </div>
            </div>
            <div className="min-w-0">
              <label className="mb-1 block text-[10px] font-bold uppercase tracking-wide text-[#8E8E93]">Satuan</label>
              <KNSelect data-testid="mobile-quickview-unit-select" className="field w-full" value={unit} onValueChange={setUnit} options={unitOptions(selected)} />
            </div>
          </div>

          <button data-testid="mobile-quickview-detail-toggle" onClick={() => setExpanded((v) => !v)} className="mt-3 flex w-full items-center justify-between rounded-lg border border-[#EFF0F2] bg-[#FAFBFC] px-3 py-2 text-[11.5px] font-semibold text-[#3C3C43]">
            <span className="flex items-center gap-1.5"><Boxes size={13} /> Stok per gudang &amp; lot</span>
            <ChevronDown size={14} className={`transition ${expanded ? "rotate-180" : ""}`} />
          </button>
          {expanded && (
            <div className="mt-2 overflow-hidden rounded-lg border border-[#EFF0F2]">
              {loadingBd && <div className="px-3 py-3 text-center text-[11.5px] text-[#6B6B73] animate-pulse">Memuat…</div>}
              {!loadingBd && (breakdown?.balances || []).length === 0 && <div className="px-3 py-3 text-center text-[11.5px] text-[#6B6B73]">Belum ada data.</div>}
              {!loadingBd && (breakdown?.balances || []).map((row) => (
                <div key={row.warehouse_id} className="flex items-center justify-between border-b border-[#EFF0F2] px-3 py-1.5 text-[11.5px] last:border-0">
                  <span className="font-semibold">{row.warehouse_name}</span>
                  <span className="text-[#126E2C]">Avail {formatQty(row.available_qty)}</span>
                </div>
              ))}
            </div>
          )}

          <button data-testid="mobile-quickview-add" disabled={avail <= 0}
            className="primary-button mt-4 w-full justify-center py-3 text-[14px]"
            onClick={() => { onAdd(selected, qty, unit); onClose(); }}>
            <ShoppingBag size={16} /> {avail <= 0 ? "Stok Habis" : `Tambah ${qty} ${unit} · ${formatCurrency(lineTotal)}`}
          </button>
        </div>
      </div>
    </div>
  );
}
