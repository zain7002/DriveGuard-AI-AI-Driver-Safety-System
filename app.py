"""
DriveGuard AI — Flask Web Server
Serves the dashboard frontend and exposes the API endpoints.
Saves all data to MySQL database.

Endpoints:
    GET  /                       → Dashboard (index.html)
    GET  /video_feed             → MJPEG camera stream
    GET  /api/status             → Live JSON status data
    POST /api/reset              → Reset session counters
    GET  /api/history            → Past session list
    GET  /api/history/<id>       → Alerts for a specific session

Run:
    python app.py
"""

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
import threading
import time
import atexit
from flask import Flask, Response, jsonify, send_from_directory, request
from main import DriverMonitor
from database import Database

# ================================================================
# FLASK APP CONFIGURATION
# ================================================================

app = Flask(
    __name__,
    static_folder=".",      # Serve CSS/JS from the project root
    static_url_path=""
)

# ================================================================
# GLOBAL OBJECTS
# ================================================================

monitor = DriverMonitor()
db = Database()                # MySQL database connection
camera = None
camera_lock = threading.Lock()
latest_frame = None            # Stores the latest processed frame
frame_lock = threading.Lock()

# ── Session Tracking ──
current_session_id = None      # Active MySQL session ID
last_alert_count = 0           # Track new alerts for DB saving
last_bio_time = 0              # Last biometrics save timestamp

# ================================================================
# START A NEW DATABASE SESSION
# ================================================================

def start_db_session():
    """Start a new monitoring session in the database."""
    global current_session_id, last_alert_count
    current_session_id = db.start_session()
    last_alert_count = 0


def end_db_session():
    """End the current database session with final counters."""
    global current_session_id
    if current_session_id is not None:
        db.end_session(
            current_session_id,
            total_alerts=monitor.total_alerts,
            drowsiness_count=monitor.drowsiness_count,
            yawn_count=monitor.yawn_count,
            phone_count=monitor.phone_count,
            distraction_count=monitor.distraction_count
        )
        current_session_id = None


# ================================================================
# AUTO-SAVE: Alerts & Biometrics
# ================================================================

def auto_save_data():
    """
    Background thread that periodically:
    1. Checks for new alerts and saves them to MySQL
    2. Saves biometrics snapshots every 5 seconds
    """
    global last_alert_count, last_bio_time

    while True:
        try:
            if current_session_id is None:
                time.sleep(1)
                continue

            # ── Save New Alerts ──
            # Compare current alert count with last known count
            current_alerts = monitor.alert_history
            if len(current_alerts) > last_alert_count:
                # Save only the new alerts
                new_alerts = current_alerts[last_alert_count:]
                for alert in new_alerts:
                    db.save_alert(
                        current_session_id,
                        alert.get("type", "UNKNOWN"),
                        alert.get("message", "")
                    )
                last_alert_count = len(current_alerts)

            # ── Save Biometrics (every 5 seconds) ──
            now = time.time()
            if now - last_bio_time >= 5:
                db.save_biometrics(
                    current_session_id,
                    ear=monitor.current_ear,
                    mouth_ratio=monitor.current_mouth_ratio,
                    mouth_width=monitor.current_mouth_width,
                    attention=monitor.current_attention,
                    face_detected=monitor.face_detected
                )
                last_bio_time = now

        except Exception as e:
            print(f"Auto-save error: {e}")

        time.sleep(0.5)  # Check every 500ms


# ================================================================
# CAMERA CAPTURE THREAD
# ================================================================

def camera_thread():
    """
    Background thread that continuously reads frames from the camera,
    processes them through the DriverMonitor, and stores the latest
    processed frame for the MJPEG stream.
    """
    global camera, latest_frame

    camera = cv2.VideoCapture(0)

    if not camera.isOpened():
        print("ERROR: Cannot open camera!")
        return

    # Set camera resolution
    camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    print("Camera started successfully.")

    while True:
        with camera_lock:
            if camera is None or not camera.isOpened():
                break
            success, frame = camera.read()

        if not success:
            time.sleep(0.01)
            continue

        # Process the frame through DriverMonitor
        # (draw_overlay=False keeps the stream clean — the web UI shows status info)
        processed_frame = monitor.process_frame(frame, draw_overlay=False)

        # Store the processed frame for the MJPEG stream
        with frame_lock:
            latest_frame = processed_frame

    print("Camera thread stopped.")


# ================================================================
# MJPEG STREAM GENERATOR
# ================================================================

def generate_mjpeg():
    """
    Generator function that yields JPEG frames for the MJPEG stream.
    This is used by the /video_feed endpoint.
    """
    while True:
        with frame_lock:
            frame = latest_frame

        if frame is None:
            # No frame available yet — wait briefly
            time.sleep(0.03)
            continue

        # Encode the frame as JPEG
        success, buffer = cv2.imencode(
            ".jpg", frame,
            [cv2.IMWRITE_JPEG_QUALITY, 80]
        )

        if not success:
            continue

        # Yield the frame in MJPEG multipart format
        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" +
            buffer.tobytes() +
            b"\r\n"
        )

        # Small delay to control frame rate (~30 fps)
        time.sleep(0.033)


# ================================================================
# ROUTES — Live Dashboard & Login Portal
# ================================================================

@app.route("/")
@app.route("/login")
def login_page():
    """Serve the standalone login portal page."""
    return send_from_directory(".", "login.html")


@app.route("/dashboard")
def dashboard():
    """Serve the main live monitoring dashboard page."""
    return send_from_directory(".", "index.html")


@app.route("/presentation")
@app.route("/slides")
def presentation():
    """Serve the interactive presentation slides deck."""
    return send_from_directory(".", "presentation.html")


@app.route("/poster")
def poster():
    """Serve the high-resolution A3 exhibition poster."""
    return send_from_directory(".", "poster.html")


@app.route("/video_feed")
def video_feed():
    """
    MJPEG video stream endpoint.
    The frontend displays this using: <img src="/video_feed">
    """
    return Response(
        generate_mjpeg(),
        mimetype="multipart/x-mixed-replace; boundary=frame"
    )


@app.route("/api/status")
def api_status():
    """
    Returns the current monitoring status as JSON.
    Polled by the frontend every 500ms.
    """
    data = monitor.get_dashboard_data()

    # Convert face_detected boolean to human-readable text
    # (The frontend handles both boolean and string values)
    if isinstance(data.get("face"), bool):
        data["face"] = "FACE DETECTED" if data["face"] else "NO FACE"

    return jsonify(data)


@app.route("/api/reset", methods=["POST"])
def api_reset():
    """
    Resets the monitoring session — clears all counters and alerts.
    Ends the current DB session and starts a new one.
    """
    global last_alert_count

    # End current session in database
    end_db_session()

    # Reset the monitor
    monitor.reset_session()
    last_alert_count = 0

    # Start a fresh session in database
    start_db_session()

    return jsonify({
        "status": "ok",
        "message": "Session reset successfully"
    })


@app.route("/api/log_break", methods=["POST"])
def api_log_break():
    """
    Logs a rest break and resets the continuous driving timer.
    """
    monitor.log_rest_break()
    return jsonify({
        "status": "ok",
        "message": "Rest break logged successfully"
    })


# ================================================================
# ROUTES — Driver Profile & Authentication
# ================================================================

@app.route("/api/drivers", methods=["GET"])
def api_get_drivers():
    """Returns list of all registered drivers."""
    drivers = db.get_all_drivers()
    return jsonify({"success": True, "drivers": drivers})


@app.route("/api/driver/login", methods=["POST"])
def api_driver_login():
    """Authenticates driver and sets active session driver."""
    data = request.get_json() or {}
    driver_code = data.get("driver_code", "DRV-101")
    pin = data.get("pin", "1234")

    driver = db.authenticate_driver(driver_code, pin)
    if driver:
        monitor.set_driver(driver)
        # Restart session with driver_id
        end_db_session()
        monitor.reset_session()
        monitor.set_driver(driver)
        start_db_session()
        return jsonify({"success": True, "driver": driver, "message": f"Welcome back, {driver['name']}!"})
    else:
        return jsonify({"success": False, "message": "Invalid Driver Code or PIN"}), 401


@app.route("/api/driver/create", methods=["POST"])
def api_driver_create():
    """Creates a new driver profile."""
    data = request.get_json() or {}
    driver_code = data.get("driver_code")
    name = data.get("name")
    pin = data.get("pin", "1234")
    vehicle_reg = data.get("vehicle_reg", "TRK-904")

    if not driver_code or not name:
        return jsonify({"success": False, "message": "Driver Code and Name are required"}), 400

    driver = db.create_driver(driver_code, name, pin, vehicle_reg)
    if driver:
        return jsonify({"success": True, "driver": driver, "message": "Driver created successfully!"})
    else:
        return jsonify({"success": False, "message": "Driver Code already exists"}), 400


# ================================================================
# ROUTES — History (MySQL)
# ================================================================

@app.route("/api/history")
def api_history():
    """
    Returns the most recent sessions from the database.
    Used by the Session History section in the dashboard.
    """
    limit = request.args.get("limit", 20, type=int)
    sessions = db.get_session_history(limit)
    return jsonify(sessions)


@app.route("/api/history/<int:session_id>")
def api_session_detail(session_id):
    """
    Returns alerts and biometrics for a specific session.
    Used when the user clicks on a session in the history.
    """
    alerts = db.get_alerts_for_session(session_id)
    biometrics = db.get_biometrics_for_session(session_id)
    return jsonify({
        "alerts": alerts,
        "biometrics": biometrics
    })


# ================================================================
# CLEANUP ON SHUTDOWN
# ================================================================

def on_shutdown():
    """Save final session data before the server stops."""
    print("\nSaving session data to database...")
    end_db_session()
    print("Session data saved.")

atexit.register(on_shutdown)


# ================================================================
# STARTUP
# ================================================================

if __name__ == "__main__":
    # Start the database session
    start_db_session()

    # Start the camera thread
    cam_thread = threading.Thread(
        target=camera_thread,
        daemon=True
    )
    cam_thread.start()

    # Start the auto-save thread
    save_thread = threading.Thread(
        target=auto_save_data,
        daemon=True
    )
    save_thread.start()

    print("\n" + "=" * 50)
    print("  DriveGuard AI Dashboard")
    print("  Open in browser: http://localhost:5000")
    print("  MySQL database: driveguard_ai")
    print("=" * 50 + "\n")

    # Run Flask on port 5000 (accessible from local network)
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False,
        threaded=True
    )
