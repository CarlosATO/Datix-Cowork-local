import { useState, useEffect, useRef } from 'react'

interface Message {
  role: 'user' | 'assistant'
  content: string
}

function App() {
  const [prompt, setPrompt] = useState('')
  const [messages, setMessages] = useState<Message[]>([])
  const [loading, setLoading] = useState(false)
  const [attachedFile, setAttachedFile] = useState<File | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages, loading])

  // Estado para la API Key
  const [showSettings, setShowSettings] = useState(false)
  const [apiKeyInput, setApiKeyInput] = useState('')
  const [isConfigured, setIsConfigured] = useState(true) // Asumimos true hasta checkear
  const [verifying, setVerifying] = useState(false)

  // Verificar estado de configuración al cargar
  useEffect(() => {
    checkConfigStatus()
  }, [])

  const checkConfigStatus = async () => {
    try {
      const res = await fetch('http://127.0.0.1:8000/config/status')
      const data = await res.json()
      setIsConfigured(data.configured)
      if (!data.configured) setShowSettings(true)
    } catch (err) {
      console.error('Error checking config:', err)
    }
  }

  const handleSaveApiKey = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!apiKeyInput.trim()) return
    
    setVerifying(true)
    try {
      const res = await fetch('http://127.0.0.1:8000/config/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ api_key: apiKeyInput }),
      })
      
      const data = await res.json()
      if (res.ok) {
        setIsConfigured(true)
        setShowSettings(false)
        setApiKeyInput('')
        alert('✅ ¡API Key configurada correctamente!')
      } else {
        throw new Error(data.detail || 'Error al validar la clave')
      }
    } catch (err) {
      alert(`❌ ${err instanceof Error ? err.message : 'Error desconocido'}`)
    } finally {
      setVerifying(false)
    }
  }

  // Inicializar dark mode con false por defecto (modo claro)
  const [isDarkMode, setIsDarkMode] = useState(false)

  // Toggle dark mode
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

    // Construir el prompt con el archivo adjunto si existe
    let finalPrompt = prompt
    if (attachedFile) {
      // Anexar referencia al archivo en el prompt
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
          console.log(`Intentando conectar (Intento ${attempt}/${MAX_RETRIES})...`);
          response = await fetch('http://127.0.0.1:8000/ask', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({ prompt: finalPrompt, history: messages }),
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

  return (
    <div className="flex h-screen bg-white dark:bg-gray-950 transition-colors duration-300 font-sans text-gray-900 dark:text-gray-100">
      
      {/* Sidebar - Estilo Gemini */}
      <aside className="w-64 bg-gray-50 dark:bg-gray-900 border-r border-gray-200 dark:border-gray-800 flex flex-col hidden md:flex">
        <div className="p-4">
          <button 
            onClick={() => {
              setMessages([]);
              setPrompt('');
            }}
            className="w-full py-3 px-4 bg-gray-200/50 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 rounded-full text-sm font-medium flex items-center gap-3 transition-all"
          >
            <span className="text-xl">+</span> Nuevo chat
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-4 space-y-2 focus:outline-none">
          <div className="text-xs font-semibold text-gray-400 dark:text-gray-500 uppercase tracking-wider px-2 mt-4 mb-2">
            Recientes
          </div>
          {/* Chats de ejemplo para la estética */}
          <div className="p-2 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-200/50 dark:hover:bg-gray-800 rounded-xl cursor-pointer truncate">
            Revision de Facturas Somyl
          </div>
          <div className="p-2 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-200/50 dark:hover:bg-gray-800 rounded-xl cursor-pointer truncate">
            Análisis de Bodega Central
          </div>
          <div className="p-2 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-200/50 dark:hover:bg-gray-800 rounded-xl cursor-pointer truncate">
            Scripts de automatización
          </div>
        </div>

        <div className="p-4 border-t border-gray-200 dark:border-gray-800">
           <button 
            onClick={() => setShowSettings(true)}
            className="w-full py-2 px-3 hover:bg-gray-200 dark:hover:bg-gray-800 rounded-xl flex items-center gap-3 text-sm transition-colors"
           >
             <span>⚙️</span> Configuración
           </button>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="flex-1 flex flex-col relative min-w-0 h-full">
        
        {/* Settings Overlay - Re-utilizado del anterior */}
        {showSettings && (
          <div className="absolute inset-0 z-50 bg-white/80 dark:bg-gray-950/90 backdrop-blur-md flex items-center justify-center p-6">
            <div className="w-full max-w-md bg-white dark:bg-gray-900 p-8 rounded-3xl shadow-2xl border border-gray-100 dark:border-gray-800">
              <div className="text-center mb-6">
                <div className="text-4xl mb-4">🔑</div>
                <h2 className="text-2xl font-bold">Configuración</h2>
                <p className="text-sm text-gray-500 mt-2">Introduce tu clave para activar el motor Datix.</p>
              </div>
              <form onSubmit={handleSaveApiKey} className="space-y-4">
                <input
                  type="password"
                  value={apiKeyInput}
                  onChange={(e) => setApiKeyInput(e.target.value)}
                  placeholder="Pega tu clave aquí..."
                  className="w-full px-4 py-3 bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500"
                  required
                />
                <button
                  type="submit"
                  disabled={verifying}
                  className="w-full py-3 bg-indigo-600 text-white font-bold rounded-xl hover:bg-indigo-700 transition-all disabled:opacity-50"
                >
                  {verifying ? 'Validando...' : 'Guardar clave'}
                </button>
                {isConfigured && (
                  <button type="button" onClick={() => setShowSettings(false)} className="w-full text-sm text-gray-500 mt-2 hover:underline">
                    Cancelar
                  </button>
                )}
              </form>
            </div>
          </div>
        )}

        {/* Top Navbar */}
        <header className="h-16 flex items-center justify-between px-6 border-b border-gray-100 dark:border-gray-800 bg-white/50 dark:bg-gray-950/50 backdrop-blur-sm z-10">
          <div className="flex items-center gap-2">
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

              <button
                type="submit"
                disabled={loading || !prompt.trim()}
                className="p-3 bg-indigo-600 hover:bg-indigo-700 text-white rounded-full disabled:opacity-30 disabled:grayscale transition-all shadow-md"
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
