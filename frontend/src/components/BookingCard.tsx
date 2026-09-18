import type { Booking } from '../types'
export default function BookingCard({ booking }: { booking: Booking | null }) {
  if (!booking) return <div className="p-4 text-sm text-gray-500 border rounded-lg bg-gray-50">No booking selected</div>
  const statusColor = booking.status === 'Cancelled' ? 'bg-red-500' : booking.status === 'Delayed' ? 'bg-amber-500' : 'bg-emerald-500'
  return (
    <div className="p-4 border rounded-xl bg-white shadow-sm mt-3">
      <div className="flex items-center justify-between">
        <div className="font-mono text-sm font-bold">{booking.flight_number}</div>
        <span className={`text-xs px-2 py-1 rounded-full text-white ${statusColor}`}>{booking.status}</span>
      </div>
      <div className="text-sm text-gray-800 mt-1">{booking.route}</div>
      <div className="text-xs text-gray-500">{booking.travel_date} at {booking.scheduled_departure}</div>
      {booking.delay_hours != null && <div className="text-xs mt-2">Delay: <span className="font-semibold">{booking.delay_hours}h</span> {booking.new_departure && `→ new ${booking.new_departure}`}</div>}
      {booking.reason && <div className="text-xs text-gray-500 mt-1">Reason: {booking.reason}</div>}
    </div>
  )
}
