import { X, FileText, Send, CheckCircle2, XCircle, ReceiptText, RotateCcw } from "lucide-react";
import { formatCurrency } from "../../utils/formatters";

const STATUS_PILL = {
  draft: ["pill-muted", "Draft"],
  pending_approval: ["pill-warning", "Menunggu Approval"],
  approved: ["pill-success", "Disetujui"],
  rejected: ["pill-danger", "Ditolak"],
};

const CONDITION_LABEL = { damaged: "Rusak", wrong_item: "Salah Kirim", excess: "Kelebihan", other: "Lainnya" };
const REASON_LABEL = { cacat: "Barang Cacat", salah_kirim: "Salah Kirim", kelebihan: "Kelebihan Kirim", lain: "Lain-lain" };

function fmtDateTime(iso) {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleString("id-ID", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
  } catch { return String(iso); }
}

function buildTimeline(r) {
  const out = [];
  out.push({ icon: FileText, tone: "#0058CC", bg: "#EFF4FF", label: "Retur dibuat", actor: r.created_by || "Sistem", at: r.created_at, note: `${(r.items || []).length} item · ${formatCurrency(r.total_amount)}` });
  if (["pending_approval", "approved", "rejected"].includes(r.status)) {
    out.push({ icon: Send, tone: "#9A5B00", bg: "#FFF7EC", label: "Diajukan untuk approval", actor: r.created_by || "Sistem", at: r.submitted_at || "", note: "" });
  }
  if (r.status === "approved") {
    out.push({ icon: CheckCircle2, tone: "#15803D", bg: "#E9F7EF", label: "Disetujui", actor: r.approved_by || "", at: r.approved_at, note: r.decision_notes || "" });
    if (r.debit_note_number) {
      out.push({ icon: ReceiptText, tone: "#15803D", bg: "#E9F7EF", label: `Nota debit diterbitkan (${r.debit_note_number})`, actor: "Sistem", at: r.approved_at, note: "Stok roll dikurangi & AP berkurang" });
    }
  }
  if (r.status === "rejected") {
    out.push({ icon: XCircle, tone: "#B91C1C", bg: "#FEF3F2", label: "Ditolak", actor: r.rejected_by || "", at: r.rejected_at, note: r.reject_reason || r.decision_notes || "" });
  }
  return out;
}

export default function ReturnDetailPanel({ ret, supName, canApprove, onClose, onSubmit, onApprove, onReject }) {
  if (!ret) return null;
  const [cls, label] = STATUS_PILL[ret.status] || ["pill-muted", ret.status];
  const timeline = buildTimeline(ret);

  return (
    <div className="modal-overlay" data-testid="return-detail-panel" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="modal-card" style={{ maxWidth: 560, width: "92vw", maxHeight: "88vh", overflowY: "auto" }}>
        <div className="flex items-start justify-between gap-2 mb-2">
          <div className="flex items-center gap-2 min-w-0">
            <RotateCcw size={16} className="text-[#0058CC]" />
            <div className="min-w-0">
              <p className="text-[14px] font-bold truncate" data-testid="return-detail-number">{ret.number}</p>
              <p className="text-[11px] text-[#6B6B73]">{ret.po_number ? `dari ${ret.po_number}` : "Tanpa PO"}</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className={`status-pill ${cls}`}>{label}</span>
            <button data-testid="return-detail-close" onClick={onClose} className="text-[#6B6B73] hover:text-[#1C1C1E]"><X size={16} /></button>
          </div>
        </div>

        {/* Meta */}
        <div className="grid grid-cols-2 gap-x-3 gap-y-1.5 rounded-md border border-[#EFF0F2] bg-[#FAFBFC] px-2.5 py-2 text-[11px] mb-2.5">
          <Meta label="Supplier" value={ret.supplier_name || supName?.(ret.supplier_id)} />
          <Meta label="Nota Debit" value={ret.debit_note_number || "—"} />
          <Meta label="Alasan" value={REASON_LABEL[ret.reason] || ret.reason || "—"} />
          <Meta label="Total" value={formatCurrency(ret.total_amount)} strong />
          {ret.notes ? <div className="col-span-2"><Meta label="Catatan" value={ret.notes} /></div> : null}
        </div>

        {/* Items */}
        <div className="rounded-md border border-[#EFF0F2] overflow-hidden mb-2.5">
          <div className="px-2.5 py-1.5 bg-[#FAFBFC] text-[10px] font-bold uppercase text-[#6B6B73] border-b border-[#EFF0F2]">Item Retur ({ret.items?.length || 0})</div>
          {(ret.items || []).map((it, i) => (
            <div key={i} data-testid={`return-detail-item-${i}`} className="grid grid-cols-[1fr_90px_120px] gap-2 px-2.5 py-1.5 border-b border-[#EFF0F2] last:border-0 text-[11px]">
              <div className="min-w-0">
                <p className="font-semibold truncate">{it.sku || it.product_name}</p>
                <p className="text-[10px] text-[#6B6B73] truncate">{CONDITION_LABEL[it.condition] || it.condition} · {REASON_LABEL[it.reason] || it.reason}</p>
              </div>
              <span className="tabular-nums text-right self-center text-[#3C3C43]">{it.quantity} {it.unit}</span>
              <span className="tabular-nums text-right self-center font-semibold">{formatCurrency(it.subtotal || (it.quantity || 0) * (it.price || 0))}</span>
            </div>
          ))}
        </div>

        {/* Timeline */}
        <div className="rounded-md border border-[#EFF0F2] overflow-hidden mb-1">
          <div className="px-2.5 py-1.5 bg-[#FAFBFC] text-[10px] font-bold uppercase text-[#6B6B73] border-b border-[#EFF0F2]">Riwayat / Timeline</div>
          <ol className="p-2.5" data-testid="return-timeline">
            {timeline.map((t, i) => {
              const Icon = t.icon;
              const last = i === timeline.length - 1;
              return (
                <li key={i} data-testid={`return-timeline-entry-${i}`} className="flex gap-2.5">
                  <div className="flex flex-col items-center">
                    <span className="flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full" style={{ background: t.bg, color: t.tone }}><Icon size={13} /></span>
                    {!last && <span className="w-px flex-1 my-0.5" style={{ background: "#E5E7EB", minHeight: 14 }} />}
                  </div>
                  <div className={`min-w-0 flex-1 ${last ? "" : "pb-2.5"}`}>
                    <div className="flex items-baseline justify-between gap-2">
                      <p className="text-[11.5px] font-semibold text-[#1C1C1E] truncate">{t.label}</p>
                      <span className="text-[10px] tabular-nums text-[#8E8E93] whitespace-nowrap">{fmtDateTime(t.at)}</span>
                    </div>
                    <p className="text-[10.5px] text-[#6B6B73]">oleh <span className="font-medium text-[#3C3C43]">{t.actor || "Sistem"}</span></p>
                    {t.note ? <p className="mt-0.5 text-[10.5px] text-[#6B6B73] italic">{t.note}</p> : null}
                  </div>
                </li>
              );
            })}
          </ol>
        </div>

        {/* Actions */}
        {(ret.status === "draft" || (ret.status === "pending_approval" && canApprove)) && (
          <div className="modal-actions">
            {ret.status === "draft" && (
              <button data-testid="return-detail-submit" onClick={() => onSubmit(ret)} className="btn-primary"><Send size={13} /> Ajukan Approval</button>
            )}
            {ret.status === "pending_approval" && canApprove && (
              <>
                <button data-testid="return-detail-reject" onClick={() => onReject(ret)} className="btn-danger"><XCircle size={13} /> Tolak</button>
                <button data-testid="return-detail-approve" onClick={() => onApprove(ret)} className="btn-primary"><CheckCircle2 size={13} /> Setujui & Terbitkan Nota</button>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function Meta({ label, value, strong }) {
  return (
    <div className="min-w-0">
      <p className="text-[9.5px] font-bold uppercase text-[#9A9BA3]">{label}</p>
      <p className={`truncate ${strong ? "font-bold tabular-nums text-[#1C1C1E]" : "text-[#3C3C43]"}`}>{value || "—"}</p>
    </div>
  );
}
