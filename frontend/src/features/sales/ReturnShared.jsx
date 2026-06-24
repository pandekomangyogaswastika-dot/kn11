/** Shared components for the Returns feature. */
const RETURN_TYPE_LABEL = {
  retur:       "Retur",
  bs:          "Barang Sisa (BS)",
  penggantian: "Penggantian",
  komplain:    "Komplain",
  garansi:     "Garansi",
};
const STATUS_STYLE = {
  draft:            { cls: "pill-muted",   label: "Draft" },
  pending_approval: { cls: "pill-warning", label: "Menunggu Approval" },
  approved:         { cls: "pill-success", label: "Approved" },
  rejected:         { cls: "pill-danger",  label: "Ditolak" },
};
export function fmtNum(n, d = 1) {
  return new Intl.NumberFormat("id-ID", { minimumFractionDigits: d, maximumFractionDigits: d }).format(n || 0);
}
export function fmtDate(s) {
  if (!s) return "-";
  return new Date(s).toLocaleDateString("id-ID", { day: "2-digit", month: "short", year: "numeric" });
}
export function ReturnStatusPill({ status }) {
  const s = STATUS_STYLE[status] || { cls: "pill-muted", label: status };
  return <span className={`status-pill ${s.cls}`}>{s.label}</span>;
}
export function ReturnTypeBadge({ type }) {
  const colors = {
    retur: "badge-blue", bs: "badge-orange", penggantian: "badge-purple",
    komplain: "badge-red", garansi: "badge-teal",
  };
  return (
    <span className={`feature-badge ${colors[type] || "badge-muted"}`}>
      {RETURN_TYPE_LABEL[type] || type}
    </span>
  );
}
