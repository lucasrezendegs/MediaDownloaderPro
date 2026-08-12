import os
import sys
import tkinter as tk
import threading
from tkinter import filedialog, messagebox
import customtkinter as ctk

from config_manager import load_config, save_config
from ffmpeg_checker import is_ffmpeg_available, find_ffmpeg
from updater import update_ytdlp
from downloader import YtDlpManager

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class PlaylistSelectionWindow(ctk.CTkToplevel):
    """Janela Pop-up para exibir e selecionar itens da playlist antes de baixar."""
    def __init__(self, master, videos, on_confirm_callback):
        super().__init__(master)
        self.title("Selecionar Vídeos para Download")
        self.geometry("650x450")
        self.transient(master)
        self.grab_set()

        self.videos = videos
        self.on_confirm_callback = on_confirm_callback
        self.checkbox_vars = []

        lbl = ctk.CTkLabel(self, text="Vídeos Identificados na URL", font=("Helvetica", 14, "bold"))
        lbl.pack(pady=10)

        frame_botoes_selecao = ctk.CTkFrame(self, fg_color="transparent")
        frame_botoes_selecao.pack(fill="x", padx=20, pady=2)
        
        ctk.CTkButton(frame_botoes_selecao, text="Marcar Todos", width=120, command=self.marcar_todos, fg_color="#475569").pack(side="left", padx=5)
        ctk.CTkButton(frame_botoes_selecao, text="Desmarcar Todos", width=120, command=self.desmarcar_todos, fg_color="#475569").pack(side="left", padx=5)

        self.scroll_frame = ctk.CTkScrollableFrame(self, fg_color="#1E293B", corner_radius=8)
        self.scroll_frame.pack(fill="both", expand=True, padx=20, pady=10)

        for video in self.videos:
            var = ctk.BooleanVar(value=True)
            self.checkbox_vars.append((var, video))
            cb = ctk.CTkCheckBox(self.scroll_frame, text=video["title"], variable=var, font=("Helvetica", 12))
            cb.pack(anchor="w", padx=10, pady=6, fill="x")

        bottom_frame = ctk.CTkFrame(self, fg_color="transparent")
        bottom_frame.pack(fill="x", side="bottom", pady=15, padx=20)

        ctk.CTkButton(bottom_frame, text="Cancelar", command=self.destroy, fg_color="#EF4444", hover_color="#DC2626", width=120).pack(side="left")
        ctk.CTkButton(bottom_frame, text="Adicionar à Fila", command=self.confirmar_selecao, fg_color="#22C55E", hover_color="#16A34A", width=150).pack(side="right")

    def marcar_todos(self):
        for var, _ in self.checkbox_vars:
            var.set(True)

    def desmarcar_todos(self):
        for var, _ in self.checkbox_vars:
            var.set(False)

    def confirmar_selecao(self):
        selecionados = [video for var, video in self.checkbox_vars if var.get()]
        if not selecionados:
            messagebox.showwarning("Aviso", "Por favor, selecione ao menos um item da lista.")
            return
        self.on_confirm_callback(selecionados)
        self.destroy()


class DownloadCard(ctk.CTkFrame):
    """Card visual para cada item da fila de download."""
    def __init__(self, master, item, **kwargs):
        super().__init__(master, fg_color="#1E293B", corner_radius=10, **kwargs)
        self.item = item
        self.grid_columnconfigure(1, weight=1)

        self.status_icon = ctk.CTkLabel(self, text="📥", font=("Arial", 20))
        self.status_icon.grid(row=0, column=0, rowspan=2, padx=12, pady=10)

        self.title_label = ctk.CTkLabel(
            self, text=self.item.title, font=("Helvetica", 13, "bold"),
            anchor="w", text_color="#F8FAFC"
        )
        self.title_label.grid(row=0, column=1, sticky="ew", padx=(0, 10), pady=(8, 2))

        self.details_label = ctk.CTkLabel(
            self, text="Aguardando na fila...", font=("Helvetica", 11),
            anchor="w", text_color="#94A3B8"
        )
        self.details_label.grid(row=1, column=1, sticky="ew", padx=(0, 10), pady=(0, 5))

        self.progress_bar = ctk.CTkProgressBar(self, height=8, progress_color="#3B82F6")
        self.progress_bar.set(0.0)
        self.progress_bar.grid(row=2, column=0, columnspan=2, sticky="ew", padx=12, pady=(0, 10))

    def update_data(self):
        self.title_label.configure(text=self.item.title)
        pct = self.item.progress
        self.progress_bar.set(pct / 100.0)

        status_text = f"Status: {self.item.status} | {pct:.1f}% | {self.item.speed} | ETA: {self.item.eta}"
        if self.item.status == "Erro" and self.item.error_message:
            status_text = f"Erro: {self.item.error_message[:60]}..."

        self.details_label.configure(text=status_text)

        if self.item.status == "Concluído":
            self.progress_bar.configure(progress_color="#22C55E")
            self.status_icon.configure(text="✅")
        elif self.item.status == "Erro":
            self.progress_bar.configure(progress_color="#EF4444")
            self.status_icon.configure(text="❌")
        elif self.item.status in ["Convertendo para MP4", "Extraindo Áudio"]:
            self.progress_bar.configure(progress_color="#EAB308")
            self.status_icon.configure(text="⚙️")
        elif self.item.status == "Baixando":
            self.progress_bar.configure(progress_color="#3B82F6")
            self.status_icon.configure(text="⬇️")


class MediaDownloaderApp(ctk.CTk):
    """Janela principal da aplicação CustomTkinter."""
    def __init__(self):
        super().__init__()

        self.title("Gerenciador de Downloads de Mídia Pro")
        self.geometry("920x680")
        self.minsize(800, 600)

        self.config = load_config()
        self.card_widgets = {}
        
        # Primeiro monta a UI
        self.setup_ui()
        
        # Inicializa o gerenciador com referências limpas
        self.downloader = YtDlpManager(
            config=self.config,
            ui_update_callback=lambda: self.on_downloader_update(),
            log_callback=lambda msg: self.log(msg)
        )
        
        self.after(500, self.initial_checks)

    def setup_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        # --- Cabeçalho ---
        header_frame = ctk.CTkFrame(self, fg_color="#0F172A", corner_radius=0, height=60)
        header_frame.grid(row=0, column=0, sticky="ew")
        header_frame.grid_columnconfigure(0, weight=1)

        header_title = ctk.CTkLabel(
            header_frame, text="⚡ Media Downloader Pro",
            font=("Helvetica", 18, "bold"), text_color="#F8FAFC"
        )
        header_title.grid(row=0, column=0, padx=20, pady=15, sticky="w")

        theme_btn = ctk.CTkButton(
            header_frame, text="Mudar Tema", width=100,
            command=self.toggle_theme, fg_color="#334155", hover_color="#475569"
        )
        theme_btn.grid(row=0, column=1, padx=20, pady=15, sticky="e")

        # --- Entrada de Link ---
        input_frame = ctk.CTkFrame(self, fg_color="#1E293B", corner_radius=10)
        input_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=12)
        input_frame.grid_columnconfigure(0, weight=1)

        self.url_entry = ctk.CTkEntry(
            input_frame, placeholder_text="Cole o link do YouTube (Vídeo ou Playlist), TikTok, Instagram...",
            height=40, font=("Helvetica", 13)
        )
        self.url_entry.grid(row=0, column=0, padx=(15, 10), pady=12, sticky="ew")

        paste_btn = ctk.CTkButton(
            input_frame, text="📋 Colar", width=80, height=40,
            command=self.paste_clipboard, fg_color="#475569", hover_color="#64748B"
        )
        paste_btn.grid(row=0, column=1, padx=(0, 10), pady=12)

        self.add_btn = ctk.CTkButton(
            input_frame, text="🔍 Analisar Link", width=150, height=40,
            font=("Helvetica", 13, "bold"), command=self.start_link_analysis,
            fg_color="#2563EB", hover_color="#1D4ED8"
        )
        self.add_btn.grid(row=0, column=2, padx=(0, 15), pady=12)

        # --- Painel de Opções ---
        opts_frame = ctk.CTkFrame(self, fg_color="#1E293B", corner_radius=10)
        opts_frame.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 12))
        opts_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)

        ctk.CTkLabel(opts_frame, text="Modo:", font=("Helvetica", 11, "bold")).grid(row=0, column=0, padx=10, pady=(8, 0), sticky="w")
        self.mode_var = ctk.StringVar(value=self.config.get("media_mode", "Vídeo + Áudio"))
        self.mode_dropdown = ctk.CTkOptionMenu(
            opts_frame, values=["Vídeo + Áudio", "Apenas Áudio"],
            variable=self.mode_var, command=self.on_mode_change
        )
        self.mode_dropdown.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="ew")

        ctk.CTkLabel(opts_frame, text="Qualidade de Vídeo:", font=("Helvetica", 11, "bold")).grid(row=0, column=1, padx=10, pady=(8, 0), sticky="w")
        self.quality_var = ctk.StringVar(value=self.config.get("video_quality", "Melhor Disponível"))
        self.quality_dropdown = ctk.CTkOptionMenu(
            opts_frame, values=["Melhor Disponível", "4K (2160p)", "1080p", "720p", "480p", "360p"],
            variable=self.quality_var, command=self.save_current_config
        )
        self.quality_dropdown.grid(row=1, column=1, padx=10, pady=(0, 10), sticky="ew")

        ctk.CTkLabel(opts_frame, text="Cookies de Navegador:", font=("Helvetica", 11, "bold")).grid(row=0, column=2, padx=10, pady=(8, 0), sticky="w")
        self.cookie_var = ctk.StringVar(value=self.config.get("cookie_browser", "Nenhum"))
        self.cookie_dropdown = ctk.CTkOptionMenu(
            opts_frame, values=["Nenhum", "Chrome", "Firefox", "Edge", "Brave", "Opera", "Vivaldi"],
            variable=self.cookie_var, command=self.save_current_config
        )
        self.cookie_dropdown.grid(row=1, column=2, padx=10, pady=(0, 10), sticky="ew")

        ctk.CTkLabel(opts_frame, text="Pasta de Salvamento:", font=("Helvetica", 11, "bold")).grid(row=0, column=3, padx=10, pady=(8, 0), sticky="w")
        folder_btn = ctk.CTkButton(
            opts_frame, text="📁 Escolher Pasta", command=self.choose_folder,
            fg_color="#334155", hover_color="#475569"
        )
        folder_btn.grid(row=1, column=3, padx=10, pady=(0, 10), sticky="ew")

        # --- Área de Processamento / Fila ---
        self.queue_frame = ctk.CTkScrollableFrame(self, fg_color="#0F172A", corner_radius=10)
        self.queue_frame.grid(row=3, column=0, sticky="nsew", padx=20, pady=(0, 15))

    def paste_clipboard(self):
        try:
            text = self.clipboard_get()
            self.url_entry.delete(0, tk.END)
            self.url_entry.insert(0, text)
        except Exception:
            pass

    def start_link_analysis(self):
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showwarning("Aviso", "Por favor, cole um link válido para analisar.")
            return

        self.add_btn.configure(state="disabled", text="🔍 Analisando...")
        
        def rodar():
            videos = self.downloader.obter_videos_da_playlist(url)
            self.after(0, lambda: self.finish_link_analysis(videos))

        threading.Thread(target=rodar, daemon=True).start()

    def finish_link_analysis(self, videos):
        self.add_btn.configure(state="normal", text="🔍 Analisando Link")
        if not videos:
            messagebox.showerror("Erro de Leitura", "Não foi possível extrair metadados dessa URL.")
            return

        PlaylistSelectionWindow(self, videos, self.enqueue_selected_videos)

    def enqueue_selected_videos(self, selecionados):
        for video in selecionados:
            self.downloader.add_to_queue(video["url"], custom_title=video["title"])
        self.url_entry.delete(0, tk.END)

    def choose_folder(self):
        folder = filedialog.askdirectory(initialdir=self.config.get("download_path"))
        if folder:
            self.config["download_path"] = folder
            save_config(self.config)

    def on_mode_change(self, val):
        if val == "Apenas Áudio":
            self.quality_dropdown.configure(state="disabled")
        else:
            self.quality_dropdown.configure(state="normal")
        self.save_current_config()

    def save_current_config(self, *args):
        self.config["media_mode"] = self.mode_var.get()
        self.config["video_quality"] = self.quality_var.get()
        self.config["cookie_browser"] = self.cookie_var.get()
        save_config(self.config)

    def toggle_theme(self):
        current = ctk.get_appearance_mode()
        novo = "Light" if current == "Dark" else "Dark"
        ctk.set_appearance_mode(novo)

    def initial_checks(self):
        if not is_ffmpeg_available():
            messagebox.showwarning("FFmpeg Não Encontrado", "O mecanismo FFmpeg não foi encontrado localmente.")
        
        def run_update():
            update_ytdlp()
        threading.Thread(target=run_update, daemon=True).start()

    def log(self, msg):
        print(msg)

    def on_downloader_update(self):
        self.after(0, self.sync_ui_cards)

    def sync_ui_cards(self):
        for item_id, item in list(self.downloader.items.items()):
            if item_id not in self.card_widgets:
                card = DownloadCard(self.queue_frame, item)
                card.pack(fill="x", padx=10, pady=6)
                self.card_widgets[item_id] = card
            
            self.card_widgets[item_id].update_data()
