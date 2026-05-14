# watcher.py - run this on Windows, outside Docker
import time, requests, os
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

WATCH_FOLDER = r"C:\n8n\incoming_docs"
WEBHOOK_URL = "http://localhost:5678/webhook-test/document-intake"

class NewFileHandler(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory:
            return
        filepath = event.src_path
        filename = os.path.basename(filepath)
        print(f"New file detected: {filename}")
        time.sleep(1)

        with open(filepath, "rb") as f:
            # Send as raw binary with filename in header
            requests.post(
                WEBHOOK_URL,
                data=f.read(),
                headers={
                    "Content-Type": "application/octet-stream",
                    "X-Filename": filename        # filename in custom header
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