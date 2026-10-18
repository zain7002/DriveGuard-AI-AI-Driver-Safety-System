import sys
import types
from unittest.mock import MagicMock

# Bypass Windows Application Control DLL block on matplotlib inside mediapipe
sys.modules['matplotlib'] = MagicMock()
sys.modules['matplotlib.pyplot'] = MagicMock()

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

import cv2
import mediapipe as mp
import math
import time
import threading
import queue
import pyttsx3
import winsound

# Robust MediaPipe Solutions import for all mediapipe versions
mp_face_mesh = None

try:
    import mediapipe.solutions.face_mesh as mp_face_mesh
except Exception:
    pass

if mp_face_mesh is None:
    try:
        from mediapipe.python.solutions import face_mesh as mp_face_mesh
    except Exception:
        pass

if mp_face_mesh is None:
    try:
        import mediapipe as mp
        mp_face_mesh = getattr(mp, 'solutions', None)
        if mp_face_mesh is not None:
            mp_face_mesh = mp_face_mesh.face_mesh
    except Exception:
        pass

from collections import deque

try:
    from ultralytics import YOLO
    HAS_YOLO = True
except Exception as e:
    print(f"[WARNING] YOLO/PyTorch import bypassed ({e}). All other AI monitoring features active.")
    YOLO = None
    HAS_YOLO = False


class DriverMonitor:

    # ============================================================
    # FACE LANDMARKS
    # ============================================================

    LEFT_EYE = [362, 385, 387, 263, 373, 380]
    RIGHT_EYE = [33, 160, 158, 133, 153, 144]

    UPPER_LIP = 13
    LOWER_LIP = 14

    MOUTH_LEFT = 78
    MOUTH_RIGHT = 308

    NOSE_TIP = 1
    LEFT_FACE = 234
    RIGHT_FACE = 454

    # ============================================================
    # SETTINGS
    # ============================================================

    # Drowsiness
    EAR_THRESHOLD = 0.21
    DROWSY_TIME = 2.0

    # Yawning
    YAWN_THRESHOLD = 0.30
    YAWN_TIME = 2.0
    YAWN_MIN_WIDTH = 0.16
    YAWN_COOLDOWN = 5.0

    # Smoothing
    SMOOTHING_FRAMES = 7

    # Phone Detection Settings
    PHONE_CONFIDENCE = 0.20          # High-sensitivity threshold for indoor webcam & handheld phones
    PHONE_CONFIRM_FRAMES = 1         # Detect immediately without multi-frame lag
    PHONE_LOST_FRAMES = 5

    # Distraction
    DISTRACTION_TIME = 1.5
    DISTRACTION_CENTER_TIME = 0.5

    LEFT_THRESHOLD = 0.38
    RIGHT_THRESHOLD = 0.62

    # Driving Duration & Rest Break Settings (Seconds)
    # Advisory break recommended after 2 hours (7200s), Critical rest break required after 2.5 hours (9000s)
    BREAK_ADVISORY_SECONDS = 7200
    BREAK_CRITICAL_SECONDS = 9000
    AUTO_BREAK_ABSENT_SECONDS = 300  # 5 mins no face = auto rest break

    # ============================================================
    # INITIALIZATION
    # ============================================================

    def __init__(self):

        print("Initializing AI Driver Monitor...")

        # --------------------------------------------------------
        # MediaPipe
        # --------------------------------------------------------

        if mp_face_mesh is None:
            raise RuntimeError(
                "MediaPipe solutions could not be loaded from your installed 'mediapipe' package.\n"
                "Please reinstall MediaPipe by running:\n\n"
                "    pip install --upgrade --force-reinstall mediapipe==0.10.9\n"
            )

        self.mp_face_mesh = mp_face_mesh

        self.face_mesh = self.mp_face_mesh.FaceMesh(
            static_image_mode=False,
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )

        # --------------------------------------------------------
        # YOLO
        # --------------------------------------------------------

        if HAS_YOLO and YOLO is not None:
            print("Loading YOLO model...")
            try:
                self.model = YOLO("yolo11n.pt")
                print("YOLO model loaded successfully.")
            except Exception as e:
                print("YOLO loading error:", e)
                self.model = None
        else:
            print("[INFO] YOLO model disabled (PyTorch DLL blocked by OS). Other AI modules active.")
            self.model = None

        # --------------------------------------------------------
        # Alert Queue
        # --------------------------------------------------------

        self.alert_queue = queue.Queue()

        self.alert_worker = threading.Thread(
            target=self.alert_worker_function,
            daemon=True
        )

        self.alert_worker.start()

        # --------------------------------------------------------
        # Session
        # --------------------------------------------------------

        self.reset_session()

        print("AI Driver Monitor Ready.")

    # ============================================================
    # RESET SESSION
    # ============================================================

    def reset_session(self):

        # --------------------------------------------------------
        # Counters
        # --------------------------------------------------------

        self.drowsiness_count = 0
        self.yawn_count = 0
        self.phone_count = 0
        self.distraction_count = 0

        self.total_alerts = 0

        # --------------------------------------------------------
        # Alert History
        # --------------------------------------------------------

        self.alert_history = []

        # --------------------------------------------------------
        # Drowsiness State
        # --------------------------------------------------------

        self.eyes_closed_start = None

        self.drowsiness_condition = False
        self.drowsiness_alerted = False

        # --------------------------------------------------------
        # Yawning State
        # --------------------------------------------------------

        self.yawn_start = None

        self.yawning_condition = False
        self.yawn_alerted = False

        self.last_yawn_alert_time = 0

        # --------------------------------------------------------
        # Phone State
        # --------------------------------------------------------

        self.phone_detected = False
        self.phone_alerted = False

        self.phone_confirm_counter = 0
        self.phone_lost_counter = 0

        # --------------------------------------------------------
        # Distraction State
        # --------------------------------------------------------

        self.distraction_start = None
        self.distraction_condition = False
        self.distraction_alerted = False

        self.center_start = None

        self.last_attention = "CENTER"

        self.current_ear = 0.0
        self.current_mouth_ratio = 0.0
        self.current_mouth_width = 0.0
        self.current_drowsy = False
        self.current_yawning = False
        self.current_phone = False
        self.current_distraction = False
        self.current_attention = "CENTER"

        # --------------------------------------------------------
        # Driver Profile State
        # --------------------------------------------------------
        self.current_driver = {
            "id": 1,
            "driver_code": "DRV-101",
            "name": "Alex Johnson",
            "vehicle_reg": "TRK-904",
            "safety_score": 98
        }

        # --------------------------------------------------------
        # Driving Duration & Rest Break State
        # --------------------------------------------------------
        self.session_start_time = time.time()
        self.drive_start_time = time.time()
        self.last_break_time = time.time()
        self.break_advisory_alerted = False
        self.break_critical_alerted = False
        self.last_face_seen_time = time.time()

        # --------------------------------------------------------
        # Smoothing
        # --------------------------------------------------------

        self.ear_history = deque(
            maxlen=self.SMOOTHING_FRAMES
        )

        self.mouth_history = deque(
            maxlen=self.SMOOTHING_FRAMES
        )

        self.mouth_width_history = deque(
            maxlen=self.SMOOTHING_FRAMES
        )

        self.head_position_history = deque(
            maxlen=self.SMOOTHING_FRAMES
        )

    # ============================================================
    # REST BREAK MANAGEMENT
    # ============================================================

    def log_rest_break(self):
        """Reset continuous driving timer when driver takes a rest break."""
        now = time.time()
        self.drive_start_time = now
        self.last_break_time = now
        self.break_advisory_alerted = False
        self.break_critical_alerted = False
        print(f"[{time.strftime('%H:%M:%S')}] Rest break logged. Continuous driving timer reset.")
        return True

    # ============================================================
    # DRIVER PROFILE & SAFETY SCORE
    # ============================================================

    def set_driver(self, driver_info):
        """Set the active driver profile for monitoring session."""
        if driver_info:
            self.current_driver = driver_info
            print(f"[{time.strftime('%H:%M:%S')}] Active driver set: {driver_info.get('name')} ({driver_info.get('driver_code')})")

    def calculate_safety_score(self):
        """Calculate live driver safety score (0 - 100%) with focused driving recovery bonus."""
        now = time.time()

        # Check if driver is currently focused & clean
        is_clean_focused = (
            self.face_detected and
            not self.current_drowsy and
            not self.current_yawning and
            not self.current_phone and
            not self.current_distraction
        )

        if is_clean_focused:
            if not hasattr(self, 'last_focused_start') or self.last_focused_start is None:
                self.last_focused_start = now
            time_focused = now - self.last_focused_start
            # Gain +1 point back for every 15 seconds of clean attentive driving
            recovery_points = int(time_focused / 15.0)
        else:
            self.last_focused_start = now
            recovery_points = 0

        # Balanced, realistic deductions
        deductions = (
            (self.drowsiness_count * 3) +
            (self.yawn_count * 1) +
            (self.phone_count * 3) +
            (self.distraction_count * 1)
        )

        base_score = 100 - deductions
        final_score = max(0, min(100, base_score + recovery_points))

        if final_score >= 90:
            grade = "A"
        elif final_score >= 80:
            grade = "B"
        elif final_score >= 65:
            grade = "C"
        else:
            grade = "F"

        return final_score, grade

        # --------------------------------------------------------
        # Current Frame Status
        # --------------------------------------------------------

        self.face_detected = False

        self.current_drowsy = False
        self.current_yawning = False
        self.current_phone = False
        self.current_distraction = False

        self.current_attention = "CENTER"

        self.current_ear = 0.0
        self.current_mouth_ratio = 0.0
        self.current_mouth_width = 0.0

    # ============================================================
    # ALERT QUEUE
    # ============================================================

    def queue_alert(self, message):

        self.alert_queue.put(message)

    # ============================================================
    # ALERT WORKER
    # ============================================================

    def alert_worker_function(self):

        while True:

            message = self.alert_queue.get()

            try:

                # Buzzer
                self.buzzer()

                # Voice
                self.speak_message(message)

            except Exception as e:

                print("Alert error:", e)

            finally:

                self.alert_queue.task_done()

    # ============================================================
    # BUZZER
    # ============================================================

    def buzzer(self):

        try:

            for _ in range(3):

                winsound.Beep(
                    1000,
                    220
                )

                time.sleep(0.08)

        except Exception as e:

            print("Buzzer error:", e)

    # ============================================================
    # VOICE ALERT
    # ============================================================

    def speak_message(self, message):

        try:

            engine = pyttsx3.init()

            engine.setProperty(
                "rate",
                165
            )

            engine.setProperty(
                "volume",
                1.0
            )

            engine.say(message)

            engine.runAndWait()

            engine.stop()

        except Exception as e:

            print("Voice error:", e)

    # ============================================================
    # ADD ALERT
    # ============================================================

    def add_alert(self, alert_type, message):

        self.total_alerts += 1

        timestamp = time.strftime(
            "%H:%M:%S"
        )

        alert_data = {
            "timestamp": timestamp,
            "type": alert_type,
            "message": message
        }

        self.alert_history.append(
            alert_data
        )

        print(
            f"[{timestamp}] "
            f"{alert_type}: {message}"
        )

        self.queue_alert(
            message
        )

    # ============================================================
    # DISTANCE
    # ============================================================

    def distance(self, p1, p2):

        return math.sqrt(
            (p1[0] - p2[0]) ** 2 +
            (p1[1] - p2[1]) ** 2
        )

    # ============================================================
    # EAR CALCULATION
    # ============================================================

    def calculate_ear(
        self,
        landmarks,
        eye_points
    ):

        p1 = landmarks[eye_points[0]]
        p2 = landmarks[eye_points[1]]
        p3 = landmarks[eye_points[2]]
        p4 = landmarks[eye_points[3]]
        p5 = landmarks[eye_points[4]]
        p6 = landmarks[eye_points[5]]

        vertical_1 = self.distance(
            (p2.x, p2.y),
            (p6.x, p6.y)
        )

        vertical_2 = self.distance(
            (p3.x, p3.y),
            (p5.x, p5.y)
        )

        horizontal = self.distance(
            (p1.x, p1.y),
            (p4.x, p4.y)
        )

        if horizontal == 0:

            return 0

        return (
            vertical_1 +
            vertical_2
        ) / (2.0 * horizontal)

    # ============================================================
    # MOUTH RATIO
    # ============================================================

    def calculate_mouth_ratio(
        self,
        landmarks
    ):

        upper = landmarks[
            self.UPPER_LIP
        ]

        lower = landmarks[
            self.LOWER_LIP
        ]

        left = landmarks[
            self.MOUTH_LEFT
        ]

        right = landmarks[
            self.MOUTH_RIGHT
        ]

        vertical = self.distance(
            (upper.x, upper.y),
            (lower.x, lower.y)
        )

        horizontal = self.distance(
            (left.x, left.y),
            (right.x, right.y)
        )

        if horizontal == 0:

            return 0

        return vertical / horizontal

    # ============================================================
    # MOUTH WIDTH
    # ============================================================

    def calculate_mouth_width_ratio(
        self,
        landmarks
    ):

        left = landmarks[
            self.MOUTH_LEFT
        ]

        right = landmarks[
            self.MOUTH_RIGHT
        ]

        face_left = landmarks[
            self.LEFT_FACE
        ]

        face_right = landmarks[
            self.RIGHT_FACE
        ]

        mouth_width = self.distance(
            (left.x, left.y),
            (right.x, right.y)
        )

        face_width = self.distance(
            (face_left.x, face_left.y),
            (face_right.x, face_right.y)
        )

        if face_width == 0:

            return 0

        return mouth_width / face_width

    # ============================================================
    # HEAD POSITION
    # ============================================================

    def calculate_head_position(
        self,
        landmarks
    ):

        nose = landmarks[
            self.NOSE_TIP
        ]

        left_face = landmarks[
            self.LEFT_FACE
        ]

        right_face = landmarks[
            self.RIGHT_FACE
        ]

        face_width = (
            right_face.x -
            left_face.x
        )

        if face_width == 0:

            return "CENTER"

        normalized_x = (
            nose.x -
            left_face.x
        ) / face_width

        if normalized_x < self.LEFT_THRESHOLD:

            return "LEFT"

        if normalized_x > self.RIGHT_THRESHOLD:

            return "RIGHT"

        return "CENTER"

    # ============================================================
    # DRAW FACE POINTS
    # ============================================================

    def draw_light_face_points(
        self,
        frame,
        landmarks
    ):

        height, width, _ = frame.shape

        points = [
            self.NOSE_TIP,
            self.UPPER_LIP,
            self.LOWER_LIP,
            self.MOUTH_LEFT,
            self.MOUTH_RIGHT,
            self.LEFT_FACE,
            self.RIGHT_FACE,
            self.LEFT_EYE[0],
            self.RIGHT_EYE[0]
        ]

        for index in points:

            point = landmarks[index]

            x = int(
                point.x * width
            )

            y = int(
                point.y * height
            )

            cv2.circle(
                frame,
                (x, y),
                2,
                (0, 255, 0),
                -1
            )

    # ============================================================
    # PROCESS FRAME
    # ============================================================

    def process_frame(self, frame, draw_overlay=True):

        # Mirror camera
        frame = cv2.flip(
            frame,
            1
        )

        # --------------------------------------------------------
        # MediaPipe
        # --------------------------------------------------------

        rgb_frame = cv2.cvtColor(
            frame,
            cv2.COLOR_BGR2RGB
        )

        results = self.face_mesh.process(
            rgb_frame
        )

        # --------------------------------------------------------
        # Reset current status
        # --------------------------------------------------------

        self.face_detected = False

        self.current_drowsy = False
        self.current_yawning = False
        self.current_phone = False
        self.current_distraction = False

        self.current_attention = "CENTER"

        # ========================================================
        # FACE DETECTION
        # ========================================================

        if results.multi_face_landmarks:

            self.face_detected = True

            landmarks = (
                results
                .multi_face_landmarks[0]
                .landmark
            )

            # ----------------------------------------------------
            # Draw tiny landmark points
            # ----------------------------------------------------

            self.draw_light_face_points(
                frame,
                landmarks
            )

            # ====================================================
            # EYE / EAR
            # ====================================================

            left_ear = self.calculate_ear(
                landmarks,
                self.LEFT_EYE
            )

            right_ear = self.calculate_ear(
                landmarks,
                self.RIGHT_EYE
            )

            ear = (
                left_ear +
                right_ear
            ) / 2.0

            self.ear_history.append(
                ear
            )

            smooth_ear = (
                sum(self.ear_history) /
                len(self.ear_history)
            )

            self.current_ear = smooth_ear

            # ====================================================
            # MOUTH
            # ====================================================

            mouth_ratio = (
                self.calculate_mouth_ratio(
                    landmarks
                )
            )

            mouth_width = (
                self.calculate_mouth_width_ratio(
                    landmarks
                )
            )

            self.mouth_history.append(
                mouth_ratio
            )

            self.mouth_width_history.append(
                mouth_width
            )

            smooth_mouth = (
                sum(self.mouth_history) /
                len(self.mouth_history)
            )

            smooth_mouth_width = (
                sum(self.mouth_width_history) /
                len(self.mouth_width_history)
            )

            self.current_mouth_ratio = (
                smooth_mouth
            )

            self.current_mouth_width = (
                smooth_mouth_width
            )

            # ====================================================
            # DROWSINESS
            # ====================================================

            if smooth_ear < self.EAR_THRESHOLD:

                self.current_drowsy = True

                if self.eyes_closed_start is None:

                    self.eyes_closed_start = (
                        time.time()
                    )

                closed_time = (
                    time.time() -
                    self.eyes_closed_start
                )

                if (
                    closed_time >=
                    self.DROWSY_TIME
                    and
                    not self.drowsiness_alerted
                ):

                    self.drowsiness_condition = True

                    self.drowsiness_alerted = True

                    self.drowsiness_count += 1

                    self.add_alert(
                        "DROWSINESS",
                        "Warning! Driver appears drowsy. Please stay alert."
                    )

            else:

                self.current_drowsy = False

                self.eyes_closed_start = None

                # New episode can trigger again
                self.drowsiness_condition = False
                self.drowsiness_alerted = False

            # ====================================================
            # YAWNING
            # ====================================================

            yawn_condition = (
                smooth_mouth >=
                self.YAWN_THRESHOLD
                and
                smooth_mouth_width >=
                self.YAWN_MIN_WIDTH
            )

            if yawn_condition:

                self.current_yawning = True

                if self.yawn_start is None:

                    self.yawn_start = (
                        time.time()
                    )

                yawn_time = (
                    time.time() -
                    self.yawn_start
                )

                if (
                    yawn_time >=
                    self.YAWN_TIME
                    and
                    not self.yawn_alerted
                ):

                    now = time.time()

                    if (
                        now -
                        self.last_yawn_alert_time
                        >=
                        self.YAWN_COOLDOWN
                    ):

                        self.yawning_condition = True

                        self.yawn_alerted = True

                        self.last_yawn_alert_time = now

                        self.yawn_count += 1

                        self.add_alert(
                            "YAWNING",
                            "Warning! Driver is yawning. Please stay alert."
                        )

            else:

                self.current_yawning = False

                self.yawn_start = None

                # New yawn can trigger again
                self.yawning_condition = False
                self.yawn_alerted = False

            # ====================================================
            # HEAD POSITION
            # ====================================================

            head_position = (
                self.calculate_head_position(
                    landmarks
                )
            )

            self.head_position_history.append(
                head_position
            )

            positions = list(
                self.head_position_history
            )

            if positions:

                center_count = (
                    positions.count("CENTER")
                )

                left_count = (
                    positions.count("LEFT")
                )

                right_count = (
                    positions.count("RIGHT")
                )

                if (
                    left_count > center_count
                    and
                    left_count >= right_count
                ):

                    stable_position = "LEFT"

                elif (
                    right_count > center_count
                    and
                    right_count > left_count
                ):

                    stable_position = "RIGHT"

                else:

                    stable_position = "CENTER"

            else:

                stable_position = "CENTER"

            self.current_attention = (
                stable_position
            )

            # ====================================================
            # DISTRACTION
            # ====================================================

            if stable_position != "CENTER":

                self.current_distraction = True

                self.center_start = None

                if self.distraction_start is None:

                    self.distraction_start = (
                        time.time()
                    )

                distraction_time = (
                    time.time() -
                    self.distraction_start
                )

                if (
                    distraction_time >=
                    self.DISTRACTION_TIME
                    and
                    not self.distraction_alerted
                ):

                    self.distraction_condition = True

                    self.distraction_alerted = True

                    self.distraction_count += 1

                    direction = (
                        stable_position.lower()
                    )

                    self.add_alert(
                        "DISTRACTION",
                        f"Warning! Please look at the road. You are looking {direction}."
                    )

            else:

                self.current_distraction = False

                self.distraction_start = None

                if self.center_start is None:

                    self.center_start = (
                        time.time()
                    )

                center_time = (
                    time.time() -
                    self.center_start
                )

                # Driver has looked forward again
                if (
                    center_time >=
                    self.DISTRACTION_CENTER_TIME
                ):

                    self.distraction_condition = False

                    self.distraction_alerted = False

            self.last_attention = (
                stable_position
            )

        # ========================================================
        # NO FACE
        # ========================================================

        else:

            self.current_attention = (
                "NO FACE"
            )

            self.current_drowsy = False
            self.current_yawning = False
            self.current_distraction = False

        # ========================================================
        # YOLO PHONE DETECTION
        # ========================================================

        if self.model is not None:

            try:

                # Run YOLO with sensitive confidence threshold
                yolo_results = self.model(
                    frame,
                    conf=0.15,
                    verbose=False
                )

                phone_found = False
                best_phone_conf = 0.0

                # ------------------------------------------------
                # Process YOLO detections
                # ------------------------------------------------

                for result in yolo_results:

                    if result.boxes is None:

                        continue

                    for box in result.boxes:

                        confidence = float(
                            box.conf[0]
                        )

                        class_id = int(
                            box.cls[0]
                        )

                        class_name = (
                            self.model.names[
                                class_id
                            ]
                        )

                        # Match cell phone (67), remote (65), or any phone/cellular/remote label
                        is_phone = (
                            class_id in [67, 65]
                            or "phone" in class_name.lower()
                            or "cell" in class_name.lower()
                            or "remote" in class_name.lower()
                        )

                        if is_phone and confidence >= self.PHONE_CONFIDENCE:

                            phone_found = True
                            if confidence > best_phone_conf:
                                best_phone_conf = confidence

                            x1, y1, x2, y2 = map(
                                int,
                                box.xyxy[0]
                            )

                            # Draw glowing red phone bounding box
                            cv2.rectangle(
                                frame,
                                (x1, y1),
                                (x2, y2),
                                (0, 0, 255),
                                3
                            )

                            label = f"PHONE {confidence:.2f}"
                            cv2.rectangle(
                                frame,
                                (x1, max(0, y1 - 25)),
                                (x1 + 130, y1),
                                (0, 0, 255),
                                -1
                            )
                            cv2.putText(
                                frame,
                                label,
                                (x1 + 5, y1 - 7),
                                cv2.FONT_HERSHEY_SIMPLEX,
                                0.55,
                                (255, 255, 255),
                                2
                            )

                # =================================================
                # PHONE CONFIRMATION & SMOOTHING
                # =================================================

                if phone_found:

                    self.phone_confirm_counter += 1
                    self.phone_lost_counter = 0
                    self.current_phone = True

                    if (
                        self.phone_confirm_counter
                        >=
                        self.PHONE_CONFIRM_FRAMES
                    ):

                        self.phone_detected = True

                        if not self.phone_alerted:

                            self.phone_alerted = True
                            self.phone_count += 1

                            print(f"[{time.strftime('%H:%M:%S')}] 🚨 PHONE DETECTED! (Confidence: {best_phone_conf:.2f})")

                            self.add_alert(
                                "PHONE",
                                "Warning! Please do not use your phone while driving."
                            )

                else:

                    self.phone_lost_counter += 1
                    self.phone_confirm_counter = 0

                    if (
                        self.phone_lost_counter
                        >=
                        self.PHONE_LOST_FRAMES
                    ):

                        self.phone_detected = False
                        self.phone_alerted = False
                        self.current_phone = False

                    else:
                        # Smooth transition: keep current_phone True while brief drop occurs
                        self.current_phone = self.phone_detected

            except Exception as e:

                print(
                    "YOLO error:",
                    e
                )

        # ========================================================
        # DRAW DASHBOARD
        # ========================================================

        if draw_overlay:
            self.draw_dashboard(
                frame
            )

        return frame

    # ============================================================
    # DASHBOARD
    # ============================================================

    def draw_dashboard(
        self,
        frame
    ):

        height, width, _ = frame.shape

        # ========================================================
        # TOP BAR
        # ========================================================

        cv2.rectangle(
            frame,
            (0, 0),
            (width, 95),
            (25, 25, 25),
            -1
        )

        cv2.putText(
            frame,
            "AI DRIVER MONITOR",
            (25, 35),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.0,
            (255, 255, 255),
            2
        )

        # Face
        if self.face_detected:

            face_text = (
                "FACE: DETECTED"
            )

        else:

            face_text = (
                "FACE: NOT DETECTED"
            )

        cv2.putText(
            frame,
            face_text,
            (25, 72),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (255, 255, 255),
            2
        )

        # Attention
        cv2.putText(
            frame,
            f"ATTENTION: {self.current_attention}",
            (width - 360, 35),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (255, 255, 255),
            2
        )

        # Total alerts
        cv2.putText(
            frame,
            f"TOTAL ALERTS: {self.total_alerts}",
            (width - 360, 72),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (255, 255, 255),
            2
        )

        # ========================================================
        # LIVE STATUS PANEL
        # ========================================================

        x1 = 20
        y1 = 115
        x2 = 380
        y2 = 360

        cv2.rectangle(
            frame,
            (x1, y1),
            (x2, y2),
            (30, 30, 30),
            -1
        )

        cv2.putText(
            frame,
            "LIVE STATUS",
            (35, 145),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2
        )

        cv2.putText(
            frame,
            f"EAR: {self.current_ear:.3f}",
            (35, 180),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (255, 255, 255),
            1
        )

        cv2.putText(
            frame,
            f"Mouth Ratio: {self.current_mouth_ratio:.3f}",
            (35, 210),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (255, 255, 255),
            1
        )

        cv2.putText(
            frame,
            f"Mouth Width: {self.current_mouth_width:.3f}",
            (35, 240),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (255, 255, 255),
            1
        )

        drowsy = (
            "YES"
            if self.current_drowsy
            else "NO"
        )

        cv2.putText(
            frame,
            f"Drowsiness: {drowsy}",
            (35, 275),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (255, 255, 255),
            1
        )

        yawning = (
            "YES"
            if self.current_yawning
            else "NO"
        )

        cv2.putText(
            frame,
            f"Yawning: {yawning}",
            (35, 305),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (255, 255, 255),
            1
        )

        phone = (
            "YES"
            if self.current_phone
            else "NO"
        )

        cv2.putText(
            frame,
            f"Phone: {phone}",
            (35, 335),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (255, 255, 255),
            1
        )

        # ========================================================
        # EVENT COUNTERS
        # ========================================================

        counter_x = width - 300
        counter_y = 130

        cv2.rectangle(
            frame,
            (counter_x - 15, counter_y - 25),
            (width - 15, 315),
            (30, 30, 30),
            -1
        )

        cv2.putText(
            frame,
            "EVENT COUNTERS",
            (counter_x, counter_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (255, 255, 255),
            2
        )

        cv2.putText(
            frame,
            f"Drowsiness : {self.drowsiness_count}",
            (counter_x, counter_y + 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (255, 255, 255),
            1
        )

        cv2.putText(
            frame,
            f"Yawning     : {self.yawn_count}",
            (counter_x, counter_y + 75),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (255, 255, 255),
            1
        )

        cv2.putText(
            frame,
            f"Phone       : {self.phone_count}",
            (counter_x, counter_y + 110),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (255, 255, 255),
            1
        )

        cv2.putText(
            frame,
            f"Distraction : {self.distraction_count}",
            (counter_x, counter_y + 145),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (255, 255, 255),
            1
        )

        # ========================================================
        # WARNING AREA
        # ========================================================

        warnings = []

        if self.current_drowsy:

            warnings.append(
                "DROWSINESS DETECTED"
            )

        if self.current_yawning:

            warnings.append(
                "YAWNING DETECTED"
            )

        if self.current_phone:

            warnings.append(
                "PHONE DETECTED"
            )

        if self.current_distraction:

            warnings.append(
                f"DISTRACTION: {self.current_attention}"
            )

        warning_y = height - 105

        for warning in warnings:

            cv2.rectangle(
                frame,
                (20, warning_y - 30),
                (520, warning_y + 5),
                (40, 40, 40),
                -1
            )

            cv2.putText(
                frame,
                warning,
                (30, warning_y - 7),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (255, 255, 255),
                2
            )

            warning_y += 40

        # ========================================================
        # CONTROLS
        # ========================================================

        cv2.putText(
            frame,
            "Q: Quit    R: Reset Session",
            (20, height - 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (255, 255, 255),
            1
        )

    # ============================================================
    # DASHBOARD DATA
    # ============================================================

    def get_dashboard_data(self):
        # Calculate distraction glance duration
        distraction_duration = 0.0
        if self.distraction_start is not None:
            distraction_duration = round(time.time() - self.distraction_start, 1)

        # Context-Aware Mirror Check: Glance < 1.5s to LEFT or RIGHT
        is_mirror_check = False
        mirror_direction = None
        if self.current_attention in ["LEFT", "RIGHT"] and distraction_duration < self.DISTRACTION_TIME:
            is_mirror_check = True
            mirror_direction = self.current_attention

        # Driving Duration & Rest Break Calculations
        now = time.time()
        drive_seconds = max(0, int(now - self.drive_start_time))
        hours = drive_seconds // 3600
        minutes = (drive_seconds % 3600) // 60
        secs = drive_seconds % 60
        drive_duration_formatted = f"{hours:02d}h {minutes:02d}m {secs:02d}s"

        # Auto-break detection if driver was away > 5 mins
        if not self.face_detected:
            if now - self.last_face_seen_time > self.AUTO_BREAK_ABSENT_SECONDS:
                self.log_rest_break()

        # Trigger Break Alerts
        if drive_seconds >= self.BREAK_CRITICAL_SECONDS and not self.break_critical_alerted:
            self.break_critical_alerted = True
            self.add_alert(
                "BREAK_OVERDUE",
                "MANDATORY REST BREAK REQUIRED! You have driven over 2.5 hours continuously. Pull over safely."
            )
        elif drive_seconds >= self.BREAK_ADVISORY_SECONDS and not self.break_advisory_alerted:
            self.break_advisory_alerted = True
            self.add_alert(
                "BREAK_ADVISORY",
                "Rest Break Recommended Soon: You have been driving for 2 hours continuously."
            )

        # Break status
        if drive_seconds >= self.BREAK_CRITICAL_SECONDS:
            break_status = "OVERDUE"
        elif drive_seconds >= self.BREAK_ADVISORY_SECONDS:
            break_status = "ADVISORY"
        else:
            break_status = "OPTIMAL"

        break_progress_percent = min(100, int((drive_seconds / self.BREAK_ADVISORY_SECONDS) * 100))

        # Determine Graduated Alert Level & Stage
        # Stage 2: Critical (Active Alarm & Alert Logged)
        if self.drowsiness_alerted or self.yawn_alerted or self.phone_alerted or self.distraction_alerted or self.break_critical_alerted:
            alert_level = "CRITICAL"
            alert_stage = 2
        # Stage 1: Early Warning / Caution (Pre-alarm onset)
        elif self.current_drowsy or self.current_yawning or self.current_phone or self.break_advisory_alerted or (self.current_distraction and distraction_duration >= 1.0):
            alert_level = "WARNING"
            alert_stage = 1
        # Context-Aware Mirror Glance (Normal driving)
        elif is_mirror_check:
            alert_level = "MIRROR_CHECK"
            alert_stage = 0
        # Normal Focused State
        else:
            alert_level = "NORMAL"
            alert_stage = 0

        # Safety Score & Grade
        safety_score, safety_grade = self.calculate_safety_score()

        return {
            "face": self.face_detected,
            "drowsiness": self.current_drowsy,
            "yawning": self.current_yawning,
            "phone": self.current_phone,
            "attention": self.current_attention,
            "ear": self.current_ear,
            "mouth_ratio": self.current_mouth_ratio,
            "mouth_width": self.current_mouth_width,
            "total_alerts": self.total_alerts,
            "drowsiness_count": self.drowsiness_count,
            "yawn_count": self.yawn_count,
            "phone_count": self.phone_count,
            "distraction_count": self.distraction_count,
            "alerts": self.alert_history,
            "is_mirror_check": is_mirror_check,
            "mirror_direction": mirror_direction,
            "alert_level": alert_level,
            "alert_stage": alert_stage,
            "distraction_duration": distraction_duration,
            "drive_duration_seconds": drive_seconds,
            "drive_duration_formatted": drive_duration_formatted,
            "break_status": break_status,
            "break_progress_percent": break_progress_percent,
            "driver": self.current_driver,
            "safety_score": safety_score,
            "safety_grade": safety_grade
        }

    # ============================================================
    # STATISTICS
    # ============================================================

    def get_statistics(self):

        return {

            "Total Alerts":
                self.total_alerts,

            "Drowsiness Events":
                self.drowsiness_count,

            "Yawning Events":
                self.yawn_count,

            "Phone Events":
                self.phone_count,

            "Distraction Events":
                self.distraction_count
        }

    # ============================================================
    # RELEASE
    # ============================================================

    def release(self):

        try:

            self.face_mesh.close()

        except Exception:
            pass

        print("\nMonitoring stopped.")

        print("\nSession Statistics:")

        statistics = self.get_statistics()

        for key, value in statistics.items():

            print(
                f"{key}: {value}"
            )


# ================================================================
# CAMERA APPLICATION
# ================================================================

def run_camera():

    print()
    print("=" * 55)
    print("             AI DRIVER MONITOR")
    print("=" * 55)
    print("Q = Quit")
    print("R = Reset Session")
    print("=" * 55)
    print()

    # ------------------------------------------------------------
    # Create monitor
    # ------------------------------------------------------------

    monitor = DriverMonitor()

    # ------------------------------------------------------------
    # Open camera
    # ------------------------------------------------------------

    camera = cv2.VideoCapture(0)

    camera.set(
        cv2.CAP_PROP_FRAME_WIDTH,
        1280
    )

    camera.set(
        cv2.CAP_PROP_FRAME_HEIGHT,
        720
    )

    if not camera.isOpened():

        print(
            "ERROR: Could not open camera."
        )

        monitor.release()

        return

    print(
        "Camera started successfully."
    )

    # ============================================================
    # MAIN LOOP
    # ============================================================

    while True:

        ret, frame = camera.read()

        if not ret:

            print(
                "ERROR: Could not read camera frame."
            )

            break

        try:

            processed_frame = (
                monitor.process_frame(
                    frame
                )
            )

            cv2.imshow(
                "AI Driver Monitor",
                processed_frame
            )

        except Exception as e:

            print(
                "Frame processing error:",
                e
            )

        # --------------------------------------------------------
        # Keyboard
        # --------------------------------------------------------

        key = cv2.waitKey(1) & 0xFF

        # Q
        if key == ord("q"):

            break

        # R
        elif key == ord("r"):

            print(
                "\nSession reset."
            )

            monitor.reset_session()

    # ============================================================
    # CLEANUP
    # ============================================================

    camera.release()

    cv2.destroyAllWindows()

    monitor.release()


# ================================================================
# START PROGRAM
# ================================================================

if __name__ == "__main__":

    run_camera()