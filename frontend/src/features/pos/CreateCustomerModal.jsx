import { useState } from "react";
import { X, UserPlus } from "lucide-react";
import KNSelect from "../../components/KNSelect";

const LOT_POLICY_OPTIONS = [
  { value: "", label: "Default (prefer single)" },
  { value: "prefer_single", label: "Prefer single lot" },
  { value: "strict_single", label: "Strict single lot" },
  { value: "allow_mixed", label: "Boleh mixed lot" },
];

/** EPIC5 — Buat Customer sebagai MODAL (dipanggil dari checkout step 1). */
export default function CreateCustomerModal({ open, onClose, onCreateCustomer }) {
  const [form, setForm] = useState({
    name: "", pic_name: "", phone: "", city: "Jakarta", address: "",
    enforce_single_dye_lot: false, lot_policy: "",
  });
  const [busy, setBusy] = useState(false);
  if (!open) return null;

  const valid = form.name && form.pic_name && form.phone && form.city && form.address;

  async function submit() {
    if (!valid) return;
    setBusy(true);
    try {
      await onCreateCustomer(form);
      onClose();
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="fixed inset-0 z-[120] flex items-center justify-center bg-black/40 p-4" data-testid="create-customer-modal">
      <div className="w-full max-w-md rounded-xl bg-white shadow-2xl">
        <div className="flex items-center justify-between border-b border-[#EFF0F2] px-4 py-3">
          <div className="flex items-center gap-2">
            <UserPlus size={16} className="text-[#0058CC]" />
            <h3 className="text-[14px] font-bold">Customer Baru</h3>
          </div>
          <button data-testid="create-customer-close" className="icon-button" onClick={onClose} aria-label="Tutup"><X size={16} /></button>
        </div>
        <div className="grid gap-2 p-4">
          <input data-testid="new-customer-name-input" className="field" placeholder="Nama customer" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          <input data-testid="new-customer-pic-input" className="field" placeholder="Nama PIC" value={form.pic_name} onChange={(e) => setForm({ ...form, pic_name: e.target.value })} />
          <input data-testid="new-customer-phone-input" className="field" placeholder="No. WhatsApp" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
          <div className="grid gap-2 sm:grid-cols-2">
            <input data-testid="new-customer-city-input" className="field" placeholder="Kota" value={form.city} onChange={(e) => setForm({ ...form, city: e.target.value })} />
            <input data-testid="new-customer-address-input" className="field" placeholder="Alamat" value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })} />
          </div>
          <div className="grid gap-2 rounded-md border border-[#E5C7F5] bg-[#FBF7FF] p-2">
            <label data-testid="new-customer-enforce-dyelot" className="flex items-start gap-2 text-[11px] text-[#3C3C43] cursor-pointer">
              <input type="checkbox" className="mt-0.5" checked={form.enforce_single_dye_lot} onChange={(e) => setForm({ ...form, enforce_single_dye_lot: e.target.checked })} />
              <span>Paksa <b>1 dye lot</b> saat alokasi (hindari belang warna antar roll)</span>
            </label>
            <div>
              <label className="block text-[10px] font-bold uppercase tracking-wide text-[#6B6B73] mb-1">Kebijakan Lot</label>
              <KNSelect data-testid="new-customer-lot-policy" className="field w-full" value={form.lot_policy} onValueChange={(v) => setForm({ ...form, lot_policy: v })} options={LOT_POLICY_OPTIONS} />
            </div>
          </div>
          <div className="mt-1 flex justify-end gap-2">
            <button className="secondary-button" onClick={onClose}>Batal</button>
            <button data-testid="create-customer-button" className="primary-button" disabled={!valid || busy} onClick={submit}>
              <UserPlus size={14} /> {busy ? "Menyimpan..." : "Buat Customer"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
