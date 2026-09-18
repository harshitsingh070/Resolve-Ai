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
  const [intentLabel, setIntentLabel] = useState<string | null>(null)
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [showSugg, setShowSugg] = useState(false)
  const [used, setUsed] = useState<string[]>(() => { try { return JSON.parse(localStorage.getItem('resolveai_used_pnrs')||'[]') } catch { return [] } })

  // PNR lookup handler — keep signature intact, only re-skinned UI calls it
  const load = async (selected: string) => {
    if (!selected) { setCustomer(null); setBooking(null); setMessages([]); setTrace([]); setActions([]); setEscalation(null); setIntentLabel(null); setError(null); return }
    setError(null); setTrace([]); setEscalation(null); setMessages([]); setActions([]); setIntentLabel(null)
    try { localStorage.setItem(LS_PNR, selected) } catch {}
    try {
      const sess = await getSession(selected)
      setCustomer(sess.customer); setBooking(sess.booking); setMessages(sess.messages); setTrace(sess.decision_trace || []); setActions(sess.actions); setEscalation(sess.escalation)
      // derive intent label from persisted trace for display
      const t0 = (sess.decision_trace||[])[0] || ''
      const m = t0.match(/Intent:\s*(\w+)/)
      const p = m?.[1] || ''
      const map: Record<string,string> = { hotel_request:'Hotel accommodation', refund_request:'Refund request', fare_waiver_request:'Fare waiver', upgrade_request:'Upgrade request', rebooking_request:'Rebooking', meal_voucher_request:'Meal voucher', lounge_request:'Lounge access', booking_inquiry:'Booking inquiry', complaint:'Complaint', unknown:'General inquiry' }
      setIntentLabel(p ? (map[p] || p) : null)
      try {
        const prev: string[] = JSON.parse(localStorage.getItem('resolveai_used_pnrs')||'[]')
        const next = [selected, ...prev.filter(p=> p!==selected)].slice(0,6)
        localStorage.setItem('resolveai_used_pnrs', JSON.stringify(next))
        setUsed(next)
      } catch {}
    } catch (e: any) {
      const msg = String(e.message)
      const friendly = msg.includes('not found') ? 'Booking not found' : msg
      setError(friendly); setCustomer(null); setBooking(null)
    }
  }
  useEffect(()=>{ if(pnr) load(pnr) },[pnr])
  const handleFind = () => { const v=lookup.trim().toUpperCase(); if(v) setPnr(v) }

  // Chat send handler — keep signature intact, chips will reuse this same path
  const send = async ()=>{
    if(!input.trim()||loading||!pnr) return
    const msg=input.trim(); setInput(''); setMessages(m=>[...m,{role:'user', message:msg}]); setLoading(true)
    try{
      const res: ChatResponse = await postChat(pnr, msg)
      setMessages(m=>[...m,{role:'assistant', message:res.response}])
      setTrace(res.decision_trace||[]); setEscalation(res.escalation||null)
      const p = (res as any).intent?.primary_intent || (res.decision_trace?.[0]?.match(/Intent:\s*(\w+)/)?.[1] || '')
      const map: Record<string,string> = { hotel_request:'Hotel accommodation', refund_request:'Refund request', fare_waiver_request:'Fare waiver', upgrade_request:'Upgrade request', rebooking_request:'Rebooking', meal_voucher_request:'Meal voucher', lounge_request:'Lounge access', booking_inquiry:'Booking inquiry', complaint:'Complaint', unknown:'General inquiry' }
      setIntentLabel(p ? (map[p] || p) : null)
      if(res.booking) setBooking(res.booking as any)
      if(res.customer) setCustomer(res.customer as any)
      if(res.actions?.length) setActions(prev=>{ const ids=new Set(prev.map(a=>a.id)); return [...prev, ...res.actions.filter(a=>!ids.has(a.id))] })
      const ac=await getActions(pnr); setActions(ac)
    } catch(e:any){ setMessages(m=>[...m,{role:'assistant', message:'Error: '+e.message}]) } finally{ setLoading(false) }
  }
  // Quick-reply chips reuse same send path — set input to chip text and invoke same handler
  const sendChip = async (text: string) => {
    if(loading || !pnr) return
    setMessages(m=>[...m,{role:'user', message:text}]); setLoading(true)
    try{
      const res: ChatResponse = await postChat(pnr, text)
      setMessages(m=>[...m,{role:'assistant', message:res.response}])
      setTrace(res.decision_trace||[]); setEscalation(res.escalation||null)
      const p = (res as any).intent?.primary_intent || (res.decision_trace?.[0]?.match(/Intent:\s*(\w+)/)?.[1] || '')
      const map: Record<string,string> = { hotel_request:'Hotel accommodation', refund_request:'Refund request', fare_waiver_request:'Fare waiver', upgrade_request:'Upgrade request', rebooking_request:'Rebooking', meal_voucher_request:'Meal voucher', lounge_request:'Lounge access', booking_inquiry:'Booking inquiry', complaint:'Complaint', unknown:'General inquiry' }
      setIntentLabel(p ? (map[p] || p) : null)
      if(res.booking) setBooking(res.booking as any)
      if(res.customer) setCustomer(res.customer as any)
      if(res.actions?.length) setActions(prev=>{ const ids=new Set(prev.map(a=>a.id)); return [...prev, ...res.actions.filter(a=>!ids.has(a.id))] })
      const ac=await getActions(pnr); setActions(ac)
    } catch(e:any){ setMessages(m=>[...m,{role:'assistant', message:'Error: '+e.message}]) } finally{ setLoading(false) }
  }

  const scenarios = [
    { pnr:'SK4821X', name:'Priya', label:'Cancellation', status:'CANCELLED', dot:'var(--red)' },
    { pnr:'TR1190B', name:'Arvind', label:'4h Delay', status:'DELAYED', dot:'var(--amber)' },
    { pnr:'WL7742', name:'Meher', label:'6h Delay', status:'DELAYED', dot:'var(--amber)' },
  ]

  // Helper: does last assistant message offer a choice (rebook vs refund) — show chips
  const lastAssistant = [...messages].reverse().find(m=> m.role==='assistant')
  const showChips = lastAssistant && /rebook|refund/i.test(lastAssistant.message) && /or|choice|choose/i.test(lastAssistant.message)

  return (
    <div className="h-screen flex flex-col overflow-hidden" style={{background:'var(--bg)'}}>
      {/* HEADER 64-72px — navy/brand, PNR Find */}
      <header className="flex-shrink-0 flex items-center justify-between px-6 bg-white" style={{height:68, borderBottom:'1px solid var(--line)', background:'var(--paper)'}}>
        <div className="flex items-center gap-3">
          <div className="h-8 w-8 rounded-lg flex items-center justify-center text-white" style={{background:'var(--navy)'}}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M2 16L10 14L14 10L22 6L18 10L10 14L8 22L2 16Z" fill="white"/></svg>
          </div>
          <div>
            <div className="brand text-sm font-bold tracking-tight" style={{color:'var(--navy)'}}>AIRLINE RESOLUTION ASSISTANT</div>
            <div className="text-xs" style={{color:'var(--slate)'}}>Support for flight disruptions</div>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs hidden sm:inline" style={{color:'var(--slate)'}}>PNR</span>
          <div className="relative">
            <input value={lookup} onChange={e=> setLookup(e.target.value)} onFocus={()=> setShowSugg(true)} onBlur={()=> setTimeout(()=> setShowSugg(false),150)} onKeyDown={e=> e.key==='Enter' && handleFind()} placeholder="SK4821X" aria-label="PNR input" className="border rounded-md px-3 py-1.5 text-sm w-36 bg-white" style={{borderColor:'var(--line)'}} />
            {showSugg && (
              <div className="absolute top-full mt-1 left-0 w-72 bg-white border rounded-lg shadow-lg z-20 max-h-64 overflow-y-auto card">
                <div className="px-3 py-2 text-[11px] font-semibold" style={{color:'var(--slate)'}}>Provided PNRs</div>
                {[
                  {pnr:'SK4821X', desc:'Priya Nair · Gold · SK-204 Cancelled'},
                  {pnr:'TR1190B', desc:'Arvind Kulkarni · Silver · SK-118 Delayed 4h'},
                  {pnr:'WL7742', desc:'Meher Kaur · Platinum · SK-305 Delayed 6h'},
                  {pnr:'SK4821X-R', desc:'Priya return · SK-204R Unaffected'},
                ].filter(o=> !lookup || o.pnr.toLowerCase().includes(lookup.toLowerCase()) || o.desc.toLowerCase().includes(lookup.toLowerCase())).map(o=> (
                  <button key={o.pnr} onMouseDown={e=>{e.preventDefault(); setLookup(o.pnr); setPnr(o.pnr)}} className="w-full text-left px-3 py-2 hover:bg-gray-50 flex justify-between items-center focus-visible:outline-none" style={{color:'var(--ink)'}}>
                    <span className="text-sm font-mono">{o.pnr}</span><span className="text-xs" style={{color:'var(--slate)'}}>{o.desc}</span>
                  </button>
                ))}
                {used.length>0 && <>
                  <div className="px-3 py-2 text-[11px] font-semibold border-t mt-1" style={{color:'var(--slate)', borderColor:'var(--line)'}}>Recently used</div>
                  {used.filter(p=> !lookup || p.toLowerCase().includes(lookup.toLowerCase())).map(p=> (
                    <button key={p} onMouseDown={e=>{e.preventDefault(); setLookup(p); setPnr(p)}} className="w-full text-left px-3 py-2 hover:bg-gray-50 text-sm font-mono focus-visible:outline-none" style={{color:'var(--ink)'}}>{p}</button>
                  ))}
                </>}
              </div>
            )}
          </div>
          <button onClick={handleFind} className="px-4 py-1.5 rounded-md text-sm text-white focus-visible:outline-none" style={{background:'var(--navy)'}}>Find</button>
        </div>
      </header>

      {/* PASSENGER TABS ROW */}
      <div className="flex-shrink-0 bg-white flex gap-6 px-6 border-b" style={{borderColor:'var(--line)'}}>
        {scenarios.map(s=> {
          const active = pnr===s.pnr
          return (
            <button key={s.pnr} onClick={()=> { setLookup(s.pnr); setPnr(s.pnr) }} aria-selected={active} className="py-3 flex items-center gap-2 border-b-2 text-xs focus-visible:outline-none" style={active ? {color:'var(--navy)', borderColor:'var(--navy)', fontWeight:600} : {color:'var(--slate)', borderColor:'transparent'}}>
              <span className="h-2 w-2 rounded-full" style={{background: s.dot}} aria-hidden="true"></span>
              {s.name} · {s.label}
            </button>
          )
        })}
      </div>

      {/* MAIN — fills viewport, no page scroll */}
      <div className="flex-1 min-h-0 overflow-hidden max-w-[1240px] mx-auto w-full px-4 py-3 flex flex-col gap-3">
        {!pnr || !customer ? (
          <div className="flex-1 flex items-center justify-center">
            <div className="card p-8 text-center max-w-md w-full">
              <div className="text-base font-semibold" style={{color:'var(--ink)'}}>How can we help with your flight?</div>
              <div className="text-sm mt-1" style={{color:'var(--slate)'}}>Enter your booking reference to get started.</div>
              <div className="flex gap-2 justify-center mt-4 relative">
                <div className="flex-1 relative">
                  <input value={lookup} onChange={e=> setLookup(e.target.value)} onFocus={()=> setShowSugg(true)} onBlur={()=> setTimeout(()=> setShowSugg(false),150)} onKeyDown={e=> e.key==='Enter' && handleFind()} placeholder="SK4821X" aria-label="PNR input" className="w-full border rounded-md px-3 py-2 text-sm" style={{borderColor:'var(--line)'}} />
                  {showSugg && (
                    <div className="absolute top-full mt-1 left-0 right-0 bg-white border rounded-lg shadow-lg z-20 card">
                      <div className="px-3 py-2 text-[11px] font-semibold" style={{color:'var(--slate)'}}>Provided PNRs</div>
                      {[
                        {pnr:'SK4821X', desc:'Priya Nair · Cancelled'},
                        {pnr:'TR1190B', desc:'Arvind · Delayed 4h'},
                        {pnr:'WL7742', desc:'Meher · Delayed 6h'},
                      ].filter(o=> !lookup || o.pnr.toLowerCase().includes(lookup.toLowerCase())).map(o=> (
                        <button key={o.pnr} onMouseDown={e=>{e.preventDefault(); setLookup(o.pnr); setPnr(o.pnr)}} className="w-full text-left px-3 py-2 hover:bg-gray-50 flex justify-between focus-visible:outline-none">
                          <span className="text-sm font-mono" style={{color:'var(--ink)'}}>{o.pnr}</span><span className="text-xs" style={{color:'var(--slate)'}}>{o.desc}</span>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
                <button onClick={handleFind} className="px-4 py-2 rounded-md text-sm text-white" style={{background:'var(--navy)'}}>Find my booking</button>
              </div>
              <div className="text-xs mt-2" style={{color:'var(--slate)'}}>Use the booking reference from your reservation.</div>
              {error && <div className="text-xs mt-3" style={{color:'var(--red)'}}>{error}</div>}
            </div>
          </div>
        ) : (
          <>
            {/* FLIGHT INFO BAR — single full-width card */}
            <div className="flex-shrink-0 card px-4 py-3 flex items-center justify-between gap-4">
              <div className="flex gap-8">
                <div>
                  <div className="flight-code text-sm font-bold" style={{color:'var(--ink)'}}>{booking?.flight_number}</div>
                  <div className="text-sm" style={{color:'var(--ink)'}}>{booking?.route}</div>
                  <div className="text-xs" style={{color:'var(--slate)'}}>{booking?.travel_date} · {booking?.scheduled_departure} {booking?.reason ? `· ${booking.reason}` : ''}</div>
                </div>
                <div className="flex flex-col justify-center">
                  <span className="inline-block text-xs px-2 py-1 rounded font-semibold w-fit" style={booking?.status==='Cancelled' ? {background:'var(--red-bg)', color:'var(--red)'} : booking?.status==='Delayed' ? {background:'#FFF3E0', color:'#8a5a00'} : {background:'#E8F5E9', color:'var(--success)'}}>{booking?.status?.toUpperCase()}</span>
                  {booking?.status==='Delayed' && <span className="text-xs mt-1" style={{color:'var(--slate)'}}>New departure · {booking?.new_departure} · {booking?.delay_hours} HOURS</span>}
                </div>
              </div>
              <div className="text-right">
                <div className="text-sm font-semibold" style={{color:'var(--ink)'}}>{customer.name}</div>
                <div className="text-xs" style={{color:'var(--slate)'}}>PNR: {customer.pnr} · {customer.loyalty_tier}</div>
              </div>
            </div>

            {/* TWO-COLUMN MAIN — responsive below 820px */}
            <div className="flex-1 min-h-0 flex gap-3 overflow-hidden max-[820px]:flex-col max-[820px]:overflow-auto">
              {/* LEFT ~68% — CHAT PANEL */}
              <div className="flex-[68] min-w-0 card flex flex-col overflow-hidden">
                <div className="px-4 py-3 border-b" style={{borderColor:'var(--line)'}}>
                  <div className="text-sm font-semibold flex items-center gap-2" style={{color:'var(--ink)'}}><span>🤖</span> Resolution Assistant</div>
                  <div className="text-xs" style={{color:'var(--slate)'}}>Usually replies in a few seconds</div>
                </div>
                <div className="flex-1 min-h-0 overflow-y-auto p-4 space-y-3">
                  {messages.length===0 && <div className="text-xs" style={{color:'var(--slate)'}}>No messages yet.</div>}
                  {messages.map((m,i)=> (
                    <div key={i} className="flex flex-col">
                      <div className={`text-[11px] font-semibold mb-1 ${m.role==='user'?'text-right':''}`} style={{color:'var(--slate)'}}>{m.role==='user'?'YOU':'ASSISTANT'}</div>
                      <div className={`max-w-[75%] px-3 py-2 rounded-lg text-sm leading-relaxed whitespace-pre-wrap ${m.role==='user'?'ml-auto text-white':'mr-auto border'}`} style={m.role==='user'?{background:'var(--navy)', color:'white'}:{background:'var(--bg)', color:'var(--ink)', borderColor:'var(--line)'}}>
                        {m.message}
                        {/* Bulleted list for policy terms inside assistant messages — lightweight, keep existing message text */}
                        {m.role==='assistant' && /policy|Policy|SR-/.test(m.message) && (
                          <ul className="list-disc pl-4 mt-2 text-xs" style={{color:'var(--ink)'}}>
                            {m.message.includes('rebook') && <li>Free rebooking within 24 hours</li>}
                            {m.message.includes('refund') && <li>Full refund within 7 business days</li>}
                          </ul>
                        )}
                      </div>
                      {/* Quick-reply chips after assistant offer (rebook vs refund) — reuse same send handler */}
                      {m.role==='assistant' && i===messages.length-1 && showChips && (
                        <div className="flex gap-2 mt-2 flex-wrap justify-start">
                          <button onClick={()=> sendChip("Rebook my flight")} className="px-3 py-1.5 rounded-full text-xs border bg-white hover:bg-gray-50 focus-visible:outline-none" style={{borderColor:'var(--line)', color:'var(--blue)', background:'var(--blue-bg)'}}>Rebook my flight</button>
                          <button onClick={()=> sendChip("Request a refund")} className="px-3 py-1.5 rounded-full text-xs border bg-white hover:bg-gray-50 focus-visible:outline-none" style={{borderColor:'var(--line)', color:'var(--blue)', background:'var(--blue-bg)'}}>Request a refund</button>
                        </div>
                      )}
                    </div>
                  ))}
                  {loading && <div className="text-xs" style={{color:'var(--slate)'}}>Checking your booking…</div>}
                </div>
                <div className="flex-shrink-0 p-3 border-t flex gap-2" style={{borderColor:'var(--line)'}}>
                  <input value={input} onChange={e=> setInput(e.target.value)} onKeyDown={e=> e.key==='Enter' && send()} placeholder="Type your message..." aria-label="Chat input" className="flex-1 border rounded-full px-4 py-2 text-sm focus-visible:outline-none" style={{borderColor:'var(--line)'}} disabled={loading} />
                  <button onClick={send} disabled={loading||!input.trim()} aria-label="Send message" className="h-9 w-9 rounded-full flex items-center justify-center text-white disabled:opacity-50 focus-visible:outline-none flex-shrink-0" style={{background:'var(--navy)'}}>
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" aria-hidden="true"><path d="M5 12L19 12M19 12L13 6M19 12L13 18"/></svg>
                  </button>
                </div>
              </div>

              {/* RIGHT ~280px — SIDEBAR */}
              <div className="w-[280px] max-[820px]:w-full flex-shrink-0 flex flex-col gap-3 overflow-hidden max-[820px]:overflow-visible">
                {intentLabel && (
                  <div className="card p-3">
                    <div className="text-xs font-semibold" style={{color:'var(--ink)'}}>Detected Intent</div>
                    <div className="text-xs mt-1 px-2 py-1 rounded-full inline-block" style={{background:'var(--blue-bg)', color:'var(--blue)', border:'1px solid var(--line)'}}>{intentLabel}</div>
                  </div>
                )}
                <div className="card p-4">
                  <div className="text-xs font-semibold mb-2" style={{color:'var(--ink)'}}>Booking details</div>
                  <div className="space-y-2 text-xs">
                    <div className="flex justify-between" style={{color:'var(--slate)'}}><span>Route</span><span style={{color:'var(--ink)'}}>{booking?.route || '—'}</span></div>
                    <div className="flex justify-between" style={{color:'var(--slate)'}}><span>Status</span><span style={{color:'var(--ink)'}}>{booking?.status || '—'}{booking?.delay_hours ? ` · ${booking.delay_hours}h` : ''}</span></div>
                    <div className="flex justify-between" style={{color:'var(--slate)'}}><span>Policy reference</span><span style={{color:'var(--ink)'}}>{trace.map(t=> t.match(/\(SR-[^)]+\)/)?.[0]).filter(Boolean).join(', ') || '—'}</span></div>
                    <div className="flex justify-between" style={{color:'var(--slate)'}}><span>PNR</span><span className="font-mono" style={{color:'var(--ink)'}}>{booking?.pnr || '—'}</span></div>
                    <div className="flex justify-between" style={{color:'var(--slate)'}}><span>Tier</span><span style={{color:'var(--ink)'}}>{customer.loyalty_tier || '—'}</span></div>
                  </div>
                </div>
                <div className="card p-4 flex-1 min-h-0 overflow-y-auto">
                  <div className="text-xs font-semibold mb-2" style={{color:'var(--ink)'}}>Actions taken</div>
                  {actions.length===0 ? <div className="text-xs" style={{color:'var(--slate)'}}>No actions yet. Actions taken by the agent will appear here.</div> : (
                    <div className="space-y-2">
                      {actions.map(a=> (
                        <div key={a.id} className="flex justify-between text-xs py-1 border-b last:border-0" style={{borderColor:'var(--line)'}}>
                          <span className="flex gap-2"><span style={{color:'var(--success)'}}>✓</span><span style={{color:'var(--ink)'}}>{a.action_type.replace('_',' ').toLowerCase()}</span></span>
                          <span style={{color:'var(--slate)'}}>{a.metadata?.amount ? `₹${a.metadata.amount}` : a.metadata?.coverage ? 'delayed hours' : ''}</span>
                        </div>
                      ))}
                      {escalation && <div className="text-xs mt-2 p-2 rounded" style={{background:'var(--warning-bg)', color:'var(--warning)'}}>⚠ {escalation.reason.replace(/_/g,' ')} — {escalation.status}</div>}
                    </div>
                  )}
                </div>
              </div>
            </div>
          </>
        )}
      </div>

      <footer className="flex-shrink-0 text-center text-xs py-2 border-t" style={{borderColor:'var(--line)', color:'var(--slate)'}}>© 2026 Airline · Customer Support &nbsp; Privacy | Terms | Contact</footer>
    </div>
  )
}
