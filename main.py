import time
import threading
import ctypes
import keyboard
import pyperclip
import pystray
from PIL import Image, ImageDraw
from collections import deque

class FIFOClipboard:
    def __init__(self):
        self.queue = deque()
        # Get the deep Windows OS clipboard sequence ID
        self.last_seq = ctypes.windll.user32.GetClipboardSequenceNumber()
        self.is_running = True
        self.is_pasting = False
        self.icon = None

    def monitor_clipboard(self):
        """Monitors Windows OS directly for copy events."""
        while self.is_running:
            try:
                current_seq = ctypes.windll.user32.GetClipboardSequenceNumber()
                
                # If Windows registers a new copy action, and we aren't currently pasting
                if current_seq != self.last_seq and not self.is_pasting:
                    self.last_seq = current_seq
                    current_clipboard = pyperclip.paste()
                    
                    # Ensure it's text, and prevent duplicates if you spam Ctrl+C
                    if current_clipboard and (not self.queue or self.queue[-1] != current_clipboard):
                        self.queue.append(current_clipboard)
                        self.update_tray()
            except Exception:
                pass
            time.sleep(0.05) # Super fast 50ms polling

    def paste_oldest(self):
        """Triggered on Ctrl+V."""
        keyboard.release('ctrl') # Let go of Ctrl virtually so Shift+Insert works cleanly
        if self.queue:
            self.is_pasting = True
            item = self.queue.popleft()
            
            pyperclip.copy(item)
            time.sleep(0.05) 
            keyboard.send('shift+insert')
            time.sleep(0.05) 
            
            # Update our sequence ID so we don't accidentally "copy" our own paste
            self.last_seq = ctypes.windll.user32.GetClipboardSequenceNumber()
            self.is_pasting = False
            self.update_tray()
        else:
            keyboard.send('shift+insert')

    def update_tray(self):
        """Updates the text you see when hovering over the tray icon."""
        if self.icon:
            self.icon.title = f"FIFO Clipboard: {len(self.queue)} items"

    def start(self):
        keyboard.add_hotkey('ctrl+v', self.paste_oldest, suppress=True)
        self.monitor_thread = threading.Thread(target=self.monitor_clipboard, daemon=True)
        self.monitor_thread.start()

    def stop(self):
        self.is_running = False
        keyboard.unhook_all()


def create_tray_icon_image():
    """Draws a simple icon for the system tray."""
    image = Image.new('RGB', (64, 64), color=(0, 120, 215))
    draw = ImageDraw.Draw(image)
    draw.rectangle([16, 16, 48, 48], outline="white", width=4)
    return image

def main():
    manager = FIFOClipboard()
    manager.start()

    def on_quit(icon, item):
        manager.stop()
        icon.stop()

    def create_menu():
        """Dynamically creates the menu list every time you click the tray icon."""
        items =[]
        items.append(pystray.MenuItem(f"Items stored: {len(manager.queue)}", lambda: None, enabled=False))
        items.append(pystray.MenuItem("--------", lambda: None, enabled=False))
        
        # Show up to 15 items in the list
        for i, text in enumerate(list(manager.queue)[:15]):
            # Clean up the text so it looks nice in the menu
            preview = text.replace('\n', ' ').replace('\r', '')
            if len(preview) > 40:
                preview = preview[:37] + "..."
            items.append(pystray.MenuItem(f"{i+1}. {preview}", lambda: None, enabled=False))
            
        if len(manager.queue) > 15:
            items.append(pystray.MenuItem(f"... and {len(manager.queue) - 15} more", lambda: None, enabled=False))
            
        items.append(pystray.MenuItem("--------", lambda: None, enabled=False))
        items.append(pystray.MenuItem("Quit", on_quit))
        return items

    manager.icon = pystray.Icon(
        "FIFO_Clipboard",
        create_tray_icon_image(),
        "FIFO Clipboard: 0 items",
        menu=pystray.Menu(create_menu)
    )
    
    manager.icon.run()

if __name__ == "__main__":
    main()
