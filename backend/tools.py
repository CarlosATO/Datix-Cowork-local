import os
import json
import shutil
import pandas as pd
from pathlib import Path
from docx import Document
from langchain_core.tools import tool

# Directorio de configuración global (coherente con main.py)
CONFIG_DIR = Path.home() / ".gemini_cowork"
INDEX_FILE = CONFIG_DIR / "file_index.json"

# Función de ayuda para IA local (evitar importación circular si fuera necesario, 
# pero aquí ai_engine es independiente)
def _get_local_ai_response(prompt: str) -> str:
    try:
        from ai_engine import query_gemma4
        return query_gemma4(prompt)
    except Exception as e:
        return f"Error al acceder al motor local: {str(e)}"


@tool
def listar_archivos_carpeta(ruta: str) -> str:
    """
    Lista todos los archivos y carpetas dentro de una ruta especificada en el sistema local.
    
    Esta herramienta es útil cuando el usuario quiere explorar el contenido de una carpeta
    en su computadora. Devuelve una lista con los nombres de archivos y directorios.
    
    Args:
        ruta (str): La ruta de la carpeta a explorar (ej: "C:\\Users\\nombre\\Documents" o ".")
    
    Returns:
        str: Una cadena con los nombres de archivos/carpetas separados por líneas, 
             o un mensaje de error si hay problemas.
    
    Ejemplos:
        - Si el usuario dice "muéstrame los archivos de mi escritorio"
        - Si el usuario pregunta "qué hay en la carpeta de descargas"
        - Si el usuario quiere explorar una carpeta específica
    """
    try:
        # Normalizar la ruta
        ruta_abs = os.path.abspath(ruta)
        
        # Verificar que la ruta existe y es un directorio
        if not os.path.exists(ruta_abs):
            return f"❌ Error: La ruta '{ruta}' no existe."
        
        if not os.path.isdir(ruta_abs):
            return f"❌ Error: '{ruta}' no es una carpeta, es un archivo."
        
        # Listar contenido
        contenido = os.listdir(ruta_abs)
        
        if not contenido:
            return f"📁 La carpeta '{ruta}' está vacía."
        
        # Separar archivos y carpetas para mejor visualización
        archivos = []
        carpetas = []
        
        for item in contenido:
            ruta_item = os.path.join(ruta_abs, item)
            if os.path.isdir(ruta_item):
                carpetas.append(f"📁 {item}/")
            else:
                archivos.append(f"📄 {item}")
        
        # Organizar resultado
        resultado = []
        if carpetas:
            resultado.append("=== Carpetas ===")
            resultado.extend(sorted(carpetas))
        
        if archivos:
            resultado.append("=== Archivos ===")
            resultado.extend(sorted(archivos))
        
        return "\n".join(resultado)
    
    except PermissionError:
        return f"❌ Error: Permiso denegado para acceder a '{ruta}'."
    except Exception as e:
        return f"❌ Error inesperado al listar archivos: {str(e)}"


@tool
def leer_contenido_archivo(ruta_archivo: str) -> str:
    """
    Lee y devuelve el contenido completo de un archivo de texto específico.
    
    Esta herramienta es útil para analizar código, revisar configuraciones, 
    examinar datos en archivos de texto plano o entender la estructura de un archivo.
    Compatible con archivos de texto: .txt, .py, .js, .ts, .json, .csv, .md, .html, .xml, etc.
    
    Args:
        ruta_archivo (str): La ruta completa del archivo a leer (ej: "C:\\path\\to\\file.txt" o "./main.py")
    
    Returns:
        str: El contenido del archivo como string. Si es muy grande (>10000 líneas), 
             devuelve solo las primeras líneas con un aviso de truncamiento.
             En caso de error, devuelve un mensaje de error descriptivo.
    
    Ejemplos:
        - Si el usuario dice "lee mi archivo de configuración"
        - Si el usuario pregunta "muéstrame el contenido de este archivo Python"
        - Si el usuario quiere revisar los datos de un CSV
    """
    MAX_LINES = 10000
    
    try:
        # Normalizar la ruta
        ruta_abs = os.path.abspath(ruta_archivo)
        
        # Verificar que el archivo existe
        if not os.path.exists(ruta_abs):
            return f"❌ Error: El archivo '{ruta_archivo}' no existe."
        
        # Verificar que es un archivo (no un directorio)
        if not os.path.isfile(ruta_abs):
            return f"❌ Error: '{ruta_archivo}' es una carpeta, no un archivo."
        
        # Intentar leer el archivo
        try:
            with open(ruta_abs, 'r', encoding='utf-8') as f:
                lineas = f.readlines()
        except UnicodeDecodeError:
            # Intentar con otra codificación si UTF-8 falla
            try:
                with open(ruta_abs, 'r', encoding='latin-1') as f:
                    lineas = f.readlines()
            except:
                return f"❌ Error: No se puede leer '{ruta_archivo}'. Parece ser un archivo binario o tiene una codificación desconocida."
        
        # Verificar si el archivo es muy grande
        if len(lineas) > MAX_LINES:
            contenido = "".join(lineas[:MAX_LINES])
            aviso = f"\n\n⚠️ ARCHIVO TRUNCADO: Este archivo tiene {len(lineas)} líneas. Se muestran solo las primeras {MAX_LINES}."
            return contenido + aviso
        
        # Devolver contenido completo
        return "".join(lineas)
    
    except PermissionError:
        return f"❌ Error: Permiso denegado para leer '{ruta_archivo}'."
    except Exception as e:
        return f"❌ Error inesperado al leer archivo: {str(e)}"


@tool
def leer_pdf(ruta_pdf: str, max_paginas: int = 50) -> str:
    """
    Extrae y devuelve el texto completo de un archivo PDF.
    
    Esta herramienta es útil para analizar documentos PDF, extraer información,
    resumir contenido o buscar texto específico dentro de un PDF.
    
    Args:
        ruta_pdf (str): La ruta completa del archivo PDF (ej: "C:\\documentos\\informe.pdf")
        max_paginas (int): Número máximo de páginas a leer (por defecto 50)
    
    Returns:
        str: El texto extraído del PDF o un mensaje de error si hay problemas.
             Si el PDF tiene más de max_paginas, se leen solo las primeras y se muestra un aviso.
    
    Ejemplos:
        - Si el usuario dice "lee mi PDF y resume el contenido"
        - Si el usuario pregunta "extrae el texto de este documento"
        - Si el usuario quiere buscar información en un PDF
    """
    try:
        from pypdf import PdfReader
    except ImportError:
        return "❌ Error: pypdf no está instalado. Instala con: pip install pypdf"
    
    try:
        # Normalizar la ruta
        ruta_abs = os.path.abspath(ruta_pdf)
        
        # Verificar que el archivo existe
        if not os.path.exists(ruta_abs):
            return f"❌ Error: El archivo '{ruta_pdf}' no existe."
        
        # Verificar que es un archivo PDF
        if not ruta_abs.lower().endswith('.pdf'):
            return f"❌ Error: '{ruta_pdf}' no es un archivo PDF."
        
        # Leer el PDF
        reader = PdfReader(ruta_abs)
        total_paginas = len(reader.pages)
        
        # Determinar cuántas páginas leer
        paginas_a_leer = min(max_paginas, total_paginas)
        
        # Extraer texto
        texto = []
        for i in range(paginas_a_leer):
            page = reader.pages[i]
            texto.append(f"--- Página {i+1} ---\n{page.extract_text()}\n")
        
        resultado = "".join(texto)
        
        # Si se truncó, agregar aviso
        if paginas_a_leer < total_paginas:
            aviso = f"\n\n⚠️ PDF TRUNCADO: Este PDF tiene {total_paginas} páginas. Se extrajeron solo las primeras {paginas_a_leer}."
            resultado += aviso
        
        return resultado
    
    except PermissionError:
        return f"❌ Error: Permiso denegado para leer '{ruta_pdf}'."
    except Exception as e:
        return f"❌ Error al leer PDF: {str(e)}"


@tool
def leer_excel(ruta_excel: str, hoja: str = None, max_filas: int = 1000) -> str:
    """
    Lee y devuelve el contenido de un archivo Excel o CSV.
    
    Esta herramienta es útil para analizar datos en hojas de cálculo, 
    explorar estructuras de datos, o extraer información específica.
    Compatible con: .xlsx, .xls, .csv
    
    Args:
        ruta_excel (str): La ruta del archivo Excel o CSV (ej: "C:\\datos\\datos.xlsx")
        hoja (str): Nombre de la hoja a leer (opcional, por defecto la primera)
        max_filas (int): Número máximo de filas a leer (por defecto 1000)
    
    Returns:
        str: El contenido de la hoja de cálculo formateado como tabla o CSV,
             o un mensaje de error si hay problemas.
    
    Ejemplos:
        - Si el usuario dice "lee este archivo Excel y muéstrame los datos"
        - Si el usuario pregunta "¿cuáles son las columnas principales?"
        - Si el usuario quiere analizar datos de una hoja de cálculo
    """
    try:
        import pandas as pd
    except ImportError:
        return "❌ Error: pandas no está instalado. Instala con: pip install openpyxl pandas"
    
    try:
        # Normalizar la ruta
        ruta_abs = os.path.abspath(ruta_excel)
        
        # Verificar que el archivo existe
        if not os.path.exists(ruta_abs):
            return f"❌ Error: El archivo '{ruta_excel}' no existe."
        
        # Verificar que es un archivo válido
        extension = ruta_abs.lower()
        if not any(extension.endswith(ext) for ext in ['.xlsx', '.xls', '.csv']):
            return f"❌ Error: '{ruta_excel}' no es un archivo Excel (.xlsx, .xls) o CSV."
        
        # Leer el archivo según su tipo
        try:
            if extension.endswith('.csv'):
                df = pd.read_csv(ruta_abs, encoding='utf-8')
            else:
                # Excel
                if hoja:
                    df = pd.read_excel(ruta_abs, sheet_name=hoja)
                else:
                    df = pd.read_excel(ruta_abs)
        except UnicodeDecodeError:
            # Intentar con otra codificación
            df = pd.read_csv(ruta_abs, encoding='latin-1')
        
        # Limitar filas
        if len(df) > max_filas:
            df = df.head(max_filas)
            aviso = f"\n\n⚠️ DATOS TRUNCADOS: La hoja tiene más de {max_filas} filas. Se muestran solo las primeras {max_filas}."
        else:
            aviso = ""
        
        # Formatar como string
        resultado = f"Dimensiones: {df.shape[0]} filas × {df.shape[1]} columnas\n"
        resultado += f"Columnas: {', '.join(df.columns)}\n\n"
        resultado += df.to_string()
        resultado += aviso
        
        return resultado
    
    except PermissionError:
        return f"❌ Error: Permiso denegado para leer '{ruta_excel}'."
    except Exception as e:
        return f"❌ Error al leer Excel/CSV: {str(e)}"

@tool
def crear_carpeta_local(ruta: str) -> str:
    r"""
    Crea una nueva carpeta en la ruta especificada en el disco duro del usuario.
    Ejemplo de ruta válida en Windows: 'C:\Users\carlo\Desktop\MiCarpeta'
    
    Args:
        ruta: La ruta absoluta donde se debe crear la carpeta.
        
    Returns:
        Un mensaje de éxito o el error detallado si falla.
    """
    try:
        os.makedirs(ruta, exist_ok=True)
        return f"Éxito: La carpeta ha sido creada en {ruta}."
    except Exception as e:
        return f"Error al crear la carpeta: {str(e)}"

@tool
def copiar_archivos_por_patron(ruta_origen: str, ruta_destino: str, patron_nombre: str) -> str:
    """
    Busca archivos en 'ruta_origen' cuyo nombre contenga 'patron_nombre' y los copia a 'ruta_destino'.
    Útil para organizar archivos masivamente.
    
    Args:
        ruta_origen: Carpeta donde se buscarán los archivos.
        ruta_destino: Carpeta donde se pegarán los archivos.
        patron_nombre: Texto que debe estar incluido en el nombre del archivo (ej. 'Salida_de_Bodega').
        
    Returns:
        Un resumen de cuántos archivos se copiaron con éxito.
    """
    if not os.path.exists(ruta_origen):
        return f"Error: La ruta de origen {ruta_origen} no existe."
    if not os.path.exists(ruta_destino):
        return f"Error: La ruta de destino {ruta_destino} no existe. Créala primero usando crear_carpeta_local."
        
    archivos_copiados = 0
    try:
        for nombre_archivo in os.listdir(ruta_origen):
            if patron_nombre.lower() in nombre_archivo.lower():
                ruta_completa_origen = os.path.join(ruta_origen, nombre_archivo)
                if os.path.isfile(ruta_completa_origen):
                    ruta_completa_destino = os.path.join(ruta_destino, nombre_archivo)
                    shutil.copy2(ruta_completa_origen, ruta_completa_destino)
                    archivos_copiados += 1
                    
        if archivos_copiados > 0:
            return f"Éxito: Se copiaron {archivos_copiados} archivos que coinciden con '{patron_nombre}' a {ruta_destino}."
        else:
            return f"Aviso: No se encontraron archivos que contengan '{patron_nombre}' en la ruta de origen."
            
    except Exception as e:
        return f"Error durante la copia: {str(e)}"


@tool
def crear_archivo_texto(ruta: str, contenido: str) -> str:
    r"""
    Crea un archivo de texto plano (.txt, .md, .csv, .json) en el disco duro local.

    Args:
        ruta: La ruta absoluta con el nombre y extensión del archivo (ej. 'C:\Docs\resumen.txt').
        contenido: El texto completo que se escribirá en el archivo.
    """
    try:
        with open(ruta, 'w', encoding='utf-8') as f:
            f.write(contenido)
        return f"Éxito: Archivo de texto creado y guardado en {ruta}"
    except Exception as e:
        return f"Error al crear archivo de texto: {str(e)}"


@tool
def crear_archivo_word(ruta: str, contenido: str) -> str:
    r"""
    Crea un documento formal de Microsoft Word (.docx).
    Usa esta herramienta cuando el usuario pida generar informes, actas, contratos o presupuestos.

    Args:
        ruta: Ruta absoluta del archivo terminada en .docx (ej. 'C:\Desktop\Presupuesto_Somyl.docx').
        contenido: El texto que irá dentro del documento.
    """
    try:
        doc = Document()
        doc.add_paragraph(contenido)
        doc.save(ruta)
        return f"Éxito: Documento Word (.docx) creado exitosamente en {ruta}"
    except Exception as e:
        return f"Error al crear documento Word: {str(e)}"


@tool
def crear_archivo_excel(ruta: str, datos_json: str) -> str:
    r"""
    Crea un archivo de Excel (.xlsx) a partir de datos estructurados.

    Args:
        ruta: Ruta absoluta del archivo terminada en .xlsx (ej. 'C:\Docs\Inventario.xlsx').
        datos_json: Un string en formato JSON válido que represente una lista de diccionarios.
                    Ejemplo: '[{"Item": "Cable", "Cant": 10}, {"Item": "Router", "Cant": 2}]'
    """
    try:
        datos = json.loads(datos_json)
        df = pd.DataFrame(datos)
        df.to_excel(ruta, index=False)
        return f"Éxito: Archivo Excel (.xlsx) generado correctamente en {ruta}"
    except Exception as e:
        return f"Error al generar Excel: {str(e)}"


@tool
def indexar_directorios_principales() -> str:
    r"""
    Escanea los directorios clave del usuario (Descargas, Escritorio, Documentos y OneDrive) 
    y guarda un mapa de rutas en un archivo local.
    
    Esta herramienta debe ejecutarse al menos una vez para que el agente pueda
    encontrar archivos sin que el usuario proporcione rutas absolutas.
    
    Returns:
        str: Mensaje indicando cuántos archivos fueron indexados.
    """
    home = str(Path.home())
    
    # Buscar OneDrive dinámicamente (puede tener diferentes nombres)
    onedrive_path = None
    try:
        for d in os.listdir(home):
            full_path = os.path.join(home, d)
            if "OneDrive" in d and os.path.isdir(full_path):
                onedrive_path = full_path
                break
    except:
        pass
    
    directorios_a_escanear = [
        os.path.join(home, "Downloads"),
        os.path.join(home, "Desktop"),
        os.path.join(home, "Documents")
    ]
    if onedrive_path:
        directorios_a_escanear.append(onedrive_path)
    
    index = {}
    archivos_encontrados = 0
    
    try:
        # Asegurar que el directorio de configuración exista
        INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        for directorio in directorios_a_escanear:
            if not os.path.exists(directorio):
                continue
            for root, dirs, files in os.walk(directorio):
                for name in dirs + files:
                    index[name.lower()] = os.path.join(root, name)
                    archivos_encontrados += 1
                    
        with open(INDEX_FILE, "w", encoding="utf-8") as f:
            json.dump(index, f)
            
        return f"✅ Éxito: Indexación completa. Se han mapeado {archivos_encontrados} archivos y carpetas en la memoria del agente."
    except Exception as e:
        return f"❌ Error durante la indexación: {str(e)}"


@tool
def buscar_ruta_en_indice(nombre: str) -> str:
    r"""
    Busca la ruta absoluta de un archivo o carpeta en el índice local.
    
    Úsalo SIEMPRE que el usuario mencione un archivo pero no dé la ruta completa.
    Por ejemplo: 'busca la orden 3752', 'abre el archivo ventas.xlsx', etc.
    
    Args:
        nombre: Nombre completo o parcial del archivo/carpeta a buscar.
    
    Returns:
        str: La ruta encontrada, múltiples coincidencias, o un error si no existe el índice.
    """
    if not INDEX_FILE.exists():
        return "⚠️ El índice no existe. Pregunta al usuario si desea que escanees su PC ejecutando 'indexar_directorios_principales'."
        
    try:
        with open(INDEX_FILE, "r", encoding="utf-8") as f:
            index = json.load(f)
            
        nombre_lower = nombre.lower()
        
        # 1. Búsqueda exacta
        if nombre_lower in index:
            return f"✅ Ruta exacta encontrada: {index[nombre_lower]}"
            
        # 2. Búsqueda parcial (contiene la palabra)
        coincidencias = [ruta for clave, ruta in index.items() if nombre_lower in clave]
        if coincidencias:
            if len(coincidencias) == 1:
                return f"✅ Ruta encontrada: {coincidencias[0]}"
            # Devolvemos máximo 10 para no saturar
            return "📋 Se encontraron múltiples coincidencias:\n" + "\n".join(coincidencias[:10])
            
        return f"❌ No se encontró nada que coincida con '{nombre}' en el índice."
    except Exception as e:
        return f"❌ Error al buscar en el índice: {str(e)}"


@tool
def abrir_archivo_o_aplicacion(ruta_o_nombre: str) -> str:
    r"""
    Abre un archivo, carpeta, aplicación o URL con la aplicación predeterminada del sistema.
    
    Esta herramienta es FUNDAMENTAL. Úsala cuando el usuario diga:
    - "Abre el archivo ventas.xlsx"
    - "Abre Excel" o "Abre Chrome" o "Abre Word"
    - "Abre la carpeta de descargas"
    - "Abre google.com"
    
    Args:
        ruta_o_nombre: Puede ser:
            - Ruta completa a un archivo (C:\Users\...\archivo.xlsx)
            - Nombre de aplicación (chrome, excel, word, notepad, code)
            - URL (https://google.com)
            - Ruta a una carpeta
    
    Returns:
        Mensaje de éxito o error.
    """
    import subprocess
    import webbrowser
    
    # Mapeo de nombres comunes a ejecutables de Windows
    aplicaciones_comunes = {
        "chrome": "chrome",
        "google chrome": "chrome",
        "firefox": "firefox",
        "edge": "msedge",
        "microsoft edge": "msedge",
        "word": "winword",
        "microsoft word": "winword",
        "excel": "excel",
        "microsoft excel": "excel",
        "powerpoint": "powerpnt",
        "outlook": "outlook",
        "notepad": "notepad",
        "bloc de notas": "notepad",
        "calculadora": "calc",
        "calculator": "calc",
        "explorador": "explorer",
        "explorer": "explorer",
        "cmd": "cmd",
        "terminal": "cmd",
        "powershell": "powershell",
        "code": "code",
        "visual studio code": "code",
        "vscode": "code",
        "paint": "mspaint",
        "spotify": "spotify",
        "teams": "teams",
        "microsoft teams": "teams",
        "slack": "slack",
        "zoom": "zoom",
    }
    
    try:
        nombre_lower = ruta_o_nombre.lower().strip()
        
        # 1. Verificar si es una URL
        if nombre_lower.startswith(('http://', 'https://', 'www.')):
            url = ruta_o_nombre if ruta_o_nombre.startswith('http') else f'https://{ruta_o_nombre}'
            webbrowser.open(url)
            return f"✅ URL abierta en el navegador: {url}"
        
        # 2. Verificar si es un nombre de aplicación común
        if nombre_lower in aplicaciones_comunes:
            app = aplicaciones_comunes[nombre_lower]
            subprocess.Popen(app, shell=True)
            return f"✅ Aplicación iniciada: {ruta_o_nombre}"
        
        # 3. Verificar si es una ruta existente (archivo o carpeta)
        ruta_abs = os.path.abspath(ruta_o_nombre)
        if os.path.exists(ruta_abs):
            os.startfile(ruta_abs)
            tipo = "Carpeta" if os.path.isdir(ruta_abs) else "Archivo"
            return f"✅ {tipo} abierto: {ruta_abs}"
        
        # 4. Intentar buscar en el índice si no encontró nada
        if INDEX_FILE.exists():
            with open(INDEX_FILE, "r", encoding="utf-8") as f:
                index = json.load(f)
            
            if nombre_lower in index:
                ruta_encontrada = index[nombre_lower]
                os.startfile(ruta_encontrada)
                return f"✅ Archivo abierto desde índice: {ruta_encontrada}"
            
            # Búsqueda parcial
            for clave, ruta in index.items():
                if nombre_lower in clave:
                    os.startfile(ruta)
                    return f"✅ Archivo abierto: {ruta}"
        
        # 5. Último intento: ejecutar como comando
        try:
            subprocess.Popen(ruta_o_nombre, shell=True)
            return f"✅ Comando ejecutado: {ruta_o_nombre}"
        except:
            pass
        
        return f"❌ No se encontró '{ruta_o_nombre}'. Verifica que exista o esté instalado."
        
    except PermissionError:
        return f"❌ Permiso denegado para abrir '{ruta_o_nombre}'."
    except Exception as e:
        return f"❌ Error al abrir: {str(e)}"


# --- MEMORIA PERMANENTE ---
USER_MEMORY_FILE = CONFIG_DIR / "user_memory.json"
CONVERSATION_MEMORIES_DIR = CONFIG_DIR / "conversation_memories"

def _load_user_memory() -> dict:
    """Carga la memoria del usuario desde el archivo JSON."""
    if USER_MEMORY_FILE.exists():
        try:
            with open(USER_MEMORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {}

def _save_user_memory(data: dict):
    """Guarda la memoria del usuario en el archivo JSON."""
    USER_MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(USER_MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def _get_conversation_memory_file(conversation_id: str) -> Path:
    """Obtiene la ruta del archivo de memoria de una conversación."""
    CONVERSATION_MEMORIES_DIR.mkdir(parents=True, exist_ok=True)
    return CONVERSATION_MEMORIES_DIR / f"{conversation_id}.json"

def _load_conversation_memory(conversation_id: str) -> dict:
    """Carga la memoria de una conversación específica."""
    memory_file = _get_conversation_memory_file(conversation_id)
    if memory_file.exists():
        try:
            with open(memory_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {"hechos": [], "archivos_usados": [], "tareas_realizadas": [], "notas": []}

def _save_conversation_memory(conversation_id: str, data: dict):
    """Guarda la memoria de una conversación."""
    memory_file = _get_conversation_memory_file(conversation_id)
    with open(memory_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def eliminar_memoria_conversacion(conversation_id: str):
    """Elimina la memoria asociada a una conversación. Llamar desde main.py al eliminar conversación."""
    memory_file = _get_conversation_memory_file(conversation_id)
    if memory_file.exists():
        memory_file.unlink()


@tool
def guardar_dato_usuario(clave: str, valor: str) -> str:
    """
    Guarda información PERMANENTE del usuario (nombre, edad, empresa, preferencias).
    
    IMPORTANTE: Usa esto para datos que NO cambian o cambian raramente.
    Esta información persiste PARA SIEMPRE hasta que se borre manualmente.
    
    Args:
        clave: Tipo de dato (nombre, edad, empresa, email, telefono, cargo, etc.)
        valor: El valor a guardar
    
    Ejemplos:
        - "Mi nombre es Carlos" → guardar_dato_usuario("nombre", "Carlos")
        - "Trabajo en Somyl" → guardar_dato_usuario("empresa", "Somyl")
    """
    try:
        memoria = _load_user_memory()
        # Case insensitive para la clave
        clave_lower = clave.lower().strip()
        memoria[clave_lower] = valor
        _save_user_memory(memoria)
        return f"✅ Guardado permanentemente: {clave} = '{valor}'"
    except Exception as e:
        return f"❌ Error al guardar: {str(e)}"


@tool
def obtener_dato_usuario(clave: str) -> str:
    """
    Recupera un dato específico del usuario.
    
    Args:
        clave: Qué dato buscar (nombre, edad, empresa, etc.) - NO importa mayúsculas/minúsculas
    """
    try:
        memoria = _load_user_memory()
        clave_lower = clave.lower().strip()
        
        # Búsqueda exacta
        if clave_lower in memoria:
            return f"{clave.capitalize()}: {memoria[clave_lower]}"
        
        # Búsqueda parcial
        for k, v in memoria.items():
            if clave_lower in k or k in clave_lower:
                return f"{k.capitalize()}: {v}"
        
        return f"No tengo guardado '{clave}' del usuario."
    except Exception as e:
        return f"❌ Error: {str(e)}"


@tool
def obtener_todos_datos_usuario() -> str:
    """
    Recupera TODA la información guardada del usuario.
    
    Úsalo al INICIO de cada conversación para recordar quién es el usuario.
    """
    try:
        memoria = _load_user_memory()
        if not memoria:
            return "No tengo información del usuario guardada todavía."
        
        info = []
        for clave, valor in memoria.items():
            info.append(f"• {clave.capitalize()}: {valor}")
        
        return "📋 Perfil del usuario:\n" + "\n".join(info)
    except Exception as e:
        return f"❌ Error: {str(e)}"


@tool
def guardar_en_memoria(conversation_id: str, tipo: str, contenido: str) -> str:
    """
    Guarda información en la memoria de la conversación actual.
    
    DEBES usar esto para registrar TODO lo importante que ocurre:
    - Archivos creados, abiertos o modificados
    - Tareas completadas
    - Hechos importantes mencionados
    - Notas o recordatorios
    
    Args:
        conversation_id: ID de la conversación actual
        tipo: Categoría (hecho, archivo, tarea, nota)
        contenido: Descripción de lo que guardar
    
    Ejemplos:
        - guardar_en_memoria(id, "archivo", "Creé documento ventas.docx en Escritorio")
        - guardar_en_memoria(id, "hecho", "Usuario mencionó que tiene reunión el lunes")
        - guardar_en_memoria(id, "tarea", "Organicé 50 archivos en la carpeta Documentos")
    """
    try:
        memoria = _load_conversation_memory(conversation_id)
        
        tipo_lower = tipo.lower().strip()
        if tipo_lower in ["hecho", "hechos", "fact"]:
            memoria["hechos"].append(contenido)
        elif tipo_lower in ["archivo", "archivos", "file"]:
            memoria["archivos_usados"].append(contenido)
        elif tipo_lower in ["tarea", "tareas", "task"]:
            memoria["tareas_realizadas"].append(contenido)
        else:
            memoria["notas"].append(contenido)
        
        _save_conversation_memory(conversation_id, memoria)
        return f"✅ Guardado en memoria: [{tipo}] {contenido}"
    except Exception as e:
        return f"❌ Error: {str(e)}"

@tool
def process_text_locally(text: str, instruction: str) -> str:
    """
    Procesa un texto de forma LOCAL usando el modelo Gemma 4 a través de Ollama.
    Úsalo para resumir, extraer datos, o analizar información sensible sin enviarla a la nube.
    
    Args:
        text (str): El texto a procesar.
        instruction (str): La instrucción específica (ej. 'Resume este texto', 'Extrae los montos en dólares').
    """
    prompt = f"### Instrucción:\n{instruction}\n\n### Texto:\n{text}\n\n### Respuesta:"
    return _get_local_ai_response(prompt)


@tool
def obtener_memoria_conversacion(conversation_id: str) -> str:
    """
    Recupera TODO lo guardado en la memoria de esta conversación.
    
    Úsalo para recordar qué se hizo anteriormente en esta conversación.
    
    Args:
        conversation_id: ID de la conversación
    """
    try:
        memoria = _load_conversation_memory(conversation_id)
        
        if not any(memoria.values()):
            return "Esta conversación no tiene memoria guardada todavía."
        
        resultado = ["📚 MEMORIA DE ESTA CONVERSACIÓN:"]
        
        if memoria.get("hechos"):
            resultado.append("\n🔹 Hechos importantes:")
            for h in memoria["hechos"]:
                resultado.append(f"  • {h}")
        
        if memoria.get("archivos_usados"):
            resultado.append("\n📁 Archivos trabajados:")
            for a in memoria["archivos_usados"]:
                resultado.append(f"  • {a}")
        
        if memoria.get("tareas_realizadas"):
            resultado.append("\n✅ Tareas completadas:")
            for t in memoria["tareas_realizadas"]:
                resultado.append(f"  • {t}")
        
        if memoria.get("notas"):
            resultado.append("\n📝 Notas:")
            for n in memoria["notas"]:
                resultado.append(f"  • {n}")
        
        return "\n".join(resultado)
    except Exception as e:
        return f"❌ Error: {str(e)}"


@tool  
def buscar_en_todas_memorias(termino: str) -> str:
    """
    Busca un término en TODAS las memorias de conversaciones anteriores.
    
    Úsalo cuando el usuario pregunte por algo que pudo haber mencionado antes
    pero no recuerdas en qué conversación.
    
    Args:
        termino: Palabra o frase a buscar (NO importa mayúsculas/minúsculas)
    """
    try:
        if not CONVERSATION_MEMORIES_DIR.exists():
            return "No hay memorias de conversaciones anteriores."
        
        termino_lower = termino.lower()
        resultados = []
        
        for memory_file in CONVERSATION_MEMORIES_DIR.glob("*.json"):
            try:
                with open(memory_file, "r", encoding="utf-8") as f:
                    memoria = json.load(f)
                
                conv_id = memory_file.stem
                encontrados = []
                
                for categoria, items in memoria.items():
                    if isinstance(items, list):
                        for item in items:
                            if termino_lower in item.lower():
                                encontrados.append(f"[{categoria}] {item}")
                
                if encontrados:
                    resultados.append(f"\n📌 Conversación {conv_id}:")
                    resultados.extend([f"  • {e}" for e in encontrados])
            except:
                continue
        
        if not resultados:
            return f"No encontré '{termino}' en ninguna conversación anterior."
        
        return f"🔍 Resultados para '{termino}':" + "\n".join(resultados)
    except Exception as e:
        return f"❌ Error: {str(e)}"

