import { useEffect, useState } from 'react'
import type { Customer, Booking, Action, Escalation, ChatResponse } from './types'
import { getSession, getActions, postChat } from './services/api'
import CustomerCard from './components/CustomerCard'
import BookingCard from './components/BookingCard'
import ChatWindow from './components/ChatWindow'
import DecisionTrace from './components/DecisionTrace'
import ActionLog from './components/ActionLog'
import EscalationBanner from './components/EscalationBanner'

const PNRS = ['SK4821X', 'TR1190B', 'WL7742'] as const
const LS_PNR = 'resolveai_selected_pnr'

export default function App() {
  const [pnr, setPnr] = useState<string>(() => {
    try { return localStorage.getItem(LS_PNR) || 'SK4821X' } catch { return 'SK4821X' }
  })
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
    setError(null)
    // State rule: when selecting new PNR, clear old PNR's session state (trace, escalation, messages, actions) before loading new
    setTrace([]); setEscalation(null); setMessages([]); setActions([])
    try { localStorage.setItem(LS_PNR, selected) } catch {}
    try {
      // Preferred: single read-only session hydration (persists trace without Groq regeneration)
      const sess = await getSession(selected)
      setCustomer(sess.customer); setBooking(sess.booking); setMessages(sess.messages); setTrace(sess.decision_trace || []); setActions(sess.actions); setEscalation(sess.escalation)
    } catch (e: any) {
      // Unknown PNR or no session yet — keep empty state with friendly error
      if (String(e.message).includes('Session not found') || String(e.message).includes('not found')) {
        setError(e.message)
        setCustomer(null); setBooking(null); setActions([]); setMessages([]); setTrace([]); setEscalation(null)
      } else {
        setError(e.message)
      }
    }
  }

  useEffect(() => { load(pnr) }, [pnr])

  const send = async () => {
    if (!input.trim() || loading) return
    const msg = input.trim()
    setInput('')
    setMessages(m => [...m, { role: 'user', message: msg }])
    setLoading(true)
    try {
      const res: ChatResponse = await postChat(pnr, msg)
      // Atomic response update: all panels from SAME /api/chat response (spec: 6. Atomic response update)
      setMessages(m => [...m, { role: 'assistant', message: res.response }])
      setTrace(res.decision_trace || [])
      setEscalation(res.escalation || null)
      if (res.booking) setBooking(res.booking as any)
      if (res.customer) setCustomer(res.customer as any)
      // Action Log: backend returns this turn's actions; merge with existing for cumulative log (or refetch full history)
      // Use response actions if present, else fallback to full fetch
      if (res.actions && res.actions.length > 0) {
        // merge: keep existing + new (idempotent, so no duplicate id)
        setActions(prev => {
          const existingIds = new Set(prev.map(a => a.id))
          const newActions = res.actions.filter(a => !existingIds.has(a.id))
          return [...prev, ...newActions]
        })
      }
      // also ensure full history is eventually consistent (optional refetch)
      // but do NOT overwrite trace
      const ac = await getActions(pnr)
      setActions(ac)
    } catch (e: any) {
      setMessages(m => [...m, { role: 'assistant', message: 'Error: ' + e.message }])
    } finally { setLoading(false) }
  }

  const scenarios = [
    { label: 'Priya — Cancellation + Upgrade', pnr: 'SK4821X', hint: '“I am furious! Refund + business upgrade”' },
    { label: 'Arvind — 4h Delay + Hotel', pnr: 'TR1190B', hint: '“Need hotel for 4h delay”' },
    { label: 'Meher — 6h + ₹2,000 Waiver', pnr: 'WL7742', hint: '“Full-night hotel + waive 2000”' },
  ]

  return (
    <div className="min-h-screen bg-gray-100">
      <header className="bg-white border-b px-6 py-4">
        <div className="flex items-center justify-between gap-4 flex-wrap">
          <div>
            <div className="font-bold text-gray-900 tracking-tight">AIRLINE RESOLUTION AGENT</div>
            <div className="text-xs text-gray-500">Policy-grounded customer support — deterministic rules, not a generic chatbot</div>
          </div>
          <div className="flex items-center gap-2">
            <select value={pnr} onChange={e => setPnr(e.target.value)} className="border rounded-lg px-3 py-1.5 text-sm bg-white">
              {PNRS.map(v => <option key={v} value={v}>{v}</option>)}
              <option value="SK4821X-R">SK4821X-R (Priya return)</option>
              <option value="XX9999">XX9999 (unknown)</option>
            </select>
            <span className="text-xs text-gray-500 hidden sm:inline">PNR</span>
          </div>
        </div>
        <div className="flex flex-wrap gap-2 mt-3">
          {scenarios.map(s => (
            <button key={s.pnr} onClick={() => setPnr(s.pnr)} className={`text-xs px-3 py-1.5 rounded-full border ${pnr===s.pnr ? 'bg-blue-600 text-white border-blue-600' : 'bg-white text-gray-700 hover:bg-gray-50'}`}>
              {s.label} <span className="hidden lg:inline text-gray-400">· {s.hint}</span>
            </button>
          ))}
        </div>
      </header>

      {error && <div className="mx-6 mt-3 p-2 bg-red-50 border border-red-200 text-xs text-red-700 rounded-lg">{error}</div>}

      <div className="grid grid-cols-12 gap-4 p-4 max-w-[1400px] mx-auto">
        {/* LEFT */}
        <div className="col-span-12 md:col-span-3">
          <CustomerCard customer={customer} />
          <BookingCard booking={booking} />
          <div className="mt-3">
            <EscalationBanner escalation={escalation} />
          </div>
        </div>

        {/* CENTER */}
        <div className="col-span-12 md:col-span-6 flex flex-col gap-3">
          <ChatWindow messages={messages} />
          <div className="flex gap-2">
            <input value={input} onChange={e => setInput(e.target.value)} onKeyDown={e => e.key === 'Enter' && send()} placeholder="Type message…" className="flex-1 border rounded-xl px-4 py-2 text-sm bg-white" disabled={loading} />
            <button onClick={send} disabled={loading} className="px-5 py-2 bg-blue-600 text-white rounded-xl text-sm disabled:opacity-50">{loading ? '...' : 'Send'}</button>
          </div>
          <div className="text-xs text-gray-400">Try: “I want refund” / “hotel for tonight” / “waive 2000” / “business upgrade”</div>
        </div>

        {/* RIGHT */}
        <div className="col-span-12 md:col-span-3 space-y-3">
          <DecisionTrace trace={trace} />
          <ActionLog actions={actions} />
        </div>
      </div>
    </div>
  )
}
