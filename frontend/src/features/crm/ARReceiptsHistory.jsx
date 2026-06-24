/**
 * ARReceiptsHistory (EPIC3B) — daftar penerimaan pembayaran terbaru.
 * GET /api/ar-receipts. Refresh saat `refreshKey` berubah.
 */
import { useCallback, useEffect, useState } from "react";
import { Wallet, RefreshCw, Ban } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import ErrorNotice from "../../components/ErrorNotice";
import { formatCurrency } from "../../utils/formatters";
import { fmtDate } from "./crmUtils";

export default function ARReceiptsHistory({ refreshKey, selectedEntity, currentUser, onChanged }) {
  const canVoid = ["admin", "manager"].includes(currentUser?.role);
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [voiding, setVoiding] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await axios.get(`${API}/ar-receipts`);
      let list = Array.isArray(r.data) ? r.data : [];
      if (selectedEntity && selectedEntity !== "all") list = list.filter((x) => x.entity_id === selectedEntity);
      setRows(list.slice(0, 25));
      setError("");
    } catch (e) {
      setError(e.response?.data?.detail || "Gagal memuat riwayat pembayaran.");
    } finally { setLoading(false); }
  }, [selectedEntity]);

  useEffect(() => { load(); }, [load, refreshKey]);

  async function voidReceipt(r) {
    if (!window.confirm(`Batalkan penerimaan ${r.number} (${formatCurrency(r.amount)})? Pembayaran pada order & kas akan dibalik.`)) return;
    setVoiding(r.id);
    try {
      await axios.post(`${API}/ar-receipts/${r.id}/void`);
      await load();
      onChanged?.(`Penerimaan ${r.number} dibatalkan (void).`);
    } catch (e) {
      setError(e.response?.data?.detail || "Gagal membatalkan penerimaan.");
    } finally { setVoiding(""); }
  }

  return (
    <div className="section-card mt-3" data-testid="ar-receipts-history">
      <div className="section-head">
        <div className="flex items-center gap-2"><Wallet size={15} className="text-[#1B7F4B]" /><h2>Riwayat Pembayaran (AR)</h2></div>
        <button data-testid="ar-history-refresh" className="icon-button ml-auto" onClick={load} aria-label="Refresh"><RefreshCw size={13} className={loading ? "animate-spin" : ""} /></button>
      </div>
      <div className="section-body">
        <ErrorNotice message={error} onRetry={load} onDismiss={() => setError("")} testId="ar-history-error" />
        {loading ? (
          <div className="py-6 text-center text-[12px] text-[#6B6B73]" data-testid="ar-history-loading">Memuat...</div>
        ) : rows.length === 0 ? (
          <div className="py-8 text-center text-[12px] text-[#6B6B73]" data-testid="ar-history-empty">Belum ada pembayaran tercatat.</div>
        ) : (
          <div className="overflow-auto rounded-md border border-[#EFF0F2]">
            <table className="w-full text-[12px]" data-testid="ar-history-table">
              <thead>
                <tr className="text-left text-[10px] font-bold uppercase text-[#8E8E93] bg-[#FAFBFC] border-b border-[#EFF0F2]">
                  <th className="px-3 py-2">No.</th><th className="px-3 py-2">Tanggal</th><th className="px-3 py-2">Pelanggan</th>
                  <th className="px-3 py-2">Metode</th><th className="px-3 py-2 text-right">Jumlah</th><th className="px-3 py-2">Order</th>
                  <th className="px-3 py-2 text-center">Status</th>{canVoid && <th className="px-3 py-2 text-center">Aksi</th>}
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => {
                  const isVoid = r.status === "void";
                  return (
                  <tr key={r.id} data-testid={`ar-history-row-${r.id}`} className={`border-b border-[#F5F5F7] last:border-0 ${isVoid ? "opacity-55" : ""}`}>
                    <td className="px-3 py-2 font-mono text-[11px] text-[#0058CC]">{r.number}</td>
                    <td className="px-3 py-2 text-[#6B6B73]">{fmtDate(r.receipt_date)}</td>
                    <td className="px-3 py-2 font-semibold">{r.customer_name}</td>
                    <td className="px-3 py-2 capitalize text-[#3C3C43]">{r.method}</td>
                    <td className={`px-3 py-2 text-right tabular-nums font-semibold ${isVoid ? "line-through text-[#9A9BA3]" : "text-[#1B7F4B]"}`}>{formatCurrency(r.amount)}</td>
                    <td className="px-3 py-2 text-[11px] text-[#6B6B73]">{(r.allocations || []).map((a) => a.order_number).join(", ") || "—"}</td>
                    <td className="px-3 py-2 text-center">
                      <span data-testid={`ar-history-status-${r.id}`} className={`status-pill ${isVoid ? "pill-danger" : "pill-success"}`}>{isVoid ? "Void" : "Posted"}</span>
                    </td>
                    {canVoid && (
                      <td className="px-3 py-2 text-center">
                        {!isVoid && (
                          <button data-testid={`ar-history-void-${r.id}`} className="icon-button text-[#D14343]" disabled={voiding === r.id}
                            onClick={() => voidReceipt(r)} title="Batalkan (void) penerimaan"><Ban size={14} /></button>
                        )}
                      </td>
                    )}
                  </tr>
                );})}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
