import time
import threading
import keyboard
import pyperclip
import pystray
from PIL import Image, ImageDraw
from collections import deque

class FIFOClipboard:
    def __init__(self):
        self.queue = deque()
        self.last_seen = pyperclip.paste()
        self.is_running = True
        
    def monitor_clipboard(self):
        """Runs in the background and watches for newly copied text."""
        while self.is_running:
            try:
                current_clipboard = pyperclip.paste()
                if current_clipboard != self.last_seen and current_clipboard:
                    self.queue.append(current_clipboard)
                self.last_seen = current_clipboard
            except Exception:
                pass
            time.sleep(0.1) 

    def paste_oldest(self):
        """Triggered when Ctrl+V is pressed."""
        # Release the Ctrl key virtually so our 'shift+insert' doesn't become 'ctrl+shift+insert'
        keyboard.release('ctrl')
        
        if self.queue:
            item = self.queue.popleft()
            self.last_seen = item
            pyperclip.copy(item)
            time.sleep(0.05)
            keyboard.send('shift+insert')
        else:
            # Paste normally if memory is empty
            keyboard.send('shift+insert')

    def start(self):
        keyboard.add_hotkey('ctrl+v', self.paste_oldest, suppress=True)
        self.monitor_thread = threading.Thread(target=self.monitor_clipboard, daemon=True)
        self.monitor_thread.start()

    def stop(self):
        self.is_running = False
        keyboard.unhook_all()

def create_tray_icon_image():
    """Generates a simple blue icon with a white square inside for the System Tray."""
    image = Image.new('RGB', (64, 64), color=(0, 120, 215)) # Windows Blue
    draw = ImageDraw.Draw(image)
    draw.rectangle([16, 16, 48, 48], outline="white", width=4)
    return image

def main():
    # 1. Start the clipboard manager logic
    manager = FIFOClipboard()
    manager.start()

    # 2. Define what happens when "Quit" is clicked in the tray
    def on_quit(icon, item):
        manager.stop()
        icon.stop()

    # 3. Create the System Tray icon
    tray_icon = pystray.Icon(
        "FIFO_Clipboard",
        create_tray_icon_image(),
        "FIFO Clipboard Manager",
        menu=pystray.Menu(pystray.MenuItem("Quit", on_quit))
    )
    
    # 4. Run the tray icon (This keeps the program running in the background)
    tray_icon.run()

if __name__ == "__main__":
    main()
