import { useEffect, useState } from "react";
import { Plus, Package } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import { formatCurrency } from "../../utils/formatters";
import { getStatusBadge } from "./po/poUtils";
import POCreateForm from "./po/POCreateForm";
import PODetailPanel from "./po/PODetailPanel";
import POAmendModal from "./po/POAmendModal";
import ConfirmModal from "../../components/ConfirmModal";
import ErrorNotice from "../../components/ErrorNotice";

/**
 * PurchaseOrderManagement
 *
 * Manage Purchase Orders untuk inbound receiving workflow.
 * Create PO → Auto-create inbound tasks → Staff scan & receive.
 *
 * Sub-komponen (colocated di po/):
 *   - POCreateForm    — form buat PO baru
 *   - PODetailPanel   — panel detail PO dipilih
 *   - poUtils         — getStatusBadge helper
 */
export default function PurchaseOrderManagement({ user, onApprovePO, focusDoc, onClearFocus, onOpenDocument }) {
  const [pos, setPos] = useState([]);
  const [products, setProducts] = useState([]);
  const [warehouses, setWarehouses] = useState([]);
  const [suppliers, setSuppliers] = useState([]);
  const [loading, setLoading] = useState(false);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [selectedPO, setSelectedPO] = useState(null);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [creating, setCreating] = useState(false);
  const [confirm, setConfirm] = useState(null); // { title, message, confirmLabel, danger, withReason, onConfirm }
  const [amendPO, setAmendPO] = useState(null);  // Phase 7.2 — PO yang sedang direvisi
  const [amending, setAmending] = useState(false);

  const emptyForm = {
    supplier_id: "", supplier_name: "", supplier_contact: "", warehouse_id: "",
    items: [], expected_delivery_date: "", notes: "",
    order_discount_percent: 0, tax_mode: "",   // P0-1 — diskon order + mode PPN Masukan
    created_by: user?.name || "Admin",
  };
  const [formData, setFormData] = useState(emptyForm);
  const [newItem, setNewItem] = useState({ product_id: "", quantity: 0, unit: "meter", price: 0, discount_percent: 0 });

  useEffect(() => { fetchPOs(); fetchMasterData(); }, []); // eslint-disable-line

  const fetchPOs = async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/purchase-orders`);
      setPos(res.data);
    } catch (e) {
      setError(e.response?.data?.detail || "Gagal memuat daftar Purchase Order.");
    } finally {
      setLoading(false);
    }
  };

  const fetchMasterData = async () => {
    try {
      const [pRes, wRes, sRes] = await Promise.all([
        axios.get(`${API}/products`).catch(() => ({ data: [] })),
        axios.get(`${API}/warehouses`).catch(() => ({ data: [] })),
        axios.get(`${API}/suppliers`).catch(() => ({ data: [] })),
      ]);
      setProducts(Array.isArray(pRes.data) ? pRes.data : []);
      setWarehouses(Array.isArray(wRes.data) ? wRes.data : []);
      setSuppliers(Array.isArray(sRes.data) ? sRes.data : []);
    } catch (e) { /* non-blocking */ }
  };

  const handleAddItem = () => {
    if (!newItem.product_id || newItem.quantity <= 0) {
      setError("Pilih produk dan masukkan qty yang valid (> 0)."); return;
    }
    setError("");
    const product = products.find((p) => p.id === newItem.product_id);
    setFormData({
      ...formData,
      items: [...formData.items, {
        ...newItem,
        price: newItem.price > 0 ? newItem.price : product?.price || 0,
        discount_percent: Number(newItem.discount_percent) || 0,
      }],
    });
    setNewItem({ product_id: "", quantity: 0, unit: "meter", price: 0, discount_percent: 0 });
  };

  const handleRemoveItem = (index) => {
    setFormData({ ...formData, items: formData.items.filter((_, i) => i !== index) });
  };

  const handleCreatePO = async () => {
    if (!formData.supplier_name || !formData.warehouse_id) {
      setError("Nama supplier dan gudang wajib diisi."); return;
    }
    if (formData.items.length === 0) {
      setError("Tambahkan minimal 1 item."); return;
    }
    setError("");
    setCreating(true);
    try {
      const res = await axios.post(`${API}/purchase-orders`, formData);
      const po = res.data;
      setNotice(po.approval_required
        ? `Purchase Order ${po.po_number} dibuat. Menunggu APPROVAL role '${po.required_approval_role}' sebelum inbound task dibuat.`
        : `Purchase Order ${po.po_number} dibuat & inbound task otomatis dibuat.`);
      setShowCreateForm(false);
      setFormData(emptyForm);
      fetchPOs();
    } catch (e) {
      setError(e.response?.data?.detail || "Gagal membuat PO.");
    } finally {
      setCreating(false);
    }
  };

  const handleViewDetail = async (poId) => {
    try {
      const res = await axios.get(`${API}/purchase-orders/${poId}`);
      setSelectedPO(res.data);
    } catch {
      setError("Gagal memuat detail PO.");
    }
  };

  // EPIC6 — deep-link: auto-buka detail PO saat dinavigasi dari Document Hub.
  useEffect(() => {
    if (focusDoc?.focus_type === "purchase_order" && focusDoc?.focus_id) {
      handleViewDetail(focusDoc.focus_id);
      onClearFocus?.();
    }
  }, [focusDoc]); // eslint-disable-line

  const handleCancelPO = (poId) => {
    const po = pos.find((p) => p.id === poId);
    setConfirm({
      title: "Batalkan Purchase Order",
      message: `Yakin membatalkan ${po?.po_number || "PO ini"}? Tindakan ini tidak dapat dibatalkan.`,
      confirmLabel: "Batalkan PO",
      danger: true,
      onConfirm: async () => {
        try {
          await axios.post(`${API}/purchase-orders/${poId}/cancel`);
          setNotice(`${po?.po_number || "PO"} berhasil dibatalkan.`);
          setConfirm(null);
          await fetchPOs();
          setSelectedPO(null);
        } catch (e) {
          setError(e.response?.data?.detail || "Gagal membatalkan PO.");
          setConfirm(null);
        }
      },
    });
  };

  const handleApprovePO = async (poId) => {
    if (!onApprovePO) return;
    const result = await onApprovePO(poId);
    if (result) { setNotice("PO disetujui. Inbound task dibuat."); await fetchPOs(); await handleViewDetail(poId); }
  };

  const handleCloseShort = (poId) => {
    const po = pos.find((p) => p.id === poId);
    setConfirm({
      title: "Tutup PO (Kurang Terima)",
      message: `Tutup ${po?.po_number || "PO ini"}? Task inbound yang masih terbuka akan dibatalkan.`,
      confirmLabel: "Tutup PO",
      danger: false,
      withReason: true,
      reasonLabel: "Alasan tutup-kurang",
      reasonPlaceholder: "Mis. sisa barang tidak akan dikirim supplier.",
      onConfirm: async (reason) => {
        try {
          await axios.post(`${API}/purchase-orders/${poId}/close`, { reason });
          setNotice(`${po?.po_number || "PO"} ditutup (kurang terima).`);
          setConfirm(null);
          await fetchPOs();
          await handleViewDetail(poId);
        } catch (e) {
          setError(e.response?.data?.detail || "Gagal menutup PO.");
          setConfirm(null);
        }
      },
    });
  };

  const handleCloseForm = () => {
    setShowCreateForm(false);
    setFormData(emptyForm);
  };

  // Phase 7.2 — submit amandemen PO (re-approval penuh di backend).
  const handleSubmitAmend = async (payload) => {
    if (!amendPO) return;
    setAmending(true);
    try {
      const res = await axios.post(`${API}/purchase-orders/${amendPO.id}/amend`, payload);
      const po = res.data;
      setNotice(po.approval_required
        ? `PO ${po.po_number} direvisi (v${po.version}). Menunggu APPROVAL role '${po.required_approval_role}' sebelum inbound task dibuat.`
        : `PO ${po.po_number} direvisi (v${po.version}). Inbound task diperbarui otomatis.`);
      setAmendPO(null);
      await fetchPOs();
      await handleViewDetail(po.id);
    } catch (e) {
      setError(e.response?.data?.detail || "Gagal merevisi PO.");
    } finally {
      setAmending(false);
    }
  };

  return (
    <div data-testid="po-management-panel">
      {notice && <div className="notice-bar success" data-testid="po-mgmt-notice"><span>{notice}</span><button onClick={() => setNotice("")}>×</button></div>}
      {error && <ErrorNotice message={error} onRetry={fetchPOs} onDismiss={() => setError("")} testId="po-mgmt-error" />}

      {/* Top bar */}
      <div className="section-card mb-3">
        <div className="section-head">
          <div className="flex items-center gap-2 min-w-0">
            <span className="kicker">Purchasing</span>
            <h2 data-testid="panel-title">Purchase Orders</h2>
          </div>
          <button data-testid="create-po-button"
            onClick={() => setShowCreateForm(!showCreateForm)}
            className="primary-button">
            <Plus size={13} /> {showCreateForm ? "Tutup Form" : "Buat PO"}
          </button>
        </div>
      </div>

      {/* Create Form */}
      {showCreateForm && (
        <POCreateForm
          formData={formData} setFormData={setFormData}
          newItem={newItem} setNewItem={setNewItem}
          products={products} warehouses={warehouses} suppliers={suppliers}
          submitting={creating}
          onSubmit={handleCreatePO} onCancel={handleCloseForm}
          onAddItem={handleAddItem} onRemoveItem={handleRemoveItem}
        />
      )}

      {/* Two-panel: PO table + detail */}
      <div className="grid gap-3 lg:grid-cols-[1fr_360px]">
        {/* PO Table */}
        <div className="section-card">
          <div className="overflow-hidden">
            <div className="grid grid-cols-[60px_1fr_120px_90px_60px] px-3 py-1.5 bg-[#FAFBFC] text-[10px] font-bold uppercase text-[#6B6B73] border-b border-[#EFF0F2]">
              <span>Nomor</span><span>Supplier</span><span>Gudang</span><span>Items</span><span>Status</span>
            </div>
            {loading ? (
              <div className="py-8 text-center text-[12px] text-[#6B6B73]">Loading...</div>
            ) : pos.length === 0 ? (
              <div className="py-10 text-center text-[12px] text-[#6B6B73]">
                <Package className="mx-auto mb-2 text-gray-300" size={28} />
                <p>Belum ada Purchase Order</p>
              </div>
            ) : (
              <div className="divide-y divide-[#EFF0F2] max-h-[560px] overflow-y-auto">
                {pos.map((po) => (
                  <div key={po.id} data-testid={`po-card-${po.id}`}
                    className={`grid grid-cols-[60px_1fr_120px_90px_60px] items-center px-3 py-2.5 cursor-pointer hover:bg-[#FAFBFC] transition-colors ${selectedPO?.id === po.id ? "bg-[#EFF4FF] border-l-2 border-[#007AFF]" : ""}`}
                    onClick={() => handleViewDetail(po.id)}>
                    <p data-testid={`po-number-${po.id}`} className="text-[12px] font-bold text-[#007AFF]">{po.po_number}</p>
                    <div className="min-w-0">
                      <p data-testid={`po-supplier-${po.id}`} className="text-[11.5px] font-semibold truncate">{po.supplier_name}</p>
                      <p className="text-[10.5px] text-[#6B6B73] tabular-nums">{formatCurrency(po.grand_total ?? po.total_amount)}</p>
                    </div>
                    <p className="text-[11px] text-[#3C3C43] truncate">{po.warehouse_name}</p>
                    <p className="text-[11.5px] text-[#6B6B73]">{po.items?.length || 0} item</p>
                    {getStatusBadge(po.status)}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* PO Detail Panel */}
        <PODetailPanel
          po={selectedPO}
          currentUser={user}
          onClose={() => setSelectedPO(null)}
          onApprove={handleApprovePO}
          onCancel={handleCancelPO}
          onCloseShort={handleCloseShort}
          onAmend={(po) => { setError(""); setAmendPO(po); }}
          onOpenDocument={onOpenDocument}
        />
      </div>

      {amendPO && (
        <POAmendModal
          po={amendPO}
          products={products}
          warehouses={warehouses}
          suppliers={suppliers}
          submitting={amending}
          onSubmit={handleSubmitAmend}
          onClose={() => setAmendPO(null)}
        />
      )}

      <ConfirmModal
        open={!!confirm}
        title={confirm?.title}
        message={confirm?.message}
        confirmLabel={confirm?.confirmLabel}
        danger={confirm?.danger}
        withReason={confirm?.withReason}
        reasonLabel={confirm?.reasonLabel}
        reasonPlaceholder={confirm?.reasonPlaceholder}
        onConfirm={confirm?.onConfirm}
        onCancel={() => setConfirm(null)}
        testId="po-confirm-modal"
      />
    </div>
  );
}
