import { useEffect, useState } from "react";
import axios, { API } from "../../services/apiClient";
import { RotateCcw, Plus, X, CheckCircle, XCircle, Send, FileText } from "lucide-react";
import { formatCurrency } from "../../utils/formatters";
import KNSelect from "../../components/KNSelect";
import ErrorNotice from "../../components/ErrorNotice";
import ConfirmModal from "../../components/ConfirmModal";
import ReturnDetailPanel from "./ReturnDetailPanel";

/**
 * PurchaseReturns (Depth #1B) — Retur Beli / Nota Debit.
 * Kembalikan barang ke supplier → kurangi roll + terbitkan nota debit.
 */
const TABS = [
  { key: "all", label: "Semua" },
  { key: "draft", label: "Draft" },
  { key: "pending_approval", label: "Menunggu" },
  { key: "approved", label: "Disetujui" },
  { key: "rejected", label: "Ditolak" },
];
const REASONS = [
  { value: "cacat", label: "Barang Cacat" },
  { value: "salah_kirim", label: "Salah Kirim" },
  { value: "kelebihan", label: "Kelebihan Kirim" },
  { value: "lain", label: "Lain-lain" },
];

function StatusPill({ status }) {
  const map = {
    draft: ["pill-muted", "Draft"], pending_approval: ["pill-warning", "Menunggu"],
    approved: ["pill-success", "Disetujui"], rejected: ["pill-danger", "Ditolak"],
  };
  const [cls, label] = map[status] || ["pill-muted", status];
  return <span className={`status-pill ${cls}`}>{label}</span>;
}

export default function PurchaseReturns({ currentUser, selectedEntity }) {
  const [returns, setReturns] = useState([]);
  const [suppliers, setSuppliers] = useState([]);
  const [warehouses, setWarehouses] = useState([]);
  const [products, setProducts] = useState([]);
  const [pos, setPos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [tab, setTab] = useState("all");
  const [showForm, setShowForm] = useState(false);
  const [detail, setDetail] = useState(null);
  const [rejectTarget, setRejectTarget] = useState(null);

  const blankItem = { product_id: "", quantity: "", price: "", reason: "cacat", condition: "damaged" };
  const [form, setForm] = useState({ supplier_id: "", po_id: "", warehouse_id: "", reason: "", notes: "", items: [blankItem], submit_now: true });

  const canApprove = ["admin", "manager"].includes(currentUser?.role);

  useEffect(() => { loadAll(); }, [selectedEntity]); // eslint-disable-line

  async function loadAll() {
    setLoading(true);
    try {
      const params = (selectedEntity && selectedEntity !== "all") ? { entity_id: selectedEntity } : {};
      const [rRes, sRes, wRes, pRes, poRes] = await Promise.all([
        axios.get(`${API}/purchase-returns`, { params }),
        axios.get(`${API}/suppliers`).catch(() => ({ data: [] })),
        axios.get(`${API}/warehouses`).catch(() => ({ data: [] })),
        axios.get(`${API}/products`).catch(() => ({ data: [] })),
        axios.get(`${API}/purchase-orders`).catch(() => ({ data: [] })),
      ]);
      setReturns(rRes.data?.items || []);
      setSuppliers(Array.isArray(sRes.data) ? sRes.data : []);
      setWarehouses(Array.isArray(wRes.data) ? wRes.data : []);
      setProducts(Array.isArray(pRes.data) ? pRes.data : []);
      setPos(Array.isArray(poRes.data) ? poRes.data : []);
      setError("");
    } catch (e) {
      setError(e.response?.data?.detail || "Gagal memuat data retur.");
    } finally {
      setLoading(false);
    }
  }

  function updateItem(i, patch) {
    setForm((f) => ({ ...f, items: f.items.map((it, idx) => idx === i ? { ...it, ...patch } : it) }));
  }
  function onSelectPO(poId) {
    const po = pos.find((p) => p.id === poId);
    if (po) {
      setForm((f) => ({
        ...f, po_id: poId, warehouse_id: po.warehouse_id || f.warehouse_id,
        supplier_id: po.supplier_id || f.supplier_id,
        items: (po.items || []).map((it) => ({ product_id: it.product_id, quantity: "", price: String(it.price || ""), reason: "cacat", condition: "damaged" })) || [blankItem],
      }));
    } else {
      setForm((f) => ({ ...f, po_id: "" }));
    }
  }

  async function handleSubmit() {
    const items = form.items.filter((it) => it.product_id && Number(it.quantity) > 0)
      .map((it) => {
        const prod = products.find((p) => p.id === it.product_id);
        const unit = prod?.base_unit || "meter";
        return { product_id: it.product_id, quantity: Number(it.quantity), unit, price: Number(it.price || 0), reason: it.reason, condition: it.condition };
      });
    if (!form.supplier_id) { setError("Supplier wajib dipilih."); return; }
    if (items.length === 0) { setError("Minimal satu item dengan qty > 0."); return; }
    try {
      const res = await axios.post(`${API}/purchase-returns`, { ...form, items });
      setNotice(`Retur ${res.data.number} dibuat (${res.data.status === "pending_approval" ? "menunggu approval" : "draft"}).`);
      setShowForm(false);
      setForm({ supplier_id: "", po_id: "", warehouse_id: "", reason: "", notes: "", items: [blankItem], submit_now: true });
      await loadAll();
    } catch (e) {
      setError(e.response?.data?.detail || "Gagal membuat retur.");
    }
  }

  async function act(id, action, body) {
    try {
      const urls = {
        submit: `${API}/purchase-returns/${id}/submit`,
        approve: `${API}/purchase-returns/${id}/approve`,
        reject: `${API}/purchase-returns/${id}/reject`,
      };
      const res = await axios.post(urls[action], body || {});
      const labels = { submit: "disubmit", approve: "disetujui", reject: "ditolak" };
      setNotice(`Retur ${res.data.number} ${labels[action]}.${res.data.debit_note_number ? ` Nota debit: ${res.data.debit_note_number}` : ""}`);
      setDetail(null);
      await loadAll();
    } catch (e) {
      setError(e.response?.data?.detail || `Gagal ${action}.`);
    }
  }

  const supName = (id) => suppliers.find((s) => s.id === id)?.name || "—";
  const filtered = returns.filter((r) => tab === "all" || r.status === tab);
  const counts = TABS.reduce((acc, t) => ({ ...acc, [t.key]: t.key === "all" ? returns.length : returns.filter((r) => r.status === t.key).length }), {});
  const supplierPOs = pos.filter((p) => !form.supplier_id || p.supplier_id === form.supplier_id);

  return (
    <div data-testid="purchase-returns-view">
      {notice && <div className="notice-bar success" data-testid="pret-notice"><span>{notice}</span><button onClick={() => setNotice("")}><X size={13} /></button></div>}
      <ErrorNotice message={error} onRetry={loadAll} onDismiss={() => setError("")} testId="pret-error" />

      <div className="section-card mb-3">
        <div className="section-head">
          <div className="flex items-center gap-2 min-w-0">
            <RotateCcw size={16} className="text-[#0058CC]" />
            <h2 data-testid="purchase-returns-title">Retur Beli (Nota Debit)</h2>
          </div>
          <button data-testid="create-return-button" onClick={() => setShowForm(!showForm)} className="primary-button">
            <Plus size={13} /> {showForm ? "Tutup Form" : "Buat Retur"}
          </button>
        </div>
        <div className="section-body">
          <div className="tab-bar">
            {TABS.map((t) => (
              <button key={t.key} data-testid={`pret-tab-${t.key}`} className={`tab-button ${tab === t.key ? "active" : ""}`} onClick={() => setTab(t.key)}>
                {t.label}<span className="tab-badge">{counts[t.key]}</span>
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Create form */}
      {showForm && (
        <div data-testid="return-form" className="section-card mb-3">
          <div className="section-head"><h2 className="text-[13px] font-bold">Buat Retur Beli</h2></div>
          <div className="section-body space-y-3">
            <div className="grid grid-cols-3 gap-3">
              <Field label="Supplier" req>
                <KNSelect data-testid="return-supplier-select" value={form.supplier_id} onValueChange={(v) => setForm({ ...form, supplier_id: v, po_id: "" })} className="field" placeholder="Pilih Supplier"
                  options={suppliers.filter((s) => s.status !== "inactive").map((s) => ({ value: s.id, label: `${s.code} · ${s.name}` }))} />
              </Field>
              <Field label="PO Referensi (opsional)">
                <KNSelect data-testid="return-po-select" value={form.po_id} onValueChange={onSelectPO} className="field" placeholder="Tanpa PO"
                  options={[{ value: "", label: "— Tanpa PO —" }, ...supplierPOs.map((p) => ({ value: p.id, label: `${p.po_number} · ${formatCurrency(p.total_amount)}` }))]} />
              </Field>
              <Field label="Gudang" req>
                <KNSelect data-testid="return-warehouse-select" value={form.warehouse_id} onValueChange={(v) => setForm({ ...form, warehouse_id: v })} className="field" placeholder="Pilih Gudang"
                  options={warehouses.map((w) => ({ value: w.id, label: `${w.name} (${w.code})` }))} />
              </Field>
            </div>

            {/* Items */}
            <div className="rounded-md border border-[#EFF0F2] overflow-hidden">
              <div className="grid grid-cols-[1.6fr_80px_110px_1fr_110px_36px] px-2.5 py-1.5 bg-[#FAFBFC] text-[10px] font-bold uppercase text-[#6B6B73] border-b border-[#EFF0F2]">
                <span>Produk</span><span>Qty</span><span>Harga</span><span>Alasan</span><span>Kondisi</span><span></span>
              </div>
              {form.items.map((it, i) => (
                <div key={i} className="grid grid-cols-[1.6fr_80px_110px_1fr_110px_36px] gap-1.5 items-center px-2.5 py-1.5 border-b border-[#EFF0F2] last:border-0">
                  <KNSelect data-testid={`return-item-product-${i}`} value={it.product_id} onValueChange={(v) => updateItem(i, { product_id: v })} className="field !py-1" placeholder="Produk"
                    options={products.map((p) => ({ value: p.id, label: `${p.sku} · ${p.name}` }))} />
                  <input data-testid={`return-item-qty-${i}`} type="number" value={it.quantity} onChange={(e) => updateItem(i, { quantity: e.target.value })} className="field !py-1" placeholder="0" />
                  <input type="number" value={it.price} onChange={(e) => updateItem(i, { price: e.target.value })} className="field !py-1" placeholder="harga" />
                  <KNSelect value={it.reason} onValueChange={(v) => updateItem(i, { reason: v })} className="field !py-1" options={REASONS} />
                  <KNSelect value={it.condition} onValueChange={(v) => updateItem(i, { condition: v })} className="field !py-1"
                    options={[{ value: "damaged", label: "Rusak" }, { value: "ok", label: "Baik" }]} />
                  <button className="icon-button text-red-400" onClick={() => setForm((f) => ({ ...f, items: f.items.filter((_, idx) => idx !== i) }))}><X size={13} /></button>
                </div>
              ))}
              <button data-testid="return-add-item" onClick={() => setForm((f) => ({ ...f, items: [...f.items, blankItem] }))} className="w-full py-1.5 text-[11px] text-[#0058CC] font-semibold hover:bg-[#F5F9FF]">+ Tambah Item</button>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <Field label="Alasan Retur">
                <input data-testid="return-reason-input" value={form.reason} onChange={(e) => setForm({ ...form, reason: e.target.value })} className="field" placeholder="Keterangan retur" />
              </Field>
              <Field label="Catatan">
                <input value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} className="field" placeholder="Catatan tambahan" />
              </Field>
            </div>
            <label className="flex items-center gap-2 text-[11.5px] text-[#3C3C43]">
              <input data-testid="return-submit-now" type="checkbox" checked={form.submit_now} onChange={(e) => setForm({ ...form, submit_now: e.target.checked })} />
              Langsung ajukan approval (jika tidak dicentang, disimpan sebagai draft)
            </label>
            <div className="flex gap-2">
              <button data-testid="submit-return-button" onClick={handleSubmit} className="flex-1 primary-button justify-center">Buat Retur</button>
              <button onClick={() => setShowForm(false)} className="secondary-button">Batal</button>
            </div>
          </div>
        </div>
      )}

      {/* List */}
      <div className="section-card">
        <div className="overflow-hidden">
          <div className="grid grid-cols-[100px_1.3fr_110px_120px_110px_120px] px-3 py-1.5 bg-[#FAFBFC] text-[10px] font-bold uppercase text-[#6B6B73] border-b border-[#EFF0F2]">
            <span>Nomor</span><span>Supplier / PO</span><span className="text-right">Nilai</span><span>Nota Debit</span><span>Status</span><span className="text-right">Aksi</span>
          </div>
          {loading ? (
            <div className="py-10 text-center text-[12px] text-[#6B6B73]">Memuat retur...</div>
          ) : filtered.length === 0 ? (
            <div className="py-12 text-center text-[12px] text-[#6B6B73]">
              <RotateCcw className="mx-auto mb-2 text-gray-300" size={28} />
              <p>Belum ada retur beli.</p>
            </div>
          ) : (
            <div className="divide-y divide-[#EFF0F2] max-h-[560px] overflow-y-auto">
              {filtered.map((r) => (
                <div key={r.id} data-testid={`return-row-${r.id}`} onClick={() => setDetail(r)} className="grid grid-cols-[100px_1.3fr_110px_120px_110px_120px] items-center px-3 py-2.5 hover:bg-[#FAFBFC] cursor-pointer">
                  <span className="text-[11.5px] font-bold text-[#0058CC]">{r.number}</span>
                  <div className="min-w-0">
                    <p className="text-[12px] font-semibold truncate">{r.supplier_name || supName(r.supplier_id)}</p>
                    <p className="text-[10.5px] text-[#6B6B73] truncate">{r.po_number || "Tanpa PO"} · {r.items?.length || 0} item</p>
                  </div>
                  <span className="text-[12px] font-bold tabular-nums text-right text-amber-700">{formatCurrency(r.total_amount)}</span>
                  <span className="text-[11px] font-semibold text-[#0058CC]">{r.debit_note_number || "—"}</span>
                  <StatusPill status={r.status} />
                  <div className="flex items-center justify-end gap-1.5" onClick={(e) => e.stopPropagation()}>
                    {r.status === "draft" && (
                      <button data-testid={`return-submit-${r.id}`} onClick={() => act(r.id, "submit")} className="secondary-button !px-2 !py-1 text-[11px]"><Send size={11} /> Ajukan</button>
                    )}
                    {r.status === "pending_approval" && canApprove && (
                      <>
                        <button data-testid={`return-approve-${r.id}`} onClick={() => act(r.id, "approve", { notes: "" })} className="primary-button !px-2 !py-1 text-[11px]"><CheckCircle size={11} /> Setujui</button>
                        <button data-testid={`return-reject-${r.id}`} onClick={() => setRejectTarget(r)} className="danger-button !px-2 !py-1 text-[11px]"><XCircle size={11} /></button>
                      </>
                    )}
                    {(r.status === "approved" || r.status === "rejected") && (
                      <span className="text-[10.5px] text-[#9A9BA3]">{r.approved_by || r.rejected_by || "—"}</span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <ReturnDetailPanel
        ret={detail}
        supName={supName}
        canApprove={canApprove}
        onClose={() => setDetail(null)}
        onSubmit={(r) => act(r.id, "submit")}
        onApprove={(r) => act(r.id, "approve", { notes: "" })}
        onReject={(r) => { setDetail(null); setRejectTarget(r); }}
      />

      <ConfirmModal
        open={!!rejectTarget}
        title={`Tolak ${rejectTarget?.number || "Retur"}`}
        message="Berikan alasan penolakan retur (tersimpan di riwayat)."
        confirmLabel="Tolak Retur"
        danger
        withReason
        reasonLabel="Alasan penolakan"
        reasonPlaceholder="Mis. barang tidak memenuhi syarat retur supplier."
        onConfirm={async (reason) => { await act(rejectTarget.id, "reject", { notes: reason }); setRejectTarget(null); }}
        onCancel={() => setRejectTarget(null)}
        testId="return-reject-modal"
      />
    </div>
  );
}

function Field({ label, req, children }) {
  return (
    <div>
      <label className="block text-[10.5px] font-semibold text-[#6B6B73] mb-1">{label} {req && <span className="req">*</span>}</label>
      {children}
    </div>
  );
}
