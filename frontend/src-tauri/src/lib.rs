use tauri::Manager;
use std::sync::Mutex;
use tauri_plugin_shell::ShellExt;
use tauri_plugin_shell::process::{CommandEvent, CommandChild};

// Guardamos el proceso hijo en un estado manejado por Tauri
struct SidecarState {
    child_process: Mutex<Option<CommandChild>>,
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_log::Builder::default()
            .level(log::LevelFilter::Info)
            .build())
        .manage(SidecarState {
            child_process: Mutex::new(None),
        })
        .setup(|app| {
            let state: tauri::State<SidecarState> = app.state();
            
            println!("Inicializando sidecar: backend-api");

            // Iniciar el sidecar usando el plugin de shell (recomendado en Tauri v2)
            // Esto equivale a tauri::api::process::Command::new_sidecar de v1
            let sidecar_command = app.shell().sidecar("backend-api")
                .map_err(|e| {
                    eprintln!("Error al configurar el sidecar: {}", e);
                    e
                })?;

            let (mut rx, child) = sidecar_command
                .spawn()
                .map_err(|e| {
                    eprintln!("FALLO AL LANZAR EL SIDECAR: {}", e);
                    e
                })?;

            println!("Sidecar iniciado correctamente (CommandChild)");

            // Escuchar eventos del sidecar (loguear stdout/stderr)
            tauri::async_runtime::spawn(async move {
                while let Some(event) = rx.recv().await {
                    match event {
                        CommandEvent::Stdout(line) => {
                            println!("Sidecar Output: {}", String::from_utf8_lossy(&line));
                        }
                        CommandEvent::Stderr(line) => {
                            eprintln!("Sidecar Error Output: {}", String::from_utf8_lossy(&line));
                        }
                        CommandEvent::Error(err) => {
                            eprintln!("Sidecar Process Error: {}", err);
                        }
                        CommandEvent::Terminated(status) => {
                            println!("Sidecar Terminado con código: {:?}", status.code);
                        }
                        _ => {}
                    }
                }
            });

            // Guardar el proceso hijo para manejo posterior
            *state.child_process.lock().unwrap() = Some(child);

            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(|_app_handle, event| {
            if let tauri::RunEvent::ExitRequested { .. } = event {
                // El usuario cerró la ventana, ahora cerramos el sidecar
                // En Tauri v2 con el plugin Shell, el CommandChild se maneja solo si queremos,
                // pero lo cerramos explícitamente para asegurar.
                let state: tauri::State<SidecarState> = _app_handle.state();
                let maybe_child = state.child_process.lock().unwrap().take();
                
                if let Some(child) = maybe_child {
                    println!("Cerrando sidecar process...");
                    let _ = child.kill();
                }
            }
        });
}
