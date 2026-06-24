import { useState, useEffect } from "react";
import "./App.css";
import { LoginScreen, MetricCard, Sidebar, TopBar } from "./components/CoreWidgets";
import { formatQty } from "./utils/formatters";
import { SalesPortal } from "./features/sales/SalesPortal";
import useIsMobile from "./hooks/useIsMobile";
import MobileSalesApp from "./features/sales/mobile/MobileSalesApp";
import PriceApprovals from "./features/sales/PriceApprovals";
import OrdersView from "./features/orders/OrdersView";
import CrmView from "./features/crm/CrmView";
import OperationsView from "./features/wms/OperationsView";
import QCInspection from "./features/wms/QCInspection";
import DocumentsView from "./features/documents/DocumentsView";
import AdminView from "./features/admin/AdminView";
import CostingView from "./features/costing/CostingView";
import ARAgingView from "./features/finance/ARAgingView";
import BankAccountsView from "./features/finance/BankAccountsView";
import ChartOfAccounts from "./features/finance/ChartOfAccounts";
import GeneralLedger from "./features/finance/GeneralLedger";
import ConsolidationDashboard from "./features/finance/ConsolidationDashboard";
import DetailDrawer from "./components/DetailDrawer";
import TourMenu from "./components/TourMenu";
import OnboardingPanel from "./components/OnboardingPanel";
import EntitySwitcher from "./components/EntitySwitcher";
import NotificationCenter from "./components/NotificationCenter";
import { PAGE_META, GUIDANCE_MAP, buildNavGroups, defaultNavIdForRole, defaultViewForRole, resolveActiveNavId } from "./config/navigationConfig";
import ComingSoon from "./features/ComingSoon";
import { useAppActions } from "./hooks/useAppActions";
import { setActiveEntity } from "./services/apiClient";
import ManagerDashboard from "./features/manager/ManagerDashboard";
import SalesHome from "./features/home/SalesHome";
import AdminHome from "./features/home/AdminHome";
import PurchaseOrderManagement from "./features/admin/PurchaseOrderManagement";
import BlanketPOView from "./features/purchasing/BlanketPOView";
import InventoryStatusBoard from "./features/inventory/InventoryStatusBoard";
import StockBucketsView from "./features/inventory/StockBucketsView";
import InterCompanyTransfers from "./features/transfers/InterCompanyTransfers";
import EscalationManagement from "./features/manager/EscalationManagement";
import GuidedTour from "./components/GuidedTour";
import TaxInvoices from "./features/finance/TaxInvoices";
import SalesReturns from "./features/sales/SalesReturns";
import SpecialOrders from "./features/sales/SpecialOrders";
import PricelistView from "./features/sales/PricelistView";
import ProductTemplatesView from "./features/sales/ProductTemplatesView";
import ApprovalInbox from "./features/approvals/ApprovalInbox";
import ApprovalRulesSettings from "./features/settings/ApprovalRulesSettings";
import SuppliersView from "./features/purchasing/SuppliersView";
import PurchaseApprovalView from "./features/purchasing/PurchaseApprovalView";
import CashManagementView from "./features/purchasing/CashManagementView";
import PurchaseReturns from "./features/purchasing/PurchaseReturns";
import VendorBillsView from "./features/purchasing/VendorBillsView";
import LandedCostView from "./features/purchasing/LandedCostView";
import InputTaxView from "./features/purchasing/InputTaxView";
import RFQView from "./features/purchasing/RFQView";
import PurchaseRequisitions from "./features/purchasing/PurchaseRequisitions";
import ReorderSuggestions from "./features/purchasing/ReorderSuggestions";
import {
  Archive,
  Boxes,
  Building2,
  Clock3,
  PackageCheck,
  Sparkles,
  Warehouse,
} from "lucide-react";


function App() {
  const [activeView, setActiveView] = useState(() => {
    const saved = JSON.parse(localStorage.getItem("kn_user") || "null");
    return saved ? defaultViewForRole(saved.role) : "sales";
  });
  const [activeNavId, setActiveNavId] = useState(() => {
    const saved = JSON.parse(localStorage.getItem("kn_user") || "null");
    return saved ? defaultNavIdForRole(saved.role) : "sales";
  });
  const [wmsInitialTab, setWmsInitialTab] = useState("stok");
  const [data, setData] = useState({ products: [], customers: [], orders: [], warehouses: [], metrics: {} });
  const [movements, setMovements] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [users, setUsers] = useState([]);
  const [uoms, setUoms] = useState([]);
  const [tasks, setTasks] = useState([]);
  const [onboarding, setOnboarding] = useState(null);
  const [showOnboarding, setShowOnboarding] = useState(false);
  const [permissions, setPermissions] = useState({ matrix: {}, actions: [] });
  const [auditLogs, setAuditLogs] = useState([]);
  const [auditFilters, setAuditFilters] = useState({ actor: "", module: "", action: "", date_from: "", date_to: "" });
  
  // Guided Tour state
  const [activeTour, setActiveTour] = useState(null);
  const [showTourMenu, setShowTourMenu] = useState(false);
  const [previewHtml, setPreviewHtml] = useState("");
  const [activeDetail, setActiveDetail] = useState(null);
  // EPIC6 — deep-link dokumen: { focus_type, focus_id } untuk auto-open di view tujuan.
  const [focusDoc, setFocusDoc] = useState(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  // Desktop: sidebar bisa di-hide/show (persist). Mobile (<=900px) pakai drawer (sidebarOpen).
  const [sidebarCollapsed, setSidebarCollapsed] = useState(
    () => typeof window !== "undefined" && localStorage.getItem("kn_sidebar_collapsed") === "1"
  );
  const handleToggleSidebar = () => {
    if (typeof window !== "undefined" && window.innerWidth <= 900) {
      setSidebarOpen((v) => !v);
    } else {
      setSidebarCollapsed((v) => {
        const nv = !v;
        try { localStorage.setItem("kn_sidebar_collapsed", nv ? "1" : "0"); } catch (_) { /* noop */ }
        return nv;
      });
    }
  };
  const [user, setUser] = useState(() => JSON.parse(localStorage.getItem("kn_user") || "null"));
  const [token, setToken] = useState(() => localStorage.getItem("kn_token") || "");
  const [selectedProduct, setSelectedProduct] = useState(null);
  const [breakdown, setBreakdown] = useState(null);
  const [cart, setCart] = useState([]);
  const [selectedCustomer, setSelectedCustomer] = useState(null);
  const [selectedAddress, setSelectedAddress] = useState("");
  const [search, setSearch] = useState("");
  const [notice, setNotice] = useState("Sistem siap. Stok reservation dikunci 3 hari.");
  const [lastDocument, setLastDocument] = useState(null);
  const [lastLabel, setLastLabel] = useState(null);
  const [loading, setLoading] = useState(false);

  // Multi-Entity + Notification Center (Fase 0)
  const [entities, setEntities] = useState([]);
  const [entityContext, setEntityContext] = useState(() => JSON.parse(localStorage.getItem("kn_entity_ctx") || "null"));
  const [selectedEntity, setSelectedEntity] = useState(() => localStorage.getItem("kn_entity") || "all");
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);

  // Configuration Foundation (Fase 1A) consumed by Sales/Orders (Fase 1B)
  const [settings, setSettings] = useState({});
  const [paymentTerms, setPaymentTerms] = useState([]);

  // F-6 — device-aware: sales di HP dapat tampilan mobile-first dedicated.
  const isMobile = useIsMobile();
  const [forceDesktop, setForceDesktop] = useState(() => localStorage.getItem("kn_force_desktop") === "1");
  // Test affordance (default OFF): set localStorage kn_force_mobile="1" untuk merender
  // MobileSalesApp di lebar berapa pun (verifikasi UI mobile saat automasi memaksa desktop).
  const [forceMobile] = useState(() => typeof window !== "undefined" && localStorage.getItem("kn_force_mobile") === "1");

  const onSelectEntity = (id) => {
    setSelectedEntity(id);
    localStorage.setItem("kn_entity", id);
    setActiveEntity(id);  // sinkron header X-Entity-Id sebelum view anak re-fetch
  };

  // Pastikan header X-Entity-Id ter-set sejak awal (restore session / refresh).
  useEffect(() => { setActiveEntity(selectedEntity || "all"); }, [selectedEntity]);

  // Auto-hide notice transien (mis. 'Login berhasil ...') agar tidak menetap permanen di TopBar.
  useEffect(() => {
    if (!notice) return undefined;
    const t = setTimeout(() => setNotice(""), 5000);
    return () => clearTimeout(t);
  }, [notice]);

  // Switcher: cross-entity (admin/manager) lihat SEMUA entitas aktif; single-entity terkunci.
  const canSwitchEntity = entityContext
    ? entityContext.can_switch_entity !== false
    : entities.length > 1;
  const allowedEntityIds = entityContext?.allowed_entity_ids || entities.map((e) => e.id);
  const switcherEntities = canSwitchEntity
    ? entities
    : entities.filter((e) => allowedEntityIds.includes(e.id));

  // All async actions + side-effects live in this hook (SSOT for business logic).
  const actions = useAppActions({
    // values
    user, token, auditFilters, selectedCustomer, selectedAddress, cart, data, selectedEntity,
    // setters
    setUser, setToken, setActiveView, setNotice, setOnboarding, setShowOnboarding,
    setData, setTemplates, setUoms, setMovements, setTasks, setUsers, setPermissions, setAuditLogs,
    setSelectedCustomer, setSelectedAddress, setSelectedProduct, setBreakdown,
    setCart, setLastDocument, setLastLabel, setPreviewHtml,
    setActiveDetail, setLoading, setEntities, setNotifications, setUnreadCount,
    setSettings, setPaymentTerms, setEntityContext, setSelectedEntity,
    setActiveNavId,
  });
  const {
    login, logout, showMetricDetail, loadAll,
    inspectProduct, addToCart, createCustomer, submitOrder, mutateOrder,
    payInvoice, releaseReservation, markDelivered, generateDocument, generateLabel,
    approvePurchaseOrder,
    adminCreate, adminPatch, adminDelete, importMaster, exportMaster,
    updatePermissions, seedDemo, previewTemplate, refreshAudit,
    createInboundTask, createOutboundTasks, scanTask, advanceTask,
    markNotificationRead, markAllNotificationsRead, generateNotifications,
    approveFromNotification,
    issueTaxInvoice,
  } = actions;

  // \u2500\u2500\u2500 Navigation handler: receives { navId, view, tab } from grouped Sidebar \u2500\u2500\u2500
  const handleNavSelect = (navId, view, tab) => {
    if (navId === "home") {
      setActiveView(defaultViewForRole(user?.role));
      setActiveNavId(defaultNavIdForRole(user?.role));
    } else {
      setActiveNavId(navId);
      setActiveView(view || navId);
      if (tab) setWmsInitialTab(tab);
    }
    setSidebarOpen(false);
  };

  // ─── EPIC6 — deep-link dokumen terkait (Process Timeline / Document Hub) ───
  // Navigasi in-app ke view tujuan + set focusDoc agar view target auto-open dokumen.
  const openDocument = (link) => {
    if (!link || !link.view) return;
    handleNavSelect(link.nav_id || link.view, link.view);
    if (link.focus_id) setFocusDoc({ focus_type: link.focus_type, focus_id: link.focus_id });
    else setFocusDoc(null);
  };

  const navGroups = buildNavGroups(user?.role, { showComingSoon: settings?.ui?.show_coming_soon !== false });
  const isComingSoon = typeof activeView === "string" && activeView.startsWith("cs-");
  // BUG #1/#2 fix: MetricCards & Onboarding hanya tampil di halaman landing (Beranda) per role
  const HOME_VIEWS = ["admin", "sales", "reports", "operations"];
  const isHomeView = HOME_VIEWS.includes(activeView);

  const nav = navGroups; // passed to new Sidebar (groups prop)
  // Poin 11 — highlight sidebar SELALU turunan dari activeView (cegah desync saat navigasi non-sidebar).
  const effectiveNavId = resolveActiveNavId(activeView, activeNavId, user?.role);

  if (!user) return <LoginScreen onLogin={login} notice={notice} />;

  // F-6 — Sales di perangkat mobile → tampilan mobile-first dedicated (device-aware).
  // 'Tampilan Desktop' (forceDesktop) memberi escape-hatch ke antarmuka penuh.
  if (user.role === "sales" && (isMobile || forceMobile) && !forceDesktop) {
    return (
      <MobileSalesApp
        user={user}
        token={token}
        onLogout={logout}
        data={data}
        loading={loading}
        cart={cart}
        setCart={setCart}
        onInspect={inspectProduct}
        onAdd={addToCart}
        selectedCustomer={selectedCustomer}
        setSelectedCustomer={setSelectedCustomer}
        selectedAddress={selectedAddress}
        setSelectedAddress={setSelectedAddress}
        onSubmitOrder={submitOrder}
        paymentTerms={paymentTerms}
        selectedEntity={selectedEntity}
        entities={entities}
        notifications={notifications}
        unreadCount={unreadCount}
        onMarkAllRead={markAllNotificationsRead}
        onForceDesktop={() => { localStorage.setItem("kn_force_desktop", "1"); setForceDesktop(true); }}
      />
    );
  }

  const pageMeta = PAGE_META[activeView] || { kicker: "Workspace", title: "Kain Nusantara" };
  const guidance = GUIDANCE_MAP[activeView];

  return (
    <div className={`app-shell layout-grid ${sidebarCollapsed ? "sidebar-hidden" : ""}`}>
      <a className="skip-link" href="#main-content">Skip to content</a>
      <Sidebar
        groups={nav}
        activeNavId={effectiveNavId}
        activeView={activeView}
        onSelect={handleNavSelect}
        user={user}
        onLogout={logout}
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
      />
      <div className="app-main">
        <TopBar
          title={pageMeta.title}
          kicker={pageMeta.kicker}
          onToggleSidebar={handleToggleSidebar}
          onSync={loadAll}
          syncing={loading}
          notice={notice}
          infoCta={guidance ? { label: guidance.label, onClick: () => setActiveView(guidance.target) } : null}
          entitySwitcher={<EntitySwitcher entities={switcherEntities} value={selectedEntity} onChange={onSelectEntity} canSwitch={canSwitchEntity} />}
          notificationCenter={
            <NotificationCenter
              notifications={notifications}
              unreadCount={unreadCount}
              canGenerate={["admin", "manager"].includes(user?.role)}
              currentUserRole={user?.role}
              onMarkRead={markNotificationRead}
              onMarkAll={markAllNotificationsRead}
              onGenerate={generateNotifications}
              onApprove={approveFromNotification}
              onNavigate={(target) => setActiveView(target)}
            />
          }
        />
        <main id="main-content" className="mx-auto w-full max-w-[1600px] px-4 py-4 md:px-5 md:py-5">
          <section data-testid="metrics-row" className="grid gap-3 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-5 no-print">
            {isHomeView && <>
            <MetricCard testId="metric-products" icon={Archive} label="Produk Aktif" value={data.metrics?.products || 0} tone="rgba(0,122,255,.12)" hint="Buka katalog" onClick={() => showMetricDetail("products")} />
            <MetricCard testId="metric-available" icon={Boxes} label="Available Qty" value={formatQty(data.metrics?.available_qty)} tone="rgba(52,199,89,.14)" hint="Lihat stok" onClick={() => showMetricDetail("available")} />
            <MetricCard testId="metric-reserved" icon={Clock3} label="Reserved Qty" value={formatQty(data.metrics?.reserved_qty)} tone="rgba(175,82,222,.14)" hint="Buka orders" onClick={() => showMetricDetail("reserved")} />
            <MetricCard testId="metric-orders" icon={PackageCheck} label="Active Orders" value={data.metrics?.active_orders || 0} tone="rgba(255,149,0,.14)" hint="Control room" onClick={() => showMetricDetail("orders")} />
            <MetricCard testId="metric-warehouses" icon={Building2} label="Gudang" value={data.metrics?.warehouses || 0} tone="rgba(60,60,67,.10)" hint="Buka WMS" onClick={() => showMetricDetail("warehouses")} />
            </>}
          </section>

          <div className="md:hidden mt-3">
            <div data-testid="system-notice-mobile" className="info-ribbon">
              <Sparkles size={13} className="ribbon-icon" />
              <span>{notice}</span>
            </div>
          </div>

          <DetailDrawer detail={activeDetail} onClose={() => setActiveDetail(null)} onNavigate={(target) => { setActiveView(target); setActiveDetail(null); }} />

          {/* Onboarding Checklist Panel — hanya di home view (BUG #2 fix) */}
          {showOnboarding && isHomeView && (
            <OnboardingPanel
              onboarding={onboarding}
              onDismiss={() => setShowOnboarding(false)}
              onUpdate={setOnboarding}
            />
          )}

          <div className="mt-4 md:mt-5">
            {activeView === "admin" && <AdminView data={data} loading={loading} users={users} uoms={uoms} templates={templates} entities={entities} permissions={permissions} previewHtml={previewHtml} auditLogs={auditLogs} auditFilters={auditFilters} setAuditFilters={setAuditFilters} onAdminCreate={adminCreate} onAdminPatch={adminPatch} onAdminDelete={adminDelete} onImportMaster={importMaster} onExportMaster={exportMaster} onUpdatePermissions={updatePermissions} onPreviewTemplate={previewTemplate} onRefreshAudit={refreshAudit} onShowDetail={setActiveDetail} onSeedDemo={seedDemo} />}
            {activeView === "reports" && <ManagerDashboard token={token} selectedEntity={selectedEntity} />}
            {activeView === "costing" && <CostingView selectedEntity={selectedEntity} />}
            {activeView === "ar-aging" && <ARAgingView selectedEntity={selectedEntity} />}
            {activeView === "bank-accounts" && <BankAccountsView selectedEntity={selectedEntity} />}
            {activeView === "chart-of-accounts" && <ChartOfAccounts />}
            {activeView === "general-ledger" && <GeneralLedger />}
            {activeView === "consolidation" && <ConsolidationDashboard entities={entities} />}
            {activeView === "sales-home" && <SalesHome token={token} user={user} onNavigate={(target) => handleNavSelect(target, target)} />}
            {activeView === "admin-home" && <AdminHome token={token} entities={entities} selectedEntity={selectedEntity} onNavigate={(target) => handleNavSelect(target, target)} />}
            {activeView === "sales" && <SalesPortal data={data} loading={loading} selectedProduct={selectedProduct} breakdown={breakdown} onInspect={inspectProduct} onAdd={addToCart} cart={cart} setCart={setCart} selectedCustomer={selectedCustomer} setSelectedCustomer={setSelectedCustomer} selectedAddress={selectedAddress} setSelectedAddress={setSelectedAddress} onCreateCustomer={createCustomer} onSubmitOrder={submitOrder} search={search} setSearch={setSearch} onShowDetail={setActiveDetail} settings={settings} paymentTerms={paymentTerms} selectedEntity={selectedEntity} entities={entities} />}
            {activeView === "inventory-board" && <InventoryStatusBoard selectedEntity={selectedEntity} entities={entities} />}
            {activeView === "stock-buckets" && <StockBucketsView entities={entities} currentUser={user} />}
            {activeView === "price-approvals" && <PriceApprovals currentUser={user} />}
            {activeView === "interco-transfers" && <InterCompanyTransfers currentUser={user} />}
            {activeView === "orders" && <OrdersView orders={data.orders || []} loading={loading} user={user} onShowDetail={setActiveDetail} onIssueTaxInvoice={issueTaxInvoice} onSubmitForApproval={(id) => mutateOrder(`/sales-orders/${id}/submit-for-approval`, (order) => order.status === "approved" ? `${order.number} auto-approved (di bawah threshold).` : `${order.number} dikirim untuk approval (butuh ${order.required_approval_role || "approver"}).`)} onApprove={(id) => mutateOrder(`/sales-orders/${id}/approve`, (order) => `${order.number} approved.`)} onConfirm={(id) => mutateOrder(`/sales-orders/${id}/confirm`, (order) => `${order.number} confirmed.`)} onCancel={(id) => mutateOrder(`/sales-orders/${id}/cancel`, (order) => `${order.number} dibatalkan, stok unlock.`)} onPay={payInvoice} onGenerateDocument={generateDocument} onReleaseReservation={releaseReservation} onMarkDelivered={markDelivered} focusDoc={focusDoc} onClearFocus={() => setFocusDoc(null)} onOpenDocument={openDocument} />}
            {activeView === "tax-invoices" && <TaxInvoices currentUser={user} />}
            {activeView === "returns" && <SalesReturns currentUser={user} />}
            {activeView === "special-orders" && <SpecialOrders currentUser={user} />}
            {activeView === "pricelist" && <PricelistView entities={entities} selectedEntity={selectedEntity} currentUser={user} />}
            {activeView === "product-templates" && <ProductTemplatesView currentUser={user} />}
            {activeView === "customers-crm" && <CrmView currentUser={user} selectedEntity={selectedEntity} />}
            {activeView === "approval-inbox" && <ApprovalInbox currentUser={user} onNavigate={(navId, view, tab) => handleNavSelect(navId, view, tab)} />}
            {activeView === "approval-rules" && <ApprovalRulesSettings currentUser={user} />}
            {activeView === "purchasing" && <PurchaseOrderManagement user={user} onApprovePO={approvePurchaseOrder} focusDoc={focusDoc} onClearFocus={() => setFocusDoc(null)} onOpenDocument={openDocument} />}
            {activeView === "blanket-po" && <BlanketPOView currentUser={user} selectedEntity={selectedEntity} />}
            {activeView === "suppliers" && <SuppliersView currentUser={user} selectedEntity={selectedEntity} />}
            {activeView === "purchase-approval" && <PurchaseApprovalView currentUser={user} selectedEntity={selectedEntity} />}
            {activeView === "cash-management" && <CashManagementView currentUser={user} selectedEntity={selectedEntity} />}
            {activeView === "purchase-returns" && <PurchaseReturns currentUser={user} selectedEntity={selectedEntity} />}
            {activeView === "vendor-bills" && <VendorBillsView currentUser={user} selectedEntity={selectedEntity} />}
            {activeView === "landed-cost" && <LandedCostView currentUser={user} selectedEntity={selectedEntity} />}
            {activeView === "input-tax" && <InputTaxView currentUser={user} selectedEntity={selectedEntity} />}
            {activeView === "rfq" && <RFQView currentUser={user} selectedEntity={selectedEntity} />}
            {activeView === "purchase-requisitions" && <PurchaseRequisitions currentUser={user} selectedEntity={selectedEntity} />}
            {activeView === "reorder" && <ReorderSuggestions currentUser={user} selectedEntity={selectedEntity} />}
            {activeView === "operations" && <OperationsView data={data} movements={movements} tasks={tasks} entities={entities} selectedEntity={selectedEntity} onGenerateLabel={generateLabel} onCreateInboundTask={createInboundTask} onCreateOutboundTasks={createOutboundTasks} onScanTask={scanTask} onAdvanceTask={advanceTask} onShowDetail={setActiveDetail} token={token} user={user} defaultTab={wmsInitialTab} />}
            {activeView === "qc-inspection" && <QCInspection currentUser={user} selectedEntity={selectedEntity} />}
            {isComingSoon && <ComingSoon title={pageMeta.title} kicker={pageMeta.kicker} onBack={() => handleNavSelect(defaultNavIdForRole(user?.role), defaultViewForRole(user?.role))} />}
            {activeView === "escalations" && <EscalationManagement user={user} />}
            {activeView === "documents" && <DocumentsView templates={templates} loading={loading} lastDocument={lastDocument} lastLabel={lastLabel} onGenerateLabel={generateLabel} products={data.products || []} />}
          </div>
        </main>
      </div>
      
      {/* Guided Tour Component */}
      {activeTour && (
        <GuidedTour
          isActive={true}
          onClose={() => setActiveTour(null)}
          steps={activeTour.steps}
          tourId={activeTour.id}
          onComplete={() => {
            setActiveTour(null);
          }}
        />
      )}
      
      {/* Floating Help Button */}
      <TourMenu
        userRole={user?.role}
        showMenu={showTourMenu}
        onToggleMenu={() => setShowTourMenu(!showTourMenu)}
        onSelectTour={(tour) => {
          setActiveTour(tour);
          setShowTourMenu(false);
        }}
      />
    </div>
  );
}

export default App;