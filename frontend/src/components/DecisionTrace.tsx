import { useState } from 'react'
function humanize(t:string){
  let text=t; let sub:string|undefined; let tone:'ok'|'warn'|'block'|'info'='info'
  if(t.startsWith('Intent:')){
    const m=t.match(/Intent:\s*(\w+)/); const p=m?.[1]||''
    const map:Record<string,string>={hotel_request:'Hotel accommodation',meal_voucher_request:'Meal voucher',lounge_request:'Lounge',refund_request:'Refund',rebooking_request:'Rebooking',fare_waiver_request:'Fare waiver',upgrade_request:'Upgrade',booking_inquiry:'Booking inquiry',complaint:'Complaint',unknown:'General inquiry'}
    text = map[p] || p
    if(t.includes('fare_waiver')){ const amt=t.match(/amount=([^\s]+)/)?.[1]; if(amt && amt!=='None') text+=` · ₹${amt}` }
    return {text, tone:'info'}
  }
  if(t.includes('Policy: delay')){
    const sr=t.match(/\(SR-[^)]+\)/)?.[0]; text=t.replace(/\s*\(SR-[^)]+\)/,'').replace('Policy:','').trim(); if(sr) sub=sr; tone=t.includes('✓')?'ok':t.includes('not eligible')?'block':'info'; return {text,sub,tone}
  }
  if(t.startsWith('Policy: cancellation')){
    const e=t.includes('refund eligible=True'); text=e?'Cancellation: airline-caused — refund eligible':'Cancellation: not airline-caused'; sub=t.match(/\(SR-[^)]+\)/)?.[0]; tone=e?'ok':'info'; return {text,sub,tone}
  }
  if(t.startsWith('Authority:')||t.startsWith('Blocked:')||t.startsWith('Escalation:')){
    const sr=t.match(/\(SR-[^)]+\)/)?.[0]; let c=t.replace(/\s*\(SR-[^)]+\)/,'').trim().replace(/allowed=(true|false)/,'').replace(/escalation=(true|false)/,'').trim(); text=c; if(sr) sub=sr; tone=t.includes('Escalation')?'warn':t.includes('Blocked')?'block':'info'; return {text,sub,tone}
  }
  if(t.startsWith('Action:')){ const sr=t.match(/\(SR-[^)]+\)/)?.[0]; text=t.replace(/\s*\(SR-[^)]+\)/,'').trim(); if(sr) sub=sr; tone='ok'; return {text,sub,tone} }
  return {text,sub,tone}
}
export default function DecisionTrace({ trace }: { trace: string[] }) {
  const [open,setOpen]=useState(false)
  if(!trace||trace.length===0) return <div className="py-3 border-b"><div className="text-[11px] tracking-wide text-gray-400 font-semibold mb-1">DECISION</div><div className="text-xs text-gray-400">No decision yet — send a message.</div></div>
  const filtered=trace.filter(t=> !t.includes('Groq intent failed'))
  const primary:string[]=[]; const secondary:string[]=[]
  const first=filtered[0]||''; const isFare=first.includes('fare_waiver')||filtered.some(t=>t.toLowerCase().includes('fare waiver')); const isHotel=first.includes('hotel_request')
  for(const t of filtered){
    const low=t.toLowerCase()
    let rel=true
    if(isFare && low.includes('cancellation') && !low.includes('refund')) rel=false
    if(isHotel && low.includes('cancellation')) rel=false
    if(rel) primary.push(t); else secondary.push(t)
  }
  const render=(list:string[])=> list.map((t,i)=>{ const {text,sub,tone}=humanize(t); const dot=tone==='ok'?'bg-emerald-500':tone==='warn'?'bg-amber-500':tone==='block'?'bg-red-500':'bg-gray-300'; return <div key={i} className="flex gap-2 py-1"><span className={`mt-2 h-1.5 w-1.5 rounded-full ${dot}`}/><div className="flex-1"><div className="text-xs text-gray-800 leading-snug">{text}</div>{sub && <div className="text-[11px] text-gray-400">{sub}</div>}</div></div> })
  return (
    <div className="py-3 border-b">
      <div className="text-[11px] tracking-wide text-gray-400 font-semibold mb-2">DECISION</div>
      <div className="space-y-0.5">{render(primary)}</div>
      {secondary.length>0 && <details className="mt-2" open={open} onToggle={e=> setOpen((e.target as HTMLDetailsElement).open)}><summary className="text-xs text-gray-500 cursor-pointer">Details · {secondary.length} more</summary><div className="mt-2 space-y-1 border-t pt-2">{render(secondary)}</div></details>}
    </div>
  )
}
