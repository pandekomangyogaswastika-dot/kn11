/**
 * SettingsPanel — Configuration Foundation (Fase 1A).
 * Mengelola pengaturan global (pajak/keuangan/penjualan/inventory),
 * Term Pembayaran (CRUD), dan Matriks Approval (CRUD). Semua CONFIGURABLE.
 */
import { useEffect, useState } from "react";
import { Save, Plus, Trash2, Receipt, Wallet, CreditCard, ShieldCheck, Boxes, RefreshCw, ShoppingCart } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import KNSelect from "../../components/KNSelect";

const SUBTABS = [
  ["umum", "Umum", Receipt],
  ["terms", "Term Pembayaran", CreditCard],
  ["approval", "Matriks Approval", ShieldCheck],
];

const DOC_TYPES = [
  ["sales_order", "Sales Order"],
  ["purchase_order", "Purchase Order"],
  ["discount", "Diskon (%)"],
  ["transfer", "Transfer Gudang"],
];

const fmtRp = (v) => "Rp " + Number(v || 0).toLocaleString("id-ID");

export default function SettingsPanel({ entities = [] }) {
  const [sub, setSub] = useState("umum");
  const [settings, setSettings] = useState(null);
  const [terms, setTerms] = useState([]);
  const [rules, setRules] = useState([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState("");

  const fetchAll = async () => {
    setLoading(true);
    try {
      const [s, t, r] = await Promise.all([
        axios.get(`${API}/settings/effective`),
        axios.get(`${API}/payment-terms`),
        axios.get(`${API}/approval-rules`),
      ]);
      setSettings(s.data);
      setTerms(t.data);
      setRules(r.data);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  };
  useEffect(() => { fetchAll(); }, []);

  const flash = (m) => { setMsg(m); setTimeout(() => setMsg(""), 2500); };

  const setSection = (sec, key, val) =>
    setSettings((p) => ({ ...p, [sec]: { ...(p?.[sec] || {}), [key]: val } }));

  const saveSettings = async () => {
    setSaving(true);
    try {
      await axios.put(`${API}/settings`, {
        scope: "global",
        tax: settings.tax, finance: settings.finance,
        sales: settings.sales, inventory: settings.inventory,
        allocation: settings.allocation, purchasing: settings.purchasing,
      });
      flash("Pengaturan tersimpan");
    } catch (e) { alert(e.response?.data?.detail || "Gagal simpan"); }
    finally { setSaving(false); }
  };

  // ── Payment terms CRUD ──
  const [newTerm, setNewTerm] = useState({ code: "", name: "", type: "credit", net_days: 0, dp_percent: 0, installment_count: 0 });
  const addTerm = async () => {
    if (!newTerm.code || !newTerm.name) return alert("Kode & nama wajib diisi");
    try {
      await axios.post(`${API}/payment-terms`, { ...newTerm, sort: terms.length + 1, active: true });
      setNewTerm({ code: "", name: "", type: "credit", net_days: 0, dp_percent: 0, installment_count: 0 });
      fetchAll(); flash("Term ditambahkan");
    } catch (e) { alert(e.response?.data?.detail || "Gagal"); }
  };
  const toggleTerm = async (t) => {
    await axios.patch(`${API}/payment-terms/${t.id}`, { data: { active: !t.active } });
    fetchAll();
  };

  // ── Approval rules CRUD ──
  const [newRule, setNewRule] = useState({ doc_type: "sales_order", entity_id: "all", min_amount: 0, max_amount: "", required_role: "manager", is_percent: false });
  const addRule = async () => {
    try {
      await axios.post(`${API}/approval-rules`, {
        ...newRule,
        max_amount: newRule.max_amount === "" ? null : Number(newRule.max_amount),
        is_percent: newRule.doc_type === "discount",
        sort: rules.filter((r) => r.doc_type === newRule.doc_type).length + 1,
        active: true,
      });
      setNewRule({ doc_type: "sales_order", entity_id: "all", min_amount: 0, max_amount: "", required_role: "manager", is_percent: false });
      fetchAll(); flash("Rule ditambahkan");
    } catch (e) { alert(e.response?.data?.detail || "Gagal"); }
  };
  const delRule = async (id) => {
    if (!window.confirm("Hapus rule ini?")) return;
    await axios.delete(`${API}/approval-rules/${id}`);
    fetchAll();
  };

  if (loading || !settings) {
    return <div data-testid="settings-panel" className="section-card"><div className="section-body text-[12px] text-[#6B6B73]">Memuat pengaturan…</div></div>;
  }

  const tax = settings.tax || {}, fin = settings.finance || {}, sal = settings.sales || {}, inv = settings.inventory || {}, alloc = settings.allocation || {}, pur = settings.purchasing || {};

  return (
    <div data-testid="settings-panel" className="flex flex-col gap-3">
      {/* Sub-tab bar */}
      <div className="flex flex-wrap items-center gap-1.5">
        {SUBTABS.map(([id, label, Icon]) => (
          <button key={id} data-testid={`settings-subtab-${id}`} onClick={() => setSub(id)}
            className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[12px] font-semibold transition-all ${sub === id ? "bg-[#007AFF] text-white" : "bg-white border border-[#E5E5EA] text-[#6B6B73] hover:border-[#007AFF]"}`}>
            <Icon size={13} /> {label}
          </button>
        ))}
        <button onClick={fetchAll} className="ml-auto p-1.5 rounded-lg border border-[#E5E5EA] text-[#6B6B73] hover:bg-[#FAFBFC]"><RefreshCw size={13} /></button>
        {msg && <span data-testid="settings-flash" className="text-[12px] font-semibold text-[#34C759]">{msg}</span>}
      </div>

      {/* ── UMUM ── */}
      {sub === "umum" && (
        <div className="grid gap-3 md:grid-cols-2">
          {/* Pajak & Faktur */}
          <div className="section-card">
            <div className="section-head"><div className="flex items-center gap-2"><Receipt size={15} className="text-[#007AFF]" /><h2>Pajak & Faktur</h2></div></div>
            <div className="section-body grid gap-2.5">
              <Field label="Tarif PPN (%)">
                <input type="number" data-testid="settings-ppn-rate" className="field tabular-nums" value={tax.ppn_rate ?? 11}
                  onChange={(e) => setSection("tax", "ppn_rate", parseFloat(e.target.value) || 0)} />
              </Field>
              <Field label="Mode PPN">
                <KNSelect data-testid="settings-ppn-mode" className="field" value={tax.ppn_mode || "excluded"}
                  onValueChange={(v) => setSection("tax", "ppn_mode", v)}
                  options={[
                    { value: "excluded", label: "Excluded — ditambah saat invoice" },
                    { value: "included", label: "Included — sudah termasuk di harga" },
                  ]}
                />
              </Field>
              <Toggle label="e-Faktur diaktifkan (PKP)" testid="settings-efaktur"
                checked={!!tax.efaktur_enabled} onChange={(v) => setSection("tax", "efaktur_enabled", v)} />
              <p className="text-[10.5px] text-[#8E8E93]">Entitas non-PKP otomatis PPN 0% & tanpa e-Faktur (mengikuti master entitas).</p>
            </div>
          </div>

          {/* Keuangan */}
          <div className="section-card">
            <div className="section-head"><div className="flex items-center gap-2"><Wallet size={15} className="text-[#007AFF]" /><h2>Keuangan</h2></div></div>
            <div className="section-body grid gap-2.5">
              <Field label="Mata Uang Dasar">
                <input data-testid="settings-currency" className="field" value={fin.base_currency || "IDR"}
                  onChange={(e) => setSection("finance", "base_currency", e.target.value)} />
              </Field>
              <Field label="Bulan Tutup Buku Fiskal">
                <KNSelect data-testid="settings-fiscal-month" className="field" value={String(fin.fiscal_year_end_month || 12)}
                  onValueChange={(v) => setSection("finance", "fiscal_year_end_month", parseInt(v))}
                  options={["Jan","Feb","Mar","Apr","Mei","Jun","Jul","Agu","Sep","Okt","Nov","Des"].map((m, i) => ({ value: String(i + 1), label: m }))}
                />
              </Field>
              <Field label="Term Pembayaran Default">
                <KNSelect data-testid="settings-default-term" className="field" value={fin.default_payment_term_code || ""}
                  onValueChange={(v) => setSection("finance", "default_payment_term_code", v)}
                  options={terms.map((t) => ({ value: t.code, label: t.name }))}
                />
              </Field>
            </div>
          </div>

          {/* Penjualan */}
          <div className="section-card">
            <div className="section-head"><div className="flex items-center gap-2"><CreditCard size={15} className="text-[#007AFF]" /><h2>Penjualan</h2></div></div>
            <div className="section-body grid gap-2">
              <Toggle label="Aktifkan tahap Quotation" testid="settings-quotation" checked={!!sal.quotation_enabled} onChange={(v) => setSection("sales", "quotation_enabled", v)} />
              <Toggle label="Izinkan partial shipment" testid="settings-partial" checked={!!sal.allow_partial_shipment} onChange={(v) => setSection("sales", "allow_partial_shipment", v)} />
              <Toggle label="Izinkan diskon per-order" testid="settings-order-disc" checked={!!sal.allow_order_discount} onChange={(v) => setSection("sales", "allow_order_discount", v)} />
              <Toggle label="Izinkan diskon per-item" testid="settings-item-disc" checked={!!sal.allow_item_discount} onChange={(v) => setSection("sales", "allow_item_discount", v)} />
            </div>
          </div>

          {/* Inventory */}
          <div className="section-card">
            <div className="section-head"><div className="flex items-center gap-2"><Boxes size={15} className="text-[#007AFF]" /><h2>Inventory</h2></div></div>
            <div className="section-body grid gap-2.5">
              <Field label="UOM Default"><input data-testid="settings-default-uom" className="field" value={inv.default_uom || "meter"} onChange={(e) => setSection("inventory", "default_uom", e.target.value)} /></Field>
              <Field label="Minimum Potong (qty)"><input type="number" data-testid="settings-mincut" className="field tabular-nums" value={inv.min_cut_qty ?? 0.5} onChange={(e) => setSection("inventory", "min_cut_qty", parseFloat(e.target.value) || 0)} /></Field>
              <Toggle label="Transfer antar-entitas wajib sebelum jual stok entitas lain" testid="settings-ic-transfer" checked={!!inv.intercompany_transfer_required} onChange={(v) => setSection("inventory", "intercompany_transfer_required", v)} />
            </div>
          </div>

          {/* Pembelian / Procurement (Depth #3) */}
          <div className="section-card">
            <div className="section-head"><div className="flex items-center gap-2"><ShoppingCart size={15} className="text-[#007AFF]" /><h2>Pembelian (Procurement)</h2></div></div>
            <div className="section-body grid gap-2.5">
              <Field label="Threshold Approval Deviasi Harga (%)">
                <input type="number" data-testid="settings-price-deviation" className="field tabular-nums"
                  value={pur.price_deviation_approval_percent ?? 10}
                  onChange={(e) => setSection("purchasing", "price_deviation_approval_percent", parseFloat(e.target.value) || 0)} />
              </Field>
              <p className="text-[10.5px] text-[#8E8E93]">PO dengan harga beli melebihi harga price-list supplier di atas batas ini akan otomatis butuh persetujuan.</p>
              <Field label="Toleransi Qty Terima vs PO (%)">
                <input type="number" data-testid="settings-receive-tolerance" className="field tabular-nums"
                  value={pur.receive_tolerance_percent ?? 2}
                  onChange={(e) => setSection("purchasing", "receive_tolerance_percent", parseFloat(e.target.value) || 0)} />
              </Field>
              <Toggle label="Inspeksi QC saat barang masuk (karantina dulu)" testid="settings-qc-on-receipt"
                checked={pur.qc_on_receipt !== false} onChange={(v) => setSection("purchasing", "qc_on_receipt", v)} />
              <Toggle label="Wajib pilih supplier master saat buat PO" testid="settings-require-supplier"
                checked={!!pur.require_supplier_master} onChange={(v) => setSection("purchasing", "require_supplier_master", v)} />
            </div>
          </div>

          {/* Alokasi Stok (Sub-fase 1.7 — Allocation Policy R1/R2 configurable) */}
          <div className="section-card md:col-span-2">
            <div className="section-head"><div className="flex items-center gap-2"><Boxes size={15} className="text-[#6B219A]" /><h2>Alokasi Stok (Lot &amp; Lokasi)</h2></div></div>
            <div className="section-body grid gap-2.5 md:grid-cols-3">
              <Field label="Mode Alokasi">
                <KNSelect data-testid="settings-alloc-mode" className="field" value={alloc.mode || "auto"}
                  onValueChange={(v) => setSection("allocation", "mode", v)}
                  options={[
                    { value: "auto",     label: "Auto — sistem putuskan" },
                    { value: "assisted", label: "Assisted — usul + boleh edit" },
                    { value: "manual",   label: "Manual — user pilih" },
                  ]}
                />
              </Field>
              <Field label="Kebijakan Lot (R4)">
                <KNSelect data-testid="settings-alloc-lotmode" className="field" value={alloc.lot_mode || "prefer_single"}
                  onValueChange={(v) => setSection("allocation", "lot_mode", v)}
                  options={[
                    { value: "prefer_single",  label: "Prefer Single — utamakan 1 lot (konfirmasi bila campur)" },
                    { value: "strict_single",  label: "Strict Single — tidak boleh campur" },
                    { value: "allow_mixed",    label: "Allow Mixed — boleh campur tanpa konfirmasi" },
                  ]}
                />
              </Field>
              <Field label="Pemilihan Lot (R3)">
                <KNSelect data-testid="settings-alloc-lotselect" className="field" value={alloc.lot_selection || "fefo"}
                  onValueChange={(v) => setSection("allocation", "lot_selection", v)}
                  options={[
                    { value: "fefo",         label: "FEFO — lot tertua dulu" },
                    { value: "fifo",         label: "FIFO — masuk pertama dulu" },
                    { value: "smallest_fit", label: "Smallest Fit — habiskan lot kecil" },
                    { value: "largest_fit",  label: "Largest Fit — lot terbesar dulu" },
                  ]}
                />
              </Field>
              <Field label="Preferensi Lokasi">
                <KNSelect data-testid="settings-alloc-location" className="field" value={alloc.location_pref || "single_warehouse"}
                  onValueChange={(v) => setSection("allocation", "location_pref", v)}
                  options={[
                    { value: "single_warehouse", label: "Satu Gudang — minim split" },
                    { value: "nearest_customer", label: "Terdekat Customer" },
                    { value: "fewest_splits",    label: "Paling Sedikit Potongan" },
                  ]}
                />
              </Field>
              <Toggle label="Izinkan sumber inter-company (transfer)" testid="settings-alloc-intercompany"
                checked={alloc.allow_intercompany !== false} onChange={(v) => setSection("allocation", "allow_intercompany", v)} />
              <Toggle label="Izinkan pemenuhan parsial + backorder" testid="settings-alloc-partial"
                checked={alloc.allow_partial !== false} onChange={(v) => setSection("allocation", "allow_partial", v)} />
              <p className="md:col-span-3 text-[10.5px] text-[#8E8E93]">Owner (entitas penjual) selalu prioritas #1 (HARD). Kebijakan ini menjadi default sistem; dapat di-override per customer/order. Hasil alokasi selalu disertai penjelasan (clarity) di detail order.</p>
            </div>
          </div>

          <div className="md:col-span-2">
            <button data-testid="settings-save-button" onClick={saveSettings} disabled={saving} className="primary-button"><Save size={14} /> {saving ? "Menyimpan…" : "Simpan Pengaturan"}</button>
          </div>
        </div>
      )}

      {/* ── TERM PEMBAYARAN ── */}
      {sub === "terms" && (
        <div className="section-card">
          <div className="section-head"><div className="flex items-center gap-2"><CreditCard size={15} className="text-[#007AFF]" /><h2>Term Pembayaran</h2></div></div>
          <div className="section-body">
            <div className="grid gap-2 sm:grid-cols-6 mb-3 rounded-md border border-[#EFF0F2] bg-[#FAFBFC] p-2.5">
              <input data-testid="newterm-code" className="field" placeholder="Kode" value={newTerm.code} onChange={(e) => setNewTerm({ ...newTerm, code: e.target.value.toUpperCase() })} />
              <input data-testid="newterm-name" className="field sm:col-span-2" placeholder="Nama term" value={newTerm.name} onChange={(e) => setNewTerm({ ...newTerm, name: e.target.value })} />
              <KNSelect data-testid="newterm-type" className="field" value={newTerm.type}
                onValueChange={(v) => setNewTerm({ ...newTerm, type: v })}
                options={[{ value: "cash", label: "Tunai" }, { value: "credit", label: "Kredit" }, { value: "dp", label: "DP" }, { value: "installment", label: "Bertahap" }]}
              />
              <input type="number" data-testid="newterm-netdays" className="field tabular-nums" placeholder="NET hari" value={newTerm.net_days} onChange={(e) => setNewTerm({ ...newTerm, net_days: parseInt(e.target.value) || 0 })} />
              <button data-testid="newterm-add" onClick={addTerm} className="primary-button"><Plus size={13} /> Tambah</button>
            </div>
            <div className="overflow-x-auto rounded-md border border-[#EFF0F2]">
              <table className="w-full text-[11.5px]">
                <thead><tr className="bg-[#FAFBFC] text-[10px] uppercase text-[#6B6B73]">
                  <th className="text-left px-3 py-2">Kode</th><th className="text-left px-3 py-2">Nama</th><th className="text-left px-3 py-2">Tipe</th><th className="text-right px-3 py-2">NET</th><th className="text-right px-3 py-2">DP%</th><th className="px-3 py-2">Status</th><th></th>
                </tr></thead>
                <tbody className="divide-y divide-[#EFF0F2]">
                  {terms.map((t) => (
                    <tr key={t.id} data-testid={`term-row-${t.id}`} className={t.active ? "" : "opacity-50"}>
                      <td className="px-3 py-2 font-bold text-[#007AFF]">{t.code}</td>
                      <td className="px-3 py-2">{t.name}</td>
                      <td className="px-3 py-2 capitalize">{t.type}</td>
                      <td className="px-3 py-2 text-right tabular-nums">{t.net_days}h</td>
                      <td className="px-3 py-2 text-right tabular-nums">{t.dp_percent}%</td>
                      <td className="px-3 py-2 text-center"><span className={`rounded px-1.5 py-0.5 text-[10px] font-semibold ${t.active ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-500"}`}>{t.active ? "Aktif" : "Nonaktif"}</span></td>
                      <td className="px-3 py-2 text-right"><button data-testid={`term-toggle-${t.id}`} onClick={() => toggleTerm(t)} className="secondary-button text-[11px]">{t.active ? "Nonaktifkan" : "Aktifkan"}</button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* ── MATRIKS APPROVAL ── */}
      {sub === "approval" && (
        <div className="section-card">
          <div className="section-head"><div className="flex items-center gap-2"><ShieldCheck size={15} className="text-[#007AFF]" /><h2>Matriks Approval</h2></div></div>
          <div className="section-body">
            <div className="grid gap-2 sm:grid-cols-7 mb-3 rounded-md border border-[#EFF0F2] bg-[#FAFBFC] p-2.5">
              <KNSelect data-testid="newrule-doctype" className="field sm:col-span-2" value={newRule.doc_type}
                onValueChange={(v) => setNewRule({ ...newRule, doc_type: v })}
                options={DOC_TYPES.map(([v, l]) => ({ value: v, label: l }))}
              />
              <KNSelect data-testid="newrule-entity" className="field" value={newRule.entity_id}
                onValueChange={(v) => setNewRule({ ...newRule, entity_id: v })}
                options={[{ value: "all", label: "Semua Entitas" }, ...entities.map(en => ({ value: en.id, label: en.short_name || en.legal_name }))]}
              />
              <input type="number" data-testid="newrule-min" className="field tabular-nums" placeholder="Min" value={newRule.min_amount} onChange={(e) => setNewRule({ ...newRule, min_amount: parseFloat(e.target.value) || 0 })} />
              <input type="number" data-testid="newrule-max" className="field tabular-nums" placeholder="Max (kosong=∞)" value={newRule.max_amount} onChange={(e) => setNewRule({ ...newRule, max_amount: e.target.value })} />
              <KNSelect data-testid="newrule-role" className="field" value={newRule.required_role}
                onValueChange={(v) => setNewRule({ ...newRule, required_role: v })}
                options={[{ value: "", label: "Tanpa approval" }, { value: "manager", label: "Manager" }, { value: "admin", label: "Admin" }]}
              />
              <button data-testid="newrule-add" onClick={addRule} className="primary-button"><Plus size={13} /> Tambah</button>
            </div>
            {DOC_TYPES.map(([dt, dl]) => {
              const group = rules.filter((r) => r.doc_type === dt);
              if (group.length === 0) return null;
              return (
                <div key={dt} className="mb-3">
                  <p className="text-[11px] font-bold uppercase tracking-wide text-[#6B6B73] mb-1">{dl}</p>
                  <div className="overflow-x-auto rounded-md border border-[#EFF0F2]">
                    <table className="w-full text-[11.5px]">
                      <thead><tr className="bg-[#FAFBFC] text-[10px] uppercase text-[#6B6B73]">
                        <th className="text-left px-3 py-2">Entitas</th><th className="text-right px-3 py-2">Min</th><th className="text-right px-3 py-2">Max</th><th className="px-3 py-2">Butuh Approval</th><th></th>
                      </tr></thead>
                      <tbody className="divide-y divide-[#EFF0F2]">
                        {group.map((r) => (
                          <tr key={r.id} data-testid={`rule-row-${r.id}`}>
                            <td className="px-3 py-2">{r.entity_id === "all" ? "Semua" : (entities.find((e) => e.id === r.entity_id)?.short_name || r.entity_id)}</td>
                            <td className="px-3 py-2 text-right tabular-nums">{r.is_percent ? `${r.min_amount}%` : fmtRp(r.min_amount)}</td>
                            <td className="px-3 py-2 text-right tabular-nums">{r.max_amount == null ? "∞" : (r.is_percent ? `${r.max_amount}%` : fmtRp(r.max_amount))}</td>
                            <td className="px-3 py-2 text-center">{r.required_role ? <span className="rounded px-1.5 py-0.5 text-[10px] font-semibold bg-orange-100 text-orange-700 capitalize">{r.required_role}</span> : <span className="text-[#8E8E93]">—</span>}</td>
                            <td className="px-3 py-2 text-right"><button data-testid={`rule-del-${r.id}`} onClick={() => delRule(r.id)} className="danger-button text-[11px]"><Trash2 size={12} /></button></td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

function Field({ label, children }) {
  return (
    <label className="block">
      <span className="block text-[10.5px] font-semibold text-[#6B6B73] mb-1">{label}</span>
      {children}
    </label>
  );
}

function Toggle({ label, checked, onChange, testid }) {
  return (
    <button type="button" data-testid={testid} onClick={() => onChange(!checked)}
      className="flex items-center justify-between gap-3 rounded-md border border-[#EFF0F2] px-2.5 py-2 text-left hover:bg-[#FAFBFC]">
      <span className="text-[11.5px] font-medium">{label}</span>
      <span className={`relative h-5 w-9 shrink-0 rounded-full transition-colors ${checked ? "bg-[#34C759]" : "bg-[#D1D1D6]"}`}>
        <span className={`absolute top-0.5 h-4 w-4 rounded-full bg-white shadow transition-all ${checked ? "left-[18px]" : "left-0.5"}`} />
      </span>
    </button>
  );
}
