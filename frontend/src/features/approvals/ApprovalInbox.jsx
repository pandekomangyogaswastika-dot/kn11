import { useEffect, useState } from "react";
import axios, { API } from "../../services/apiClient";
import {
  Inbox, ShoppingCart, Tag, ArrowRight, Clock, RefreshCw, CheckSquare,
  RotateCcw, ClipboardCheck,
} from "lucide-react";
import { formatCurrency } from "../../utils/formatters";
import ErrorNotice from "../../components/ErrorNotice";

/**
 * ApprovalInbox — "Pusat Persetujuan".
 * Hub terpadu lintas-modul: menampilkan SEMUA persetujuan yang menunggu keputusan
 * (PO pembelian, harga khusus, retur jual, retur beli, cycle count) dalam satu tempat,
 * lalu deep-link ke antrian modul terkait untuk meninjau detail & memutuskan.
 * Read-only di sini — keputusan dilakukan di view modul yang kaya konteks (bukan duplikasi aksi).
 */

// kind → tampilan (label, ikon, warna) + tab grup
const KIND_META = {
  po:              { label: "PO Pembelian",  icon: ShoppingCart,   fg: "#0058CC", bg: "#EFF4FF", group: "po" },
  price:           { label: "Harga Khusus",  icon: Tag,            fg: "#6D28D9", bg: "#F3EEFF", group: "price" },
  sales_return:    { label: "Retur Jual",    icon: RotateCcw,      fg: "#B45309", bg: "#FEF3C7", group: "returns" },
  purchase_return: { label: "Retur Beli",    icon: RotateCcw,      fg: "#0E7490", bg: "#E0F2FE", group: "returns" },
  cycle:           { label: "Cycle Count",   icon: ClipboardCheck, fg: "#15803D", bg: "#DCFCE7", group: "cycle" },
};

const TABS = [
  { key: "all",     label: "Semua" },
  { key: "po",      label: "Pembelian (PO)" },
  { key: "price",   label: "Harga Khusus" },
  { key: "returns", label: "Retur" },
  { key: "cycle",   label: "Cycle Count" },
];

function timeAgo(iso) {
  if (!iso) return "";
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 3600) return `${Math.max(1, Math.floor(diff / 60))} mnt lalu`;
  if (diff < 86400) return `${Math.floor(diff / 3600)} jam lalu`;
  return `${Math.floor(diff / 86400)} hari lalu`;
}

const arr = (d) => (Array.isArray(d) ? d : (Array.isArray(d?.items) ? d.items : []));

export default function ApprovalInbox({ currentUser, onNavigate }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [tab, setTab] = useState("all");

  useEffect(() => { load(); }, []); // eslint-disable-line

  async function load() {
    setLoading(true);
    try {
      const [poRes, prRes, srRes, purRes, ccRes] = await Promise.all([
        axios.get(`${API}/purchase-orders`).catch(() => ({ data: [] })),
        axios.get(`${API}/price-approvals`, { params: { status: "pending" } }).catch(() => ({ data: [] })),
        axios.get(`${API}/sales-returns`, { params: { status: "pending_approval" } }).catch(() => ({ data: [] })),
        axios.get(`${API}/purchase-returns`).catch(() => ({ data: [] })),
        axios.get(`${API}/cycle-count/sessions`).catch(() => ({ data: [] })),
      ]);

      const pos = arr(poRes.data)
        .filter((p) => p.status === "waiting_approval")
        .map((p) => ({
          kind: "po", id: p.id, title: p.po_number, subtitle: p.supplier_name,
          meta: `${p.warehouse_name || ""} · ${p.items?.length || 0} item`,
          amount: p.total_amount, requester: p.created_by, role: p.required_approval_role,
          at: p.created_at, target: "purchase-approval",
        }));

      const prices = arr(prRes.data).map((p) => ({
        kind: "price", id: p.id, title: p.product_name || p.sku, subtitle: p.customer_name,
        meta: `${formatCurrency(p.normal_price)} → ${formatCurrency(p.requested_price)}${p.discount_percent ? ` (-${p.discount_percent}%)` : ""}`,
        amount: p.requested_price, requester: p.requested_by_name, role: "manager",
        at: p.created_at, target: "price-approvals",
      }));

      const salesReturns = arr(srRes.data)
        .filter((r) => r.status === "pending_approval")
        .map((r) => ({
          kind: "sales_return", id: r.id, title: r.number, subtitle: r.customer_name || "Customer",
          meta: `Order ${r.order_number || "—"} · ${r.items?.length || 0} item`,
          amount: null, requester: r.created_by, role: "manager",
          at: r.created_at, target: "returns",
        }));

      const purchaseReturns = arr(purRes.data)
        .filter((r) => r.status === "pending_approval")
        .map((r) => ({
          kind: "purchase_return", id: r.id, title: r.number, subtitle: r.supplier_name || "Supplier",
          meta: `${r.po_number ? `dari ${r.po_number} · ` : ""}${r.items?.length || 0} item`,
          amount: r.total_amount, requester: r.created_by, role: "manager",
          at: r.created_at, target: "purchase-returns",
        }));

      const cycleCounts = arr(ccRes.data)
        .filter((s) => s.status === "submitted")
        .map((s) => ({
          kind: "cycle", id: s.id, title: s.name || "Cycle Count", subtitle: s.warehouse_name || "Gudang",
          meta: `${s.items?.length || 0} item dihitung`,
          amount: null, requester: s.submitted_by || s.created_by, role: "manager",
          at: s.submitted_at || s.created_at, target: "wms-cycle", targetView: "operations", targetTab: "cycle",
        }));

      const all = [...pos, ...prices, ...salesReturns, ...purchaseReturns, ...cycleCounts]
        .sort((a, b) => new Date(a.at || 0) - new Date(b.at || 0));
      setItems(all);
      setError("");
    } catch (e) {
      setError(e.response?.data?.detail || "Gagal memuat antrian persetujuan.");
    } finally {
      setLoading(false);
    }
  }

  const groupOf = (it) => KIND_META[it.kind]?.group;
  const counts = TABS.reduce((acc, t) => {
    acc[t.key] = t.key === "all" ? items.length : items.filter((i) => groupOf(i) === t.key).length;
    return acc;
  }, {});
  const filtered = items.filter((i) => tab === "all" || groupOf(i) === tab);

  return (
    <div data-testid="approval-inbox-view">
      <ErrorNotice message={error} onRetry={load} onDismiss={() => setError("")} testId="approval-inbox-error" />

      <div className="section-card mb-3">
        <div className="section-head">
          <div className="flex items-center gap-2 min-w-0">
            <Inbox size={16} className="text-[#0058CC]" />
            <div className="min-w-0">
              <h2 data-testid="approval-inbox-title">Pusat Persetujuan</h2>
              <p className="text-[11px] text-[#6B6B73]">Semua persetujuan lintas modul yang menunggu keputusan Anda — PO, harga, retur & cycle count.</p>
            </div>
          </div>
          <button data-testid="approval-inbox-refresh" onClick={load} className="secondary-button">
            <RefreshCw size={13} className={loading ? "animate-spin" : ""} /> Muat Ulang
          </button>
        </div>
        <div className="section-body">
          <div className="tab-bar">
            {TABS.map((t) => (
              <button key={t.key} data-testid={`approval-inbox-tab-${t.key}`}
                className={`tab-button ${tab === t.key ? "active" : ""}`} onClick={() => setTab(t.key)}>
                {t.label}<span className="tab-badge">{counts[t.key]}</span>
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="section-card">
        {loading ? (
          <div className="py-12 text-center text-[12px] text-[#6B6B73]">Memuat antrian persetujuan...</div>
        ) : filtered.length === 0 ? (
          <div className="py-14 text-center text-[12px] text-[#6B6B73]" data-testid="approval-inbox-empty">
            <CheckSquare className="mx-auto mb-2 text-gray-300" size={30} />
            <p className="font-semibold text-[#3C3C43]">Tidak ada yang menunggu persetujuan.</p>
            <p>Semua keputusan sudah ditindaklanjuti.</p>
          </div>
        ) : (
          <div className="divide-y divide-[#EFF0F2]">
            {filtered.map((it) => {
              const m = KIND_META[it.kind] || KIND_META.po;
              const Icon = m.icon;
              return (
                <div key={`${it.kind}-${it.id}`} data-testid={`approval-inbox-item-${it.id}`}
                  className="flex items-center gap-3 px-3 py-2.5 hover:bg-[#FAFBFC]">
                  <span className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full"
                    style={{ background: m.bg, color: m.fg }}>
                    <Icon size={15} />
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-[12px] font-bold text-[#1C1C1E] truncate">{it.title}</span>
                      <span className="text-[9px] font-bold uppercase px-1.5 py-0.5 rounded"
                        style={{ background: m.bg, color: m.fg }}>
                        {m.label}
                      </span>
                    </div>
                    <p className="text-[11px] text-[#6B6B73] truncate">{it.subtitle} · {it.meta}</p>
                    <p className="text-[10px] text-[#9A9BA3] flex items-center gap-1 mt-0.5">
                      <Clock size={10} /> {timeAgo(it.at)} · diajukan {it.requester || "—"} · butuh <b className="uppercase">{it.role || "manager"}</b>
                    </p>
                  </div>
                  <div className="text-right flex-shrink-0">
                    {it.amount != null && (
                      <p className="text-[13px] font-bold tabular-nums text-[#1C1C1E]">{formatCurrency(it.amount)}</p>
                    )}
                    <button data-testid={`approval-inbox-review-${it.id}`}
                      onClick={() => onNavigate?.(it.target, it.targetView, it.targetTab)}
                      className="mt-1 inline-flex items-center gap-1 text-[11px] font-bold text-[#0058CC] hover:underline">
                      Tinjau &amp; Putuskan <ArrowRight size={12} />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
