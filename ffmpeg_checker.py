import os
import shutil
import sys

def find_ffmpeg() -> str | None:
    """
    Verifica se o ffmpeg.exe está presente:
    1. Na mesma pasta do executável / script Python.
    2. No PATH do sistema operacional Windows.
    Retorna o caminho absoluto do ffmpeg.exe ou None se não encontrado.
    """
    # 1. Pasta do script ou do executável PyInstaller
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))

    local_ffmpeg = os.path.join(base_dir, "ffmpeg.exe")
    if os.path.exists(local_ffmpeg):
        return local_ffmpeg

    # Também checa sem a extensão .exe caso esteja rodando em Linux/macOS
    local_ffmpeg_bin = os.path.join(base_dir, "ffmpeg")
    if os.path.exists(local_ffmpeg_bin):
        return local_ffmpeg_bin

    # 2. No PATH do sistema
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg

    return None

def is_ffmpeg_available() -> bool:
    """Retorna True se o FFmpeg for encontrado no sistema ou na pasta local."""
    return find_ffmpeg() is not None
