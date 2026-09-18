const scenarios = [
  { pnr: 'SK4821X', label: 'Priya · Cancellation' },
  { pnr: 'TR1190B', label: 'Arvind · 4h Delay' },
  { pnr: 'WL7742', label: 'Meher · 6h Delay' },
]
export default function ScenarioBar({ active, onSelect }: { active: string; onSelect: (pnr: string) => void }) {
  return (
    <div className="px-4 py-2 bg-white border-b flex gap-4 text-xs">
      {scenarios.map(s => (
        <button key={s.pnr} onClick={() => onSelect(s.pnr)} className={`hover:underline ${active===s.pnr ? 'text-blue-600 font-semibold' : 'text-gray-500'}`}>
          {s.label}
        </button>
      ))}
    </div>
  )
}
