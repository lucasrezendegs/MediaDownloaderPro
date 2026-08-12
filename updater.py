import sys
import os

def update_ytdlp(log_callback=None) -> bool:
    """
    Atualiza o yt-dlp de forma segura e universal para qualquer PC,
    evitando travamentos caso o sistema operacional bloqueie a sobrescrita.
    """
    def log(msg):
        if log_callback:
            log_callback(msg)
        else:
            print(msg)

    log("[Auto-Update] Verificando atualizações do yt-dlp...")

    try:
        import yt_dlp.update
        try:
            # Tenta a atualização interna padrão
            yt_dlp.update.update_self(to_stdout=False)
            log("[Auto-Update] yt-dlp atualizado com sucesso!")
            return True
        except PermissionError:
            log("[Auto-Update] Sem permissão de administrador para atualizar o binário nesta pasta. Usando versão atual.")
        except Exception as e:
            log(f"[Auto-Update] Atualização automática indisponível nesta máquina ({e}).")
    except ImportError:
        log("[Auto-Update] yt-dlp não localizado no ambiente.")

    return False
