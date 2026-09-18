export default function ChatInput({ value, onChange, onSend, loading }: { value: string; onChange:(v:string)=>void; onSend:()=>void; loading:boolean }) {
  return (
    <div className="border-t pt-3">
      <div className="flex gap-2">
        <input id="chat-input" value={value} onChange={e=>onChange(e.target.value)} onKeyDown={e=> e.key==='Enter' && !e.shiftKey && (e.preventDefault(), onSend())} placeholder="Type a message..." aria-label="Chat message" className="flex-1 border rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-1 focus:ring-blue-500" disabled={loading} />
        <button onClick={onSend} disabled={loading || !value.trim()} aria-label="Send" className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm disabled:opacity-50">Send</button>
      </div>
      <div className="text-xs text-gray-400 mt-1">Enter to send · Shift+Enter for newline</div>
    </div>
  )
}
