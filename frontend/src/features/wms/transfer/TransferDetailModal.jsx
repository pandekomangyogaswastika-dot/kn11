/** TransferDetailModal — detail view + lifecycle actions for a single transfer. */
import { CheckCircle, XCircle } from "lucide-react";
import { formatQty } from "../../../utils/formatters";
import { StatusBadge } from "./transferConstants";

export default function TransferDetailModal({ transfer, user, onClose, onApprove, onReject, onUpdateStatus, onCancel }) {
  return (
    <div
      data-testid="transfer-detail-modal"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4"
      onClick={onClose}
    >
      <div
        className="bg-white border border-[#E5E5EA] rounded-2xl w-full max-w-3xl max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold">Detail Transfer</h3>
            <button onClick={onClose}>
              <XCircle size={20} className="text-[#3C3C43]" />
            </button>
          </div>

          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-[#F2F2F7] rounded-lg p-3">
                <p className="text-xs text-[#3C3C43] mb-1">Code</p>
                <p className="font-semibold">{transfer.code}</p>
              </div>
              <div className="bg-[#F2F2F7] rounded-lg p-3">
                <p className="text-xs text-[#3C3C43] mb-1">Status</p>
                <StatusBadge status={transfer.status} />
              </div>
              <div className="bg-[#F2F2F7] rounded-lg p-3">
                <p className="text-xs text-[#3C3C43] mb-1">Gudang Asal</p>
                <p className="font-semibold text-sm">{transfer.source_warehouse_name}</p>
              </div>
              <div className="bg-[#F2F2F7] rounded-lg p-3">
                <p className="text-xs text-[#3C3C43] mb-1">Gudang Tujuan</p>
                <p className="font-semibold text-sm">{transfer.dest_warehouse_name}</p>
              </div>
            </div>

            {/* Items */}
            <div>
              <h4 className="text-sm font-semibold mb-2">Items</h4>
              <div className="space-y-2">
                {transfer.items?.map((item, index) => (
                  <div key={index} className="flex items-center justify-between bg-[#F2F2F7] rounded-lg p-2">
                    <div>
                      <p className="text-sm font-semibold">{item.sku} - {item.product_name}</p>
                    </div>
                    <p className="text-sm font-bold tabular-nums">{formatQty(item.qty)} {item.unit}</p>
                  </div>
                ))}
              </div>
            </div>

            {/* Actions */}
            <div className="flex flex-wrap gap-2">
              {transfer.status === "waiting_approval" && user?.role === "manager" && (
                <>
                  <button
                    data-testid="approve-transfer-button"
                    onClick={() => onApprove(transfer.id)}
                    className="flex items-center gap-2 bg-[#34C759] hover:bg-[#28A745] text-white rounded-full px-4 py-2 text-sm font-medium"
                  >
                    <CheckCircle size={14} /> Approve
                  </button>
                  <button
                    data-testid="reject-transfer-button"
                    onClick={() => onReject(transfer.id)}
                    className="flex items-center gap-2 bg-[#FF3B30] hover:bg-[#DC3545] text-white rounded-full px-4 py-2 text-sm font-medium"
                  >
                    <XCircle size={14} /> Reject
                  </button>
                </>
              )}
              {transfer.status === "approved" && (
                <button
                  data-testid="start-picking-button"
                  onClick={() => onUpdateStatus(transfer.id, "picking")}
                  className="bg-[#007AFF] hover:bg-[#0056B3] text-white rounded-full px-4 py-2 text-sm font-medium"
                >
                  Start Picking
                </button>
              )}
              {transfer.status === "picking" && (
                <button
                  data-testid="move-to-staging-button"
                  onClick={() => onUpdateStatus(transfer.id, "staging")}
                  className="bg-[#007AFF] hover:bg-[#0056B3] text-white rounded-full px-4 py-2 text-sm font-medium"
                >
                  Move to Staging
                </button>
              )}
              {transfer.status === "staging" && (
                <button
                  data-testid="dispatch-button"
                  onClick={() => onUpdateStatus(transfer.id, "dispatched")}
                  className="bg-[#007AFF] hover:bg-[#0056B3] text-white rounded-full px-4 py-2 text-sm font-medium"
                >
                  Dispatch
                </button>
              )}
              {transfer.status === "dispatched" && (
                <button
                  data-testid="complete-transfer-button"
                  onClick={() => onUpdateStatus(transfer.id, "completed")}
                  className="bg-[#34C759] hover:bg-[#28A745] text-white rounded-full px-4 py-2 text-sm font-medium"
                >
                  Complete Transfer
                </button>
              )}
              {!["completed", "rejected", "cancelled"].includes(transfer.status) && (
                <button
                  data-testid="cancel-transfer-button"
                  onClick={() => onCancel(transfer.id)}
                  className="bg-gray-500 hover:bg-gray-600 text-white rounded-full px-4 py-2 text-sm font-medium"
                >
                  Cancel
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
