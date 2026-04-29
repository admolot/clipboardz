import time
import threading
import keyboard
import pyperclip
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
                # If the clipboard changed and is not empty, add to queue
                if current_clipboard != self.last_seen and current_clipboard:
                    self.queue.append(current_clipboard)
                    print(f"[+] Added to queue: {repr(current_clipboard[:30])}...")
                self.last_seen = current_clipboard
            except Exception:
                pass
            time.sleep(0.1) # Check every 100ms

    def paste_oldest(self):
        """Triggered when Ctrl+V is pressed."""
        if self.queue:
            # Get the oldest copied item and remove it from memory
            item = self.queue.popleft()
            
            # Update last_seen so our monitor doesn't re-queue it
            self.last_seen = item
            
            # Put the item on the actual Windows clipboard
            pyperclip.copy(item)
            
            # Wait a tiny bit for the Windows clipboard to register the change
            time.sleep(0.05)
            
            # Simulate a Paste using Shift+Insert (avoids triggering Ctrl+V again)
            keyboard.send('shift+insert')
            print(f"[-] Pasted & Forgot: {repr(item[:30])}... | Items left: {len(self.queue)}")
        else:
            # If memory is empty, just paste whatever is currently in the clipboard normally
            keyboard.send('shift+insert')
            print("[!] Memory empty. Pasted current default clipboard.")

    def start(self):
        print("=== FIFO Clipboard Manager Started ===")
        print("1. Copy items normally using Ctrl+C")
        print("2. Press Ctrl+V to paste the oldest item and forget it")
        print("3. Press 'ESC' to close the program\n")
        
        # Suppress the default Ctrl+V action and attach our custom function
        keyboard.add_hotkey('ctrl+v', self.paste_oldest, suppress=True)
        
        # Start the background monitoring thread
        monitor_thread = threading.Thread(target=self.monitor_clipboard, daemon=True)
        monitor_thread.start()
        
        # Keep the program running until the user presses Escape
        keyboard.wait('esc')
        self.is_running = False
        print("Exiting...")

if __name__ == "__main__":
    manager = FIFOClipboard()
    manager.start()
