import { useEffect, useMemo, useState } from "react";
import axios, { API } from "../../services/apiClient";
import { Receipt, Plus, Send, Wallet, Scale } from "lucide-react";
import { formatCurrency } from "../../utils/formatters";
import ErrorNotice from "../../components/ErrorNotice";
import EntityBadge from "../../components/EntityBadge";
import VendorBillCreateModal from "./VendorBillCreateModal";
import VendorBillDetailPanel from "./VendorBillDetailPanel";

/**
 * VendorBillsView (Fase 5.2 — P0-2) — Tagihan Supplier (Vendor Bill) + 3-Way Matching.
 * AP berbasis bill posted. PO ↔ GR ↔ Bill dicocokkan dengan toleransi qty & harga.
 */
const TABS = [
  { key: "all", label: "Semua" },
  { key: "draft", label: "Draft" },
  { key: "pending_approval", label: "Menunggu" },
  { key: "posted", label: "Posted" },
  { key: "paid", label: "Lunas" },
  { key: "cancelled", label: "Batal" },
];

function StatusPill({ status }) {
  const map = {
    draft: ["pill-muted", "Draft"], pending_approval: ["pill-warning", "Menunggu"],
    posted: ["pill-info", "Posted"], paid: ["pill-success", "Lunas"], cancelled: ["pill-danger", "Batal"],
  };
  const [cls, label] = map[status] || ["pill-muted", status];
  return <span className={`status-pill ${cls}`}>{label}</span>;
}
function MatchPill({ status }) {
  const map = { matched: ["pill-success", "Match"], warning: ["pill-warning", "Selisih"], blocked: ["pill-danger", "Over-bill"] };
  const [cls, label] = map[status] || ["pill-muted", "—"];
  return <span className={`status-pill ${cls}`}>{label}</span>;
}

export default function VendorBillsView({ currentUser, selectedEntity }) {
  const [bills, setBills] = useState([]);
  const [pos, setPos] = useState([]);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [tab, setTab] = useState("all");
  const [showCreate, setShowCreate] = useState(false);
  const [detail, setDetail] = useState(null);

  const canApprove = ["admin", "manager"].includes(currentUser?.role);
  const canCreate = ["admin", "manager"].includes(currentUser?.role);

  useEffect(() => { loadAll(); }, [selectedEntity]); // eslint-disable-line

  async function loadAll() {
    setLoading(true);
    try {
      const params = (selectedEntity && selectedEntity !== "all") ? { entity_id: selectedEntity } : {};
      const [bRes, poRes, sRes] = await Promise.all([
        axios.get(`${API}/vendor-bills`, { params }),
        axios.get(`${API}/purchase-orders`, { params }).catch(() => ({ data: [] })),
        axios.get(`${API}/vendor-bills/payables/summary`, { params }).catch(() => ({ data: null })),
      ]);
      setBills(Array.isArray(bRes.data) ? bRes.data : []);
      // PO yang bisa ditagih: sudah disetujui/diterima (bukan draft/menunggu/batal/ditolak)
      const billable = (Array.isArray(poRes.data) ? poRes.data : []).filter(
        (p) => !["waiting_approval", "rejected", "cancelled", "draft"].includes(p.status));
      setPos(billable);
      setSummary(sRes.data);
      setError("");
    } catch (e) {
      setError(e.response?.data?.detail || "Gagal memuat data vendor bill.");
    } finally { setLoading(false); }
  }

  async function refreshDetail(id) {
    try {
      const r = await axios.get(`${API}/vendor-bills/${id}`);
      setDetail(r.data);
    } catch { /* ignore */ }
  }

  function onCreated(bill, submitted) {
    setShowCreate(false);
    const msg = bill.status === "posted" ? "langsung di-posting (match bersih)"
      : bill.status === "pending_approval" ? "menunggu approval (ada selisih)" : "disimpan sebagai draft";
    setNotice(`Vendor Bill ${bill.bill_number} dibuat — ${msg}.`);
    loadAll();
  }

  async function onAction(action, data) {
    const labels = { submit: "disubmit", approve: "disetujui & posted", reject: "ditolak", cancel: "dibatalkan", pay: "pembayaran dicatat" };
    setNotice(`${data.bill_number}: ${labels[action] || action}.`);
    setDetail(data);
    await loadAll();
  }

  async function quickAct(bill, action, body) {
    try {
      const urls = {
        submit: `${API}/vendor-bills/${bill.id}/submit`,
        approve: `${API}/vendor-bills/${bill.id}/approve`,
      };
      const r = await axios.post(urls[action], body || {});
      const labels = { submit: "disubmit", approve: "disetujui & posted" };
      setNotice(`${r.data.bill_number}: ${labels[action] || action}.`);
      await loadAll();
    } catch (e) {
      setError(e.response?.data?.detail || `Gagal ${action}.`);
    }
  }

  const filtered = useMemo(() => bills.filter((b) => tab === "all" || b.status === tab), [bills, tab]);
  const counts = useMemo(() => TABS.reduce((acc, t) => ({
    ...acc, [t.key]: t.key === "all" ? bills.length : bills.filter((b) => b.status === t.key).length,
  }), {}), [bills]);

  return (
    <div data-testid="vendor-bills-view">
      {notice && <div className="notice-bar success" data-testid="vb-notice"><span>{notice}</span><button onClick={() => setNotice("")}>×</button></div>}
      <ErrorNotice message={error} onRetry={loadAll} onDismiss={() => setError("")} testId="vb-error" />

      {/* AP summary */}
      {summary && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-2.5 mb-3" data-testid="vb-summary">
          <SummaryCard label="Total Hutang (AP)" value={formatCurrency(summary.total_outstanding)} tone="text-red-600" big testId="vb-summary-total" />
          <SummaryCard label="0–30 hari" value={formatCurrency(summary.aging?.["0-30"])} />
          <SummaryCard label="31–60 hari" value={formatCurrency(summary.aging?.["31-60"])} />
          <SummaryCard label="61–90 hari" value={formatCurrency(summary.aging?.["61-90"])} tone="text-amber-600" />
          <SummaryCard label="> 90 hari" value={formatCurrency(summary.aging?.[">90"])} tone="text-red-600" />
        </div>
      )}

      {/* Header + tabs */}
      <div className="section-card mb-3">
        <div className="section-head">
          <div className="flex items-center gap-2 min-w-0">
            <Receipt size={16} className="text-[#0058CC]" />
            <h2 data-testid="vendor-bills-title">Tagihan Supplier (Vendor Bill)</h2>
          </div>
          {canCreate && (
            <button data-testid="create-vendor-bill-button" onClick={() => setShowCreate(true)} className="primary-button">
              <Plus size={13} /> Buat Vendor Bill
            </button>
          )}
        </div>
        <div className="section-body">
          <div className="tab-bar">
            {TABS.map((t) => (
              <button key={t.key} data-testid={`vb-tab-${t.key}`} className={`tab-button ${tab === t.key ? "active" : ""}`} onClick={() => setTab(t.key)}>
                {t.label}<span className="tab-badge">{counts[t.key]}</span>
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* List */}
      <div className="section-card">
        <div className="overflow-hidden">
          <div className="grid grid-cols-[110px_1.4fr_120px_120px_110px_90px_100px_120px] px-3 py-1.5 bg-[#FAFBFC] text-[10px] font-bold uppercase text-[#6B6B73] border-b border-[#EFF0F2]">
            <span>Nomor</span><span>Supplier / PO</span><span className="text-right">Total</span><span className="text-right">Sisa</span>
            <span>Match</span><span>Status</span><span>Inv. Supplier</span><span className="text-right">Aksi</span>
          </div>
          {loading ? (
            <div className="py-10 text-center text-[12px] text-[#6B6B73]">Memuat vendor bill...</div>
          ) : filtered.length === 0 ? (
            <div className="py-12 text-center text-[12px] text-[#6B6B73]">
              <Scale className="mx-auto mb-2 text-gray-300" size={28} />
              <p>Belum ada vendor bill{tab !== "all" ? ` (${tab})` : ""}.</p>
              {canCreate && tab === "all" && <p className="mt-1 text-[11px]">Buat tagihan dari PO yang sudah diterima untuk memulai 3-way matching.</p>}
            </div>
          ) : (
            <div className="divide-y divide-[#EFF0F2] max-h-[560px] overflow-y-auto">
              {filtered.map((b) => (
                <div key={b.id} data-testid={`vb-row-${b.id}`} onClick={() => setDetail(b)}
                     className="grid grid-cols-[110px_1.4fr_120px_120px_110px_90px_100px_120px] items-center px-3 py-2.5 hover:bg-[#FAFBFC] cursor-pointer">
                  <span className="text-[11.5px] font-bold text-[#0058CC]">{b.bill_number}</span>
                  <div className="min-w-0">
                    <p className="text-[12px] font-semibold truncate">{b.supplier_name}</p>
                    <p className="text-[10.5px] text-[#6B6B73] truncate flex items-center gap-1">
                      <EntityBadge entityId={b.entity_id} />
                      <span className="truncate">{b.po_number} · {b.items?.length || 0} item</span>
                    </p>
                  </div>
                  <span className="text-[12px] font-bold tabular-nums text-right">{formatCurrency(b.grand_total)}</span>
                  <span className="text-[12px] tabular-nums text-right text-red-600">{formatCurrency(b.financials?.outstanding ?? b.outstanding)}</span>
                  <MatchPill status={b.match_status} />
                  <StatusPill status={b.status} />
                  <span className="text-[10.5px] text-[#6B6B73] truncate">{b.supplier_invoice_no || "—"}</span>
                  <div className="flex items-center justify-end gap-1.5" onClick={(e) => e.stopPropagation()}>
                    {b.status === "draft" && (
                      <button data-testid={`vb-quick-submit-${b.id}`} onClick={() => quickAct(b, "submit")} className="secondary-button !px-2 !py-1 text-[11px]"><Send size={11} /> Submit</button>
                    )}
                    {b.status === "pending_approval" && canApprove && (
                      <button data-testid={`vb-quick-approve-${b.id}`} onClick={() => quickAct(b, "approve")} className="primary-button !px-2 !py-1 text-[11px]">Setujui</button>
                    )}
                    {b.status === "posted" && (
                      <button data-testid={`vb-quick-pay-${b.id}`} onClick={() => setDetail(b)} className="primary-button !px-2 !py-1 text-[11px]"><Wallet size={11} /> Bayar</button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <VendorBillCreateModal
        open={showCreate}
        pos={pos}
        selectedEntity={selectedEntity}
        onClose={() => setShowCreate(false)}
        onCreated={onCreated}
        onError={(m) => setError(m)}
      />

      {detail && (
        <VendorBillDetailPanel
          bill={detail}
          canApprove={canApprove}
          currentUser={currentUser}
          onClose={() => setDetail(null)}
          onAction={onAction}
          onError={(m) => setError(m)}
        />
      )}
    </div>
  );
}

function SummaryCard({ label, value, tone, big, testId }) {
  return (
    <div className="section-card !p-3" data-testid={testId}>
      <p className="text-[9.5px] font-bold uppercase text-[#6B6B73]">{label}</p>
      <p className={`${big ? "text-[18px]" : "text-[14px]"} font-bold tabular-nums ${tone || "text-[#0F1115]"}`}>{value}</p>
    </div>
  );
}
