/** Sub-fase 1.11 — Create return form. */
import { useState, useEffect } from "react";
import axios, { API } from "../../services/apiClient";
import { AlertCircle, ArrowLeft, Loader2, Plus, RotateCcw, Trash2, X } from "lucide-react";
import KNSelect from "../../components/KNSelect";


export default function CreateReturnForm({ orders, token, onCreated, onCancel, onLoadOrders }) {
  const [orderId, setOrderId]       = useState("");
  const [returnType, setReturnType] = useState("retur");
  const [items, setItems]           = useState([{ product_id: "", product_name: "", quantity_returned: "", unit: "meter", reason: "", condition: "ok" }]);
  const [notes, setNotes]           = useState("");
  const [submitNow, setSubmitNow]   = useState(true);
  const [saving, setSaving]         = useState(false);
  const [error, setError]           = useState(null);

  useEffect(() => { onLoadOrders(); }, []); // eslint-disable-line

  function handleOrderChange(id) {
    setOrderId(id);
    const order = orders.find(o => o.id === id);
    if (order?.items?.length) {
      setItems(order.items.map(li => ({
        product_id:        li.product_id || "",
        product_name:      li.product_name || "",
        quantity_returned: "",
        unit:              li.unit || "meter",
        reason:            "",
        condition:         "ok",
      })));
    }
  }

  const updateItem = (i, f, v) => setItems(prev => prev.map((it, idx) => idx === i ? { ...it, [f]: v } : it));
  const addItem    = () => setItems(prev => [...prev, { product_id: "", product_name: "", quantity_returned: "", unit: "meter", reason: "", condition: "ok" }]);
  const removeItem = (i) => setItems(prev => prev.filter((_, idx) => idx !== i));

  async function handleSubmit(e) {
    e.preventDefault();
    if (!orderId) return setError("Pilih pesanan terlebih dahulu");
    const validItems = items.filter(it => it.product_id && parseFloat(it.quantity_returned) > 0);
    if (!validItems.length) return setError("Minimal 1 item dengan kuantitas > 0");
    setSaving(true); setError(null);
    try {
      const res = await axios.post(`${API}/sales-returns`, {
        order_id: orderId, return_type: returnType,
        items: validItems.map(it => ({ ...it, quantity_returned: parseFloat(it.quantity_returned) })),
        notes, submit_now: submitNow,
      }, { headers: { Authorization: `Bearer ${token}` } });
      onCreated(res.data);
    } catch (err) {
      setError("Gagal membuat return: " + (err.response?.data?.detail || err.message));
    } finally { setSaving(false); }
  }

  return (
    <div data-testid="create-return-form" className="view-container">
      <button className="back-button" onClick={onCancel}><ArrowLeft size={14} /> Batal</button>

      <div className="view-header">
        <div>
          <h1 className="view-title">Buat Return Baru</h1>
          <p className="view-subtitle">Retur barang, Barang Sisa (BS), penggantian, komplain & garansi (aftersales) dari customer</p>
        </div>
      </div>

      {error && (
        <div className="notice-bar danger">
          <AlertCircle size={14} /> {error}
          <button onClick={() => setError(null)}><X size={12} /></button>
        </div>
      )}

      <form onSubmit={handleSubmit} className="form-card">
        <div className="form-row-2col">
          <div className="form-group">
            <label className="form-label" htmlFor="ret-order">Pesanan (SO) <span className="req">*</span></label>
            <KNSelect
              data-testid="return-order-select"
              className="form-select"
              value={orderId}
              onValueChange={handleOrderChange}
              placeholder="-- Pilih pesanan --"
              options={[
                { value: "", label: "-- Pilih pesanan --" },
                ...orders.map(o => ({ value: o.id, label: `${o.number} — ${o.customer_name} (${o.status})` })),
              ]}
            />
          </div>
          <div className="form-group">
            <label className="form-label" htmlFor="ret-type">Tipe Return <span className="req">*</span></label>
            <KNSelect
              data-testid="return-type-select"
              className="form-select"
              value={returnType}
              onValueChange={setReturnType}
              options={[
                { value: "retur", label: "Retur (customer kembalikan barang)" },
                { value: "bs", label: "Barang Sisa — BS (sisa penggunaan)" },
                { value: "penggantian", label: "Penggantian (cacat / salah kirim)" },
                { value: "komplain", label: "Komplain (keluhan kualitas)" },
                { value: "garansi", label: "Garansi (klaim jaminan)" },
              ]}
            />
          </div>
        </div>

        <div className="form-group">
          <label className="form-label">Item yang Diretur <span className="req">*</span></label>
          <div className="form-items-table">
            <div className="form-items-header">
              <span>Produk</span><span>Qty</span><span>Satuan</span><span>Kondisi</span><span>Alasan</span><span></span>
            </div>
            {items.map((it, i) => (
              <div key={i} className="form-items-row" data-testid={`return-item-row-${i}`}>
                <input data-testid={`item-product-${i}`} className="form-input" placeholder="ID Produk"
                  value={it.product_id} onChange={e => updateItem(i, "product_id", e.target.value)} />
                <input data-testid={`item-qty-${i}`} className="form-input text-right" type="number"
                  min="0.01" step="0.01" placeholder="0.00"
                  value={it.quantity_returned} onChange={e => updateItem(i, "quantity_returned", e.target.value)} />
                <KNSelect data-testid={`item-unit-${i}`} className="form-select" value={it.unit}
                  onValueChange={v => updateItem(i, "unit", v)}
                  options={[
                    { value: "meter", label: "meter" },
                    { value: "kg", label: "kg" },
                    { value: "roll", label: "roll" },
                    { value: "pcs", label: "pcs" },
                  ]}
                />
                <KNSelect data-testid={`item-condition-${i}`} className="form-select" value={it.condition}
                  onValueChange={v => updateItem(i, "condition", v)}
                  options={[
                    { value: "ok", label: "Baik" },
                    { value: "damaged", label: "Rusak" },
                  ]}
                />
                <input data-testid={`item-reason-${i}`} className="form-input" placeholder="Alasan..."
                  value={it.reason} onChange={e => updateItem(i, "reason", e.target.value)} />
                <button type="button" className="icon-button danger" onClick={() => removeItem(i)}
                  disabled={items.length === 1} data-testid={`remove-item-${i}`}>
                  <Trash2 size={12} />
                </button>
              </div>
            ))}
            <button type="button" className="link-button" onClick={addItem} data-testid="add-return-item-btn">
              <Plus size={12} /> Tambah Item
            </button>
          </div>
        </div>

        <div className="form-group">
          <label className="form-label" htmlFor="ret-notes">Catatan</label>
          <textarea id="ret-notes" data-testid="return-notes-input" className="textarea" rows={2}
            placeholder="Keterangan tambahan..." value={notes} onChange={e => setNotes(e.target.value)} />
        </div>

        <div className="form-group">
          <label className="form-check-label">
            <input type="checkbox" data-testid="submit-now-check" checked={submitNow}
              onChange={e => setSubmitNow(e.target.checked)} />
            {" "}Langsung kirim untuk approval (skip draft)
          </label>
        </div>

        <div className="form-actions">
          <button type="button" className="secondary-button" onClick={onCancel}>Batal</button>
          <button type="submit" data-testid="save-return-btn" className="primary-button" disabled={saving}>
            {saving ? <Loader2 size={14} className="spin" /> : <RotateCcw size={14} />} Buat Return
          </button>
        </div>
      </form>
    </div>
  );
}
