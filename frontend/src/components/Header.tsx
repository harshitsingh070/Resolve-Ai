type Props = { pnr: string; onChange: (v: string) => void; customerName?: string }
const PNRS = ['SK4821X','TR1190B','WL7742','SK4821X-R','XX9999']
export default function Header({ pnr, onChange }: Props) {
  return (
    <header className="bg-white border-b px-4 py-3 flex items-center justify-between gap-3">
      <div>
        <div className="text-[15px] font-semibold text-gray-900 tracking-tight">AIRLINE RESOLUTION AGENT</div>
        <div className="text-xs text-gray-500">Policy-grounded customer support</div>
      </div>
      <div className="flex items-center gap-2">
        <span className="text-xs text-gray-500">PNR</span>
        <select value={pnr} onChange={e => onChange(e.target.value)} aria-label="Select PNR" className="border rounded-md px-2 py-1 text-sm bg-white">
          {PNRS.map(v => <option key={v} value={v}>{v}</option>)}
        </select>
      </div>
    </header>
  )
}
