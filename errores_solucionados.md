# Registro de Errores Solucionados (Datix Cowork Local)

Este archivo sirve como bitácora técnica de fallas críticas y sus soluciones durante el desarrollo de Datix Cowork Local.
**Regla de Arquitectura:** Antes de hacer una refactorización masiva de librerías, leer este documento.

---

## 1. Crash del Servidor: "Failed to fetch" (Conexión rechazada)
**Causa:** `PyInstaller` (en `build_backend.py`) no empaquetaba correctamente librerías dinámicas o metadata de nuevas dependencias como LangGraph o nuevos módulos de LangChain, por lo que el `.exe` crasheaba en silencio al abrirse en el Sidecar de Tauri.
**Solución:** Siempre que se agreguen librerías pesadas o de Inteligencia Artificial al entorno virtual, SE DEBE actualizar el arreglo `copy_metadata` y `hidden_imports` en `build_backend.py`.
**Ejemplo de arreglo:** `"--copy-metadata=langgraph"`, `"--copy-metadata=langchain_core"`.

---

## 2. Model NotFound 404 en la API de Gemini
**Causa:** Durante una reescritura completa del código (`main.py`), la versión del modelo vuelve por defecto a algo anticuado u obsoleto (ej. `models/gemini-1.5-flash`).
**Solución:** Mantener siempre sincronizada y codificada la versión moderna permitida (`models/gemini-2.5-flash` o `models/gemini-3.1-pro`), revisar siempre los LLM invocados en `/ask` y `/config/save`.

---

## 3. Alucinaciones, Bucles y Parser JSON Manual Roto
**Causa:** Originalmente, se pedía a la IA que devolviera un Raw JSON y un Regex se encargaba de filtrarlo (`re.search(...)`). La IA a menudo envolvía la respuesta en Markdown o conversaba al mismo tiempo, rompiendo la experiencia de ejecución de herramientas.
**Solución:** Se abandonó el parsing manual. El proyecto utiliza la arquitectura oficial y robusta de **LangGraph** (`create_react_agent`) que invoca herramientas con llamadas a funciones nativas (*Tool Calling*), definiéndolas como decoradores `@tool`.

---

## 4. Agente sin Memoria a Corto Plazo (Amnesia Conversacional)
**Causa:** El endpoint `/ask` recibía el `prompt` pero destruía el contexto, por lo que la IA pedía "Dime la ruta", el usuario la respondía y la IA olvidaba para qué se la había pedido.
**Solución:** El frontend en React (`App.tsx`) envía TODO el historial del estado `messages` en el Payload del body al backend FastAPI, y el backend lo reconstruye usando ciclos de `HumanMessage` y `AIMessage` dentro de la llamada en LangChain.

---

## 5. Deprecación de LangChain: ImportError 'AgentExecutor'
**Causa:** En LangChain v1.x y superior, `AgentExecutor` de `langchain.agents` ya no es el método recomendado ni disponible en todas las ramas.
**Solución:** Migración completa a LangGraph. Usar siempre `from langgraph.prebuilt import create_react_agent`, y controlar los bucles de llamadas infinitas con el parámetro estricto de invocación `{"recursion_limit": 5}` en el `ainvoke`.

---

## 6. Error de Rutas de Windows (Unicode Escape Error en Python)
**Causa:** Colocar ejemplos de rutas del sistema operativo en Docstrings (ej. `"C:\Users\nombre\Desktop"`) detona que el lector de Python lo tome como caracteres de escape (ej. `\U`).
**Solución:** Declarar los Docstrings como strings "crudos", anteponiendo una r: `r""" ... """` al documentar herramientas para evadir la expansión de Unicode.

---

## 7. Ejecutar Asyncs Bloqueantes (RuntimeWarning: coroutine was never awaited)
**Causa:** Uso de librerías como LangChain que disparan promesas (await) o ejecutan ChromaDB vector stores dentro de funciones def regulares.
**Solución:** Todo el endpoint y el invocador del agente (`run_agent`) deben ser rutinas `async def` y tener en cuenta el `await` correspondiente al invocar a las herramientas de LangChain (ej. `await agent.ainvoke()`).

---

## 8. API Key Revocada: 403 PERMISSION_DENIED ("reported as leaked")
**Causa:** Google escanea repositorios públicos de GitHub en busca de claves API expuestas. Si encuentra una (en código, capturas, logs o archivos de configuración), la **revoca automáticamente** y devuelve un error 403.
**Solución:**
1. NUNCA subir `.env` ni `config.json` a un repositorio público. Verificar siempre que `.gitignore` los excluya.
2. Si ocurre: ir a [Google AI Studio](https://aistudio.google.com/app/apikey), eliminar la clave comprometida y generar una nueva.
3. No compartir capturas de pantalla que muestren la clave en texto plano.

---

## 9. TypeError en create_react_agent(): parámetro incorrecto
**Causa:** La API de `langgraph.prebuilt.create_react_agent()` cambia nombres de parámetros entre versiones. En versiones anteriores se usaba `state_modifier`, pero en la versión instalada (`langgraph==1.1.4`) el parámetro correcto es `prompt`.
**Solución:** Siempre verificar la firma real con `inspect.signature(create_react_agent)` antes de asumir nombres de parámetros. Usar `prompt=` para pasar el system prompt al agente.

---

## 10. Respuesta del Agente viene como Lista de Bloques (no string)
**Causa:** Gemini 2.5 puede devolver `content` como una lista de diccionarios (`[{"type": "text", "text": "..."}]`) en lugar de un string plano, lo cual rompe el frontend si se pasa tal cual.
**Solución:** Verificar `isinstance(content, list)` antes de retornar. Si es lista, extraer las partes de texto. Si es string, retornar directo.

---

## 11. Error INVALID_CHAT_HISTORY al retomar conversación
**Fecha:** 2025-01
**Causa:** LangGraph con `SqliteSaver` almacena mensajes del historial incluyendo `tool_calls` de AIMessage. Si la conversación se corta abruptamente (usuario cierra la app) DESPUÉS de que la IA solicite una herramienta pero ANTES de que se ejecute, el historial queda corrupto: un AIMessage con `tool_calls` pero sin el correspondiente `ToolMessage` de respuesta.
**Síntoma:** Al reiniciar y retomar la conversación: `InvalidUpdateError: INVALID_CHAT_HISTORY: expected AIMessage followed by ToolMessage`.
**Solución:**
1. Capturar `INVALID_CHAT_HISTORY` o `tool_calls` en el mensaje de error.
2. Limpiar el checkpoint corrupto de la DB para ese `thread_id`.
3. Reintentar la invocación del agente con historial limpio.
```python
except Exception as history_error:
    if "INVALID_CHAT_HISTORY" in str(history_error):
        # Limpiar checkpoint corrupto y reintentar
```

---

## 12. SqliteSaver no soporta operaciones async
**Fecha:** 2025-01
**Causa:** El `SqliteSaver` estándar de LangGraph usa operaciones síncronas de SQLite, lo cual bloquea el event loop de FastAPI y genera errores o timeouts.
**Solución:** Usar `AsyncSqliteSaver.from_conn_string()` dentro de un context manager `async with`:
```python
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

async with AsyncSqliteSaver.from_conn_string(str(DB_PATH)) as memory:
    agent = create_react_agent(..., checkpointer=memory)
    result = await agent.ainvoke(...)
```
**Nota:** No usar la conexión directa con `aiosqlite.connect()` porque `AsyncSqliteSaver` necesita el string de conexión.

---

## 13. Conversaciones no persisten: localStorage vs Backend
**Fecha:** 2025-01
**Causa:** El frontend guardaba títulos de conversación en `localStorage`, pero el backend usaba un solo `thread_id` fijo ("datix_session"). Esto significaba que:
- El sidebar mostraba múltiples conversaciones, pero todas apuntaban al mismo hilo en el backend
- Los mensajes se mezclaban entre sesiones
- No se podía retomar una conversación específica
**Solución:** Implementar sistema completo de gestión de conversaciones:
1. Base de datos SQLite separada para metadatos (`conversations.sqlite`)
2. Cada conversación tiene su propio `thread_id` único
3. API REST: `/conversations`, `/conversations/{id}`, DELETE, export
4. El frontend carga conversaciones desde el backend, no localStorage
5. Al enviar mensaje, se pasa `conversation_id` al endpoint `/ask`

---

## 14. PowerShell 5.1 no soporta operador &&
**Fecha:** 2025-01
**Causa:** En Windows con PowerShell 5.1, el operador `&&` para encadenar comandos no funciona. Solo está disponible en PowerShell 7+.
**Síntoma:** `The token '&&' is not a valid statement separator in this version.`
**Solución:** Ejecutar comandos por separado o usar `;` como separador.

---

## 15. El agente no recuerda datos del usuario entre sesiones
**Fecha:** 2025-01
**Causa:** LangGraph con `checkpointer` solo mantiene memoria DENTRO de una misma conversación (thread_id). Cuando el usuario inicia una nueva conversación, el agente no tiene acceso a datos de conversaciones anteriores.
**Síntoma:** Usuario dice "Mi nombre es Carlos" → agente lo recuerda en esa sesión. Al día siguiente, en nueva conversación, agente pregunta "¿cómo te llamas?".
**Solución:** Crear sistema de **Memoria de Usuario** independiente del checkpointer:
1. Archivo JSON: `~/.gemini_cowork/user_memory.json`
2. Herramientas: `guardar_dato_usuario`, `obtener_dato_usuario`, `obtener_todos_datos_usuario`
3. El prompt del sistema instruye al agente a:
   - Usar `guardar_dato_usuario` cuando el usuario comparta información personal
   - Usar `obtener_todos_datos_usuario` al inicio para recordar quién es el usuario
```python
@tool
def guardar_dato_usuario(clave: str, valor: str) -> str:
    memoria = _load_user_memory()
    memoria[clave.lower()] = valor
    _save_user_memory(memoria)
```

---

## 16. Sistema de memoria completo por conversación
**Fecha:** 2025-01
**Implementación:** Además de la memoria de usuario, se creó un sistema de memoria por conversación que guarda TODO lo que ocurre.

**Archivos involucrados:**
- `~/.gemini_cowork/user_memory.json` - Datos permanentes del usuario (nombre, edad, empresa)
- `~/.gemini_cowork/conversation_memories/` - Carpeta con JSON por cada conversación

**Herramientas de memoria:**
1. **guardar_dato_usuario(clave, valor)** - Datos permanentes del usuario
2. **obtener_dato_usuario(clave)** - Recuperar dato (case-insensitive)
3. **obtener_todos_datos_usuario()** - Ver perfil completo
4. **guardar_en_memoria(conversation_id, tipo, contenido)** - Registrar acciones en conversación
5. **obtener_memoria_conversacion(conversation_id)** - Ver historial de la conversación
6. **buscar_en_todas_memorias(termino)** - Buscar en TODAS las conversaciones (case-insensitive)

**Comportamiento:**
- La memoria de conversación se guarda automáticamente cuando el agente completa tareas
- La memoria SOLO se borra cuando se elimina la conversación manualmente desde el sidebar
- Las búsquedas son case-insensitive (no importa mayúsculas/minúsculas)

**Estructura de memoria por conversación:**
```json
{
  "hechos": ["Usuario mencionó que tiene reunión el lunes"],
  "archivos_usados": ["Abrí documento ventas.docx", "Creé reporte.xlsx"],
  "tareas_realizadas": ["Organicé 50 archivos en Documentos"],
  "notas": ["Preferencia: informes en formato PDF"]
}
```

---

## 17. Límite de cuota API 429 RESOURCE_EXHAUSTED
**Fecha:** 2025-01
**Causa:** La API de Google Gemini tiene límites diarios (20 requests/día en capa gratuita para algunos modelos). Al superar el límite, devuelve `429 RESOURCE_EXHAUSTED`.
**Solución:** Implementar sistema multi-proveedor que permite usar diferentes APIs:

**Proveedores soportados:**
1. **Google Gemini** - Modelos: gemini-1.5-flash, gemini-1.5-pro, gemini-2.0-flash-exp
2. **Groq** - Modelos: llama-3.3-70b, llama-3.1-8b, mixtral-8x7b, gemma2-9b (GRATIS, muy rápido)
3. **Together AI** - Modelos: Llama 3.3 70B Turbo, Llama 3.2 Vision, Mixtral
4. **OpenRouter** - Modelos: múltiples modelos gratuitos con `:free` suffix

**Arquitectura:**
```python
PROVIDERS = {
    "google": {"models": [...], "key_placeholder": "AIza..."},
    "groq": {"models": [...], "key_placeholder": "gsk_..."},
    "together": {"models": [...]},
    "openrouter": {"models": [...], "key_placeholder": "sk-or-..."},
}

# config.json ahora soporta múltiples keys
{
  "api_keys": {"google": "...", "groq": "...", "together": "...", "openrouter": "..."},
  "active_provider": "google",
  "active_model": "gemini-1.5-flash"
}
```

**Beneficios:**
- El usuario puede cambiar de proveedor desde la UI sin reiniciar
- Cada proveedor tiene su propia cuota independiente
- Groq es especialmente recomendado por ser muy rápido y generoso
- No requiere instalación local (como Ollama)

**Dependencias nuevas:**
```
langchain-groq
langchain-together  
langchain-openai
```

---

## 18. Error 404 NOT_FOUND con modelos de Gemini
**Fecha:** 2026-04-06
**Causa:** Los nombres de modelos de Google Gemini NO deben incluir el prefijo `models/` en la versión actual de la API. Usar `models/gemini-1.5-flash` genera error 404.
**Síntoma:** `'models/gemini-1.5-flash' is not found for API version v1beta`
**Solución:** Usar nombres SIN el prefijo `models/`:
```python
# ❌ INCORRECTO
{"id": "models/gemini-1.5-flash", "name": "Gemini 1.5 Flash"}

# ✅ CORRECTO
{"id": "gemini-1.5-flash", "name": "Gemini 1.5 Flash"}
```
**Modelos verificados (2026):**
- `gemini-1.5-flash` - Rápido y eficiente
- `gemini-1.5-pro` - Más potente
- `gemini-2.0-flash-exp` - Experimental, última versión

---

## 19. Error 404 con modelos gratuitos de OpenRouter
**Fecha:** 2026-04-06
**Causa:** No todos los modelos con sufijo `:free` están disponibles en OpenRouter. Algunos modelos grandes como `llama-3.3-70b-instruct:free` o `gemini-2.0-flash-exp:free` pueden no estar en la capa gratuita o haber sido deshabilitados.
**Síntoma:** `'No endpoints found for google/gemini-2.0-flash-exp:free'`
**Solución:** Usar solo modelos verificados como disponibles en OpenRouter:

**Modelos gratuitos CONFIRMADOS (2026-04):**
```python
"openrouter": {
    "models": [
        {"id": "meta-llama/llama-3.1-8b-instruct:free", "name": "Llama 3.1 8B"},
        {"id": "microsoft/phi-3-mini-128k-instruct:free", "name": "Phi-3 Mini"},
        {"id": "google/gemma-2-9b-it:free", "name": "Gemma 2 9B"},
        {"id": "qwen/qwen-2-7b-instruct:free", "name": "Qwen 2 7B"},
        {"id": "mistralai/mistral-7b-instruct:free", "name": "Mistral 7B"},
    ]
}
```

**Recomendación:** Usar `llama-3.1-8b-instruct:free` o `phi-3-mini-128k-instruct:free` por su balance entre velocidad y calidad.
