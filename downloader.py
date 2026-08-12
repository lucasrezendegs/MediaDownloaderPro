import os
import time
import random
import threading
import queue
import yt_dlp
from ffmpeg_checker import find_ffmpeg

class DownloadItem:
    """Representa um item individual na fila de downloads."""
    def __init__(self, item_id: str, url: str, title: str = "Aguardando informações..."):
        self.item_id = item_id
        self.url = url
        self.title = title
        self.progress = 0.0  # 0.0 a 100.0
        self.speed = "0.0 MB/s"
        self.eta = "--:--"
        self.status = "Aguardando"  # Aguardando, Baixando, Convertendo para MP4, Concluído, Erro
        self.error_message = ""
        self.file_path = ""

class YtDlpManager:
    """
    Gerenciador avançado de downloads com suporte a threads concorrentes,
    processamento em lote, tratamento de cookies, conversão para MP4 e tratamento do FFmpeg.
    """
    BROWSER_MAP = {
        "Chrome": ("chrome",),
        "Firefox": ("firefox",),
        "Edge": ("edge",),
        "Brave": ("brave",),
        "Opera": ("opera",),
        "Vivaldi": ("vivaldi",)
    }

    RESOLUTION_MAP = {
        "4K (2160p)": "bestvideo[height<=2160]+bestaudio/best[height<=2160]",
        "1080p": "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
        "720p": "bestvideo[height<=720]+bestaudio/best[height<=720]",
        "480p": "bestvideo[height<=480]+bestaudio/best[height<=480]",
        "360p": "bestvideo[height<=360]+bestaudio/best[height<=360]",
        "Melhor Disponível": "bestvideo+bestaudio/best"
    }

    def __init__(self, config: dict, ui_update_callback=None, log_callback=None):
        self.config = config
        self.ui_update_callback = ui_update_callback
        self.log_callback = log_callback
        
        self.items = {}  # item_id -> DownloadItem
        self.download_queue = queue.Queue()
        self.active_threads = []
        self.is_running = True
        self.semaphore = threading.Semaphore(config.get("max_concurrent", 3))

    def log(self, msg: str):
        if self.log_callback:
            self.log_callback(msg)
        else:
            print(msg)

    def notify_ui(self):
        if self.ui_update_callback:
            self.ui_update_callback()

    def obter_videos_da_playlist(self, url: str) -> list:
        """Extrai os títulos e URLs dos vídeos de uma playlist sem baixá-los."""
        ydl_opts = {
            'extract_flat': True,
            'skip_download': True,
            'quiet': True,
            'nocheckcertificate': True
        }
        try:
            self.log(f"[Análise] Analisando links da URL: {url}")
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if not info:
                    return []
                
                # Se for uma playlist contendo múltiplos vídeos
                if 'entries' in info:
                    videos = []
                    for entry in info['entries']:
                        if entry:
                            title = entry.get('title') or "Vídeo sem título"
                            video_url = entry.get('url') or entry.get('id')
                            if video_url and not video_url.startswith('http'):
                                video_url = f"https://youtube.com{video_url}"
                            videos.append({"title": title, "url": video_url})
                    return videos
                
                # Se for apenas um vídeo individual
                return [{"title": info.get('title', 'Vídeo Individual'), "url": url}]
        except Exception as e:
            self.log(f"[Erro] Falha ao ler metadados: {str(e)}")
            return []

    def add_to_queue(self, url: str, custom_title: str = None) -> str:
        """Adiciona uma URL para download e retorna seu ID único."""
        item_id = f"dl_{int(time.time() * 1000)}_{random.randint(100, 999)}"
        title = custom_title if custom_title else "Aguardando informações..."
        item = DownloadItem(item_id=item_id, url=url, title=title)
        self.items[item_id] = item
        self.download_queue.put(item)
        self.notify_ui()
        self.log(f"[Fila] Item adicionado: {title[:30]}")
        
        t = threading.Thread(target=self._worker_loop, args=(item_id,), daemon=True)
        t.start()
        return item_id

    def _worker_loop(self, item_id: str):
        item = self.items.get(item_id)
        if not item:
            return

        with self.semaphore:
            self._download_single_item(item)

    def _download_single_item(self, item: DownloadItem):
        item.status = "Baixando"
        self.notify_ui()

        ffmpeg_bin = find_ffmpeg()
        ffmpeg_dir = os.path.dirname(ffmpeg_bin) if ffmpeg_bin else None

        download_dir = self.config.get("download_path", os.path.join(os.path.expanduser("~"), "Downloads"))
        os.makedirs(download_dir, exist_ok=True)
        out_template = os.path.join(download_dir, "%(title)s.%(ext)s")

        media_mode = self.config.get("media_mode", "Vídeo + Áudio")
        video_quality = self.config.get("video_quality", "Melhor Disponível")

        ydl_opts = {
            'outtmpl': out_template,
            'windowsfilenames': True,
            'nocheckcertificate': True,
            'ignoreerrors': False,
            'logtostderr': False,
            'quiet': True,
            'no_warnings': True,
            'sleep_interval': 2,
            'max_sleep_interval': 5,
            'noplaylist': True,  # Força o yt-dlp a processar estritamente o vídeo individual do link
        }

        if ffmpeg_dir:
            ydl_opts['ffmpeg_location'] = ffmpeg_dir

        cookie_file = self.config.get("cookie_file", "").strip()
        cookie_browser = self.config.get("cookie_browser", "Nenhum")

        if cookie_file and os.path.exists(cookie_file):
            ydl_opts['cookiefile'] = cookie_file
            self.log(f"[Cookies] Usando arquivo: {cookie_file}")
        elif cookie_browser in self.BROWSER_MAP:
            browser_tuple = self.BROWSER_MAP[cookie_browser]
            ydl_opts['cookiesfrombrowser'] = browser_tuple
            self.log(f"[Cookies] Lendo do navegador: {cookie_browser}")

        if media_mode == "Apenas Áudio":
            ydl_opts['format'] = 'bestaudio/best'
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '320',
            }]
        else:
            ydl_opts['format'] = self.RESOLUTION_MAP.get(video_quality, "bestvideo+bestaudio/best")
            ydl_opts['merge_output_format'] = 'mp4'
            ydl_opts['postprocessors'] = [
                {
                    'key': 'FFmpegVideoConvertor',
                    'preferedformat': 'mp4',
                }
            ]

        def progress_hook(d):
            if d['status'] == 'downloading':
                if d.get('info_dict', {}).get('title'):
                    item.title = d['info_dict']['title']

                total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
                downloaded_bytes = d.get('downloaded_bytes') or 0
                if total_bytes > 0:
                    item.progress = min(100.0, (downloaded_bytes / total_bytes) * 100.0)

                speed = d.get('speed')
                if speed:
                    item.speed = f"{speed / (1024 * 1024):.2f} MB/s"
                else:
                    item.speed = "0.0 MB/s"

                eta = d.get('eta')
                if eta is not None:
                    mins, secs = divmod(int(eta), 60)
                    item.eta = f"{mins:02d}:{secs:02d}"
                else:
                    item.eta = "--:--"

                item.status = "Baixando"
                self.notify_ui()

            elif d['status'] == 'postprocessing' or d['status'] == 'finished':
                item.status = "Convertendo para MP4" if media_mode != "Apenas Áudio" else "Extraindo Áudio"
                item.progress = 99.0
                self.notify_ui()

        ydl_opts['progress_hooks'] = [progress_hook]

        try:
            self.log(f"[Download] Iniciando {item.title[:30]}")
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(item.url, download=True)
                if info:
                    item.title = info.get('title', item.title)
            
            item.status = "Concluído"
            item.progress = 100.0
            item.speed = "0.0 MB/s"
            item.eta = "00:00"
            self.log(f"[Concluído] {item.title}")

        except Exception as e:
            err_msg = str(e)
            item.status = "Erro"
            item.error_message = err_msg
            self.log(f"[Erro] Falha no item {item.title[:20]}: {err_msg}")

        self.notify_ui()
