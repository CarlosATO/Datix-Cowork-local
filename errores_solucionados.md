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
