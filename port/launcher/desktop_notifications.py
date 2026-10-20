# SPDX-License-Identifier: GPL-2.0-or-later
"""Optional Windows Shell notifications: no registry changes, focus or extra packages.

Created/pumped/destroyed on the achievement observer's worker thread only.
Windows may suppress notifications; persistence does not depend on delivery.
API: https://learn.microsoft.com/windows/win32/api/shellapi/ns-shellapi-notifyicondataw
"""
import ctypes
from ctypes import wintypes as w
import sys


class GUID(ctypes.Structure):
    _fields_ = [('a', w.DWORD), ('b', w.WORD), ('c', w.WORD), ('d', w.BYTE * 8)]


class NotifyData(ctypes.Structure):
    _fields_ = [('cbSize', w.DWORD), ('hWnd', w.HWND), ('uID', w.UINT), ('uFlags', w.UINT),
                ('uCallbackMessage', w.UINT), ('hIcon', w.HICON), ('szTip', w.WCHAR * 128),
                ('dwState', w.DWORD), ('dwStateMask', w.DWORD), ('szInfo', w.WCHAR * 256),
                ('uTimeout', w.UINT), ('szInfoTitle', w.WCHAR * 64), ('dwInfoFlags', w.DWORD),
                ('guidItem', GUID), ('hBalloonIcon', w.HICON)]


def text_limit(text, units):
    return str(text).replace('\0', '').encode('utf-16-le')[:units * 2].decode('utf-16-le', errors='ignore')


class WindowsNotifications:
    def __init__(self, title='Achievement unlocked', body='Trophy #{id} — The Last Guardian'):
        self.title, self.body = title, body
        self.user = ctypes.WinDLL('user32', use_last_error=True)
        self.shell = ctypes.WinDLL('shell32', use_last_error=True)
        self.kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        self.kernel.GetModuleHandleW.argtypes = [w.LPCWSTR]
        self.kernel.GetModuleHandleW.restype = w.HMODULE
        self.user.CreateWindowExW.argtypes = [w.DWORD, w.LPCWSTR, w.LPCWSTR, w.DWORD,
                                             ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                             w.HWND, w.HMENU, w.HINSTANCE, w.LPVOID]
        self.user.CreateWindowExW.restype = w.HWND
        self.user.DestroyWindow.argtypes = [w.HWND]
        self.user.DestroyWindow.restype = w.BOOL
        self.user.LoadIconW.argtypes = [w.HINSTANCE, ctypes.c_void_p]
        self.user.LoadIconW.restype = w.HICON
        self.user.PeekMessageW.argtypes = [ctypes.POINTER(w.MSG), w.HWND, w.UINT, w.UINT, w.UINT]
        self.user.PeekMessageW.restype = w.BOOL
        self.user.TranslateMessage.argtypes = [ctypes.POINTER(w.MSG)]
        self.user.TranslateMessage.restype = w.BOOL
        self.user.DispatchMessageW.argtypes = [ctypes.POINTER(w.MSG)]
        self.user.DispatchMessageW.restype = ctypes.c_ssize_t
        self.shell.Shell_NotifyIconW.argtypes = [w.DWORD, ctypes.POINTER(NotifyData)]
        self.shell.Shell_NotifyIconW.restype = w.BOOL
        self.window = self.user.CreateWindowExW(0, 'STATIC', 'TLG local achievements', 0,
                                               0, 0, 0, 0, w.HWND(-3), None,
                                               self.kernel.GetModuleHandleW(None), None)
        self.added = False
        if not self.window:
            raise OSError('Cannot create notification message window')
        self.data = NotifyData()
        self.data.cbSize = ctypes.sizeof(NotifyData)
        self.data.hWnd, self.data.uID = self.window, 1
        self.data.uFlags = 0x02 | 0x04  # NIF_ICON | NIF_TIP; no focus/click action
        self.data.hIcon = self.user.LoadIconW(None, 32516)  # shared IDI_INFORMATION
        self.data.szTip = 'The Last Guardian — local achievements'
        if not self.shell.Shell_NotifyIconW(0, ctypes.byref(self.data)):  # NIM_ADD
            self.close()
            raise OSError('Windows notification area is unavailable')
        self.added = True

    def show(self, trophy_id):
        self.data.uFlags = 0x10  # NIF_INFO
        self.data.szInfoTitle = text_limit(self.title, 63)
        self.data.szInfo = text_limit(self.body.format(id=trophy_id), 255)
        self.data.dwInfoFlags = 0x01 | 0x10 | 0x80  # INFO, NOSOUND, RESPECT_QUIET_TIME
        if not self.shell.Shell_NotifyIconW(1, ctypes.byref(self.data)):  # NIM_MODIFY
            raise OSError('Windows did not accept the notification')
        self.pump()

    def pump(self):
        message = w.MSG()
        # Bounded: a busy desktop must not starve the local persistence queue.
        for _ in range(32):
            if not self.user.PeekMessageW(ctypes.byref(message), None, 0, 0, 1):
                break
            self.user.TranslateMessage(ctypes.byref(message))
            self.user.DispatchMessageW(ctypes.byref(message))

    def close(self):
        if self.added:
            self.shell.Shell_NotifyIconW(2, ctypes.byref(self.data))  # NIM_DELETE
            self.added = False
        if self.window:
            self.user.DestroyWindow(self.window)
            self.window = None


def factory(enabled, title='Achievement unlocked', body='Trophy #{id} — The Last Guardian'):
    """Return a lazy constructor, not a notification or window at startup."""
    if not enabled or sys.platform != 'win32':
        return None
    return lambda: WindowsNotifications(title, body)
