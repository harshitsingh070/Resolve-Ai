function humanizeTrace(t: string): { text: string; sub?: string; tone: 'ok' | 'warn' | 'block' | 'info' } {
  // Hide raw implementation details: amount=None, hotel_type=None, [] etc.
  let text = t
  let sub: string | undefined
  let tone: 'ok' | 'warn' | 'block' | 'info' = 'info'

  // Intent line: "Intent: hotel_request + [] (neutral) amount=None hotel_type=None" -> human
  if (t.startsWith('Intent:')) {
    const m = t.match(/Intent:\s*(\w+)(?:\s*\+\s*\[(.*?)\])?/);
    const primary = m?.[1] || ''
    const secondary = m?.[2] || ''
    const sentimentMatch = t.match(/\((\w+)\)/)
    const sentiment = sentimentMatch?.[1] || ''
    // hide None/empty
    const amountMatch = t.match(/amount=([^\s]+)/)
    const hotelMatch = t.match(/hotel_type=([^\s]+)/)
    const amount = amountMatch?.[1]
    const hotelType = hotelMatch?.[1]
    const map: Record<string, string> = {
      hotel_request: 'Hotel accommodation', meal_voucher_request: 'Meal voucher', lounge_request: 'Lounge access',
      refund_request: 'Refund request', rebooking_request: 'Rebooking', fare_waiver_request: 'Fare waiver',
      upgrade_request: 'Upgrade request', booking_inquiry: 'Booking inquiry', complaint: 'Complaint', unknown: 'General inquiry'
    }
    const primaryLabel = map[primary] || primary.replace('_request','').replace('_',' ')
    let secondaryLabel = ''
    if (secondary && secondary.trim() && secondary !== '') {
      const secs = secondary.split(',').map(s=> s.trim().replace(/['"\s]/g,'')).filter(Boolean)
      if (secs.length) secondaryLabel = ' + ' + secs.map(s=> map[s] || s).join(', ')
    }
    text = `Intent: ${primaryLabel}${secondaryLabel}`
    if (sentiment && sentiment !== 'neutral') sub = `Sentiment: ${sentiment}`
    // hide amount None, show only when present and not None
    if (amount && amount !== 'None' && amount !== 'null') {
      sub = (sub ? sub + ' • ' : '') + `Amount: ₹${amount}`
    }
    if (hotelType && hotelType !== 'None' && hotelType !== 'null') {
      sub = (sub ? sub + ' • ' : '') + `Hotel: ${hotelType.replace('_',' ')}`
    }
    tone = 'info'
    return { text, sub, tone }
  }

  // Policy and authority lines: make SR refs subtle
  if (t.includes('Policy: delay')) {
    // Extract human part, keep SR as sub
    const sr = t.match(/\(SR-[^)]+\)/)?.[0]
    const clean = t.replace(/\s*\(SR-[^)]+\)/, '').replace('Policy:','').trim()
    text = clean
    if (sr) sub = sr
    if (t.includes('✓')) tone = 'ok'
    else if (t.includes('✗') || t.includes('not eligible')) tone = 'block'
    else tone = 'info'
    return { text, sub, tone }
  }
  if (t.startsWith('Policy: cancellation')) {
    // simplify
    const eligible = t.includes('refund eligible=True')
    text = eligible ? 'Cancellation: Airline-caused — refund & rebooking eligible' : 'Cancellation: Not airline-caused'
    const sr = t.match(/\(SR-[^)]+\)/)?.[0]
    if (sr) sub = sr
    tone = eligible ? 'ok' : 'info'
    return { text, sub, tone }
  }
  if (t.startsWith('Authority:') || t.startsWith('Blocked:') || t.startsWith('Escalation:')) {
    const sr = t.match(/\(SR-[^)]+\)/)?.[0]
    let clean = t.replace(/\s*\(SR-[^)]+\)/, '').trim()
    // hide technical allowed=true/false
    clean = clean.replace(/allowed=(true|false)/, '').replace(/eligible=(true|false)/,'').replace(/escalation=(true|false)/,'').replace(/\s{2,}/g,' ').trim()
    // add icon tone
    if (t.includes('Escalation')) tone = 'warn'
    else if (t.includes('Blocked') || t.includes('not eligible') || t.includes('unspecified')) tone = 'block'
    else if (t.includes('allowed=true') || t.includes('✓')) tone = 'ok'
    text = clean
    if (sr) sub = sr
    return { text, sub, tone }
  }
  if (t.startsWith('Action:')) {
    tone = 'ok'
    // make SR subtle
    const sr = t.match(/\(SR-[^)]+\)/)?.[0]
    let clean = t.replace(/\s*\(SR-[^)]+\)/, '').trim()
    text = clean
    if (sr) sub = sr
    return { text, sub, tone }
  }

  // generic
  if (t.includes('✓')) tone = 'ok'
  else if (t.includes('Escalation') || t.includes('escalation')) tone = 'warn'
  else if (t.includes('Blocked') || t.includes('blocked') || t.includes('not eligible')) tone = 'block'
  return { text, sub, tone }
}

export default function DecisionTrace({ trace }: { trace: string[] }) {
  if (!trace || trace.length === 0) return <div className="p-4 text-xs text-gray-400 border rounded-xl bg-gray-50">No decision yet — send a message to see the policy trace</div>
  return (
    <div className="p-4 border rounded-xl bg-white shadow-sm">
      <div className="text-xs font-bold tracking-wide text-gray-800 mb-3">DECISION TRACE</div>
      <div className="space-y-3">
        {trace.filter(t => {
          // hide very technical noise: ask for PNR, Groq fallback
          if (t.includes('Groq intent failed')) return false
          return true
        }).map((t, i) => {
          const { text, sub, tone } = humanizeTrace(t)
          const dot = tone === 'ok' ? 'bg-emerald-500' : tone === 'warn' ? 'bg-amber-500' : tone === 'block' ? 'bg-red-500' : 'bg-slate-400'
          const textColor = tone === 'ok' ? 'text-gray-900' : tone === 'warn' ? 'text-amber-900' : tone === 'block' ? 'text-red-700' : 'text-gray-700'
          return (
            <div key={i} className="flex gap-2">
              <span className={`mt-1.5 h-2 w-2 rounded-full flex-shrink-0 ${dot}`} />
              <div className="flex-1">
                <div className={`text-xs leading-snug ${textColor}`}>{text}</div>
                {sub && <div className="text-[11px] text-gray-400 mt-0.5">{sub}</div>}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
