/**
 * Shared constants & tiny presentational helpers untuk modul Purchase Requisition (Depth #2a).
 * Dipakai oleh PurchaseRequisitions.jsx (list/create) & PurchaseRequisitionDetail.jsx.
 */

export const STATUS_STYLE = {
  draft:            { cls: "pill-muted",   label: "Draft" },
  pending_approval: { cls: "pill-warning", label: "Menunggu Approval" },
  approved:         { cls: "pill-success", label: "Disetujui" },
  converted:        { cls: "pill-info",    label: "Jadi PO" },
  rejected:         { cls: "pill-danger",  label: "Ditolak" },
  cancelled:        { cls: "pill-muted",   label: "Dibatalkan" },
};

export const SOURCE_LABEL = {
  manual: "Manual", reorder: "Reorder", special_order: "Special Order",
};

export function StatusPill({ status }) {
  const s = STATUS_STYLE[status] || { cls: "pill-muted", label: status };
  return <span className={`status-pill ${s.cls}`}>{s.label}</span>;
}

export function Field({ label, value }) {
  return (
    <div>
      <p className="text-[10px] font-bold uppercase tracking-wide text-[#8E8E93]">{label}</p>
      <p className="text-[12.5px] font-semibold tabular-nums">{value}</p>
    </div>
  );
}
