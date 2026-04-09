import os
import json
import sys
import re
import time
import sqlite3

# Forzar codificación UTF-8 para evitar crashes del sidecar (Tauri) con emojis en Windows
if sys.stdout is not None:
    sys.stdout.reconfigure(encoding='utf-8')
if sys.stderr is not None:
    sys.stderr.reconfigure(encoding='utf-8')

import aiosqlite
from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from pathlib import Path
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_groq import ChatGroq
from langchain_together import ChatTogether
from langchain_openai import ChatOpenAI
from langchain_chroma import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langchain_core.tools import tool
from tools import (
    listar_archivos_carpeta, leer_contenido_archivo, leer_pdf, leer_excel,
    crear_carpeta_local, copiar_archivos_por_patron,
    crear_archivo_texto, crear_archivo_word, crear_archivo_excel,
    indexar_directorios_principales, buscar_ruta_en_indice,
    abrir_archivo_o_aplicacion, INDEX_FILE,
    guardar_dato_usuario, obtener_dato_usuario, obtener_todos_datos_usuario,
    guardar_en_memoria, obtener_memoria_conversacion, buscar_en_todas_memorias,
    eliminar_memoria_conversacion, process_text_locally
)
from ai_engine import query_gemma4, engine

# --- Gestión de Configuración Local ---
CONFIG_DIR = Path.home() / ".gemini_cowork"
CONFIG_FILE = CONFIG_DIR / "config.json"
VECTOR_DB_DIR = CONFIG_DIR / "vector_db"
CONVERSATIONS_DB = CONFIG_DIR / "conversations.sqlite"
CHECKPOINTS_DB = CONFIG_DIR / "checkpoints.sqlite"
INDEX_TIMESTAMP_FILE = CONFIG_DIR / "last_index.txt"

# Asegurar que existe el directorio
CONFIG_DIR.mkdir(parents=True, exist_ok=True)

# --- Base de datos de conversaciones ---
def init_conversations_db():
    """Inicializa la base de datos de metadatos de conversaciones."""
    conn = sqlite3.connect(str(CONVERSATIONS_DB))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            message_count INTEGER DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
        )
    """)
    conn.commit()
    conn.close()

# Inicializar DB al importar
init_conversations_db()

# --- PROVEEDORES Y MODELOS DISPONIBLES ---
PROVIDERS = {
    "google": {
        "name": "Google Gemini",
        "models": [
            {"id": "gemini-1.5-flash", "name": "Gemini 1.5 Flash"},
            {"id": "gemini-1.5-pro", "name": "Gemini 1.5 Pro"},
            {"id": "gemini-2.0-flash-exp", "name": "Gemini 2.0 Flash (Experimental)"},
        ],
        "key_prefix": "AIza",
        "key_placeholder": "AIza...",
    },
    "groq": {
        "name": "Groq",
        "models": [
            {"id": "llama-3.3-70b-versatile", "name": "Llama 3.3 70B"},
            {"id": "llama-3.1-8b-instant", "name": "Llama 3.1 8B (rápido)"},
            {"id": "mixtral-8x7b-32768", "name": "Mixtral 8x7B"},
            {"id": "gemma2-9b-it", "name": "Gemma 2 9B"},
        ],
        "key_prefix": "gsk_",
        "key_placeholder": "gsk_...",
    },
    "together": {
        "name": "Together AI",
        "models": [
            {"id": "meta-llama/Llama-3.3-70B-Instruct-Turbo", "name": "Llama 3.3 70B Turbo"},
            {"id": "meta-llama/Llama-3.2-11B-Vision-Instruct-Turbo", "name": "Llama 3.2 11B Vision"},
            {"id": "mistralai/Mixtral-8x7B-Instruct-v0.1", "name": "Mixtral 8x7B"},
        ],
        "key_prefix": "",
        "key_placeholder": "tu-api-key-together",
    },
    "openrouter": {
        "name": "OpenRouter",
        "models": [
            {"id": "nousresearch/hermes-3-llama-3.1-405b:free", "name": "Hermes 3 Llama 405B (gratis)"},
            {"id": "google/gemini-flash-1.5", "name": "Gemini Flash 1.5"},
            {"id": "meta-llama/llama-3.1-8b-instruct", "name": "Llama 3.1 8B"},
            {"id": "microsoft/phi-3-mini-128k-instruct", "name": "Phi-3 Mini"},
            {"id": "mistralai/mistral-7b-instruct", "name": "Mistral 7B"},
        ],
        "key_prefix": "sk-or-",
        "key_placeholder": "sk-or-...",
    },
}

DEFAULT_PROVIDER = "google"
DEFAULT_MODEL = "gemini-1.5-flash"

def get_stored_config() -> dict:
    """Lee toda la configuración guardada."""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except:
            pass
    return {}

def save_full_config(config: dict):
    """Guarda toda la configuración."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)

def get_provider_key(provider: str) -> str:
    """Obtiene la API key de un proveedor específico."""
    config = get_stored_config()
    keys = config.get("api_keys", {})
    return keys.get(provider, "")

def get_active_provider() -> str:
    """Obtiene el proveedor activo."""
    config = get_stored_config()
    return config.get("active_provider", DEFAULT_PROVIDER)

def get_active_model() -> str:
    """Obtiene el modelo activo."""
    config = get_stored_config()
    return config.get("active_model", DEFAULT_MODEL)

def set_provider_key(provider: str, api_key: str):
    """Guarda la API key de un proveedor."""
    config = get_stored_config()
    if "api_keys" not in config:
        config["api_keys"] = {}
    config["api_keys"][provider] = api_key
    save_full_config(config)

def set_active_provider(provider: str, model: str = None):
    """Establece el proveedor y modelo activos."""
    config = get_stored_config()
    config["active_provider"] = provider
    if model:
        config["active_model"] = model
    elif provider in PROVIDERS:
        # Usar primer modelo del proveedor como default
        config["active_model"] = PROVIDERS[provider]["models"][0]["id"]
    save_full_config(config)

# Funciones de compatibilidad
def get_stored_api_key():
    """Obtiene la API key del proveedor activo."""
    return get_provider_key(get_active_provider())

def get_stored_model():
    """Obtiene el modelo activo."""
    return get_active_model()

def save_api_key(api_key: str):
    """Guarda la API Key del proveedor activo."""
    set_provider_key(get_active_provider(), api_key)

def save_config(api_key: str = None, model: str = None):
    """Compatibilidad con código anterior."""
    if api_key:
        save_api_key(api_key)
    if model:
        config = get_stored_config()
        config["active_model"] = model
        save_full_config(config)

def get_llm(provider: str = None, model: str = None, api_key: str = None):
    """Crea el LLM correcto según el proveedor."""
    if not provider:
        provider = get_active_provider()
    if not model:
        model = get_active_model()
    if not api_key:
        api_key = get_provider_key(provider)
    
    if not api_key:
        raise ValueError(f"No hay API key configurada para {provider}")
    
    if provider == "google":
        return ChatGoogleGenerativeAI(
            model=model,
            google_api_key=api_key,
            temperature=0
        )
    elif provider == "groq":
        return ChatGroq(
            model=model,
            api_key=api_key,
            temperature=0
        )
    elif provider == "together":
        return ChatTogether(
            model=model,
            api_key=api_key,
            temperature=0
        )
    elif provider == "openrouter":
        return ChatOpenAI(
            model=model,
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1",
            temperature=0
        )
    else:
        raise ValueError(f"Proveedor no soportado: {provider}")

def get_vector_store():
    """Inicializa la base de datos de memoria local."""
    api_key = get_stored_api_key()
    if not api_key:
        return None
    
    embeddings = GoogleGenerativeAIEmbeddings(
        model="models/embedding-001",
        google_api_key=api_key
    )
    
    return Chroma(
        persist_directory=str(VECTOR_DB_DIR),
        embedding_function=embeddings,
        collection_name="gemini_cowork_memory"
    )

def should_reindex() -> bool:
    """Verifica si debe reindexar (primera vez o pasaron 24h)."""
    if not INDEX_FILE.exists():
        return True
    if not INDEX_TIMESTAMP_FILE.exists():
        return True
    try:
        with open(INDEX_TIMESTAMP_FILE, "r") as f:
            last_index = datetime.fromisoformat(f.read().strip())
        return datetime.now() - last_index > timedelta(hours=24)
    except:
        return True

def save_index_timestamp():
    """Guarda el timestamp del último indexado."""
    with open(INDEX_TIMESTAMP_FILE, "w") as f:
        f.write(datetime.now().isoformat())

app = FastAPI(title="Gemini-Cowork-Local API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ConfigRequest(BaseModel):
    api_key: str

class QueryRequest(BaseModel):
    prompt: str
    conversation_id: Optional[str] = None

class LocalChatRequest(BaseModel):
    message: str
    history: Optional[List[dict]] = None

class NewConversationRequest(BaseModel):
    title: Optional[str] = None

class SyncRequest(BaseModel):
    path: str

# --- Endpoints de Conversaciones ---

@app.get("/conversations")
def list_conversations():
    """Lista todas las conversaciones ordenadas por fecha."""
    conn = sqlite3.connect(str(CONVERSATIONS_DB))
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("""
        SELECT id, title, created_at, updated_at, message_count 
        FROM conversations 
        ORDER BY updated_at DESC
    """)
    conversations = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return {"conversations": conversations}

@app.get("/conversations/{conversation_id}")
def get_conversation(conversation_id: str):
    """Obtiene todos los mensajes de una conversación."""
    conn = sqlite3.connect(str(CONVERSATIONS_DB))
    conn.row_factory = sqlite3.Row
    
    # Obtener metadatos
    cursor = conn.execute("SELECT * FROM conversations WHERE id = ?", (conversation_id,))
    conv = cursor.fetchone()
    if not conv:
        conn.close()
        raise HTTPException(status_code=404, detail="Conversación no encontrada")
    
    # Obtener mensajes
    cursor = conn.execute("""
        SELECT role, content, timestamp 
        FROM messages 
        WHERE conversation_id = ? 
        ORDER BY timestamp ASC
    """, (conversation_id,))
    messages = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return {
        "conversation": dict(conv),
        "messages": messages
    }

@app.post("/conversations/new")
def create_conversation(request: NewConversationRequest = None):
    """Crea una nueva conversación."""
    conv_id = f"conv_{int(time.time() * 1000)}"
    title = request.title if request and request.title else "Nueva conversación"
    now = datetime.now().isoformat()
    
    conn = sqlite3.connect(str(CONVERSATIONS_DB))
    conn.execute("""
        INSERT INTO conversations (id, title, created_at, updated_at, message_count)
        VALUES (?, ?, ?, ?, 0)
    """, (conv_id, title, now, now))
    conn.commit()
    conn.close()
    
    return {"id": conv_id, "title": title, "created_at": now}

@app.delete("/conversations/{conversation_id}")
def delete_conversation(conversation_id: str):
    """Elimina una conversación y todos sus mensajes."""
    conn = sqlite3.connect(str(CONVERSATIONS_DB))
    
    # Verificar que existe
    cursor = conn.execute("SELECT id FROM conversations WHERE id = ?", (conversation_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Conversación no encontrada")
    
    # Eliminar mensajes y conversación
    conn.execute("DELETE FROM messages WHERE conversation_id = ?", (conversation_id,))
    conn.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
    conn.commit()
    conn.close()
    
    # También eliminar del checkpoint de LangGraph si existe
    try:
        checkpoint_conn = sqlite3.connect(str(CHECKPOINTS_DB))
        checkpoint_conn.execute("DELETE FROM checkpoints WHERE thread_id = ?", (conversation_id,))
        checkpoint_conn.commit()
        checkpoint_conn.close()
    except:
        pass
    
    # Eliminar la memoria de la conversación
    try:
        eliminar_memoria_conversacion(conversation_id)
    except:
        pass
    
    return {"status": "deleted", "id": conversation_id}

@app.get("/conversations/{conversation_id}/export")
def export_conversation(conversation_id: str):
    """Exporta una conversación a JSON."""
    conn = sqlite3.connect(str(CONVERSATIONS_DB))
    conn.row_factory = sqlite3.Row
    
    cursor = conn.execute("SELECT * FROM conversations WHERE id = ?", (conversation_id,))
    conv = cursor.fetchone()
    if not conv:
        conn.close()
        raise HTTPException(status_code=404, detail="Conversación no encontrada")
    
    cursor = conn.execute("""
        SELECT role, content, timestamp 
        FROM messages 
        WHERE conversation_id = ? 
        ORDER BY timestamp ASC
    """, (conversation_id,))
    messages = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    export_data = {
        "conversation": dict(conv),
        "messages": messages,
        "exported_at": datetime.now().isoformat()
    }
    
    return JSONResponse(
        content=export_data,
        headers={
            "Content-Disposition": f"attachment; filename=conversation_{conversation_id}.json"
        }
    )

# --- Endpoint de Reindexación ---

@app.post("/index/reindex")
def reindex_files():
    """Fuerza un reindexado de archivos."""
    result = indexar_directorios_principales.invoke({})
    save_index_timestamp()
    return {"status": "success", "result": result}

@app.get("/index/status")
def index_status():
    """Devuelve el estado del índice."""
    needs_reindex = should_reindex()
    last_index = None
    file_count = 0
    
    if INDEX_TIMESTAMP_FILE.exists():
        try:
            with open(INDEX_TIMESTAMP_FILE, "r") as f:
                last_index = f.read().strip()
        except:
            pass
    
    if INDEX_FILE.exists():
        try:
            with open(INDEX_FILE, "r") as f:
                index = json.load(f)
                file_count = len(index)
        except:
            pass
    
    return {
        "indexed": INDEX_FILE.exists(),
        "needs_reindex": needs_reindex,
        "last_index": last_index,
        "file_count": file_count
    }

# --- Healthcheck y Config ---

@app.get("/healthcheck")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}

@tool
def consultar_memoria_local(pregunta: str) -> str:
    """Busca en los recuerdos guardados y documentos indexados de Datix. Úsala cuando el usuario pregunte por algo histórico o general del negocio."""
    db = get_vector_store()
    if not db: return "Error: Memoria no disponible."
    docs = db.similarity_search(pregunta, k=4)
    if not docs: return "No hay recuerdos relevantes."
    return "\n---\n".join([d.page_content for d in docs])

@tool
async def indexar_ruta(ruta: str) -> str:
    """Aprende de una carpeta o archivo físico en el disco y lo indexa en memoria permanentemente."""
    try:
        sync_res = await kb_sync(SyncRequest(path=ruta))
        return f"Éxito: He procesado {sync_res['count']} fragmentos de la ruta {ruta} y han sido añadidos a tu memoria local."
    except Exception as e:
        return f"Error al intentar indexar la ruta: {str(e)}"

def save_message(conversation_id: str, role: str, content: str):
    """Guarda un mensaje en la base de datos."""
    conn = sqlite3.connect(str(CONVERSATIONS_DB))
    now = datetime.now().isoformat()
    
    conn.execute("""
        INSERT INTO messages (conversation_id, role, content, timestamp)
        VALUES (?, ?, ?, ?)
    """, (conversation_id, role, content, now))
    
    # Actualizar contador y timestamp de la conversación
    conn.execute("""
        UPDATE conversations 
        SET message_count = message_count + 1, updated_at = ?
        WHERE id = ?
    """, (now, conversation_id))
    
    conn.commit()
    conn.close()

def update_conversation_title(conversation_id: str, first_message: str):
    """Actualiza el título de la conversación basado en el primer mensaje."""
    title = first_message[:50] + "..." if len(first_message) > 50 else first_message
    conn = sqlite3.connect(str(CONVERSATIONS_DB))
    conn.execute("UPDATE conversations SET title = ? WHERE id = ?", (title, conversation_id))
    conn.commit()
    conn.close()

async def run_agent(llm, user_input: str, conversation_id: str) -> str:
    """Agente LangGraph estricto con memoria persistente SQLite."""
    system_prompt = f"""Eres 'Datix-Cerebro', un agente operativo para Datix Soluciones Profesionales.
Tu objetivo es EJECUTAR TAREAS en la computadora del usuario usando tus herramientas.

CONVERSACIÓN ACTUAL: {conversation_id}

REGLAS DE MEMORIA (MUY IMPORTANTES):
1. AL INICIO de cada conversación, usa 'obtener_todos_datos_usuario' para recordar quién es el usuario.
2. Cuando el usuario te diga su nombre, edad, empresa u otros datos personales → usa 'guardar_dato_usuario'.
3. DESPUÉS de cada acción importante (crear archivo, abrir documento, completar tarea, crear plan estrategico), DEBES usar 'guardar_en_memoria' con el conversation_id actual para registrar qué hiciste.
4. Si el usuario pregunta qué hiciste antes en esta conversación → usa 'obtener_memoria_conversacion'.
5. Si el usuario pregunta por algo de conversaciones anteriores → usa 'buscar_en_todas_memorias'.

REGLAS DE OPERACIÓN:
1. Si el usuario pide trabajar con un archivo sin dar ruta → usa 'buscar_ruta_en_indice' (NO importa mayúsculas/minúsculas).
2. Si el índice no existe → pregunta si desea escanear y ejecuta 'indexar_directorios_principales'.
3. Para crear documentos físicos → usa crear_archivo_word, crear_archivo_excel o crear_archivo_texto.
4. NUNCA devuelvas JSON crudo o simules código. Usa las herramientas físicas.
5. Sé directo, breve y profesional.

HERRAMIENTAS DE MEMORIA DISPONIBLES:
- guardar_dato_usuario(clave, valor): Datos permanentes del usuario (nombre, edad, empresa)
- obtener_dato_usuario(clave): Recuperar un dato del usuario
- obtener_todos_datos_usuario(): Ver TODO el perfil del usuario
- guardar_en_memoria(conversation_id, tipo, contenido): Registrar acciones en esta conversación
- obtener_memoria_conversacion(conversation_id): Ver qué se hizo en esta conversación
- buscar_en_todas_memorias(termino): Buscar en TODAS las conversaciones anteriores

Sistema: {os.name} | Directorio: {os.getcwd()}
"""
    
    tools_list = [
        listar_archivos_carpeta, leer_contenido_archivo, leer_pdf, leer_excel,
        crear_carpeta_local, copiar_archivos_por_patron,
        crear_archivo_texto, crear_archivo_word, crear_archivo_excel,
        consultar_memoria_local, indexar_ruta,
        indexar_directorios_principales, buscar_ruta_en_indice,
        abrir_archivo_o_aplicacion,
        guardar_dato_usuario, obtener_dato_usuario, obtener_todos_datos_usuario,
        guardar_en_memoria, obtener_memoria_conversacion, buscar_en_todas_memorias,
        process_text_locally
    ]
    
    config = {"configurable": {"thread_id": conversation_id}, "recursion_limit": 15}
    
    try:
        async with AsyncSqliteSaver.from_conn_string(str(CHECKPOINTS_DB)) as memory:
            agent = create_react_agent(llm, tools=tools_list, prompt=system_prompt, checkpointer=memory)
            
            try:
                result = await agent.ainvoke(
                    {"messages": [HumanMessage(content=user_input)]},
                    config=config
                )
            except Exception as history_error:
                error_str = str(history_error)
                if "INVALID_CHAT_HISTORY" in error_str or "tool_calls" in error_str:
                    print(f"Historial corrupto, reiniciando conversación: {history_error}")
                    # Limpiar checkpoint corrupto
                    try:
                        checkpoint_conn = sqlite3.connect(str(CHECKPOINTS_DB))
                        checkpoint_conn.execute("DELETE FROM checkpoints WHERE thread_id = ?", (conversation_id,))
                        checkpoint_conn.commit()
                        checkpoint_conn.close()
                    except:
                        pass
                    
                    # Reintentar sin historial
                    async with AsyncSqliteSaver.from_conn_string(str(CHECKPOINTS_DB)) as new_memory:
                        agent = create_react_agent(llm, tools=tools_list, prompt=system_prompt, checkpointer=new_memory)
                        result = await agent.ainvoke(
                            {"messages": [HumanMessage(content=user_input)]},
                            config=config
                        )
                else:
                    raise history_error
        
        last_msg = result["messages"][-1]
        content = last_msg.content
        
        if isinstance(content, list):
            text_parts = [block.get("text", "") for block in content if isinstance(block, dict) and block.get("type") == "text"]
            return "\n".join(text_parts) if text_parts else str(content)
        return content
    except Exception as e:
        print(f"Error Agente: {e}")
        return f"Error de ejecución: {str(e)}"

@app.post("/config/save")
async def config_save(request: ConfigRequest):
    """Guarda API key del proveedor activo."""
    try:
        provider = get_active_provider()
        model = get_active_model()
        
        # Validar la API key
        llm = get_llm(provider=provider, model=model, api_key=request.api_key)
        llm.invoke([HumanMessage(content="test")])
        
        # Guardar si es válida
        set_provider_key(provider, request.api_key)
        return {"status": "success", "provider": provider}
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))

@app.get("/config/status")
def config_status():
    """Estado completo de configuración."""
    provider = get_active_provider()
    return {
        "configured": bool(get_provider_key(provider)),
        "active_provider": provider,
        "active_model": get_active_model(),
        "providers": PROVIDERS,
        "api_keys": {p: bool(get_provider_key(p)) for p in PROVIDERS}
    }

@app.post("/config/provider")
def change_provider(provider: str, model: str = None):
    """Cambia el proveedor activo."""
    if provider not in PROVIDERS:
        raise HTTPException(status_code=400, detail=f"Proveedor inválido: {provider}")
    
    set_active_provider(provider, model)
    return {
        "status": "success",
        "provider": provider,
        "model": get_active_model(),
        "has_key": bool(get_provider_key(provider))
    }

@app.post("/config/key/{provider}")
def save_provider_key(provider: str, api_key: str):
    """Guarda la API key de un proveedor específico."""
    if provider not in PROVIDERS:
        raise HTTPException(status_code=400, detail=f"Proveedor inválido: {provider}")
    
    # Validar la key
    try:
        first_model = PROVIDERS[provider]["models"][0]["id"]
        llm = get_llm(provider=provider, model=first_model, api_key=api_key)
        llm.invoke([HumanMessage(content="test")])
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"API Key inválida: {str(e)}")
    
    set_provider_key(provider, api_key)
    return {"status": "success", "provider": provider}

@app.post("/config/model")
def set_model(model_id: str):
    """Cambia el modelo activo."""
    config = get_stored_config()
    config["active_model"] = model_id
    save_full_config(config)
    return {"status": "success", "model": model_id}

@app.get("/config/models")
def get_models():
    """Devuelve los proveedores y modelos disponibles."""
    return {
        "active_provider": get_active_provider(),
        "active_model": get_active_model(),
        "providers": PROVIDERS,
        "api_keys": {p: bool(get_provider_key(p)) for p in PROVIDERS}
    }

@app.post("/kb/sync")
async def kb_sync(request: SyncRequest):
    """Indexa un archivo o carpeta en la memoria local."""
    try:
        api_key = get_stored_api_key()
        if not api_key: raise HTTPException(status_code=401, detail="Configura la clave primero")
        
        path = Path(request.path)
        if not path.exists(): raise HTTPException(status_code=404, detail="Ruta no encontrada")
        
        all_text = ""
        if path.is_file():
            if path.suffix == ".pdf": all_text = leer_pdf.invoke({"ruta_pdf": str(path)})
            else: all_text = leer_contenido_archivo.invoke({"ruta_archivo": str(path)})
        else:
            files = list(path.glob("*.*"))[:5]
            for f in files:
                try: 
                    if f.suffix == ".pdf": all_text += leer_pdf.invoke({"ruta_pdf": str(f)})
                    else: all_text += leer_contenido_archivo.invoke({"ruta_archivo": str(f)})
                except: continue
        
        if not all_text: return {"status": "error", "message": "Archivo vacío"}

        splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
        chunks = splitter.split_text(all_text)
        db = get_vector_store()
        db.add_texts(chunks, metadatas=[{"source": str(path)}]*len(chunks))
        
        return {"status": "success", "count": len(chunks)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/ask")
async def ask(request: QueryRequest):
    api_key = get_stored_api_key()
    if not api_key: raise HTTPException(status_code=401, detail="Sin clave configurada para el proveedor activo")
    
    # Si no hay conversation_id, crear una nueva conversación
    conversation_id = request.conversation_id
    is_new_conversation = False
    
    if not conversation_id:
        conv = create_conversation()
        conversation_id = conv["id"]
        is_new_conversation = True
    
    # Guardar mensaje del usuario
    save_message(conversation_id, "user", request.prompt)
    
    # Actualizar título si es el primer mensaje
    if is_new_conversation:
        update_conversation_title(conversation_id, request.prompt)
    
    # Usar el proveedor y modelo configurado
    try:
        llm = get_llm()
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))
    
    output = await run_agent(llm, request.prompt, conversation_id)
    
    # Guardar respuesta del asistente
    save_message(conversation_id, "assistant", output)
    
    return {"response": output, "conversation_id": conversation_id}

@app.post("/api/chat/local")
async def chat_local(request: LocalChatRequest):
    """
    Endpoint para chatear con el modelo local Gemma 4 a través de Ollama.
    """
    output = query_gemma4(request.message, request.history)
    
    # Si la respuesta empieza con "Error" o "El motor de IA local", 
    # FastAPI devolverá el texto, pero el frontend puede manejarlo.
    return {"response": output, "mode": "local"}

@app.get("/api/ollama/status")
def get_ollama_status():
    """Devuelve el estado de la instalación de Ollama."""
    status = engine.check_status()
    return status

@app.post("/api/ollama/install")
async def install_ollama():
    """Inicia la instalación silenciosa de Ollama."""
    success = await engine.install_ollama_silently()
    if success:
        return {"status": "success", "message": "Instalación completada o ejecutándose en segundo plano."}
    else:
        raise HTTPException(status_code=500, detail="Error durante la instalación de Ollama.")

@app.post("/api/ollama/pull")
async def pull_ollama_model(force: bool = False):
    """Inicia la descarga del modelo configurado."""
    success = await engine.pull_model(force=force)
    if success:
        return {"status": "success", "message": f"Modelo {engine.model_name} descargado."}
    else:
        raise HTTPException(status_code=500, detail="Error descargando el modelo.")

# --- Startup: Auto-indexar si es necesario ---
@app.on_event("startup")
async def startup_event():
    """Al iniciar, verificar si necesita reindexar."""
    if should_reindex():
        print("Indexando archivos automáticamente...")
        try:
            result = indexar_directorios_principales.invoke({})
            save_index_timestamp()
            print(f"Indexación completada: {result}")
        except Exception as e:
            print(f"Error al indexar: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
