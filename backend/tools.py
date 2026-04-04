import os
from langchain_core.tools import tool


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
