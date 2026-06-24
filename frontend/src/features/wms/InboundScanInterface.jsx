import { useEffect, useState } from "react";
import {
  Scan, Package, CheckCircle, AlertTriangle,
  Camera, CameraOff, X, ChevronRight, TrendingUp,
} from "lucide-react";
import axios, { API } from "../../services/apiClient";
import ErrorNotice from "../../components/ErrorNotice";
import KNSelect from "../../components/KNSelect";
import GRCatchWeightModal from "./inbound/GRCatchWeightModal";
import { formatQty } from "../../utils/formatters";

// P0-4 — grade tekstil aktual (A | A+ | B | C | BS)
const GRADE_OPTIONS = [
  { value: "A", label: "Grade A" },
  { value: "A+", label: "Grade A+" },
  { value: "B", label: "Grade B" },
  { value: "C", label: "Grade C" },
  { value: "BS", label: "BS (Barang Sisa)" },
];

const STATUS_MAP = {
  waiting_goods: { label: "Waiting", cls: "bg-gray-100 text-gray-600" },
  receiving:     { label: "Receiving", cls: "bg-blue-100 text-blue-700" },
  qc_check:      { label: "QC", cls: "bg-purple-100 text-purple-700" },
  put_away:      { label: "Put Away", cls: "bg-indigo-100 text-indigo-700" },
  completed:     { label: "Done", cls: "bg-green-100 text-green-700" },
  escalated:     { label: "Escalated", cls: "bg-red-100 text-red-700" },
};

function Badge({ status }) {
  const s = STATUS_MAP[status] || { label: status, cls: "bg-gray-100 text-gray-600" };
  return <span className={`inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-semibold ${s.cls}`}>{s.label}</span>;
}

function MiniBar({ pct, status }) {
  const color = status === 'completed' ? 'bg-[#34C759]' : status === 'escalated' ? 'bg-red-400' : 'bg-[#007AFF]';
  return (
    <div className="h-1 w-full rounded-full bg-gray-200 overflow-hidden">
      <div className={`h-full rounded-full transition-all ${color}`} style={{ width: `${Math.min(pct, 100)}%` }} />
    </div>
  );
}

export default function InboundScanInterface({ user }) {
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [selectedTask, setSelectedTask] = useState(null);
  const [filterStatus, setFilterStatus] = useState("all");

  const [cameraActive, setCameraActive] = useState(false);
  const [scanValue, setScanValue] = useState("");
  const [scanData, setScanData] = useState({ actual_qty: 0, batch: "", lot: "", dye_lot: "", grade: "A", roll_id: "", bin_id: "" });

  const [showEscalateModal, setShowEscalateModal] = useState(false);
  const [escalationReason, setEscalationReason] = useState("");
  const [submitting, setSubmitting] = useState(false);

  // Fase 8 (Catch-weight) — entri roll saat Goods Receipt (panjang m + berat kg per roll).
  const [products, setProducts] = useState({});
  const [showGRModal, setShowGRModal] = useState(false);
  const [grRolls, setGrRolls] = useState([]);
  const round2 = (n) => Math.round((Number(n) + Number.EPSILON) * 100) / 100;
  const kgPerMeter = (p) => {
    if (!p) return 0;
    const ex = Number(p?.kg_per_meter) || 0;
    if (ex > 0) return ex;
    return (Number(p?.gramasi) || 0) * (Number(p?.lebar) || 0) / 1000;
  };

  useEffect(() => {
    axios.get(`${API}/products`).then((r) => {
      const m = {};
      (r.data || []).forEach((p) => { m[p.id] = p; });
      setProducts(m);
    }).catch(() => { /* opsional */ });
  }, []);

  useEffect(() => { fetchTasks(); }, [filterStatus]);

  const fetchTasks = async () => {
    setLoading(true);
    try {
      const params = filterStatus !== "all" ? `?status=${filterStatus}` : "";
      const res = await axios.get(`${API}/inbound/tasks${params}`);
      setTasks(res.data);
      setError("");
    } catch (e) { setError(e.response?.data?.detail || "Gagal memuat inbound task."); }
    finally { setLoading(false); }
  };

  const startCamera = async () => {
    try {
      const { BrowserMultiFormatReader } = await import("@zxing/browser");
      const reader = new BrowserMultiFormatReader();
      const el = document.getElementById("inbound-video-compact");
      if (!el) return;
      await reader.decodeFromVideoDevice(null, el, (result) => {
        if (result) { setScanValue(result.getText()); stopCamera(); }
      });
      setCameraActive(true);
    } catch { alert("Gagal buka kamera."); }
  };

  const stopCamera = () => {
    const el = document.getElementById("inbound-video-compact");
    if (el?.srcObject) { el.srcObject.getTracks().forEach(t => t.stop()); el.srcObject = null; }
    setCameraActive(false);
  };

  const handleScanReceive = async () => {
    if (!selectedTask || scanData.actual_qty <= 0) return alert("Masukkan qty yang valid");
    setSubmitting(true);
    try {
      const res = await axios.post(`${API}/inbound/tasks/${selectedTask.id}/scan-receive`, {
        product_id: selectedTask.product_id, ...scanData
      });
      setTasks(prev => prev.map(t => t.id === selectedTask.id ? res.data : t));
      setSelectedTask(res.data);
      setScanData({ actual_qty: 0, batch: "", lot: "", dye_lot: "", grade: "A", roll_id: "", bin_id: "" });
      setScanValue("");
    } catch (e) { alert(e.response?.data?.detail || "Gagal scan"); }
    finally { setSubmitting(false); }
  };

  // Fase 8 — buka modal entri roll catch-weight; prefilled 1 roll dari qty diterima.
  const openComplete = () => {
    if (!selectedTask) return;
    if ((selectedTask.received_qty || 0) < selectedTask.expected_qty)
      return alert("Qty belum sesuai! Silakan escalate.");
    const isKg = (selectedTask.unit || "").toLowerCase() === "kg";
    const kgm = kgPerMeter(products[selectedTask.product_id]);
    const recv = Number(selectedTask.received_qty) || 0;
    setGrRolls([{
      length: isKg ? (kgm > 0 ? round2(recv / kgm) : 0) : recv,
      weight: isKg ? recv : (kgm > 0 ? round2(recv * kgm) : 0),
      dye_lot: selectedTask.dye_lot || "",
      grade: "A",
    }]);
    setShowGRModal(true);
  };

  const submitComplete = async () => {
    if (!selectedTask) return;
    setSubmitting(true);
    try {
      const rolls = grRolls.map((r) => ({
        length: Number(r.length) || 0,
        weight: Number(r.weight) || 0,
        dye_lot: r.dye_lot || "",
        grade: r.grade || "A",
      }));
      await axios.post(`${API}/inbound/tasks/${selectedTask.id}/complete`, { rolls });
      setShowGRModal(false);
      setGrRolls([]);
      fetchTasks();
      setSelectedTask(null);
    } catch (e) { alert(e.response?.data?.detail || "Gagal complete"); }
    finally { setSubmitting(false); }
  };

  const handleEscalate = async () => {
    if (!escalationReason.trim()) return alert("Masukkan alasan escalation");
    setSubmitting(true);
    try {
      await axios.post(`${API}/inbound/tasks/${selectedTask.id}/escalate`, null, {
        params: { reason: escalationReason }
      });
      setShowEscalateModal(false);
      setEscalationReason("");
      fetchTasks();
      setSelectedTask(null);
    } catch (e) { alert(e.response?.data?.detail || "Gagal escalate"); }
    finally { setSubmitting(false); }
  };

  const FILTERS = ["all", "waiting_goods", "receiving", "qc_check", "escalated"];
  const FILTER_LABELS = { all: "Semua", waiting_goods: "Waiting", receiving: "Receiving", qc_check: "QC", escalated: "Escalated" };

  const activeTasks = tasks.filter(t => !['completed'].includes(t.status));
  const doneTasks = tasks.filter(t => t.status === 'completed');

  return (
    <div data-testid="inbound-scan-panel" className="flex flex-col gap-3">
      <ErrorNotice message={error} onRetry={fetchTasks} onDismiss={() => setError("")} testId="inbound-scan-error" />
      {/* Filter strip */}
      <div className="flex items-center gap-1.5 overflow-x-auto">
        {FILTERS.map(s => (
          <button key={s}
            data-testid={`filter-status-${s}`}
            onClick={() => setFilterStatus(s)}
            className={`rounded-full px-3 py-1 text-xs font-medium whitespace-nowrap transition-all ${filterStatus === s ? "bg-[#34C759] text-white" : "bg-white border border-[#E5E5EA] text-[#6B6B73] hover:border-[#34C759]"}`}>
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
            <span className="text-[11px] font-bold uppercase tracking-wide text-[#6B6B73]">Inbound Tasks</span>
            <button onClick={fetchTasks} className="text-[#007AFF] text-[11px] font-medium">Refresh</button>
          </div>
          {loading ? (
            <div className="py-8 text-center text-[12px] text-[#6B6B73]">Loading...</div>
          ) : tasks.length === 0 ? (
            <div className="py-8 text-center text-[12px] text-[#6B6B73]">
              <Package size={28} className="mx-auto mb-2 text-gray-300" />
              <p>Tidak ada inbound task</p>
            </div>
          ) : (
            <div className="divide-y divide-[#EFF0F2] overflow-y-auto max-h-[520px]">
              {tasks.map(task => {
                const pct = task.expected_qty ? Math.min((task.received_qty || 0) / task.expected_qty * 100, 100) : 0;
                const isSelected = selectedTask?.id === task.id;
                return (
                  <button key={task.id}
                    data-testid={`inbound-task-${task.id}`}
                    onClick={() => { setSelectedTask(task); stopCamera(); }}
                    className={`w-full text-left px-3 py-2.5 hover:bg-[#F5F7FF] transition-colors ${isSelected ? 'bg-[#EFF4FF] border-l-2 border-[#007AFF]' : ''}`}>
                    <div className="flex items-center justify-between gap-2 mb-1">
                      <span className="text-[12px] font-bold text-[#007AFF]">{task.po_number}</span>
                      <div className="flex items-center gap-1">
                        <Badge status={task.status} />
                        <ChevronRight size={12} className="text-gray-400" />
                      </div>
                    </div>
                    <p className="text-[11px] text-[#3C3C43] truncate">{task.sku}</p>
                    <p className="text-[10px] text-[#8E8E93] truncate">{task.product_name}</p>
                    <div className="mt-1.5">
                      <MiniBar pct={pct} status={task.status} />
                      <div className="flex justify-between mt-0.5">
                        <span className="text-[10px] text-[#8E8E93]">{formatQty(task.received_qty || 0)}/{formatQty(task.expected_qty)} {task.unit}</span>
                        <span className="text-[10px] font-semibold text-[#3C3C43]">{pct.toFixed(0)}%</span>
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {/* RIGHT: Scan Panel */}
        {selectedTask ? (
          <div className="bg-white border border-[#EFF0F2] rounded-xl overflow-hidden">
            <div className="px-3 py-2 border-b border-[#EFF0F2] bg-[#FAFBFC] flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="text-[11px] font-bold uppercase tracking-wide text-[#6B6B73]">Scan Receive</span>
                <Badge status={selectedTask.status} />
              </div>
              <button onClick={() => { stopCamera(); setSelectedTask(null); }} className="text-[#6B6B73] hover:text-black">
                <X size={14} />
              </button>
            </div>

            <div className="p-3 space-y-3">
              {/* Info bar */}
              <div className="grid grid-cols-3 gap-2">
                <div className="bg-[#F5F7FF] rounded-lg p-2">
                  <p className="text-[10px] text-[#6B6B73] uppercase font-semibold">PO</p>
                  <p className="text-[12px] font-bold text-[#007AFF]">{selectedTask.po_number}</p>
                </div>
                <div className="bg-[#F5F7FF] rounded-lg p-2">
                  <p className="text-[10px] text-[#6B6B73] uppercase font-semibold">SKU</p>
                  <p className="text-[11px] font-semibold truncate">{selectedTask.sku}</p>
                </div>
                <div className="bg-[#F5F7FF] rounded-lg p-2">
                  <p className="text-[10px] text-[#6B6B73] uppercase font-semibold">Progress</p>
                  <p className="text-[12px] font-bold">{formatQty(selectedTask.received_qty || 0)}<span className="text-[10px] text-[#6B6B73]">/{formatQty(selectedTask.expected_qty)}</span></p>
                </div>
              </div>

              <div className="bg-[#FAFBFC] rounded-lg p-2">
                <p className="text-[11px] text-[#3C3C43] font-medium">{selectedTask.product_name}</p>
                <p className="text-[10.5px] text-[#6B6B73]">Supplier: {selectedTask.supplier_name || '-'} · Gudang: {selectedTask.warehouse_name}</p>
              </div>

              {/* Escalation info */}
              {selectedTask.status === 'escalated' && selectedTask.escalation && (
                <div className="bg-red-50 border border-red-200 rounded-lg p-2 text-[11px]">
                  <p className="font-semibold text-red-700">Escalated: {selectedTask.escalation.escalated_by}</p>
                  <p className="text-red-600">{selectedTask.escalation.reason}</p>
                  {selectedTask.escalation.status === 'resolved' && (
                    <p className="text-green-700 mt-1 inline-flex items-center gap-1"><CheckCircle size={12} /> Resolved by {selectedTask.escalation.resolved_by}: {selectedTask.escalation.resolution_notes}</p>
                  )}
                </div>
              )}

              {/* Camera */}
              {!['completed','escalated'].includes(selectedTask.status) && (
                <>
                  <div className="flex items-center gap-2">
                    <button onClick={cameraActive ? stopCamera : startCamera}
                      className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[11px] font-medium ${cameraActive ? 'bg-red-500 text-white' : 'bg-[#F5F7FF] text-[#007AFF] border border-[#007AFF]/30'}`}>
                      {cameraActive ? <><CameraOff size={12} /> Stop Camera</> : <><Camera size={12} /> Camera</>}
                    </button>
                    {scanValue && <span className="text-[11px] text-green-700 font-medium inline-flex items-center gap-1"><CheckCircle size={11} /> {scanValue}</span>}
                  </div>
                  <video id="inbound-video-compact"
                    className={`w-full rounded-lg border border-[#007AFF]/30 ${cameraActive ? 'block' : 'hidden'}`}
                    style={{ maxHeight: '160px' }} />

                  {/* Scan Form */}
                  <div className="grid grid-cols-3 gap-2">
                    <div className="col-span-1">
                      <label className="block text-[10px] font-semibold text-[#6B6B73] mb-1">Actual Qty *</label>
                      <input type="number" value={scanData.actual_qty}
                        onChange={e => setScanData({ ...scanData, actual_qty: parseFloat(e.target.value) || 0 })}
                        className="w-full border border-[#E5E5EA] rounded-lg px-2 py-1.5 text-sm" placeholder="0" />
                    </div>
                    <div>
                      <label className="block text-[10px] font-semibold text-[#6B6B73] mb-1">Batch</label>
                      <input type="text" value={scanData.batch}
                        onChange={e => setScanData({ ...scanData, batch: e.target.value })}
                        className="w-full border border-[#E5E5EA] rounded-lg px-2 py-1.5 text-sm" placeholder="BTK-001" />
                    </div>
                    <div>
                      <label className="block text-[10px] font-semibold text-[#6B6B73] mb-1">Lot</label>
                      <input type="text" value={scanData.lot}
                        onChange={e => setScanData({ ...scanData, lot: e.target.value })}
                        className="w-full border border-[#E5E5EA] rounded-lg px-2 py-1.5 text-sm" placeholder="LOT-001" />
                    </div>
                    <div>
                      <label className="block text-[10px] font-semibold text-[#6B6B73] mb-1">Dye Lot</label>
                      <input type="text" value={scanData.dye_lot}
                        data-testid="scan-dye-lot-input"
                        onChange={e => setScanData({ ...scanData, dye_lot: e.target.value })}
                        className="w-full border border-[#E5E5EA] rounded-lg px-2 py-1.5 text-sm" placeholder="DL-RED-01" />
                    </div>
                    <div>
                      <label className="block text-[10px] font-semibold text-[#6B6B73] mb-1">Grade</label>
                      <KNSelect
                        data-testid="scan-grade-select"
                        className="w-full border border-[#E5E5EA] rounded-lg px-2 py-1.5 text-sm bg-white text-left"
                        value={scanData.grade}
                        onValueChange={(v) => setScanData({ ...scanData, grade: v })}
                        options={GRADE_OPTIONS}
                      />
                    </div>
                    <div>
                      <label className="block text-[10px] font-semibold text-[#6B6B73] mb-1">Roll ID</label>
                      <input type="text" value={scanData.roll_id}
                        onChange={e => setScanData({ ...scanData, roll_id: e.target.value })}
                        className="w-full border border-[#E5E5EA] rounded-lg px-2 py-1.5 text-sm" placeholder="ROLL-001" />
                    </div>
                    <div className="col-span-2">
                      <label className="block text-[10px] font-semibold text-[#6B6B73] mb-1">Bin Location *</label>
                      <input type="text" value={scanData.bin_id}
                        onChange={e => setScanData({ ...scanData, bin_id: e.target.value })}
                        className="w-full border border-[#E5E5EA] rounded-lg px-2 py-1.5 text-sm" placeholder="A1-01" />
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="flex gap-2">
                    <button onClick={handleScanReceive} disabled={submitting}
                      data-testid={`scan-task-${selectedTask.id}`}
                      className="flex-1 bg-[#34C759] hover:bg-[#28A745] text-white rounded-lg px-3 py-2 text-[12px] font-semibold flex items-center justify-center gap-1.5 disabled:opacity-50">
                      <CheckCircle size={13} /> Submit Scan
                    </button>
                    {(selectedTask.received_qty || 0) >= selectedTask.expected_qty && (
                      <button onClick={openComplete} disabled={submitting}
                        data-testid={`complete-task-${selectedTask.id}`}
                        className="flex-1 bg-[#007AFF] hover:bg-[#0056B3] text-white rounded-lg px-3 py-2 text-[12px] font-semibold flex items-center justify-center gap-1.5 disabled:opacity-50">
                        <TrendingUp size={13} /> Complete
                      </button>
                    )}
                    <button onClick={() => setShowEscalateModal(true)}
                      className="bg-orange-50 border border-orange-300 text-orange-600 hover:bg-orange-100 rounded-lg px-3 py-2 text-[12px] font-semibold flex items-center gap-1.5">
                      <AlertTriangle size={13} /> Escalate
                    </button>
                  </div>
                </>
              )}

              {selectedTask.status === 'completed' && (
                <div className="bg-green-50 border border-green-200 rounded-lg p-3 text-center">
                  <CheckCircle className="mx-auto text-green-500 mb-1" size={24} />
                  <p className="text-[12px] font-semibold text-green-700">Receiving selesai!</p>
                  <p className="text-[11px] text-green-600">{formatQty(selectedTask.received_qty)} {selectedTask.unit} diterima</p>
                  {selectedTask.scan_log?.length > 0 && (
                    <div className="mt-2 text-left">
                      <p className="text-[10px] font-bold text-[#6B6B73] uppercase mb-1">Scan History ({selectedTask.scan_log.length})</p>
                      {selectedTask.scan_log.map((log, i) => (
                        <div key={i} className="flex justify-between text-[10.5px] py-0.5 border-t border-green-200">
                          <span>{log.roll_id || log.batch}</span>
                          <span className="font-semibold">{formatQty(log.actual_qty)} {selectedTask.unit}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        ) : (
          <div className="bg-white border border-dashed border-[#E5E5EA] rounded-xl flex items-center justify-center">
            <div className="text-center p-8">
              <Scan size={32} className="mx-auto mb-2 text-gray-300" />
              <p className="text-[13px] font-semibold text-[#6B6B73]">Pilih task dari daftar</p>
              <p className="text-[11px] text-[#8E8E93] mt-1">Klik baris task untuk buka scan form</p>
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
              placeholder="Alasan escalation (contoh: Qty kurang 10m dari PO)" />
            <div className="flex gap-2">
              <button onClick={handleEscalate} disabled={submitting}
                className="flex-1 bg-orange-500 hover:bg-orange-600 text-white rounded-lg px-4 py-2 text-[12px] font-semibold disabled:opacity-50">
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

      {/* Fase 8 — Goods Receipt: entri roll catch-weight (panjang m + berat kg) */}
      {showGRModal && selectedTask && (
        <GRCatchWeightModal
          task={selectedTask}
          product={products[selectedTask.product_id]}
          rolls={grRolls}
          setRolls={setGrRolls}
          onSubmit={submitComplete}
          onClose={() => setShowGRModal(false)}
          submitting={submitting}
        />
      )}
    </div>
  );
}
