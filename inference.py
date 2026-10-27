import queue
import threading
import numpy as np


class InferenceWorker:
    def __init__(self, model, cfg, stop_event):
        self.model = model
        self.cfg = cfg
        self.stop_event = stop_event
        self.frames = queue.Queue(maxsize=1)
        self.results = queue.Queue(maxsize=1)
        self.ready = threading.Event()
        self.ready.set()
        self.thread = threading.Thread(target=self.run, daemon=True)

    def run(self):
        kwargs = {"conf": self.cfg.yolo_conf, "imgsz": self.cfg.yolo_imgsz, "verbose": False}
        if self.cfg.yolo_device:
            kwargs["device"] = self.cfg.yolo_device
        if self.cfg.yolo_classes is not None:
            kwargs["classes"] = self.cfg.yolo_classes
        keywords = {
            "battery": ("battery",),
            "handbag": ("handbag", "handback"),
            "backpack": ("backpack",),
            "chair": ("chair",),
        }
        while not self.stop_event.is_set():
            try:
                rgb, ir_corr = self.frames.get(timeout=0.1)
            except queue.Empty:
                continue
            try:
                h, w = rgb.shape[:2]
                result = self.model.predict(source=rgb, **kwargs)[0]
                dets = []
                if result.boxes is not None:
                    boxes = result.boxes
                    for coords, cls_id, conf in zip(
                        boxes.xyxy.cpu().numpy(), boxes.cls.int().cpu().tolist(), boxes.conf.cpu().tolist()
                    ):
                        label = self.model.names[cls_id]
                        obj_type = "other"
                        for name, aliases in keywords.items():
                            if any((alias in str(label).lower() for alias in aliases)):
                                obj_type = name
                                break
                        if obj_type == "other":
                            continue
                        x1, y1, x2, y2 = np.clip(coords, (0, 0, 0, 0), (w - 1, h - 1, w - 1, h - 1))
                        x1, x2 = sorted((float(x1), float(x2)))
                        y1, y2 = sorted((float(y1), float(y2)))
                        if (x2 - x1) * (y2 - y1) < self.cfg.min_box_area:
                            continue
                        dets.append(
                            {
                                "box": (x1, y1, x2, y2),
                                "label": label,
                                "obj_type": obj_type,
                                "conf": float(conf),
                            }
                        )
                value = (dets, rgb, ir_corr)
            except Exception as error:
                value = error
            finally:
                try:
                    self.results.get_nowait()
                except queue.Empty:
                    pass
                self.results.put_nowait(value)
                self.ready.set()
