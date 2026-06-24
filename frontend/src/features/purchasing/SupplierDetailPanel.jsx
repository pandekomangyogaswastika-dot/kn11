import { useState } from "react";
import { X, Info, Tag, BarChart3, Building2, Truck, Clock } from "lucide-react";
import SupplierPriceList from "./SupplierPriceList";
import SupplierScorecard from "./SupplierScorecard";

/**
 * SupplierDetailPanel (Depth #3) — modal detail supplier dengan 3 tab:
 *   Info · Daftar Harga (price-list CRUD) · Scorecard (metrik dari data nyata).
 */
const TABS = [
  { id: "info", label: "Info", icon: Info },
  { id: "price", label: "Daftar Harga", icon: Tag },
  { id: "scorecard", label: "Scorecard", icon: BarChart3 },
];

function InfoRow({ label, value }) {
  return (
    <div className="flex items-start justify-between gap-3 py-1.5 border-b border-[#F2F3F5] last:border-0">
      <span className="text-[11px] text-[#6B6B73]">{label}</span>
      <span className="text-[12px] font-medium text-right">{value || "—"}</span>
    </div>
  );
}

export default function SupplierDetailPanel({ supplier, currentUser, onClose }) {
  const [tab, setTab] = useState("info");
  const canManage = ["admin", "manager"].includes(currentUser?.role);
  if (!supplier) return null;

  return (
    <div className="modal-overlay" data-testid="supplier-detail-modal" onClick={onClose}>
      <div className="modal-card wide" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="flex items-start justify-between mb-3">
          <div className="flex items-center gap-2.5 min-w-0">
            <div className="w-9 h-9 rounded-lg bg-[#EFF4FF] flex items-center justify-center shrink-0">
              <Truck size={17} className="text-[#0058CC]" />
            </div>
            <div className="min-w-0">
              <p data-testid="supplier-detail-name" className="modal-title truncate">{supplier.name}</p>
              <p className="text-[11px] text-[#6B6B73] flex items-center gap-2 flex-wrap">
                <span className="font-bold text-[#0058CC]">{supplier.code}</span>
                {supplier.city && <span className="flex items-center gap-1"><Building2 size={10} />{supplier.city}</span>}
                {supplier.lead_time_days > 0 && <span className="flex items-center gap-1"><Clock size={10} />{supplier.lead_time_days} hari lead</span>}
              </p>
            </div>
          </div>
          <button data-testid="supplier-detail-close" className="icon-button" onClick={onClose}><X size={16} /></button>
        </div>

        {/* Tabs */}
        <div className="tab-bar">
          {TABS.map((t) => {
            const Icon = t.icon;
            return (
              <button key={t.id} data-testid={`supplier-tab-${t.id}`}
                className={`tab-button ${tab === t.id ? "active" : ""}`} onClick={() => setTab(t.id)}>
                <Icon size={14} /> {t.label}
              </button>
            );
          })}
        </div>

        {/* Tab content */}
        {tab === "info" && (
          <div data-testid="supplier-tab-info-content" className="section-card">
            <div className="section-body">
              <InfoRow label="Nama" value={supplier.name} />
              <InfoRow label="Kode" value={supplier.code} />
              <InfoRow label="NPWP" value={supplier.npwp} />
              <InfoRow label="PIC" value={supplier.pic_name} />
              <InfoRow label="Telepon" value={supplier.phone} />
              <InfoRow label="Email" value={supplier.email} />
              <InfoRow label="Alamat" value={supplier.address} />
              <InfoRow label="Kota" value={supplier.city} />
              <InfoRow label="Jenis Barang" value={supplier.goods_type} />
              <InfoRow label="Term Pembayaran" value={supplier.payment_term_code} />
              <InfoRow label="Lead Time Default" value={`${supplier.lead_time_days || 0} hari`} />
              <InfoRow label="Status" value={supplier.status === "active" ? "Aktif" : "Nonaktif"} />
              <InfoRow label="Catatan" value={supplier.notes} />
            </div>
          </div>
        )}
        {tab === "price" && <SupplierPriceList supplierId={supplier.id} canManage={canManage} />}
        {tab === "scorecard" && <SupplierScorecard supplierId={supplier.id} />}
      </div>
    </div>
  );
}
