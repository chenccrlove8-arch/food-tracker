import copy
from io import BytesIO
import json
import math
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from PIL import Image
from streamlit.testing.v1 import AppTest

from tracker_core import month_records, parse_analysis, prepare_image, totals, validate_items
from tracker_store import read_meals, write_meal

APP = str(Path(__file__).resolve().parent / "app.py")
ITEM = {"name": "测试餐食", "grams": 100, "calories": 200, "protein": 10, "carbs": 25, "fat": 6}
ANALYSIS = {"is_food": True, "items": [ITEM], "confidence": "中", "uncertainties": ["份量为估算"], "reason": "测试数据", "suggestion": "测试建议"}


class CoreTests(unittest.TestCase):
    def test_invalid_ai_output_cannot_be_saved(self):
        for value in [float("nan"), float("inf"), -1, 20001, True]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_items([{**ITEM, "calories": value}])
        with self.assertRaises(ValueError):
            validate_items([])
        self.assertFalse(parse_analysis('{"is_food":false,"reason":"非食物"}')["is_food"])
        self.assertEqual(parse_analysis("```json\n" + json.dumps(ANALYSIS) + "\n```")["items"][0]["name"], ITEM["name"])

    def test_portion_and_month_boundaries(self):
        self.assertEqual(totals([ITEM], 0.5)["calories"], 100)
        rows = [{"meal_date": "2026-09-30"}, {"meal_date": "2026-10-01"}, {"meal_date": "2026-10-31"}, {"meal_date": "2026-11-01"}]
        self.assertEqual(len(month_records(rows, "2026-10")), 2)

    def test_photo_resized_and_metadata_removed(self):
        image = Image.new("RGB", (2000, 1000), "gray")
        exif = image.getexif()
        exif[270] = "private metadata"
        output = BytesIO()
        image.save(output, format="JPEG", exif=exif)
        prepared = Image.open(BytesIO(prepare_image(output.getvalue())))
        self.assertEqual(prepared.size, (1280, 640))
        self.assertFalse(prepared.getexif())
        with self.assertRaises(ValueError):
            prepare_image(b"x" * (16 * 1024 * 1024))


class StoreTests(unittest.TestCase):
    def test_reads_filter_owner_and_save_retries_ignore_duplicates(self):
        client = MagicMock()
        query = client.table.return_value
        query.select.return_value.eq.return_value.order.return_value.order.return_value.range.return_value.execute.return_value.data = []
        self.assertEqual(read_meals(client, "user-A"), [])
        query.select.return_value.eq.assert_called_with("user_id", "user-A")
        write_meal(client, "user-A", {"id": "fixed-id", "user_id": "spoofed"})
        query.upsert.assert_called_once_with({"id": "fixed-id", "user_id": "user-A"}, on_conflict="id", ignore_duplicates=True)


class AppTests(unittest.TestCase):
    def test_guest_startup_and_pages(self):
        app = AppTest.from_file(APP).run(timeout=15)
        self.assertFalse(app.exception)
        self.assertTrue(any("体验模式" in x.value for x in app.warning))
        for page in ["饮食记录", "月度回顾", "记一餐"]:
            app.segmented_control(key="page").set_value(page).run()
            self.assertFalse(app.exception)

    def test_auto_analysis_only_once_confirmation_scales_and_refreshes(self):
        buffer = BytesIO()
        Image.new("RGB", (10, 10), "gray").save(buffer, format="JPEG")
        photo = BytesIO(buffer.getvalue())
        ai = MagicMock()
        ai.return_value.chat.completions.create.return_value = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(ANALYSIS)))])
        def camera(*args, **kwargs):
            import streamlit as st
            return photo if st.session_state.capture_version == 0 else None
        with patch("streamlit.camera_input", side_effect=camera), patch("openai.OpenAI", ai):
            app = AppTest.from_file(APP)
            app.session_state["own_api_key"] = "fake-test-key"
            app.run(timeout=15)
            self.assertFalse(app.exception)
            self.assertEqual(len(app.session_state["guest_meals"]), 0)
            self.assertEqual(ai.return_value.chat.completions.create.call_count, 1)
            draft_id = app.session_state["draft"]["id"]
            app.select_slider(key=f"portion_{draft_id}").set_value(50).run()
            self.assertFalse(app.exception)
            self.assertEqual(ai.return_value.chat.completions.create.call_count, 1)
            app.button(key="save_meal").click().run()
            self.assertFalse(app.exception)
            self.assertEqual(len(app.session_state["guest_meals"]), 1)
            self.assertEqual(app.session_state["guest_meals"][0]["calories"], 100)
            self.assertEqual(app.metric[0].value, "100 kcal")
            app.run()
            self.assertEqual(len(app.session_state["guest_meals"]), 1)
            app.segmented_control(key="page").set_value("饮食记录").run()
            self.assertFalse(app.exception)
            self.assertEqual(len(app.dataframe[0].value), 1)

    def test_bad_photo_result_never_writes(self):
        buffer = BytesIO()
        Image.new("RGB", (10, 10)).save(buffer, format="JPEG")
        ai = MagicMock()
        ai.return_value.chat.completions.create.return_value = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='{"is_food":false,"reason":"没有食物"}'))])
        with patch("streamlit.camera_input", return_value=buffer), patch("openai.OpenAI", ai):
            app = AppTest.from_file(APP)
            app.session_state["own_api_key"] = "fake-test-key"
            app.run(timeout=15)
            self.assertFalse(app.exception)
            self.assertIsNone(app.session_state["draft"])
            self.assertEqual(len(app.session_state["guest_meals"]), 0)


if __name__ == "__main__":
    unittest.main()
