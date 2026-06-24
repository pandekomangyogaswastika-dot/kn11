import { Plus, Info, Layers } from "lucide-react";
import { formatCurrency, formatQty } from "../../../utils/formatters";

/** EPIC-VAR — Kartu produk MOBILE (group-aware, kompak). Klik membuka MobileQuickView. */
export function MobileProductCard({ group, onOpen, specialMap = {} }) {
  const rep = group.base;
  const total = group.totalAvailable;
  const availState = total <= 0 ? "habis" : total <= 40 ? "low" : "ready";
  const availLabel = { habis: "Habis", low: "Rendah", ready: "Tersedia" }[availState];
  const availPill = { habis: "status-cancelled", low: "status-waiting_approval", ready: "status-confirmed" }[availState];
  const anySpecial = group.variants.some((v) => specialMap[v.id]?.has_special);
  const priceText = group.isMulti && group.priceMin !== group.priceMax
    ? `${formatCurrency(group.priceMin)}+`
    : formatCurrency(group.priceMin);

  return (
    <article data-testid={`mobile-product-${rep.id}`} className="flex flex-col overflow-hidden rounded-xl border border-[#E5E5EA] bg-white">
      <button data-testid={`mobile-product-image-${rep.id}`} className="relative block w-full text-left" onClick={() => onOpen(group)}>
        <img src={group.image} alt={group.name} className="h-28 w-full object-cover" />
        <span className="absolute right-1.5 top-1.5 rounded-md bg-black/85 px-1.5 py-0.5 text-[9px] font-bold text-white">{rep.grade}</span>
        {group.isMulti
          ? <span className="absolute left-1.5 top-1.5 inline-flex items-center gap-0.5 rounded-full bg-[#0058CC] px-1.5 py-0.5 text-[8.5px] font-bold text-white"><Layers size={9} /> {group.variants.length} varian</span>
          : <span className={`status-pill ${availPill} absolute left-1.5 top-1.5 scale-90`}>{availLabel}</span>}
        {anySpecial && <span className="absolute left-1.5 bottom-1.5 rounded-full bg-[#6B219A] px-1.5 py-0.5 text-[8.5px] font-bold text-white">Harga khusus</span>}
      </button>
      <div className="flex flex-1 flex-col p-2.5">
        <p data-testid={`mobile-product-sku-${rep.id}`} className="text-[9.5px] font-bold uppercase tracking-wide text-[#0058CC]">{group.isMulti ? rep.category : rep.sku}</p>
        <h3 data-testid={`mobile-product-name-${rep.id}`} className="mt-0.5 line-clamp-2 text-[12.5px] font-semibold leading-tight">{group.name}</h3>
        <p className="mt-0.5 line-clamp-1 text-[10.5px] text-[#6B6B73]">{group.isMulti ? `${group.variants.length} warna/grade` : rep.color}</p>
        <p data-testid={`mobile-product-price-${rep.id}`} className="mt-1.5 text-[14px] font-bold tabular-nums text-[#1C1C1E]">{priceText}<span className="text-[9.5px] font-medium text-[#8E8E93]">/{rep.base_unit || "meter"}</span></p>
        <p className="text-[10px] text-[#6B6B73]"><b data-testid={`mobile-product-rolls-${rep.id}`} className="text-[#1C1C1E]">{group.totalRolls || 0} roll</b> / <b data-testid={`mobile-product-available-${rep.id}`} className="text-[#126E2C]">{formatQty(total)}</b> {rep.base_unit || "meter"}</p>
        <div className="mt-2 flex gap-1.5">
          <button data-testid={`mobile-add-${rep.id}`} className="primary-button flex-1 justify-center py-2 text-[12px]" disabled={availState === "habis"} onClick={() => onOpen(group)}>
            <Plus size={13} /> {availState === "habis" ? "Habis" : (group.isMulti ? "Pilih" : "Tambah")}
          </button>
          <button data-testid={`mobile-detail-${rep.id}`} className="secondary-button px-2.5 py-2" onClick={() => onOpen(group)} aria-label="Detail"><Info size={14} /></button>
        </div>
      </div>
    </article>
  );
}
