export default function StatusBadge({ status }: { status: string }) {
  const map: Record<string,string> = {
    Cancelled: 'bg-red-500 text-white', Delayed: 'bg-amber-500 text-white', Unaffected: 'bg-emerald-500 text-white',
  }
  return <span className={`text-xs px-2.5 py-1 rounded-full font-semibold ${map[status] || 'bg-slate-400 text-white'}`}>{status.toUpperCase()}</span>
}
