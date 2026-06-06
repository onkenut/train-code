import ctypes
import ctypes.wintypes
import sys
import platform

user32 = None
IS_WINDOWS = platform.system() == 'Windows'

if IS_WINDOWS:
    try:
        user32 = ctypes.windll.user32
    except Exception:
        user32 = None

INPUT_MOUSE = 0
INPUT_KEYBOARD = 1

MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_WHEEL = 0x0800
MOUSEEVENTF_ABSOLUTE = 0x8000

KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_SCANCODE = 0x0008

VK_LBUTTON = 0x01
VK_RBUTTON = 0x02
VK_CANCEL = 0x03
VK_MBUTTON = 0x04
VK_XBUTTON1 = 0x05
VK_XBUTTON2 = 0x06
VK_BACK = 0x08
VK_TAB = 0x09
VK_CLEAR = 0x0C
VK_RETURN = 0x0D
VK_SHIFT = 0x10
VK_CONTROL = 0x11
VK_MENU = 0x12
VK_PAUSE = 0x13
VK_CAPITAL = 0x14
VK_KANA = 0x15
VK_HANGEUL = 0x15
VK_HANGUL = 0x15
VK_JUNJA = 0x17
VK_FINAL = 0x18
VK_HANJA = 0x19
VK_KANJI = 0x19
VK_ESCAPE = 0x1B
VK_CONVERT = 0x1C
VK_NONCONVERT = 0x1D
VK_ACCEPT = 0x1E
VK_MODECHANGE = 0x1F
VK_SPACE = 0x20
VK_PRIOR = 0x21
VK_NEXT = 0x22
VK_END = 0x23
VK_HOME = 0x24
VK_LEFT = 0x25
VK_UP = 0x26
VK_RIGHT = 0x27
VK_DOWN = 0x28
VK_SELECT = 0x29
VK_PRINT = 0x2A
VK_EXECUTE = 0x2B
VK_SNAPSHOT = 0x2C
VK_INSERT = 0x2D
VK_DELETE = 0x2E
VK_HELP = 0x2F
VK_LWIN = 0x5B
VK_RWIN = 0x5C
VK_APPS = 0x5D
VK_SLEEP = 0x5F
VK_NUMPAD0 = 0x60
VK_NUMPAD1 = 0x61
VK_NUMPAD2 = 0x62
VK_NUMPAD3 = 0x63
VK_NUMPAD4 = 0x64
VK_NUMPAD5 = 0x65
VK_NUMPAD6 = 0x66
VK_NUMPAD7 = 0x67
VK_NUMPAD8 = 0x68
VK_NUMPAD9 = 0x69
VK_MULTIPLY = 0x6A
VK_ADD = 0x6B
VK_SEPARATOR = 0x6C
VK_SUBTRACT = 0x6D
VK_DECIMAL = 0x6E
VK_DIVIDE = 0x6F
VK_F1 = 0x70
VK_F2 = 0x71
VK_F3 = 0x72
VK_F4 = 0x73
VK_F5 = 0x74
VK_F6 = 0x75
VK_F7 = 0x76
VK_F8 = 0x77
VK_F9 = 0x78
VK_F10 = 0x79
VK_F11 = 0x7A
VK_F12 = 0x7B
VK_NUMLOCK = 0x90
VK_SCROLL = 0x91
VK_LSHIFT = 0xA0
VK_RSHIFT = 0xA1
VK_LCONTROL = 0xA2
VK_RCONTROL = 0xA3
VK_LMENU = 0xA4
VK_RMENU = 0xA5
VK_BROWSER_BACK = 0xA6
VK_BROWSER_FORWARD = 0xA7
VK_BROWSER_REFRESH = 0xA8
VK_BROWSER_STOP = 0xA9
VK_BROWSER_SEARCH = 0xAA
VK_BROWSER_FAVORITES = 0xAB
VK_BROWSER_HOME = 0xAC
VK_VOLUME_MUTE = 0xAD
VK_VOLUME_DOWN = 0xAE
VK_VOLUME_UP = 0xAF
VK_MEDIA_NEXT_TRACK = 0xB0
VK_MEDIA_PREV_TRACK = 0xB1
VK_MEDIA_STOP = 0xB2
VK_MEDIA_PLAY_PAUSE = 0xB3
VK_LAUNCH_MAIL = 0xB4
VK_LAUNCH_MEDIA_SELECT = 0xB5
VK_LAUNCH_APP1 = 0xB6
VK_LAUNCH_APP2 = 0xB7
VK_OEM_1 = 0xBA
VK_OEM_PLUS = 0xBB
VK_OEM_COMMA = 0xBC
VK_OEM_MINUS = 0xBD
VK_OEM_PERIOD = 0xBE
VK_OEM_2 = 0xBF
VK_OEM_3 = 0xC0
VK_OEM_4 = 0xDB
VK_OEM_5 = 0xDC
VK_OEM_6 = 0xDD
VK_OEM_7 = 0xDE
VK_OEM_8 = 0xDF
VK_OEM_102 = 0xE2
VK_PROCESSKEY = 0xE5
VK_PACKET = 0xE7
VK_ATTN = 0xF6
VK_CRSEL = 0xF7
VK_EXSEL = 0xF8
VK_EREOF = 0xF9
VK_PLAY = 0xFA
VK_ZOOM = 0xFB
VK_NONAME = 0xFC
VK_PA1 = 0xFD
VK_OEM_CLEAR = 0xFE

VIRTUAL_KEY_MAP = {
    'ctrl': VK_LCONTROL,
    'control': VK_LCONTROL,
    'lcontrol': VK_LCONTROL,
    'rcontrol': VK_RCONTROL,
    'shift': VK_LSHIFT,
    'lshift': VK_LSHIFT,
    'rshift': VK_RSHIFT,
    'alt': VK_LMENU,
    'lalt': VK_LMENU,
    'ralt': VK_RMENU,
    'win': VK_LWIN,
    'lwin': VK_LWIN,
    'rwin': VK_RWIN,
    'esc': VK_ESCAPE,
    'escape': VK_ESCAPE,
    'tab': VK_TAB,
    'enter': VK_RETURN,
    'return': VK_RETURN,
    'space': VK_SPACE,
    'backspace': VK_BACK,
    'delete': VK_DELETE,
    'del': VK_DELETE,
    'insert': VK_INSERT,
    'ins': VK_INSERT,
    'home': VK_HOME,
    'end': VK_END,
    'pageup': VK_PRIOR,
    'pagedown': VK_NEXT,
    'up': VK_UP,
    'down': VK_DOWN,
    'left': VK_LEFT,
    'right': VK_RIGHT,
    'f1': VK_F1,
    'f2': VK_F2,
    'f3': VK_F3,
    'f4': VK_F4,
    'f5': VK_F5,
    'f6': VK_F6,
    'f7': VK_F7,
    'f8': VK_F8,
    'f9': VK_F9,
    'f10': VK_F10,
    'f11': VK_F11,
    'f12': VK_F12,
    'printscreen': VK_SNAPSHOT,
    'capslock': VK_CAPITAL,
    'numlock': VK_NUMLOCK,
    'scrolllock': VK_SCROLL,
    'pause': VK_PAUSE,
}

SCREEN_WIDTH = 1920
SCREEN_HEIGHT = 1080

if user32:
    try:
        SCREEN_WIDTH = user32.GetSystemMetrics(0)
        SCREEN_HEIGHT = user32.GetSystemMetrics(1)
    except Exception:
        pass


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ('dx', ctypes.wintypes.LONG),
        ('dy', ctypes.wintypes.LONG),
        ('mouseData', ctypes.wintypes.DWORD),
        ('dwFlags', ctypes.wintypes.DWORD),
        ('time', ctypes.wintypes.DWORD),
        ('dwExtraInfo', ctypes.POINTER(ctypes.wintypes.ULONG)),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ('wVk', ctypes.wintypes.WORD),
        ('wScan', ctypes.wintypes.WORD),
        ('dwFlags', ctypes.wintypes.DWORD),
        ('time', ctypes.wintypes.DWORD),
        ('dwExtraInfo', ctypes.POINTER(ctypes.wintypes.ULONG)),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ('uMsg', ctypes.wintypes.DWORD),
        ('wParamL', ctypes.wintypes.WORD),
        ('wParamH', ctypes.wintypes.WORD),
    ]


class INPUT_UNION(ctypes.Union):
    _fields_ = [
        ('mi', MOUSEINPUT),
        ('ki', KEYBDINPUT),
        ('hi', HARDWAREINPUT),
    ]


class INPUT(ctypes.Structure):
    _fields_ = [
        ('type', ctypes.wintypes.DWORD),
        ('union', INPUT_UNION),
    ]


def _send_input(*inputs):
    if not user32:
        return 0
    nInputs = len(inputs)
    LPINPUT = INPUT * nInputs
    pInputs = LPINPUT(*inputs)
    cbSize = ctypes.c_int(ctypes.sizeof(INPUT))
    return user32.SendInput(nInputs, pInputs, cbSize)


def _mouse_input(dx, dy, mouseData, dwFlags):
    return INPUT(
        type=INPUT_MOUSE,
        union=INPUT_UNION(
            mi=MOUSEINPUT(
                dx=dx,
                dy=dy,
                mouseData=mouseData,
                dwFlags=dwFlags,
                time=0,
                dwExtraInfo=None,
            )
        ),
    )


def _keyboard_input(wVk, wScan, dwFlags):
    return INPUT(
        type=INPUT_KEYBOARD,
        union=INPUT_UNION(
            ki=KEYBDINPUT(
                wVk=wVk,
                wScan=wScan,
                dwFlags=dwFlags,
                time=0,
                dwExtraInfo=None,
            )
        ),
    )


def mouse_move_absolute(x, y):
    dx = int(x * 65535 / SCREEN_WIDTH)
    dy = int(y * 65535 / SCREEN_HEIGHT)
    _send_input(_mouse_input(dx, dy, 0, MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE))


def mouse_move_relative(dx, dy):
    _send_input(_mouse_input(int(dx), int(dy), 0, MOUSEEVENTF_MOVE))


def mouse_left_down():
    _send_input(_mouse_input(0, 0, 0, MOUSEEVENTF_LEFTDOWN))


def mouse_left_up():
    _send_input(_mouse_input(0, 0, 0, MOUSEEVENTF_LEFTUP))


def mouse_left_click():
    mouse_left_down()
    mouse_left_up()


def mouse_right_down():
    _send_input(_mouse_input(0, 0, 0, MOUSEEVENTF_RIGHTDOWN))


def mouse_right_up():
    _send_input(_mouse_input(0, 0, 0, MOUSEEVENTF_RIGHTUP))


def mouse_right_click():
    mouse_right_down()
    mouse_right_up()


def mouse_middle_down():
    _send_input(_mouse_input(0, 0, 0, MOUSEEVENTF_MIDDLEDOWN))


def mouse_middle_up():
    _send_input(_mouse_input(0, 0, 0, MOUSEEVENTF_MIDDLEUP))


def mouse_middle_click():
    mouse_middle_down()
    mouse_middle_up()


def mouse_wheel(delta_x, delta_y):
    if delta_y != 0:
        _send_input(_mouse_input(0, 0, int(delta_y), MOUSEEVENTF_WHEEL))
    if delta_x != 0:
        _send_input(_mouse_input(0, 0, int(delta_x), 0x1000))


def key_down(vk):
    if not user32:
        return
    if isinstance(vk, str):
        vk_lower = vk.lower()
        if vk_lower in VIRTUAL_KEY_MAP:
            vk = VIRTUAL_KEY_MAP[vk_lower]
        elif len(vk) == 1:
            vk = ord(vk.upper())
        else:
            return
    scan = user32.MapVirtualKeyW(vk, 0)
    _send_input(_keyboard_input(vk, scan, KEYEVENTF_SCANCODE))


def key_up(vk):
    if not user32:
        return
    if isinstance(vk, str):
        vk_lower = vk.lower()
        if vk_lower in VIRTUAL_KEY_MAP:
            vk = VIRTUAL_KEY_MAP[vk_lower]
        elif len(vk) == 1:
            vk = ord(vk.upper())
        else:
            return
    scan = user32.MapVirtualKeyW(vk, 0)
    _send_input(_keyboard_input(vk, scan, KEYEVENTF_SCANCODE | KEYEVENTF_KEYUP))


def key_press(vk):
    key_down(vk)
    key_up(vk)


def key_combination(*keys):
    for key in keys:
        key_down(key)
    for key in reversed(keys):
        key_up(key)
