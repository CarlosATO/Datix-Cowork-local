# Guía: Preparar Datix para Tauri 2.0

Este documento explica cómo convertir la aplicación web en una aplicación de escritorio nativa usando Tauri.

---

## Requisitos previos
- Rust instalado (https://rustup.rs/)
- Node.js 18+ (ya instalado)
- Frontend funcionando correctamente

---

## Paso 1: Instalar Tauri CLI

En el directorio `frontend/`:

```powershell
npm install -D @tauri-apps/cli@next
```

---

## Paso 2: Inicializar Tauri

Desde el directorio raíz del proyecto:

```powershell
cd D:\Gemini-Cowork-Local
npm install @tauri-apps/api@next
npx tauri init
```

Responde las preguntas del asistente:
- **App name**: datix-soluciones
- **Window title**: Datix Soluciones Profesionales
- **Web assets path**: ../frontend/dist
- **Dev server URL**: http://localhost:5173
- **Dev server command**: cd frontend && npm run dev
- **Build command**: cd frontend && npm run build

---

## Paso 3: Estructura esperada

Después de `tauri init`, la estructura será:

```
D:\Gemini-Cowork-Local\
├── backend/          (FastAPI + Agente)
├── frontend/         (React + Vite)
└── src-tauri/        (Configuración Tauri)
    ├── src/
    │   └── main.rs
    ├── tauri.conf.json
    ├── Cargo.toml
    └── icons/
```

---

## Paso 4: Configurar tauri.conf.json

Edita `src-tauri/tauri.conf.json` para ajustar:

```json
{
  "productName": "Datix Soluciones",
  "version": "1.0.0",
  "identifier": "com.datix.soluciones",
  "build": {
    "beforeDevCommand": "cd ../frontend && npm run dev",
    "beforeBuildCommand": "cd ../frontend && npm run build",
    "devUrl": "http://localhost:5173",
    "frontendDist": "../frontend/dist"
  },
  "bundle": {
    "active": true,
    "targets": "all",
    "windows": {
      "certificateThumbprint": null,
      "digestAlgorithm": "sha256",
      "timestampUrl": ""
    }
  },
  "app": {
    "windows": [
      {
        "title": "Datix Soluciones Profesionales",
        "width": 1200,
        "height": 800,
        "minWidth": 800,
        "minHeight": 600,
        "resizable": true,
        "fullscreen": false
      }
    ]
  }
}
```

---

## Paso 5: Ejecutar en modo desarrollo

```powershell
cd D:\Gemini-Cowork-Local
npx tauri dev
```

Esto abre la app en una ventana nativa de escritorio.

---

## Paso 6: Compilar para producción

```powershell
npx tauri build
```

Esto genera un ejecutable en `src-tauri/target/release/`.

---

## Paso 7: Integración con el Backend

### Opción A: Backend externo
- Mantén el backend corriendo por separado (`python -m uvicorn main:app`)
- El frontend se conecta a `http://localhost:8000/ask`

### Opción B: Backend empaquetado (avanzado)
- Usa Tauri sidecar para empaquetar el backend Python
- Configura el sidecar en `tauri.conf.json`
- El backend se inicia automáticamente con la app

---

## Scripts recomendados (package.json raíz)

Crea un `package.json` en la raíz con:

```json
{
  "name": "datix-soluciones",
  "version": "1.0.0",
  "scripts": {
    "tauri": "tauri",
    "dev": "tauri dev",
    "build": "tauri build"
  },
  "devDependencies": {
    "@tauri-apps/cli": "^2.0.0"
  },
  "dependencies": {
    "@tauri-apps/api": "^2.0.0"
  }
}
```

---

## Características del modo escritorio

✅ Ventana nativa del sistema operativo
✅ Sin barra de dirección del navegador
✅ Icono personalizado en la barra de tareas
✅ Instalador .exe/.msi para Windows
✅ Menor consumo de recursos que Electron

---

## Próximos pasos

1. Ejecuta `npx tauri init` para inicializar
2. Prueba con `npx tauri dev`
3. Personaliza iconos en `src-tauri/icons/`
4. Compila con `npx tauri build`

---

## Notas importantes

- El backend debe estar corriendo para que la app funcione
- Considera empaquetar el backend como sidecar para distribución
- Los adjuntos de archivos funcionarán mejor en modo escritorio
- Tauri puede acceder al sistema de archivos local sin restricciones del navegador