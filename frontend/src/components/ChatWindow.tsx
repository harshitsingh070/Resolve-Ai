type Msg = { role: 'user' | 'assistant'; message: string }
export default function ChatWindow({ messages }: { messages: Msg[] }) {
  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-3 bg-white rounded-xl border shadow-sm" style={{ minHeight: 320, maxHeight: 520 }}>
      {messages.length === 0 && (
        <div className="text-center mt-8">
          <div className="text-sm text-gray-600">👋 No messages yet</div>
          <div className="text-xs text-gray-400 mt-1">Select a PNR above and send your first message — the agent will reply here in order</div>
        </div>
      )}
      {messages.map((m, i) => (
        <div key={i} className="flex flex-col">
          <div className={`text-[11px] mb-1 ${m.role === 'user' ? 'text-right text-blue-600' : 'text-left text-gray-500'}`}>{m.role === 'user' ? 'You' : 'Agent'}</div>
          <div className={`max-w-[80%] p-3 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap ${m.role === 'user' ? 'bg-blue-600 text-white ml-auto rounded-br-sm' : 'bg-gray-100 text-gray-900 mr-auto rounded-bl-sm border'}`}>
            {m.message}
          </div>
        </div>
      ))}
    </div>
  )
}
