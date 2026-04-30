import sys
import time
import threading
import ctypes
from ctypes import wintypes
import keyboard
import pystray
from PIL import Image, ImageDraw
from collections import deque

# --- Monkey-patch pystray to open menu on Left-Click (Windows) ---
if sys.platform == 'win32':
    import pystray._win32
    original_on_notify = pystray._win32.Icon._on_notify

    def patched_on_notify(self, wparam, lparam):
        # 0x0202 is WM_LBUTTONUP (Left Click), 0x0205 is WM_RBUTTONUP (Right Click)
        if lparam == 0x0202: 
            lparam = 0x0205 
        return original_on_notify(self, wparam, lparam)

    pystray._win32.Icon._on_notify = patched_on_notify
# -----------------------------------------------------------------

# --- Pure Ctypes Clipboard API ---
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002

user32.OpenClipboard.argtypes =[wintypes.HWND]
user32.OpenClipboard.restype = wintypes.BOOL
user32.CloseClipboard.argtypes =[]
user32.CloseClipboard.restype = wintypes.BOOL
user32.EmptyClipboard.argtypes =[]
user32.EmptyClipboard.restype = wintypes.BOOL
user32.GetClipboardData.argtypes = [wintypes.UINT]
user32.GetClipboardData.restype = wintypes.HANDLE
user32.SetClipboardData.argtypes =[wintypes.UINT, wintypes.HANDLE]
user32.SetClipboardData.restype = wintypes.HANDLE
user32.EnumClipboardFormats.argtypes = [wintypes.UINT]
user32.EnumClipboardFormats.restype = wintypes.UINT

kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
kernel32.GlobalAlloc.restype = wintypes.HANDLE
kernel32.GlobalLock.argtypes =[wintypes.HANDLE]
kernel32.GlobalLock.restype = wintypes.LPVOID
kernel32.GlobalUnlock.argtypes = [wintypes.HANDLE]
kernel32.GlobalUnlock.restype = wintypes.BOOL
kernel32.GlobalSize.argtypes = [wintypes.HANDLE]
kernel32.GlobalSize.restype = ctypes.c_size_t
# -----------------------------------------------------------------

class FIFOClipboard:
    def __init__(self):
        self.queue = deque()
        self.last_seq = ctypes.windll.user32.GetClipboardSequenceNumber()
        self.is_running = True
        self.is_pasting = False
        self.icon = None

    def get_clipboard_data(self):
        """Safely opens memory and clones EVERY format on the clipboard."""
        data = {}
        for _ in range(5):
            if user32.OpenClipboard(None):
                try:
                    fmt = 0
                    while True:
                        # Iterate through all available clipboard formats
                        fmt = user32.EnumClipboardFormats(fmt)
                        if fmt == 0:
                            break
                        handle = user32.GetClipboardData(fmt)
                        if handle:
                            ptr = kernel32.GlobalLock(handle)
                            if ptr:
                                size = kernel32.GlobalSize(handle)
                                # Grab exactly what is in memory as raw bytes
                                data[fmt] = ctypes.string_at(ptr, size)
                                kernel32.GlobalUnlock(handle)
                finally:
                    user32.CloseClipboard()
                return data
            time.sleep(0.02)
        return data

    def set_clipboard_data(self, data):
        """Safely opens memory and restores all cloned formats byte-for-byte."""
        for _ in range(5):
            if user32.OpenClipboard(None):
                try:
                    user32.EmptyClipboard()
                    for fmt, buffer in data.items():
                        size = len(buffer)
                        handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, size)
                        if handle:
                            ptr = kernel32.GlobalLock(handle)
                            if ptr:
                                ctypes.memmove(ptr, buffer, size)
                                kernel32.GlobalUnlock(handle)
                                user32.SetClipboardData(fmt, handle)
                finally:
                    user32.CloseClipboard()
                return
            time.sleep(0.02)

    def monitor_clipboard(self):
        """Monitors Windows OS directly for copy events."""
        while self.is_running:
            try:
                current_seq = ctypes.windll.user32.GetClipboardSequenceNumber()
                
                if current_seq != self.last_seq and not self.is_pasting:
                    self.last_seq = current_seq
                    time.sleep(0.05) 
                    
                    data = self.get_clipboard_data()
                    
                    # Convert the raw memory bytes back into a readable Python string for our tray menu
                    raw_text_bytes = data.get(CF_UNICODETEXT, b"")
                    text = raw_text_bytes.decode('utf-16-le', errors='ignore').rstrip('\x00')
                    
                    # Ensure the copied object actually has text, and prevent duplicate spam
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
            
            # Put every single format exactly back on the clipboard
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
        """Dynamically creates the menu list every time you click the tray icon."""
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
