import type { Booking } from '../types'
import { useEffect, useState } from 'react'

export default function BookingCard({ booking }: { booking: Booking | null }) {
  const [others, setOthers] = useState<Booking[]>([])
  const [open, setOpen] = useState(false)
  useEffect(()=>{
    if(!booking || booking.pnr !== 'SK4821X') { setOthers([]); return }
    fetch(`${(import.meta as any).env?.VITE_API_URL ?? 'http://localhost:8000'}/api/bookings/SK4821X?include_return=true`)
      .then(r=> r.ok? r.json(): []).then((data:any)=> { if(Array.isArray(data)) setOthers(data.filter((b:any)=> b.pnr !== booking.pnr)) }).catch(()=>{})
  },[booking?.pnr])
  if (!booking) return <div className="py-3 text-xs text-gray-400 border-b">No booking</div>
  return (
    <div className="py-3 border-b">
      <div className="text-[11px] tracking-wide text-gray-400 font-semibold mb-2">BOOKING</div>
      <div className="text-sm font-semibold text-gray-900">{booking.flight_number}</div>
      <div className="text-sm text-gray-700">{booking.route}</div>
      <div className="text-xs text-gray-500 mt-1">{booking.travel_date} · {booking.scheduled_departure}</div>
      <div className="mt-2 text-xs">
        <span className={`inline-block px-2 py-0.5 rounded text-white text-[11px] ${booking.status==='Cancelled'?'bg-red-500':booking.status==='Delayed'?'bg-amber-500':'bg-emerald-500'}`}>{booking.status.toUpperCase()}</span>
        {booking.status==='Delayed' && booking.delay_hours!=null && <span className="ml-2 text-gray-600">· {booking.delay_hours}h</span>}
      </div>
      {booking.new_departure && <div className="text-xs text-gray-500 mt-1">New departure · {booking.new_departure}</div>}
      {booking.reason && <div className="text-xs text-gray-500 mt-1">{booking.reason}</div>}
      {others.length>0 && (
        <div className="mt-3">
          <button onClick={()=>setOpen(!open)} className="text-xs text-gray-500 hover:text-gray-700">Other bookings ({others.length}) {open?'▲':'▼'}</button>
          {open && <div className="mt-2 space-y-1 text-xs text-gray-600">{others.map(b=> <div key={b.pnr} className="border-t pt-1">{b.pnr} · {b.route} · {b.status}</div>)}</div>}
        </div>
      )}
    </div>
  )
}
