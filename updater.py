import sys
import logging

def update_ytdlp(log_callback=None) -> bool:
    """
    Versão segura para executáveis compilados.
    Verifica atualizações usando apenas a API interna do yt-dlp.
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
            yt_dlp.update.update_self(to_stdout=False)
            log("[Auto-Update] yt-dlp verificado e atualizado com sucesso!")
            return True
        except Exception as e:
            log(f"[Auto-Update] Atualização interna indisponível ({e}).")
    except ImportError:
        log("[Auto-Update] yt-dlp não localizado no ambiente empacotado.")

    return False
