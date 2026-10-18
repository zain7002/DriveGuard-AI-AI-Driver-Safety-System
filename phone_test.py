import sys
import types
import time

# Bypass broken torchvision::nms C++ operator by routing to Ultralytics' native TorchNMS.nms
try:
    from ultralytics.utils.nms import TorchNMS
    _tv = types.ModuleType('torchvision')
    _tv_ops = types.ModuleType('torchvision.ops')
    _tv_ops.nms = TorchNMS.nms
    _tv.ops = _tv_ops
    sys.modules['torchvision'] = _tv
    sys.modules['torchvision.ops'] = _tv_ops
except Exception:
    pass

from ultralytics import YOLO
import cv2

# Load YOLO model
print("Loading YOLO model...")
model = YOLO("yolo11n.pt")
print("YOLO model loaded successfully.")


def main():
    # Open camera
    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        print("❌ Camera not detected")
        return

    # Set optimal 640x480 resolution for high speed & responsiveness
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    print("\n" + "=" * 50)
    print("✅ YOLO Phone Detection Active!")
    print("Sensitivity: conf >= 0.20 (Classes: cell phone, remote)")
    print("Press 'Q' on the video window to exit.")
    print("=" * 50 + "\n")

    prev_time = time.time()
    last_print_time = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # Mirror camera
        frame = cv2.flip(frame, 1)

        curr_time = time.time()
        fps = 1.0 / max(0.001, (curr_time - prev_time))
        prev_time = curr_time

        # YOLO detection with sensitive confidence threshold
        results = model(frame, conf=0.15, verbose=False)

        phone_detected = False
        detected_objects = []

        # Process detections
        for result in results:
            if result.boxes is None:
                continue

            for box in result.boxes:
                class_id = int(box.cls[0])
                class_name = model.names[class_id]
                confidence = float(box.conf[0])
                detected_objects.append(f"{class_name} ({confidence:.2f})")

                x1, y1, x2, y2 = map(int, box.xyxy[0])

                # Check if phone or handheld device
                is_phone = (
                    class_id in [67, 65]
                    or "phone" in class_name.lower()
                    or "cell" in class_name.lower()
                    or "remote" in class_name.lower()
                )

                if is_phone and confidence >= 0.20:
                    phone_detected = True

                    # Glowing Red/Crimson Box for Phone
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 3)

                    label = f"📱 PHONE {confidence * 100:.0f}%"
                    cv2.rectangle(
                        frame,
                        (x1, max(0, y1 - 26)),
                        (x1 + 160, y1),
                        (0, 0, 255),
                        -1
                    )
                    cv2.putText(
                        frame,
                        label,
                        (x1 + 6, y1 - 7),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.6,
                        (255, 255, 255),
                        2
                    )

                elif confidence >= 0.35 and class_name.lower() != "person":
                    # Draw other detected objects in subtle cyan so user sees AI tracking
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 200, 0), 1)
                    cv2.putText(
                        frame,
                        f"{class_name} {confidence:.2f}",
                        (x1, max(15, y1 - 5)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.45,
                        (255, 200, 0),
                        1
                    )

        # Print detection status periodically to terminal
        if curr_time - last_print_time >= 1.0:
            last_print_time = curr_time
            if phone_detected:
                print(f"[{time.strftime('%H:%M:%S')}] 🚨 PHONE DETECTED! Objects in view: {', '.join(detected_objects)}")
            elif detected_objects:
                print(f"[{time.strftime('%H:%M:%S')}] Watching... Detected: {', '.join(detected_objects[:4])}")

        # Top HUD Status Bar
        if phone_detected:
            # Flashing Alert Banner
            cv2.rectangle(frame, (0, 0), (frame.shape[1], 55), (0, 0, 200), -1)
            cv2.putText(
                frame,
                "⚠️ ALERT: PHONE DETECTED IN DRIVER HAND!",
                (20, 38),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.75,
                (255, 255, 255),
                2
            )
        else:
            cv2.rectangle(frame, (0, 0), (frame.shape[1], 45), (20, 25, 30), -1)
            cv2.putText(
                frame,
                f"STATUS: NORMAL (NO PHONE) • FPS: {fps:.1f}",
                (20, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 120),
                2
            )

        cv2.imshow("YOLO Phone Detection — Diagnostic Test", frame)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()
    print("\nCamera closed. Diagnostic test ended.")


if __name__ == "__main__":
    main()