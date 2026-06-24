import { useEffect, useState } from "react";
import {
  Scan, Truck, CheckCircle, AlertTriangle,
  Camera, CameraOff, FileText, Send, X, ChevronRight,
} from "lucide-react";
import axios, { API } from "../../services/apiClient";
import ErrorNotice from "../../components/ErrorNotice";
import { formatQty } from "../../utils/formatters";

const STATUS_MAP = {
  created:    { label: "Created", cls: "bg-gray-100 text-gray-600" },
  picking:    { label: "Picking", cls: "bg-blue-100 text-blue-700" },
  packing:    { label: "Packing", cls: "bg-purple-100 text-purple-700" },
  staging:    { label: "Staging", cls: "bg-indigo-100 text-indigo-700" },
  partially_shipped: { label: "Terkirim Sebagian", cls: "bg-orange-100 text-orange-700" },
  dispatched: { label: "Dispatched", cls: "bg-green-100 text-green-700" },
  escalated:  { label: "Escalated", cls: "bg-red-100 text-red-700" },
};

function Badge({ status }) {
  const s = STATUS_MAP[status] || { label: status, cls: "bg-gray-100 text-gray-600" };
  return <span className={`inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-semibold ${s.cls}`}>{s.label}</span>;
}

function MiniBar({ pct, status }) {
  const color = status === 'dispatched' ? 'bg-[#34C759]' : status === 'escalated' ? 'bg-red-400' : 'bg-[#FF9500]';
  return (
    <div className="h-1 w-full rounded-full bg-gray-200 overflow-hidden">
      <div className={`h-full rounded-full transition-all ${color}`} style={{ width: `${Math.min(pct, 100)}%` }} />
    </div>
  );
}

export default function OutboundScanInterface({ user }) {
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [selectedTask, setSelectedTask] = useState(null);
  const [filterStatus, setFilterStatus] = useState("all");

  const [cameraActive, setCameraActive] = useState(false);
  const [scanValue, setScanValue] = useState("");
  const [scanData, setScanData] = useState({ actual_qty: 0, batch: "", lot: "", roll_id: "", bin_id: "" });

  const [showEscalateModal, setShowEscalateModal] = useState(false);
  const [escalationReason, setEscalationReason] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [shipQty, setShipQty] = useState("");          // Sub-fase 1.8 — qty kirim parsial
  const [lastShipment, setLastShipment] = useState(null);

  useEffect(() => { fetchTasks(); }, [filterStatus]);

  const fetchTasks = async () => {
    setLoading(true);
    try {
      const params = filterStatus !== "all" ? `?status=${filterStatus}` : "";
      const res = await axios.get(`${API}/outbound/tasks${params}`);
      setTasks(res.data);
      setError("");
    } catch (e) { setError(e.response?.data?.detail || "Gagal memuat outbound task."); }
    finally { setLoading(false); }
  };

  const startCamera = async () => {
    try {
      const { BrowserMultiFormatReader } = await import("@zxing/browser");
      const reader = new BrowserMultiFormatReader();
      const el = document.getElementById("outbound-video-compact");
      if (!el) return;
      await reader.decodeFromVideoDevice(null, el, (result) => {
        if (result) { setScanValue(result.getText()); stopCamera(); }
      });
      setCameraActive(true);
    } catch { alert("Gagal buka kamera."); }
  };

  const stopCamera = () => {
    const el = document.getElementById("outbound-video-compact");
    if (el?.srcObject) { el.srcObject.getTracks().forEach(t => t.stop()); el.srcObject = null; }
    setCameraActive(false);
  };

  const handleScanPick = async () => {
    if (!selectedTask || scanData.actual_qty <= 0) return alert("Masukkan qty yang valid");
    setSubmitting(true);
    try {
      const res = await axios.post(`${API}/outbound/tasks/${selectedTask.id}/scan-pick`, null, { params: scanData });
      setTasks(prev => prev.map(t => t.id === selectedTask.id ? res.data : t));
      setSelectedTask(res.data);
      setScanData({ actual_qty: 0, batch: "", lot: "", roll_id: "", bin_id: "" });
      setScanValue("");
    } catch (e) { alert(e.response?.data?.detail || "Gagal scan"); }
    finally { setSubmitting(false); }
  };

  const handleDispatch = async (partial = false) => {
    if (!selectedTask) return;
    const picked = Number(selectedTask.picked_qty || 0);
    const shipped = Number(selectedTask.shipped_qty || 0);
    const maxShip = Math.round((Math.min(picked, selectedTask.quantity) - shipped) * 100) / 100;
    if (maxShip <= 0) return alert("Belum ada qty ter-pick yang siap dikirim. Pick dulu sebelum dispatch.");
    let qty = maxShip;
    if (partial) {
      qty = Number(shipQty);
      if (!qty || qty <= 0 || qty > maxShip + 0.01) return alert(`Qty kirim harus antara 1 dan ${maxShip}.`);
    }
    if (!window.confirm(`Kirim ${qty} ${selectedTask.unit || ""}?`)) return;
    setSubmitting(true);
    try {
      const res = await axios.post(`${API}/outbound/tasks/${selectedTask.id}/dispatch`, null,
        qty < maxShip - 0.001 ? { params: { ship_qty: qty } } : {});
      const sj = res.data?.shipment?.shipment_no;
      setShipQty("");
      setLastShipment(res.data?.shipment || null);
      await fetchTasks();
      setSelectedTask(res.data?.task || null);
      if (sj) alert(`Terkirim. No. Surat Jalan: ${sj}`);
    } catch (e) { alert(e.response?.data?.detail || "Gagal dispatch"); }
    finally { setSubmitting(false); }
  };

  const handleEscalate = async () => {
    if (!escalationReason.trim()) return alert("Masukkan alasan escalation");
    setSubmitting(true);
    try {
      await axios.post(`${API}/outbound/tasks/${selectedTask.id}/escalate`, null, {
        params: { reason: escalationReason }
      });
      setShowEscalateModal(false);
      setEscalationReason("");
      fetchTasks();
      setSelectedTask(null);
    } catch (e) { alert(e.response?.data?.detail || "Gagal escalate"); }
    finally { setSubmitting(false); }
  };

  const handleViewSuratJalan = (orderId, warehouseId) => {
    const url = warehouseId
      ? `${API}/outbound/so/${orderId}/surat-jalan?warehouse_id=${warehouseId}`
      : `${API}/outbound/so/${orderId}/surat-jalan`;
    window.open(url, '_blank');
  };

  const FILTERS = ["all", "created", "picking", "packing", "staging", "partially_shipped", "escalated"];
  const FILTER_LABELS = { all: "Semua", created: "Created", picking: "Picking", packing: "Packing", staging: "Staging", partially_shipped: "Parsial", escalated: "Escalated" };

  return (
    <div data-testid="outbound-scan-panel" className="flex flex-col gap-3">
      <ErrorNotice message={error} onRetry={fetchTasks} onDismiss={() => setError("")} testId="outbound-scan-error" />
      {/* Filter strip */}
      <div className="flex items-center gap-1.5 overflow-x-auto">
        {FILTERS.map(s => (
          <button key={s}
            data-testid={`filter-status-${s}`}
            onClick={() => setFilterStatus(s)}
            className={`rounded-full px-3 py-1 text-xs font-medium whitespace-nowrap transition-all ${filterStatus === s ? "bg-[#FF9500] text-white" : "bg-white border border-[#E5E5EA] text-[#6B6B73] hover:border-[#FF9500]"}`}>
            {FILTER_LABELS[s]}
          </button>
        ))}
        <span className="ml-auto text-[11px] text-[#6B6B73] whitespace-nowrap">{tasks.length} task</span>
      </div>

      {/* 2-panel layout */}
      <div className="grid grid-cols-1 lg:grid-cols-[340px_1fr] gap-3">
        {/* LEFT: Task List */}
        <div className="bg-white border border-[#EFF0F2] rounded-xl overflow-hidden">
          <div className="px-3 py-2 border-b border-[#EFF0F2] bg-[#FAFBFC] flex items-center justify-between">
            <span className="text-[11px] font-bold uppercase tracking-wide text-[#6B6B73]">Outbound Tasks</span>
            <button onClick={fetchTasks} className="text-[#007AFF] text-[11px] font-medium">Refresh</button>
          </div>
          {loading ? (
            <div className="py-8 text-center text-[12px] text-[#6B6B73]">Loading...</div>
          ) : tasks.length === 0 ? (
            <div className="py-8 text-center text-[12px] text-[#6B6B73]">
              <Truck size={28} className="mx-auto mb-2 text-gray-300" />
              <p>Tidak ada outbound task</p>
            </div>
          ) : (
            <div className="divide-y divide-[#EFF0F2] overflow-y-auto max-h-[520px]">
              {tasks.map(task => {
                const pct = task.quantity ? Math.min((task.picked_qty || 0) / task.quantity * 100, 100) : 0;
                const isSelected = selectedTask?.id === task.id;
                return (
                  <button key={task.id}
                    data-testid={`outbound-task-${task.id}`}
                    onClick={() => { setSelectedTask(task); stopCamera(); }}
                    className={`w-full text-left px-3 py-2.5 hover:bg-[#FFF8EE] transition-colors ${isSelected ? 'bg-[#FFF4E0] border-l-2 border-[#FF9500]' : ''}`}>
                    <div className="flex items-center justify-between gap-2 mb-1">
                      <span className="text-[12px] font-bold text-[#FF9500]">{task.order_number}</span>
                      <div className="flex items-center gap-1">
                        <Badge status={task.status} />
                        <ChevronRight size={12} className="text-gray-400" />
                      </div>
                    </div>
                    <p className="text-[11px] text-[#3C3C43] truncate">{task.sku}</p>
                    <p className="text-[10px] text-[#8E8E93] truncate">{task.warehouse_name}</p>
                    <div className="mt-1.5">
                      <MiniBar pct={pct} status={task.status} />
                      <div className="flex justify-between mt-0.5">
                        <span className="text-[10px] text-[#8E8E93]">{formatQty(task.picked_qty || 0)}/{formatQty(task.quantity)} {task.unit}</span>
                        <span className="text-[10px] font-semibold text-[#3C3C43]">{pct.toFixed(0)}%</span>
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {/* RIGHT: Pick Panel */}
        {selectedTask ? (
          <div className="bg-white border border-[#EFF0F2] rounded-xl overflow-hidden">
            <div className="px-3 py-2 border-b border-[#EFF0F2] bg-[#FAFBFC] flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="text-[11px] font-bold uppercase tracking-wide text-[#6B6B73]">Pick & Dispatch</span>
                <Badge status={selectedTask.status} />
              </div>
              <button onClick={() => { stopCamera(); setSelectedTask(null); }} className="text-[#6B6B73] hover:text-black">
                <X size={14} />
              </button>
            </div>

            <div className="p-3 space-y-3">
              {/* Info bar */}
              <div className="grid grid-cols-3 gap-2">
                <div className="bg-[#FFF8EE] rounded-lg p-2">
                  <p className="text-[10px] text-[#6B6B73] uppercase font-semibold">SO</p>
                  <p className="text-[12px] font-bold text-[#FF9500]">{selectedTask.order_number}</p>
                </div>
                <div className="bg-[#FFF8EE] rounded-lg p-2">
                  <p className="text-[10px] text-[#6B6B73] uppercase font-semibold">Gudang</p>
                  <p className="text-[11px] font-semibold truncate">{selectedTask.warehouse_name}</p>
                </div>
                <div className="bg-[#FFF8EE] rounded-lg p-2">
                  <p className="text-[10px] text-[#6B6B73] uppercase font-semibold">Progress</p>
                  <p className="text-[12px] font-bold">{formatQty(selectedTask.picked_qty || 0)}<span className="text-[10px] text-[#6B6B73]">/{formatQty(selectedTask.quantity)}</span></p>
                </div>
              </div>

              <div className="bg-[#FAFBFC] rounded-lg p-2">
                <p className="text-[11px] text-[#3C3C43] font-medium">{selectedTask.product_name}</p>
                <p className="text-[10.5px] text-[#6B6B73]">SKU: {selectedTask.sku} · Customer: {selectedTask.customer_name}</p>
              </div>

              {/* Escalation info */}
              {selectedTask.status === 'escalated' && selectedTask.escalation && (
                <div className="bg-red-50 border border-red-200 rounded-lg p-2 text-[11px]">
                  <p className="font-semibold text-red-700">Escalated: {selectedTask.escalation.escalated_by}</p>
                  <p className="text-red-600">{selectedTask.escalation.reason}</p>
                  {selectedTask.escalation.status === 'resolved' && (
                    <p className="text-green-700 mt-1 inline-flex items-center gap-1"><CheckCircle size={12} /> Resolved: {selectedTask.escalation.resolution_notes}</p>
                  )}
                </div>
              )}

              {/* Camera + Form */}
              {!['dispatched', 'escalated'].includes(selectedTask.status) && (
                <>
                  <div className="flex items-center gap-2">
                    <button onClick={cameraActive ? stopCamera : startCamera}
                      className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[11px] font-medium ${cameraActive ? 'bg-red-500 text-white' : 'bg-[#FFF8EE] text-[#FF9500] border border-[#FF9500]/30'}`}>
                      {cameraActive ? <><CameraOff size={12} /> Stop</> : <><Camera size={12} /> Camera</>}
                    </button>
                    {scanValue && <span className="text-[11px] text-green-700 font-medium inline-flex items-center gap-1"><CheckCircle size={11} /> {scanValue}</span>}
                  </div>
                  <video id="outbound-video-compact"
                    className={`w-full rounded-lg border border-[#FF9500]/30 ${cameraActive ? 'block' : 'hidden'}`}
                    style={{ maxHeight: '160px' }} />

                  <div className="grid grid-cols-3 gap-2">
                    <div className="col-span-1">
                      <label className="block text-[10px] font-semibold text-[#6B6B73] mb-1">Picked Qty *</label>
                      <input type="number" value={scanData.actual_qty}
                        onChange={e => setScanData({ ...scanData, actual_qty: parseFloat(e.target.value) || 0 })}
                        className="w-full border border-[#E5E5EA] rounded-lg px-2 py-1.5 text-sm" placeholder="0" />
                    </div>
                    <div>
                      <label className="block text-[10px] font-semibold text-[#6B6B73] mb-1">Batch</label>
                      <input type="text" value={scanData.batch}
                        onChange={e => setScanData({ ...scanData, batch: e.target.value })}
                        className="w-full border border-[#E5E5EA] rounded-lg px-2 py-1.5 text-sm" />
                    </div>
                    <div>
                      <label className="block text-[10px] font-semibold text-[#6B6B73] mb-1">Lot</label>
                      <input type="text" value={scanData.lot}
                        onChange={e => setScanData({ ...scanData, lot: e.target.value })}
                        className="w-full border border-[#E5E5EA] rounded-lg px-2 py-1.5 text-sm" />
                    </div>
                    <div>
                      <label className="block text-[10px] font-semibold text-[#6B6B73] mb-1">Roll ID</label>
                      <input type="text" value={scanData.roll_id}
                        onChange={e => setScanData({ ...scanData, roll_id: e.target.value })}
                        className="w-full border border-[#E5E5EA] rounded-lg px-2 py-1.5 text-sm" />
                    </div>
                    <div className="col-span-2">
                      <label className="block text-[10px] font-semibold text-[#6B6B73] mb-1">Bin Location</label>
                      <input type="text" value={scanData.bin_id}
                        onChange={e => setScanData({ ...scanData, bin_id: e.target.value })}
                        className="w-full border border-[#E5E5EA] rounded-lg px-2 py-1.5 text-sm" />
                    </div>
                  </div>

                  <div className="flex gap-2">
                    <button onClick={handleScanPick} disabled={submitting}
                      data-testid={`scan-task-${selectedTask.id}`}
                      className="flex-1 bg-[#FF9500] hover:bg-[#CC7700] text-white rounded-lg px-3 py-2 text-[12px] font-semibold flex items-center justify-center gap-1.5 disabled:opacity-50">
                      <CheckCircle size={13} /> Submit Pick
                    </button>
                    <button onClick={() => setShowEscalateModal(true)}
                      className="bg-red-50 border border-red-300 text-red-600 hover:bg-red-100 rounded-lg px-3 py-2 text-[12px] font-semibold flex items-center gap-1.5">
                      <AlertTriangle size={13} /> Escalate
                    </button>
                  </div>

                  {/* Sub-fase 1.8 — Dispatch (mendukung pengiriman PARSIAL) */}
                  {(() => {
                    const picked = Number(selectedTask.picked_qty || 0);
                    const shipped = Number(selectedTask.shipped_qty || 0);
                    const maxShip = Math.round((Math.min(picked, selectedTask.quantity) - shipped) * 100) / 100;
                    if (maxShip <= 0) return null;
                    return (
                      <div data-testid="dispatch-panel" className="rounded-lg border border-[#BFE6CC] bg-[#F1FBF4] p-2.5 space-y-2">
                        <div className="flex items-center justify-between text-[10.5px]">
                          <span className="text-[#6B6B73]">Siap dikirim: <strong className="text-[#1C7A3E] tabular-nums">{formatQty(maxShip)} {selectedTask.unit}</strong></span>
                          {shipped > 0 && <span className="text-[#B23B14]">Sudah dikirim: {formatQty(shipped)}</span>}
                        </div>
                        <div className="flex gap-2">
                          <input type="number" min="0" max={maxShip} step="any"
                            data-testid="dispatch-qty-input"
                            value={shipQty} onChange={(e) => setShipQty(e.target.value)}
                            placeholder={`Maks ${maxShip}`}
                            className="w-24 border border-[#BFE6CC] rounded-lg px-2 py-1.5 text-[12px] tabular-nums" />
                          <button onClick={() => handleDispatch(true)} disabled={submitting}
                            data-testid={`dispatch-partial-${selectedTask.id}`}
                            className="bg-[#FF9500] hover:bg-[#CC7700] text-white rounded-lg px-3 py-1.5 text-[11.5px] font-semibold flex items-center gap-1.5 disabled:opacity-50">
                            <Send size={12} /> Kirim Sebagian
                          </button>
                          <button onClick={() => handleDispatch(false)} disabled={submitting}
                            data-testid={`dispatch-all-${selectedTask.id}`}
                            className="flex-1 bg-[#34C759] hover:bg-[#28A745] text-white rounded-lg px-3 py-1.5 text-[11.5px] font-semibold flex items-center justify-center gap-1.5 disabled:opacity-50">
                            <Send size={12} /> Kirim Semua ({formatQty(maxShip)})
                          </button>
                        </div>
                      </div>
                    );
                  })()}
                </>
              )}

              {['dispatched', 'partially_shipped'].includes(selectedTask.status) && (
                <div className={`rounded-lg p-3 border ${selectedTask.status === 'dispatched' ? 'bg-green-50 border-green-200' : 'bg-[#FFF3EA] border-[#FFD2B5]'}`}>
                  <div className="flex items-center justify-between">
                    <div>
                      <p className={`text-[12px] font-semibold ${selectedTask.status === 'dispatched' ? 'text-green-700' : 'text-[#B23B14]'}`}>
                        {selectedTask.status === 'dispatched' ? 'Terkirim Penuh!' : 'Terkirim Sebagian'}
                      </p>
                      <p className="text-[11px] text-[#6B6B73]">
                        {formatQty(selectedTask.shipped_qty || 0)} / {formatQty(selectedTask.quantity)} {selectedTask.unit} terkirim
                        {lastShipment?.shipment_no && <span className="ml-1 font-semibold text-[#0058CC]">· {lastShipment.shipment_no}</span>}
                      </p>
                    </div>
                    <button onClick={() => handleViewSuratJalan(selectedTask.order_id, selectedTask.warehouse_id)}
                      data-testid={`view-surat-jalan-${selectedTask.id}`}
                      className="flex items-center gap-1.5 bg-[#007AFF] text-white rounded-lg px-3 py-1.5 text-[11px] font-semibold">
                      <FileText size={12} /> Surat Jalan
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        ) : (
          <div className="bg-white border border-dashed border-[#E5E5EA] rounded-xl flex items-center justify-center">
            <div className="text-center p-8">
              <Truck size={32} className="mx-auto mb-2 text-gray-300" />
              <p className="text-[13px] font-semibold text-[#6B6B73]">Pilih task dari daftar</p>
              <p className="text-[11px] text-[#8E8E93] mt-1">Klik baris task untuk buka pick form</p>
            </div>
          </div>
        )}
      </div>

      {/* Escalate Modal */}
      {showEscalateModal && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/40 p-4"
          onClick={() => setShowEscalateModal(false)}>
          <div className="bg-white rounded-xl p-5 w-full max-w-sm" onClick={e => e.stopPropagation()}>
            <h3 className="text-[13px] font-bold mb-3">Escalate ke Manager</h3>
            <textarea value={escalationReason} onChange={e => setEscalationReason(e.target.value)}
              className="w-full border border-[#E5E5EA] rounded-lg px-3 py-2 text-sm mb-3" rows="3"
              placeholder="Alasan escalation (contoh: Stock fisik hanya 40m, sistem 50m)" />
            <div className="flex gap-2">
              <button onClick={handleEscalate} disabled={submitting}
                className="flex-1 bg-red-500 hover:bg-red-600 text-white rounded-lg px-4 py-2 text-[12px] font-semibold disabled:opacity-50">
                Escalate
              </button>
              <button onClick={() => setShowEscalateModal(false)}
                className="flex-1 bg-[#F2F2F7] text-[#3C3C43] rounded-lg px-4 py-2 text-[12px] font-semibold">
                Batal
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
