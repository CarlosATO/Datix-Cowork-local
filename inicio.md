# Inicio - Levantar servicios

Este documento explica cómo arrancar el Backend (FastAPI con Agente) y el Frontend (Vite + React) en Windows.

---

## Requisitos previos
- Python 3.11+
- Node.js 18+
- API Key de Google Gemini (obtener en: https://aistudio.google.com/app/apikey)

---

## Backend (FastAPI + Agente Inteligente)

### 🛠️ Herramientas disponibles del Agente

El agente tiene acceso a 4 herramientas poderosas:

1. **listar_archivos_carpeta** - Explora directorios del sistema
   - Uso: "Muéstrame los archivos de C:\Users\nombre\Documents"
   - Devuelve: Lista formateada de carpetas y archivos

2. **leer_contenido_archivo** - Lee archivos de texto plano
   - Uso: "Lee el contenido de ./main.py"
   - Soporta: .txt, .py, .js, .json, .csv, .md, .html, etc.

3. **leer_pdf** - Extrae texto de archivos PDF 🆕
   - Uso: "Lee mi documento PDF y resume el contenido"
   - Devuelve: Texto completo de las páginas del PDF

4. **leer_excel** - Lee hojas de cálculo Excel y CSV 🆕
   - Uso: "Muéstrame los datos de este archivo Excel"
   - Devuelve: Tabla formateada con los datos

### Primera instalación: Instalar todas las dependencias

En `D:\Gemini-Cowork-Local\backend` (con venv activado):

```powershell
python -m pip install -r requirements.txt
```

O instalar solo las nuevas (si ya tienes langchain):
```powershell
python -m pip install pypdf openpyxl pandas
```

### Iniciar el servidor

1. **Abrir PowerShell** y navegar al backend:
   ```powershell
   cd D:\Gemini-Cowork-Local\backend
   ```

2. **Activar entorno virtual**:
   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```

3. **Ejecutar el servidor**:
   ```powershell
   python -m uvicorn main:app --reload --port 8000
   ```

4. **Verificar**:
   - Healthcheck: http://localhost:8000/healthcheck
   - Docs interactivos: http://localhost:8000/docs

---

## Frontend (Vite + React + Tailwind)

1. **Abrir otra terminal PowerShell** y navegar al frontend:
   ```powershell
   cd D:\Gemini-Cowork-Local\frontend
   ```

2. **Levantar el dev server**:
   ```powershell
   npm run dev
   ```

3. **Abrir en el navegador**: http://localhost:5173

---

## 🎨 Nuevas características del Frontend

### Interfaz Empresarial
- **Rebranding**: "Datix Soluciones Profesionales"
- **Modo Oscuro/Claro**: Botón ☀️/🌙 en la esquina superior derecha
- **Diseño minimalista**: Bordes redondeados (rounded-2xl), sombras suaves
- **Gradientes modernos**: Indigo → Purple → Pink

### Adjuntar Archivos 📎
- Click en el botón 📎 para adjuntar archivos
- Formatos soportados: PDF, Excel, CSV, TXT, código
- El archivo se muestra como etiqueta antes de enviar
- El agente automáticamente identifica y procesa el archivo

---

## 🛠️ Herramientas disponibles del Agente

| Herramienta | Descripción | Ejemplo |
|---|---|---|
| 📁 **listar_archivos_carpeta** | Explora directorios | "Muéstrame los archivos de C:\Users\..." |
| 📄 **leer_contenido_archivo** | Lee archivos de texto | "Lee el contenido de ./main.py" |
| 📕 **leer_pdf** | Extrae texto de PDFs | "Resume mi documento.pdf" |
| 📊 **leer_excel** | Lee hojas de cálculo | "Muéstrame los datos de ventas.xlsx" |

---

## 🖥️ Convertir a Aplicación de Escritorio (Tauri)

Ver guía completa en: **`TAURI_SETUP.md`**

Resumen rápido:
```powershell
# Instalar Tauri
cd D:\Gemini-Cowork-Local
npm install -D @tauri-apps/cli@next
npx tauri init

# Ejecutar como app de escritorio
npx tauri dev

# Compilar ejecutable
npx tauri build
```

---

## Resumen de puertos
| Servicio | Puerto | URL |
|----------|--------|-----|
| Backend (FastAPI + Agente) | 8000 | http://localhost:8000 |
| Frontend (Vite) | 5173 | http://localhost:5173 |

---

## Solución de problemas

### Error "No module named 'langchain'"
Instala: `python -m pip install langchain`

### Error 429 (cuota agotada)
Ver sección anterior en "Solución de problemas".

### El agente no responde
- Verifica que las herramientas estén importadas en main.py
- Revisa los logs del backend para ver el error detallado
- Asegúrate de que `tools.py` está en la carpeta `backend/`



compilar

cd D:\Gemini-Cowork-Local
.\backend\.venv\Scripts\Activate.ps1
python build_backend.py
cd frontend
npm run tauri build

taskkill /F /IM backend-api.exe /IM app.exe

pruebas locales sin compilar: 

cd frontend
npm run tauri dev
