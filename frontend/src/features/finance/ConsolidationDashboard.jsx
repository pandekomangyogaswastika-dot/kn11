/**
 * ConsolidationDashboard (Multi-Entity F0-E enhancement) — Konsolidasi Grup vs Per-PT.
 * Satu layar untuk owner memantau >1 PT: toggle ringkasan keuangan GABUNGAN
 * semua entitas vs PER-PT (bandingkan), memakai buku terpisah F0-E.
 * Sumber: GET /api/gl/consolidation. Akses admin/manager (permission accounting).
 */
import { useCallback, useEffect, useState } from "react";
import {
  Landmark, RefreshCw, TrendingUp, TrendingDown, Wallet, Scale,
  Layers, Building2, ArrowDownRight, ArrowUpRight, PiggyBank, Percent,
} from "lucide-react";
import axios, { API } from "../../services/apiClient";
import ErrorNotice from "../../components/ErrorNotice";
import EntityBadge from "../../components/EntityBadge";
import { formatCurrency } from "../../utils/formatters";

const PURPLE = "#6B219A";

function pct(v) {
  const n = Number(v || 0);
  return `${n > 0 ? "" : ""}${n.toFixed(1)}%`;
}

export default function ConsolidationDashboard({ entities = [] }) {
  const [data, setData] = useState(null);
  const [view, setView] = useState("consolidated");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true); setError("");
    try {
      const res = await axios.get(`${API}/gl/consolidation`);
      setData(res.data || null);
    } catch (e) {
      setError(e.response?.data?.detail || "Gagal memuat data konsolidasi.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const cons = data?.consolidated || {};
  const rows = data?.entities || [];
  const realRows = rows.filter((r) => !r.is_shared);
  const maxRevenue = Math.max(1, ...rows.map((r) => r.revenue || 0));

  return (
    <div data-testid="consolidation-view">
      {/* ── Header KPI (selalu gabungan) ── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-3">
        <Kpi testId="cons-kpi-revenue" label="Total Pendapatan" value={formatCurrency(cons.revenue)} icon={TrendingUp} tone="text-[#1B7F4B]" />
        <Kpi testId="cons-kpi-gross" label="Laba Kotor" value={formatCurrency(cons.gross_profit)} icon={ArrowUpRight} />
        <Kpi testId="cons-kpi-net" label="Laba Bersih" value={formatCurrency(cons.net_income)} icon={PiggyBank} tone={cons.net_income >= 0 ? "text-[#1B7F4B]" : "text-[#C0392B]"} />
        <Kpi testId="cons-kpi-margin" label="Margin Bersih" value={pct(cons.net_margin)} icon={Percent} tone={cons.net_margin >= 0 ? "text-[#0058CC]" : "text-[#C0392B]"} />
      </div>

      <div className="section-card">
        <div className="section-head">
          <div className="flex items-center gap-1.5">
            <button data-testid="cons-toggle-consolidated" onClick={() => setView("consolidated")}
              className={`inline-flex items-center gap-1.5 text-[12px] font-semibold rounded-lg px-3 py-1.5 border ${view === "consolidated" ? "bg-[#6B219A] text-white border-[#6B219A]" : "bg-white border-[#EFF0F2] text-[#6B6B73] hover:border-[#D9C4EC]"}`}>
              <Layers size={14} /> Konsolidasi (Gabungan)
            </button>
            <button data-testid="cons-toggle-per-entity" onClick={() => setView("per-entity")}
              className={`inline-flex items-center gap-1.5 text-[12px] font-semibold rounded-lg px-3 py-1.5 border ${view === "per-entity" ? "bg-[#6B219A] text-white border-[#6B219A]" : "bg-white border-[#EFF0F2] text-[#6B6B73] hover:border-[#D9C4EC]"}`}>
              <Building2 size={14} /> Per-PT (Bandingkan)
            </button>
          </div>
          <div className="flex items-center gap-2 ml-auto">
            <span className="text-[11px] text-[#9A9BA3]" data-testid="cons-entity-count">{cons.entity_count || realRows.length} entitas</span>
            <button data-testid="cons-refresh" className="icon-button" onClick={load} aria-label="Refresh"><RefreshCw size={14} className={loading ? "animate-spin" : ""} /></button>
          </div>
        </div>
        <div className="section-body">
          <ErrorNotice message={error} onRetry={load} onDismiss={() => setError("")} testId="cons-error" />

          {loading ? (
            <div className="grid gap-2" data-testid="cons-loading">{[0, 1, 2, 3].map((i) => <div key={i} className="h-16 bg-[#F5F5F7] rounded animate-pulse" />)}</div>
          ) : rows.length === 0 ? (
            <div data-testid="cons-empty" className="py-12 text-center text-[12px] text-[#8E8E93]">
              <Landmark size={26} className="mx-auto mb-2 text-gray-300" />Belum ada data keuangan. Posting jurnal terlebih dahulu di Buku Besar.
            </div>
          ) : view === "consolidated" ? (
            <ConsolidatedView cons={cons} rows={rows} maxRevenue={maxRevenue} entities={entities} />
          ) : (
            <PerEntityView rows={rows} entities={entities} />
          )}
        </div>
      </div>
    </div>
  );
}

// ─── KONSOLIDASI (GABUNGAN) ──────────────────────────────────────────────────
function ConsolidatedView({ cons, rows, maxRevenue, entities }) {
  return (
    <div data-testid="cons-consolidated" className="grid lg:grid-cols-2 gap-4">
      {/* Laba Rugi gabungan */}
      <div className="rounded-lg border border-[#EFF0F2] overflow-hidden">
        <div className="px-3 py-2 bg-[#FAF6FE] border-b border-[#EFF0F2] flex items-center gap-2">
          <TrendingUp size={14} className="text-[#6B219A]" /><h3 className="text-[12px] font-bold text-[#1C1C1E]">Laba Rugi (Gabungan)</h3>
        </div>
        <div className="divide-y divide-[#F5F5F7] text-[12px]">
          <StatementRow label="Pendapatan" value={cons.revenue} positive />
          <StatementRow label="Harga Pokok Penjualan" value={-cons.cogs} muted />
          <StatementRow label="Laba Kotor" value={cons.gross_profit} bold />
          <StatementRow label="Beban Operasional" value={-cons.opex} muted />
          <StatementRow label="Laba Bersih" value={cons.net_income} bold highlight />
        </div>
      </div>

      {/* Posisi Keuangan gabungan */}
      <div className="rounded-lg border border-[#EFF0F2] overflow-hidden">
        <div className="px-3 py-2 bg-[#FAF6FE] border-b border-[#EFF0F2] flex items-center gap-2">
          <Scale size={14} className="text-[#6B219A]" /><h3 className="text-[12px] font-bold text-[#1C1C1E]">Posisi Keuangan (Gabungan)</h3>
        </div>
        <div className="divide-y divide-[#F5F5F7] text-[12px]">
          <StatementRow label="Total Aset" value={cons.assets} bold />
          <StatementRow label="· Kas & Bank" value={cons.cash} sub />
          <StatementRow label="· Piutang Usaha" value={cons.ar} sub />
          <StatementRow label="· Persediaan" value={cons.inventory} sub />
          <StatementRow label="Total Kewajiban" value={cons.liabilities} bold />
          <StatementRow label="· Hutang Usaha" value={cons.ap} sub />
          <StatementRow label="· PPN Keluaran" value={cons.ppn_out} sub />
          <StatementRow label="Total Ekuitas + Laba" value={cons.equity_total} bold highlight />
        </div>
      </div>

      {/* Kontribusi pendapatan per entitas */}
      <div className="lg:col-span-2 rounded-lg border border-[#EFF0F2] p-3">
        <div className="flex items-center gap-2 mb-3">
          <Building2 size={14} className="text-[#6B219A]" /><h3 className="text-[12px] font-bold text-[#1C1C1E]">Kontribusi Pendapatan per Entitas</h3>
        </div>
        <div className="space-y-2.5" data-testid="cons-contribution">
          {rows.map((r) => {
            const share = cons.revenue > 0 ? (r.revenue / cons.revenue) * 100 : 0;
            const width = Math.max(2, (r.revenue / maxRevenue) * 100);
            return (
              <div key={r.entity_id} data-testid={`cons-contrib-${r.entity_id}`}>
                <div className="flex items-center justify-between text-[11px] mb-1">
                  <span className="flex items-center gap-1.5">
                    <EntityBadge entityId={r.entity_id} entities={entities} />
                    <span className="text-[#6B6B73]">{r.entity_name}</span>
                  </span>
                  <span className="tabular-nums font-semibold text-[#1C1C1E]">{formatCurrency(r.revenue)} <span className="text-[#9A9BA3] font-normal">({share.toFixed(1)}%)</span></span>
                </div>
                <div className="h-2 rounded-full bg-[#F0EAFB] overflow-hidden">
                  <div className="h-full rounded-full" style={{ width: `${width}%`, background: PURPLE }} />
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

// ─── PER-PT (BANDINGKAN) ─────────────────────────────────────────────────────
function PerEntityView({ rows, entities }) {
  return (
    <div data-testid="cons-per-entity">
      <div className="grid sm:grid-cols-2 xl:grid-cols-3 gap-3 mb-4">
        {rows.map((r) => (
          <div key={r.entity_id} data-testid={`cons-card-${r.entity_id}`}
            className={`rounded-lg border p-3 ${r.is_shared ? "border-dashed border-[#D9C4EC] bg-[#FBF8FE]" : "border-[#EFF0F2]"}`}>
            <div className="flex items-center justify-between mb-2.5">
              <div className="min-w-0">
                <EntityBadge entityId={r.entity_id} entities={entities} />
                <p className="text-[12px] font-bold text-[#1C1C1E] mt-1 truncate" title={r.entity_name}>{r.entity_name}</p>
              </div>
              {!r.is_shared && (
                <span className={`text-[9px] font-bold rounded px-1.5 py-0.5 ${r.is_pkp ? "bg-[#E7F0FF] text-[#0058CC]" : "bg-[#F5F5F7] text-[#8E8E93]"}`}>
                  {r.is_pkp ? "PKP" : "Non-PKP"}
                </span>
              )}
            </div>
            <div className="grid grid-cols-2 gap-2">
              <Metric label="Pendapatan" value={formatCurrency(r.revenue)} tone="text-[#1B7F4B]" />
              <Metric label="Laba Bersih" value={formatCurrency(r.net_income)} tone={r.net_income >= 0 ? "text-[#1B7F4B]" : "text-[#C0392B]"} icon={r.net_income >= 0 ? ArrowUpRight : ArrowDownRight} />
              <Metric label="Margin" value={pct(r.net_margin)} />
              <Metric label="Kas & Bank" value={formatCurrency(r.cash)} icon={Wallet} />
              <Metric label="Piutang" value={formatCurrency(r.ar)} />
              <Metric label="Hutang" value={formatCurrency(r.ap)} />
            </div>
          </div>
        ))}
      </div>

      {/* Tabel bandingkan */}
      <div className="overflow-auto rounded-md border border-[#EFF0F2]">
        <table className="w-full text-[12px]" data-testid="cons-compare-table">
          <thead>
            <tr className="text-left text-[10px] font-bold uppercase text-[#8E8E93] bg-[#FAFBFC] border-b border-[#EFF0F2]">
              <th className="px-3 py-2">Entitas</th>
              <th className="px-3 py-2 text-right">Pendapatan</th>
              <th className="px-3 py-2 text-right">Laba Kotor</th>
              <th className="px-3 py-2 text-right">Beban Ops</th>
              <th className="px-3 py-2 text-right">Laba Bersih</th>
              <th className="px-3 py-2 text-right">Margin</th>
              <th className="px-3 py-2 text-right">Aset</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.entity_id} data-testid={`cons-compare-row-${r.entity_id}`} className="border-b border-[#F5F5F7] last:border-0">
                <td className="px-3 py-2"><EntityBadge entityId={r.entity_id} entities={entities} /> <span className="text-[#6B6B73] ml-1">{r.short_name}</span></td>
                <td className="px-3 py-2 text-right tabular-nums">{formatCurrency(r.revenue)}</td>
                <td className="px-3 py-2 text-right tabular-nums">{formatCurrency(r.gross_profit)}</td>
                <td className="px-3 py-2 text-right tabular-nums text-[#C0392B]">{formatCurrency(r.opex)}</td>
                <td className={`px-3 py-2 text-right tabular-nums font-semibold ${r.net_income >= 0 ? "text-[#1B7F4B]" : "text-[#C0392B]"}`}>{formatCurrency(r.net_income)}</td>
                <td className="px-3 py-2 text-right tabular-nums">{pct(r.net_margin)}</td>
                <td className="px-3 py-2 text-right tabular-nums">{formatCurrency(r.assets)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ─── Sub-komponen ────────────────────────────────────────────────────────────
function StatementRow({ label, value, bold, highlight, muted, sub, positive }) {
  return (
    <div className={`flex items-center justify-between px-3 py-2 ${highlight ? "bg-[#FAF6FE]" : ""} ${sub ? "pl-5" : ""}`}>
      <span className={`${bold ? "font-bold text-[#1C1C1E]" : sub ? "text-[#9A9BA3] text-[11px]" : "text-[#6B6B73]"}`}>{label}</span>
      <span className={`tabular-nums ${bold ? "font-bold" : ""} ${highlight ? "text-[#6B219A]" : muted ? "text-[#C0392B]" : positive ? "text-[#1B7F4B]" : "text-[#1C1C1E]"}`}>{formatCurrency(value)}</span>
    </div>
  );
}

function Metric({ label, value, tone = "text-[#1C1C1E]", icon: Icon }) {
  return (
    <div>
      <p className="text-[9px] font-bold uppercase tracking-wide text-[#9A9BA3]">{label}</p>
      <p className={`text-[12px] font-bold tabular-nums truncate flex items-center gap-1 ${tone}`}>
        {Icon && <Icon size={12} />}{value}
      </p>
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
