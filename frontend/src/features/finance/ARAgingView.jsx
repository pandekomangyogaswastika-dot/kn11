/**
 * ARAgingView (EPIC7-A) — Piutang / Accounts Receivable Aging.
 * Akses admin/manager. Sumber: GET /api/ar/aging (+ /ar/aging/{customer_id}).
 * Aging buckets: Lancar / 1-30 / 31-60 / 61-90 / 90+ hari. Denda = ESTIMASI (info).
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  RefreshCw, Search, Wallet, AlertTriangle, TrendingDown, Clock3, Users, X, FileText,
} from "lucide-react";
import axios, { API } from "../../services/apiClient";
import ErrorNotice from "../../components/ErrorNotice";
import { formatCurrency } from "../../utils/formatters";
import { CreditStatusPill } from "../crm/crmUtils";

const BUCKETS = [
  { key: "current", label: "Lancar", tone: "#1B7F4B", bg: "#E6F6EC" },
  { key: "b1_30", label: "1-30 hr", tone: "#B45309", bg: "#FDF3E7" },
  { key: "b31_60", label: "31-60 hr", tone: "#B45309", bg: "#FDF3E7" },
  { key: "b61_90", label: "61-90 hr", tone: "#C0392B", bg: "#FCEBEA" },
  { key: "b90_plus", label: "90+ hr", tone: "#C0392B", bg: "#FCEBEA" },
];

function fmtDate(iso) {
  if (!iso) return "—";
  try { return new Date(iso).toLocaleDateString("id-ID", { day: "2-digit", month: "short", year: "2-digit" }); }
  catch { return "—"; }
}

export default function ARAgingView({ selectedEntity }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [q, setQ] = useState("");
  const [onlyOverdue, setOnlyOverdue] = useState(false);
  const [selected, setSelected] = useState(null);   // customer_id
  const [detail, setDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = {};
      if (selectedEntity && selectedEntity !== "all") params.entity_id = selectedEntity;
      const res = await axios.get(`${API}/ar/aging`, { params });
      setData(res.data || null);
      setError("");
    } catch (e) {
      setError(e.response?.data?.detail || "Gagal memuat data piutang (AR aging).");
    } finally {
      setLoading(false);
    }
  }, [selectedEntity]);

  useEffect(() => { load(); }, [load]);

  const openDetail = useCallback(async (cid) => {
    setSelected(cid);
    setDetail(null);
    setDetailLoading(true);
    try {
      const res = await axios.get(`${API}/ar/aging/${cid}`);
      setDetail(res.data || null);
    } catch {
      setDetail(null);
    } finally {
      setDetailLoading(false);
    }
  }, []);

  const totals = data?.totals || {};
  const dendaRate = data?.config?.denda_rate_pct_per_month || 0;

  const rows = useMemo(() => {
    let r = data?.customers || [];
    const term = q.trim().toLowerCase();
    if (term) r = r.filter((c) => `${c.customer_name} ${c.assigned_sales_name}`.toLowerCase().includes(term));
    if (onlyOverdue) r = r.filter((c) => (c.overdue || 0) > 0.01);
    return r;
  }, [data, q, onlyOverdue]);

  const overduePct = totals.total > 0 ? Math.round((totals.overdue / totals.total) * 100) : 0;

  return (
    <div data-testid="ar-aging-view">
      {/* KPI cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-3">
        <Kpi testId="ar-kpi-total" label="Total Piutang" value={formatCurrency(totals.total)} icon={Wallet} />
        <Kpi testId="ar-kpi-overdue" label={`Jatuh Tempo (${overduePct}%)`} value={formatCurrency(totals.overdue)} icon={AlertTriangle} tone={totals.overdue > 0 ? "text-[#C0392B]" : ""} />
        <Kpi testId="ar-kpi-current" label="Lancar (Belum JT)" value={formatCurrency(totals.current)} icon={Clock3} tone="text-[#1B7F4B]" />
        <Kpi testId="ar-kpi-denda" label={`Est. Denda (${dendaRate}%/bln)`} value={formatCurrency(totals.denda)} icon={TrendingDown} tone={totals.denda > 0 ? "text-[#B45309]" : ""} />
      </div>

      {/* Aging bucket strip */}
      <div className="section-card mb-3">
        <div className="section-body py-3">
          <div className="flex items-center gap-2 mb-2">
            <TrendingDown size={15} className="text-[#6B219A]" />
            <h3 className="text-[12px] font-bold text-[#1C1C1E]">Sebaran Umur Piutang</h3>
            <span className="text-[10.5px] text-[#9A9BA3] ml-auto" data-testid="ar-aging-customers">{totals.customers || 0} pelanggan · {totals.orders || 0} order</span>
          </div>
          <AgingBar totals={totals} />
        </div>
      </div>

      {/* Master table */}
      <div className="section-card">
        <div className="section-head">
          <div className="flex items-center gap-2"><Wallet size={16} className="text-[#6B219A]" /><h2 data-testid="ar-aging-title">Piutang per Pelanggan</h2></div>
          <div className="flex items-center gap-2 ml-auto">
            <button
              data-testid="ar-aging-overdue-toggle"
              className={`text-[11px] font-semibold rounded-md px-2.5 py-1.5 border transition-colors ${onlyOverdue ? "bg-[#FCEBEA] border-[#F0B5AE] text-[#C0392B]" : "bg-white border-[#EFF0F2] text-[#6B6B73] hover:border-[#C9DBF7]"}`}
              onClick={() => setOnlyOverdue((v) => !v)}
            >
              {onlyOverdue ? "Hanya Overdue ✓" : "Hanya Overdue"}
            </button>
            <div className="relative">
              <Search size={13} className="absolute left-2 top-1/2 -translate-y-1/2 text-[#9A9BA3]" />
              <input data-testid="ar-aging-search" className="field pl-7 py-1 text-[12px]" placeholder="Cari pelanggan / sales..." value={q} onChange={(e) => setQ(e.target.value)} />
            </div>
            <button data-testid="ar-aging-refresh" className="icon-button" onClick={load} aria-label="Refresh"><RefreshCw size={14} className={loading ? "animate-spin" : ""} /></button>
          </div>
        </div>
        <div className="section-body">
          <ErrorNotice message={error} onRetry={load} onDismiss={() => setError("")} testId="ar-aging-error" />
          {loading ? (
            <div className="grid gap-2" data-testid="ar-aging-loading">{[0, 1, 2, 3, 4].map((i) => <div key={i} className="h-10 bg-[#F5F5F7] rounded animate-pulse" />)}</div>
          ) : rows.length === 0 ? (
            <div data-testid="ar-aging-empty" className="py-12 text-center text-[12px] text-[#8E8E93]">
              <Users size={26} className="mx-auto mb-2 text-gray-300" />
              {onlyOverdue ? "Tidak ada piutang jatuh tempo. 🎉" : "Tidak ada piutang terbuka."}
            </div>
          ) : (
            <div className="overflow-auto rounded-md border border-[#EFF0F2]">
              <table className="w-full text-[12px]" data-testid="ar-aging-table">
                <thead>
                  <tr className="text-left text-[10px] font-bold uppercase text-[#8E8E93] bg-[#FAFBFC] border-b border-[#EFF0F2]">
                    <th className="px-3 py-2">Pelanggan</th>
                    <th className="px-3 py-2 text-right">Lancar</th>
                    <th className="px-3 py-2 text-right">1-30</th>
                    <th className="px-3 py-2 text-right">31-60</th>
                    <th className="px-3 py-2 text-right">61-90</th>
                    <th className="px-3 py-2 text-right">90+</th>
                    <th className="px-3 py-2 text-right">Outstanding</th>
                    <th className="px-3 py-2 text-right">Est. Denda</th>
                    <th className="px-3 py-2 text-center">Kredit</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((c) => (
                    <tr
                      key={c.customer_id}
                      data-testid={`ar-aging-row-${c.customer_id}`}
                      className={`border-b border-[#F5F5F7] last:border-0 cursor-pointer hover:bg-[#FAFBFF] ${selected === c.customer_id ? "bg-[#EFF4FF]" : ""}`}
                      onClick={() => openDetail(c.customer_id)}
                    >
                      <td className="px-3 py-2">
                        <p className="font-semibold text-[#1C1C1E]">{c.customer_name}</p>
                        <p className="text-[10px] text-[#9A9BA3]">{c.assigned_sales_name || "—"}{c.oldest_days > 0 ? ` · telat ${c.oldest_days} hr` : ""}</p>
                      </td>
                      <Cell v={c.current} />
                      <Cell v={c.b1_30} warn />
                      <Cell v={c.b31_60} warn />
                      <Cell v={c.b61_90} danger />
                      <Cell v={c.b90_plus} danger />
                      <td className="px-3 py-2 text-right tabular-nums font-bold text-[#1C1C1E]">{formatCurrency(c.outstanding)}</td>
                      <td className="px-3 py-2 text-right tabular-nums text-[#B45309]">{c.denda > 0 ? formatCurrency(c.denda) : "—"}</td>
                      <td className="px-3 py-2 text-center"><CreditStatusPill status={c.credit_status} testId={`ar-credit-${c.customer_id}`} /></td>
                    </tr>
                  ))}
                </tbody>
                <tfoot>
                  <tr className="bg-[#FAFBFC] border-t border-[#EFF0F2] text-[11px] font-bold">
                    <td className="px-3 py-2 text-[#6B6B73] uppercase text-[10px]">Total</td>
                    <td className="px-3 py-2 text-right tabular-nums">{formatCurrency(totals.current)}</td>
                    <td className="px-3 py-2 text-right tabular-nums">{formatCurrency(totals.b1_30)}</td>
                    <td className="px-3 py-2 text-right tabular-nums">{formatCurrency(totals.b31_60)}</td>
                    <td className="px-3 py-2 text-right tabular-nums">{formatCurrency(totals.b61_90)}</td>
                    <td className="px-3 py-2 text-right tabular-nums">{formatCurrency(totals.b90_plus)}</td>
                    <td className="px-3 py-2 text-right tabular-nums" data-testid="ar-aging-total">{formatCurrency(totals.total)}</td>
                    <td className="px-3 py-2 text-right tabular-nums text-[#B45309]">{formatCurrency(totals.denda)}</td>
                    <td className="px-3 py-2" />
                  </tr>
                </tfoot>
              </table>
            </div>
          )}
          <p className="text-[10.5px] text-[#9A9BA3] mt-2">Umur dihitung dari tanggal order + term pembayaran. <b>Est. Denda</b> = estimasi informasional ({dendaRate}%/bulan atas saldo jatuh tempo) — belum diposting ke order/buku besar.</p>
        </div>
      </div>

      {/* Drill-down detail */}
      {selected && (
        <CustomerDetail
          detail={detail}
          loading={detailLoading}
          onClose={() => { setSelected(null); setDetail(null); }}
        />
      )}
    </div>
  );
}

function Cell({ v, warn, danger }) {
  const tone = (v || 0) <= 0.01 ? "text-[#C7C7CC]" : danger ? "text-[#C0392B]" : warn ? "text-[#B45309]" : "text-[#3C3C43]";
  return <td className={`px-3 py-2 text-right tabular-nums ${tone}`}>{(v || 0) > 0.01 ? formatCurrency(v) : "—"}</td>;
}

function AgingBar({ totals }) {
  const total = totals.total || 0;
  return (
    <div data-testid="ar-aging-bar">
      <div className="flex h-3 w-full overflow-hidden rounded-full bg-[#F2F2F7]">
        {BUCKETS.map((b) => {
          const v = totals[b.key] || 0;
          const pct = total > 0 ? (v / total) * 100 : 0;
          if (pct <= 0) return null;
          return <div key={b.key} title={`${b.label}: ${formatCurrency(v)}`} style={{ width: `${pct}%`, background: b.tone }} />;
        })}
      </div>
      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1">
        {BUCKETS.map((b) => (
          <span key={b.key} className="flex items-center gap-1.5 text-[10.5px] text-[#6B6B73]" data-testid={`ar-bucket-${b.key}`}>
            <span className="h-2.5 w-2.5 rounded-sm" style={{ background: b.tone }} />
            {b.label}: <b className="tabular-nums text-[#1C1C1E]">{formatCurrency(totals[b.key])}</b>
          </span>
        ))}
      </div>
    </div>
  );
}

function CustomerDetail({ detail, loading, onClose }) {
  return (
    <div className="section-card mt-3" data-testid="ar-aging-detail">
      <div className="section-head">
        <div className="flex items-center gap-2">
          <FileText size={15} className="text-[#0058CC]" />
          <h2>{detail?.customer_name || "Rincian Piutang"}</h2>
          {detail && <span className="text-[11px] text-[#6B6B73]">· Outstanding <b className="tabular-nums">{formatCurrency(detail.totals?.total)}</b></span>}
        </div>
        <button data-testid="ar-aging-detail-close" className="icon-button ml-auto" onClick={onClose} aria-label="Tutup"><X size={14} /></button>
      </div>
      <div className="section-body">
        {loading ? (
          <div className="grid gap-2" data-testid="ar-aging-detail-loading">{[0, 1, 2].map((i) => <div key={i} className="h-9 bg-[#F5F5F7] rounded animate-pulse" />)}</div>
        ) : !detail || (detail.items || []).length === 0 ? (
          <div className="py-8 text-center text-[12px] text-[#8E8E93]" data-testid="ar-aging-detail-empty">Tidak ada order terbuka.</div>
        ) : (
          <div className="overflow-auto rounded-md border border-[#EFF0F2]">
            <table className="w-full text-[12px]">
              <thead>
                <tr className="text-left text-[10px] font-bold uppercase text-[#8E8E93] bg-[#FAFBFC] border-b border-[#EFF0F2]">
                  <th className="px-3 py-2">Order</th>
                  <th className="px-3 py-2">Jatuh Tempo</th>
                  <th className="px-3 py-2 text-center">Umur</th>
                  <th className="px-3 py-2 text-right">Total</th>
                  <th className="px-3 py-2 text-right">Terbayar</th>
                  <th className="px-3 py-2 text-right">Outstanding</th>
                  <th className="px-3 py-2 text-right">Est. Denda</th>
                </tr>
              </thead>
              <tbody>
                {detail.items.map((it) => (
                  <tr key={it.order_id} data-testid={`ar-detail-row-${it.order_id}`} className="border-b border-[#F5F5F7] last:border-0">
                    <td className="px-3 py-2 font-semibold text-[#0058CC]">{it.order_number}</td>
                    <td className="px-3 py-2 text-[#3C3C43]">{fmtDate(it.due_date)}</td>
                    <td className="px-3 py-2 text-center">
                      {it.overdue
                        ? <span className="rounded bg-[#FCEBEA] px-1.5 py-0.5 text-[10px] font-bold text-[#C0392B]">telat {it.days_late} hr</span>
                        : <span className="rounded bg-[#E6F6EC] px-1.5 py-0.5 text-[10px] font-bold text-[#1B7F4B]">lancar</span>}
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums">{formatCurrency(it.grand_total)}</td>
                    <td className="px-3 py-2 text-right tabular-nums text-[#1B7F4B]">{formatCurrency(it.paid_total)}</td>
                    <td className="px-3 py-2 text-right tabular-nums font-bold">{formatCurrency(it.outstanding)}</td>
                    <td className="px-3 py-2 text-right tabular-nums text-[#B45309]">{it.denda_estimate > 0 ? formatCurrency(it.denda_estimate) : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

function Kpi({ label, value, icon: Icon, tone = "", testId }) {
  return (
    <div className="section-card" data-testid={testId}>
      <div className="section-body flex items-center gap-3 py-3">
        <div className="w-9 h-9 rounded-lg bg-[#F3EAFB] flex items-center justify-center"><Icon size={17} className="text-[#6B219A]" /></div>
        <div className="min-w-0">
          <p className="text-[10px] font-bold uppercase tracking-wide text-[#8E8E93]">{label}</p>
          <p className={`text-[17px] font-bold tabular-nums truncate ${tone || "text-[#1C1C1E]"}`} data-testid={`${testId}-value`}>{value}</p>
        </div>
      </div>
    </div>
  );
}
