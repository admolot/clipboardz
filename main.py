import time
import threading
import ctypes
import keyboard
import win32clipboard
import pystray
from PIL import Image, ImageDraw
from collections import deque

class FIFOClipboard:
    def __init__(self):
        self.queue = deque()
        self.last_seq = ctypes.windll.user32.GetClipboardSequenceNumber()
        self.is_running = True
        self.is_pasting = False
        self.icon = None
        
        # We want to capture Plain text, Web HTML (bold/colors), and Word Rich Text
        self.formats_to_save =[
            win32clipboard.CF_UNICODETEXT,
            win32clipboard.RegisterClipboardFormat("HTML Format"),
            win32clipboard.RegisterClipboardFormat("Rich Text Format")
        ]

    def get_clipboard_data(self):
        """Safely opens clipboard and extracts Plain Text, HTML, and RTF."""
        data = {}
        # Try 5 times in case another app is currently locking the clipboard
        for _ in range(5):
            try:
                win32clipboard.OpenClipboard()
                for fmt in self.formats_to_save:
                    if win32clipboard.IsClipboardFormatAvailable(fmt):
                        try:
                            data[fmt] = win32clipboard.GetClipboardData(fmt)
                        except Exception:
                            pass
                win32clipboard.CloseClipboard()
                return data
            except Exception:
                time.sleep(0.02)
        return data

    def set_clipboard_data(self, data):
        """Safely opens clipboard and restores all formats."""
        for _ in range(5):
            try:
                win32clipboard.OpenClipboard()
                win32clipboard.EmptyClipboard()
                for fmt, content in data.items():
                    try:
                        win32clipboard.SetClipboardData(fmt, content)
                    except Exception:
                        pass
                win32clipboard.CloseClipboard()
                return
            except Exception:
                time.sleep(0.02)

    def monitor_clipboard(self):
        """Monitors Windows OS directly for copy events."""
        while self.is_running:
            try:
                current_seq = ctypes.windll.user32.GetClipboardSequenceNumber()
                
                if current_seq != self.last_seq and not self.is_pasting:
                    self.last_seq = current_seq
                    time.sleep(0.05) # Wait for the copying app to release the clipboard
                    
                    data = self.get_clipboard_data()
                    
                    # Extract the plain text version so we can display it in the tray menu
                    text = data.get(win32clipboard.CF_UNICODETEXT, "")
                    
                    # If it has text, and it's not a spam duplicate of the last item
                    if text and (not self.queue or self.queue[-1]['text'] != text):
                        self.queue.append({'text': text, 'data': data})
                        self.update_tray()
            except Exception:
                pass
            time.sleep(0.05) 

    def paste_oldest(self):
        """Triggered on Ctrl+V."""
        keyboard.release('ctrl') 
        if self.queue:
            self.is_pasting = True
            item = self.queue.popleft()
            
            # Put the Rich Text / HTML back on the clipboard
            self.set_clipboard_data(item['data'])
            
            time.sleep(0.05) 
            keyboard.send('shift+insert')
            time.sleep(0.05) 
            
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
        """Dynamically creates the menu list every time you right click the tray icon."""
        items =[]
        items.append(pystray.MenuItem(f"Items stored: {len(manager.queue)}", lambda: None, enabled=False))
        items.append(pystray.MenuItem("--------", lambda: None, enabled=False))
        
        for i, item in enumerate(list(manager.queue)[:15]):
            text = item['text']
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
