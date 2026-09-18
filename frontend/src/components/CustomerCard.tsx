import type { Customer } from '../types'
export default function CustomerCard({ customer }: { customer: Customer | null }) {
  if (!customer) return <div className="p-4 text-sm text-gray-500 border rounded-lg bg-gray-50">Select a customer to see details</div>
  const tierColor = customer.loyalty_tier === 'Platinum' ? 'bg-purple-600' : customer.loyalty_tier === 'Gold' ? 'bg-amber-500' : 'bg-slate-400'
  return (
    <div className="p-4 border rounded-xl bg-white shadow-sm">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-gray-900">{customer.name}</h3>
        <span className={`text-xs px-2 py-1 rounded-full text-white ${tierColor}`}>{customer.loyalty_tier}</span>
      </div>
      <div className="text-xs text-gray-500 mt-1">{customer.pnr}</div>
      <div className="text-xs text-gray-600 mt-2 break-all">{customer.email}<br/>{customer.phone}</div>
    </div>
  )
}
