/** LedgerTable — chronological inventory movement history (max 60 rows). */
import { formatQty, formatDate, MOV_TYPE_MAP } from "./inventoryConstants";

export default function LedgerTable({ movements = [], balances = [], loading = false }) {
  return (
    <div className="bg-white rounded-xl border border-[#EFF0F2] overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-[11.5px]">
          <thead>
            <tr className="bg-[#FAFBFC] border-b border-[#EFF0F2]">
              <th className="text-left px-3 py-2 text-[10px] font-bold uppercase tracking-wide text-[#6B6B73]">Waktu</th>
              <th className="text-left px-3 py-2 text-[10px] font-bold uppercase tracking-wide text-[#6B6B73]">Tipe</th>
              <th className="text-left px-3 py-2 text-[10px] font-bold uppercase tracking-wide text-[#6B6B73]">Produk</th>
              <th className="text-left px-3 py-2 text-[10px] font-bold uppercase tracking-wide text-[#6B6B73]">Gudang</th>
              <th className="text-left px-3 py-2 text-[10px] font-bold uppercase tracking-wide text-[#6B6B73]">Batch/Lot</th>
              <th className="text-right px-3 py-2 text-[10px] font-bold uppercase tracking-wide text-[#6B6B73]">Qty</th>
              <th className="text-left px-3 py-2 text-[10px] font-bold uppercase tracking-wide text-[#6B6B73]">Dokumen</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#EFF0F2]">
            {loading && (
              <tr><td colSpan={7} className="text-center py-8 text-[12px] text-[#6B6B73]">Loading...</td></tr>
            )}
            {!loading && movements.length === 0 && (
              <tr><td colSpan={7} className="text-center py-10 text-[12px] text-[#6B6B73]">Tidak ada data pergerakan stok</td></tr>
            )}
            {!loading && movements.slice(0, 60).map((m) => {
              const mt = MOV_TYPE_MAP[m.movement_type] || { label: m.movement_type, color: "text-gray-600", dot: "bg-gray-400" };
              const prod = balances.find(b => b.product_id === m.product_id);
              return (
                <tr key={m.id} data-testid={`movement-row-${m.id}`} className="hover:bg-[#FAFBFC] transition-colors">
                  <td className="px-3 py-2 text-[10.5px] text-[#6B6B73] whitespace-nowrap">{formatDate(m.timestamp)}</td>
                  <td className="px-3 py-2">
                    <div className="flex items-center gap-1.5">
                      <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${mt.dot}`} />
                      <span className={`text-[10.5px] font-semibold ${mt.color}`}>{mt.label}</span>
                    </div>
                  </td>
                  <td className="px-3 py-2">
                    <p className="font-semibold text-[#007AFF]">{prod?.sku || m.product_id}</p>
                  </td>
                  <td className="px-3 py-2 text-[10.5px] text-[#6B6B73]">
                    {balances.find(b => b.warehouse_id === m.warehouse_id)?.warehouse_name || m.warehouse_id}
                  </td>
                  <td className="px-3 py-2 text-[10.5px] text-[#6B6B73]">
                    {[m.batch, m.lot, m.roll_id].filter(Boolean).join(" · ") || "-"}
                  </td>
                  <td className={`px-3 py-2 text-right font-bold tabular-nums ${m.quantity < 0 ? "text-red-600" : "text-green-700"}`}>
                    {m.quantity > 0 ? "+" : ""}{formatQty(m.quantity)}
                  </td>
                  <td className="px-3 py-2 text-[10.5px] text-[#007AFF]">{m.source_document || "-"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
