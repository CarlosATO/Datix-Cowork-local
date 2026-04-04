import os
import json
import sys
import re
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pathlib import Path
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_chroma import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from tools import listar_archivos_carpeta, leer_contenido_archivo, leer_pdf, leer_excel

# --- Gestión de Configuración Local ---
CONFIG_DIR = Path.home() / ".gemini_cowork"
CONFIG_FILE = CONFIG_DIR / "config.json"
VECTOR_DB_DIR = CONFIG_DIR / "vector_db"

def get_stored_api_key():
    """Busca la API Key en el archivo de configuración local o en el sistema."""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r") as f:
                data = json.load(f)
                return data.get("api_key")
        except:
            pass
    return os.getenv("GOOGLE_API_KEY")

def save_api_key(api_key: str):
    """Guarda la API Key en la carpeta de usuario de forma persistente."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump({"api_key": api_key}, f)

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
    history: list[dict] = []

class SyncRequest(BaseModel):
    path: str

@app.get("/healthcheck")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}

async def run_agent(llm, user_input: str, history: list[dict]) -> str:
    """Agente con Memoria Inteligente Local (RAG) y contexto de conversación."""
    system_prompt = """Eres Datix-Cerebro, un asistente IA COMPLETAMENTE AUTÓNOMO. Tienes MEMORIA INFINITA y ves el historial.
    
    TÚ interactúas con la PC del usuario a través de herramientas. EL USUARIO NO EJECUTA NADA, TÚ LO HACES.
    Si necesitas ver qué hay en descargas, usa tu herramienta en formato JSON. NUNCA le pidas al usuario que ejecute el JSON.

    HERRAMIENTAS:
    - 'consultar_memoria_local': Buscar en tus recuerdos previos de documentos.
    - 'indexar_ruta': Úsalo cuando el usuario te pida "Aprende de esta carpeta" o "Sincroniza esta ruta".
    - 'listar_archivos_carpeta', 'leer_pdf', 'leer_contenido_archivo', 'leer_excel': Ver y leer archivos actuales.

    Para usar una herramienta, DEBES escribir ÚNICAMENTE un bloque JSON con tu acción.
    Ejemplo:
    {"action": "listar_archivos_carpeta", "ruta": "C:\\Users\\carlo\\Downloads"}
    """
    
    messages = [SystemMessage(content=system_prompt)]
    
    # Añadir historial de la conversación
    for msg in history[-10:]: # Últimos 10 mensajes para mantener contexto sin saturar
        role = msg.get("role")
        content = msg.get("content", "")
        if role == "user":
            messages.append(HumanMessage(content=content))
        elif role == "assistant":
            messages.append(AIMessage(content=content))
            
    messages.append(HumanMessage(content=user_input))
    
    response = llm.invoke(messages)
    text = response.content
    
    try:
        # Extraer JSON de la respuesta usando expresiones regulares (por si viene en bloque markdown)
        json_match = re.search(r'(\{[\s\S]*\})', text)
        
        if json_match:
            action_json = json.loads(json_match.group(1))
            action = action_json.get("action")
            
            if action == "consultar_memoria_local":
                db = get_vector_store()
                docs = db.similarity_search(action_json.get("pregunta", user_input), k=4)
                contexto = "\n---\n".join([d.page_content for d in docs])
                return llm.invoke([
                    SystemMessage(content="Responde basándote en estos recuerdos:"),
                    HumanMessage(content=f"Contexto: {contexto}\nPregunta: {user_input}")
                ]).content

            elif action == "indexar_ruta":
                ruta = action_json.get("path", "")
                sync_res = await kb_sync(SyncRequest(path=ruta))
                return f"✅ ¡Entendido! He procesado {sync_res['count']} fragmentos de {ruta} y ahora los recordaré para siempre."

            elif action == "listar_archivos_carpeta":
                res = listar_archivos_carpeta.invoke({"ruta": action_json.get("ruta", ".")})
                return llm.invoke([SystemMessage(content="Resume la lista:"), HumanMessage(content=res)]).content

    except Exception as e:
        print(f"Error Agente: {e}")
        
    return text

@app.post("/config/save")
async def config_save(request: ConfigRequest):
    try:
        llm = ChatGoogleGenerativeAI(model="models/gemini-2.5-flash", google_api_key=request.api_key)
        llm.invoke([HumanMessage(content="test")])
        save_api_key(request.api_key)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))

@app.get("/config/status")
def config_status():
    return {"configured": bool(get_stored_api_key())}

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
            files = list(path.glob("*.*"))[:5] # Límite para el ejemplo
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
    if not api_key: raise HTTPException(status_code=401, detail="Sin clave")
    
    llm = ChatGoogleGenerativeAI(model="models/gemini-2.5-flash", google_api_key=api_key)
    output = await run_agent(llm, request.prompt, request.history)
    return {"response": output}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
