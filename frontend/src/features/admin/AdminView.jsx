import { useState, useEffect, useCallback } from "react";
import {
  RefreshCw, Settings, Plus, XCircle, Save, ShieldCheck, UserCog,
  Check, AlertTriangle, ChevronUp, ChevronDown,
} from "lucide-react";
import SettingsPanel from "./SettingsPanel";
import CategoryManager from "./CategoryManager";
import KNSelect from "../../components/KNSelect";
import axios, { API } from "../../services/apiClient";

export default function AdminView({
  data,
  users,
  uoms,
  templates,
  entities,
  permissions,
  previewHtml,
  auditLogs,
  auditFilters,
  setAuditFilters,
  onAdminCreate,
  onAdminPatch,
  onAdminDelete,
  onImportMaster,
  onExportMaster,
  onUpdatePermissions,
  onPreviewTemplate,
  onRefreshAudit,
  onShowDetail,
  onSeedDemo,
}) {
  const [tab, setTab] = useState("products");
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [categories, setCategories] = useState([]);
  const loadCategories = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/product-categories`);
      setCategories(Array.isArray(res.data) ? res.data : []);
    } catch (_) { /* non-blocking: form produk fallback ke daftar baku */ }
  }, []);
  useEffect(() => { loadCategories(); }, [loadCategories]);
  // Opsi dropdown kategori (aktif saja) untuk form produk; fallback 7 kategori baku.
  const categoryOptions = (categories.length
    ? categories.filter((c) => c.status === "active")
    : ["Batik", "Tenun", "Lurik", "Songket", "Ulos", "Jumputan", "Endek"].map((n) => ({ name: n })))
    .map((c) => ({ value: c.name, label: c.name }));
  const [product, setProduct] = useState({ sku: "", name: "", category: "Batik", variant: "Regular", color: "", motif: "", grade: "A", supplier: "", base_unit: "meter", price: 0, harga_pokok: 0, gramasi: 0, lebar: 0, image: "", description: "", uom_conversions: [] });
  const [editingProductId, setEditingProductId] = useState(null);
  const [productError, setProductError] = useState("");
  const [customer, setCustomer] = useState({ name: "", pic_name: "", phone: "", city: "Jakarta", address: "", npwp: "", credit_limit: 0, sales_pic: "" });
  const [entity, setEntity] = useState({ legal_name: "", short_name: "", type: "PT", npwp: "", address: "", city: "Bandung", default_tax_mode: "ppn", doc_prefix: "", logo_url: "" });
  const [warehouse, setWarehouse] = useState({ code: "", name: "", city: "Jakarta", bin_code: "A1-01", bin_capacity: 1000, lat: "", lng: "" });
  const [uom, setUom] = useState({ code: "", name: "", base_type: "length", precision: 2 });
  const [template, setTemplate] = useState({ document_type: "surat_jalan", name: "", header: "Kain Nusantara", footer: "", columns: "SKU,Nama Barang,Qty,Unit", logo_url: "", paper_size: "A4", orientation: "portrait", margin_mm: 12, signature_left: "Dibuat Oleh", signature_right: "Disetujui Oleh", section_order: ["header", "customer", "items", "allocation", "signature", "footer"] });
  const [userForm, setUserForm] = useState({ name: "", email: "", role: "sales", password: "demo12345" });
  const [importFile, setImportFile] = useState(null);
  const [importPreview, setImportPreview] = useState(null);
  const [importLoading, setImportLoading] = useState(false);

  // Sub-fase 1.13 — helper form produk (uom_conversions + create/edit)
  const emptyProduct = { sku: "", name: "", category: "Batik", variant: "Regular", color: "", motif: "", grade: "A", supplier: "", base_unit: "meter", price: 0, harga_pokok: 0, gramasi: 0, lebar: 0, image: "", description: "", uom_conversions: [] };
  const resetProductForm = () => { setProduct(emptyProduct); setEditingProductId(null); setProductError(""); };
  const updateConv = (idx, key, val) => setProduct({
    ...product,
    uom_conversions: (product.uom_conversions || []).map((c, i) => i === idx ? { ...c, [key]: val } : c),
  });
  const addConv = () => setProduct({ ...product, uom_conversions: [...(product.uom_conversions || []), { from_unit: "", to_unit: product.base_unit || "meter", factor: 0 }] });
  const removeConv = (idx) => setProduct({ ...product, uom_conversions: (product.uom_conversions || []).filter((_, i) => i !== idx) });
  // Sub-fase 1.13 — validasi konversi: unit wajib diisi, factor > 0, from != to.
  const validateConversions = () => {
    const rows = product.uom_conversions || [];
    for (let i = 0; i < rows.length; i++) {
      const from = String(rows[i].from_unit || "").trim();
      const to = String(rows[i].to_unit || "").trim();
      const factor = Number(rows[i].factor);
      if (!from || !to) return `Konversi #${i + 1}: unit "Dari" dan "Ke" wajib diisi.`;
      if (from.toLowerCase() === to.toLowerCase()) return `Konversi #${i + 1}: unit "Dari" dan "Ke" tidak boleh sama.`;
      if (!(factor > 0)) return `Konversi #${i + 1}: faktor harus lebih besar dari 0.`;
    }
    return "";
  };
  const saveProduct = async () => {
    const err = validateConversions();
    if (err) { setProductError(err); return; }
    setProductError("");
    if (editingProductId) {
      await onAdminPatch("products", editingProductId, product);
    } else {
      await onAdminCreate("products", product);
    }
    resetProductForm();
  };
  // Sub-fase 1.13 — catch-weight kg per meter (transparansi di form).
  const kgPerMeter = (Number(product.gramasi) || 0) * (Number(product.lebar) || 0) / 1000;
  const loadProductForEdit = (row) => {
    setProduct({
      sku: row.sku || "", name: row.name || "", category: row.category || "", variant: row.variant || "",
      color: row.color || "", motif: row.motif || "", grade: row.grade || "", supplier: row.supplier || "",
      base_unit: row.base_unit || "meter", price: Number(row.price || 0), harga_pokok: Number(row.harga_pokok || 0),
      gramasi: Number(row.gramasi || 0), lebar: Number(row.lebar || 0), image: row.image || "", description: row.description || "", uom_conversions: row.uom_conversions || [],
    });
    setEditingProductId(row.id);
    setShowCreateForm(true);  // F3 — buka form saat Edit (sebelumnya tetap tertutup)
  };

  const tabs = [
    ["entities", "Entities"], ["products", "Product"], ["categories", "Kategori"], ["customers", "Customer"], ["warehouses", "Warehouse"], ["uoms", "UOM"], ["settings", "Pengaturan"], ["templates", "Templates"], ["permissions", "Permissions"], ["audit", "Audit"], ["users", "Users"],
  ];
  const currentResource = tab === "templates" ? "templates" : tab;

  const handleDryRunImport = async () => {
    if (!importFile) return;
    setImportLoading(true);
    const result = await onImportMaster(currentResource, importFile, true);
    setImportPreview(result);
    setImportLoading(false);
  };

  const moveSection = (section, direction) => {
    const next = [...template.section_order];
    const index = next.indexOf(section);
    const target = index + direction;
    if (target < 0 || target >= next.length) return;
    [next[index], next[target]] = [next[target], next[index]];
    setTemplate({ ...template, section_order: next });
  };

  return (
    <div data-testid="admin-view">
      <section className="section-card mb-3">
        <div className="section-head">
          <div className="flex items-center gap-3 min-w-0">
            <span className="kicker">Admin Master Data</span>
            <h2>CRUD product · customer · warehouse · UOM · template · user</h2>
          </div>
          {onSeedDemo && (
            <button
              data-testid="admin-seed-demo-button"
              onClick={onSeedDemo}
              className="ml-auto secondary-button text-orange-700 border-orange-200 hover:bg-orange-50"
              title="Reset database & isi ulang dengan demo data (DESTRUCTIVE)"
            >
              <RefreshCw size={13} /> Reset Demo Data
            </button>
          )}
        </div>
        <div className="flex flex-wrap gap-1.5 px-3 pb-3">
          {tabs.map(([id, label]) => <button key={id} data-testid={`admin-tab-${id}-button`} className={`nav-button ${tab === id ? "active" : ""}`} onClick={() => setTab(id)}><Settings size={13} /> {label}</button>)}
        </div>
      </section>
      {tab === "settings" && <SettingsPanel entities={entities} />}
      {tab === "categories" && <CategoryManager onChanged={loadCategories} />}
      {tab !== "settings" && tab !== "categories" && (
      <section className="grid gap-3 lg:grid-cols-[360px_1fr]">
        {!showCreateForm && (
          <button
            data-testid="toggle-admin-create-form-button"
            className="secondary-button"
            onClick={() => setShowCreateForm(true)}
          >
            <Plus size={14} /> Tampilkan Form Create
          </button>
        )}
        {showCreateForm && (
        <div className="section-card">
          <div className="section-head">
            <h2>Create</h2>
            <button
              data-testid="hide-admin-create-form-button"
              className="icon-button ml-auto"
              onClick={() => setShowCreateForm(false)}
            >
              <XCircle size={14} />
            </button>
          </div>
          <div className="section-body">
          {!["users", "permissions", "audit", "entities"].includes(tab) && <div data-testid="admin-import-export-panel" className="mb-3 grid gap-2 rounded-md border border-[#EFF0F2] bg-[#FAFBFC] p-2.5">
            <p className="text-[11px] font-bold uppercase tracking-wide text-[#6B6B73]">Import / Export {currentResource}</p>
            <input data-testid="admin-import-file-input" className="field" type="file" accept=".csv,.xlsx" onChange={(e) => setImportFile(e.target.files?.[0] || null)} />
            <div className="flex flex-wrap gap-1.5">
              <button data-testid="admin-dry-run-button" className="secondary-button" disabled={importLoading} onClick={handleDryRunImport}>{importLoading ? "..." : "Preview Dry-Run"}</button>
              <button data-testid="admin-import-button" className="secondary-button" onClick={() => { onImportMaster(currentResource, importFile, false); setImportPreview(null); }}>Import</button>
              <button data-testid="admin-export-csv-button" className="secondary-button" onClick={() => onExportMaster(currentResource, "csv")}>Export CSV</button>
            </div>
            {importPreview && (
              <div data-testid="import-preview-result" className="rounded-md border border-[#EFF0F2] bg-white p-2 text-[11.5px]">
                <p className="font-bold mb-1">Preview: {importPreview.total} baris</p>
                <p className="text-green-700 inline-flex items-center gap-1"><Check size={12} /> Akan dibuat: {importPreview.created}</p>
                <p className="text-blue-700">~ Akan diupdate: {importPreview.updated}</p>
                {(importPreview.errors || []).length > 0 && (
                  <div className="mt-1 max-h-24 overflow-auto">
                    <p className="text-red-700 font-bold inline-flex items-center gap-1"><AlertTriangle size={12} /> {importPreview.errors.length} error:</p>
                    {(importPreview.errors || []).map((e, i) => <p key={i} className="text-red-600 text-[10.5px]">{e}</p>)}
                  </div>
                )}
                <button data-testid="confirm-import-button" className="mt-1 primary-button text-[11px]" onClick={() => { onImportMaster(currentResource, importFile, false); setImportPreview(null); }}>Konfirmasi Import</button>
              </div>
            )}
          </div>}
          {tab === "entities" && <div className="grid gap-2">
            <p className="text-[11px] text-[#6B6B73]">Entitas legal grup (PT/CV). Data transaksi (SO/PO/Invoice) akan di-scope per entitas via Entity Switcher.</p>
            {[["legal_name", "Nama legal (PT Kain Suka Cita)"], ["short_name", "Nama singkat (KSC)"], ["npwp", "NPWP"], ["address", "Alamat"], ["city", "Kota"], ["doc_prefix", "Prefix dokumen (KSC)"], ["logo_url", "Logo URL (opsional)"]].map(([key, ph]) => <input key={key} data-testid={`admin-entity-${key}-input`} className="field" placeholder={ph} value={entity[key]} onChange={(e) => setEntity({ ...entity, [key]: e.target.value })} />)}
            <div className="grid grid-cols-2 gap-2">
              <KNSelect data-testid="admin-entity-type-input" className="field" value={entity.type}
                onValueChange={v => setEntity({ ...entity, type: v })}
                options={[{ value: "PT", label: "PT" }, { value: "CV", label: "CV" }]}
              />
              <KNSelect data-testid="admin-entity-tax-input" className="field" value={entity.default_tax_mode}
                onValueChange={v => setEntity({ ...entity, default_tax_mode: v })}
                options={[{ value: "ppn", label: "PPN" }, { value: "non_ppn", label: "Non-PPN" }]}
              />
            </div>
            <button data-testid="admin-create-entity-button" className="primary-button" onClick={() => onAdminCreate("entities", entity)}><Save size={14} /> Simpan Entitas</button>
          </div>}
          {tab === "products" && <div className="grid gap-2">
            {[["sku", "SKU"], ["name", "Nama produk"], ["category", "Kategori"], ["variant", "Varian"], ["color", "Warna"], ["motif", "Motif"], ["grade", "Grade"], ["supplier", "Supplier"], ["base_unit", "Satuan Dasar"], ["price", "Harga jual"], ["harga_pokok", "Harga pokok (HPP)"], ["gramasi", "Gramasi (gsm)"], ["lebar", "Lebar (meter)"]].map(([key, ph]) => { if (key === "category") { return <KNSelect key={key} data-testid="admin-product-category-input" className="field" value={product.category ?? ""} placeholder="Pilih kategori" onValueChange={(v) => setProduct({ ...product, category: v })} options={categoryOptions} />; } if (key === "base_unit") { return <KNSelect key={key} data-testid="admin-product-base_unit-input" className="field" value={product.base_unit ?? "meter"} placeholder="Satuan Dasar" onValueChange={(v) => setProduct({ ...product, base_unit: v })} options={[{ value: "meter", label: "Meter" }, { value: "yard", label: "Yard" }, { value: "cm", label: "Cm" }, { value: "inch", label: "Inch" }, { value: "kg", label: "Kg (catch-weight)" }, { value: "pcs", label: "Pcs" }, { value: "lembar", label: "Lembar" }]} />; } const isNum = ["price", "harga_pokok", "gramasi", "lebar"].includes(key); return <input key={key} data-testid={`admin-product-${key}-input`} className="field" type={isNum ? "number" : "text"} placeholder={ph} value={product[key] ?? ""} onChange={(e) => setProduct({ ...product, [key]: isNum ? Number(e.target.value) : e.target.value })} />; })}
            <p className="-mt-0.5 text-[11px] text-[#6B6B73]"><b>Satuan Dasar</b>: 1 produk = 1 satuan untuk semua roll-nya. Tiap roll beda <b>panjang</b>, bukan beda satuan. POS menjual per satuan dasar (tampil "X roll / Y {product.base_unit || "meter"}").</p>
            {/* Sub-fase 1.13 — transparansi catch-weight kg */}
            {kgPerMeter > 0 ? (
              <p data-testid="admin-product-kgm-info" className="-mt-0.5 text-[11px] text-[#3A7D44]">
                Catch-weight aktif: 1 {product.base_unit || "meter"} ≈ {kgPerMeter.toFixed(3)} kg
                <span className="text-[#8E8E93]"> (kg/m = gramasi × lebar ÷ 1000) · unit "kg" tersedia di penjualan</span>
              </p>
            ) : (
              <p data-testid="admin-product-kgm-info" className="-mt-0.5 text-[11px] text-[#8E8E93]">
                Isi Gramasi (gsm) & Lebar (meter) untuk mengaktifkan penjualan per "kg" (catch-weight).
              </p>
            )}
            {/* F3 — Gambar per-varian + Deskripsi produk */}
            <div data-testid="admin-product-media" className="space-y-2 rounded-md border border-[#EFF0F2] bg-[#FAFBFC] p-2.5">
              <p className="text-[11px] font-bold uppercase tracking-wide text-[#8E8E93]">Gambar Varian &amp; Deskripsi</p>
              <div className="flex gap-2.5">
                {product.image ? (
                  <img data-testid="admin-product-image-preview" src={product.image} alt="preview varian" className="h-16 w-16 shrink-0 rounded-md border border-[#EFF0F2] object-cover" />
                ) : (
                  <div className="flex h-16 w-16 shrink-0 items-center justify-center rounded-md border border-dashed border-[#D9DBE0] text-[10px] text-[#B0B2BA]">Tanpa gambar</div>
                )}
                <input data-testid="admin-product-image-input" className="field flex-1" placeholder="URL gambar varian (https://...)" value={product.image ?? ""} onChange={(e) => setProduct({ ...product, image: e.target.value })} />
              </div>
              <p className="text-[10.5px] text-[#8E8E93]">Tiap varian boleh punya gambar berbeda — gambar di popup detail berubah saat ganti varian.</p>
              <textarea data-testid="admin-product-description-input" className="field min-h-[70px] resize-y" placeholder="Deskripsi produk (mis. komposisi, motif, perawatan) — tampil di popup detail POS" value={product.description ?? ""} onChange={(e) => setProduct({ ...product, description: e.target.value })} />
            </div>
            {/* Sub-fase 1.13 — editor konversi UOM per produk */}
            <div data-testid="admin-product-uom-editor" className="rounded-md border border-[#EFF0F2] bg-[#FAFBFC] p-2.5">
              <div className="flex items-center justify-between">
                <p className="text-[11px] font-bold uppercase tracking-wide text-[#8E8E93]">Konversi UOM (mis. roll → meter)</p>
                <button type="button" data-testid="admin-product-add-conv-button" className="secondary-button" onClick={addConv}><Plus size={13} /> Konversi</button>
              </div>
              {(product.uom_conversions || []).length === 0 && (
                <p className="mt-1 text-[11px] text-[#6B6B73]">Belum ada konversi variabel. Length (yard/cm/inch) otomatis; kg otomatis bila gramasi & lebar terisi.</p>
              )}
              {(product.uom_conversions || []).map((c, i) => (
                <div key={i} className="mt-2 grid grid-cols-[1fr_1fr_1fr_30px] items-center gap-1.5">
                  <input data-testid={`admin-product-conv-from-${i}`} className="field" placeholder="Dari (roll)" value={c.from_unit} onChange={(e) => updateConv(i, "from_unit", e.target.value)} />
                  <input data-testid={`admin-product-conv-to-${i}`} className="field" placeholder="Ke (meter)" value={c.to_unit} onChange={(e) => updateConv(i, "to_unit", e.target.value)} />
                  <input data-testid={`admin-product-conv-factor-${i}`} className="field" type="number" placeholder="Faktor (50)" value={c.factor} onChange={(e) => updateConv(i, "factor", Number(e.target.value))} />
                  <button type="button" data-testid={`admin-product-conv-remove-${i}`} className="icon-button" onClick={() => removeConv(i)} aria-label="Hapus konversi"><XCircle size={14} /></button>
                </div>
              ))}
            </div>
            {productError && (
              <p data-testid="admin-product-error" className="text-[12px] font-semibold text-[#D14343]">{productError}</p>
            )}
            <div className="flex gap-2">
              <button data-testid="admin-create-product-button" className="primary-button" onClick={saveProduct}><Save size={14} /> {editingProductId ? "Update Product" : "Simpan Product"}</button>
              {editingProductId && <button data-testid="admin-cancel-edit-product-button" className="secondary-button" onClick={resetProductForm}>Batal Edit</button>}
            </div>
          </div>}
          {tab === "customers" && <div className="grid gap-2">
            {[["name", "Nama customer"], ["pic_name", "PIC"], ["phone", "Phone"], ["city", "Kota"], ["address", "Alamat"], ["npwp", "NPWP"], ["sales_pic", "Sales PIC"]].map(([key, ph]) => <input key={key} data-testid={`admin-customer-${key}-input`} className="field" placeholder={ph} value={customer[key]} onChange={(e) => setCustomer({ ...customer, [key]: e.target.value })} />)}
            <input data-testid="admin-customer-credit_limit-input" className="field" type="number" placeholder="Credit limit (Rp)" value={customer.credit_limit} onChange={(e) => setCustomer({ ...customer, credit_limit: Number(e.target.value) })} />
            <button data-testid="admin-create-customer-button" className="primary-button" onClick={() => onAdminCreate("customers", customer)}><Save size={14} /> Simpan Customer</button>
          </div>}
          {tab === "warehouses" && <div className="grid gap-2">
            {[["code", "Kode gudang"], ["name", "Nama gudang"], ["city", "Kota"], ["bin_code", "Kode bin"], ["bin_capacity", "Kapasitas bin"]].map(([key, ph]) => <input key={key} data-testid={`admin-warehouse-${key}-input`} className="field" placeholder={ph} value={warehouse[key]} onChange={(e) => setWarehouse({ ...warehouse, [key]: key === "bin_capacity" ? Number(e.target.value) : e.target.value })} />)}
            <div className="grid grid-cols-2 gap-2">
              <input data-testid="admin-warehouse-lat-input" className="field" type="number" step="0.0001" placeholder="Latitude (opsional)" value={warehouse.lat} onChange={e => setWarehouse({...warehouse, lat: e.target.value ? Number(e.target.value) : ""})} />
              <input data-testid="admin-warehouse-lng-input" className="field" type="number" step="0.0001" placeholder="Longitude (opsional)" value={warehouse.lng} onChange={e => setWarehouse({...warehouse, lng: e.target.value ? Number(e.target.value) : ""})} />
            </div>
            <p className="text-[10.5px] text-[#8E8E93]">Koordinat digunakan untuk alokasi gudang terdekat.</p>
            <button data-testid="admin-create-warehouse-button" className="primary-button" onClick={() => onAdminCreate("warehouses", {...warehouse, lat: warehouse.lat || null, lng: warehouse.lng || null})}><Save size={14} /> Simpan Warehouse</button>
          </div>}
          {tab === "uoms" && <div className="grid gap-2">
            {[["code", "Kode UOM"], ["name", "Nama UOM"], ["base_type", "Base type"], ["precision", "Precision"]].map(([key, ph]) => <input key={key} data-testid={`admin-uom-${key}-input`} className="field" placeholder={ph} value={uom[key]} onChange={(e) => setUom({ ...uom, [key]: key === "precision" ? Number(e.target.value) : e.target.value })} />)}
            <button data-testid="admin-create-uom-button" className="primary-button" onClick={() => onAdminCreate("uoms", uom)}><Save size={14} /> Simpan UOM</button>
          </div>}
          {tab === "templates" && <div className="grid gap-2">
            {[["document_type", "Tipe dokumen"], ["name", "Nama template"], ["header", "Header"], ["footer", "Footer"], ["columns", "Kolom dipisah koma"], ["logo_url", "Logo URL"], ["paper_size", "Ukuran kertas"], ["orientation", "Orientasi"], ["margin_mm", "Margin mm"], ["signature_left", "TTD kiri"], ["signature_right", "TTD kanan"]].map(([key, ph]) => <input key={key} data-testid={`admin-template-${key}-input`} className="field" placeholder={ph} value={template[key]} onChange={(e) => setTemplate({ ...template, [key]: key === "margin_mm" ? Number(e.target.value) : e.target.value })} />)}
            <div data-testid="template-section-order-editor" className="rounded-md border border-[#EFF0F2] bg-[#FAFBFC] p-2.5">
              <p className="mb-1.5 text-[11px] font-bold uppercase tracking-wide text-[#6B6B73]">Urutan section</p>
              {template.section_order.map((section) => <div key={section} data-testid={`template-section-${section}`} draggable className="mb-1.5 flex items-center justify-between rounded-md bg-white px-2 py-1 text-[12px] font-semibold border border-[#EFF0F2]"><span>{section}</span><span className="flex gap-1"><button data-testid={`template-section-${section}-up-button`} className="secondary-button" onClick={() => moveSection(section, -1)}><ChevronUp size={13} /></button><button data-testid={`template-section-${section}-down-button`} className="secondary-button" onClick={() => moveSection(section, 1)}><ChevronDown size={13} /></button></span></div>)}
            </div>
            <button data-testid="admin-create-template-button" className="primary-button" onClick={() => onAdminCreate("document-templates", { ...template, columns: template.columns.split(",").map((c) => c.trim()).filter(Boolean) })}><Save size={14} /> Simpan Template</button>
          </div>}
          {tab === "permissions" && <div data-testid="permission-matrix-editor" className="grid gap-2">
            <p className="text-[12px] text-[#3C3C43]">Klik checkbox untuk ubah permission. Perubahan tersimpan otomatis.</p>
            <button data-testid="save-permissions-button" className="primary-button" onClick={() => onUpdatePermissions(permissions.matrix)}><ShieldCheck size={14} /> Simpan ke Database</button>
            <p className="text-[10.5px] text-[#8E8E93]">Semua perubahan di-preview dulu, klik Simpan untuk persisten.</p>
          </div>}
          {tab === "audit" && <div data-testid="audit-filter-panel" className="grid gap-2">
            <input data-testid="audit-actor-filter-input" className="field" placeholder="Filter actor" value={auditFilters.actor} onChange={(e) => setAuditFilters({ ...auditFilters, actor: e.target.value })} />
            <input data-testid="audit-module-filter-input" className="field" placeholder="Filter module/entity" value={auditFilters.module} onChange={(e) => setAuditFilters({ ...auditFilters, module: e.target.value })} />
            <input data-testid="audit-action-filter-input" className="field" placeholder="Filter action" value={auditFilters.action} onChange={(e) => setAuditFilters({ ...auditFilters, action: e.target.value })} />
            <div className="grid grid-cols-2 gap-2">
              <input data-testid="audit-date-from-input" className="field" type="date" value={auditFilters.date_from} onChange={(e) => setAuditFilters({ ...auditFilters, date_from: e.target.value })} />
              <input data-testid="audit-date-to-input" className="field" type="date" value={auditFilters.date_to} onChange={(e) => setAuditFilters({ ...auditFilters, date_to: e.target.value })} />
            </div>
            <button data-testid="refresh-audit-button" className="primary-button" onClick={onRefreshAudit}><RefreshCw size={14} /> Refresh Audit</button>
          </div>}
          {tab === "users" && <div className="grid gap-2">
            {[["name", "Nama user"], ["email", "Email"], ["role", "Role"], ["password", "Password"]].map(([key, ph]) => <input key={key} data-testid={`admin-user-${key}-input`} className="field" placeholder={ph} value={userForm[key]} onChange={(e) => setUserForm({ ...userForm, [key]: e.target.value })} />)}
            <button data-testid="admin-create-user-button" className="primary-button" onClick={() => onAdminCreate("users", userForm)}><UserCog size={14} /> Buat User</button>
          </div>}
          </div>
        </div>
        )}
        <div className="section-card">
          <div className="section-head"><h2>Records</h2></div>
          <div className="section-body">
          {tab === "permissions" && <div data-testid="permission-matrix-records" className="grid gap-4 overflow-auto">
            {Object.entries(permissions.matrix || {}).map(([role, modules]) => (
              <div key={role} className="rounded-xl border border-[#EFF0F2] bg-[#FAFBFC] p-3">
                <h4 className="text-[13px] font-bold capitalize mb-2">{role}</h4>
                <div className="grid gap-2">
                  {Object.entries(modules).map(([module, actions]) => {
                    const ALL_ACTIONS = {
                      product: ["view", "create", "update", "delete", "import", "export"],
                      customer: ["view", "create", "update", "delete", "import", "export"],
                      warehouse: ["view", "create", "update", "delete", "import", "export"],
                      uom: ["view", "create", "update", "delete", "import", "export"],
                      template: ["view", "create", "update", "delete", "print", "import", "export"],
                      order: ["view", "create", "update", "delete", "approve", "confirm", "print"],
                      wms: ["view", "create", "update", "scan", "dispatch", "print"],
                      document: ["view", "create", "print"],
                      user: ["view", "create", "update", "delete"],
                      permission: ["view", "update"],
                      inventory: ["view", "create", "update", "cycle_count", "approve_count"],
                      reports: ["view", "export"],
                    };
                    const availableActions = ALL_ACTIONS[module] || Array.from(new Set([...Object.values(ALL_ACTIONS).flat()]));
                    return (
                      <div key={module} data-testid={`permission-row-${role}-${module}`} className="rounded-md border border-[#EFF0F2] bg-white p-2">
                        <p className="text-[11.5px] font-bold capitalize">{module}</p>
                        <div className="mt-1.5 flex flex-wrap gap-1.5">
                          {availableActions.map((action) => (
                            <label key={action} data-testid={`permission-cell-${role}-${module}-${action}`}
                              className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10.5px] font-semibold border cursor-pointer transition-colors ${
                                (actions || []).includes(action) ? "bg-[#007AFF] text-white border-[#007AFF]" : "bg-white text-[#6B6B73] border-[#EFF0F2] hover:border-[#007AFF]"
                              }`}>
                              <input type="checkbox" className="sr-only" checked={(actions || []).includes(action)}
                                onChange={(e) => {
                                  const next = JSON.parse(JSON.stringify(permissions.matrix));
                                  const current = new Set(next[role]?.[module] || []);
                                  if (e.target.checked) current.add(action); else current.delete(action);
                                  next[role] = next[role] || {};
                                  next[role][module] = Array.from(current);
                                  onUpdatePermissions(next, false);
                                }} />
                              {action}
                            </label>
                          ))}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>}
          {tab === "audit" && <div data-testid="audit-history-records" className="grid gap-2">
            {(auditLogs || []).map((log) => <button data-testid={`audit-row-${log.id}`} key={log.id} className="rounded-md border border-[#EFF0F2] bg-[#FAFBFC] interactive-card p-2.5 text-left" onClick={() => onShowDetail({ title: log.action, body: `Audit by ${log.actor} on ${log.entity_type}.`, facts: [{ label: "Entity", value: log.entity_id }, { label: "Time", value: new Date(log.timestamp).toLocaleString("id-ID") }], target: "admin", cta: "Tetap di Audit" })}><div className="flex flex-wrap items-center justify-between gap-2"><p className="text-[12.5px] font-semibold">{log.action}</p><p className="text-[10.5px] font-semibold text-[#0058CC]">{new Date(log.timestamp).toLocaleString("id-ID")}</p></div><p className="mt-0.5 text-[11.5px] text-[#3C3C43]">{log.actor} • {log.entity_type} • {log.entity_id}</p><p className="mt-1 line-clamp-2 text-[10.5px] text-[#3C3C43]">{JSON.stringify(log.after).slice(0, 240)}</p></button>)}
          </div>}
          {!['permissions', 'audit'].includes(tab) && <>
          <div className="grid gap-2">
            {(tab === "products" ? data.products : tab === "customers" ? data.customers : tab === "warehouses" ? data.warehouses : tab === "uoms" ? uoms : tab === "templates" ? templates : tab === "entities" ? (entities || []) : users).length === 0 && (
              <div data-testid={`admin-records-empty-${tab}`} className="px-3 py-8 text-center text-[12px] text-[#6B6B73]">Belum ada data {tab}.</div>
            )}
            {(tab === "products" ? data.products : tab === "customers" ? data.customers : tab === "warehouses" ? data.warehouses : tab === "uoms" ? uoms : tab === "templates" ? templates : tab === "entities" ? (entities || []) : users).map((row) => (
              <div data-testid={`admin-record-${tab}-${row.id}`} key={row.id} role="button" tabIndex={0} className="rounded-md border border-[#EFF0F2] bg-[#FAFBFC] interactive-card flex flex-col gap-2 p-2.5 md:flex-row md:items-center md:justify-between" onClick={() => onShowDetail({ title: row.name || row.legal_name || row.code || row.email, body: `Record ${tab} ini dapat diupdate, dinonaktifkan, atau diexport dari Admin CRUD.`, facts: [{ label: "Module", value: tab }, { label: "Status", value: row.status || (row.active === false ? "inactive" : "active") }], target: "admin", cta: "Tetap di Admin" })}>
                <div className="min-w-0">
                  <p data-testid={`admin-record-title-${row.id}`} className="text-[12.5px] font-semibold truncate">{row.name || row.legal_name || row.code || row.email}</p>
                  <p data-testid={`admin-record-meta-${row.id}`} className="text-[11px] text-[#3C3C43] truncate">{row.sku || row.code || row.document_type || row.role || row.short_name || row.city} • {row.status || (row.active === false ? "inactive" : "active")}</p>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {tab === "products" && <button data-testid={`admin-edit-products-${row.id}-button`} className="secondary-button" onClick={(e) => { e.stopPropagation(); loadProductForEdit(row); window.scrollTo({ top: 0, behavior: "smooth" }); }}>Edit</button>}
                  {tab !== "products" && <button data-testid={`admin-update-${tab}-${row.id}-button`} className="secondary-button" onClick={(e) => { e.stopPropagation(); onAdminPatch(tab === "templates" ? "document-templates" : tab, row.id, tab === "warehouses" ? { city: row.city } : tab === "uoms" ? { precision: row.precision } : tab === "users" ? { status: row.status || "active" } : { status: row.status || "active" }); }}>Update</button>}
                  {tab === "templates" && data.orders?.[0] && <button data-testid={`admin-preview-template-${row.id}-button`} className="secondary-button" onClick={(e) => { e.stopPropagation(); onPreviewTemplate(row.id, data.orders[0].id); }}>Preview</button>}
                  <button data-testid={`admin-delete-${tab}-${row.id}-button`} className="danger-button" onClick={(e) => { e.stopPropagation(); onAdminDelete(tab === "templates" ? "document-templates" : tab, row.id); }}>Deactivate</button>
                </div>
              </div>
            ))}
          </div>
          {tab === "templates" && previewHtml && <iframe data-testid="template-live-preview-frame" title="Template Preview" className="mt-4 h-[480px] w-full rounded-md border border-[#EFF0F2] bg-white" srcDoc={previewHtml} />}
          </>}
          </div>
        </div>
      </section>
      )}
    </div>
  );
}
