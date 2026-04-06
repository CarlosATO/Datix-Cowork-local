
import subprocess
import sys
import os
import shutil

def get_platform_executable_name():
    """Determines the platform-specific executable name for Tauri."""
    if sys.platform == "win32":
        return "backend-api-x86_64-pc-windows-msvc.exe"
    elif sys.platform == "darwin":
        # Assuming Apple Silicon for modern Macs
        return "backend-api-aarch64-apple-darwin"
    elif sys.platform.startswith("linux"):
        return "backend-api-x86_64-unknown-linux-gnu"
    else:
        raise RuntimeError(f"Unsupported platform: {sys.platform}")

def build():
    """Compiles the FastAPI backend using PyInstaller and moves the executable."""
    backend_main_path = os.path.join("backend", "main.py")
    
    # These are packages that PyInstaller might not find automatically.
    # LangChain and its components often need this.
    hidden_imports = [
        "--hidden-import=uvicorn.logging",
        "--hidden-import=uvicorn.loops",
        "--hidden-import=uvicorn.protocols",
        "--hidden-import=uvicorn.lifespan",
        "--hidden-import=uvicorn.loops.auto",
        "--hidden-import=uvicorn.protocols.http.auto",
        "--hidden-import=uvicorn.protocols.websockets.auto",
        # Add any other hidden imports your app might need
    ]
    
    copy_metadata = [
        "--copy-metadata=langchain_google_genai",
        "--copy-metadata=pypdf",
        "--copy-metadata=openpyxl",
        "--copy-metadata=pandas",
        "--copy-metadata=langchain",
        "--copy-metadata=langchain_core",
        "--copy-metadata=langgraph",
        "--copy-metadata=python-docx",
        "--copy-metadata=fastapi",
        "--copy-metadata=uvicorn",
    ]

    command = [
        "pyinstaller",
        "--onefile",
        "--windowed", # Use --noconsole on non-Windows if needed
        "--name", "backend-api",
        *hidden_imports,
        *copy_metadata,
        backend_main_path,
    ]

    print(f"Running command: {' '.join(command)}")
    
    try:
        # We need to run this from the backend directory so it picks up the venv
        # Note: This assumes the script is run from the project root.
        subprocess.run(command, check=True, cwd=os.getcwd())
    except subprocess.CalledProcessError as e:
        print(f"PyInstaller failed: {e}")
        sys.exit(1)
    except FileNotFoundError:
        print("PyInstaller not found. Make sure it's installed in your environment.")
        sys.exit(1)

    print("PyInstaller build successful.")

    # --- Move and rename the executable for Tauri ---
    dist_path = os.path.join(os.getcwd(), "dist")
    original_exe_path = os.path.join(dist_path, "backend-api.exe" if sys.platform == "win32" else "backend-api")
    
    tauri_bin_path = os.path.join(os.getcwd(), "frontend", "src-tauri", "bin")
    if not os.path.exists(tauri_bin_path):
        os.makedirs(tauri_bin_path)
        print(f"Created directory: {tauri_bin_path}")

    platform_exe_name = get_platform_executable_name()
    final_exe_path = os.path.join(tauri_bin_path, platform_exe_name)

    if os.path.exists(original_exe_path):
        print(f"Moving {original_exe_path} to {final_exe_path}")
        shutil.copy(original_exe_path, final_exe_path)
        print("Executable moved and renamed for Tauri sidecar.")
    else:
        print(f"Error: Could not find the built executable at {original_exe_path}")
        sys.exit(1)

    # --- Clean up ---
    print("Cleaning up build artifacts...")
    shutil.rmtree(dist_path, ignore_errors=True)
    shutil.rmtree(os.path.join(os.getcwd(), "build"), ignore_errors=True)
    spec_file = os.path.join(os.getcwd(), "backend-api.spec")
    if os.path.exists(spec_file):
        os.remove(spec_file)
    print("Cleanup complete.")


if __name__ == "__main__":
    build()
