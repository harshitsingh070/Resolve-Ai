import type { Action } from '../types'
const label: Record<string, string> = {
  MEAL_VOUCHER: 'Meal voucher', LOUNGE_ACCESS: 'Lounge access', HOTEL: 'Hotel', REFUND_INITIATED: 'Refund initiated', REBOOKED: 'Rebooked'
}
export default function ActionLog({ actions }: { actions: Action[] }) {
  if (!actions || actions.length === 0) return <div className="p-4 text-xs text-gray-400 border rounded-xl bg-gray-50">No actions yet — eligible actions will appear here after your message</div>
  return (
    <div className="p-4 border rounded-xl bg-white shadow-sm">
      <div className="text-xs font-bold tracking-wide text-gray-800 mb-3">ACTION LOG</div>
      <div className="space-y-2">
        {actions.map(a => (
          <div key={a.id} className="flex items-center gap-3 p-2 bg-emerald-50 border border-emerald-200 rounded-lg">
            <span className="h-6 w-6 rounded-full bg-emerald-600 text-white flex items-center justify-center text-xs">✓</span>
            <div className="flex-1">
              <div className="text-xs font-semibold text-emerald-900">{label[a.action_type] || a.action_type}</div>
              <div className="text-[11px] text-emerald-700">{a.reason?.replace('delay_','').replace('_',' ') || 'completed'}</div>
            </div>
            <div className="text-right">
              {a.metadata?.amount && <div className="text-xs font-bold text-gray-900">₹{a.metadata.amount}</div>}
              {a.metadata?.coverage && <div className="text-[11px] text-gray-500">{a.metadata.coverage.replace('_',' ')}</div>}
              {a.metadata?.window_hours && <div className="text-[11px] text-gray-500">{a.metadata.window_hours}h window</div>}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
