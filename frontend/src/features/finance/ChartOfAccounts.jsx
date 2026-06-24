/**
 * ChartOfAccounts (EPIC7-C) — Bagan Akun / Chart of Accounts.
 * Akses admin/manager (permission "accounting"). Sumber: /api/gl/accounts.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  RefreshCw, Plus, BookOpen, Pencil, Trash2, X, Layers,
} from "lucide-react";
import axios, { API } from "../../services/apiClient";
import ErrorNotice from "../../components/ErrorNotice";
import KNSelect from "../../components/KNSelect";

const TYPE_META = {
  asset: { label: "Aset", tone: "bg-[#E7F0FF] text-[#0058CC]" },
  liability: { label: "Kewajiban", tone: "bg-[#FDEDE7] text-[#C0392B]" },
  equity: { label: "Ekuitas", tone: "bg-[#F3EAFB] text-[#6B219A]" },
  income: { label: "Pendapatan", tone: "bg-[#E6F6EC] text-[#1B7F4B]" },
  expense: { label: "Beban", tone: "bg-[#FFF4E0] text-[#B45309]" },
};
const TYPE_ORDER = ["asset", "liability", "equity", "income", "expense"];
const TYPE_OPTIONS = TYPE_ORDER.map((t) => ({ value: t, label: TYPE_META[t].label }));
const EMPTY_FORM = { code: "", name: "", type: "asset", parent_code: "", is_postable: true };

export default function ChartOfAccounts() {
  const [accounts, setAccounts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [filterType, setFilterType] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [editAcc, setEditAcc] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/gl/accounts`);
      setAccounts(Array.isArray(res.data) ? res.data : []);
      setError("");
    } catch (e) {
      setError(e.response?.data?.detail || "Gagal memuat bagan akun.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const parentOptions = useMemo(
    () => [{ value: "", label: "— Tanpa induk (root) —" },
      ...accounts.map((a) => ({ value: a.code, label: `${a.code} — ${a.name}` }))],
    [accounts]);

  const stats = useMemo(() => {
    const byType = {};
    TYPE_ORDER.forEach((t) => { byType[t] = 0; });
    accounts.forEach((a) => { byType[a.type] = (byType[a.type] || 0) + 1; });
    return {
      total: accounts.length,
      postable: accounts.filter((a) => a.is_postable).length,
      byType,
    };
  }, [accounts]);

  const grouped = useMemo(() => {
    const rows = filterType ? accounts.filter((a) => a.type === filterType) : accounts;
    const g = {};
    TYPE_ORDER.forEach((t) => { g[t] = []; });
    rows.forEach((a) => { (g[a.type] = g[a.type] || []).push(a); });
    TYPE_ORDER.forEach((t) => g[t].sort((x, y) => (x.code > y.code ? 1 : -1)));
    return g;
  }, [accounts, filterType]);

  const submitForm = async (e) => {
    e.preventDefault();
    if (!form.code.trim() || !form.name.trim()) return;
    setSaving(true);
    try {
      await axios.post(`${API}/gl/accounts`, form);
      setForm(EMPTY_FORM);
      setShowForm(false);
      await load();
    } catch (err) {
      setError(err.response?.data?.detail || "Gagal membuat akun.");
    } finally {
      setSaving(false);
    }
  };

  const removeAccount = async (acc) => {
    setError("");
    try {
      await axios.delete(`${API}/gl/accounts/${acc.code}`);
      await load();
    } catch (err) {
      setError(err.response?.data?.detail || "Gagal menghapus akun.");
    }
  };

  return (
    <div data-testid="coa-view">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-3">
        <Kpi testId="coa-kpi-total" label="Total Akun" value={stats.total} icon={BookOpen} />
        <Kpi testId="coa-kpi-postable" label="Akun Detail (Postable)" value={stats.postable} icon={Layers} tone="text-[#0058CC]" />
        <Kpi testId="coa-kpi-asset" label="Aset / Beban" value={`${stats.byType.asset} / ${stats.byType.expense}`} icon={Layers} tone="text-[#1B7F4B]" />
        <Kpi testId="coa-kpi-liab" label="Kewajiban / Ekuitas" value={`${stats.byType.liability} / ${stats.byType.equity}`} icon={Layers} tone="text-[#6B219A]" />
      </div>

      <div className="section-card">
        <div className="section-head">
          <div className="flex items-center gap-2"><BookOpen size={16} className="text-[#6B219A]" /><h2 data-testid="coa-title">Bagan Akun (Chart of Accounts)</h2></div>
          <div className="flex items-center gap-2 ml-auto">
            <div className="w-[170px]">
              <KNSelect data-testid="coa-filter-type" className="field py-1 text-[12px]" value={filterType} onValueChange={setFilterType}
                placeholder="Semua tipe" options={[{ value: "", label: "Semua tipe" }, ...TYPE_OPTIONS]} />
            </div>
            <button data-testid="coa-add-toggle" className="btn-primary text-[12px] py-1.5 px-3 inline-flex items-center gap-1" onClick={() => setShowForm((v) => !v)}>
              <Plus size={14} /> Tambah Akun
            </button>
            <button data-testid="coa-refresh" className="icon-button" onClick={load} aria-label="Refresh"><RefreshCw size={14} className={loading ? "animate-spin" : ""} /></button>
          </div>
        </div>
        <div className="section-body">
          <ErrorNotice message={error} onRetry={load} onDismiss={() => setError("")} testId="coa-error" />

          {showForm && (
            <form data-testid="coa-add-form" onSubmit={submitForm} className="mb-3 rounded-lg border border-[#E6E0F2] bg-[#FAF8FE] p-3 grid grid-cols-2 md:grid-cols-3 gap-2">
              <Labeled label="Kode Akun">
                <input data-testid="coa-form-code" className="field py-1 text-[12px] tabular-nums" value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} placeholder="6-5000" required />
              </Labeled>
              <Labeled label="Nama Akun">
                <input data-testid="coa-form-name" className="field py-1 text-[12px]" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Beban Pemasaran" required />
              </Labeled>
              <Labeled label="Tipe">
                <KNSelect data-testid="coa-form-type" className="field py-1 text-[12px]" value={form.type} onValueChange={(v) => setForm({ ...form, type: v })} options={TYPE_OPTIONS} />
              </Labeled>
              <Labeled label="Akun Induk (opsional)">
                <KNSelect data-testid="coa-form-parent" className="field py-1 text-[12px]" value={form.parent_code} onValueChange={(v) => setForm({ ...form, parent_code: v })} options={parentOptions} placeholder="— Tanpa induk —" />
              </Labeled>
              <Labeled label="Jenis Akun">
                <div className="flex gap-1 mt-0.5">
                  {[{ k: true, t: "Detail" }, { k: false, t: "Header" }].map((o) => (
                    <button type="button" key={String(o.k)} data-testid={`coa-form-postable-${o.k}`}
                      className={`flex-1 text-[12px] font-semibold rounded-md py-1 border ${form.is_postable === o.k ? "bg-[#6B219A] text-white border-[#6B219A]" : "bg-white border-[#EFF0F2] text-[#6B6B73]"}`}
                      onClick={() => setForm({ ...form, is_postable: o.k })}>{o.t}</button>
                  ))}
                </div>
              </Labeled>
              <div className="col-span-2 md:col-span-3 flex justify-end gap-2 mt-1">
                <button type="button" className="btn-secondary text-[12px] py-1.5 px-3" onClick={() => { setShowForm(false); setForm(EMPTY_FORM); }}>Batal</button>
                <button type="submit" data-testid="coa-form-submit" className="btn-primary text-[12px] py-1.5 px-4" disabled={saving}>{saving ? "Menyimpan..." : "Simpan Akun"}</button>
              </div>
            </form>
          )}

          {loading ? (
            <div className="grid gap-2" data-testid="coa-loading">{[0, 1, 2, 3].map((i) => <div key={i} className="h-9 bg-[#F5F5F7] rounded animate-pulse" />)}</div>
          ) : accounts.length === 0 ? (
            <div data-testid="coa-empty" className="py-12 text-center text-[12px] text-[#8E8E93]">
              <BookOpen size={26} className="mx-auto mb-2 text-gray-300" />Belum ada akun.
            </div>
          ) : (
            <div className="space-y-4" data-testid="coa-groups">
              {TYPE_ORDER.filter((t) => grouped[t] && grouped[t].length > 0).map((t) => (
                <div key={t} data-testid={`coa-group-${t}`}>
                  <div className="flex items-center gap-2 mb-1.5">
                    <span className={`text-[10px] font-bold uppercase tracking-wide rounded px-2 py-0.5 ${TYPE_META[t].tone}`}>{TYPE_META[t].label}</span>
                    <span className="text-[11px] text-[#9A9BA3]">{grouped[t].length} akun</span>
                  </div>
                  <div className="overflow-hidden rounded-md border border-[#EFF0F2]">
                    <table className="w-full text-[12px]">
                      <tbody>
                        {grouped[t].map((a) => (
                          <tr key={a.code} data-testid={`coa-row-${a.code}`} className={`border-b border-[#F5F5F7] last:border-0 ${a.is_postable ? "" : "bg-[#FAFBFC]"}`}>
                            <td className="px-3 py-2 w-[110px]"><span className="font-mono font-semibold text-[#3C3C43] tabular-nums">{a.code}</span></td>
                            <td className="px-3 py-2">
                              <span className={a.is_postable ? "text-[#1C1C1E]" : "font-bold text-[#3C3C43] uppercase text-[11px] tracking-wide"}>{a.name}</span>
                              {a.is_active === false && <span className="ml-2 text-[10px] text-[#C0392B]">nonaktif</span>}
                            </td>
                            <td className="px-3 py-2 text-right text-[10px] text-[#9A9BA3]">{a.is_postable ? "Detail" : "Header"} · {a.normal_balance === "debit" ? "D" : "K"}</td>
                            <td className="px-3 py-2 w-[80px] text-right">
                              <div className="inline-flex items-center gap-1">
                                <button data-testid={`coa-edit-${a.code}`} className="icon-button" onClick={() => setEditAcc(a)} aria-label="Edit"><Pencil size={13} /></button>
                                {!a.system && (
                                  <button data-testid={`coa-delete-${a.code}`} className="icon-button text-[#C0392B]" onClick={() => removeAccount(a)} aria-label="Hapus"><Trash2 size={13} /></button>
                                )}
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {editAcc && (
        <EditAccountModal acc={editAcc} onClose={() => setEditAcc(null)}
          onSaved={async () => { setEditAcc(null); await load(); }}
          onError={(m) => setError(m)} />
      )}
    </div>
  );
}

function EditAccountModal({ acc, onClose, onSaved, onError }) {
  const [name, setName] = useState(acc.name);
  const [isActive, setIsActive] = useState(acc.is_active !== false);
  const [saving, setSaving] = useState(false);

  const save = async () => {
    setSaving(true);
    try {
      await axios.patch(`${API}/gl/accounts/${acc.code}`, { name: name.trim(), is_active: isActive });
      await onSaved();
    } catch (err) {
      onError(err.response?.data?.detail || "Gagal menyimpan akun.");
      onClose();
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" data-testid="coa-edit-modal">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md">
        <div className="flex items-center gap-2 px-4 py-3 border-b border-[#EFF0F2]">
          <Pencil size={15} className="text-[#6B219A]" />
          <h3 className="font-bold text-[14px]">Edit Akun <span className="font-mono tabular-nums text-[#6B6B73]">{acc.code}</span></h3>
          <button data-testid="coa-edit-close" className="icon-button ml-auto" onClick={onClose} aria-label="Tutup"><X size={15} /></button>
        </div>
        <div className="p-4 space-y-3">
          <Labeled label="Nama Akun">
            <input data-testid="coa-edit-name" className="field py-1.5 text-[13px]" value={name} onChange={(e) => setName(e.target.value)} />
          </Labeled>
          <label className="flex items-center gap-2 text-[12px] text-[#3C3C43]">
            <input data-testid="coa-edit-active" type="checkbox" checked={isActive} onChange={(e) => setIsActive(e.target.checked)} />
            Akun aktif (dapat dijurnal)
          </label>
          {acc.system && <p className="text-[11px] text-[#8E8E93]">Akun baku sistem — hanya nama & status aktif yang dapat diubah.</p>}
        </div>
        <div className="flex justify-end gap-2 px-4 py-3 border-t border-[#EFF0F2]">
          <button className="btn-secondary text-[12px] py-1.5 px-3" onClick={onClose}>Batal</button>
          <button data-testid="coa-edit-save" className="btn-primary text-[12px] py-1.5 px-4" onClick={save} disabled={saving}>{saving ? "Menyimpan..." : "Simpan"}</button>
        </div>
      </div>
    </div>
  );
}

function Labeled({ label, children }) {
  return (
    <div>
      <label className="text-[10px] font-bold uppercase text-[#8E8E93]">{label}</label>
      {children}
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
