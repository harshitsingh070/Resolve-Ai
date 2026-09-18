import type { Action } from '../types'
export default function ResolutionSummary({ actions, escalation, trace }: { actions: Action[]; escalation: any; trace: string[] }) {
  if (actions.length===0 && !escalation && trace.length===0) {
    return <div className="py-3 border-b"><div className="text-[11px] tracking-wide text-gray-400 font-semibold mb-1">RESOLUTION</div><div className="text-xs text-gray-400">No resolution yet</div></div>
  }
  const items: { icon:string; title:string; sub?:string; tone:string }[]=[]
  const has=(t:string)=> actions.some(a=> a.action_type===t)
  if(has('MEAL_VOUCHER')) items.push({icon:'✓', title:'Meal voucher ₹500', tone:'emerald'})
  if(has('LOUNGE_ACCESS')) items.push({icon:'✓', title:'Lounge access', tone:'emerald'})
  if(has('HOTEL')) items.push({icon:'✓', title:'Hotel — delayed hours', tone:'emerald'})
  if(has('REFUND_INITIATED')) items.push({icon:'✓', title:'Refund initiated', tone:'emerald'})
  if(has('REBOOKED')) items.push({icon:'✓', title:'Rebooked', tone:'emerald'})
  const traceText = trace.join(' ').toLowerCase()
  if(!has('HOTEL') && traceText.includes('hotel') && traceText.includes('not eligible')) items.push({icon:'✕', title:'Hotel — not eligible', tone:'red'})
  if(escalation){
    const isFare = escalation.reason==='fare_difference_exceeds_limit'
    const isUp = escalation.reason==='upgrade_exception'
    if(isFare) items.push({icon:'⚠', title:'₹2,000 waiver — supervisor review', tone:'amber'})
    else if(isUp) items.push({icon:'⚠', title:'Upgrade — supervisor review', tone:'amber'})
    else items.push({icon:'⚠', title: escalation.reason.replace(/_/g,' '), tone:'amber'})
  }
  return (
    <div className="py-3 border-b">
      <div className="text-[11px] tracking-wide text-gray-400 font-semibold mb-2">RESOLUTION</div>
      <div className="space-y-1">
        {items.map((it,i)=> (
          <div key={i} className="flex items-center gap-2 text-xs">
            <span className={it.tone==='emerald'?'text-emerald-600':it.tone==='amber'?'text-amber-600':'text-red-500'}>{it.icon}</span>
            <span className="text-gray-800">{it.title}</span>
            {it.sub && <span className="text-gray-400 ml-1">{it.sub}</span>}
          </div>
        ))}
      </div>
    </div>
  )
}
