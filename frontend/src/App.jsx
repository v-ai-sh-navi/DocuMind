import { useEffect, useRef, useState } from 'react'
import { FileText, Plus, Send, Upload, Trash2, Bot, User, PanelLeftClose, Sparkles, Database, LoaderCircle } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

const API = 'http://127.0.0.1:8000'

export default function App() {
  const [documents, setDocuments] = useState([])
  const [conversations, setConversations] = useState([])
  const [activeId, setActiveId] = useState(null)
  const [messages, setMessages] = useState([])
  const [question, setQuestion] = useState('')
  const [selectedDocs, setSelectedDocs] = useState([])
  const [busy, setBusy] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState('')
  const endRef = useRef(null)
  const fileRef = useRef(null)

  async function loadDocuments() {
    const r = await fetch(`${API}/api/documents`)
    if (r.ok) setDocuments(await r.json())
  }
  async function loadConversations() {
    const r = await fetch(`${API}/api/conversations`)
    if (r.ok) setConversations(await r.json())
  }
  async function openConversation(id) {
    setActiveId(id)
    const r = await fetch(`${API}/api/conversations/${id}/messages`)
    if (r.ok) setMessages(await r.json())
  }
  async function newConversation() {
    const r = await fetch(`${API}/api/conversations`, { method: 'POST' })
    if (!r.ok) return setError('Could not create conversation.')
    const c = await r.json()
    await loadConversations()
    setActiveId(c.id)
    setMessages([])
  }
  async function deleteConversation(id, e) {
    e.stopPropagation()
    await fetch(`${API}/api/conversations/${id}`, { method: 'DELETE' })
    if (activeId === id) { setActiveId(null); setMessages([]) }
    await loadConversations()
  }
  async function deleteDocument(id, e) {
    e.stopPropagation()
    const confirmed = window.confirm(
      'Are you sure you want to delete this PDF?'
    )
    if (!confirmed) return
    const response = await fetch(`${API}/api/documents/${id}`, {
      method: 'DELETE'
    })
    if (!response.ok) {
      alert('Failed to delete PDF.')
      return
    }
    setSelectedDocs(p => p.filter(x => x !== id))
    await loadDocuments()
  }
  async function uploadFile(file) {
    if (!file) return
    setUploading(true); setError('')
    const data = new FormData(); data.append('file', file)
    try {
      const r = await fetch(`${API}/api/upload`, { method: 'POST', body: data })
      const result = await r.json()
      if (!r.ok) throw new Error(result.detail || 'Upload failed')
      await loadDocuments()
      setSelectedDocs(prev => [...prev, result.id])
    } catch (e) { setError(e.message) }
    finally { setUploading(false); if (fileRef.current) fileRef.current.value = '' }
  }
  async function sendQuestion(e) {
    e?.preventDefault()
    if (!question.trim() || busy) return
    setError('')
    let conversationId = activeId
    if (!conversationId) {
      const r = await fetch(`${API}/api/conversations`, { method: 'POST' })
      const c = await r.json(); conversationId = c.id; setActiveId(c.id)
    }
    const q = question.trim()
    setQuestion('')
    setMessages(prev => [...prev, { role: 'user', content: q }])
    setBusy(true)
    try {
      const r = await fetch(`${API}/api/ask`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: q, conversation_id: conversationId, document_ids: selectedDocs.length ? selectedDocs : null })
      })
      const result = await r.json()
      if (!r.ok) throw new Error(result.detail || 'Request failed')
      setMessages(prev => [...prev, { role: 'assistant', content: result.answer, sources: result.sources }])
      await loadConversations()
    } catch (e) {
      setError(e.message)
      setMessages(prev => [...prev, { role: 'assistant', content: `Sorry, something went wrong: ${e.message}` }])
    } finally { setBusy(false) }
  }
  useEffect(() => { loadDocuments(); loadConversations() }, [])
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages, busy])

  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand"><div className="brand-icon"><Sparkles size={19}/></div><div><b>DocuMind</b><small>AI RESEARCH WORKSPACE</small></div></div>
      <button className="new-chat" onClick={newConversation}><Plus size={17}/> New conversation</button>
      <div className="side-label">YOUR LIBRARY</div>
      <button className="upload-card" onClick={() => fileRef.current?.click()}>
        <Upload size={18}/><span><b>{uploading ? 'Uploading…' : 'Upload a PDF'}</b><small>PDF up to 25 MB</small></span>
      </button>
      <input ref={fileRef} type="file" accept="application/pdf,.pdf" hidden onChange={e => uploadFile(e.target.files?.[0])}/>
      <div className="doc-list">
        {documents.map(d => <label className="doc-item" key={d.id}>
          <input type="checkbox" checked={selectedDocs.includes(d.id)} onChange={e => setSelectedDocs(p => e.target.checked ? [...p,d.id] : p.filter(x => x !== d.id))}/>
          <FileText size={15}/><span title={d.filename}>{d.filename}</span>
          <button
            className="delete-doc"
            title="Delete PDF"
            onClick={e => deleteDocument(d.id, e)}
          >
            <Trash2 size={14}/>
          </button>
        </label>)}
        {!documents.length && <p className="muted tiny">Your uploaded PDFs will appear here.</p>}
      </div>
      <div className="side-label history-label">RECENT CHATS</div>
      <div className="history-list">
        {conversations.map(c => <div className={`history-item ${activeId===c.id?'active':''}`} key={c.id} onClick={() => openConversation(c.id)}>
          <span>{c.title}</span><button title="Delete chat" onClick={e => deleteConversation(c.id,e)}><Trash2 size={14}/></button>
        </div>)}
      </div>
      <div className="sidebar-bottom"><Database size={15}/> PostgreSQL connected via API</div>
    </aside>

    <main className="main">
      <header className="topbar"><div><span className="status-dot"></span> AI DOCUMENT ASSISTANT</div><span className="top-tag">HYBRID SEARCH · RAG</span></header>
      <section className="chat-area">
        {messages.length === 0 ? <div className="welcome">
          <div className="hero-icon"><Sparkles size={25}/></div>
          <p className="eyebrow">YOUR DOCUMENTS, UNDERSTOOD</p>
          <h1>Ask your PDFs<br/><span>anything.</span></h1>
          <p className="welcome-copy">Upload research papers, reports, or notes. DocuMind finds relevant passages using semantic and keyword search, then generates answers grounded in your documents.</p>
          <div className="feature-row">
            <div><b>01</b><strong>Upload</strong><small>Add a PDF to your library</small></div>
            <div><b>02</b><strong>Retrieve</strong><small>Hybrid search finds context</small></div>
            <div><b>03</b><strong>Understand</strong><small>Ask questions with sources</small></div>
          </div>
          {!documents.length && <button className="primary-btn" onClick={() => fileRef.current?.click()}><Upload size={16}/> Upload your first PDF</button>}
        </div> : <div className="messages">
          {messages.map((m,i) => <div className={`message ${m.role}`} key={m.id || i}>
            <div className="avatar">{m.role==='assistant'?<Bot size={17}/>:<User size={17}/>}</div>
            <div className="message-body"><div className="message-role">{m.role==='assistant'?'DOCUMIND AI':'YOU'}</div><div className="message-text">
  {m.role === 'assistant' ? (
    <ReactMarkdown 
      remarkPlugins={[remarkGfm]}
      components={{
    a: ({ href, children }) => (
      <a
        href={href}
        onClick={(e) => {
          if (href?.startsWith('#source-')) {
            e.preventDefault()
            document.getElementById(href.slice(1))?.scrollIntoView({
              behavior: 'smooth',
              block: 'center'
            })
          }
        }}
      >
        {children}
      </a>
    )
  }}
      >
      {m.content.replace(
  /\[Source\s+(\d+)\]/g,
  (_, sourceNumber) => {
    const source = m.sources?.[Number(sourceNumber) - 1]
    return source ? `[Page ${source.page}](#source-${m.id || i}-${sourceNumber})` : ''
  }
)}
    </ReactMarkdown>
  ) : (
    m.content
  )}
</div>
              {!!m.sources?.length && (
  <div className="sources">
    <b>Sources</b>
    {[...new Set(m.sources.map(s => s.page))].map(page => (
  <div className="source-page" key={page}>
    <strong>Page {page}</strong>

    {m.sources.map((s, j) =>
      s.page === page ? (
        <div
          className="source"
          id={`source-${m.id || i}-${j + 1}`}
          key={j}
        >
          <FileText size={13} />
          <span>{s.text}</span>
        </div>
      ) : null
    )}
  </div>
))}
  </div>
)}
            </div>
          </div>)}
          {busy && <div className="thinking"><LoaderCircle size={16}/> Searching documents and generating an answer…</div>}
          <div ref={endRef}/>
        </div>}
      </section>
      <div className="composer-wrap">
        {error && <div className="error">{error}</div>}
        <form className="composer" onSubmit={sendQuestion}>
          <textarea value={question} onChange={e => setQuestion(e.target.value)} placeholder={documents.length ? "Ask a question about your selected PDFs…" : "Upload a PDF to get started…"} rows="1" onKeyDown={e => { if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();sendQuestion()} }}/>
          <button className="send-btn" disabled={!question.trim()||busy}><Send size={17}/></button>
        </form>
        <p className="disclaimer">AI can make mistakes. Verify important information against the cited PDF pages.</p>
      </div>
    </main>
  </div>
}
