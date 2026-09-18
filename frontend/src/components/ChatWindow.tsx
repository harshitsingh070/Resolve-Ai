type Msg = { role: 'user' | 'assistant'; message: string }
export default function ChatWindow({ messages, loading }: { messages: Msg[]; loading?: boolean }) {
  return (
    <div className="flex-1 overflow-y-auto py-3 space-y-3" style={{ minHeight: 320, maxHeight: 460 }}>
      {messages.length === 0 && <div className="text-center py-8"><div className="text-sm text-gray-500">No messages yet</div><div className="text-xs text-gray-400 mt-1">Send a message to check the booking and applicable policy.</div></div>}
      {messages.map((m, i) => (
        <div key={i} className="flex flex-col">
          <div className={`text-[11px] font-semibold mb-1 ${m.role==='user'?'text-right text-gray-500':'text-left text-gray-500'}`}>{m.role==='user'?'YOU':'AGENT'}</div>
          <div className={`max-w-[75%] px-3 py-2 rounded-xl text-sm leading-relaxed whitespace-pre-wrap ${m.role==='user'?'bg-blue-600 text-white ml-auto':'bg-white border text-gray-800'}`}>{m.message}</div>
        </div>
      ))}
      {loading && <div className="text-xs text-gray-500">Checking…</div>}
    </div>
  )
}
