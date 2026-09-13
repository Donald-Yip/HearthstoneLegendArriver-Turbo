# -*- coding: utf-8 -*-
"""多语言（中文 / English）：键完整性、切换、持久化与界面接线。

这个测试也是「后续改文案要记得补英文」这条约定的守门人：
  * 两种语言的键必须完全一致；
  * 网页里 data-i18n / t("…") 引用的键必须存在；
  * Python 代码里 t("…") 引用的键必须存在；
  * 中文文案不能为空。
少写一个（比如只加了中文）就会在这里失败。
"""

import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import config
import i18n
import log_overlay
import web_ui

ROOT = Path(__file__).resolve().parent.parent
INDEX_HTML = ROOT / "web" / "index.html"
PY_FILES = ("web_ui.py", "log_overlay.py", "FSM_action.py")


class TextTableTests(unittest.TestCase):
    def test_two_languages(self):
        self.assertEqual(("zh", "en"), i18n.LANGUAGES)

    def test_every_key_has_both_languages(self):
        for key, entry in i18n._TEXTS.items():
            self.assertIn("zh", entry, key)
            self.assertIn("en", entry, key)

    def test_no_empty_text(self):
        for key, entry in i18n._TEXTS.items():
            for lang in i18n.LANGUAGES:
                self.assertTrue(str(entry.get(lang, "")).strip(),
                                f"{key} 的 {lang} 文案是空的")

    def test_english_is_not_chinese_text(self):
        """英文项里不能还留着中文（漏翻最容易这样）。"""
        han = re.compile(r"[\u4e00-\u9fff]")
        leftovers = [key for key, entry in i18n._TEXTS.items()
                     if han.search(str(entry.get("en", "")))
                     and key.startswith(("page.", "ov.", "msg."))]
        self.assertEqual([], leftovers)

    def test_placeholders_match_between_languages(self):
        """中英版本的占位符必须一致，否则某一种语言会漏填。"""
        pattern = re.compile(r"\{(\w+)\}")
        for key, entry in i18n._TEXTS.items():
            zh = set(pattern.findall(str(entry.get("zh", ""))))
            en = set(pattern.findall(str(entry.get("en", ""))))
            self.assertEqual(zh, en, f"{key} 的占位符不一致：{zh} vs {en}")


class TranslationApiTests(unittest.TestCase):
    def setUp(self):
        self._saved = i18n.current_language()

    def tearDown(self):
        i18n.set_language(self._saved)

    def test_t_returns_chinese_by_default(self):
        i18n.set_language("zh")
        self.assertEqual("空闲", i18n.t("page.phase.idle"))

    def test_t_returns_english_after_switch(self):
        i18n.set_language("en")
        self.assertEqual("Idle", i18n.t("page.phase.idle"))

    def test_t_fills_placeholders(self):
        i18n.set_language("zh")
        self.assertIn("3", i18n.t("page.chip.start", time="3:00"))
        i18n.set_language("en")
        self.assertEqual("Starts in 3:00", i18n.t("page.chip.start", time="3:00"))

    def test_unknown_key_returns_the_key(self):
        self.assertEqual("nope.missing", i18n.t("nope.missing"))

    def test_unknown_placeholder_does_not_raise(self):
        self.assertTrue(i18n.t("page.chip.start"))

    def test_normalize_falls_back_to_chinese(self):
        self.assertEqual("zh", i18n.normalize("fr"))
        self.assertEqual("en", i18n.normalize("EN"))

    def test_texts_returns_a_flat_dict(self):
        table = i18n.texts("en")
        self.assertEqual(len(i18n._TEXTS), len(table))
        self.assertEqual("Idle", table["page.phase.idle"])


class LanguagePersistenceTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "ui_config.json"
        self._saved_path = config.CONFIG_PATH
        config.CONFIG_PATH = self.path
        self.path.write_text(json.dumps(
            {"name": "TestUser#12345", "log_root": "D:\\Logs"},
            ensure_ascii=False), encoding="utf-8")

    def tearDown(self):
        config.CONFIG_PATH = self._saved_path
        self._tmp.cleanup()

    def test_default_is_chinese(self):
        self.assertEqual("zh", config.ui_language())

    def test_save_and_read_back(self):
        self.assertEqual("en", config.save_ui_language("en"))
        self.assertEqual("en", config.ui_language())

    def test_illegal_value_falls_back(self):
        self.assertEqual("zh", config.save_ui_language("klingon"))
        self.assertEqual("zh", config.ui_language())

    def test_other_settings_are_preserved(self):
        config.save_ui_language("en")
        written = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual("TestUser#12345", written["name"])
        self.assertEqual("D:\\Logs", written["log_root"])

    def test_overlay_setting_and_language_coexist(self):
        config.save_ui_language("en")
        config.save_overlay_setting("show_account", False)

        self.assertEqual("en", config.ui_language())
        self.assertFalse(config.overlay_settings()["show_account"])


class PageWiringTests(unittest.TestCase):
    def setUp(self):
        self.html = INDEX_HTML.read_text(encoding="utf-8")

    def test_language_switch_is_in_the_header(self):
        header = self.html.split("</header>")[0]
        self.assertIn('id="langSwitch"', header)
        self.assertIn('data-lang="zh"', header)
        self.assertIn('data-lang="en"', header)

    def test_page_references_only_existing_keys(self):
        keys = set(re.findall(r'data-i18n(?:-ph|-title)?="([^"]+)"', self.html))
        keys |= set(re.findall(r'\bt\("([^"]+)"', self.html))
        self.assertGreater(len(keys), 60)
        missing = sorted(k for k in keys if not i18n.has_key(k))
        self.assertEqual([], missing, f"页面引用了不存在的文案键：{missing}")

    def test_python_code_references_only_existing_keys(self):
        missing = {}
        for name in PY_FILES:
            source = (ROOT / name).read_text(encoding="utf-8")
            keys = set(re.findall(r'\bt\(\s*"([^"]+)"', source))
            # web_ui 里的状态/阶段映射表：值是文案键
            if name == "web_ui.py":
                keys |= set(re.findall(r'"(msg\.state\.[a-z_]+)"', source))
                keys |= set(re.findall(r'"(msg\.stage\.[a-z_]+)"', source))
            bad = sorted(k for k in keys if not i18n.has_key(k))
            if bad:
                missing[name] = bad
        self.assertEqual({}, missing)

    def test_no_hardcoded_chinese_left_in_the_page_script(self):
        """页面脚本里不应再出现中文提示（文案都在 i18n.py 里）。"""
        script = self.html.split("<script>", 1)[1].split("</script>", 1)[0]
        # 先去掉注释，再找残留的中文（注释写中文没问题，是给维护者看的）。
        script = re.sub(r"/\*.*?\*/", "", script, flags=re.S)
        script = re.sub(r"//[^\n]*", "", script)
        han = re.compile(r"[\u4e00-\u9fff]")
        offenders = [line.strip()[:60] for line in script.splitlines()
                     if han.search(line)]
        self.assertEqual([], offenders)


class ServerApiTests(unittest.TestCase):
    """接口层的语言切换。

    注意：这几条测试会真的走「保存语言」的代码路径，所以必须把配置文件路径
    指到临时文件 —— 否则跑一次测试就把用户自己的 ui_config.json 改成英文了。
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "ui_config.json"
        self.path.write_text(json.dumps(
            {"name": "TestUser#12345", "log_root": "D:\\Logs"},
            ensure_ascii=False), encoding="utf-8")
        self._saved = i18n.current_language()
        self._config_path = config.CONFIG_PATH
        self._web_config_path = web_ui.CONFIG_PATH
        config.CONFIG_PATH = self.path
        web_ui.CONFIG_PATH = self.path
        self.saved_config = {}
        self._patches = [
            patch.object(web_ui, "_log"),
        ]
        for p in self._patches:
            p.start()
        self._thread = web_ui.CTRL.automation_thread
        web_ui.CTRL.automation_thread = None

    def tearDown(self):
        web_ui.CTRL.automation_thread = self._thread
        for p in self._patches:
            p.stop()
        config.CONFIG_PATH = self._config_path
        web_ui.CONFIG_PATH = self._web_config_path
        self._tmp.cleanup()
        i18n.set_language(self._saved)

    def test_switch_language_returns_the_new_table(self):
        result = web_ui.api_set_language({"lang": "en"})

        self.assertTrue(result["ok"])
        self.assertEqual("en", result["lang"])
        self.assertEqual("Idle", result["texts"]["page.phase.idle"])
        self.assertEqual("en", i18n.current_language())

    def test_switch_language_is_persisted(self):
        with patch.object(config, "save_ui_language") as save:
            web_ui.api_set_language({"lang": "en"})

        save.assert_called_once_with("en")

    def test_bad_language_is_refused(self):
        result = web_ui.api_set_language({"lang": "fr"})

        self.assertFalse(result["ok"])
        self.assertIn("fr", result["error"])

    def test_status_reports_the_language(self):
        web_ui.api_set_language({"lang": "en"})

        self.assertEqual("en", web_ui.status_snapshot()["lang"])

    def test_state_label_follows_the_language(self):
        web_ui.api_set_language({"lang": "zh"})
        self.assertEqual("对战中", web_ui.state_label("Battling"))

        web_ui.api_set_language({"lang": "en"})
        self.assertEqual("In game", web_ui.state_label("Battling"))

    def test_api_messages_follow_the_language(self):
        # 用空配置 → api_start 只会返回「请先填写用户 ID」，不会真去启动自动化。
        with patch.object(web_ui, "load_config", return_value={}):
            web_ui.api_set_language({"lang": "en"})
            self.assertEqual("Enter your BattleTag first.",
                             web_ui.api_start({})["error"])

            web_ui.api_set_language({"lang": "zh"})
            self.assertEqual("请先填写用户 ID。", web_ui.api_start({})["error"])


class OverlayLanguageTests(unittest.TestCase):
    def setUp(self):
        self._saved = i18n.current_language()

    def tearDown(self):
        i18n.set_language(self._saved)

    def test_rows_follow_the_language(self):
        info = {"enabled": True, "post_delay_min": 0.5, "post_delay_max": 3.0,
                "hover_min": 0.2, "hover_max": 1.0}
        i18n.set_language("zh")
        self.assertEqual("开", log_overlay.human_like_row(info)["value"])
        i18n.set_language("en")
        self.assertEqual("on", log_overlay.human_like_row(info)["value"])

    def test_account_row_hidden_text_follows_the_language(self):
        info = {"config": "A#1", "players": {"1": "A#1"}, "matched": True}
        i18n.set_language("en")
        row = log_overlay.account_row(info, show_account=False)
        self.assertEqual(log_overlay.account_hidden_text(), row["detail"])
        self.assertEqual("hidden", row["detail"])

    def test_hearthstone_row_follows_the_language(self):
        i18n.set_language("en")
        row = log_overlay.hearthstone_row({"status": "gone"})
        self.assertEqual("exited", row["value"])

    def test_delay_bar_accepts_english_wording(self):
        match = log_overlay._delay_start_re.search("Delay 2.4s after")
        self.assertIsNotNone(match)
        self.assertAlmostEqual(2.4, float(match.group(1)), places=3)
        self.assertIn("delay finished", log_overlay._delay_end_markers)


class FsmAlertLanguageTests(unittest.TestCase):
    def setUp(self):
        self._saved = i18n.current_language()

    def tearDown(self):
        i18n.set_language(self._saved)

    def test_liveness_alert_is_translated(self):
        import FSM_action

        saved = (FSM_action.quitting_flag, FSM_action._liveness_alert)
        FSM_action.quitting_flag = False
        FSM_action._liveness_alert = None
        FSM_action.shutdown_event.clear()
        try:
            i18n.set_language("en")
            with patch.object(FSM_action.manual_controller, "output"), \
                 patch.object(FSM_action, "error_print"):
                FSM_action._alert_hearthstone_gone("Hearthstone exited")
            self.assertIn("Hearthstone exited", FSM_action._liveness_alert)
            self.assertIn("stopped itself", FSM_action._liveness_alert)
            self.assertTrue(FSM_action.quitting_flag)
        finally:
            (FSM_action.quitting_flag, FSM_action._liveness_alert) = saved
            FSM_action.shutdown_event.clear()
            i18n.set_language(self._saved)


class OverlayPanelWidthTests(unittest.TestCase):
    """状态面板必须放得下两种语言（英文更长，最容易把数值列挤没）。

    用真实的 Tk 控件与字号量一遍面板的需求宽度，超过窗口宽度就说明新加的
    文案太长——要么改短，要么把 WINDOW_WIDTH 调大。
    """

    # 每行的“最坏情况”数据（最长的值 + 最长的说明）
    ROWS = (
        ("human_like_row", {"enabled": True, "post_delay_min": 0.5,
                            "post_delay_max": 3.0, "hover_min": 0.2,
                            "hover_max": 1.0}),
        ("concede_detect_row", {"enabled": True, "threshold": 20.0, "rounds": 3,
                                "rate": 15.4, "streak": 2, "checked_turn": 5,
                                "triggered": False}),
        ("hearthstone_row", {"status": "warning", "log_age": 130.0,
                             "in_game": True}),
        ("account_row", {"config": "VeryLongBattleTag#12345",
                         "players": {"1": "VeryLongBattleTag#12345"},
                         "matched": False}),
    )

    def _measure(self, lang):
        import tkinter as tk

        i18n.set_language(lang)
        root = tk.Tk()
        root.withdraw()
        try:
            frame = tk.Frame(root, bg=log_overlay.PANEL)
            frame.columnconfigure(2, weight=1)
            names = ("ov.row.human_like", "ov.row.concede",
                     "ov.row.hearthstone", "ov.row.account")
            for index, ((func_name, info), name_key) in enumerate(
                    zip(self.ROWS, names)):
                row = getattr(log_overlay, func_name)(info)
                tk.Label(frame, text="●",
                         font=("Segoe UI", 7)).grid(
                    row=index, column=0, sticky="w", padx=(8, 3), pady=1)
                tk.Label(frame, text=i18n.t(name_key),
                         font=("Microsoft YaHei", 8)).grid(
                    row=index, column=1, sticky="w", pady=1)
                tk.Label(frame, text=row["value"],
                         font=("Microsoft YaHei", 8, "bold")).grid(
                    row=index, column=2, sticky="w", padx=(6, 0), pady=1)
                tk.Label(frame, text=row["detail"],
                         font=("Microsoft YaHei", 8)).grid(
                    row=index, column=3, sticky="e", padx=(6, 6), pady=1)
            eye = tk.Frame(frame, bg=log_overlay.PANEL, width=24, height=18)
            eye.grid(row=0, column=4, sticky="e", padx=(2, 6), pady=1)
            frame.update_idletasks()
            return frame.winfo_reqwidth()
        finally:
            root.destroy()

    def test_panel_fits_the_window_in_both_languages(self):
        try:
            import tkinter  # noqa: F401
        except Exception:                       # pragma: no cover
            self.skipTest("当前环境没有 tkinter")
        for lang in i18n.LANGUAGES:
            with self.subTest(lang=lang):
                width = self._measure(lang)
                self.assertLessEqual(
                    width, log_overlay.WINDOW_WIDTH,
                    f"{lang} 的面板需要 {width}px，超过窗口宽度 "
                    f"{log_overlay.WINDOW_WIDTH}px（文案太长或窗口太窄）")

    def tearDown(self):
        i18n.set_language("zh")


if __name__ == "__main__":
    unittest.main()
