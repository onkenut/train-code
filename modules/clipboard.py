import win32clipboard
import win32con
import time
from . import input_control

CF_UNICODETEXT = 13

def get_clipboard_text():
    try:
        win32clipboard.OpenClipboard()
        try:
            if win32clipboard.IsClipboardFormatAvailable(CF_UNICODETEXT):
                data = win32clipboard.GetClipboardData(CF_UNICODETEXT)
                return data
            return None
        finally:
            win32clipboard.CloseClipboard()
    except Exception:
        return None

def set_clipboard_text(text):
    try:
        win32clipboard.OpenClipboard()
        try:
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(CF_UNICODETEXT, text)
        finally:
            win32clipboard.CloseClipboard()
        return True
    except Exception:
        return False

def paste_text(text):
    original_text = get_clipboard_text()
    try:
        if not set_clipboard_text(text):
            return False
        time.sleep(0.01)
        input_control.key_combination('ctrl', 'V')
        time.sleep(0.05)
        return True
    finally:
        if original_text is not None:
            time.sleep(0.05)
            set_clipboard_text(original_text)
        else:
            time.sleep(0.05)
            try:
                win32clipboard.OpenClipboard()
                try:
                    win32clipboard.EmptyClipboard()
                finally:
                    win32clipboard.CloseClipboard()
            except Exception:
                pass
