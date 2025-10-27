import { useState } from 'react'
import axios from 'axios'

const API_URL = 'http://localhost:8000/api/agent/query'

function App() {
  const [prompt, setPrompt] = useState('')
  const [messages, setMessages] = useState([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState(null)

  const handleSubmit = async (event) => {
    event.preventDefault()
    const trimmedPrompt = prompt.trim()

    if (!trimmedPrompt) {
      return
    }

    const userMessage = { role: 'user', content: trimmedPrompt }
    setMessages((prev) => [...prev, userMessage])
    setPrompt('')
    setIsLoading(true)
    setError(null)

    try {
      const { data } = await axios.post(
        API_URL,
        { prompt: trimmedPrompt },
        { headers: { 'Content-Type': 'application/json' } },
      )

      const agentResponse = data?.response ?? 'No response received.'
      setMessages((prev) => [...prev, { role: 'agent', content: agentResponse }])
    } catch (err) {
      setError('Unable to contact the SuperAgent backend. Please try again.')
      setMessages((prev) => prev.slice(0, -1))
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800 bg-slate-900/60 backdrop-blur">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-4 px-6 py-4">
          <h1 className="text-lg font-semibold text-emerald-400">SuperAgent Trader</h1>
          <div className="flex items-center gap-6 text-sm">
            <div className="text-right">
              <p className="text-slate-400">Capital Used</p>
              <p className="font-medium">$0.00</p>
            </div>
            <div className="text-right">
              <p className="text-slate-400">ROI</p>
              <p className="font-medium">0%</p>
            </div>
            <div className="text-right">
              <p className="text-slate-400">Currency</p>
              <p className="font-medium">USD</p>
            </div>
          </div>
        </div>
      </header>

      <main className="mx-auto flex max-w-3xl flex-col gap-6 px-4 py-10">
        <section className="rounded-xl border border-slate-800 bg-slate-900/40 p-6 shadow-lg">
          <h2 className="mb-4 text-lg font-semibold">Chat with SuperAgent</h2>
          <div className="space-y-4 overflow-y-auto rounded-lg border border-slate-800 bg-slate-900/60 p-4 max-h-[50vh]">
            {messages.length === 0 && (
              <p className="text-sm text-slate-400">Start the conversation by asking about trading strategies.</p>
            )}
            {messages.map((message, index) => (
              <div
                key={`${message.role}-${index}`}
                className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <span
                  className={`inline-block max-w-[80%] rounded-lg px-4 py-2 text-sm leading-relaxed ${
                    message.role === 'user'
                      ? 'bg-emerald-500 text-slate-900'
                      : 'bg-slate-800 text-slate-100'
                  }`}
                >
                  {message.content}
                </span>
              </div>
            ))}
          </div>

          <form onSubmit={handleSubmit} className="mt-6 flex flex-col gap-3 sm:flex-row">
            <label htmlFor="prompt" className="sr-only">
              Prompt
            </label>
            <input
              id="prompt"
              type="text"
              value={prompt}
              onChange={(event) => setPrompt(event.target.value)}
              placeholder="Ask SuperAgent about the markets..."
              className="w-full rounded-lg border border-slate-700 bg-slate-900 px-4 py-3 text-sm text-slate-100 placeholder:text-slate-500 focus:border-emerald-400 focus:outline-none focus:ring-2 focus:ring-emerald-400/40"
              disabled={isLoading}
            />
            <button
              type="submit"
              className="inline-flex items-center justify-center rounded-lg bg-emerald-500 px-6 py-3 text-sm font-semibold text-slate-900 transition hover:bg-emerald-400 disabled:cursor-not-allowed disabled:opacity-70"
              disabled={isLoading}
            >
              {isLoading ? 'Sending...' : 'Send'}
            </button>
          </form>

          {error && <p className="mt-2 text-sm text-rose-400">{error}</p>}
        </section>
      </main>
    </div>
  )
}

export default App
