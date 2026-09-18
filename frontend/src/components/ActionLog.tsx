import type { Action } from '../types'
export default function ActionLog({ actions }: { actions: Action[] }) {
  if(!actions||actions.length===0) return <div className="py-3 border-b"><div className="text-[11px] tracking-wide text-gray-400 font-semibold mb-1">ACTIONS</div><div className="text-xs text-gray-400">No actions yet</div></div>
  return (
    <div className="py-3 border-b">
      <div className="text-[11px] tracking-wide text-gray-400 font-semibold mb-2">ACTIONS</div>
      <div className="space-y-1">
        {actions.map(a=> (
          <div key={a.id} className="flex items-center gap-2 text-xs">
            <span className="text-emerald-600 text-xs">✓</span>
            <span className="text-gray-800">{a.action_type.replace('_',' ').toLowerCase()}</span>
            {a.metadata?.amount && <span className="ml-auto text-gray-600">₹{a.metadata.amount}</span>}
            {a.metadata?.coverage && <span className="ml-auto text-gray-500 text-[11px]">{a.metadata.coverage.replace('_',' ')}</span>}
          </div>
        ))}
      </div>
    </div>
  )
}
