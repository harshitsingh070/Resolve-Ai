export default function EscalationBanner({ escalation }: { escalation: any }) {
  if(!escalation) return null
  const isFare = escalation.reason==='fare_difference_exceeds_limit'
  return (
    <div className="py-3 border-b">
      <div className="text-[11px] tracking-wide text-amber-600 font-semibold mb-1">ESCALATION</div>
      <div className="text-xs text-amber-800">⚠ Supervisor review required</div>
      <div className="text-xs text-gray-600 mt-1">{escalation.reason.replace(/_/g,' ')}</div>
      {isFare && <div className="text-xs text-gray-500 mt-1">₹2,000 requested · Agent limit ₹1,500</div>}
      {escalation.requested_action && !isFare && <div className="text-xs text-gray-500">{escalation.requested_action.replace('_',' ')}</div>}
      <div className="text-[11px] text-gray-400 mt-1">Status: {escalation.status}</div>
    </div>
  )
}
