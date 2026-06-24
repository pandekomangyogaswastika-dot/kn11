import { RefreshCw } from "lucide-react";

/**
 * ErrorNotice — bilah error konsisten dengan tombol "Coba lagi" (retry) opsional.
 * Dipakai di seluruh list view purchasing agar kegagalan load bisa dicoba ulang
 * tanpa reload halaman (sesuai KN_08 — error state harus punya retry).
 */
export default function ErrorNotice({ message, onRetry, onDismiss, testId = "error-notice" }) {
  if (!message) return null;
  return (
    <div className="notice-bar danger" data-testid={testId}>
      <span>{message}</span>
      <span style={{ marginLeft: "auto", display: "flex", gap: 10, alignItems: "center" }}>
        {onRetry && (
          <button data-testid={`${testId}-retry`} onClick={onRetry}
            style={{ marginLeft: 0, fontWeight: 700, display: "inline-flex", alignItems: "center", gap: 4 }}>
            <RefreshCw size={12} /> Coba lagi
          </button>
        )}
        {onDismiss && <button onClick={onDismiss} style={{ marginLeft: 0 }}>×</button>}
      </span>
    </div>
  );
}
