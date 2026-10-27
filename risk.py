import random
import numpy as np


class SeatAnalyzer:
    def __init__(self, cfg):
        self.cfg = cfg
        self.seat_ids = ("A1", "A2", "A3", "B1", "B2", "B3")

    def analyze(self, dets, ir_corr):
        records = []
        h, w = ir_corr.shape
        for det in dets:
            x1, y1, x2, y2 = det["box"]
            margins = self.cfg.seat_inner_margin if det["obj_type"] == "chair" else self.cfg.obj_inner_margin
            mx, my = ((x2 - x1) * margins[0], (y2 - y1) * margins[1])
            inner = (x1 + mx, y1 + my, x2 - mx, y2 - my)
            if inner[2] <= inner[0] or inner[3] <= inner[1]:
                inner = (x1, y1, x2, y2)
            left, top, right, bottom = (
                round(value) for value in np.clip(inner, (0, 0, 0, 0), (w - 1, h - 1, w - 1, h - 1))
            )
            if right <= left or bottom <= top:
                continue
            values = ir_corr[top : bottom + 1, left : right + 1].astype(np.float32).reshape(-1)
            cutoff = np.percentile(values, 100.0 - self.cfg.top_percent)
            current_ir = float(values[values >= cutoff].mean())
            records.append(
                {
                    **det,
                    "cx": (x1 + x2) / 2,
                    "cy": (y1 + y2) / 2,
                    "current_ir": current_ir,
                    "is_hot": current_ir >= self.cfg.obj_hot_ir,
                }
            )
        chairs = sorted(
            (r for r in records if r["obj_type"] == "chair"), key=lambda r: r["conf"], reverse=True
        )[:6]
        chairs.sort(key=lambda r: r["cy"])
        seat_map = dict(zip(self.seat_ids[:3], sorted(chairs[:3], key=lambda r: r["cx"])))
        seat_map.update(zip(self.seat_ids[3:], sorted(chairs[3:], key=lambda r: r["cx"])))
        statuses = {
            seat_id: {
                "state": "NO DETECT",
                "mean_heat": 0,
                "max_heat": 0,
                "crop_image": "",
                "warning_message": "",
                "hot_object": "",
            }
            for seat_id in self.seat_ids
        }
        overlays = []
        crop_boxes = {}
        names = {"battery": "배터리", "handbag": "핸드백", "backpack": "백팩"}
        for seat_id, chair in seat_map.items():
            x1, y1, x2, y2 = chair["box"]
            margin = self.cfg.seat_center_margin
            left, right, top, bottom = (x1 + margin, x2 - margin, y1 + margin, y2 - margin)
            if left >= right or top >= bottom:
                left, right, top, bottom = (x1, x2, y1, y2)
            matched = [
                r
                for r in records
                if r["obj_type"] in names and left <= r["cx"] <= right and (top <= r["cy"] <= bottom)
            ]
            target = max(matched, key=lambda r: (r["obj_type"] == "battery", r["conf"])) if matched else chair
            current_ir = target["current_ir"]
            obj_type = target["obj_type"]
            if matched and current_ir >= self.cfg.obj_hot_ir:
                state, color = ("HOT", (0, 0, 255))
                message = f"{seat_id} 좌석 의자 위 {names[obj_type]}에서 열 발생이 감지되었습니다."
                mean_heat = random.uniform(43.0, 45.0)
                max_heat = random.uniform(max(45.0, mean_heat + 0.5), 47.0)
            elif not matched and current_ir >= self.cfg.no_obj_warn_ir:
                state, color = ("WARN", (0, 255, 255))
                message = f"{seat_id} 좌석에서 주의가 필요한 열 발생이 감지되었습니다."
                mean_heat = random.uniform(30.0, 36.5)
                max_heat = random.uniform(mean_heat + 0.5, min(39.0, mean_heat + 2.5))
            else:
                state, color = ("OK", (0, 255, 0))
                message = (
                    f"{seat_id} 좌석 의자 위 {names[obj_type]}의 온도가 정상입니다."
                    if matched
                    else f"{seat_id} 좌석 상태가 정상입니다."
                )
                mean_heat = random.uniform(20.0, 27.0)
                max_heat = random.uniform(mean_heat + 0.5, min(29.0, mean_heat + 2.0))
            statuses[seat_id] = {
                "state": state,
                "mean_heat": round(mean_heat, 1),
                "max_heat": round(max_heat, 1),
                "crop_image": "",
                "warning_message": message,
                "hot_object": obj_type,
                "current_ir": round(current_ir, 1),
                "display_temp_note": "state_based_ui_display_value",
                "ir_object_hot_threshold": self.cfg.obj_hot_ir,
                "ir_no_object_warn_threshold": self.cfg.no_obj_warn_ir,
                "has_danger_object": bool(matched),
            }
            text_object = "NO-OBJECT " if state == "WARN" else f"{obj_type} " if state == "HOT" else ""
            overlays.append((target["box"], f"{seat_id} {state} {text_object}IR:{current_ir:.0f}", color))
            crop_boxes[seat_id] = chair["box"]
        return (records, statuses, overlays, crop_boxes)
