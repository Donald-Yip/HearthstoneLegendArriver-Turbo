# -*- coding: utf-8 -*-
"""脚本实际用到的「屏幕截图区域 / 状态判定点」清单，以及区域框预览图生成。

Web 控制台「🎯 校准 / 截图区域框」卡片里的 [显示截图区域框] 按钮
→ GET /api/regions → build_region_preview()：截一张当前屏幕，把脚本所有
截图区域画成彩色框、状态判定点画成十字准星，直接把图返回给浏览器显示。

用户据此一眼确认三件事：
    1. 分辨率 / 缩放对不对——框的整体位置和整屏大小是否和 1920×1080 吻合；
    2. 盒子 UI 有没有摆正——盒子的「打法参考A」面板是否正好落在绿框
       （推荐区域 recommendation_roi）里；
    3. 换牌「确认」按钮、AI胜率浮动条这些区域有没有对偏。

整个过程只截屏，不点击、不移动鼠标，自动化运行中也能安全使用。
区域坐标全部来自 config.py（用户可在 ui_config.json 覆盖），
本模块不重复定义，避免「预览画的和实际截的不是同一个框」。
"""
from __future__ import annotations

import base64
import io
import time
from datetime import datetime
from typing import Callable, Optional

from selfcheck import STATUS_FAIL, STATUS_OK, STATUS_WARN

# 盒子浮动条「AI胜率 X%」的截图区域，必须与 FSM_action._AI_WIN_RATE_REGIONS
# 一致（test_screen_regions.py 会导入 FSM_action 校验，防止两边改岔）。
AI_WIN_RATE_REGION = (110, 8, 270, 48)
AI_WIN_RATE_WIDE_REGION = (95, 0, 300, 60)

# get_screen.get_state() 直接读这几个像素来判断当前阶段（屏幕坐标 x, y）。
# 它们不是区域而是单点，所以画成十字准星：位置偏了状态识别就会错。
STATE_PROBE_POINTS = (
    {"key": "probe_main", "label": "主界面/选英雄/匹配判定点",
     "point": (1090, 1070)},
    {"key": "probe_main_alt", "label": "主界面判定点（备用）",
     "point": (705, 305)},
    {"key": "probe_mulligan", "label": "选牌界面判定点",
     "point": (860, 960)},
)

_FONT_CANDIDATES = (r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\msyh.ttf",
                    r"C:\Windows\Fonts\simhei.ttf", r"C:\Windows\Fonts\simsun.ttc")


def _default_config():
    try:
        from config import RecommendationConfig
        return RecommendationConfig()
    except Exception:
        return None


def _box(value, fallback):
    """把配置里的 ROI 规整成 (left, top, right, bottom)，非法就用兜底值。"""
    try:
        vals = tuple(int(v) for v in value)
        if len(vals) == 4 and vals[0] < vals[2] and vals[1] < vals[3]:
            return vals
    except Exception:
        pass
    return tuple(int(v) for v in fallback)


def screenshot_regions(config=None) -> list[dict]:
    """脚本所有截图区域（区域框预览与文档共同的唯一来源）。"""
    cfg = config if config is not None else _default_config()
    return [
        {"key": "recommendation", "color": "#63c76f",
         "label": "盒子推荐面板（OCR 识别来源）",
         "box": _box(getattr(cfg, "recommendation_roi", None), (7, 200, 202, 500)),
         "note": "对战中把盒子的「打法参考A」面板拖进这个绿框，脚本就靠它读出牌建议"},
        {"key": "mulligan_confirm", "color": "#5fa8e6",
         "label": "换牌「确认」按钮（提交校验）",
         "box": _box(getattr(cfg, "mulligan_confirm_roi", None), (860, 810, 1060, 890)),
         "note": "换牌阶段用来确认按钮是否已经消失（还在=没提交成功，要重试）"},
        {"key": "win_rate", "color": "#e2a84e",
         "label": "盒子「AI胜率」浮动条",
         "box": AI_WIN_RATE_REGION,
         "note": "开了自动投降才用得到：靠它读左上角 AI胜率"},
        {"key": "win_rate_wide", "color": "#e2705f",
         "label": "AI胜率兜底区域",
         "box": AI_WIN_RATE_WIDE_REGION,
         # 兜底区域完全包住主区域，所以画细一点、标签放框下面，避免和上面重叠。
         "width": 1, "label_below": True,
         "note": "主区域读不到时放宽再读一次，偏一点也能兜住"},
    ]


def state_probe_points() -> list[dict]:
    """阶段判定的像素点（复制一份，调用方改动不影响模块常量）。"""
    return [{"key": p["key"], "label": p["label"], "point": tuple(p["point"])}
            for p in STATE_PROBE_POINTS]


# ---------------------------------------------------------------- 截屏 / 度量
def _default_grabber():
    """整屏截图（主显示器），返回 PIL.Image（RGB）。"""
    from PIL import ImageGrab
    return ImageGrab.grab(all_screens=False)


def _default_screen_metrics() -> tuple[int, int, int]:
    width = height = dpi = 0
    try:
        import ctypes
        user32 = ctypes.windll.user32
        width, height = int(user32.GetSystemMetrics(0)), int(user32.GetSystemMetrics(1))
        dpi = int(user32.GetDpiForSystem())
    except Exception:
        pass
    return width, height, dpi


def _default_panel_detector(crop) -> bool:
    """复用 DesktopCapture 的面板可见性判定（暗红顶栏 + 像素方差）。"""
    import numpy as np
    from src.capture.desktop_capture import DesktopCapture
    pixels = np.ascontiguousarray(np.asarray(crop.convert("RGB"))[:, :, ::-1])
    return bool(DesktopCapture._panel_is_visible(pixels))


def _font(size: int):
    from PIL import ImageFont
    for path in _FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return None


def label_font(size: int):
    """公开的字体加载入口（区域框预览图与屏幕叠加层共用）。"""
    return _font(size)


def panel_visible(crop) -> bool:
    """公开入口：判断一块截图里有没有盒子面板（暗红标题栏 + 像素方差）。"""
    return _default_panel_detector(crop)


def _check(key: str, label: str, status: str, detail: str,
           hint: str = "", required: bool = True) -> dict:
    return {"key": key, "label": label, "status": status, "detail": detail,
            "hint": hint, "required": bool(required)}


def _expected(config) -> tuple[int, int, int]:
    if config is None:
        return (1920, 1080, 96)
    size = getattr(config, "desktop_size", (1920, 1080))
    try:
        width, height = int(size[0]), int(size[1])
    except Exception:
        width, height = 1920, 1080
    try:
        dpi = int(getattr(config, "desktop_dpi", 96))
    except Exception:
        dpi = 96
    return width, height, dpi


# ---------------------------------------------------------------- 预览图
def draw_region_boxes(image, config=None, scale: float = 1.0) -> list[dict]:
    """在 PIL 图像上画出所有截图区域框 + 标签，并回填 in_bounds。

    网页里的区域框预览图与屏幕上叠加的「校准」框共用这一份绘制逻辑，
    保证两处画出来的框完全一致。scale 是图像相对屏幕的缩放倍数。
    """
    from PIL import ImageColor, ImageDraw

    draw = ImageDraw.Draw(image)
    try:
        draw.fontmode = "1"  # 关掉抗锯齿，小字更清楚
    except Exception:
        pass
    font = _font(16)
    small = _font(13)
    width, height = image.size
    regions = screenshot_regions(config)
    for region in regions:
        left, top, right, bottom = region["box"]
        in_bounds = (0 <= left < right <= width and 0 <= top < bottom <= height)
        region["in_bounds"] = in_bounds
        if not in_bounds:
            continue
        color = ImageColor.getrgb(region["color"])
        x0, y0 = int(left * scale), int(top * scale)
        x1, y1 = int(right * scale), int(bottom * scale)
        draw.rectangle((x0, y0, x1, y1), outline=color,
                       width=int(region.get("width", 3)))
        label = (f"{region['label']} {left},{top},{right},{bottom}"
                 if font is not None else
                 f"{region['key']} {left},{top},{right},{bottom}")
        text_draw = small if small is not None else font
        try:
            text_box = draw.textbbox((0, 0), label, font=text_draw)
            text_width = text_box[2] - text_box[0]
            text_height = text_box[3] - text_box[1]
        except Exception:
            text_width, text_height = len(label) * 7, 14
        label_x = min(max(0, x0), max(0, width - text_width - 8))
        if region.get("label_below"):
            label_y = min(y1 + 4, max(0, height - text_height - 4))
        else:
            label_y = y0 - text_height - 8
            if label_y < 0:
                label_y = min(y0 + 4, max(0, height - text_height - 4))
        draw.rectangle((label_x - 3, label_y - 2,
                        label_x + text_width + 3, label_y + text_height + 3),
                       fill=(0, 0, 0))
        draw.text((label_x, label_y), label, fill=color, font=text_draw)
    return regions


def draw_state_probe_points(image, scale: float = 1.0) -> list[dict]:
    """把阶段判定点画成黄色十字准星（同样是预览图与屏幕叠加层共用）。"""
    from PIL import ImageColor, ImageDraw

    draw = ImageDraw.Draw(image)
    width, height = image.size
    color = ImageColor.getrgb("#f7d97e")
    probes = state_probe_points()
    for probe in probes:
        px, py = probe["point"]
        in_bounds = 0 <= px < width and 0 <= py < height
        probe["in_bounds"] = in_bounds
        if not in_bounds:
            continue
        cx, cy = int(px * scale), int(py * scale)
        draw.line((cx - 9, cy, cx + 9, cy), fill=color, width=2)
        draw.line((cx, cy - 9, cx, cy + 9), fill=color, width=2)
        draw.ellipse((cx - 3, cy - 3, cx + 3, cy + 3), outline=color, width=2)
    return probes


def build_region_preview(config=None, grabber: Optional[Callable] = None,
                         screen_metrics: Optional[Callable] = None,
                         panel_detector: Optional[Callable] = None,
                         jpeg_quality: int = 82,
                         max_width: int = 1920) -> dict:
    """截一张整屏、画上所有截图区域框，返回可直接给前端 <img> 用的结果。

    返回的 checks 与「环境自检」用同一套 ok/warn/fail 结构，前端一套渲染逻辑。
    """
    from PIL import Image, ImageColor, ImageDraw

    grabber = grabber or _default_grabber
    screen_metrics = screen_metrics or _default_screen_metrics
    panel_detector = panel_detector or _default_panel_detector

    image = grabber()
    if image is None:
        raise RuntimeError("截屏失败：请确认脚本以管理员身份运行")
    image = image.convert("RGB")
    actual_width, actual_height = image.size

    expected_width, expected_height, expected_dpi = _expected(config)
    screen_width, screen_height, dpi = 0, 0, 0
    try:
        screen_width, screen_height, dpi = screen_metrics()
    except Exception:
        pass

    # 4K 屏的整屏 JPEG 太大，超宽时等比缩小后再画（框坐标同步缩放）。
    scale = min(1.0, float(max_width) / float(actual_width or 1))
    if scale < 1.0:
        image = image.resize((max(1, int(actual_width * scale)),
                              max(1, int(actual_height * scale))),
                             Image.LANCZOS)

    draw = ImageDraw.Draw(image)
    try:
        draw.fontmode = "1"  # 关掉抗锯齿，小字更清楚
    except Exception:
        pass
    checks: list[dict] = []

    # --- 分辨率 / 缩放
    if (actual_width, actual_height) == (expected_width, expected_height):
        checks.append(_check("resolution", "屏幕分辨率", STATUS_OK,
                             f"{actual_width}×{actual_height}"))
    else:
        checks.append(_check(
            "resolution", "屏幕分辨率", STATUS_FAIL,
            f"{actual_width}×{actual_height}（要求 {expected_width}×{expected_height}）",
            "脚本的点击坐标按 1920×1080 硬编码：请把 Windows 分辨率设为 "
            f"{expected_width}×{expected_height}，炉石用全屏模式（别用最大化窗口）。"))
    if dpi:
        if dpi == expected_dpi:
            checks.append(_check("dpi", "显示缩放（DPI）", STATUS_OK,
                                 f"{dpi}（{round(dpi / 96 * 100)}%）"))
        else:
            checks.append(_check(
                "dpi", "显示缩放（DPI）", STATUS_FAIL,
                f"{dpi}（{round(dpi / 96 * 100)}%，要求 100%）",
                "显示设置 → 缩放改成 100%：不是 100% 时截图和点击会整体偏移。"))

    # --- 逐个区域：是否在屏幕内 + 画框
    regions = draw_region_boxes(image, config, scale=scale)
    out_of_bounds = [r for r in regions if not r.get("in_bounds")]
    for region in out_of_bounds:
        left, top, right, bottom = region["box"]
        # 区域跑到屏幕外 = 截图会被裁掉、点击也点不到，属于致命问题。
        checks.append(_check(
            f"bounds-{region['key']}", f"区域范围：{region['label']}", STATUS_FAIL,
            f"[{left},{top},{right},{bottom}] 超出屏幕 {actual_width}×{actual_height}",
            "这个区域会被裁掉/点不到：请校正分辨率与缩放，或重新校准区域。"))

    # --- 状态判定点
    probes = draw_state_probe_points(image, scale=scale)

    # --- 绿框里到底有没有盒子面板（决定要不要「移动盒子 UI」）
    recommendation = next((r for r in regions if r["key"] == "recommendation"), None)
    if recommendation is not None and recommendation.get("in_bounds"):
        left, top, right, bottom = recommendation["box"]
        try:
            crop = image.crop((int(left * scale), int(top * scale),
                               int(right * scale), int(bottom * scale)))
            visible = bool(panel_detector(crop))
        except Exception as exc:
            visible = False
            checks.append(_check("panel", "绿框内盒子面板", STATUS_WARN,
                                 f"无法判定：{type(exc).__name__}: {exc}", "",
                                 required=False))
        else:
            if visible:
                checks.append(_check("panel", "绿框内盒子面板", STATUS_OK,
                                     "检测到盒子面板（暗红标题栏）"))
            else:
                checks.append(_check(
                    "panel", "绿框内盒子面板", STATUS_WARN,
                    "绿框里没有检测到盒子面板",
                    "对战中把盒子的「打法参考A」面板拖进绿框再看一次；"
                    "不在对局时看不到面板是正常的。", required=False))

    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=int(jpeg_quality), optimize=True)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")

    failed = [c for c in checks if c["status"] == STATUS_FAIL and c["required"]]
    return {
        "ok": not failed,
        "image": f"data:image/jpeg;base64,{encoded}",
        "width": actual_width,
        "height": actual_height,
        "scaled": scale < 1.0,
        "dpi": dpi,
        "screen": {"width": screen_width or actual_width,
                   "height": screen_height or actual_height, "dpi": dpi},
        "expected": {"width": expected_width, "height": expected_height,
                     "dpi": expected_dpi},
        "regions": regions,
        "points": probes,
        "checks": checks,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "generated_ts": time.time(),
    }


def main() -> int:
    """命令行直接跑：python screen_regions.py [输出文件]（默认 preview.jpg）。"""
    import sys
    from pathlib import Path
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("region_preview.jpg")
    result = build_region_preview()
    data = result["image"].split(",", 1)[1]
    out.write_bytes(base64.b64decode(data))
    print(f"区域框预览已保存：{out}（{result['width']}×{result['height']}）")
    for item in result["checks"]:
        print(f"  [{item['status']}] {item['label']}：{item['detail']}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
