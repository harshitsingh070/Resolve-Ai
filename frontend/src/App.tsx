import { useEffect, useState } from 'react'
import type { Customer, Booking, Action, Escalation, ChatResponse } from './types'
import { getSession, getActions, postChat } from './services/api'

const LS_PNR = 'resolveai_selected_pnr'

export default function App() {
  const [pnr, setPnr] = useState<string>(() => { try { return localStorage.getItem(LS_PNR) || '' } catch { return '' } })
  const [lookup, setLookup] = useState<string>(() => { try { return localStorage.getItem(LS_PNR) || '' } catch { return '' } })
  const [customer, setCustomer] = useState<Customer | null>(null)
  const [booking, setBooking] = useState<Booking | null>(null)
  const [messages, setMessages] = useState<{ role: 'user' | 'assistant'; message: string }[]>([])
  const [trace, setTrace] = useState<string[]>([])
  const [actions, setActions] = useState<Action[]>([])
  const [escalation, setEscalation] = useState<Escalation | null>(null)
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const load = async (selected: string) => {
    if (!selected) { setCustomer(null); setBooking(null); setMessages([]); setTrace([]); setActions([]); setEscalation(null); setError(null); return }
    setError(null); setTrace([]); setEscalation(null); setMessages([]); setActions([])
    try { localStorage.setItem(LS_PNR, selected) } catch {}
    try {
      const sess = await getSession(selected)
      setCustomer(sess.customer); setBooking(sess.booking); setMessages(sess.messages); setTrace(sess.decision_trace || []); setActions(sess.actions); setEscalation(sess.escalation)
    } catch (e: any) {
      const msg = String(e.message)
      const friendly = msg.includes('not found') ? 'Booking not found' : msg
      setError(friendly); setCustomer(null); setBooking(null)
    }
  }
  useEffect(()=>{ if(pnr) load(pnr) },[pnr])
  const handleFind = () => { const v=lookup.trim().toUpperCase(); if(v) setPnr(v) }
  const send = async ()=>{
    if(!input.trim()||loading||!pnr) return
    const msg=input.trim(); setInput(''); setMessages(m=>[...m,{role:'user', message:msg}]); setLoading(true)
    try{
      const res: ChatResponse = await postChat(pnr, msg)
      setMessages(m=>[...m,{role:'assistant', message:res.response}])
      setTrace(res.decision_trace||[]); setEscalation(res.escalation||null)
      if(res.booking) setBooking(res.booking as any)
      if(res.customer) setCustomer(res.customer as any)
      if(res.actions?.length) setActions(prev=>{ const ids=new Set(prev.map(a=>a.id)); return [...prev, ...res.actions.filter(a=>!ids.has(a.id))] })
      const ac=await getActions(pnr); setActions(ac)
    } catch(e:any){ setMessages(m=>[...m,{role:'assistant', message:'Error: '+e.message}]) } finally{ setLoading(false) }
  }

  const scenarios = [
    { pnr:'SK4821X', label:'Priya · Cancellation' },
    { pnr:'TR1190B', label:'Arvind · 4h Delay' },
    { pnr:'WL7742', label:'Meher · 6h Delay' },
  ]

  return (
    <div className="h-screen flex flex-col overflow-hidden" style={{background:'var(--bg)'}}>
      {/* HEADER 64-72px */}
      <header className="flex-shrink-0 bg-white flex items-center justify-between px-6" style={{height:68, borderBottom:'1px solid var(--border)', background:'#F1F5F9'}}>
        <div className="flex items-center gap-3">
          <div className="h-8 w-8 rounded-lg flex items-center justify-center text-white text-xs" style={{background:'var(--primary)'}}>✈</div>
          <div>
            <div className="text-sm font-semibold tracking-tight" style={{color:'var(--text)'}}>AIRLINE RESOLUTION ASSISTANT</div>
            <div className="text-xs" style={{color:'var(--text-secondary)'}}>Support for flight disruptions</div>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs hidden sm:inline" style={{color:'var(--text-secondary)'}}>PNR</span>
          <input value={lookup} onChange={e=> setLookup(e.target.value)} onKeyDown={e=> e.key==='Enter' && handleFind()} placeholder="SK4821X" className="border rounded-md px-3 py-1.5 text-sm w-36 bg-white" style={{borderColor:'var(--border)'}} />
          <button onClick={handleFind} className="px-4 py-1.5 rounded-md text-sm text-white" style={{background:'var(--primary)'}}>Find</button>
          <span className="text-xs hidden md:inline ml-2" style={{color:'var(--text-secondary)'}}>Help</span>
        </div>
      </header>

      {/* SCENARIO NAV */}
      <div className="flex-shrink-0 bg-white flex gap-6 px-6 py-2 text-xs border-b" style={{borderColor:'var(--border)'}}>
        {scenarios.map(s=> (
          <button key={s.pnr} onClick={()=> { setLookup(s.pnr); setPnr(s.pnr) }} className="pb-1 border-b-2" style={pnr===s.pnr ? {color:'var(--primary)', borderColor:'var(--primary)', fontWeight:600} : {color:'var(--text-secondary)', borderColor:'transparent'}}>
            {s.label}
          </button>
        ))}
      </div>

      {/* MAIN — fills viewport, no page scroll */}
      <div className="flex-1 min-h-0 overflow-hidden max-w-[1280px] mx-auto w-full px-4 py-3 flex flex-col gap-3">
        {!pnr || !customer ? (
          <div className="flex-1 flex items-center justify-center">
            <div className="bg-white border rounded-xl p-8 text-center max-w-md w-full" style={{borderColor:'var(--border)'}}>
              <div className="text-base font-semibold" style={{color:'var(--text)'}}>How can we help with your flight?</div>
              <div className="text-sm mt-1" style={{color:'var(--text-secondary)'}}>Enter your booking reference to get started.</div>
              <div className="flex gap-2 justify-center mt-4">
                <input value={lookup} onChange={e=> setLookup(e.target.value)} onKeyDown={e=> e.key==='Enter' && handleFind()} placeholder="SK4821X" className="flex-1 border rounded-md px-3 py-2 text-sm" style={{borderColor:'var(--border)'}} />
                <button onClick={handleFind} className="px-4 py-2 rounded-md text-sm text-white" style={{background:'var(--primary)'}}>Find my booking</button>
              </div>
              <div className="text-xs mt-2" style={{color:'var(--text-secondary)'}}>Use the booking reference from your reservation.</div>
              {error && <div className="text-xs mt-3" style={{color:'var(--error)'}}>{error}</div>}
            </div>
          </div>
        ) : (
          <>
            {/* BOOKING SUMMARY — compact horizontal */}
            <div className="flex-shrink-0 bg-white border rounded-lg px-4 py-3 flex items-center justify-between gap-4" style={{borderColor:'var(--border)'}}>
              <div className="flex gap-8">
                <div>
                  <div className="text-[11px] tracking-wide font-semibold" style={{color:'var(--text-secondary)'}}>YOUR FLIGHT</div>
                  <div className="text-sm font-semibold" style={{color:'var(--text)'}}>{booking?.flight_number}</div>
                  <div className="text-sm" style={{color:'var(--text)'}}>{booking?.route}</div>
                  <div className="text-xs" style={{color:'var(--text-secondary)'}}>{booking?.travel_date} · {booking?.scheduled_departure}</div>
                </div>
                <div className="flex flex-col justify-center">
                  <span className={`inline-block text-xs px-2 py-1 rounded font-semibold text-white w-fit ${booking?.status==='Cancelled'?'bg-red-500':booking?.status==='Delayed'?'bg-amber-500':'bg-emerald-500'}`}>{booking?.status?.toUpperCase()}</span>
                  {booking?.status==='Cancelled' && booking?.reason && <span className="text-xs mt-1" style={{color:'var(--text-secondary)'}}>{booking.reason}</span>}
                  {booking?.status==='Delayed' && <span className="text-xs mt-1" style={{color:'var(--text-secondary)'}}>New departure · {booking?.new_departure} · {booking?.delay_hours} HOURS</span>}
                </div>
              </div>
              <div className="text-right">
                <div className="text-[11px] tracking-wide font-semibold" style={{color:'var(--text-secondary)'}}>PASSENGER</div>
                <div className="text-sm font-semibold" style={{color:'var(--text)'}}>{customer.name}</div>
                <div className="text-xs" style={{color:'var(--text-secondary)'}}>{customer.loyalty_tier} · PNR: {customer.pnr}</div>
              </div>
            </div>

            {/* TWO-COL MAIN */}
            <div className="flex-1 min-h-0 flex gap-3 overflow-hidden">
              {/* LEFT 68% — CHAT */}
              <div className="flex-[68] min-w-0 bg-white border rounded-lg flex flex-col overflow-hidden" style={{borderColor:'var(--border)'}}>
                <div className="px-4 py-2 border-b flex items-center gap-2" style={{borderColor:'var(--border)'}}>
                  <span className="text-sm">🤖</span>
                  <div>
                    <div className="text-sm font-semibold" style={{color:'var(--text)'}}>Resolution Assistant</div>
                    <div className="text-xs" style={{color:'var(--text-secondary)'}}>Tell us what you need help with.</div>
                  </div>
                </div>
                <div className="flex-1 min-h-0 overflow-y-auto p-4 space-y-3">
                  {messages.length===0 && <div className="text-xs" style={{color:'var(--text-secondary)'}}>No messages yet.</div>}
                  {messages.map((m,i)=> (
                    <div key={i} className="flex flex-col">
                      <div className={`text-[11px] font-semibold mb-1 ${m.role==='user'?'text-right':''}`} style={{color:'var(--text-secondary)'}}>{m.role==='user'?'YOU':'ASSISTANT'}</div>
                      <div className={`max-w-[75%] px-3 py-2 rounded-lg text-sm leading-relaxed whitespace-pre-wrap ${m.role==='user'?'ml-auto text-white':'mr-auto border'}`} style={m.role==='user'?{background:'var(--primary)'}:{background:'#F8FAFC', color:'var(--text)', borderColor:'var(--border)'}}>
                        {m.message}
                      </div>
                    </div>
                  ))}
                  {loading && <div className="text-xs" style={{color:'var(--text-secondary)'}}>Checking your booking…</div>}
                </div>
                <div className="flex-shrink-0 p-3 border-t flex gap-2" style={{borderColor:'var(--border)'}}>
                  <input value={input} onChange={e=> setInput(e.target.value)} onKeyDown={e=> e.key==='Enter' && send()} placeholder="Type your message..." className="flex-1 border rounded-md px-3 py-2 text-sm" style={{borderColor:'var(--border)'}} disabled={loading} />
                  <button onClick={send} disabled={loading||!input.trim()} className="px-4 py-2 rounded-md text-sm text-white disabled:opacity-50" style={{background:'var(--primary)'}}>Send</button>
                </div>
              </div>

              {/* RIGHT 32% — ACTIONS & STATUS */}
              <div className="flex-[32] min-w-0 bg-white border rounded-lg flex flex-col overflow-hidden" style={{borderColor:'var(--border)'}}>
                <div className="flex-1 min-h-0 overflow-y-auto p-4 space-y-4">
                  <div>
                    <div className="text-xs font-semibold mb-2" style={{color:'var(--text)'}}>ACTIONS & STATUS</div>
                    {actions.length===0 ? <div className="text-xs" style={{color:'var(--text-secondary)'}}>No actions yet<br/>Actions taken by the agent will appear here after your request.</div> : (
                      <div className="space-y-1">
                        {actions.map(a=> (
                          <div key={a.id} className="flex justify-between text-xs py-1 border-b last:border-0" style={{borderColor:'var(--border)'}}>
                            <span className="flex gap-2"><span style={{color:'var(--success)'}}>✓</span><span style={{color:'var(--text)'}}>{a.action_type.replace('_',' ').toLowerCase()}</span></span>
                            <span style={{color:'var(--text-secondary)'}}>{a.metadata?.amount ? `₹${a.metadata.amount}` : a.metadata?.coverage ? 'delayed hours' : ''}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                  {escalation && (
                    <div className="rounded-md p-3" style={{background:'var(--warning-bg)', border:'1px solid #FDE68A'}}>
                      <div className="text-xs font-semibold" style={{color:'var(--warning)'}}>SUPERVISOR REVIEW REQUIRED</div>
                      <div className="text-xs mt-1" style={{color:'var(--text-secondary)'}}>
                        {escalation.reason==='fare_difference_exceeds_limit' ? 'The requested ₹2,000 fare difference waiver requires supervisor approval.' : escalation.reason==='upgrade_exception' ? 'The requested business-class upgrade is not covered by the available disruption policy.' : escalation.reason.replace(/_/g,' ')}
                      </div>
                    </div>
                  )}
                  <details className="rounded-md border p-3" style={{borderColor:'var(--border)'}} open>
                    <summary className="text-xs font-semibold cursor-pointer" style={{color:'var(--text)'}}>▾ Resolution details</summary>
                    <div className="mt-2 space-y-1 text-xs" style={{color:'var(--text-secondary)'}}>
                      <div>Intent · {(() => {
                        const raw = trace[0] || ''
                        const m = raw.match(/Intent:\s*(\w+)/)
                        const p = m?.[1] || 'unknown'
                        const map: Record<string,string> = { hotel_request:'Hotel accommodation', refund_request:'Refund request', fare_waiver_request:'Fare waiver', upgrade_request:'Upgrade request', rebooking_request:'Rebooking', meal_voucher_request:'Meal voucher', lounge_request:'Lounge access', booking_inquiry:'Booking inquiry', complaint:'Complaint', unknown:'General inquiry' }
                        return map[p] || p.replace('_request','').replace(/_/g,' ')
                      })()}</div>
                      <div>Booking · {customer.name} · {booking?.pnr}</div>
                      <div>Flight status · {booking?.status} {booking?.delay_hours ? `${booking.delay_hours}h` : ''}</div>
                      <div>Verified facts · {booking?.route}</div>
                      <div>Policy reference · {trace.map(t=> t.match(/\(SR-[^)]+\)/)?.[0]).filter(Boolean).join(', ') || '—'}</div>
                      <div>Actions · {actions.map(a=> a.action_type.toLowerCase()).join(', ') || 'none'}</div>
                      {escalation && <div>Escalation · {escalation.reason.replace(/_/g,' ')}</div>}
                    </div>
                  </details>
                </div>
              </div>
            </div>
          </>
        )}
      </div>

      <footer className="flex-shrink-0 text-center text-xs py-2 border-t" style={{borderColor:'var(--border)', color:'var(--text-secondary)'}}>© 2026 Airline · Customer Support &nbsp; Privacy | Terms | Contact</footer>
    </div>
  )
}
