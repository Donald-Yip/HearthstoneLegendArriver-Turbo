# -*- coding: utf-8 -*-
"""屏幕上叠加显示「截图区域框」——浮窗「校准」按钮触发。

用途：对战中一眼确认盒子 UI 有没有摆正，并提示「请对齐相应UI」。
屏幕上直接画出脚本实际使用的截图区域（颜色与网页预览一致）：
    🟩 绿框 = 盒子推荐面板（OCR 识别来源，把「打法参考A」面板移进来）
    🟦 蓝框 = 换牌「确认」按钮
    🟧 橙框 = 盒子「AI胜率」浮动条   🟥 红细框 = AI胜率兜底区域
    ✛  黄十字 = 阶段判定点

设计要点：
  * 置顶 + **鼠标穿透**（WS_EX_TRANSPARENT）：框只是用来看的，点击照常落到炉石上；
  * 不抢焦点（WS_EX_NOACTIVATE）、不出现在任务栏（WS_EX_TOOLWINDOW）；
  * 顶部提示条每 1.5s 重新判断一次「绿框里有没有盒子面板」，对齐成功会变 ✅；
  * Esc 或再点一次浮窗「校准」关闭；窗口随进程退出自动消失。

窗口用与 calibrate_roi.py 相同的分层窗口（UpdateLayeredWindow）实现，
不依赖 Tk，也不与浮窗抢焦点。绘制逻辑复用 screen_regions 的区域登记表，
保证屏幕上画的框和网页预览/程序实际截图的是同一批区域。
"""
from __future__ import annotations

import ctypes
import threading
import time
from ctypes import wintypes
from typing import Callable, Optional

from screen_regions import (
    draw_region_boxes, draw_state_probe_points, label_font, panel_visible,
    screenshot_regions,
)

# ---------------------------------------------------------------- Win32
USER32 = ctypes.windll.user32
GDI32 = ctypes.windll.gdi32
KERNEL32 = ctypes.windll.kernel32

WS_POPUP = 0x80000000
WS_VISIBLE = 0x10000000
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020      # 鼠标穿透：点击落到下面的炉石上
WS_EX_TOPMOST = 0x00000008
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000
ULW_ALPHA = 0x00000002
PM_REMOVE = 0x0001
VK_ESCAPE = 0x1B
CLASS_NAME = "HSLegendArriverRegionBox"

# 面板判定刷新间隔（秒）：对齐过程中随时能看到“绿框里有没有盒子面板”。
PANEL_REFRESH_SECONDS = 1.5


class MSG(ctypes.Structure):
    _fields_ = [("hwnd", wintypes.HWND), ("message", wintypes.UINT),
                ("wParam", wintypes.WPARAM), ("lParam", wintypes.LPARAM),
                ("time", wintypes.DWORD), ("pt_x", wintypes.LONG),
                ("pt_y", wintypes.LONG)]


class WNDCLASSW(ctypes.Structure):
    _fields_ = [("style", wintypes.UINT), ("lpfnWndProc", ctypes.c_void_p),
                ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int),
                ("hInstance", wintypes.HINSTANCE), ("hIcon", wintypes.HICON),
                ("hCursor", wintypes.HANDLE), ("hbrBackground", wintypes.HANDLE),
                ("lpszMenuName", wintypes.LPCWSTR),
                ("lpszClassName", wintypes.LPCWSTR)]


class BLENDFUNCTION(ctypes.Structure):
    _fields_ = [("BlendOp", ctypes.c_ubyte), ("BlendFlags", ctypes.c_ubyte),
                ("SourceConstantAlpha", ctypes.c_ubyte),
                ("AlphaFormat", ctypes.c_ubyte)]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG),
                ("biHeight", wintypes.LONG), ("biPlanes", wintypes.WORD),
                ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
                ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD),
                ("biClrImportant", wintypes.DWORD)]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wintypes.DWORD * 3)]


WNDPROC = ctypes.WINFUNCTYPE(
    ctypes.c_ssize_t, wintypes.HWND, wintypes.UINT,
    wintypes.WPARAM, wintypes.LPARAM)


def _passive_wndproc(hwnd, msg, wparam, lparam):
    return USER32.DefWindowProcW(hwnd, msg, wparam, lparam)


_WNDPROC_IMPL = WNDPROC(_passive_wndproc)  # 全局引用防止被回收

USER32.RegisterClassW.argtypes = [ctypes.c_void_p]
USER32.RegisterClassW.restype = ctypes.c_ushort
USER32.CreateWindowExW.argtypes = [wintypes.DWORD, wintypes.LPCWSTR,
                                   wintypes.LPCWSTR, wintypes.DWORD,
                                   ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                   ctypes.c_int, wintypes.HWND,
                                   wintypes.HMENU, wintypes.HINSTANCE,
                                   wintypes.LPVOID]
USER32.CreateWindowExW.restype = wintypes.HWND
USER32.PeekMessageW.argtypes = [ctypes.c_void_p, wintypes.HWND,
                                wintypes.UINT, wintypes.UINT, wintypes.UINT]
USER32.PeekMessageW.restype = wintypes.BOOL
USER32.TranslateMessage.argtypes = [ctypes.c_void_p]
USER32.DispatchMessageW.argtypes = [ctypes.c_void_p]
USER32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT,
                                  wintypes.WPARAM, wintypes.LPARAM]
USER32.DefWindowProcW.restype = ctypes.c_ssize_t
USER32.GetSystemMetrics.argtypes = [ctypes.c_int]
USER32.GetSystemMetrics.restype = ctypes.c_int
USER32.GetAsyncKeyState.argtypes = [ctypes.c_int]
USER32.GetAsyncKeyState.restype = ctypes.c_short
USER32.GetDC.argtypes = [wintypes.HWND]
USER32.GetDC.restype = wintypes.HDC
USER32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
USER32.DestroyWindow.argtypes = [wintypes.HWND]
GDI32.CreateCompatibleDC.argtypes = [wintypes.HDC]
GDI32.CreateCompatibleDC.restype = wintypes.HDC
GDI32.CreateDIBSection.argtypes = [wintypes.HDC, ctypes.c_void_p,
                                   wintypes.UINT, ctypes.c_void_p,
                                   wintypes.HANDLE, wintypes.DWORD]
GDI32.CreateDIBSection.restype = wintypes.HBITMAP
GDI32.SelectObject.argtypes = [wintypes.HDC, wintypes.HANDLE]
GDI32.DeleteDC.argtypes = [wintypes.HDC]
GDI32.DeleteObject.argtypes = [wintypes.HANDLE]
KERNEL32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
KERNEL32.GetModuleHandleW.restype = wintypes.HINSTANCE
USER32.UpdateLayeredWindow.argtypes = [wintypes.HWND, wintypes.HDC,
                                       ctypes.c_void_p, ctypes.c_void_p,
                                       wintypes.HDC, ctypes.c_void_p,
                                       wintypes.DWORD, ctypes.c_void_p,
                                       wintypes.DWORD]
USER32.UpdateLayeredWindow.restype = wintypes.BOOL

# ---------------------------------------------------------------- 提示条
HINT_TITLE = "请对齐相应UI"
HINT_DETAIL = "把盒子的「打法参考A」面板移进绿框；橙框=AI胜率浮动条、黄十字=阶段判定点"
HINT_CLOSE = "按 Esc 或再点浮窗「校准」关闭"

_CARD_BG = (18, 13, 8, 222)
_CARD_BORDER = (232, 185, 59, 240)
_TITLE_COLOR = (247, 217, 126, 255)
_TEXT_COLOR = (240, 228, 200, 255)
_OK_COLOR = (99, 199, 111, 255)
_WARN_COLOR = (226, 168, 78, 255)


def hint_lines(panel_state: Optional[bool] = None) -> list[dict]:
    """提示条内容：标题「请对齐相应UI」+ 说明 + 盒子面板判定 + 关闭方式。"""
    lines = [
        {"text": HINT_TITLE, "color": _TITLE_COLOR, "size": 22, "bold": True},
        {"text": HINT_DETAIL, "color": _TEXT_COLOR, "size": 13, "bold": False},
    ]
    if panel_state is True:
        # 这些字是 PIL 用微软雅黑画的：没有彩色 emoji 字形，✓/✗ 也不一定在
        # 字体里（会画成方框），所以只用纯文字 + 颜色区分状态。
        lines.append({"text": "已检测到盒子面板",
                      "color": _OK_COLOR, "size": 15, "bold": True})
    elif panel_state is False:
        lines.append({"text": "还没检测到盒子面板：请把「打法参考A」面板移进绿框",
                      "color": _WARN_COLOR, "size": 15, "bold": True})
    lines.append({"text": HINT_CLOSE, "color": _TEXT_COLOR,
                  "size": 12, "bold": False})
    return lines


def paint_layer(width: int, height: int, panel_state: Optional[bool] = None,
                config=None):
    """画出一整屏的叠加层（RGBA，背景全透明）——纯函数，方便离线检查。"""
    from PIL import Image, ImageDraw

    canvas = Image.new("RGBA", (max(1, width), max(1, height)), (0, 0, 0, 0))
    draw_region_boxes(canvas, config)
    draw_state_probe_points(canvas)

    draw = ImageDraw.Draw(canvas)
    lines = hint_lines(panel_state)
    fonts = [label_font(line["size"]) for line in lines]

    pad_x, pad_y, gap = 18, 12, 6
    widths, heights = [], []
    for line, font in zip(lines, fonts):
        try:
            box = draw.textbbox((0, 0), line["text"], font=font)
        except Exception:
            box = (0, 0, len(line["text"]) * line["size"], line["size"] + 4)
        widths.append(box[2] - box[0])
        heights.append(box[3] - box[1])
    card_w = min(width, max(widths) + pad_x * 2)
    card_h = sum(heights) + gap * (len(lines) - 1) + pad_y * 2
    card_x = max(0, (width - card_w) // 2)
    card_y = 24
    draw.rectangle((card_x, card_y, card_x + card_w, card_y + card_h),
                   fill=_CARD_BG, outline=_CARD_BORDER, width=2)
    y = card_y + pad_y
    for line, font, text_w, text_h in zip(lines, fonts, widths, heights):
        x = card_x + (card_w - text_w) // 2
        try:
            draw.text((x, y), line["text"], fill=line["color"], font=font)
        except Exception:
            draw.text((x, y), line["text"], fill=line["color"])
        y += text_h + gap
    return canvas


class RegionBoxOverlay:
    """屏幕上的截图区域框叠加层（单例用法见 default_overlay()）。"""

    def __init__(self,
                 runner: Optional[Callable[[], None]] = None,
                 detector: Optional[Callable] = None,
                 screen_size: Optional[Callable[[], tuple]] = None,
                 config_provider: Optional[Callable[[], object]] = None,
                 refresh_seconds: float = PANEL_REFRESH_SECONDS):
        self._runner = runner or self._run_window
        self._detector = detector or panel_visible
        self._screen_size = screen_size or (
            lambda: (USER32.GetSystemMetrics(0), USER32.GetSystemMetrics(1)))
        self._config_provider = config_provider
        self._refresh_seconds = max(0.3, float(refresh_seconds))
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None
        self._visible = False

    # -------------------------------------------------- 状态
    def is_visible(self) -> bool:
        with self._lock:
            return self._visible

    def show(self) -> bool:
        with self._lock:
            if self._visible:
                return True
            self._visible = True
            self._stop.clear()
            self._thread = threading.Thread(
                target=self._run_safely, name="hs-region-box", daemon=True)
        self._thread.start()
        return True

    def hide(self) -> bool:
        self._stop.set()
        with self._lock:
            self._visible = False
        return False

    def toggle(self) -> bool:
        """切换显示状态，返回切换后是否正在显示。"""
        return self.hide() if self.is_visible() else self.show()

    def _run_safely(self):
        try:
            self._runner()
        except Exception as exc:
            print(f"[校准] 屏幕区域框叠加层异常：{type(exc).__name__}: {exc}")
        finally:
            with self._lock:
                self._visible = False

    # -------------------------------------------------- 面板判定
    def _panel_state(self, config=None) -> Optional[bool]:
        """截一小块推荐区域，看看绿框里现在有没有盒子面板（判断不了返回 None）。"""
        try:
            from PIL import ImageGrab
            regions = screenshot_regions(
                self._config() if config is None else config)
            roi = next(r for r in regions if r["key"] == "recommendation")["box"]
            crop = ImageGrab.grab(bbox=tuple(roi), all_screens=False)
            return bool(self._detector(crop))
        except Exception:
            return None

    def _config(self):
        if self._config_provider is not None:
            try:
                return self._config_provider()
            except Exception:
                return None
        try:
            from config import RecommendationConfig
            return RecommendationConfig()
        except Exception:
            return None

    # -------------------------------------------------- 窗口主循环
    def _run_window(self):
        from PIL import Image

        width, height = self._screen_size()
        if width <= 0 or height <= 0:
            print("[校准] 读不到屏幕尺寸，无法显示区域框")
            return
        hwnd = self._create_window(width, height)
        if not hwnd:
            print("[校准] 创建区域框窗口失败")
            return
        hdc = USER32.GetDC(None)
        mem_dc = GDI32.CreateCompatibleDC(hdc)
        info = BITMAPINFO()
        info.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        info.bmiHeader.biWidth = width
        info.bmiHeader.biHeight = -height            # 顶向下
        info.bmiHeader.biPlanes = 1
        info.bmiHeader.biBitCount = 32
        info.bmiHeader.biCompression = 0
        bits = ctypes.c_void_p()
        dib = GDI32.CreateDIBSection(hdc, ctypes.byref(info), 0,
                                     ctypes.byref(bits), None, 0)
        GDI32.SelectObject(mem_dc, dib)
        USER32.ReleaseDC(None, hdc)

        blend = BLENDFUNCTION(0, 0, 255, 1)
        point_dst = wintypes.POINT(0, 0)
        size = wintypes.SIZE(width, height)
        point_src = wintypes.POINT(0, 0)
        msg = MSG()
        panel_state = None
        next_panel_check = 0.0
        esc_held = False
        # 区域坐标一帧都不该重读配置文件：进来读一次，之后复用。
        config = self._config()
        try:
            while not self._stop.is_set():
                while USER32.PeekMessageW(ctypes.byref(msg), None, 0, 0, PM_REMOVE):
                    USER32.TranslateMessage(ctypes.byref(msg))
                    USER32.DispatchMessageW(ctypes.byref(msg))
                esc = bool(USER32.GetAsyncKeyState(VK_ESCAPE) & 0x8000)
                if esc and not esc_held:
                    break
                esc_held = esc
                now = time.time()
                if now >= next_panel_check:
                    next_panel_check = now + self._refresh_seconds
                    panel_state = self._panel_state(config)
                layer = paint_layer(width, height, panel_state, config)
                # UpdateLayeredWindow 要的是 BGRA 字节序（PIL 的 RGBA 直接
                # 塞进去会把红蓝调换），用 raw BGRA 转一次再提交。
                data = layer.tobytes("raw", "BGRA")
                ctypes.memmove(bits.value, data, len(data))
                USER32.UpdateLayeredWindow(
                    hwnd, None, ctypes.byref(point_dst), ctypes.byref(size),
                    mem_dc, ctypes.byref(point_src), 0, ctypes.byref(blend),
                    ULW_ALPHA)
                time.sleep(0.06)
        finally:
            if hwnd:
                USER32.DestroyWindow(hwnd)
            GDI32.DeleteDC(mem_dc)
            GDI32.DeleteObject(dib)

    @staticmethod
    def _create_window(width: int, height: int):
        inst = KERNEL32.GetModuleHandleW(None)
        wc = WNDCLASSW()
        wc.lpfnWndProc = ctypes.cast(_WNDPROC_IMPL, ctypes.c_void_p).value
        wc.hInstance = inst
        wc.lpszClassName = CLASS_NAME
        USER32.RegisterClassW(ctypes.byref(wc))
        return USER32.CreateWindowExW(
            WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOPMOST
            | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE,
            CLASS_NAME, "HSLegendArriver 截图区域框", WS_POPUP | WS_VISIBLE,
            0, 0, width, height, None, None, inst, None)


_DEFAULT = RegionBoxOverlay()


def default_overlay() -> RegionBoxOverlay:
    return _DEFAULT


def toggle() -> bool:
    """显示/隐藏屏幕上的截图区域框，返回切换后是否正在显示。"""
    return _DEFAULT.toggle()


def hide() -> None:
    _DEFAULT.hide()


def is_visible() -> bool:
    return _DEFAULT.is_visible()


def main() -> int:
    """命令行直接跑（调试/验证用）：

        python region_overlay.py --render out.png   # 只画图，不显示窗口
        python region_overlay.py --selftest [秒]     # 真显示，N 秒后自动关
    """
    import sys

    args = sys.argv[1:]
    if "--render" in args:
        index = args.index("--render")
        out = args[index + 1] if len(args) > index + 1 else "region_overlay.png"
        width, height = _DEFAULT._screen_size()
        preview = paint_layer(width, height, None)
        preview.save(out)
        print(f"已生成叠加层预览：{out}（{width}×{height}）")
        return 0
    seconds = 3.0
    if "--selftest" in args:
        index = args.index("--selftest")
        if len(args) > index + 1:
            try:
                seconds = float(args[index + 1])
            except ValueError:
                pass
    _DEFAULT.show()
    print(f"[校准] 已显示截图区域框，{seconds:.0f}s 后自动关闭"
          f"（{HINT_TITLE}）")
    time.sleep(max(0.1, seconds))
    _DEFAULT.hide()
    time.sleep(0.2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
