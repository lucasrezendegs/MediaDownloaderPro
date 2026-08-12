import multiprocessing
import sys

if __name__ == '__main__':
    # Trava absoluta contra loops no topo do arquivo raiz
    multiprocessing.freeze_support()
    
    # Importa e inicia a interface apenas dentro do bloco seguro
    from gui import MediaDownloaderApp
    print("Iniciando Media Downloader Pro GUI com proteção ativa...")
    app = MediaDownloaderApp()
    app.mainloop()
