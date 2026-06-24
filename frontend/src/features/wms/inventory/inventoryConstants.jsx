/**
 * inventoryConstants — shared formatters, movement-type map, and stock-status
 * helpers used across the Inventory (WMS Stock tab) sub-components.
 */
import { AlertTriangle } from "lucide-react";

export const formatQty = (v) => {
  if (v === undefined || v === null) return "0";
  return Number(v).toLocaleString("id-ID", { maximumFractionDigits: 2 });
};

export const formatDate = (iso) => {
  if (!iso) return "-";
  return new Date(iso).toLocaleDateString("id-ID", {
    day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit",
  });
};

export const MOV_TYPE_MAP = {
  initial_stock:       { label: "Initial Stock",       color: "text-gray-600",  dot: "bg-gray-400" },
  inbound_receiving:   { label: "Inbound Receiving",   color: "text-green-700", dot: "bg-green-500" },
  outbound_dispatch:   { label: "Outbound Dispatch",   color: "text-red-600",   dot: "bg-red-500" },
  transfer_out:        { label: "Transfer Out",        color: "text-orange-600",dot: "bg-orange-400" },
  transfer_in:         { label: "Transfer In",         color: "text-blue-600",  dot: "bg-blue-500" },
  cycle_count_adjust:  { label: "Cycle Count Adj.",    color: "text-purple-600",dot: "bg-purple-400" },
};

// Stock status berdasarkan available_qty
export const stockStatus = (b) => {
  if (b.available_qty <= 0) return "empty";
  if (b.available_qty < 100) return "low";
  return "ok";
};

export const ROW_CLASSES = {
  ok:    "hover:bg-[#FAFBFC]",
  low:   "bg-amber-50 hover:bg-amber-100",
  empty: "bg-red-50 hover:bg-red-100",
};

export const STATUS_BADGE = {
  ok:    <span data-testid="stock-status-ok" className="rounded px-1.5 py-0.5 text-[10px] font-semibold bg-green-100 text-green-700">OK</span>,
  low:   <span data-testid="stock-status-low" className="rounded px-1.5 py-0.5 text-[10px] font-semibold bg-amber-100 text-amber-700 flex items-center gap-1"><AlertTriangle size={9} />Rendah</span>,
  empty: <span data-testid="stock-status-empty" className="rounded px-1.5 py-0.5 text-[10px] font-semibold bg-red-100 text-red-700">Habis</span>,
};

// ── Roll-as-SSOT (Fase 0.5) ────────────────────────────────────────────────
export const ROLL_STATUS_META = {
  available:                { label: "Available",   cls: "bg-green-100 text-green-700" },
  reserved:                 { label: "Reserved",    cls: "bg-orange-100 text-orange-700" },
  committed:                { label: "Committed",   cls: "bg-purple-100 text-purple-700" },
  picked:                   { label: "Picked",      cls: "bg-blue-100 text-blue-700" },
  packed:                   { label: "Packed",      cls: "bg-indigo-100 text-indigo-700" },
  quarantine:               { label: "Quarantine",  cls: "bg-amber-100 text-amber-700" },
  blocked:                  { label: "Blocked",     cls: "bg-amber-100 text-amber-800" },
  damaged:                  { label: "Damaged",     cls: "bg-red-100 text-red-700" },
  sold:                     { label: "Sold",        cls: "bg-gray-200 text-gray-600" },
  in_transit_inbound:       { label: "In-Transit (Inbound)",  cls: "bg-cyan-100 text-cyan-700" },
  in_transit_transfer:      { label: "In-Transit (Transfer)", cls: "bg-cyan-100 text-cyan-700" },
  in_transit_intercompany:  { label: "In-Transit (Antar-PT)", cls: "bg-teal-100 text-teal-700" },
  in_transit_sales:         { label: "In-Transit (Sales)",    cls: "bg-cyan-100 text-cyan-700" },
};

export const RollStatusBadge = ({ status }) => {
  const m = ROLL_STATUS_META[status] || { label: status, cls: "bg-gray-100 text-gray-600" };
  return (
    <span data-testid={`roll-status-${status}`} className={`rounded px-1.5 py-0.5 text-[10px] font-semibold ${m.cls}`}>
      {m.label}
    </span>
  );
};
