# -*- coding: utf-8 -*-
"""中英双语文案（唯一来源）。

**改动约定（重要）**
    * 所有面向用户的文案都写在这里，不要在别处硬编码中文：
        - 网页：``web/index.html`` 用 ``data-i18n="键名"`` 引用（JS 里用 ``t("键名")``）；
        - 浮窗：``log_overlay.py`` 用 ``t("键名")``；
        - 网页接口返回的 ``message`` / ``error``、日志告警：``web_ui`` / ``FSM_action`` 用 ``t()``。
    * **新增或修改文案时，必须同时补 ``zh`` 与 ``en`` 两个版本。**
      ``tests/test_i18n.py`` 会检查：两种语言键完全一致、页面上引用的键存在、
      代码里 ``t("…")`` 用到的键存在——少写一个（或只写中文）测试就会失败。
    * 键名格式：``区域.用途``，例如 ``page.btn.start`` / ``ov.btn.start`` / ``msg.api.started``。
    * 占位符写 ``{name}``，由 :func:`t` 填充；网页端 JS 做同样的替换。
    * 语言保存在 ``ui_config.json`` 的 ``language``："zh"（默认）/"en"。

语言切换会立刻生效：网页重新取一次文案，浮窗下一帧就用新语言渲染。
"""
from __future__ import annotations

from typing import Dict

LANGUAGES = ("zh", "en")
DEFAULT_LANGUAGE = "zh"
LANGUAGE_LABELS = {"zh": "中文", "en": "EN"}

# 内存里的当前语言（进程级；启动时从 ui_config.json 读取）。
_CURRENT = [DEFAULT_LANGUAGE]
_LOADED = [False]


def normalize(lang) -> str:
    """把任意输入规整成受支持的语言代码。"""
    value = str(lang or "").strip().lower()
    return value if value in LANGUAGES else DEFAULT_LANGUAGE


def current_language() -> str:
    """当前语言（首次调用时从 ui_config.json 读取一次）。"""
    if not _LOADED[0]:
        try:
            import config
            _CURRENT[0] = normalize(config.ui_language())
        except Exception:
            _CURRENT[0] = DEFAULT_LANGUAGE
        _LOADED[0] = True
    return _CURRENT[0]


def set_language(lang: str) -> str:
    """切换当前语言（只改内存；写盘由调用方决定）。"""
    _CURRENT[0] = normalize(lang)
    _LOADED[0] = True
    return _CURRENT[0]


def texts(lang=None) -> Dict[str, str]:
    """返回某语言的全部文案（供网页一次性取走）。"""
    code = normalize(lang) if lang is not None else current_language()
    return {key: entry.get(code) or entry.get(DEFAULT_LANGUAGE) or key
            for key, entry in _TEXTS.items()}


def t(key: str, **kwargs) -> str:
    """取一条文案并按需填充占位符；缺失的键原样返回（便于测试发现）。"""
    entry = _TEXTS.get(key)
    if entry is None:
        return key
    text = entry.get(current_language()) or entry.get(DEFAULT_LANGUAGE) or key
    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, IndexError, ValueError):
            pass
    return text


def has_key(key: str) -> bool:
    return key in _TEXTS


# ---------------------------------------------------------------- 文案表
_TEXTS: Dict[str, Dict[str, str]] = {

    # ============================================================ 网页
    "page.subtitle": {"zh": "炉石传说 · 自动对战控制台",
                      "en": "Hearthstone auto-play console"},
    "page.lang": {"zh": "界面语言", "en": "Language"},
    "page.repo.label": {"zh": "📦 本开源项目地址：",
                        "en": "📦 Open-source project:"},
    "page.repo.note": {
        "zh": "（GPL-3.0 · 完全免费开源，仅用于技术研究与代码交流；觉得有用欢迎点个 ⭐）",
        "en": "(GPL-3.0 · free and open source, for technical study and code sharing)"},
    "page.footer": {"zh": "HSLegendArriver · 仅用于技术研究与代码交流 · ",
                    "en": "HSLegendArriver · for technical study and code sharing · "},

    # ---- 状态胶囊 / 阶段
    "page.phase.idle": {"zh": "空闲", "en": "Idle"},
    "page.phase.waiting": {"zh": "等待定时启动", "en": "Waiting for schedule"},
    "page.phase.playing": {"zh": "自动化运行中", "en": "Running"},
    "page.phase.stopping": {"zh": "本局结束后停止", "en": "Stopping after this game"},
    "page.phase.finished": {"zh": "计划已完成", "en": "Schedule finished"},
    "page.starting": {"zh": "启动中…", "en": "Starting…"},
    "page.idle.text": {"zh": "待机", "en": "Idle"},

    # ---- 运行概览
    "page.card.overview": {"zh": "📊 运行概览", "en": "📊 Overview"},
    "page.stat.state": {"zh": "当前状态", "en": "State"},
    "page.stat.games": {"zh": "已完成对局", "en": "Games"},
    "page.stat.wins": {"zh": "胜场", "en": "Wins"},
    "page.stat.concede": {"zh": "自动认输", "en": "Auto-concedes"},
    "page.stat.rate": {"zh": "胜率", "en": "Win rate"},
    "page.elapsed": {"zh": "⏱ 本局已进行 ", "en": "⏱ This game "},
    "page.stop_note": {"zh": "🔶 本局结束后将自动停止",
                       "en": "🔶 Will stop after this game"},

    # ---- 基础配置
    "page.card.basic": {"zh": "👤 基础配置", "en": "👤 Setup"},
    "page.basic.name": {"zh": "用户 ID（战网完整昵称）",
                        "en": "BattleTag (full name, including #number)"},
    "page.basic.name.ph": {"zh": "例如：为所欲为、异灵术#54321",
                           "en": "e.g. Name#54321"},
    "page.basic.name.hint": {
        "zh": "必须与当前战网账号的<b>完整昵称</b>一致（含 <b>#编号</b>）。"
              "换了账号务必同步修改：脚本靠昵称区分敌我，不匹配会整局不出牌。",
        "en": "Must match the current account's <b>full BattleTag</b> (with <b>#number</b>). "
              "Update it after switching accounts, or the bot will never play a card."},
    "page.basic.log": {"zh": "炉石日志目录（Logs 文件夹）",
                       "en": "Hearthstone log folder (Logs)"},
    "page.basic.log.ph": {"zh": "例如：D:\\Hearthstone\\Logs",
                          "en": "e.g. D:\\Hearthstone\\Logs"},
    "page.basic.check": {"zh": "检测", "en": "Check"},
    "page.basic.checking": {"zh": "检测中…", "en": "Checking…"},
    "page.basic.save_hint": {
        "zh": "💡 输入框失焦自动保存，无需改 constants.py；运行中不可修改。",
        "en": "💡 Saved automatically on blur — no need to edit constants.py. "
              "Locked while running."},
    "page.namecheck.waiting": {
        "zh": "账号校验：等待读到对局日志中的玩家名…（配置：{config}）",
        "en": "Account check: waiting for player names in the game log… (configured: {config})"},
    "page.namecheck.ok": {"zh": "账号校验：✅ 日志玩家名与配置一致（{config}）",
                          "en": "Account check: ✅ matches the game log ({config})"},
    "page.namecheck.bad": {
        "zh": "账号校验：❌ 不匹配！日志中玩家为 {names}，当前配置为 {config}"
              " —— 请改成完整战网昵称（含 #编号），否则整局不出牌",
        "en": "Account check: ❌ mismatch! Log players: {names}, configured: {config}"
              " — fix the BattleTag (with #number) or the bot will never play."},

    # ---- 定时任务
    "page.card.schedule": {"zh": "⏰ 定时任务", "en": "⏰ Schedule"},
    "page.schedule.start": {"zh": "开始时间", "en": "Start time"},
    "page.schedule.start.hint": {"zh": "不能早于当前时间",
                                 "en": "Cannot be in the past"},
    "page.schedule.end": {"zh": "结束时间（可选）", "en": "End time (optional)"},
    "page.schedule.end.hint": {
        "zh": "到点后先打完本局对战，再自动停止；留空则一直运行到手动停止",
        "en": "Finishes the current game first, then stops. Leave empty to run until stopped."},
    "page.schedule.save": {"zh": "💾 保存定时任务", "en": "💾 Save schedule"},
    "page.schedule.cancel": {"zh": "取消计划", "en": "Cancel"},
    "page.chip.start": {"zh": "距开始 {time}", "en": "Starts in {time}"},
    "page.chip.end": {"zh": "距结束 {time}", "en": "Ends in {time}"},
    "page.chip.end_reached": {"zh": "计划结束时间已到", "en": "End time reached"},
    "page.chip.plan_running": {"zh": "计划运行中", "en": "Scheduled run"},
    "page.chip.wait_game": {"zh": "等待本局对战打完…",
                            "en": "Waiting for this game to finish…"},

    # ---- 对战控制
    "page.card.control": {"zh": "🕹️ 对战控制", "en": "🕹️ Control"},
    "page.btn.start": {"zh": "⚔️ 开始对战", "en": "⚔️ Start playing"},
    "page.btn.prepare": {"zh": "🪄 开始运行（准备）", "en": "🪄 Prepare"},
    "page.btn.overlay": {"zh": "🪟 日志浮窗（{state}）",
                         "en": "🪟 Log overlay ({state})"},
    "page.on": {"zh": "开", "en": "on"},
    "page.off": {"zh": "关", "en": "off"},
    "page.btn.after_game": {"zh": "本局结束后停止",
                            "en": "Stop after this game"},
    "page.btn.stop_now": {"zh": "立即停止", "en": "Stop now"},
    "page.control.hint": {
        "zh": "🪄 点 <b>「开始运行」</b>只开浮窗、把炉石切到前台，<b>不会自动开打</b>；"
              "就绪后再点一次 <b>「开始对战」</b>（二次确认）才真正开始。<br>"
              "⌨️ Ctrl+Q 随时立即停止。请保持炉石与盒子前台可见。<br>"
              "🖥️ 炉石用 <b>全屏模式</b>（<code>设置 → 选项 → 显示 → 全屏</code>），"
              "<b>不要用「最大化窗口」</b>：最大化时点击坐标会整体偏移，法术指定目标会一直失败重试。",
        "en": "🪄 <b>Prepare</b> only opens the overlay and brings Hearthstone to the front — "
              "it never starts playing. Press <b>Start playing</b> (with confirmation) for that.<br>"
              "⌨️ Ctrl+Q stops immediately. Keep Hearthstone and the deck helper visible.<br>"
              "🖥️ Use Hearthstone <b>fullscreen</b> (<code>Settings → Options → Display → Fullscreen</code>), "
              "not a maximized window: click coordinates shift and targeted spells keep retrying."},
    "page.confirm.start": {
        "zh": "已就绪：确定开始自动对战？（脚本会开始匹配并自动打牌）",
        "en": "Ready. Start auto-play now? (it will queue and play automatically)"},
    "page.confirm.start_schedule": {
        "zh": "当前有定时任务，立即开始对战将取消定时任务。确定继续？",
        "en": "A schedule is set; starting now cancels it. Continue?"},
    "page.confirm.after_game": {
        "zh": "确定在本局对战结束后停止自动化？",
        "en": "Stop the automation after the current game?"},
    "page.confirm.stop_now": {
        "zh": "确定立即停止自动化？（当前对局会被中断）",
        "en": "Stop the automation right now? (the current game will be interrupted)"},

    # ---- 存活检测
    "page.card.liveness": {"zh": "🩺 存活检测（挂机防空转）",
                           "en": "🩺 Liveness check (idle safety)"},
    "page.common.enabled": {"zh": "启用", "en": "Enable"},
    "page.liveness.warn": {"zh": "日志停滞告警（秒）",
                           "en": "Log stall warning (s)"},
    "page.liveness.stop": {"zh": "日志停滞自动停止（秒）",
                           "en": "Log stall auto-stop (s)"},
    "page.liveness.save": {"zh": "💾 保存存活检测",
                           "en": "💾 Save liveness check"},
    "page.liveness.hint": {
        "zh": "挂机最怕“炉石已经没了，脚本还在对着失效画面做 OCR”。开启后每个循环都会确认 "
              "<b>Hearthstone.exe 进程是否还在</b>（闪退/被关）以及"
              "<b>对局中 Power.log 是否还在更新</b>（进程还在但游戏卡死）；"
              "判定退出会立刻<b>醒目告警并自动停止自动化</b>。默认开启，运行中不可修改。",
        "en": "Worst case while idle: Hearthstone is gone but the bot keeps OCR-ing a dead screen. "
              "Each loop now checks whether <b>Hearthstone.exe is still running</b> (crash / closed) and "
              "whether <b>Power.log still updates during a game</b> (frozen client). "
              "On a confirmed exit it <b>alerts prominently and stops the automation</b>. "
              "Enabled by default; locked while running."},
    "page.liveness.status.disabled": {
        "zh": "存活状态：已关闭（不会检测炉石是否还在运行）",
        "en": "Liveness: disabled (Hearthstone is not monitored)"},
    "page.liveness.status.gone": {
        "zh": "存活状态：❌ 炉石已退出（Hearthstone.exe 进程消失）",
        "en": "Liveness: ❌ Hearthstone exited (Hearthstone.exe is gone)"},
    "page.liveness.status.stale": {
        "zh": "存活状态：❌ 炉石疑似无响应（对局中 Power.log 停滞 {age}s）",
        "en": "Liveness: ❌ Hearthstone not responding (Power.log stalled {age}s)"},
    "page.liveness.status.warning": {
        "zh": "存活状态：⚠️ 对局中 Power.log 已停滞 {age}s（超过 {stop}s 将自动停止）",
        "en": "Liveness: ⚠️ Power.log stalled {age}s during a game (auto-stop at {stop}s)"},
    "page.liveness.status.idle": {
        "zh": "存活状态：炉石未运行（点「开始运行」会先拉起战网/炉石）",
        "en": "Liveness: Hearthstone is not running (Prepare will launch it)"},
    "page.liveness.status.ok": {
        "zh": "存活状态：✅ 炉石正在运行{age_text}；判定退出阈值：{warn}s 告警 / {stop}s 自动停止",
        "en": "Liveness: ✅ Hearthstone is running{age_text}; thresholds: {warn}s warning / {stop}s auto-stop"},
    "page.liveness.age": {"zh": "（Power.log {age}s 前更新）",
                          "en": " (Power.log updated {age}s ago)"},
    "page.liveness.status.unknown": {
        "zh": "存活状态：无法判定（进程列表读取失败）",
        "en": "Liveness: unknown (could not read the process list)"},

    # ---- 自动投降
    "page.card.concede": {"zh": "🏳️ 自动投降", "en": "🏳️ Auto-concede"},
    "page.concede.threshold": {"zh": "AI 胜率阈值（%）",
                               "en": "AI win-rate threshold (%)"},
    "page.concede.rounds": {"zh": "连续回合数", "en": "Consecutive turns"},
    "page.concede.save": {"zh": "💾 保存自动投降", "en": "💾 Save auto-concede"},
    "page.concede.hint": {
        "zh": "检测左上角盒子的「AI胜率」：连续 N 回合低于阈值时，自动点右下角齿轮 → 中间红色「认输」。"
              "默认关闭；运行中不可修改。",
        "en": "Reads the helper's “AI win rate” (top-left). When it stays below the threshold for "
              "N turns in a row, it clicks the gear (bottom-right) → red “Concede”. "
              "Off by default; locked while running."},
    "page.concede.status.disabled": {"zh": "检测状态：已关闭",
                                     "en": "Detection: off"},
    "page.concede.status.triggered": {
        "zh": "检测状态：已触发认输（连续 {streak}/{rounds} 回合）",
        "en": "Detection: concede triggered ({streak}/{rounds} turns)"},
    "page.concede.status.no_rate": {
        "zh": "检测状态：该回合未读到 AI胜率（连续 {streak}/{rounds} 回合）{turn_text}",
        "en": "Detection: no win rate read this turn ({streak}/{rounds} turns){turn_text}"},
    "page.concede.status.rate": {
        "zh": "检测状态：AI胜率 {rate}%（阈值 {threshold}%，连续 {streak}/{rounds} 回合）{mark_text}{turn_text}",
        "en": "Detection: win rate {rate}% (threshold {threshold}%, {streak}/{rounds} turns){mark_text}{turn_text}"},
    "page.concede.below": {"zh": " ⚠️ 低于阈值", "en": " ⚠️ below threshold"},
    "page.concede.above": {"zh": " ✅ 未低于阈值", "en": " ✅ above threshold"},
    "page.concede.turn_text": {"zh": " · 最近检测：第 {turn} 回合",
                               "en": " · last checked: turn {turn}"},
    "page.concede.waiting": {"zh": "检测状态：等待自动化运行…",
                             "en": "Detection: waiting for the automation to run…"},

    # ---- 活人感
    "page.card.humanlike": {"zh": "🎭 活人感（可选）",
                            "en": "🎭 Human-like pacing (optional)"},
    "page.hl.min": {"zh": "随机延时下限（秒）", "en": "Random delay min (s)"},
    "page.hl.max": {"zh": "随机延时上限（秒）", "en": "Random delay max (s)"},
    "page.hl.hover_min": {"zh": "每处悬停下限（秒）", "en": "Hover min (s)"},
    "page.hl.hover_max": {"zh": "每处悬停上限（秒）", "en": "Hover max (s)"},
    "page.hl.save": {"zh": "💾 保存活人感", "en": "💾 Save human-like pacing"},
    "page.hl.hint": {
        "zh": "开启后：每次出牌结束不再用固定的「操作后延时」，改为 <b>0.5~3 秒随机延时</b>；"
              "延时期间鼠标在手牌区随机悬停（每处 <b>0.2~1 秒随机</b>），只移动、绝不点击，"
              "最后仍复位到左上角。默认关闭；下一局开始时生效。",
        "en": "When on, each executed action is followed by a <b>random 0.5–3 s delay</b> instead of the "
              "fixed post-action delay; during it the cursor hovers over random hand cards "
              "(<b>0.2–1 s each</b>), only moving, never clicking, then returns to the reset point. "
              "Off by default; applies from the next game."},

    # ---- 延时设置
    "page.card.delays": {"zh": "⏱️ 延时设置", "en": "⏱️ Timings"},
    "page.delay.ready": {"zh": "换牌前等待（秒）", "en": "Mulligan wait (s)"},
    "page.delay.ready.hint": {"zh": "每局进入换牌后先等 N 秒再识图",
                              "en": "Wait before OCR in the mulligan phase"},
    "page.delay.post_ocr": {"zh": "识别后缓冲（秒）", "en": "Post-OCR buffer (s)"},
    "page.delay.post_ocr.hint": {"zh": "换牌识别成功后到点击的缓冲",
                                 "en": "Buffer between recognition and the click"},
    "page.delay.retry": {"zh": "换牌重试间隔（秒）", "en": "Mulligan retry (s)"},
    "page.delay.retry.hint": {"zh": "面板未就绪/推荐不可执行时每轮重试的等待",
                              "en": "Wait between retries when the panel is not ready"},
    "page.delay.first_card": {"zh": "每张开局卡延时（秒）",
                              "en": "Per start-of-game card (s)"},
    "page.delay.first_card.hint": {"zh": "检测到一张开局生效全局卡额外追加的秒数",
                                   "en": "Extra seconds per start-of-game trigger card"},
    "page.delay.pre": {"zh": "每回合前延时（秒）", "en": "Pre-turn delay (s)"},
    "page.delay.pre.hint": {"zh": "新回合开始给盒子更新推荐留时间",
                            "en": "Give the deck helper time to refresh its advice"},
    "page.delay.post": {"zh": "操作后延时（秒）", "en": "Post-action delay (s)"},
    "page.delay.post.hint": {"zh": "一次操作后到下轮 OCR 的间隔",
                             "en": "Gap between an action and the next OCR"},
    "page.delay.ocr": {"zh": "OCR 缩放", "en": "OCR scale"},
    "page.delay.ocr.hint": {"zh": "识别精度/速度平衡点",
                            "en": "Accuracy / speed trade-off"},
    "page.delay.save": {"zh": "💾 保存延时", "en": "💾 Save timings"},
    "page.delay.summary": {
        "zh": "当前时序：换牌前 {ready}s / 识别后 {post_ocr}s / 换牌重试 {retry}s / "
              "每张开局卡 {first_card}s / 回合前 {pre}s / 操作后 {post}s / OCR {ocr}。"
              "写入 ui_config.json 的 delays 段即时生效（下次开局/下回合读取）；运行中不可修改。",
        "en": "Current timings: mulligan {ready}s / post-OCR {post_ocr}s / retry {retry}s / "
              "per card {first_card}s / pre-turn {pre}s / post-action {post}s / OCR {ocr}. "
              "Saved to delays in ui_config.json, applied on the next game or turn; locked while running."},
    "page.delay.loading": {"zh": "当前时序由服务端配置返回，见下方保存后刷新。",
                           "en": "Timings come from the server config; save to refresh."},

    # ---- 校准
    "page.card.calibrate": {"zh": "🎯 校准推荐区域", "en": "🎯 Calibrate ROI"},
    "page.calibrate.btn": {"zh": "📐 显示校准框", "en": "📐 Show calibration box"},
    "page.calibrate.hint": {
        "zh": "对战中启动：屏幕显示绿框（= 程序截图区域）。拖动绿框与盒子的「打法参考A」面板对齐，"
              "按 S 保存（不覆盖名字/日志目录），Esc 退出。",
        "en": "Start it while in a game: a green box marks the captured region. Drag it over the helper's "
              "advice panel, press S to save (name/log folder untouched), Esc to exit."},

    # ---- 实时日志
    "page.card.log": {"zh": "📜 实时日志", "en": "📜 Live log"},
    "page.log.autoscroll": {"zh": "自动滚动", "en": "Auto-scroll"},
    "page.log.clear": {"zh": "清空", "en": "Clear"},

    # ---- 横幅
    "page.banner.not_admin": {
        "zh": "当前未以<b>管理员权限</b>运行，自动化鼠标/键盘操作可能失效。<br>"
              "请关闭本窗口，在<b>管理员命令提示符</b>中运行：<b>python web_ui.py</b>",
        "en": "Not running as <b>administrator</b>: mouse/keyboard automation may fail.<br>"
              "Close this window and run <b>python web_ui.py</b> from an <b>administrator</b> shell."},
    "page.banner.mismatch": {
        "zh": "用户 ID 与日志玩家名<b>不匹配</b>：日志中玩家为 <b>{names}</b>，"
              "当前配置为 <b>{config}</b>。<br>请把「用户 ID」改成现在的"
              "<b>完整战网昵称（含 #编号）</b>，否则脚本会把整局都当成对手回合而<b>不出牌</b>。",
        "en": "BattleTag does <b>not match</b> the game log: log players are <b>{names}</b>, "
              "configured is <b>{config}</b>.<br>Set the <b>full BattleTag (with #number)</b>, "
              "otherwise the bot treats every turn as the opponent's and <b>never plays</b>."},
    "page.banner.schedule_done": {
        "zh": "定时任务完成：本局对战结束后已自动停止。<b>共完成 {games} 场对战，赢 {wins} 场</b>。"
              "可再次开始对战或设置新的定时任务。",
        "en": "Schedule finished: stopped after the last game. <b>{games} games, {wins} wins</b>. "
              "You can start again or set a new schedule."},

    # ---- 提示条 / 错误
    "page.toast.saved": {"zh": "配置已保存", "en": "Configuration saved"},
    "page.toast.save_failed": {"zh": "保存失败", "en": "Save failed"},
    "page.toast.op_failed": {"zh": "操作失败", "en": "Action failed"},
    "page.toast.pick_start": {"zh": "请选择开始时间", "en": "Pick a start time"},
    "page.toast.sched_failed": {"zh": "设置失败", "en": "Could not set the schedule"},
    "page.toast.cancel_failed": {"zh": "取消失败", "en": "Could not cancel"},
    "page.toast.network": {"zh": "网络错误：{msg}", "en": "Network error: {msg}"},
    "page.toast.lang_saved": {"zh": "界面语言已切换为中文",
                              "en": "Language switched to English"},
    "page.empty": {"zh": "（空）", "en": "(empty)"},
    "page.none": {"zh": "空", "en": "empty"},
    "page.countdown.now": {"zh": "已到点", "en": "due"},

    # ============================================================ 日志浮窗
    "ov.brand.sub": {"zh": "炉石传说 · 自动对战", "en": "Hearthstone auto-play"},
    "ov.title": {"zh": "自动化日志", "en": "Automation log"},
    "ov.score.none": {"zh": "📊 战绩： —", "en": "📊 Score: —"},
    "ov.score": {"zh": "📊 战绩： 胜 {wins} · 负 {losses} · 胜率 {rate}{concedes}",
                 "en": "📊 Score: {wins}W · {losses}L · {rate}{concedes}"},
    "ov.score.concedes": {"zh": " · 认输 {n}", "en": " · {n} conceded"},
    "ov.row.human_like": {"zh": "活人感", "en": "Human"},
    "ov.row.concede": {"zh": "投降检测", "en": "Concede"},
    "ov.row.hearthstone": {"zh": "炉石", "en": "Client"},
    "ov.row.account": {"zh": "账号", "en": "Account"},
    "ov.value.on": {"zh": "开", "en": "on"},
    "ov.value.off": {"zh": "关", "en": "off"},
    "ov.value.unknown": {"zh": "—", "en": "—"},
    "ov.hl.detail": {"zh": "{lo}~{hi}s · 悬停 {h_lo}~{h_hi}s",
                     "en": "{lo}~{hi}s · hover {h_lo}~{h_hi}s"},
    "ov.cd.detail": {"zh": "阈值 {threshold}% · 连续 {streak}/{rounds}",
                     "en": "threshold {threshold}% · {streak}/{rounds}"},
    "ov.cd.detail.below": {"zh": "低于阈值 {threshold}% · 连续 {streak}/{rounds}",
                           "en": "below {threshold}% · {streak}/{rounds}"},
    "ov.cd.triggered": {"zh": "已触发认输", "en": "conceded"},
    "ov.cd.no_rate": {"zh": "未读到", "en": "no data"},
    "ov.cd.no_rate.detail": {"zh": "{where} · 连续 {streak}/{rounds}",
                             "en": "{where} · {streak}/{rounds}"},
    "ov.cd.where.turn": {"zh": "第 {turn} 回合", "en": "turn {turn}"},
    "ov.cd.where.now": {"zh": "本回合", "en": "this turn"},
    "ov.lv.disabled": {"zh": "关", "en": "off"},
    "ov.lv.gone": {"zh": "已退出", "en": "exited"},
    "ov.lv.gone.detail": {"zh": "已自动停止", "en": "auto-stopped"},
    "ov.lv.stale": {"zh": "无响应", "en": "no response"},
    "ov.lv.warning": {"zh": "疑似卡死", "en": "possibly stuck"},
    "ov.lv.stall": {"zh": "日志停滞 {age}s", "en": "log stalled {age}s"},
    "ov.lv.idle": {"zh": "未运行", "en": "not running"},
    "ov.lv.ok": {"zh": "运行中", "en": "running"},
    "ov.lv.ok.detail": {"zh": "日志 {age}s 前", "en": "log {age}s ago"},
    "ov.account.match": {"zh": "匹配", "en": "match"},
    "ov.account.mismatch": {"zh": "不匹配", "en": "MISMATCH"},
    "ov.account.hidden": {"zh": "已隐藏", "en": "hidden"},
    "ov.btn.start": {"zh": "▶  开始对战", "en": "▶  Start playing"},
    "ov.btn.in_game": {"zh": "⏳  对局进行中", "en": "⏳  In game"},
    "ov.btn.halt": {"zh": "⏹  中止", "en": "⏹  Stop"},
    "ov.btn.resume": {"zh": "▶  恢复", "en": "▶  Resume"},
    "ov.btn.stop_after": {"zh": "⏸  本局结束后停止",
                          "en": "⏸  Stop after this game"},
    "ov.btn.stop_after.active": {"zh": "✓  本局结束后停止（点击取消）",
                                 "en": "✓  Stop after this game (click to cancel)"},
    "ov.btn.save": {"zh": "💾  保存日志", "en": "💾  Save log"},
    "ov.btn.saved": {"zh": "✓  已保存", "en": "✓  Saved"},
    "ov.btn.save_failed": {"zh": "✗  保存失败", "en": "✗  Save failed"},
    "ov.btn.exit": {"zh": "🚪  退出脚本", "en": "🚪  Quit script"},
    "ov.delay.none": {"zh": "延时：无", "en": "Delay: none"},
    "ov.delay.running": {"zh": "⏳ {desc}（{remaining}/{total}s）",
                         "en": "⏳ {desc} ({remaining}/{total}s)"},
    "ov.log.saved": {"zh": "[SYS] 对战日志已保存：{path}",
                     "en": "[SYS] Log saved to {path}"},
    "ov.log.save_failed": {"zh": "[SYS] 保存对战日志失败：{error}",
                           "en": "[SYS] Could not save the log: {error}"},

    # ============================================================ 服务端消息
    "msg.api.need_name": {"zh": "请先填写用户 ID。", "en": "Enter your BattleTag first."},
    "msg.api.need_log": {"zh": "请先填写炉石日志目录。",
                         "en": "Enter the Hearthstone log folder first."},
    "msg.api.log_missing": {"zh": "日志目录不存在：{path}",
                            "en": "Log folder does not exist: {path}"},
    "msg.api.running": {"zh": "自动化已经在运行中。",
                        "en": "The automation is already running."},
    "msg.api.not_running": {"zh": "当前没有正在运行的自动化。",
                            "en": "No automation is running."},
    "msg.api.starting": {"zh": "正在启动自动化，请稍候……",
                         "en": "Starting the automation, one moment…"},
    "msg.api.resuming": {"zh": "正在恢复自动化（战绩继续累计），请稍候……",
                         "en": "Resuming the automation (score kept)…"},
    "msg.api.prepared": {
        "zh": "已就绪：浮窗已开、炉石已切前台（不会自动开始）。再点一次「开始对战」或浮窗的 ▶ 开始对战 才会真正开打。",
        "en": "Ready: overlay open, Hearthstone in the foreground (nothing started). Press "
              "“Start playing” to actually begin."},
    "msg.api.stop_after": {"zh": "本局对战结束后将自动停止",
                           "en": "Will stop after the current game"},
    "msg.api.stopping": {"zh": "正在停止……", "en": "Stopping…"},
    "msg.api.schedule_set": {"zh": "定时任务已设置，请保持本程序运行。",
                             "en": "Schedule saved; keep this program running."},
    "msg.api.schedule_canceled": {"zh": "定时任务已取消", "en": "Schedule cancelled"},
    "msg.api.schedule_bad_start": {"zh": "开始时间格式不正确。",
                                   "en": "Invalid start time."},
    "msg.api.schedule_bad_end": {"zh": "结束时间格式不正确。",
                                 "en": "Invalid end time."},
    "msg.api.schedule_past": {"zh": "开始时间不能早于当前时间。",
                              "en": "The start time cannot be in the past."},
    "msg.api.schedule_order": {"zh": "结束时间必须晚于开始时间。",
                               "en": "The end time must be after the start time."},
    "msg.api.schedule_while_running": {
        "zh": "自动化运行中，请先停止后再设置定时任务。",
        "en": "Stop the automation before setting a schedule."},
    "msg.api.locked": {"zh": "自动化运行中，请先停止后再修改{what}。",
                       "en": "Stop the automation before changing {what}."},
    "msg.api.config_saved": {"zh": "配置已保存", "en": "Configuration saved"},
    "msg.api.concede_saved": {"zh": "自动投降配置已保存",
                              "en": "Auto-concede settings saved"},
    "msg.api.human_like_saved": {"zh": "活人感配置已保存",
                                 "en": "Human-like pacing saved"},
    "msg.api.liveness_saved": {"zh": "存活检测配置已保存",
                               "en": "Liveness settings saved"},
    "msg.api.delays_saved": {"zh": "延时配置已保存", "en": "Timings saved"},
    "msg.api.overlay_on": {"zh": "日志浮窗已开启", "en": "Log overlay opened"},
    "msg.api.overlay_off": {"zh": "日志浮窗已关闭", "en": "Log overlay closed"},
    "msg.api.overlay_unavailable": {"zh": "日志浮窗模块不可用",
                                    "en": "The log overlay module is unavailable"},
    "msg.api.bad_number": {"zh": "{field}必须为数字。",
                           "en": "{field} must be a number."},
    "msg.api.bad_int": {"zh": "{field}必须为整数。",
                        "en": "{field} must be a whole number."},
    "msg.api.out_of_range": {"zh": "{field}必须介于 {lo}–{hi}。",
                             "en": "{field} must be between {lo} and {hi}."},
    "msg.field.threshold": {"zh": "阈值", "en": "The threshold"},
    "msg.field.rounds": {"zh": "连续回合数", "en": "The turn count"},
    "msg.field.stall": {"zh": "停滞阈值", "en": "The stall threshold"},
    "msg.what.config": {"zh": "配置", "en": "the configuration"},
    "msg.what.concede": {"zh": "自动投降配置",
                         "en": "the auto-concede settings"},
    "msg.what.human_like": {"zh": "活人感配置",
                            "en": "the human-like pacing settings"},
    "msg.what.liveness": {"zh": "存活检测配置", "en": "the liveness settings"},
    "msg.what.delays": {"zh": "延时配置", "en": "the timings"},
    "msg.api.unknown": {"zh": "未知接口", "en": "Unknown endpoint"},
    "msg.api.calibrate_started": {
        "zh": "校准工具已启动（无预览：拖绿框对齐盒子面板后按 S 保存，Esc 退出）",
        "en": "Calibration tool started (drag the green box, press S to save, Esc to quit)"},
    "msg.api.calibrate_missing": {"zh": "校准工具缺失：{path}",
                                  "en": "Calibration tool missing: {path}"},
    "msg.api.calibrate_failed": {"zh": "启动校准工具失败：{error}",
                                 "en": "Could not start the calibration tool: {error}"},
    "msg.api.lang_saved": {"zh": "界面语言已切换为中文",
                           "en": "Interface language switched to English"},
    "msg.api.lang_bad": {"zh": "不支持的语言：{lang}",
                         "en": "Unsupported language: {lang}"},
    "msg.check.no_path": {"zh": "请先输入日志目录。",
                          "en": "Enter the log folder first."},
    "msg.check.missing": {"zh": "目录不存在，请检查路径。",
                          "en": "Folder not found — check the path."},
    "msg.check.found": {"zh": "✅ 找到最新对局日志 Power.log",
                        "en": "✅ Found the latest Power.log"},
    "msg.check.session_only": {
        "zh": "找到会话目录，暂无 Power.log（进行一局对战后自动生成）",
        "en": "Session folder found, no Power.log yet (created after one game)"},
    "msg.check.no_session": {
        "zh": "目录存在，但未发现炉石会话子目录（Hearthstone_时间戳 形式）",
        "en": "Folder exists but no Hearthstone_<timestamp> session folder was found"},

    # ---- 状态标签（网页「当前状态」/进度胶囊）
    "msg.state.idle": {"zh": "待机", "en": "Idle"},
    "msg.state.leave_hs": {"zh": "炉石未运行", "en": "Hearthstone not running"},
    "msg.state.wait_main_menu": {"zh": "等待主菜单", "en": "Waiting for main menu"},
    "msg.state.main_menu": {"zh": "主菜单", "en": "Main menu"},
    "msg.state.choosing_hero": {"zh": "选择职业", "en": "Choosing hero"},
    "msg.state.matching": {"zh": "匹配对手", "en": "Finding opponent"},
    "msg.state.choosing_card": {"zh": "换牌阶段", "en": "Mulligan"},
    "msg.state.battling": {"zh": "对战中", "en": "In game"},
    "msg.state.quitting": {"zh": "对局结算", "en": "Game over"},
    "msg.state.error": {"zh": "状态异常", "en": "Error"},

    # ---- 存活检测告警（issue 的核心）
    "msg.liveness.gone": {
        "zh": "炉石已退出：Hearthstone.exe 进程消失（已确认 {seconds:.0f}s 未回来）",
        "en": "Hearthstone exited: Hearthstone.exe is gone (missing for {seconds:.0f}s)"},
    "msg.liveness.stale_warn": {
        "zh": "炉石疑似无响应：对局中 Power.log 已 {age:.0f}s 没有新内容"
              "（超过 {warn:.0f}s 告警阈值，达到 {stop:.0f}s 将自动停止）{tail}",
        "en": "Hearthstone may be stuck: Power.log has been silent for {age:.0f}s "
              "during a game (warning at {warn:.0f}s, auto-stop at {stop:.0f}s){tail}"},
    "msg.liveness.stale_stop": {
        "zh": "炉石疑似无响应：对局中 Power.log 已 {age:.0f}s 没有新内容"
              "（超过 {stop:.0f}s 阈值）{tail}",
        "en": "Hearthstone may be stuck: Power.log has been silent for {age:.0f}s "
              "during a game (past the {stop:.0f}s threshold){tail}"},
    "msg.liveness.detail": {"zh": "（{detail}）", "en": " ({detail})"},
    "msg.liveness.detail.diag": {"zh": "最近自动化诊断：{code}",
                                 "en": "last diagnostic: {code}"},
    "msg.liveness.detail.fails": {"zh": "连续 {n} 次推荐读取失败",
                                  "en": "{n} failed read attempts in a row"},
    "msg.liveness.abort": {
        "zh": "⚠️ {message}；自动化已自动停止。请重新启动炉石后再点「开始运行」。",
        "en": "⚠️ {message}; the automation stopped itself. Restart Hearthstone, then press Prepare."},
    "msg.liveness.save_failed": {"zh": "保存浮窗显示偏好失败：{error}",
                                 "en": "Could not save the overlay preference: {error}"},
    "msg.overlay.account_shown": {"zh": "浮窗「账号」行已显示战网昵称。",
                                  "en": "Overlay account row now shows the BattleTag."},
    "msg.overlay.account_hidden": {
        "zh": "浮窗「账号」行已隐藏战网昵称（点眼睛按钮可恢复）。",
        "en": "Overlay account row now hides the BattleTag (click the eye to restore)."},

    # ---- 昵称校验
    "msg.name.mismatch": {
        "zh": "⚠️ 用户 ID 与日志玩家名不匹配：日志中玩家为 {names}，当前配置为 {config}。"
              "若刚换过战网账号，请把网页里的「用户 ID」改成现在的完整战网昵称（含 #编号），"
              "否则脚本会把整局都当成对手回合而不出牌。",
        "en": "⚠️ BattleTag mismatch: game log shows {names}, configured is {config}. "
              "After switching accounts, set the full BattleTag (with #number) in the web console, "
              "otherwise the bot treats every turn as the opponent's and never plays."},
    "msg.name.no_number": {
        "zh": "用户 ID 未包含 #编号，可能无法识别己方玩家，建议填写完整战网昵称。",
        "en": "The BattleTag has no #number; the bot may fail to recognise your own player. "
              "Use the full BattleTag."},

    # ---- 其它服务端提示
    "msg.hotkey.ok": {"zh": "热键 Ctrl+Q 已注册（立即停止）。",
                      "en": "Hotkey Ctrl+Q registered (stop now)."},
    "msg.hotkey.failed": {"zh": "注册 Ctrl+Q 热键失败：{error}（仍可通过页面停止）",
                          "en": "Could not register Ctrl+Q: {error} (use the page to stop)"},
    "msg.stage": {"zh": "-----{stage}阶段-----", "en": "-----{stage}-----"},
    "msg.stage.none": {"zh": "未对局", "en": "not in game"},
    "msg.stage.end": {"zh": "对局结束", "en": "game over"},
    "msg.stage.mulligan": {"zh": "换牌", "en": "mulligan"},
    "msg.stage.mine": {"zh": "我方出牌", "en": "my turn"},
    "msg.stage.opponent": {"zh": "对手回合", "en": "opponent turn"},
    "msg.log.started": {
        "zh": "自动化启动：用户 {name}，日志目录 {root}（战绩从 0 开始）",
        "en": "Automation started: user {name}, log folder {root} (score reset)"},
    "msg.log.resumed": {
        "zh": "自动化恢复：用户 {name}，日志目录 {root}（战绩继续累计：已完成 {games} 场）",
        "en": "Automation resumed: user {name}, log folder {root} (score kept: {games} games)"},
    "msg.log.ready": {
        "zh": "已就绪：日志浮窗已开启、正在把炉石切到前台；未开始对战，确认无误后再点「开始对战」。",
        "en": "Ready: overlay opened and Hearthstone is being brought to the front. "
              "Nothing started yet — press Start playing when ready."},
    "msg.log.ctrlq": {"zh": "收到 Ctrl+Q，立即停止自动化。",
                      "en": "Ctrl+Q received — stopping the automation."},
    "msg.summary.with_games": {
        "zh": "自动化结束：共完成 {games} 场对战，赢 {wins} 场{concedes}。",
        "en": "Automation finished: {games} games, {wins} wins{concedes}."},
    "msg.summary.concedes": {"zh": "，自动认输 {n} 场", "en": ", {n} conceded"},
    "msg.summary.no_games": {"zh": "自动化结束。", "en": "Automation finished."},
}
