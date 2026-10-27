import base64
import cv2
import numpy as np


def draw_box(image, box, text, color=(0, 255, 0)):
    h, w = image.shape[:2]
    x1, y1, x2, y2 = (round(value) for value in np.clip(box, (0, 0, 0, 0), (w - 1, h - 1, w - 1, h - 1)))
    cv2.rectangle(image, (x1, y1), (x2, y2), color, 2)
    if text:
        cv2.putText(
            image, text, (x1, max(20, y1 - 10)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2, cv2.LINE_AA
        )


class Display:
    def __init__(self, cfg):
        self.cfg = cfg
        self.window_name = "RGB + YOLO | COLOR IR + TEMP | BLEND"

    def make_crops(self, rgb, ir_corr, crop_boxes):
        ir = (
            cv2.applyColorMap(ir_corr, cv2.COLORMAP_JET)
            if self.cfg.use_colormap
            else cv2.cvtColor(ir_corr, cv2.COLOR_GRAY2BGR)
        )
        blend = cv2.addWeighted(rgb, self.cfg.rgb_alpha, ir, 1 - self.cfg.rgb_alpha, 0)
        h, w = ir_corr.shape
        images = {}
        for seat_id, box in crop_boxes.items():
            x1, y1, x2, y2 = box
            left, top = (max(0, int(x1) - 45), max(0, int(y1) - 45))
            right, bottom = (min(w, int(x2) + 45), min(h, int(y2) + 45))
            if right <= left or bottom <= top:
                images[seat_id] = ""
                continue
            crops = []
            for source, title in ((rgb, "RGB"), (ir, "IR"), (blend, "BLEND")):
                crop = source[top:bottom, left:right]
                crop = cv2.resize(crop, (int(crop.shape[1] * 240 / crop.shape[0]), 240))
                color = (0, 255, 0) if title == "RGB" else (255, 255, 255)
                cv2.putText(crop, title, (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
                crops.append(crop)
            ok, encoded = cv2.imencode(".jpg", np.hstack(crops), [cv2.IMWRITE_JPEG_QUALITY, 82])
            if not ok:
                images[seat_id] = ""
                continue
            images[seat_id] = "data:image/jpeg;base64," + base64.b64encode(encoded).decode("utf-8")
        return images

    def show(self, rgb, ir_corr, records, overlays, info_text):
        rgb_display = rgb.copy()
        ir_display = (
            cv2.applyColorMap(ir_corr, cv2.COLORMAP_JET)
            if self.cfg.use_colormap
            else cv2.cvtColor(ir_corr, cv2.COLOR_GRAY2BGR)
        )
        for record in records:
            color = (0, 0, 255) if record["is_hot"] else (0, 255, 0)
            draw_box(rgb_display, record["box"], f"{record['obj_type']} {record['conf']:.2f}", color)
            draw_box(ir_display, record["box"], "", color)
        for box, text, color in overlays:
            draw_box(ir_display, box, text, color)
        blend = cv2.addWeighted(rgb_display, self.cfg.rgb_alpha, ir_display, 1 - self.cfg.rgb_alpha, 0)
        panels = []
        for image, title in (
            (rgb_display, "RGB + YOLO"),
            (ir_display, "COLOR IR CORRECTED"),
            (blend, "RGB + IR BLEND"),
        ):
            h, w = image.shape[:2]
            resized = cv2.resize(image, (int(w * self.cfg.show_height / h), self.cfg.show_height))
            cv2.putText(resized, title, (15, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2, cv2.LINE_AA)
            panels.append(resized)
        panel = np.hstack(panels)
        cv2.putText(
            panel,
            info_text,
            (20, panel.shape[0] - 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.58,
            (0, 255, 0),
            2,
            cv2.LINE_AA,
        )
        cv2.imshow(self.window_name, panel)
