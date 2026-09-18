import type { Escalation } from '../types'
const reasonMap: Record<string, string> = {
  fare_difference_exceeds_limit: 'Fare difference exceeds agent authority of ₹1,500',
  upgrade_exception: 'Free upgrade not covered by policy',
  refund_payment_method: 'Refund must go to original payment method',
  legal_threat: 'Formal complaint / legal threat — human review required',
  full_night_hotel: 'Full-night hotel not covered (delayed-hours only)',
}
export default function EscalationBanner({ escalation }: { escalation: Escalation | null }) {
  if (!escalation) return null
  const human = reasonMap[escalation.reason] || escalation.reason.replace(/_/g,' ')
  const isFare = escalation.reason === 'fare_difference_exceeds_limit'
  const fareAmt = isFare ? escalation.requested_action.replace('waive_','').replace('_',' ') : null
  return (
    <div className="p-4 bg-amber-50 border-2 border-amber-400 rounded-xl">
      <div className="flex items-center gap-2 text-amber-900">
        <span className="h-7 w-7 rounded-full bg-amber-500 text-white flex items-center justify-center">⚠</span>
        <div className="text-sm font-bold">Supervisor escalation required</div>
        <span className="ml-auto text-xs px-2 py-1 bg-amber-200 rounded-full">{escalation.status}</span>
      </div>
      <div className="text-xs text-amber-800 mt-2 leading-snug">{human}</div>
      {isFare && (
        <div className="text-xs text-amber-700 mt-1 font-mono bg-amber-100 px-2 py-1 rounded">₹{fareAmt} requested — agent limit ₹1,500 (SR-06) — pending supervisor</div>
      )}
      {escalation.requested_action && !isFare && (
        <div className="text-xs text-amber-700 mt-1">Requested: {escalation.requested_action.replace('_',' ')}</div>
      )}
    </div>
  )
}
