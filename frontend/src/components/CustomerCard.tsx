import type { Customer } from '../types'
export default function CustomerCard({ customer }: { customer: Customer | null }) {
  if (!customer) return <div className="py-3 text-sm text-gray-500 border-b">Customer not found<span className="block text-xs">Check the PNR and try again.</span></div>
  return (
    <div className="py-3 border-b">
      <div className="text-[11px] tracking-wide text-gray-400 font-semibold mb-2">CUSTOMER</div>
      <div className="flex items-baseline justify-between">
        <div className="text-[15px] font-semibold text-gray-900">{customer.name}</div>
        <span className="text-[11px] px-2 py-0.5 rounded-full border text-gray-600 bg-gray-50">{customer.loyalty_tier}</span>
      </div>
      <div className="text-xs font-mono text-gray-600 mt-1">{customer.pnr}</div>
      <div className="text-xs text-gray-500 mt-2 leading-relaxed">{customer.email}<br/>{customer.phone}</div>
    </div>
  )
}
