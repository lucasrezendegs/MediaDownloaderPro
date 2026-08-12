import os
import json

CONFIG_FILE = "config.json"

DEFAULT_CONFIG = {
    "download_path": os.path.join(os.path.expanduser("~"), "Downloads"),
    "cookie_browser": "Nenhum",
    "cookie_file": "",
    "media_mode": "Vídeo + Áudio",
    "video_quality": "Melhor Disponível",
    "max_concurrent": 3,
    "theme": "Dark"
}

def load_config() -> dict:
    """Carrega as configurações salvas no config.json ou retorna os padrões."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Garante que chaves ausentes recebam os valores padrão
                config = DEFAULT_CONFIG.copy()
                config.update(data)
                return config
        except Exception as e:
            print(f"Erro ao ler config.json: {e}")
    return DEFAULT_CONFIG.copy()

def save_config(config: dict) -> bool:
    """Salva as configurações atuais no arquivo local config.json."""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Erro ao salvar config.json: {e}")
        return False
