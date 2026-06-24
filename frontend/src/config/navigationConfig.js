import {
  AlertTriangle,
  ArrowLeftRight,
  BadgePercent,
  BarChart3,
  BarChart2,
  Bell,
  BookOpen,
  Boxes,
  Ship,
  CalendarX,
  ClipboardCheck,
  ClipboardList,
  Clock,
  CreditCard,
  Cpu,
  DollarSign,
  FileText,
  FileStack,
  Home,
  Layers,
  Layers3,
  LineChart,
  MapPin,
  Package,
  PackageCheck,
  PackageMinus,
  Palette,
  Percent,
  PieChart,
  Printer,
  Receipt,
  RotateCcw,
  Landmark,
  Settings,
  ShieldCheck,
  ShoppingBag,
  ShoppingCart,
  Star,
  Tag,
  Target,
  TrendingUp,
  TrendingDown,
  Truck,
  UserCheck,
  Users,
  Wallet,
  Warehouse,
  Wifi,
} from "lucide-react";

// ─── PAGE META (SSOT untuk TopBar kicker + title) ─────────────────────────────
export const PAGE_META = {
  admin:                  { kicker: "Admin",          title: "Master Data & Audit" },
  "admin-home":           { kicker: "Eksekutif",      title: "Control Tower" },
  sales:                  { kicker: "Penjualan",      title: "Katalog POS & Reservasi" },
  "sales":                { kicker: "Penjualan",      title: "POS / Sales Portal" },
  "sales-home":           { kicker: "Penjualan",      title: "Performa Saya" },
  "customers-crm":        { kicker: "Penjualan",      title: "Pelanggan / CRM \u00b7 Sales Force" },
  "price-approvals":      { kicker: "Penjualan",      title: "Approval Harga Khusus" },
  orders:                 { kicker: "Penjualan",      title: "Pesanan Penjualan" },
  "tax-invoices":         { kicker: "Penjualan",      title: "Faktur Pajak Jual" },
  "returns":              { kicker: "Penjualan",      title: "Returns & Barang Sisa" },
  "special-orders":       { kicker: "Penjualan",      title: "Special Order (OD)" },
  "pricelist":            { kicker: "Penjualan",      title: "Pricelist per-Entitas (PT)" },
  "product-templates":    { kicker: "Penjualan",      title: "Template & Varian Produk" },
  "approval-inbox":       { kicker: "Approvals",      title: "Pusat Persetujuan" },
  "approval-rules":       { kicker: "Settings",       title: "Approval Rules" },
  purchasing:             { kicker: "Pembelian",      title: "Pesanan Pembelian (PO)" },
  "blanket-po":           { kicker: "Pembelian",      title: "Blanket / Contract PO · Call-off" },
  "purchase-requisitions":{ kicker: "Pembelian",      title: "Purchase Requisition (PR)" },
  reorder:                { kicker: "Pembelian",      title: "Saran Reorder · Replenishment" },
  suppliers:              { kicker: "Pembelian",      title: "Master Pemasok (Supplier)" },
  "purchase-approval":    { kicker: "Pembelian",      title: "Approval Pembelian" },
  "cash-management":      { kicker: "Pembelian",      title: "Pengelolaan Kas" },
  "purchase-returns":     { kicker: "Pembelian",      title: "Retur Beli (Nota Debit)" },
  "vendor-bills":         { kicker: "Pembelian",      title: "Tagihan Supplier · 3-Way Matching" },
  "landed-cost":          { kicker: "Pembelian",      title: "Landed Cost · Alokasi HPP Roll" },
  "input-tax":            { kicker: "Pembelian",      title: "Faktur Pajak Masukan · PPN Masukan & Rekap" },
  "rfq":                  { kicker: "Pembelian",      title: "RFQ / Quotation · Tender & Banding Harga Supplier" },
  operations:             { kicker: "Gudang",         title: "Operasi Gudang (WMS)" },
  "qc-inspection":        { kicker: "Gudang",         title: "Inspeksi QC · Penerimaan" },
  "inventory-board":      { kicker: "Gudang",         title: "Status Stok & ATP" },
  "stock-buckets":        { kicker: "Gudang",         title: "Stok Multi-Bucket (WIP / Hold / In-transit)" },
  "interco-transfers":    { kicker: "Gudang",         title: "Transfer Antar-Entitas" },
  escalations:            { kicker: "Eskalasi",       title: "Eskalasi Inbound & Outbound" },
  documents:              { kicker: "Dokumen",        title: "Print Center & Labels" },
  reports:                { kicker: "Analitik",       title: "Dashboard & Analytics" },
  costing:                { kicker: "Analitik (BI)",  title: "Margin & HPP (WAC)" },
  // Coming Soon views (semua cs-* pakai kicker Coming Soon)
  "cs-price-list":        { kicker: "Penjualan",      title: "Price List per Customer" },
  "cs-returns":           { kicker: "Penjualan",      title: "Returns & Barang Sisa (BS)" },
  "cs-special-order":     { kicker: "Penjualan",      title: "Special Order (OD)" },
  "cs-suppliers":         { kicker: "Pembelian",      title: "Pemasok (Supplier)" },
  "cs-purchase-approval": { kicker: "Pembelian",      title: "Approval Pembelian" },
  "cs-bom":               { kicker: "Pembelian",      title: "BOM Printing" },
  "cs-kas":               { kicker: "Pembelian",      title: "Pengelolaan Kas" },
  "cs-stock-analytics":   { kicker: "Gudang",         title: "Stock Analytics (Fast/Slow/Dead)" },
  "cs-rfid-lokasi":       { kicker: "RFID",           title: "Lokasi RFID" },
  "cs-rfid-tags":         { kicker: "RFID",           title: "Tags (tag↔item)" },
  "cs-rfid-devices":      { kicker: "RFID",           title: "Devices (Reader / Gate)" },
  "cs-rfid-gate":         { kicker: "RFID",           title: "Gate Monitor" },
  "chart-of-accounts":    { kicker: "Keuangan",       title: "Bagan Akun · Chart of Accounts" },
  "general-ledger":       { kicker: "Keuangan",       title: "Buku Besar · Jurnal Umum" },
  "bank-accounts":        { kicker: "Keuangan",       title: "Kas & Bank" },
  "cs-bank":              { kicker: "Keuangan",       title: "Bank Accounts" },
  "cs-pajak":             { kicker: "Keuangan",       title: "Pajak (PPN / PPH)" },
  "ar-aging":             { kicker: "Keuangan",       title: "AR / Piutang & Aging" },
  "consolidation":        { kicker: "Keuangan",       title: "Konsolidasi Grup vs Per-PT" },
  "cs-closing":           { kicker: "Keuangan",       title: "Tutup Buku (Closing)" },
  "cs-employees":         { kicker: "SDM (HRD)",      title: "Karyawan" },
  "cs-attendance":        { kicker: "SDM (HRD)",      title: "Presensi" },
  "cs-kpi":               { kicker: "SDM (HRD)",      title: "KPI Design" },
  "cs-design-gallery":    { kicker: "SDM (HRD)",      title: "Design Gallery + AI" },
  "cs-bi-sales":          { kicker: "Analitik (BI)",  title: "Dashboard BI Sales" },
  "cs-bi-stock":          { kicker: "Analitik (BI)",  title: "Dashboard BI Stok" },
  "cs-bi-finance":        { kicker: "Analitik (BI)",  title: "Dashboard BI Keuangan" },
  "cs-bi-hrd":            { kicker: "Analitik (BI)",  title: "Dashboard BI SDM" },
};

// ─── FULL IA NAVIGATION STRUCTURE (KN_14 §5.2 + KN_13 Target Grouped Nav) ────
//
// type: "standalone" → item langsung, tidak dalam grup
// type: "group"      → grup yang bisa di-collapse (berisi items[])
//
// item.view  → view yang di-render di App.js (default = item.id)
// item.tab   → WMS tab yang di-aktivasi (hanya untuk operations sub-items)
// item.comingSoon → true = navigasi ke halaman Coming Soon
// item.roles → array role yang boleh melihat item ini

const NAV_STRUCTURE = [

  // ── 0. BERANDA (role landing) ────────────────────────────────────────────────
  {
    type: "standalone",
    id:    "home",
    label: "Beranda",
    icon:  Home,
    roles: ["admin", "sales", "manager", "warehouse"],
    // view di-resolve oleh defaultViewForRole() di App.js
    view:  null,  // App.js ganti dengan defaultViewForRole saat pertama login
  },

  // ── APPROVAL INBOX ───────────────────────────────────────────────────────────
  {
    type: "standalone",
    id:    "approval-inbox",
    label: "Pusat Persetujuan",
    icon:  Bell,
    roles: ["manager", "admin"],
  },

  // ── 1. PENJUALAN ─────────────────────────────────────────────────────────────
  {
    type:       "group",
    groupId:    "penjualan",
    label:      "Penjualan",
    icon:       ShoppingCart,
    roles:      ["admin", "sales", "manager"],
    items: [
      { id: "sales",            label: "POS / Sales Portal",        icon: ShoppingBag,  roles: ["admin", "sales"] },
      { id: "customers-crm",    label: "Pelanggan / CRM",           icon: Users,        roles: ["admin", "sales", "manager"] },
      { id: "orders",           label: "Pesanan Penjualan (SO)",     icon: FileText,     roles: ["admin", "sales", "manager"] },
      { id: "price-approvals",  label: "Approval Harga",            icon: BadgePercent, roles: ["admin", "sales", "manager"] },
      { id: "tax-invoices",     label: "Faktur Pajak Jual",         icon: Receipt,      roles: ["admin", "sales", "manager"] },
      { id: "returns",         label: "Returns & Barang Sisa",  icon: RotateCcw,    roles: ["admin", "sales", "manager"] },
      { id: "special-orders",   label: "Special Order (OD)",        icon: Star,         roles: ["admin", "sales", "manager"] },
      { id: "pricelist",        label: "Pricelist per-PT",          icon: Tag,          roles: ["admin", "manager"] },
      { id: "product-templates", label: "Template & Varian",         icon: Layers3,      roles: ["admin", "manager"] },
      { id: "cs-price-list",    label: "Price List per Customer",   icon: Tag,          roles: ["admin", "manager"], comingSoon: true },
    ],
  },

  // ── 2. PEMBELIAN ─────────────────────────────────────────────────────────────
  {
    type:       "group",
    groupId:    "pembelian",
    label:      "Pembelian",
    icon:       ClipboardList,
    roles:      ["admin", "manager", "warehouse"],
    items: [
      { id: "purchasing",             label: "Pesanan Pembelian (PO)", icon: ClipboardList, roles: ["admin", "manager"] },
      { id: "blanket-po",             label: "Blanket / Kontrak PO",    icon: FileStack,     roles: ["admin", "manager"] },
      { id: "purchase-requisitions",  label: "Purchase Requisition",    icon: ClipboardCheck, roles: ["admin", "manager", "warehouse"] },
      { id: "rfq",                    label: "RFQ / Quotation",         icon: ClipboardCheck, roles: ["admin", "manager", "warehouse"] },
      { id: "reorder",                label: "Saran Reorder",           icon: Target,         roles: ["admin", "manager"] },
      { id: "suppliers",              label: "Pemasok (Supplier)",      icon: Truck,         roles: ["admin", "manager"] },
      { id: "purchase-approval",      label: "Approval Pembelian",      icon: BadgePercent,  roles: ["admin", "manager"] },
      { id: "purchase-returns",       label: "Retur Beli",              icon: RotateCcw,     roles: ["admin", "manager", "warehouse"] },
      { id: "vendor-bills",           label: "Tagihan Supplier",        icon: Receipt,       roles: ["admin", "manager", "warehouse"] },
      { id: "landed-cost",            label: "Landed Cost (HPP)",       icon: Ship,          roles: ["admin", "manager", "warehouse"] },
      { id: "input-tax",              label: "Faktur Pajak Masukan",    icon: Percent,       roles: ["admin", "manager", "warehouse"] },
      { id: "cs-bom",                 label: "BOM Printing",            icon: Printer,       roles: ["admin"],            comingSoon: true },
      { id: "cash-management",        label: "Pengelolaan Kas",         icon: Wallet,        roles: ["admin", "manager"] },
    ],
  },

  // ── 3. GUDANG ────────────────────────────────────────────────────────────────
  {
    type:       "group",
    groupId:    "gudang",
    label:      "Gudang",
    icon:       Warehouse,
    roles:      ["admin", "warehouse", "manager", "sales"],
    items: [
      { id: "wms-stok",             label: "Stok & Inventori",          icon: Layers,         roles: ["admin", "warehouse", "manager", "sales"], view: "operations",      tab: "stok" },
      { id: "wms-inbound",          label: "Inbound / Penerimaan",      icon: PackageCheck,   roles: ["admin", "warehouse", "manager"],           view: "operations",      tab: "inbound" },
      { id: "qc-inspection",        label: "Inspeksi QC",               icon: ShieldCheck,    roles: ["admin", "warehouse", "manager"] },
      { id: "wms-outbound",         label: "Outbound / Pengiriman",     icon: PackageMinus,   roles: ["admin", "warehouse", "manager"],           view: "operations",      tab: "outbound" },
      { id: "wms-transfer",         label: "Transfer Antar Gudang",     icon: ArrowLeftRight, roles: ["admin", "warehouse", "manager"],           view: "operations",      tab: "transfer" },
      { id: "wms-cycle",            label: "Cycle Count",               icon: ClipboardCheck, roles: ["admin", "warehouse", "manager"],           view: "operations",      tab: "cycle" },
      { id: "inventory-board",      label: "Status Stok & ATP",         icon: Boxes,          roles: ["admin", "warehouse", "manager", "sales"] },
      { id: "stock-buckets",        label: "Stok Multi-Bucket",         icon: Layers3,        roles: ["admin", "warehouse", "manager"] },
      { id: "interco-transfers",    label: "Transfer Antar-Entitas",    icon: ArrowLeftRight, roles: ["admin", "warehouse", "manager"] },
      { id: "cs-stock-analytics",   label: "Stock Analytics",           icon: TrendingUp,     roles: ["admin", "manager"], comingSoon: true },
    ],
  },

  // ── 4. RFID & TRACEABILITY ───────────────────────────────────────────────────
  {
    type:       "group",
    groupId:    "rfid",
    label:      "RFID & Traceability",
    icon:       Cpu,
    roles:      ["admin", "warehouse"],
    items: [
      { id: "cs-rfid-lokasi",  label: "Lokasi RFID",          icon: MapPin,  roles: ["admin", "warehouse"], comingSoon: true },
      { id: "cs-rfid-tags",    label: "Tags (tag↔item)",      icon: Tag,     roles: ["admin", "warehouse"], comingSoon: true },
      { id: "cs-rfid-devices", label: "Devices (Reader/Gate)",icon: Wifi,    roles: ["admin"],              comingSoon: true },
      { id: "cs-rfid-gate",    label: "Gate Monitor",         icon: Cpu,     roles: ["admin", "warehouse"], comingSoon: true },
    ],
  },

  // ── 5. KEUANGAN ─────────────────────────────────────────────────────────────
  {
    type:       "group",
    groupId:    "keuangan",
    label:      "Keuangan",
    icon:       DollarSign,
    roles:      ["admin", "manager"],
    items: [
      { id: "ar-aging", label: "AR / Piutang & Aging", icon: TrendingDown, roles: ["admin", "manager"] },
      { id: "consolidation", label: "Konsolidasi Grup", icon: Landmark, roles: ["admin", "manager"] },
      { id: "chart-of-accounts", label: "Chart of Accounts",   icon: BookOpen,  roles: ["admin", "manager"] },
      { id: "general-ledger",    label: "Jurnal / Buku Besar",  icon: FileStack, roles: ["admin", "manager"] },
      { id: "bank-accounts", label: "Kas & Bank",     icon: CreditCard,   roles: ["admin", "manager"] },
      { id: "cs-pajak",   label: "Pajak (PPN / PPH)",    icon: Percent,      roles: ["admin", "manager"], comingSoon: true },
      { id: "cs-closing", label: "Tutup Buku (Closing)", icon: CalendarX,    roles: ["admin"],            comingSoon: true },
    ],
  },

  // ── 6. SDM (HRD) ────────────────────────────────────────────────────────────
  {
    type:       "group",
    groupId:    "hrd",
    label:      "SDM (HRD)",
    icon:       Users,
    roles:      ["admin", "manager"],
    items: [
      { id: "cs-employees",     label: "Karyawan",          icon: UserCheck, roles: ["admin", "manager"], comingSoon: true },
      { id: "cs-attendance",    label: "Presensi",          icon: Clock,     roles: ["admin", "manager"], comingSoon: true },
      { id: "cs-kpi",           label: "KPI Design",        icon: Target,    roles: ["admin", "manager"], comingSoon: true },
      { id: "cs-design-gallery",label: "Design Gallery + AI",icon: Palette,  roles: ["admin", "manager"], comingSoon: true },
    ],
  },

  // ── 7. ANALITIK (BI) ─────────────────────────────────────────────────────────
  {
    type:       "group",
    groupId:    "analitik",
    label:      "Analitik (BI)",
    icon:       BarChart3,
    roles:      ["admin", "manager"],
    items: [
      { id: "reports",       label: "Dashboard",       icon: BarChart3,  roles: ["admin", "manager"] },
      { id: "costing",       label: "Margin & HPP",    icon: Percent,    roles: ["admin", "manager"] },
      { id: "cs-bi-sales",   label: "BI Sales",        icon: TrendingUp, roles: ["admin", "manager"], comingSoon: true },
      { id: "cs-bi-stock",   label: "BI Stok",         icon: PieChart,   roles: ["admin", "manager"], comingSoon: true },
      { id: "cs-bi-finance", label: "BI Keuangan",     icon: LineChart,  roles: ["admin", "manager"], comingSoon: true },
      { id: "cs-bi-hrd",     label: "BI SDM",          icon: BarChart2,  roles: ["admin", "manager"], comingSoon: true },
    ],
  },

  // ── 8. DOKUMEN & PRINT ──────────────────────────────────────────────────────
  {
    type:       "group",
    groupId:    "dokumen",
    label:      "Dokumen & Print",
    icon:       FileText,
    roles:      ["admin", "sales", "warehouse", "manager"],
    items: [
      { id: "documents", label: "Print Center", icon: Printer, roles: ["admin", "sales", "warehouse", "manager"] },
    ],
  },

  // ── 9. ADMIN & MASTER DATA ───────────────────────────────────────────────────
  {
    type:       "group",
    groupId:    "admin-data",
    label:      "Admin & Master Data",
    icon:       Settings,
    roles:      ["admin"],
    items: [
      { id: "admin", label: "Master Data & Audit", icon: Settings, roles: ["admin"] },
      { id: "approval-rules", label: "Approval Rules", icon: Settings, roles: ["admin"] },
    ],
  },

  // ── 10. ESKALASI (standalone bawah) ─────────────────────────────────────────
  {
    type:  "standalone",
    id:    "escalations",
    label: "Eskalasi",
    icon:  AlertTriangle,
    roles: ["admin", "warehouse", "manager"],
    view:  "escalations",
  },
];

// ─── BUILD GROUPED NAVIGATION — filter per role; comingSoon → grup "Segera Hadir" ──
export function buildNavGroups(role, opts = {}) {
  const showComingSoon = opts.showComingSoon !== false; // default: tampilkan grup "Segera Hadir"
  const result = [];
  const comingSoonItems = [];
  for (const entry of NAV_STRUCTURE) {
    if (!entry.roles.includes(role)) continue;
    if (entry.type === "standalone") {
      if (entry.comingSoon) comingSoonItems.push(entry);
      else result.push(entry);
    } else if (entry.type === "group") {
      const roleItems = entry.items.filter(item => item.roles.includes(role));
      const liveItems = roleItems.filter(item => !item.comingSoon);
      const soonItems = roleItems.filter(item => item.comingSoon);
      if (liveItems.length > 0) result.push({ ...entry, items: liveItems });
      soonItems.forEach(item => comingSoonItems.push(item));
    }
  }
  // EPIC 0 — konsolidasikan semua item comingSoon ke 1 grup "Segera Hadir" (collapsed)
  if (showComingSoon && comingSoonItems.length > 0) {
    result.push({
      type: "group",
      groupId: "segera-hadir",
      label: "Segera Hadir",
      icon: Clock,
      roles: [role],
      comingSoonGroup: true,
      items: comingSoonItems,
    });
  }
  return result;
}

// Backward compat: flat array untuk komponen lama jika perlu
export function buildNavigation(role) {
  const groups = buildNavGroups(role);
  const flat = [];
  for (const entry of groups) {
    if (entry.type === "standalone") flat.push(entry);
    else entry.items.forEach(item => flat.push(item));
  }
  return flat;
}

// ─── ROLE-HOME REGISTRY (F5) — landing per role (config-driven; override via settings.role_home) ──
export const ROLE_HOME_REGISTRY = {
  admin:     { view: "admin-home", navId: "home" },
  manager:   { view: "reports",    navId: "reports" },
  warehouse: { view: "operations", navId: "wms-stok" },
  sales:     { view: "sales-home", navId: "home" },
};
export function defaultViewForRole(role, registry = ROLE_HOME_REGISTRY) {
  return (registry[role] || registry.sales).view;
}
export function defaultNavIdForRole(role, registry = ROLE_HOME_REGISTRY) {
  return (registry[role] || registry.sales).navId;
}

// ─── VIEW → NAV ID INDEX (poin 11: highlight sidebar = TURUNAN dari activeView, satu SSOT) ──
const VIEW_NAV_INDEX = (() => {
  const idx = {};
  for (const entry of NAV_STRUCTURE) {
    if (entry.type === "standalone") {
      const v = entry.view || entry.id;
      (idx[v] = idx[v] || []).push(entry.id);
    } else if (entry.type === "group") {
      (entry.items || []).forEach((item) => {
        const v = item.view || item.id;
        (idx[v] = idx[v] || []).push(item.id);
      });
    }
  }
  return idx;
})();

/**
 * Resolusi navId aktif dari activeView (poin 11 — cegah sidebar desync saat navigasi
 * di luar sidebar, mis. setelah submit order / klik dokumen / CTA).
 * - Pertahankan currentNavId bila masih valid untuk view ini (kasus operations multi-tab).
 * - Jika view tak terdaftar di nav (mis. admin-home/sales-home) → pakai navId role-home.
 */
export function resolveActiveNavId(activeView, currentNavId, role) {
  const candidates = VIEW_NAV_INDEX[activeView];
  if (currentNavId && candidates && candidates.includes(currentNavId)) return currentNavId;
  if (candidates && candidates.length) return candidates[0];
  const home = ROLE_HOME_REGISTRY[role];
  if (home && home.view === activeView) return home.navId;
  return currentNavId || "home";
}

// Smart guidance CTA.
export const GUIDANCE_MAP = {
  admin:                { label: "Audit",       target: "admin" },
  sales:                { label: "Cari Produk", target: "sales" },
  orders:               { label: "Review",      target: "orders" },
  purchasing:           { label: "Buat PO",     target: "purchasing" },
  operations:           { label: "WMS",         target: "operations" },
  "inventory-board":    { label: "Cek ATP",     target: "inventory-board" },
  "interco-transfers":  { label: "Approve",     target: "interco-transfers" },
  escalations:          { label: "Resolve",     target: "escalations" },
  documents:            { label: "Print",       target: "documents" },
};
