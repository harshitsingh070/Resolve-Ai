export type LoyaltyTier = 'Gold' | 'Silver' | 'Platinum'
export interface Customer {
  id: number; name: string; loyalty_tier: LoyaltyTier; pnr: string; email: string; phone: string
}
export interface Booking {
  id: number; customer_id: number; pnr: string; flight_number: string; route: string; travel_date: string; scheduled_departure: string; status: string; delay_hours: number | null; new_departure: string | null; reason: string | null
}
export interface Action {
  id: number; booking_id: number; pnr: string; action_type: string; status: string; reason: string | null; metadata: any; created_at: string
}
export interface Escalation {
  id: number; booking_id: number; pnr: string; reason: string; requested_action: string; status: string; created_at: string
}
export interface Intent {
  primary_intent: string; secondary_intents: string[]; sentiment: string; requested_exception: boolean; entities: { amount?: number | null; hotel_type?: string | null; refund_method?: string | null; upgrade_class?: string | null }
}
export interface ChatResponse {
  response: string; intent: Intent | null; actions: Action[]; escalation: Escalation | null; decision_trace: string[]; booking: Booking | null; customer: Customer | null; ask_for_pnr?: boolean
}
export type Pnr = 'SK4821X' | 'TR1190B' | 'WL7742' | 'SK4821X-R'
