import queue
import threading
import time
import cv2
from calibration import Calibration
from capture import FrameBuffer, FRM13Camera, OpenCVRGBCamera, ir_capture_loop, rgb_capture_loop
from display import Display
from inference import InferenceWorker
from risk import SeatAnalyzer
from settings import Settings
from ultralytics import YOLO
from web_client import SeatPublisher


def main():
    cfg = Settings()
    stop_event = threading.Event()
    cam_ir = cam_rgb = None
    threads = []
    try:
        calib = Calibration(cfg)
        model = YOLO(str(cfg.base_dir / cfg.model_path), task="detect")
        cam_ir = FRM13Camera(cfg.base_dir / cfg.dll_path, cfg.ir_board)
        cam_ir.start()
        cam_rgb = OpenCVRGBCamera(cfg)
        ir_frames = FrameBuffer(cfg.frame_buf_size)
        rgb_frames = FrameBuffer(cfg.frame_buf_size)
        worker = InferenceWorker(model, cfg, stop_event)
        publisher = SeatPublisher(cfg, stop_event)
        threads = [
            threading.Thread(target=ir_capture_loop, args=(cam_ir, ir_frames, stop_event), daemon=True),
            threading.Thread(target=rgb_capture_loop, args=(cam_rgb, rgb_frames, stop_event), daemon=True),
            worker.thread,
            publisher.thread,
        ]
        for thread in threads:
            thread.start()
        analyzer = SeatAnalyzer(cfg)
        display = Display(cfg)
        cv2.namedWindow(display.window_name, cv2.WINDOW_NORMAL)
        records, statuses, overlays, crop_boxes = ([], {}, [], {})
        latest_rgb = latest_ir = None
        next_yolo_ts = next_send_ts = 0.0
        prev_time = time.monotonic()
        last_ir_ts = None
        while True:
            ir_ts, raw_ir = ir_frames.get_latest()
            if raw_ir is None or ir_ts == last_ir_ts:
                time.sleep(0.002)
                continue
            _, raw_rgb = rgb_frames.pop_closest_before(ir_ts - cfg.rgb_delay)
            if raw_rgb is None:
                time.sleep(0.002)
                continue
            last_ir_ts = ir_ts
            rgb, ir_corr = calib.align(raw_rgb, raw_ir)
            try:
                result = worker.results.get_nowait()
            except queue.Empty:
                pass
            else:
                if isinstance(result, Exception):
                    raise result
                dets, latest_rgb, latest_ir = result
                records, statuses, overlays, crop_boxes = analyzer.analyze(dets, latest_ir)
            now = time.monotonic()
            if now >= next_yolo_ts and worker.ready.is_set():
                worker.ready.clear()
                worker.frames.put_nowait((rgb, ir_corr))
                next_yolo_ts = now + 1.0 / cfg.yolo_fps
            if statuses and now >= next_send_ts and publisher.ready.is_set():
                crops = display.make_crops(latest_rgb, latest_ir, crop_boxes)
                snapshot = {
                    seat_id: {**info, "crop_image": crops.get(seat_id, "")}
                    for seat_id, info in statuses.items()
                }
                publisher.ready.clear()
                publisher.snapshot = snapshot
                publisher.pending.set()
                next_send_ts = now + cfg.send_interval
            fps = 1.0 / max(now - prev_time, 1e-06)
            prev_time = now
            flask_state = (
                "OK" if publisher.last_status is not None and 200 <= publisher.last_status < 300 else "WAIT"
            )
            text = f"FPS:{fps:.1f} | YOLO:{cfg.yolo_fps:.1f}fps | objects:{len(records)} | HOT:OBJ+IR{cfg.obj_hot_ir}+ | WARN:NOOBJ+IR{cfg.no_obj_warn_ir}+ | FLASK:{flask_state} | ESC:quit"
            display.show(rgb, ir_corr, records, overlays, text)
            if cv2.waitKey(1) & 255 == 27:
                break
    except KeyboardInterrupt:
        print("Stopped by user")
    finally:
        stop_event.set()
        for thread in threads:
            if thread.ident is not None:
                thread.join(timeout=2.0)
        if cam_ir is not None:
            cam_ir.release()
        if cam_rgb is not None:
            cam_rgb.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
