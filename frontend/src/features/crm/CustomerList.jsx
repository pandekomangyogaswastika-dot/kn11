import { useEffect, useMemo, useState } from "react";
import axios, { API } from "../../services/apiClient";
import { Users, Plus, Search, UserCircle, AlertTriangle } from "lucide-react";
import { formatCurrency } from "../../utils/formatters";
import KNSelect from "../../components/KNSelect";
import ErrorNotice from "../../components/ErrorNotice";
import { CreditStatusPill, SegmentBadge } from "./crmUtils";
import CustomerFormModal from "./CustomerFormModal";
import Customer360Panel from "./Customer360Panel";

/** Daftar pelanggan + filter (segment / status kredit / sales) + Customer 360. */
export default function CustomerList({ currentUser, selectedEntity }) {
  const [rows, setRows] = useState([]);
  const [salesUsers, setSalesUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [search, setSearch] = useState("");
  const [segment, setSegment] = useState("");
  const [creditStatus, setCreditStatus] = useState("");
  const [salesFilter, setSalesFilter] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [editTarget, setEditTarget] = useState(null);
  const [selectedId, setSelectedId] = useState(null);

  const role = currentUser?.role;
  const isManager = role === "admin" || role === "manager";
  const canCreate = ["admin", "manager", "sales"].includes(role);

  useEffect(() => { loadSales(); }, []); // eslint-disable-line
  useEffect(() => { load(); }, [selectedEntity, segment, creditStatus, salesFilter]); // eslint-disable-line

  async function loadSales() {
    try {
      const r = await axios.get(`${API}/sales-users`);
      setSalesUsers(Array.isArray(r.data) ? r.data : []);
    } catch (e) { /* non-blocking */ }
  }

  async function load() {
    setLoading(true);
    try {
      const params = {};
      if (selectedEntity && selectedEntity !== "all") params.entity_id = selectedEntity;
      if (segment) params.segment = segment;
      if (creditStatus) params.credit_status = creditStatus;
      if (salesFilter) params.assigned_sales_id = salesFilter;
      const r = await axios.get(`${API}/customers`, { params });
      setRows(Array.isArray(r.data) ? r.data : []);
      setError("");
    } catch (e) {
      setError(e.response?.data?.detail || "Gagal memuat pelanggan.");
    } finally { setLoading(false); }
  }

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return rows;
    return rows.filter((c) =>
      [c.name, c.code, c.city, c.assigned_sales_name].filter(Boolean).join(" ").toLowerCase().includes(q));
  }, [rows, search]);

  const salesOptions = useMemo(() => [
    { value: "", label: "Semua Sales" },
    ...salesUsers.map((s) => ({ value: s.id, label: s.name })),
  ], [salesUsers]);

  if (selectedId) {
    return (
      <Customer360Panel customerId={selectedId} currentUser={currentUser} salesUsers={salesUsers}
        onBack={() => setSelectedId(null)}
        onChanged={(msg) => { if (msg) setNotice(msg); load(); }}
        onError={(m) => setError(m)} />
    );
  }

  return (
    <div data-testid="customer-list">
      {notice && (
        <div className="notice-bar success" data-testid="customer-notice">
          <span>{notice}</span><button onClick={() => setNotice("")}>×</button>
        </div>
      )}
      <ErrorNotice message={error} onRetry={load} onDismiss={() => setError("")} testId="customer-error" />

      <div className="section-card">
        <div className="section-head">
          <div className="flex items-center gap-2">
            <Users size={16} className="text-[#0058CC]" />
            <h2 data-testid="customer-list-title">Pelanggan {isManager ? "(Semua)" : "(Milik Saya)"}</h2>
          </div>
          {canCreate && (
            <button data-testid="customer-create-button" className="primary-button"
              onClick={() => { setEditTarget(null); setShowForm(true); }}>
              <Plus size={13} /> Pelanggan Baru
            </button>
          )}
        </div>
        <div className="section-body">
          {/* Filters */}
          <div className="flex flex-wrap items-center gap-2 mb-3">
            <div className="relative flex-1 min-w-[180px]">
              <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[#9A9BA3]" />
              <input data-testid="customer-search" value={search} onChange={(e) => setSearch(e.target.value)}
                className="field pl-8" placeholder="Cari nama / kode / kota..." />
            </div>
            <KNSelect value={segment} onValueChange={setSegment} className="field w-[150px]"
              data-testid="customer-filter-segment" placeholder="Segment"
              options={[{ value: "", label: "Semua Segment" }, { value: "Retail", label: "Retail" },
                { value: "Wholesale", label: "Wholesale" }, { value: "Distributor", label: "Distributor" },
                { value: "VIP", label: "VIP" }]} />
            <KNSelect value={creditStatus} onValueChange={setCreditStatus} className="field w-[150px]"
              data-testid="customer-filter-credit" placeholder="Status Kredit"
              options={[{ value: "", label: "Semua Kredit" }, { value: "active", label: "Sehat" },
                { value: "warning", label: "Perhatian" }, { value: "blocked", label: "Terblokir" }]} />
            {isManager && (
              <KNSelect value={salesFilter} onValueChange={setSalesFilter} className="field w-[160px]"
                data-testid="customer-filter-sales" placeholder="Sales" options={salesOptions} />
            )}
          </div>

          {/* Table */}
          <div className="rounded-md border border-[#EFF0F2] overflow-hidden">
            <div className="grid grid-cols-[1.4fr_110px_1fr_130px_110px] px-3 py-1.5 bg-[#FAFBFC] text-[10px] font-bold uppercase text-[#6B6B73] border-b border-[#EFF0F2]">
              <span>Pelanggan</span><span>Segment</span><span>Sales</span><span>AR / Limit</span><span>Kredit</span>
            </div>
            {loading ? (
              <div className="py-10 text-center text-[12px] text-[#6B6B73]" data-testid="customer-loading">Memuat...</div>
            ) : filtered.length === 0 ? (
              <div className="py-12 text-center text-[12px] text-[#6B6B73]" data-testid="customer-empty">
                <UserCircle className="mx-auto mb-2 text-gray-300" size={28} />
                <p>Belum ada pelanggan{search || segment || creditStatus ? " sesuai filter" : ""}.</p>
              </div>
            ) : (
              <div className="divide-y divide-[#EFF0F2] max-h-[600px] overflow-y-auto">
                {filtered.map((c) => {
                  const credit = c.credit || {};
                  const limit = Number(credit.credit_limit || c.credit_limit || 0);
                  const ar = Number(credit.ar_outstanding || 0);
                  const over = limit > 0 && ar >= limit;
                  return (
                    <button key={c.id} data-testid={`customer-row-${c.id}`} onClick={() => setSelectedId(c.id)}
                      className="w-full text-left grid grid-cols-[1.4fr_110px_1fr_130px_110px] items-center px-3 py-2.5 hover:bg-[#FAFBFC] transition-colors">
                      <div className="min-w-0">
                        <p className="text-[12.5px] font-semibold truncate">{c.name}</p>
                        <p className="text-[10.5px] text-[#6B6B73] truncate">{c.code} · {c.city}</p>
                      </div>
                      <SegmentBadge segment={c.segment} />
                      <span className="text-[11.5px] truncate text-[#3C3C43]">{c.assigned_sales_name || "—"}</span>
                      <div className="pr-2">
                        <p className={`text-[11.5px] tabular-nums font-semibold ${over ? "text-[#C0392B]" : ""}`}>{formatCurrency(ar)}</p>
                        <p className="text-[10px] text-[#9A9BA3] tabular-nums">/ {limit > 0 ? formatCurrency(limit) : "∞"}</p>
                      </div>
                      <div className="flex items-center gap-1">
                        <CreditStatusPill status={credit.status || "active"} />
                        {Number(credit.overdue_amount) > 0 && <AlertTriangle size={12} className="text-[#B45309]" />}
                      </div>
                    </button>
                  );
                })}
              </div>
            )}
          </div>
          {!loading && (
            <p className="text-[11px] text-[#9A9BA3] mt-2" data-testid="customer-count">{filtered.length} pelanggan</p>
          )}
        </div>
      </div>

      <CustomerFormModal open={showForm} editTarget={editTarget} currentUser={currentUser}
        salesUsers={salesUsers} selectedEntity={selectedEntity}
        onClose={() => setShowForm(false)}
        onSaved={(c, isEdit) => { setShowForm(false); setNotice(`Pelanggan ${c.name} ${isEdit ? "diperbarui" : "dibuat"}.`); load(); }}
        onError={(m) => setError(m)} />
    </div>
  );
}
