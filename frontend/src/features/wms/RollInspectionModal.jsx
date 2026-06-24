import { useEffect, useMemo, useState } from "react";
import axios, { API } from "../../services/apiClient";
import { X, Ruler, CheckCircle2, RefreshCw } from "lucide-react";
import { formatQty } from "../../utils/formatters";

/**
 * RollInspectionModal (Fase 6.2 — P1) — Inspeksi 4-Point per roll.
 * Catat poin defect (severity 1..4) + GSM/lebar aktual → set Grade roll (A/B/C).
 * Skor = Σ(point_value × count); grade dari ambang configurable (qc.grade_thresholds).
 */
const POINT_LEVELS = [
  { pv: 1, label: "1 poin (kecil <3\")" },
  { pv: 2, label: "2 poin (3–6\")" },
  { pv: 3, label: "3 poin (6–9\")" },
  { pv: 4, label: "4 poin (>9\")" },
];

export default function RollInspectionModal({ taskId, taskLabel, entityId, onClose, onDone }) {
  const [rolls, setRolls] = useState([]);
  const [thresholds, setThresholds] = useState({ a_max: 20, b_max: 40 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [openRoll, setOpenRoll] = useState(null);
  const [form, setForm] = useState({});       // pv -> count
  const [gsm, setGsm] = useState("");
  const [width, setWidth] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => { load(); }, [taskId]); // eslint-disable-line

  async function load() {
    setLoading(true);
    try {
      const params = (entityId && entityId !== "all") ? { entity_id: entityId } : {};
      const [r, t] = await Promise.all([
        axios.get(`${API}/inbound/qc/tasks/${taskId}/rolls`),
        axios.get(`${API}/qc/grade-thresholds`, { params }).catch(() => ({ data: { a_max: 20, b_max: 40 } })),
      ]);
      setRolls(Array.isArray(r.data) ? r.data : []);
      setThresholds(t.data || { a_max: 20, b_max: 40 });
      setError("");
    } catch (e) {
      setError(e.response?.data?.detail || "Gagal memuat roll.");
    } finally { setLoading(false); }
  }

  function openForm(roll) {
    setOpenRoll(roll.id);
    const insp = roll.inspection || {};
    const f = {};
    (insp.defects || []).forEach((d) => { f[d.point_value] = d.count; });
    setForm(f);
    setGsm(insp.gsm_actual ?? "");
    setWidth(insp.width_actual ?? "");
    setNote(insp.note || "");
  }

  const points = useMemo(
    () => POINT_LEVELS.reduce((s, lv) => s + lv.pv * (Number(form[lv.pv]) || 0), 0), [form]);
  const predictedGrade = points <= thresholds.a_max ? "A" : points <= thresholds.b_max ? "B" : "C";

  async function save(rollId) {
    setBusy(true);
    try {
      const defects = POINT_LEVELS
        .filter((lv) => Number(form[lv.pv]) > 0)
        .map((lv) => ({ point_value: lv.pv, count: Number(form[lv.pv]) }));
      await axios.post(`${API}/inbound/rolls/${rollId}/inspect`, {
        defects, gsm_actual: gsm === "" ? null : Number(gsm),
        width_actual: width === "" ? null : Number(width), note,
      });
      setOpenRoll(null);
      await load();
      onDone?.();
    } catch (e) {
      setError(e.response?.data?.detail || "Inspeksi gagal.");
    } finally { setBusy(false); }
  }

  const gradeTone = (g) => g === "A" ? "pill-success" : g === "B" ? "pill-warning" : g === "C" ? "pill-danger" : "pill-muted";

  return (
    <div className="modal-overlay" data-testid="roll-inspection-modal" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="modal-card" style={{ maxWidth: 720, width: "95vw", maxHeight: "92vh", overflowY: "auto" }}>
        <div className="flex items-center justify-between px-4 py-3 border-b border-[#EFF0F2] sticky top-0 bg-white z-10">
          <div className="flex items-center gap-2">
            <Ruler size={16} className="text-[#0058CC]" />
            <div>
              <h2 className="text-[14px] font-bold">Inspeksi 4-Point per Roll</h2>
              <p className="text-[10.5px] text-[#6B6B73]">{taskLabel} · Grade: ≤{thresholds.a_max}=A, ≤{thresholds.b_max}=B, &gt;{thresholds.b_max}=C</p>
            </div>
          </div>
          <button data-testid="roll-inspect-close" onClick={onClose} className="icon-button"><X size={16} /></button>
        </div>

        <div className="p-4 space-y-2">
          {error && <div className="notice-bar danger"><span>{error}</span><button onClick={() => setError("")}>×</button></div>}
          {loading ? (
            <div className="py-10 text-center text-[12px] text-[#6B6B73]"><RefreshCw size={18} className="animate-spin mx-auto mb-2" /> Memuat roll...</div>
          ) : rolls.length === 0 ? (
            <div className="py-10 text-center text-[12px] text-[#6B6B73]" data-testid="roll-inspect-empty">Tidak ada roll untuk task ini.</div>
          ) : rolls.map((roll) => (
            <div key={roll.id} data-testid={`roll-card-${roll.id}`} className="rounded-md border border-[#EFF0F2]">
              <div className="flex items-center justify-between px-3 py-2">
                <div className="min-w-0">
                  <p className="text-[12.5px] font-semibold">{roll.roll_no} · {roll.sku}
                    {roll.grade && <span className={`status-pill ${gradeTone(roll.grade)} ml-2`} data-testid={`roll-grade-${roll.id}`}>Grade {roll.grade}</span>}
                    {roll.inspected && <CheckCircle2 size={13} className="inline ml-1 text-emerald-500" />}
                  </p>
                  <p className="text-[10.5px] text-[#9A9BA3]">
                    {formatQty(roll.length_initial)} {roll.unit} · Std GSM {roll.gsm_standard ?? "—"} · Std Lebar {roll.width_standard ?? "—"}
                    {roll.inspection?.points != null && <> · {roll.inspection.points} poin</>}
                  </p>
                </div>
                <button data-testid={`roll-inspect-btn-${roll.id}`} onClick={() => (openRoll === roll.id ? setOpenRoll(null) : openForm(roll))}
                        className="secondary-button text-[11px]">{roll.inspected ? "Ubah" : "Inspeksi"}</button>
              </div>

              {openRoll === roll.id && (
                <div className="px-3 pb-3 border-t border-[#EFF0F2] pt-2.5" data-testid={`roll-inspect-form-${roll.id}`}>
                  <p className="text-[11px] font-bold uppercase text-[#6B6B73] mb-1.5">Poin Defect (4-Point)</p>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                    {POINT_LEVELS.map((lv) => (
                      <div key={lv.pv}>
                        <label className="block text-[10px] text-[#6B6B73] mb-0.5">{lv.label}</label>
                        <input type="number" min="0" data-testid={`roll-defect-${lv.pv}`} value={form[lv.pv] ?? ""}
                          onChange={(e) => setForm((f) => ({ ...f, [lv.pv]: e.target.value }))}
                          className="field text-center" placeholder="0" />
                      </div>
                    ))}
                  </div>
                  <div className="grid grid-cols-3 gap-2 mt-2">
                    <div><label className="block text-[10px] text-[#6B6B73] mb-0.5">GSM aktual</label>
                      <input type="number" data-testid={`roll-gsm-${roll.id}`} value={gsm} onChange={(e) => setGsm(e.target.value)} className="field" placeholder={roll.gsm_standard ?? "gsm"} /></div>
                    <div><label className="block text-[10px] text-[#6B6B73] mb-0.5">Lebar aktual</label>
                      <input type="number" data-testid={`roll-width-${roll.id}`} value={width} onChange={(e) => setWidth(e.target.value)} className="field" placeholder={roll.width_standard ?? "cm"} /></div>
                    <div><label className="block text-[10px] text-[#6B6B73] mb-0.5">Catatan</label>
                      <input value={note} onChange={(e) => setNote(e.target.value)} className="field" placeholder="opsional" /></div>
                  </div>
                  <div className="flex items-center justify-between mt-2.5 rounded-md bg-[#FAFBFC] border border-[#EFF0F2] px-3 py-2">
                    <span className="text-[12px]">Total Poin: <b className="tabular-nums" data-testid={`roll-points-${roll.id}`}>{points}</b></span>
                    <span className="text-[12px]">Grade: <span className={`status-pill ${gradeTone(predictedGrade)}`} data-testid={`roll-predicted-${roll.id}`}>{predictedGrade}</span></span>
                    <button data-testid={`roll-inspect-save-${roll.id}`} disabled={busy} onClick={() => save(roll.id)} className="primary-button text-[11px]">{busy ? "..." : "Simpan & Set Grade"}</button>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
