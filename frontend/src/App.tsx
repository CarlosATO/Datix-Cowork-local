import { useState, useEffect, useRef } from 'react'
import { OllamaSetup } from './OllamaSetup'

interface Message {
  role: 'user' | 'assistant'
  content: string
  timestamp?: string
}

interface Conversation {
  id: string
  title: string
  created_at: string
  updated_at: string
  message_count: number
}

function App() {
  const [prompt, setPrompt] = useState('')
  const [messages, setMessages] = useState<Message[]>([])
  const [loading, setLoading] = useState(false)
  const [attachedFile, setAttachedFile] = useState<File | null>(null)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [currentConversationId, setCurrentConversationId] = useState<string | null>(null)
  const [contextMenuId, setContextMenuId] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages, loading])

  // Estado para la API Key y configuración
  const [showSettings, setShowSettings] = useState(false)
  const [apiKeyInput, setApiKeyInput] = useState('')
  const [isConfigured, setIsConfigured] = useState(true)
  const [indexStatus, setIndexStatus] = useState<{indexed: boolean, file_count: number, last_index: string | null}>({indexed: false, file_count: 0, last_index: null})
  const [reindexing, setReindexing] = useState(false)
  
  // Multi-proveedor
  const [activeProvider, setActiveProvider] = useState('google')
  const [activeModel, setActiveModel] = useState('')
  const [providers, setProviders] = useState<Record<string, {name: string, models: {id: string, name: string}[], key_placeholder: string}>>({})
  const [apiKeys, setApiKeys] = useState<Record<string, boolean>>({})
  const [savingKey, setSavingKey] = useState(false)
  
  // Estado para modal inicial de IA Local
  const [showOllamaWelcome, setShowOllamaWelcome] = useState(false)

  // Verificar estado al cargar
  useEffect(() => {
    checkConfigStatus()
    loadConversations()
    checkIndexStatus()
    
    // Verificar si Ollama está instalado al inicio
    fetch('http://127.0.0.1:8000/api/ollama/status')
      .then(res => res.json())
      .then(data => {
        // Solo mostrar si no está instalado y no lo hemos descartado antes
        if (!data.installed && !localStorage.getItem('ollama_dismissed')) {
          setShowOllamaWelcome(true)
        }
      })
      .catch(() => console.error("Ollama no está disponible"))
  }, [])

  // Cerrar menú contextual al hacer clic fuera
  useEffect(() => {
    const handleClick = () => setContextMenuId(null)
    document.addEventListener('click', handleClick)
    return () => document.removeEventListener('click', handleClick)
  }, [])

  // Cargar conversaciones desde el backend
  const loadConversations = async () => {
    try {
      const res = await fetch('http://127.0.0.1:8000/conversations')
      if (res.ok) {
        const data = await res.json()
        setConversations(data.conversations)
      }
    } catch (err) {
      console.error('Error loading conversations:', err)
    }
  }

  // Cargar una conversación específica
  const loadConversation = async (conversationId: string) => {
    try {
      const res = await fetch(`http://127.0.0.1:8000/conversations/${conversationId}`)
      if (res.ok) {
        const data = await res.json()
        setMessages(data.messages.map((m: any) => ({
          role: m.role,
          content: m.content,
          timestamp: m.timestamp
        })))
        setCurrentConversationId(conversationId)
        setSidebarOpen(false)
      }
    } catch (err) {
      console.error('Error loading conversation:', err)
    }
  }

  // Eliminar una conversación
  const deleteConversation = async (conversationId: string) => {
    if (!confirm('¿Eliminar esta conversación?')) return
    
    try {
      const res = await fetch(`http://127.0.0.1:8000/conversations/${conversationId}`, {
        method: 'DELETE'
      })
      if (res.ok) {
        setConversations(prev => prev.filter(c => c.id !== conversationId))
        if (currentConversationId === conversationId) {
          setMessages([])
          setCurrentConversationId(null)
        }
      }
    } catch (err) {
      console.error('Error deleting conversation:', err)
    }
  }

  // Exportar una conversación
  const exportConversation = async (conversationId: string) => {
    try {
      const res = await fetch(`http://127.0.0.1:8000/conversations/${conversationId}/export`)
      if (res.ok) {
        const data = await res.json()
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `conversation_${conversationId}.json`
        a.click()
        URL.revokeObjectURL(url)
      }
    } catch (err) {
      console.error('Error exporting conversation:', err)
    }
  }

  // Nueva conversación
  const startNewConversation = () => {
    setMessages([])
    setCurrentConversationId(null)
    setSidebarOpen(false)
  }

  // Verificar estado del índice
  const checkIndexStatus = async () => {
    try {
      const res = await fetch('http://127.0.0.1:8000/index/status')
      if (res.ok) {
        const data = await res.json()
        setIndexStatus(data)
      }
    } catch (err) {
      console.error('Error checking index:', err)
    }
  }

  // Reindexar archivos
  const handleReindex = async () => {
    setReindexing(true)
    try {
      const res = await fetch('http://127.0.0.1:8000/index/reindex', { method: 'POST' })
      if (res.ok) {
        await checkIndexStatus()
        alert('✅ Archivos indexados correctamente')
      }
    } catch (err) {
      alert('❌ Error al indexar archivos')
    } finally {
      setReindexing(false)
    }
  }

  const checkConfigStatus = async () => {
    try {
      const res = await fetch('http://127.0.0.1:8000/config/status')
      const data = await res.json()
      setIsConfigured(data.configured)
      setActiveProvider(data.active_provider || 'google')
      setActiveModel(data.active_model || '')
      setProviders(data.providers || {})
      setApiKeys(data.api_keys || {})
      if (!data.configured) setShowSettings(true)
    } catch (err) {
      console.error('Error checking config:', err)
    }
  }

  const handleChangeProvider = async (provider: string) => {
    try {
      const res = await fetch(`http://127.0.0.1:8000/config/provider?provider=${provider}`, {
        method: 'POST'
      })
      if (res.ok) {
        const data = await res.json()
        setActiveProvider(provider)
        setActiveModel(data.model)
        setIsConfigured(data.has_key)
      }
    } catch (err) {
      console.error('Error changing provider:', err)
    }
  }

  const handleChangeModel = async (modelId: string) => {
    try {
      const res = await fetch(`http://127.0.0.1:8000/config/model?model_id=${encodeURIComponent(modelId)}`, {
        method: 'POST'
      })
      if (res.ok) {
        setActiveModel(modelId)
      }
    } catch (err) {
      console.error('Error changing model:', err)
    }
  }

  const handleSaveProviderKey = async (provider: string, key: string) => {
    if (!key.trim()) return
    setSavingKey(true)
    try {
      const res = await fetch(`http://127.0.0.1:8000/config/key/${provider}?api_key=${encodeURIComponent(key)}`, {
        method: 'POST'
      })
      if (res.ok) {
        setApiKeys(prev => ({...prev, [provider]: true}))
        setApiKeyInput('')
        if (provider === activeProvider) {
          setIsConfigured(true)
        }
         alert(`✅ API Key de ${providers[provider]?.name || provider} guardada`)
      } else {
        const err = await res.json()
        alert(`❌ ${err.detail}`)
      }
    } catch (err) {
      alert('❌ Error al guardar API Key')
    } finally {
      setSavingKey(false)
    }
  }

  const [isDarkMode, setIsDarkMode] = useState(false)

  useEffect(() => {
    const root = document.documentElement
    if (isDarkMode) {
      root.classList.add('dark')
    } else {
      root.classList.remove('dark')
    }
  }, [isDarkMode])

  const toggleDarkMode = () => {
    setIsDarkMode(prev => !prev)
  }

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      setAttachedFile(file)
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    
    if (!prompt.trim() || loading) return

    let finalPrompt = prompt
    if (attachedFile) {
      finalPrompt = `${prompt}\n\n[Archivo adjunto: ${attachedFile.name}]`
    }

    const userMessage: Message = { 
      role: 'user', 
      content: attachedFile ? `${prompt} 📎 ${attachedFile.name}` : prompt 
    }
    setMessages(prev => [...prev, userMessage])
    setPrompt('')
    setAttachedFile(null)
    setLoading(true)

    try {
      let response;
      let lastError;
      const MAX_RETRIES = 10;

      for (let attempt = 1; attempt <= MAX_RETRIES; attempt++) {
        try {
          response = await fetch('http://127.0.0.1:8000/ask', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
              prompt: finalPrompt, 
              conversation_id: currentConversationId 
            }),
          })

          if (response.status === 401) {
            setShowSettings(true)
            setIsConfigured(false)
            throw new Error('Por favor, configura tu API Key.')
          }

          if (response.ok) break;

          const errorData = await response.json()
          throw new Error(errorData.detail || 'Error al comunicarse con el servidor')
        } catch (error: any) {
          lastError = error;
          if (error.message.includes('API Key')) break;
          
          if (attempt < MAX_RETRIES) {
            await new Promise(resolve => setTimeout(resolve, 1000));
          } else {
            throw lastError;
          }
        }
      }

      if (!response || !response.ok) {
        throw new Error('No se pudo establecer conexión con el servidor después de varios intentos.');
      }

      const data = await response.json()
      
      // Actualizar ID de conversación si es nueva
      if (!currentConversationId && data.conversation_id) {
        setCurrentConversationId(data.conversation_id)
        loadConversations() // Recargar lista
      }
      
      const assistantMessage: Message = { role: 'assistant', content: data.response }
      setMessages(prev => [...prev, assistantMessage])
    } catch (error) {
      const errorMessage: Message = {
        role: 'assistant',
        content: `❌ Error: ${error instanceof Error ? error.message : 'Error desconocido'}`
      }
      setMessages(prev => [...prev, errorMessage])
    } finally {
      setLoading(false)
    }
  }

  // Formatear fecha
  const formatDate = (isoString: string) => {
    const date = new Date(isoString)
    return date.toLocaleString('es-ES', { 
      day: '2-digit', 
      month: 'short', 
      hour: '2-digit', 
      minute: '2-digit' 
    })
  }

  return (
    <div className="flex h-screen bg-white dark:bg-gray-950 transition-colors duration-300 font-sans text-gray-900 dark:text-gray-100">
      
      {/* Overlay para cerrar sidebar en móvil */}
      {sidebarOpen && (
        <div 
          className="fixed inset-0 bg-black/20 backdrop-blur-sm z-40 md:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar Retráctil */}
      <aside className={`
        fixed md:relative z-50 h-full w-72 
        bg-gray-50 dark:bg-gray-900 
        border-r border-gray-200 dark:border-gray-800 
        flex flex-col
        transform transition-transform duration-300 ease-in-out
        ${sidebarOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0 md:w-0 md:border-0 md:overflow-hidden'}
      `}>
        <div className="p-4 flex items-center justify-between">
          <button 
            onClick={startNewConversation}
            className="flex-1 py-3 px-4 bg-gray-200/50 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 rounded-full text-sm font-medium flex items-center gap-3 transition-all"
          >
            <span className="text-xl">+</span> Nuevo chat
          </button>
          <button 
            onClick={() => setSidebarOpen(false)}
            className="ml-2 p-2 hover:bg-gray-200 dark:hover:bg-gray-800 rounded-full md:hidden"
          >
            ✕
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-4 space-y-1 focus:outline-none">
          <div className="text-xs font-semibold text-gray-400 dark:text-gray-500 uppercase tracking-wider px-2 mt-4 mb-2">
            Conversaciones
          </div>
          
          {conversations.length === 0 ? (
            <p className="text-xs text-gray-400 dark:text-gray-600 px-2 italic">
              Sin conversaciones aún
            </p>
          ) : (
            conversations.map((conv) => (
              <div 
                key={conv.id}
                className={`relative p-2 text-sm rounded-xl cursor-pointer group flex items-center justify-between ${
                  currentConversationId === conv.id 
                    ? 'bg-indigo-100 dark:bg-indigo-900/30 text-indigo-700 dark:text-indigo-300' 
                    : 'text-gray-600 dark:text-gray-400 hover:bg-gray-200/50 dark:hover:bg-gray-800'
                }`}
                onClick={() => loadConversation(conv.id)}
              >
                <div className="flex-1 min-w-0">
                  <div className="truncate font-medium">{conv.title}</div>
                  <div className="text-[10px] text-gray-400 dark:text-gray-600 mt-0.5 flex items-center gap-2">
                    <span>{formatDate(conv.updated_at)}</span>
                    <span>• {conv.message_count} msgs</span>
                  </div>
                </div>
                
                {/* Botón de menú */}
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    setContextMenuId(contextMenuId === conv.id ? null : conv.id)
                  }}
                  className="p-1 opacity-0 group-hover:opacity-100 hover:bg-gray-300 dark:hover:bg-gray-700 rounded transition-opacity"
                >
                  ⋮
                </button>
                
                {/* Menú contextual */}
                {contextMenuId === conv.id && (
                  <div 
                    className="absolute right-0 top-full mt-1 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl shadow-lg py-1 z-50 min-w-[140px]"
                    onClick={(e) => e.stopPropagation()}
                  >
                    <button
                      onClick={() => {
                        exportConversation(conv.id)
                        setContextMenuId(null)
                      }}
                      className="w-full px-4 py-2 text-left text-sm hover:bg-gray-100 dark:hover:bg-gray-700 flex items-center gap-2"
                    >
                      📤 Exportar
                    </button>
                    <button
                      onClick={() => {
                        deleteConversation(conv.id)
                        setContextMenuId(null)
                      }}
                      className="w-full px-4 py-2 text-left text-sm text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 flex items-center gap-2"
                    >
                      🗑️ Eliminar
                    </button>
                  </div>
                )}
              </div>
            ))
          )}
        </div>

        <div className="p-4 border-t border-gray-200 dark:border-gray-800">
           <button 
            onClick={() => {
              setShowSettings(true);
              setSidebarOpen(false);
            }}
            className="w-full py-2 px-3 hover:bg-gray-200 dark:hover:bg-gray-800 rounded-xl flex items-center gap-3 text-sm transition-colors"
           >
             <span>⚙️</span> Configuración
           </button>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="flex-1 flex flex-col relative min-w-0 h-full">
        
        {/* Modal de Bienvenida para IA Local (Ollama) */}
        {showOllamaWelcome && (
          <div className="absolute inset-0 z-[60] bg-black/60 backdrop-blur-sm flex items-center justify-center p-6">
            <OllamaSetup 
              standalone 
              onClose={() => {
                setShowOllamaWelcome(false);
                localStorage.setItem('ollama_dismissed', 'true');
              }} 
            />
          </div>
        )}

        {/* Settings Overlay - Multi-proveedor e IA Local */}
        {showSettings && (
          <div className="absolute inset-0 z-50 bg-white/80 dark:bg-gray-950/90 backdrop-blur-md flex items-center justify-center p-6 overflow-y-auto">
            <div className="w-full max-w-lg bg-white dark:bg-gray-900 p-8 rounded-3xl shadow-2xl border border-gray-100 dark:border-gray-800">
              <div className="text-center mb-6">
                <div className="text-4xl mb-4">⚙️</div>
                <h2 className="text-2xl font-bold">Configuración</h2>
                <p className="text-sm text-gray-500 mt-2">Configura tu proveedor de IA y modelo.</p>
              </div>

              {/* Selector de proveedor */}
              <div className="mb-6">
                <h3 className="text-sm font-semibold mb-2">🌐 Proveedor de IA</h3>
                <div className="grid grid-cols-2 gap-2">
                  {Object.entries(providers).map(([key, prov]) => (
                    <button
                      key={key}
                      onClick={() => handleChangeProvider(key)}
                      className={`p-3 rounded-xl border-2 transition-all text-left ${
                        activeProvider === key 
                          ? 'border-indigo-500 bg-indigo-50 dark:bg-indigo-900/30' 
                          : 'border-gray-200 dark:border-gray-700 hover:border-gray-300'
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-medium text-sm">{prov.name}</span>
                        {apiKeys[key] && <span className="text-green-500">✓</span>}
                      </div>
                    </button>
                  ))}
                </div>
              </div>

              {/* API Key del proveedor activo */}
              <div className="mb-6">
                <h3 className="text-sm font-semibold mb-2">🔑 API Key - {providers[activeProvider]?.name}</h3>
                <p className="text-xs text-gray-500 mb-3">
                  {apiKeys[activeProvider] ? '✅ Configurada' : '❌ No configurada'}
                </p>
                <div className="flex gap-2">
                  <input
                    type="password"
                    value={apiKeyInput}
                    onChange={(e) => setApiKeyInput(e.target.value)}
                    placeholder={providers[activeProvider]?.key_placeholder || 'Pega tu API Key...'}
                    className="flex-1 px-4 py-3 bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500 text-sm"
                  />
                  <button
                    onClick={() => handleSaveProviderKey(activeProvider, apiKeyInput)}
                    disabled={savingKey || !apiKeyInput.trim()}
                    className="px-4 py-3 bg-indigo-600 text-white font-bold rounded-xl hover:bg-indigo-700 transition-all disabled:opacity-50 text-sm"
                  >
                    {savingKey ? '...' : 'Guardar'}
                  </button>
                </div>
              </div>

              {/* Selector de modelo */}
              <div className="mb-6">
                <h3 className="text-sm font-semibold mb-2">🤖 Modelo</h3>
                <select
                  value={activeModel}
                  onChange={(e) => handleChangeModel(e.target.value)}
                  className="w-full px-3 py-2 bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500 text-sm"
                >
                  {providers[activeProvider]?.models?.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.name}
                    </option>
                  ))}
                </select>
              </div>

              {/* Sección de indexación */}
              <div className="mb-6 pt-6 border-t border-gray-200 dark:border-gray-700">
                <h3 className="text-sm font-semibold mb-2">📁 Indexación de archivos</h3>
                <p className="text-xs text-gray-500 mb-3">
                  {indexStatus.indexed 
                    ? `${indexStatus.file_count} archivos indexados` 
                    : 'Sin indexar'}
                  {indexStatus.last_index && (
                    <span className="block mt-1">Último: {formatDate(indexStatus.last_index)}</span>
                  )}
                </p>
                <button
                  onClick={handleReindex}
                  disabled={reindexing}
                  className="w-full py-2 bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-xl hover:bg-gray-300 dark:hover:bg-gray-600 transition-all disabled:opacity-50 text-sm"
                >
                  {reindexing ? '🔄 Indexando...' : '🔍 Reindexar archivos'}
                </button>
              </div>

              {/* Sección de IA Local Integrada */}
              <div className="mb-6 pt-6 border-t border-gray-200 dark:border-gray-700">
                <OllamaSetup />
                <div className="mt-3 text-xs text-gray-500 text-center">
                  * Si configuras IA Local, usa el botón "IA Local" que aparecerá en el chat para enviar mensajes directos al motor sin usar internet.
                  (O selecciona el modo por defecto en un futuro ajuste).
                </div>
              </div>

              {/* Resumen de proveedores */}
              <div className="pt-4 border-t border-gray-200 dark:border-gray-700">
                <h3 className="text-xs font-semibold mb-2 text-gray-500">APIs Configuradas:</h3>
                <div className="flex flex-wrap gap-2">
                  {Object.entries(apiKeys).map(([key, configured]) => (
                    <span 
                      key={key}
                      className={`px-2 py-1 rounded text-xs ${
                        configured 
                          ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400' 
                          : 'bg-gray-100 text-gray-500 dark:bg-gray-800'
                      }`}
                    >
                      {providers[key]?.name || key} {configured ? '✓' : '✗'}
                    </span>
                  ))}
                </div>
              </div>

              {isConfigured && (
                <button type="button" onClick={() => setShowSettings(false)} className="w-full text-sm text-gray-500 mt-6 hover:underline">
                  Cerrar
                </button>
              )}
            </div>
          </div>
        )}

        {/* Top Navbar */}
        <header className="h-16 flex items-center justify-between px-4 md:px-6 border-b border-gray-100 dark:border-gray-800 bg-white/50 dark:bg-gray-950/50 backdrop-blur-sm z-10">
          <div className="flex items-center gap-3">
            {/* Botón hamburguesa para abrir sidebar */}
            <button 
              onClick={() => setSidebarOpen(true)}
              className="p-2 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-full transition-colors"
              title="Abrir menú"
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            </button>
            <span className="text-xl font-bold bg-gradient-to-r from-indigo-500 to-purple-600 bg-clip-text text-transparent">
              Datix Cowork
            </span>
          </div>
          
          <button 
            onClick={toggleDarkMode}
            className="p-2 rounded-full hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
          >
            {isDarkMode ? '☀️' : '🌙'}
          </button>
        </header>

        {/* Chat Canvas */}
        <div className="flex-1 overflow-y-auto px-4 md:px-0">
          <div className="max-w-3xl mx-auto py-8 space-y-8">
            
            {messages.length === 0 ? (
              <div className="text-center py-20 animate-fadeIn">
                <h2 className="text-4xl font-semibold mb-4 text-gray-800 dark:text-gray-100">
                  ¿En qué trabajamos hoy?
                </h2>
                <p className="text-gray-500 dark:text-gray-400 max-w-md mx-auto">
                  Estoy listo para analizar tus documentos de Somyl, automatizar tareas o recordar datos de tus proyectos anteriores.
                </p>
              </div>
            ) : (
              messages.map((m, i) => (
                <div key={i} className={`flex gap-4 ${m.role === 'user' ? 'justify-end' : 'justify-start'} animate-fadeIn`}>
                  <div className={`p-4 rounded-2xl max-w-[85%] ${
                    m.role === 'user' 
                      ? 'bg-gray-100 dark:bg-gray-800 text-gray-800 dark:text-gray-100' 
                      : 'bg-transparent text-gray-800 dark:text-gray-200'
                  }`}>
                    {m.role === 'assistant' && <div className="text-xs font-bold text-indigo-500 mb-1">DATIX IA</div>}
                    <div className="text-[15px] leading-relaxed whitespace-pre-wrap">{m.content}</div>
                  </div>
                </div>
              ))
            )}
            
            {loading && (
              <div className="flex gap-4 animate-pulse">
                <div className="text-indigo-500 text-xs font-bold">DATIX IA</div>
                <div className="text-sm text-gray-400">Trabajando...</div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
        </div>

        {/* Floating Input Area */}
        <div className="p-4 bg-gradient-to-t from-white dark:from-gray-950 via-white dark:via-gray-950 to-transparent">
          <form onSubmit={handleSubmit} className="max-w-3xl mx-auto relative">
            
            {attachedFile && (
              <div className="absolute bottom-full mb-3 left-0 animate-slideUp">
                 <span className="px-3 py-1.5 bg-indigo-50 dark:bg-indigo-900/30 text-indigo-600 dark:text-indigo-400 rounded-full text-xs flex items-center gap-2 border border-indigo-100 dark:border-indigo-800">
                    📎 {attachedFile.name}
                    <button type="button" onClick={() => setAttachedFile(null)} className="font-bold hover:text-red-500">×</button>
                 </span>
              </div>
            )}

            <div className="flex items-end gap-2 bg-gray-100 dark:bg-gray-900 rounded-[30px] p-2 pr-4 border border-transparent focus-within:border-gray-200 dark:focus-within:border-gray-700 transition-all shadow-sm">
              <input
                ref={fileInputRef}
                type="file"
                onChange={handleFileSelect}
                className="hidden"
              />
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                className="p-3 text-gray-500 hover:bg-white dark:hover:bg-gray-800 rounded-full transition-all"
                title="Adjuntar"
              >
                <span className="text-2xl font-light">+</span>
              </button>

              <textarea
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    handleSubmit(e as any);
                  }
                }}
                placeholder="Escribe tu instrucción aquí..."
                rows={1}
                className="flex-1 bg-transparent border-none py-3 px-2 focus:ring-0 resize-none text-[15px] outline-none min-h-[48px]"
              />

              {/* Cambiar entre modo nube y local en la misma caja */}
              <div className="flex gap-1 items-center bg-gray-200 dark:bg-gray-800 rounded-full p-1 border border-gray-300 dark:border-gray-700 mx-1">
                <button
                  type="button"
                  onClick={async (e) => {
                    // Chat local directo
                    e.preventDefault();
                    if (!prompt.trim() || loading) return;
                    
                    const userMessage: Message = { role: 'user', content: prompt };
                    setMessages(prev => [...prev, userMessage]);
                    setPrompt('');
                    setLoading(true);
                    
                    try {
                      const res = await fetch('http://127.0.0.1:8000/api/chat/local', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ message: prompt, history: messages.slice(-10) })
                      });
                      if(!res.ok) throw new Error("Error en servidor IA local");
                      const data = await res.json();
                      setMessages(prev => [...prev, { role: 'assistant', content: data.response }]);
                    } catch (error) {
                      setMessages(prev => [...prev, { role: 'assistant', content: "Error de IA Local o no está disponible." }]);
                    } finally {
                      setLoading(false);
                    }
                  }}
                  disabled={loading || !prompt.trim()}
                  className="px-3 py-2 text-xs font-bold rounded-full bg-purple-600 hover:bg-purple-700 text-white disabled:opacity-30 disabled:grayscale transition-all shadow-sm whitespace-nowrap"
                  title="Enviar por IA Local (Ollama)"
                >
                  IA Local
                </button>
              </div>

              <button
                type="submit"
                disabled={loading || !prompt.trim()}
                className="p-3 bg-indigo-600 hover:bg-indigo-700 text-white rounded-full disabled:opacity-30 disabled:grayscale transition-all shadow-md ml-1"
                title="Enviar modo Nube / Agente Completo"
              >
                <span className="text-xl">🚀</span>
              </button>
            </div>
          </form>
          <p className="text-[10px] text-center text-gray-400 mt-3 uppercase tracking-widest opacity-60">
            Datix Soluciones Profesionales • IA Segura y Local
          </p>
        </div>
      </main>
    </div>
  )
}

export default App
