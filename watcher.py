# Watcher to monitor incoming_docs folder and send webhook on new file creation
import time, requests, os
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

WATCH_FOLDER = r".\incoming_docs"
WEBHOOK_URL = "http://localhost:5678/webhook-test/document-intake"

class NewFileHandler(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory:
            return
        filepath = event.src_path
        filename = os.path.basename(filepath)
        print(f"New file detected: {filename}")
        time.sleep(1)

        requests.post(
            WEBHOOK_URL,
            headers={
                "Content-Type": "application/octet-stream",
                "X-Filename": filename
            }
        )
        print(f"Sent: {filename}")

observer = Observer()
observer.schedule(NewFileHandler(), WATCH_FOLDER, recursive=False)
observer.start()
print(f"Watching {WATCH_FOLDER} ...")
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    observer.stop()
observer.join()