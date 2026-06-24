/**
 * ARReceiptModal (EPIC3B) — Catat penerimaan pembayaran customer + alokasi ke order.
 * POST /api/ar-receipts. Mode Otomatis (FIFO) atau Manual (per order).
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { X, Wallet } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import KNSelect from "../../components/KNSelect";
import ErrorNotice from "../../components/ErrorNotice";
import { formatCurrency } from "../../utils/formatters";

const METHODS = [
  { value: "transfer", label: "Transfer Bank" },
  { value: "cash", label: "Tunai" },
  { value: "giro", label: "Giro / Cek" },
  { value: "qris", label: "QRIS" },
];

function today() { return new Date().toISOString().slice(0, 10); }

export default function ARReceiptModal({ customerId, customerName, preselectOrderId, onClose, onDone, onError }) {
  const [openOrders, setOpenOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [mode, setMode] = useState("auto"); // auto (FIFO) | manual
  const [amount, setAmount] = useState("");
  const [method, setMethod] = useState("transfer");
  const [date, setDate] = useState(today());
  const [notes, setNotes] = useState("");
  const [alloc, setAlloc] = useState({}); // order_id -> amount
  const [busy, setBusy] = useState(false);
  const [deposit, setDeposit] = useState(0);
  const [useDeposit, setUseDeposit] = useState(false);
  const [depositAmt, setDepositAmt] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [ro, rd] = await Promise.all([
        axios.get(`${API}/ar-receipts/open-orders`, { params: { customer_id: customerId } }),
        axios.get(`${API}/ar-receipts/deposit`, { params: { customer_id: customerId } }).catch(() => ({ data: {} })),
      ]);
      const list = Array.isArray(ro.data) ? ro.data : [];
      setOpenOrders(list);
      setDeposit(Number(rd.data?.deposit_balance || 0));
      const pre = preselectOrderId && list.find((o) => o.order_id === preselectOrderId);
      if (pre) {
        setMode("manual");
        setAlloc({ [pre.order_id]: pre.outstanding });
        setAmount(String(pre.outstanding));
      } else {
        const total = list.reduce((s, o) => s + Number(o.outstanding || 0), 0);
        setAmount(String(total));
      }
      setError("");
    } catch (e) {
      setError(e.response?.data?.detail || "Gagal memuat order terbuka.");
    } finally { setLoading(false); }
  }, [customerId, preselectOrderId]);

  useEffect(() => { load(); }, [load]);

  const allocTotal = useMemo(
    () => Object.values(alloc).reduce((s, v) => s + (Number(v) || 0), 0),
    [alloc]
  );
  const effectiveAmount = mode === "manual" ? allocTotal : Number(amount) || 0;
  const depositUse = useDeposit ? Math.min(Number(depositAmt) || 0, deposit) : 0;
  const totalFunds = effectiveAmount + depositUse;

  function setAllocFor(orderId, value, max) {
    const v = Math.min(Math.max(Number(value) || 0, 0), max);
    setAlloc((p) => ({ ...p, [orderId]: v }));
  }

  async function submit() {
    if (totalFunds <= 0) { setError("Jumlah pembayaran harus lebih dari 0."); return; }
    setBusy(true);
    try {
      const body = {
        customer_id: customerId,
        amount: effectiveAmount,
        method,
        receipt_date: new Date(date).toISOString(),
        notes,
        use_deposit_amount: depositUse,
      };
      if (mode === "manual") {
        body.allocations = Object.entries(alloc)
          .filter(([, v]) => Number(v) > 0)
          .map(([order_id, v]) => ({ order_id, amount: Number(v) }));
        if (body.allocations.length === 0) { setError("Isi alokasi minimal satu order."); setBusy(false); return; }
      }
      const r = await axios.post(`${API}/ar-receipts`, body);
      onDone?.(`Pembayaran ${r.data.number} (${formatCurrency(r.data.applied_total ?? r.data.amount)}) dicatat untuk ${customerName}.`);
    } catch (e) {
      const msg = e.response?.data?.detail || "Gagal mencatat pembayaran.";
      setError(msg); onError?.(msg);
    } finally { setBusy(false); }
  }

  const cashHint = ["cash", "tunai", "kontan"].includes(method)
    ? "Tunai → masuk Kas Kecil (per entitas)."
    : "Transfer/Giro/QRIS → masuk Kas Besar (bank).";

  return (
    <div className="modal-overlay" data-testid="ar-receipt-modal" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="modal-card" style={{ maxWidth: 560, width: "94vw" }}>
        <div className="flex items-center justify-between px-4 py-3 border-b border-[#EFF0F2]">
          <div className="flex items-center gap-2"><Wallet size={16} className="text-[#0058CC]" /><h2 className="text-[14px] font-bold">Catat Pembayaran · {customerName}</h2></div>
          <button onClick={onClose} className="icon-button" data-testid="ar-receipt-close"><X size={16} /></button>
        </div>
        <div className="p-4 space-y-3 max-h-[78vh] overflow-y-auto">
          <ErrorNotice message={error} onRetry={load} onDismiss={() => setError("")} testId="ar-receipt-error" />

          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="text-[11px] font-bold uppercase tracking-wide text-[#6B6B73]">Metode</label>
              <KNSelect data-testid="ar-receipt-method" className="field" value={method} onValueChange={setMethod} options={METHODS} />
            </div>
            <div>
              <label className="text-[11px] font-bold uppercase tracking-wide text-[#6B6B73]">Tanggal</label>
              <input data-testid="ar-receipt-date" type="date" className="field" value={date} onChange={(e) => setDate(e.target.value)} />
            </div>
          </div>
          <p className="text-[10.5px] text-[#9A9BA3] -mt-1" data-testid="ar-receipt-cash-hint">{cashHint}</p>

          {deposit > 0 && (
            <div className="rounded-md border border-[#E6F6EC] bg-[#F2FBF5] px-3 py-2" data-testid="ar-receipt-deposit-box">
              <label className="flex items-center gap-2 text-[12px] font-semibold text-[#1B7F4B] cursor-pointer">
                <input type="checkbox" data-testid="ar-receipt-use-deposit" checked={useDeposit}
                  onChange={(e) => { setUseDeposit(e.target.checked); if (e.target.checked && !depositAmt) setDepositAmt(String(deposit)); }} />
                Pakai deposit pelanggan (tersedia {formatCurrency(deposit)})
              </label>
              {useDeposit && (
                <input data-testid="ar-receipt-deposit-amount" type="number" className="field mt-2 py-1 text-[12px]"
                  value={depositAmt} placeholder="0"
                  onChange={(e) => setDepositAmt(String(Math.min(Math.max(Number(e.target.value) || 0, 0), deposit)))} />
              )}
            </div>
          )}

          <div className="tab-bar">
            <button data-testid="ar-receipt-mode-auto" className={`tab-button ${mode === "auto" ? "active" : ""}`} onClick={() => setMode("auto")}>Otomatis (FIFO)</button>
            <button data-testid="ar-receipt-mode-manual" className={`tab-button ${mode === "manual" ? "active" : ""}`} onClick={() => setMode("manual")}>Manual per Order</button>
          </div>

          {mode === "auto" ? (
            <div>
              <label className="text-[11px] font-bold uppercase tracking-wide text-[#6B6B73]">Jumlah Diterima</label>
              <input data-testid="ar-receipt-amount" type="number" className="field" value={amount} onChange={(e) => setAmount(e.target.value)} placeholder="0" />
              <p className="text-[10.5px] text-[#9A9BA3] mt-1">Dialokasikan otomatis ke order terbuka tertua lebih dulu.</p>
            </div>
          ) : null}

          <div className="rounded-md border border-[#EFF0F2] overflow-hidden">
            <div className="px-3 py-1.5 bg-[#FAFBFC] text-[10px] font-bold uppercase text-[#6B6B73] border-b border-[#EFF0F2] flex justify-between">
              <span>Order Terbuka</span><span>{openOrders.length} order</span>
            </div>
            {loading ? (
              <div className="py-8 text-center text-[12px] text-[#6B6B73]" data-testid="ar-receipt-loading">Memuat...</div>
            ) : openOrders.length === 0 ? (
              <div className="py-8 text-center text-[12px] text-[#6B6B73]" data-testid="ar-receipt-no-orders">Tidak ada order terbuka. 🎉</div>
            ) : (
              <div className="divide-y divide-[#EFF0F2] max-h-[240px] overflow-y-auto">
                {openOrders.map((o) => (
                  <div key={o.order_id} data-testid={`ar-receipt-order-${o.order_id}`} className="flex items-center gap-2 px-3 py-2 text-[12px]">
                    <div className="flex-1 min-w-0">
                      <p className="font-semibold text-[#0058CC]">{o.number}</p>
                      <p className="text-[10px] text-[#6B6B73] tabular-nums">Outstanding {formatCurrency(o.outstanding)}</p>
                    </div>
                    {mode === "manual" ? (
                      <input data-testid={`ar-receipt-alloc-${o.order_id}`} type="number" className="field w-36 py-1 text-[12px]"
                        value={alloc[o.order_id] ?? ""} placeholder="0"
                        onChange={(e) => setAllocFor(o.order_id, e.target.value, o.outstanding)} />
                    ) : (
                      <span className="text-[11px] text-[#9A9BA3] tabular-nums">{formatCurrency(o.outstanding)}</span>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          <div>
            <label className="text-[11px] font-bold uppercase tracking-wide text-[#6B6B73]">Catatan</label>
            <input data-testid="ar-receipt-notes" className="field" value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="No. referensi / bank..." />
          </div>

          <div className="flex items-center justify-between pt-1">
            <div className="text-[12px]">
              <span className="text-[#6B6B73]">Total dibayar: </span>
              <span data-testid="ar-receipt-total" className="font-bold tabular-nums text-[#1B7F4B]">{formatCurrency(totalFunds)}</span>
              {depositUse > 0 && <span className="text-[10.5px] text-[#6B6B73] ml-1">(kas {formatCurrency(effectiveAmount)} + deposit {formatCurrency(depositUse)})</span>}
            </div>
            <div className="flex gap-2">
              <button onClick={onClose} className="secondary-button">Batal</button>
              <button data-testid="ar-receipt-submit" disabled={busy || totalFunds <= 0} onClick={submit} className="primary-button">
                {busy ? "Menyimpan..." : "Simpan Pembayaran"}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
