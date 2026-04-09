import ollama
import logging
import subprocess
import os
import asyncio

# Configurar logging básico
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LocalAIEngine:
    def __init__(self, model_name: str = "gemma4:4b"):
        self.model_name = model_name

    def query_gemma4(self, prompt: str, context: list = None) -> str:
        """
        Envía una consulta al modelo local Gemma 4 a través de Ollama.
        
        Args:
            prompt (str): El mensaje del usuario.
            context (list, optional): Historial de mensajes previos.
            
        Returns:
            str: Respuesta del modelo o mensaje de error.
        """
        try:
            # Preparar los mensajes para Ollama
            messages = []
            
            # Si hay contexto, lo convertimos al formato de Ollama
            if context:
                for msg in context:
                    role = "user" if msg.get("role", "user") == "user" else "assistant"
                    messages.append({
                        'role': role,
                        'content': msg.get("content", "")
                    })
            
            # Añadir el mensaje actual
            messages.append({
                'role': 'user',
                'content': prompt
            })

            logger.info(f"Consultando modelo local {self.model_name}...")
            
            # Llamada a la API de Ollama
            response = ollama.chat(model=self.model_name, messages=messages)
            
            return response['message']['content']
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error en Ollama: {error_msg}")
            
            # Detectar si es un error de conexión (Ollama no iniciado)
            if "ConnectionError" in error_msg or "11434" in error_msg or "connect" in error_msg.lower():
                return "El motor de IA local (Ollama) no está disponible. Por favor, asegúrate de que Ollama esté ejecutándose en el puerto 11434."
            
            # Error de modelo no encontrado
            if "not found" in error_msg.lower():
                return f"El modelo '{self.model_name}' no se encuentra en Ollama. Ejecuta 'ollama pull {self.model_name}' para descargarlo."
                
            return f"Error al procesar la solicitud local: {error_msg}"

    def check_status(self) -> dict:
        """
        Verifica el estado de la instalación de Ollama y del modelo predeterminado.
        """
        status = {
            "installed": False,
            "running": False,
            "model_downloaded": False
        }
        
        # 1. Verificar si el comando 'ollama' existe
        try:
            # where en Windows, which en Unix
            cmd = "where ollama" if os.name == "nt" else "which ollama"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            if result.returncode == 0:
                status["installed"] = True
        except Exception:
            pass
            
        # 2. Verificar si el servicio está corriendo
        try:
            # ollama.list() arrojará excepción si no conecta
            models_response = ollama.list()
            status["running"] = True
            
            # 3. Verificar si el modelo está descargado
            if 'models' in models_response:
                model_names = [m.get('name') for m in models_response.get('models', [])]
                if self.model_name in model_names or f"{self.model_name}:latest" in model_names:
                    status["model_downloaded"] = True
        except Exception:
            # No corre, o no está instalado
            pass
            
        return status

    async def start_ollama(self) -> bool:
        """Intenta iniciar el servicio de Ollama en segundo plano si no está corriendo."""
        status = self.check_status()
        if status["running"]:
            return True
            
        if not status["installed"]:
            return False
            
        logger.info("Iniciando servicio de Ollama en segundo plano...")
        try:
            # En Windows, usar flag para ocultar ventana
            if os.name == "nt":
                import subprocess
                subprocess.Popen(
                    ["ollama", "serve"],
                    creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS
                )
            else:
                subprocess.Popen(
                    ["ollama", "serve"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            
            # Esperar hasta 20 segundos a que arranque
            for _ in range(20):
                await asyncio.sleep(1)
                # Volver a consultar directamente 
                try:
                    ollama.list()
                    return True
                except:
                    pass
            return False
        except Exception as e:
            logger.error(f"No se pudo iniciar Ollama automáticamente: {e}")
            return False


    async def install_ollama_silently(self) -> bool:
        """
        Ejecuta la instalación silenciosa de Ollama usando winget (Windows).
        Retorna True si tiene éxito o aparenta éxito.
        """
        if os.name != "nt":
            raise NotImplementedError("La instalación automática solo está soportada en Windows vía winget.")
            
        logger.info("Iniciando instalación de Ollama (winget)...")
        cmd = "winget install Ollama.Ollama --silent --accept-source-agreements --accept-package-agreements"
        
        # Ejecutar de forma asíncrona para no bloquear el backend
        process = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode == 0:
            logger.info("Ollama instalado correctamente.")
            return True
        else:
            logger.error(f"Error instalando Ollama: {stderr.decode()}")
            return False

    async def pull_model(self, force: bool = False) -> bool:
        """
        Descarga el modelo configurado.
        """
        status = self.check_status()
        
        if not status["running"]:
            started = await self.start_ollama()
            if not started:
                raise Exception("No se pudo iniciar el servicio Ollama automáticamente. Búscalo en tu menú de Inicio y ábrelo.")

        status = self.check_status()
        if status["model_downloaded"] and not force:
            logger.info(f"El modelo {self.model_name} ya está descargado.")
            return True
            
        logger.info(f"Descargando el modelo {self.model_name}... Esto puede tomar tiempo.")
        try:
            # Realizar pull asincrónico directo con Ollama
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, ollama.pull, self.model_name)
            logger.info(f"Modelo {self.model_name} descargado correctamente.")
            return True
        except Exception as e:
            logger.error(f"Error descargando modelo: {str(e)}")
            return False

# Instancia para exportar
engine = LocalAIEngine()

def query_gemma4(prompt: str, context: list = None) -> str:
    """Función de conveniencia para invocar el motor local."""
    return engine.query_gemma4(prompt, context)
