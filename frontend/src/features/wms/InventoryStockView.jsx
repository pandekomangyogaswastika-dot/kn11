/**
 * InventoryStockView — WMS Stock Tab (Roll-as-SSOT, Fase 0.5 + Pegging Sub-fase 1.7)
 * - Balances (proyeksi) per product × warehouse × OWNER
 * - Rolls tab: daftar roll fisik (SSOT) + Pegging/Earmark (soft hold ke customer, KN_15)
 * - Owner filter mengikuti Entity Switcher global (selectedEntity)
 * - Ledger movements + initial-stock (roll) form
 *
 * Sub-components live in ./inventory/ (kept under file-size limits per KN_02).
 */
import { useEffect, useState } from "react";
import { BarChart2, Plus, X, History, RefreshCw, Search, MapPin, Layers, Building2, Anchor } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import { stockStatus } from "./inventory/inventoryConstants";
import InventorySummaryCards from "./inventory/InventorySummaryCards";
import InitialStockForm from "./inventory/InitialStockForm";
import BalancesTable from "./inventory/BalancesTable";
import RollsTable from "./inventory/RollsTable";
import LedgerTable from "./inventory/LedgerTable";
import ProductHistoryPanel from "./inventory/ProductHistoryPanel";
import WarehouseStructure from "./inventory/WarehouseStructure";
import { PeggingModal } from "../../components/PeggingModal";
import ErrorNotice from "../../components/ErrorNotice";

const emptyForm = {
  product_id: "", owner_entity_id: "", warehouse_id: "", quantity: 0,
  unit: "meter", lot: "", grade: "A", batch: "", roll_no: "",
};

export default function InventoryStockView({ warehouses = [], products = [], entities = [], customers = [], selectedEntity = "all", user }) {
  const [balances, setBalances]       = useState([]);
  const [rolls, setRolls]             = useState([]);
  const [peggedRolls, setPeggedRolls] = useState([]);
  const [movements, setMovements]     = useState([]);
  const [loading, setLoading]         = useState(false);
  const [error, setError]             = useState("");
  const [warehouseFilter, setWarehouseFilter] = useState("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedRow, setSelectedRow] = useState(null);
  const [history, setHistory]         = useState([]);
  const [histLoading, setHistLoading] = useState(false);
  const [showStockForm, setShowStockForm] = useState(false);
  const [stockForm, setStockForm]     = useState({ ...emptyForm });
  const [submitting, setSubmitting]   = useState(false);
  const [tab, setTab]                 = useState("balances"); // balances | rolls | ledger
  // Pegging (Sub-fase 1.7)
  const [pegRoll, setPegRoll]         = useState(null);   // roll yang sedang dibuka di modal
  const [pegBusyId, setPegBusyId]     = useState(null);   // roll yang sedang di-unpeg
  const [pegOnly, setPegOnly]         = useState(false);  // filter: hanya tampil roll yang di-peg

  useEffect(() => { fetchBalances(); /* eslint-disable-next-line */ }, [selectedEntity]);

  const ownerParams = selectedEntity && selectedEntity !== "all" ? { owner_entity_id: selectedEntity } : {};
  const canPeg = ["admin", "manager", "warehouse", "sales"].includes(user?.role);

  const fetchBalances = async () => {
    setLoading(true);
    try {
      const [b, m, rl, pg] = await Promise.all([
        axios.get(`${API}/inventory/balances`, { params: ownerParams }),
        axios.get(`${API}/inventory/movements`),
        axios.get(`${API}/inventory/rolls`, { params: ownerParams }),
        axios.get(`${API}/pegging/rolls`),
      ]);
      setBalances(Array.isArray(b.data) ? b.data : []);
      setMovements(Array.isArray(m.data) ? m.data : []);
      setRolls(Array.isArray(rl.data) ? rl.data : []);
      setPeggedRolls(Array.isArray(pg.data) ? pg.data : []);
      setError("");
    } catch (e) { setError(e.response?.data?.detail || "Gagal memuat data stok & inventori."); }
    finally { setLoading(false); }
  };

  const fetchHistory = async (productId) => {
    setHistLoading(true);
    try {
      const r = await axios.get(`${API}/history/${productId}`);
      setHistory(r.data);
    } catch { setHistory([]); }
    finally { setHistLoading(false); }
  };

  const handleRowClick = (row) => {
    if (selectedRow?.id === row.id) { setSelectedRow(null); setHistory([]); return; }
    setSelectedRow(row);
    fetchHistory(row.product_id);
  };

  const openStockForm = () => {
    setStockForm({ ...emptyForm, owner_entity_id: selectedEntity !== "all" ? selectedEntity : "" });
    setShowStockForm(true);
  };

  const handleAddInitialStock = async () => {
    if (!stockForm.product_id || !stockForm.owner_entity_id || !stockForm.warehouse_id
        || stockForm.quantity <= 0 || !stockForm.lot.trim())
      return alert("Produk, pemilik (entitas), gudang, qty, dan lot wajib diisi");
    setSubmitting(true);
    try {
      await axios.post(`${API}/inventory/initial-stock`, stockForm);
      setShowStockForm(false);
      setStockForm({ ...emptyForm });
      fetchBalances();
    } catch (e) { alert(e.response?.data?.detail || "Gagal tambah stok"); }
    finally { setSubmitting(false); }
  };

  // Pegging handlers (KN_15 soft hold). confirmPeg sengaja TIDAK menangkap error
  // agar PeggingModal bisa menampilkan pesan gagal (try/catch internal modal).
  const confirmPeg = async (customerId, note) => {
    if (!pegRoll) return;
    await axios.post(`${API}/inventory/rolls/${pegRoll.id}/earmark`, {
      ref_type: "customer", ref_id: customerId, note,
    });
    setPegRoll(null);
    await fetchBalances();
  };

  const handleUnpeg = async (roll) => {
    setPegBusyId(roll.id);
    try {
      await axios.delete(`${API}/inventory/rolls/${roll.id}/earmark`);
      await fetchBalances();
    } catch (e) { alert(e.response?.data?.detail || "Gagal lepas pegging"); }
    finally { setPegBusyId(null); }
  };

  const matchesSearch = (...fields) => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    return fields.some(f => f?.toLowerCase().includes(q));
  };

  const filteredBalances = balances
    .filter(b => warehouseFilter === "all" || b.warehouse_id === warehouseFilter)
    .filter(b => matchesSearch(b.sku, b.product_name, b.warehouse_name, b.warehouse_city, b.owner_entity_name));

  const peggedScoped = peggedRolls.filter(r => selectedEntity === "all" || r.owner_entity_id === selectedEntity);
  const rollsBase = pegOnly ? peggedScoped : rolls;
  const filteredRolls = rollsBase
    .filter(r => warehouseFilter === "all" || r.warehouse_id === warehouseFilter)
    .filter(r => matchesSearch(r.sku, r.product_name, r.warehouse_name, r.lot, r.roll_no, r.owner_entity_name));

  const filteredMovements = movements
    .filter(m => warehouseFilter === "all" || m.warehouse_id === warehouseFilter)
    .filter(m => {
      const prod = balances.find(b => b.product_id === m.product_id);
      return matchesSearch(prod?.sku, prod?.product_name, m.source_document);
    });

  // Summary cards
  const totalOnHand   = filteredBalances.reduce((s, b) => s + (b.on_hand_qty || 0), 0);
  const totalAvail    = filteredBalances.reduce((s, b) => s + (b.available_qty || 0), 0);
  const totalReserved = filteredBalances.reduce((s, b) => s + (b.reserved_qty || 0), 0);
  const lowCount      = filteredBalances.filter(b => stockStatus(b) === "low").length;

  const entityLabel = selectedEntity === "all"
    ? "Semua Entitas"
    : (entities.find(e => e.id === selectedEntity)?.short_name || "Entitas");

  return (
    <div data-testid="inventory-stock-view" className="flex flex-col gap-3">

      <ErrorNotice message={error} onRetry={fetchBalances} onDismiss={() => setError("")} testId="inventory-stock-error" />

      <InventorySummaryCards
        totalOnHand={totalOnHand}
        totalAvail={totalAvail}
        totalReserved={totalReserved}
        lowCount={lowCount}
      />

      {/* Owner context banner */}
      <div className="flex items-center gap-2 rounded-lg bg-[#EEF2FF] border border-[#E0E7FF] px-3 py-1.5" data-testid="inventory-owner-context">
        <Building2 size={13} className="text-[#4338CA]" />
        <span className="text-[11.5px] text-[#4338CA]">
          Konteks kepemilikan: <strong>{entityLabel}</strong>
          <span className="text-[#6B6B73] ml-1">— stok = proyeksi dari roll (SSOT). Reservasi terjadi di level roll.</span>
        </span>
      </div>

      {/* Search Bar */}
      <div className="flex items-center gap-2 rounded-lg border border-[#E5E5EA] bg-white px-3 py-2">
        <Search size={14} className="text-[#6B6B73]" />
        <input
          type="text"
          data-testid="inventory-search-input"
          className="flex-1 bg-transparent text-[13px] outline-none placeholder:text-[#8E8E93]"
          placeholder="Cari SKU, produk, gudang, lot, roll, pemilik..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
        />
        {searchQuery && (
          <button onClick={() => setSearchQuery("")} className="text-[#6B6B73] hover:text-black">
            <X size={14} />
          </button>
        )}
      </div>

      {/* Warehouse filter + tabs + actions */}
      <div className="flex flex-wrap items-center gap-2">
        <div className="flex items-center gap-1.5 overflow-x-auto" data-testid="inventory-warehouse-filters">
          <button onClick={() => setWarehouseFilter("all")}
            className={`rounded-full px-3 py-1 text-xs font-medium whitespace-nowrap transition-all ${warehouseFilter === "all" ? "bg-[#007AFF] text-white" : "bg-white border border-[#E5E5EA] text-[#6B6B73] hover:border-[#007AFF]"}`}>
            Semua Gudang
          </button>
          {warehouses.map(wh => (
            <button key={wh.id} onClick={() => setWarehouseFilter(wh.id)}
              className={`rounded-full px-3 py-1 text-xs font-medium whitespace-nowrap transition-all ${warehouseFilter === wh.id ? "bg-[#007AFF] text-white" : "bg-white border border-[#E5E5EA] text-[#6B6B73] hover:border-[#007AFF]"}`}>
              <MapPin size={9} className="inline mr-1" />{wh.city}
            </button>
          ))}
        </div>
        {/* View tab toggle */}
        <div className="ml-auto flex items-center gap-1 rounded-lg border border-[#E5E5EA] p-0.5 bg-white">
          <button onClick={() => setTab("balances")} data-testid="inventory-tab-balances"
            className={`flex items-center gap-1 px-2.5 py-1 rounded-md text-[11px] font-medium transition-all ${tab === "balances" ? "bg-[#007AFF] text-white" : "text-[#6B6B73]"}`}>
            <BarChart2 size={11} /> Stok
          </button>
          <button onClick={() => setTab("rolls")} data-testid="inventory-tab-rolls"
            className={`flex items-center gap-1 px-2.5 py-1 rounded-md text-[11px] font-medium transition-all ${tab === "rolls" ? "bg-[#007AFF] text-white" : "text-[#6B6B73]"}`}>
            <Layers size={11} /> Rolls
          </button>
          <button onClick={() => setTab("ledger")} data-testid="inventory-tab-ledger"
            className={`flex items-center gap-1 px-2.5 py-1 rounded-md text-[11px] font-medium transition-all ${tab === "ledger" ? "bg-[#007AFF] text-white" : "text-[#6B6B73]"}`}>
            <History size={11} /> Ledger
          </button>
        </div>
        <button onClick={() => fetchBalances()} data-testid="inventory-refresh" className="p-1.5 rounded-lg border border-[#E5E5EA] text-[#6B6B73] hover:bg-[#FAFBFC]">
          <RefreshCw size={13} />
        </button>
        {["admin", "manager"].includes(user?.role) && (
          <button onClick={openStockForm} data-testid="add-stock-button"
            className="flex items-center gap-1.5 rounded-lg bg-[#34C759] hover:bg-[#28A745] text-white px-3 py-1.5 text-[12px] font-semibold">
            <Plus size={12} /> Tambah Stok
          </button>
        )}
      </div>

      {/* Pegging filter bar — hanya saat tab Rolls */}
      {tab === "rolls" && (
        <div className="flex items-center justify-between gap-2 rounded-lg bg-[#FBF7FF] border border-[#EFE3FB] px-3 py-1.5" data-testid="rolls-pegging-bar">
          <span className="flex items-center gap-1.5 text-[11.5px] text-[#6B219A]">
            <Anchor size={13} className="text-[#6B219A]" />
            <strong className="tabular-nums" data-testid="pegging-count">{peggedScoped.length}</strong> roll di-pegging (soft hold)
            <span className="text-[#9A6BC0]">— roll yang di-peg dikecualikan dari alokasi customer lain.</span>
          </span>
          <button
            data-testid="pegging-only-toggle"
            onClick={() => setPegOnly(v => !v)}
            className={`rounded-full px-3 py-1 text-[11px] font-semibold whitespace-nowrap transition-all ${pegOnly ? "bg-[#6B219A] text-white" : "bg-white border border-[#D6CCF0] text-[#6B219A] hover:bg-[#F6EDFF]"}`}>
            {pegOnly ? "Tampilkan Semua Roll" : "Hanya yang Di-peg"}
          </button>
        </div>
      )}

      {showStockForm && (
        <InitialStockForm
          stockForm={stockForm}
          setStockForm={setStockForm}
          products={products}
          warehouses={warehouses}
          entities={entities}
          submitting={submitting}
          onSubmit={handleAddInitialStock}
          onClose={() => setShowStockForm(false)}
        />
      )}

      {/* MAIN CONTENT — 2 panel */}
      <div className={`grid gap-3 ${selectedRow && tab === "balances" ? "lg:grid-cols-[1fr_300px]" : ""}`}>
        {tab === "balances" && (
          <BalancesTable
            loading={loading}
            rows={filteredBalances}
            selectedRow={selectedRow}
            onRowClick={handleRowClick}
          />
        )}

        {tab === "rolls" && (
          <RollsTable
            loading={loading}
            rolls={filteredRolls}
            canPeg={canPeg}
            onPeg={setPegRoll}
            onUnpeg={handleUnpeg}
            busyRollId={pegBusyId}
          />
        )}

        {tab === "ledger" && (
          <LedgerTable movements={filteredMovements} balances={balances} loading={loading} />
        )}

        {selectedRow && tab === "balances" && (
          <ProductHistoryPanel
            selectedRow={selectedRow}
            history={history}
            histLoading={histLoading}
            onClose={() => { setSelectedRow(null); setHistory([]); }}
          />
        )}
      </div>

      {/* Empty-state hints */}
      {!loading && tab === "balances" && filteredBalances.length === 0 && searchQuery ? (
        <p data-testid="inventory-no-results" className="text-center text-[12px] text-[#6B6B73] py-2">
          Tidak ada hasil untuk "{searchQuery}"
        </p>
      ) : null}

      {!loading && tab === "rolls" && pegOnly && peggedScoped.length === 0 ? (
        <p data-testid="pegging-empty" className="text-center text-[12px] text-[#6B6B73] py-2">
          Belum ada roll yang di-pegging untuk {entityLabel}.
        </p>
      ) : null}

      <WarehouseStructure warehouses={warehouses} loading={loading} />

      {/* Pegging modal */}
      {pegRoll && (
        <PeggingModal
          roll={pegRoll}
          customers={customers}
          onCancel={() => setPegRoll(null)}
          onConfirm={confirmPeg}
        />
      )}
    </div>
  );
}
