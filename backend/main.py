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
from langgraph.prebuilt import create_react_agent
from langchain_core.tools import tool
from tools import (
    listar_archivos_carpeta, leer_contenido_archivo, leer_pdf, leer_excel,
    crear_carpeta_local, copiar_archivos_por_patron,
    crear_archivo_texto, crear_archivo_word, crear_archivo_excel
)

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

async def run_agent(llm, user_input: str, history: list[dict]) -> str:
    """Agente LangGraph estricto."""
    system_prompt = """Eres 'Datix-Cerebro', un agente de inteligencia artificial operativo para Datix Soluciones Profesionales.
    Tu objetivo principal no es charlar, sino EJECUTAR TAREAS en la computadora del usuario usando las herramientas disponibles.
    
    REGLAS ESTRICTAS:
    1. Si el usuario te pide crear documentos, resúmenes, informes o presupuestos físicos, DEBES usar crear_archivo_word, crear_archivo_excel o crear_archivo_texto en la ruta solicitada. Si pide listar, mover o copiar archivos, usa la herramienta correspondiente. NUNCA simules la respuesta.
    2. NUNCA devuelvas una simulación de código. Si necesitas hacer algo, invoca la herramienta real.
    3. Si una herramienta falla, informa al usuario el motivo exacto y no intentes inventar el resultado.
    4. Sé directo, breve y profesional. No des largas descripciones a menos que se te pida analizar contenido.
    """
    
    tools_list = [
        listar_archivos_carpeta, leer_contenido_archivo, leer_pdf, leer_excel,
        crear_carpeta_local, copiar_archivos_por_patron,
        crear_archivo_texto, crear_archivo_word, crear_archivo_excel,
        consultar_memoria_local, indexar_ruta
    ]
    
    agent = create_react_agent(llm, tools=tools_list, prompt=system_prompt)
    
    chat_history = []
    for msg in history[-10:]:
        role = msg.get("role")
        content = msg.get("content", "")
        if role == "user": chat_history.append(HumanMessage(content=content))
        elif role == "assistant": chat_history.append(AIMessage(content=content))
        
    try:
        result = await agent.ainvoke(
            {"messages": chat_history + [HumanMessage(content=user_input)]},
            {"recursion_limit": 10}
        )
        last_msg = result["messages"][-1]
        content = last_msg.content
        
        # Gemini 2.5 puede devolver content como lista de bloques
        if isinstance(content, list):
            text_parts = [block.get("text", "") for block in content if isinstance(block, dict) and block.get("type") == "text"]
            return "\n".join(text_parts) if text_parts else str(content)
        return content
    except Exception as e:
        print(f"Error Agente: {e}")
        return f"Error de ejecución: {str(e)}"

@app.post("/config/save")
async def config_save(request: ConfigRequest):
    try:
        llm = ChatGoogleGenerativeAI(model="models/gemini-2.5-flash", google_api_key=request.api_key, temperature=0)
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
    
    llm = ChatGoogleGenerativeAI(model="models/gemini-2.5-flash", google_api_key=api_key, temperature=0)
    output = await run_agent(llm, request.prompt, request.history)
    return {"response": output}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
