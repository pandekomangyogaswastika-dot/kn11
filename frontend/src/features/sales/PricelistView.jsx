/**
 * PricelistView (F1a) — Pricelist per-Entitas (harga jual per-PT).
 * Owner/manager mengelola harga jual tiap PT per produk, dengan tanggal efektif
 * & histori. Fallback ke harga global bila entitas belum set harga.
 * Akses: admin/manager (permission "pricelist"). Sumber: /api/pricelist/*.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Tag, RefreshCw, Search, Plus, History, X, Download, Upload, Save,
  CheckCircle2, AlertTriangle, Building2,
} from "lucide-react";
import axios, { API } from "../../services/apiClient";
import ErrorNotice from "../../components/ErrorNotice";
import KNSelect from "../../components/KNSelect";
import EntityBadge from "../../components/EntityBadge";
import { formatCurrency } from "../../utils/formatters";

const STATUS_META = {
  current: { label: "Berlaku", tone: "bg-[#E6F6EC] text-[#1B7F4B]" },
  scheduled: { label: "Terjadwal", tone: "bg-[#E7F0FF] text-[#0058CC]" },
  expired: { label: "Kadaluarsa", tone: "bg-[#F5F5F7] text-[#8E8E93]" },
  inactive: { label: "Nonaktif", tone: "bg-[#FDEDE7] text-[#C0392B]" },
};

function fmtDate(iso) {
  if (!iso) return "—";
  try { return new Date(iso).toLocaleDateString("id-ID", { day: "2-digit", month: "short", year: "2-digit" }); }
  catch { return "—"; }
}

export default function PricelistView({ entities = [], selectedEntity, currentUser }) {
  const canManage = ["admin", "manager"].includes(currentUser?.role);
  const activeList = entities.filter((e) => e.status !== "inactive");
  const [entityId, setEntityId] = useState(
    selectedEntity && selectedEntity !== "all" ? selectedEntity : (activeList[0]?.id || ""));
  const [search, setSearch] = useState("");
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [priceModal, setPriceModal] = useState(null);    // { row }
  const [historyRow, setHistoryRow] = useState(null);    // { row }

  const load = useCallback(async () => {
    if (!entityId) return;
    setLoading(true); setError("");
    try {
      const res = await axios.get(`${API}/pricelist`, { params: { entity_id: entityId, search } });
      setRows(res.data?.rows || []);
    } catch (e) {
      setError(e.response?.data?.detail || "Gagal memuat pricelist.");
    } finally {
      setLoading(false);
    }
  }, [entityId, search]);

  useEffect(() => { load(); }, [load]);

  const entityOptions = useMemo(
    () => activeList.map((e) => ({ value: e.id, label: e.short_name || e.legal_name || e.id })),
    [activeList]);
  const overrideCount = rows.filter((r) => r.has_entity_price).length;

  const exportCsv = () => {
    const header = ["sku", "product_name", "category", "global_price", "effective_price", "source"];
    const lines = [header.join(",")].concat(
      rows.map((r) => [r.sku, `"${(r.product_name || "").replace(/"/g, "'")}"`, r.category,
        r.global_price, r.effective_price, r.price_source].join(",")));
    const blob = new Blob([lines.join("\n")], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    const eName = activeList.find((e) => e.id === entityId)?.short_name || entityId;
    a.href = url; a.download = `pricelist_${eName}_${new Date().toISOString().slice(0, 10)}.csv`; a.click();
    URL.revokeObjectURL(url);
  };

  const importCsv = async (file) => {
    if (!file) return;
    setNotice(""); setError("");
    try {
      const text = await file.text();
      const lines = text.split(/\r?\n/).filter((l) => l.trim());
      const head = lines.shift().split(",").map((h) => h.trim().toLowerCase());
      const iSku = head.indexOf("sku"), iPrice = head.indexOf("sell_price");
      const iFrom = head.indexOf("valid_from"), iUntil = head.indexOf("valid_until"), iNote = head.indexOf("note");
      if (iSku < 0 || iPrice < 0) { setError("CSV wajib punya kolom 'sku' dan 'sell_price'."); return; }
      const bySku = Object.fromEntries(rows.map((r) => [String(r.sku).toLowerCase(), r.product_id]));
      let ok = 0, fail = 0;
      for (const line of lines) {
        const cells = line.split(",");
        const pid = bySku[String(cells[iSku] || "").trim().toLowerCase()];
        const price = parseFloat(cells[iPrice]);
        if (!pid || !price || price <= 0) { fail++; continue; }
        try {
          await axios.post(`${API}/pricelist`, {
            product_id: pid, sell_price: price, entity_id: entityId,
            valid_from: iFrom >= 0 ? (cells[iFrom] || "").trim() : "",
            valid_until: iUntil >= 0 ? (cells[iUntil] || "").trim() : "",
            note: iNote >= 0 ? (cells[iNote] || "").trim() : "Import CSV",
          });
          ok++;
        } catch { fail++; }
      }
      setNotice(`Import selesai: ${ok} harga diset${fail ? `, ${fail} gagal/dilewati` : ""}.`);
      load();
    } catch (e) {
      setError("Gagal membaca file CSV.");
    }
  };

  return (
    <div data-testid="pricelist-view">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-3">
        <Kpi testId="pl-kpi-products" label="Produk" value={rows.length} icon={Tag} />
        <Kpi testId="pl-kpi-override" label="Harga Khusus PT" value={overrideCount} icon={Building2} tone="text-[#6B219A]" />
        <Kpi testId="pl-kpi-global" label="Pakai Harga Global" value={rows.length - overrideCount} icon={Tag} tone="text-[#8E8E93]" />
        <div className="section-card" data-testid="pl-kpi-entity">
          <div className="section-body flex items-center gap-3 py-3">
            <div className="w-9 h-9 rounded-lg bg-[#F3EAFB] flex items-center justify-center"><Building2 size={17} className="text-[#6B219A]" /></div>
            <div className="min-w-0">
              <p className="text-[10px] font-bold uppercase tracking-wide text-[#8E8E93]">Entitas</p>
              <EntityBadge entityId={entityId} entities={entities} />
            </div>
          </div>
        </div>
      </div>

      <div className="section-card">
        <div className="section-head flex-wrap gap-2">
          <div className="flex items-center gap-2 flex-wrap">
            <div className="w-[200px]">
              <KNSelect data-testid="pl-entity-select" className="field py-1.5 text-[12px]" value={entityId}
                onValueChange={setEntityId} placeholder="Pilih entitas" options={entityOptions} />
            </div>
            <div className="relative">
              <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[#9A9BA3]" />
              <input data-testid="pl-search" className="field py-1.5 pl-8 text-[12px] w-[220px]" placeholder="Cari SKU / nama / kategori"
                value={search} onChange={(e) => setSearch(e.target.value)} />
            </div>
          </div>
          <div className="flex items-center gap-2 ml-auto">
            <button data-testid="pl-export" className="btn-secondary text-[12px] py-1.5 px-3 inline-flex items-center gap-1" onClick={exportCsv}><Download size={13} /> Export</button>
            {canManage && (
              <label data-testid="pl-import" className="btn-secondary text-[12px] py-1.5 px-3 inline-flex items-center gap-1 cursor-pointer">
                <Upload size={13} /> Import
                <input type="file" accept=".csv" className="hidden" onChange={(e) => { importCsv(e.target.files?.[0]); e.target.value = ""; }} />
              </label>
            )}
            <button data-testid="pl-refresh" className="icon-button" onClick={load} aria-label="Refresh"><RefreshCw size={14} className={loading ? "animate-spin" : ""} /></button>
          </div>
        </div>
        <div className="section-body">
          <ErrorNotice message={error} onRetry={load} onDismiss={() => setError("")} testId="pl-error" />
          {notice && (
            <div data-testid="pl-notice" className="mb-3 rounded-md bg-[#E6F6EC] border border-[#BDE5CC] text-[#1B7F4B] text-[12px] px-3 py-2 flex items-center gap-2">
              <CheckCircle2 size={14} />{notice}<button className="ml-auto" onClick={() => setNotice("")} aria-label="Tutup"><X size={13} /></button>
            </div>
          )}

          {loading ? (
            <div className="grid gap-2" data-testid="pl-loading">{[0, 1, 2, 3, 4].map((i) => <div key={i} className="h-10 bg-[#F5F5F7] rounded animate-pulse" />)}</div>
          ) : rows.length === 0 ? (
            <div data-testid="pl-empty" className="py-12 text-center text-[12px] text-[#8E8E93]"><Tag size={26} className="mx-auto mb-2 text-gray-300" />Tidak ada produk.</div>
          ) : (
            <div className="overflow-auto rounded-md border border-[#EFF0F2]">
              <table className="w-full text-[12px]">
                <thead>
                  <tr className="text-left text-[10px] font-bold uppercase text-[#8E8E93] bg-[#FAFBFC] border-b border-[#EFF0F2]">
                    <th className="px-3 py-2">SKU</th>
                    <th className="px-3 py-2">Produk</th>
                    <th className="px-3 py-2 text-right">Harga Global</th>
                    <th className="px-3 py-2 text-right">Harga {activeList.find((e) => e.id === entityId)?.short_name || "PT"}</th>
                    <th className="px-3 py-2 text-center">Sumber</th>
                    <th className="px-3 py-2 text-right">Aksi</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r) => (
                    <tr key={r.product_id} data-testid={`pl-row-${r.product_id}`} className="border-b border-[#F5F5F7] last:border-0 hover:bg-[#FBF8FE]">
                      <td className="px-3 py-2 font-mono text-[11px] text-[#6B6B73]">{r.sku}</td>
                      <td className="px-3 py-2"><span className="font-medium text-[#1C1C1E]">{r.product_name}</span><span className="block text-[10px] text-[#9A9BA3]">{r.category}</span></td>
                      <td className="px-3 py-2 text-right tabular-nums text-[#8E8E93]">{formatCurrency(r.global_price)}</td>
                      <td className={`px-3 py-2 text-right tabular-nums font-semibold ${r.has_entity_price ? "text-[#6B219A]" : "text-[#9A9BA3]"}`} data-testid={`pl-eff-${r.product_id}`}>{formatCurrency(r.effective_price)}</td>
                      <td className="px-3 py-2 text-center">
                        <span className={`text-[9px] font-bold rounded px-1.5 py-0.5 ${r.has_entity_price ? "bg-[#F0EAFB] text-[#6B2FB3]" : "bg-[#F5F5F7] text-[#8E8E93]"}`}>{r.has_entity_price ? "Harga PT" : "Global"}</span>
                      </td>
                      <td className="px-3 py-2 text-right whitespace-nowrap">
                        <button data-testid={`pl-history-${r.product_id}`} className="icon-button" title="Riwayat" onClick={() => setHistoryRow(r)}><History size={14} /></button>
                        {canManage && (
                          <button data-testid={`pl-setprice-${r.product_id}`} className="btn-primary text-[11px] py-1 px-2.5 ml-1 inline-flex items-center gap-1" onClick={() => setPriceModal(r)}><Plus size={12} /> Set Harga</button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {priceModal && (
        <SetPriceModal row={priceModal} entityId={entityId} entityName={activeList.find((e) => e.id === entityId)?.short_name}
          onClose={() => setPriceModal(null)} onSaved={() => { setPriceModal(null); setNotice(`Harga ${priceModal.product_name} tersimpan.`); load(); }} onError={setError} />
      )}
      {historyRow && (
        <HistoryModal row={historyRow} entityId={entityId} entities={entities} canManage={canManage}
          onClose={() => setHistoryRow(null)} onChanged={() => { load(); }} />
      )}
    </div>
  );
}

// ─── Set Harga Modal ─────────────────────────────────────────────────────────
function SetPriceModal({ row, entityId, entityName, onClose, onSaved, onError }) {
  const today = new Date().toISOString().slice(0, 10);
  const [price, setPrice] = useState("");
  const [validFrom, setValidFrom] = useState(today);
  const [validUntil, setValidUntil] = useState("");
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);

  const save = async () => {
    const p = parseFloat(price);
    if (!p || p <= 0) { onError("Harga jual harus lebih dari 0."); return; }
    setSaving(true);
    try {
      await axios.post(`${API}/pricelist`, {
        product_id: row.product_id, sell_price: p, entity_id: entityId,
        valid_from: validFrom, valid_until: validUntil, note,
      });
      onSaved();
    } catch (e) {
      onError(e.response?.data?.detail || "Gagal menyimpan harga.");
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" data-testid="pl-setprice-modal">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md">
        <div className="flex items-center gap-2 px-4 py-3 border-b border-[#EFF0F2]">
          <Tag size={16} className="text-[#6B219A]" />
          <h3 className="font-bold text-[14px]">Set Harga · {entityName}</h3>
          <button data-testid="pl-setprice-close" className="icon-button ml-auto" onClick={onClose} aria-label="Tutup"><X size={15} /></button>
        </div>
        <div className="p-4 space-y-3 text-[12px]">
          <div className="rounded-md bg-[#FAFBFC] border border-[#EFF0F2] px-3 py-2">
            <p className="font-semibold text-[#1C1C1E]">{row.product_name}</p>
            <p className="text-[11px] text-[#9A9BA3]">{row.sku} · Harga global: {formatCurrency(row.global_price)} / {row.base_unit}</p>
          </div>
          <div>
            <label className="block text-[11px] font-semibold text-[#6B6B73] mb-1">Harga Jual (per {row.base_unit})</label>
            <input data-testid="pl-input-price" type="number" className="field py-2 text-[13px]" placeholder="Mis. 195000" value={price} onChange={(e) => setPrice(e.target.value)} autoFocus />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-[11px] font-semibold text-[#6B6B73] mb-1">Berlaku Mulai</label>
              <input data-testid="pl-input-from" type="date" className="field py-2 text-[13px]" value={validFrom} onChange={(e) => setValidFrom(e.target.value)} />
            </div>
            <div>
              <label className="block text-[11px] font-semibold text-[#6B6B73] mb-1">Berlaku Sampai <span className="text-[#9A9BA3] font-normal">(opsional)</span></label>
              <input data-testid="pl-input-until" type="date" className="field py-2 text-[13px]" value={validUntil} onChange={(e) => setValidUntil(e.target.value)} />
            </div>
          </div>
          <div>
            <label className="block text-[11px] font-semibold text-[#6B6B73] mb-1">Catatan <span className="text-[#9A9BA3] font-normal">(opsional)</span></label>
            <input data-testid="pl-input-note" className="field py-2 text-[13px]" placeholder="Mis. penyesuaian harga Q3" value={note} onChange={(e) => setNote(e.target.value)} />
          </div>
        </div>
        <div className="flex justify-end gap-2 px-4 py-3 border-t border-[#EFF0F2]">
          <button className="btn-secondary text-[12px] py-1.5 px-4" onClick={onClose}>Batal</button>
          <button data-testid="pl-setprice-save" className="btn-primary text-[12px] py-1.5 px-4 inline-flex items-center gap-1" onClick={save} disabled={saving}><Save size={14} /> {saving ? "Menyimpan…" : "Simpan Harga"}</button>
        </div>
      </div>
    </div>
  );
}

// ─── Riwayat Harga Modal ─────────────────────────────────────────────────────
function HistoryModal({ row, entityId, entities, canManage, onClose, onChanged }) {
  const [records, setRecords] = useState([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");

  const load = useCallback(async () => {
    setLoading(true); setErr("");
    try {
      const res = await axios.get(`${API}/pricelist/records`, { params: { product_id: row.product_id, entity_id: entityId } });
      setRecords(Array.isArray(res.data) ? res.data : []);
    } catch (e) {
      setErr(e.response?.data?.detail || "Gagal memuat riwayat.");
    } finally {
      setLoading(false);
    }
  }, [row.product_id, entityId]);

  useEffect(() => { load(); }, [load]);

  const deactivate = async (id) => {
    try {
      await axios.delete(`${API}/pricelist/${id}`);
      load(); onChanged();
    } catch (e) {
      setErr(e.response?.data?.detail || "Gagal menonaktifkan harga.");
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" data-testid="pl-history-modal">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-2xl max-h-[85vh] flex flex-col">
        <div className="flex items-center gap-2 px-4 py-3 border-b border-[#EFF0F2]">
          <History size={16} className="text-[#6B219A]" />
          <h3 className="font-bold text-[14px]">Riwayat Harga · {row.product_name}</h3>
          <EntityBadge entityId={entityId} entities={entities} />
          <button data-testid="pl-history-close" className="icon-button ml-auto" onClick={onClose} aria-label="Tutup"><X size={15} /></button>
        </div>
        <div className="p-4 overflow-auto">
          {err && <div className="mb-2 text-[12px] text-[#C0392B] flex items-center gap-1"><AlertTriangle size={13} />{err}</div>}
          {loading ? (
            <div className="grid gap-2">{[0, 1, 2].map((i) => <div key={i} className="h-9 bg-[#F5F5F7] rounded animate-pulse" />)}</div>
          ) : records.length === 0 ? (
            <div data-testid="pl-history-empty" className="py-8 text-center text-[12px] text-[#8E8E93]">Belum ada harga khusus PT untuk produk ini — memakai harga global {formatCurrency(row.global_price)}.</div>
          ) : (
            <div className="overflow-auto rounded-md border border-[#EFF0F2]">
              <table className="w-full text-[12px]">
                <thead>
                  <tr className="text-left text-[10px] font-bold uppercase text-[#8E8E93] bg-[#FAFBFC] border-b border-[#EFF0F2]">
                    <th className="px-3 py-2 text-right">Harga</th>
                    <th className="px-3 py-2">Mulai</th>
                    <th className="px-3 py-2">Sampai</th>
                    <th className="px-3 py-2 text-center">Status</th>
                    <th className="px-3 py-2">Catatan</th>
                    {canManage && <th className="px-3 py-2"></th>}
                  </tr>
                </thead>
                <tbody>
                  {records.map((r) => {
                    const sm = STATUS_META[r.effective_status] || STATUS_META.inactive;
                    return (
                      <tr key={r.id} data-testid={`pl-hist-row-${r.id}`} className="border-b border-[#F5F5F7] last:border-0">
                        <td className="px-3 py-2 text-right tabular-nums font-semibold text-[#6B219A]">{formatCurrency(r.sell_price)}</td>
                        <td className="px-3 py-2">{fmtDate(r.valid_from)}</td>
                        <td className="px-3 py-2">{r.valid_until ? fmtDate(r.valid_until) : "∞"}</td>
                        <td className="px-3 py-2 text-center"><span className={`text-[9px] font-bold rounded px-1.5 py-0.5 ${sm.tone}`}>{sm.label}</span></td>
                        <td className="px-3 py-2 text-[#6B6B73] max-w-[160px] truncate" title={r.note}>{r.note || "—"}</td>
                        {canManage && (
                          <td className="px-3 py-2 text-right">
                            {r.status !== "inactive" && <button data-testid={`pl-deactivate-${r.id}`} className="text-[11px] text-[#C0392B] hover:underline" onClick={() => deactivate(r.id)}>Nonaktifkan</button>}
                          </td>
                        )}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
        <div className="flex justify-end px-4 py-3 border-t border-[#EFF0F2]">
          <button className="btn-primary text-[12px] py-1.5 px-4" onClick={onClose}>Tutup</button>
        </div>
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
