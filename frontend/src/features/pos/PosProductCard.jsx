import { Plus, Layers, Repeat } from "lucide-react";
import { formatCurrency, formatQty } from "../../utils/formatters";

/**
 * EPIC-VAR — kartu produk POS (group-aware & ringkas).
 * Kartu menampilkan grup produk (1+ varian). Klik gambar / "Tambah"("Pilih Varian")
 * / "Detail" semuanya membuka ProductQuickView (popup) — qty, satuan, varian, dan
 * detail stok dipindahkan ke popup.
 */
export function PosProductCard({ group, specialMap = {}, onOpen, reorder }) {
  const rep = group.base;
  const total = group.totalAvailable;
  const availState = total <= 0 ? "habis" : total <= 40 ? "low" : "ready";
  const availLabel = { habis: "Habis", low: "Stok rendah", ready: "Tersedia" }[availState];
  const availPill = { habis: "status-cancelled", low: "status-waiting_approval", ready: "status-confirmed" }[availState];
  const anySpecial = group.variants.some((v) => specialMap[v.id]?.has_special);
  const priceText = group.isMulti && group.priceMin !== group.priceMax
    ? `${formatCurrency(group.priceMin)} – ${formatCurrency(group.priceMax)}`
    : formatCurrency(group.priceMin);
  const open = (expand = false) => onOpen(group, expand);

  return (
    <article data-testid={`product-card-${rep.id}`} className="product-card flex flex-col">
      <button data-testid={`product-image-button-${rep.id}`} className="relative block w-full text-left" onClick={() => open(true)}>
        <img data-testid={`product-image-${rep.id}`} src={group.image} alt={group.name} className="product-image" loading="lazy" decoding="async" />
        <span data-testid={`product-grade-${rep.id}`} className="absolute right-2 top-2 rounded-md bg-black/85 px-1.5 py-0.5 text-[10px] font-bold text-white">{rep.grade}</span>
        {group.isMulti && (
          <span data-testid={`product-variant-count-${rep.id}`} className="absolute left-2 top-2 inline-flex items-center gap-1 rounded-full bg-[#0058CC] px-2 py-0.5 text-[9.5px] font-bold text-white"><Layers size={10} /> {group.variants.length} varian</span>
        )}
        {anySpecial && (
          <span data-testid={`product-special-badge-${rep.id}`} className="absolute left-2 bottom-2 rounded-full bg-[#6B219A] px-2 py-0.5 text-[9.5px] font-bold text-white">Harga khusus</span>
        )}
        {reorder && (
          <span className="absolute right-2 bottom-2 inline-flex items-center gap-1 rounded-full bg-black/80 px-2 py-0.5 text-[9.5px] font-bold text-white"><Repeat size={10} /> {reorder.reorder_count}×</span>
        )}
      </button>
      <div className="flex flex-1 flex-col p-3">
        <p data-testid={`product-sku-${rep.id}`} className="text-[10.5px] font-bold uppercase tracking-wide text-[#0058CC]">{group.isMulti ? rep.category : rep.sku}</p>
        <h3 data-testid={`product-name-${rep.id}`} className="mt-0.5 text-[14px] font-semibold leading-tight line-clamp-2">{group.name}</h3>
        <p className="mt-0.5 text-[11px] text-[#6B6B73] line-clamp-1">{group.isMulti ? `${group.variants.length} pilihan warna/grade` : `${rep.category} • ${rep.color}`}</p>

        <div className="mt-2 flex items-center justify-between gap-2">
          <p data-testid={`product-price-${rep.id}`} className="text-[14px] font-bold tabular-nums text-[#1C1C1E]">{priceText}<span className="text-[10px] font-medium text-[#8E8E93]">/{rep.base_unit || "meter"}</span></p>
          <span data-testid={`product-stock-badge-${rep.id}`} className={`status-pill ${availPill}`}>{availLabel}</span>
        </div>
        <p className="mt-1 text-[10.5px] text-[#6B6B73]"><b data-testid={`product-rolls-${rep.id}`} className="text-[#1C1C1E]">{group.totalRolls || 0} roll</b> / <b data-testid={`product-available-${rep.id}`} className="text-[#126E2C]">{formatQty(total)}</b> {rep.base_unit || "meter"} tersedia</p>

        <div className="mt-2">
          <button data-testid={`add-to-cart-button-${rep.id}`} className="primary-button w-full" disabled={availState === "habis"} onClick={() => open(true)}>
            <Plus size={13} /> {group.isMulti ? "Pilih Varian & Detail" : "Lihat Detail & Tambah"}
          </button>
        </div>
      </div>
    </article>
  );
}
