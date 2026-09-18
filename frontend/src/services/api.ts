import type { Customer, Booking, Action, ChatResponse } from '../types'

const BASE = (import.meta as any).env?.VITE_API_URL ?? 'http://localhost:8000'

export async function getCustomer(pnr: string): Promise<Customer> {
  const r = await fetch(`${BASE}/api/customers/${pnr}`)
  if (!r.ok) throw new Error((await r.json()).detail || 'Customer not found')
  return r.json()
}
export async function getBooking(pnr: string): Promise<Booking> {
  const r = await fetch(`${BASE}/api/bookings/${pnr}`)
  if (!r.ok) throw new Error((await r.json()).detail || 'Booking not found')
  return r.json()
}
export async function getActions(pnr: string): Promise<Action[]> {
  const r = await fetch(`${BASE}/api/actions/${pnr}`)
  if (!r.ok) return []
  return r.json()
}
export async function getConversations(pnr: string): Promise<any[]> {
  const r = await fetch(`${BASE}/api/conversations/${pnr}`)
  if (!r.ok) return []
  return r.json()
}
export async function postChat(pnr: string, message: string): Promise<ChatResponse> {
  const r = await fetch(`${BASE}/api/chat`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ pnr, message }) })
  if (!r.ok) throw new Error('Chat failed')
  return r.json()
}
export async function health(): Promise<any> {
  const r = await fetch(`${BASE}/api/health`)
  return r.json()
}
export interface SessionResponse {
  customer: Customer; booking: Booking; messages: { role: 'user' | 'assistant'; message: string }[]; decision_trace: string[]; actions: Action[]; escalation: any | null
}
export async function getSession(pnr: string): Promise<SessionResponse> {
  const r = await fetch(`${BASE}/api/session/${pnr}`)
  if (!r.ok) throw new Error((await r.json()).detail || 'Session not found')
  return r.json()
}
