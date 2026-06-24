import { Bell, Check, CheckCheck, RefreshCw, AlertTriangle, Info, X, CheckCircle2, Loader2 } from "lucide-react";
import { useState, useRef, useEffect } from "react";

const SEVERITY_ICON = { warning: AlertTriangle, critical: AlertTriangle, info: Info };
const ROLE_RANK = { sales: 1, warehouse: 1, manager: 2, admin: 3 };
const canActOn = (userRole, requiredRole) =>
  (ROLE_RANK[userRole] || 0) >= (ROLE_RANK[requiredRole] || 99);

function timeAgo(iso) {
  if (!iso) return "";
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 60) return "baru saja";
  if (diff < 3600) return `${Math.floor(diff / 60)} mnt lalu`;
  if (diff < 86400) return `${Math.floor(diff / 3600)} jam lalu`;
  return `${Math.floor(diff / 86400)} hari lalu`;
}

/**
 * Notification Center (Fase 0) — bell + dropdown daftar notifikasi in-app.
 * Depth #3 — aksi inline "Setujui" untuk notifikasi PO approval (po_approve).
 */
export default function NotificationCenter({
  notifications = [], unreadCount = 0, canGenerate = false, currentUserRole = "",
  onMarkRead, onMarkAll, onGenerate, onNavigate, onApprove,
}) {
  const [open, setOpen] = useState(false);
  const [approving, setApproving] = useState(null);
  const ref = useRef(null);

  useEffect(() => {
    const onClick = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  async function handleApprove(e, n) {
    e.stopPropagation();
    setApproving(n.id);
    try { await onApprove?.(n); } finally { setApproving(null); }
  }

  return (
    <div className="notif-center" ref={ref}>
      <button
        type="button"
        data-testid="notif-bell"
        className="icon-button notif-bell"
        onClick={() => setOpen((v) => !v)}
        aria-label="Notifikasi"
        title="Notifikasi"
      >
        <Bell size={15} />
        {unreadCount > 0 && (
          <span data-testid="notif-badge" className="notif-badge">{unreadCount > 99 ? "99+" : unreadCount}</span>
        )}
      </button>
      {open && (
        <div className="notif-panel" data-testid="notif-panel">
          <div className="notif-panel-head">
            <span className="notif-panel-title">Notifikasi</span>
            <div className="flex items-center gap-1">
              {canGenerate && (
                <button data-testid="notif-generate-button" className="notif-mini-button" title="Pindai event sistem" onClick={() => onGenerate?.()}>
                  <RefreshCw size={12} /> Scan
                </button>
              )}
              <button data-testid="notif-mark-all-button" className="notif-mini-button" title="Tandai semua dibaca" onClick={() => onMarkAll?.()}>
                <CheckCheck size={12} /> Semua
              </button>
              <button className="icon-button" aria-label="Tutup" onClick={() => setOpen(false)}><X size={14} /></button>
            </div>
          </div>
          <div className="notif-list" data-testid="notif-list">
            {notifications.length === 0 && (
              <div data-testid="notif-empty" className="notif-empty">Tidak ada notifikasi. Sistem dalam kondisi baik.</div>
            )}
            {notifications.map((n) => {
              const Icon = SEVERITY_ICON[n.severity] || Info;
              const canApprove = n.action_type === "po_approve" && !n.read &&
                onApprove && canActOn(currentUserRole, n.action_role || "manager");
              return (
                <div
                  key={n.id}
                  data-testid={`notif-item-${n.id}`}
                  className={`notif-item sev-${n.severity || "info"} ${n.read ? "read" : "unread"}`}
                  role="button"
                  tabIndex={0}
                  onClick={() => { if (!n.read) onMarkRead?.(n.id); if (n.link) onNavigate?.(n.link); setOpen(false); }}
                >
                  <div className="notif-item-icon"><Icon size={15} /></div>
                  <div className="notif-item-body">
                    <div className="notif-item-title">{n.title}</div>
                    <div className="notif-item-text">{n.body}</div>
                    <div className="notif-item-foot">
                      <span className="notif-item-time">{timeAgo(n.created_at)}</span>
                      {canApprove && (
                        <button
                          data-testid={`notif-approve-${n.id}`}
                          className="notif-approve-button"
                          title="Setujui PO langsung"
                          disabled={approving === n.id}
                          onClick={(e) => handleApprove(e, n)}
                        >
                          {approving === n.id ? <Loader2 size={12} className="animate-spin" /> : <CheckCircle2 size={12} />}
                          {approving === n.id ? "Memproses..." : "Setujui"}
                        </button>
                      )}
                    </div>
                  </div>
                  {!n.read && (
                    <button
                      data-testid={`notif-read-${n.id}`}
                      className="notif-read-dot"
                      title="Tandai dibaca"
                      onClick={(e) => { e.stopPropagation(); onMarkRead?.(n.id); }}
                    >
                      <Check size={12} />
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
