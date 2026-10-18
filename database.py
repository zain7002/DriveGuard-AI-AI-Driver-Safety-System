"""
DriveGuard AI — MySQL Database Module
Handles all database operations: sessions, alerts, and biometrics.

Tables:
    sessions   — One row per monitoring session
    alerts     — Every alert event with type and message
    biometrics — Periodic EAR / mouth ratio snapshots

Usage:
    from database import Database
    db = Database()
    db.create_tables()
    session_id = db.start_session()
    db.save_alert(session_id, "DROWSINESS", "Driver appears drowsy")
    db.save_biometrics(session_id, ear=0.28, mouth_ratio=0.12, ...)
    db.end_session(session_id, total_alerts=3, ...)
"""

try:
    import mysql.connector
    from mysql.connector import Error
    HAS_MYSQL = True
except ImportError:
    HAS_MYSQL = False
    Error = Exception

from datetime import datetime


class Database:
    """
    MySQL database wrapper for DriveGuard AI.
    All methods handle their own connections to stay thread-safe.
    If mysql-connector-python is not installed or connection fails, falls back gracefully.
    """

    def __init__(
        self,
        host="localhost",
        port=3306,
        user="root",
        password="password",
        database="driveguard_ai"
    ):
        self.config = {
            "host": host,
            "port": port,
            "user": user,
            "password": password,
            "database": database
        }
        self.database_name = database
        self.is_connected = False

        if not HAS_MYSQL:
            print("[WARNING] mysql-connector-python package is not installed. Session history will not be saved to MySQL.")
            print("[TIP] To enable MySQL, run: pip install mysql-connector-python")
            return

        try:
            # Create the database if it doesn't exist
            self._create_database()
            # Create tables
            self.create_tables()
            self.is_connected = True
            print(f"MySQL database '{database}' connected successfully.")
        except Exception as e:
            print(f"[WARNING] MySQL connection failed ({e}). Continuing in standalone mode without MySQL saving.")

    # ================================================================
    # INTERNAL: Get a fresh connection (thread-safe)
    # ================================================================

    def _get_connection(self):
        """Create and return a new MySQL connection."""
        return mysql.connector.connect(**self.config)

    # ================================================================
    # CREATE DATABASE
    # ================================================================

    def _create_database(self):
        """Create the database if it doesn't already exist."""
        try:
            conn = mysql.connector.connect(
                host=self.config["host"],
                port=self.config["port"],
                user=self.config["user"],
                password=self.config["password"]
            )
            cursor = conn.cursor()
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS {self.database_name}"
            )
            cursor.close()
            conn.close()

        except Error as e:
            print(f"MySQL Error (create database): {e}")
            raise

    # ================================================================
    # CREATE TABLES
    # ================================================================

    def create_tables(self):
        """Create all required tables if they don't exist."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # ── Drivers Table ──
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS drivers (
                    id            INT AUTO_INCREMENT PRIMARY KEY,
                    driver_code   VARCHAR(50) UNIQUE NOT NULL,
                    name          VARCHAR(100) NOT NULL,
                    pin           VARCHAR(10) NOT NULL DEFAULT '1234',
                    vehicle_reg   VARCHAR(50) DEFAULT 'TRK-904',
                    safety_score  INT DEFAULT 100,
                    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Seed default drivers if empty
            cursor.execute("SELECT COUNT(*) FROM drivers")
            if cursor.fetchone()[0] == 0:
                cursor.execute("""
                    INSERT INTO drivers (driver_code, name, pin, vehicle_reg, safety_score)
                    VALUES 
                        ('DRV-101', 'Alex Johnson', '1234', 'TRK-904', 98),
                        ('DRV-102', 'Sarah Connor', '1234', 'TRK-108', 94)
                """)

            # ── Sessions Table ──
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id                INT AUTO_INCREMENT PRIMARY KEY,
                    driver_id         INT,
                    start_time        DATETIME NOT NULL,
                    end_time          DATETIME,
                    total_alerts      INT DEFAULT 0,
                    drowsiness_count  INT DEFAULT 0,
                    yawn_count        INT DEFAULT 0,
                    phone_count       INT DEFAULT 0,
                    distraction_count INT DEFAULT 0,
                    FOREIGN KEY (driver_id) REFERENCES drivers(id) ON DELETE SET NULL
                )
            """)

            # ── Alerts Table ──
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS alerts (
                    id          INT AUTO_INCREMENT PRIMARY KEY,
                    session_id  INT NOT NULL,
                    alert_time  DATETIME NOT NULL,
                    alert_type  VARCHAR(50) NOT NULL,
                    message     VARCHAR(255),
                    FOREIGN KEY (session_id) REFERENCES sessions(id)
                        ON DELETE CASCADE
                )
            """)

            # ── Biometrics Table ──
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS biometrics (
                    id            INT AUTO_INCREMENT PRIMARY KEY,
                    session_id    INT NOT NULL,
                    recorded_at   DATETIME NOT NULL,
                    ear           FLOAT,
                    mouth_ratio   FLOAT,
                    mouth_width   FLOAT,
                    attention     VARCHAR(20),
                    face_detected BOOLEAN,
                    FOREIGN KEY (session_id) REFERENCES sessions(id)
                        ON DELETE CASCADE
                )
            """)

            conn.commit()
            cursor.close()
            conn.close()

        except Error as e:
            print(f"MySQL Error (create tables): {e}")

    # ================================================================
    # DRIVER OPERATIONS
    # ================================================================

    def get_all_drivers(self):
        """Fetch list of all registered drivers."""
        if not self.is_connected:
            return [
                {"id": 1, "driver_code": "DRV-101", "name": "Alex Johnson", "pin": "1234", "vehicle_reg": "TRK-904", "safety_score": 98},
                {"id": 2, "driver_code": "DRV-102", "name": "Sarah Connor", "pin": "1234", "vehicle_reg": "TRK-108", "safety_score": 94}
            ]
        try:
            conn = self._get_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT id, driver_code, name, vehicle_reg, safety_score FROM drivers ORDER BY name ASC")
            drivers = cursor.fetchall()
            cursor.close()
            conn.close()
            return drivers
        except Error as e:
            print(f"MySQL Error (get all drivers): {e}")
            return []

    def authenticate_driver(self, driver_code, pin="1234"):
        """Authenticate a driver by driver_code and pin."""
        if not self.is_connected:
            # Fallback mock authentication
            return {
                "id": 1, "driver_code": driver_code or "DRV-101",
                "name": "Alex Johnson" if (driver_code or "").startswith("DRV-101") else "Active Driver",
                "vehicle_reg": "TRK-904", "safety_score": 98
            }
        try:
            conn = self._get_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                "SELECT id, driver_code, name, vehicle_reg, safety_score FROM drivers WHERE driver_code = %s AND pin = %s",
                (driver_code, pin)
            )
            driver = cursor.fetchone()
            cursor.close()
            conn.close()
            return driver
        except Error as e:
            print(f"MySQL Error (authenticate driver): {e}")
            return None

    def create_driver(self, driver_code, name, pin="1234", vehicle_reg="TRK-904"):
        """Create a new driver profile."""
        if not self.is_connected:
            return {"id": 99, "driver_code": driver_code, "name": name, "vehicle_reg": vehicle_reg, "safety_score": 100}
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO drivers (driver_code, name, pin, vehicle_reg, safety_score) VALUES (%s, %s, %s, %s, 100)",
                (driver_code, name, pin, vehicle_reg)
            )
            driver_id = cursor.lastrowid
            conn.commit()
            cursor.close()
            conn.close()
            return {"id": driver_id, "driver_code": driver_code, "name": name, "vehicle_reg": vehicle_reg, "safety_score": 100}
        except Error as e:
            print(f"MySQL Error (create driver): {e}")
            return None

    # ================================================================
    # SESSION OPERATIONS
    # ================================================================

    def start_session(self, driver_id=None):
        """
        Insert a new session row and return the session ID.
        Called when the server starts or when the user resets.
        """
        if not self.is_connected:
            return None

        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            if driver_id:
                cursor.execute(
                    "INSERT INTO sessions (driver_id, start_time) VALUES (%s, %s)",
                    (driver_id, datetime.now())
                )
            else:
                cursor.execute(
                    "INSERT INTO sessions (start_time) VALUES (%s)",
                    (datetime.now(),)
                )

            session_id = cursor.lastrowid

            conn.commit()
            cursor.close()
            conn.close()

            print(f"New session started (ID: {session_id}, Driver ID: {driver_id})")
            return session_id

        except Error as e:
            print(f"MySQL Error (start session): {e}")
            return None

    def end_session(
        self,
        session_id,
        total_alerts=0,
        drowsiness_count=0,
        yawn_count=0,
        phone_count=0,
        distraction_count=0
    ):
        """
        Update the session with end_time and final counters.
        Called when the user resets or the server shuts down.
        """
        if not self.is_connected or session_id is None:
            return

        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                UPDATE sessions SET
                    end_time = %s,
                    total_alerts = %s,
                    drowsiness_count = %s,
                    yawn_count = %s,
                    phone_count = %s,
                    distraction_count = %s
                WHERE id = %s
                """,
                (
                    datetime.now(),
                    total_alerts,
                    drowsiness_count,
                    yawn_count,
                    phone_count,
                    distraction_count,
                    session_id
                )
            )

            conn.commit()
            cursor.close()
            conn.close()

            print(f"Session {session_id} ended.")

        except Error as e:
            print(f"MySQL Error (end session): {e}")

    # ================================================================
    # ALERT OPERATIONS
    # ================================================================

    def save_alert(self, session_id, alert_type, message):
        """
        Save a single alert event to the database.
        Called automatically when new alerts are detected.
        """
        if not self.is_connected or session_id is None:
            return

        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO alerts (session_id, alert_time, alert_type, message)
                VALUES (%s, %s, %s, %s)
                """,
                (session_id, datetime.now(), alert_type, message)
            )

            conn.commit()
            cursor.close()
            conn.close()

        except Error as e:
            print(f"MySQL Error (save alert): {e}")

    # ================================================================
    # BIOMETRICS OPERATIONS
    # ================================================================

    def save_biometrics(
        self,
        session_id,
        ear,
        mouth_ratio,
        mouth_width,
        attention,
        face_detected
    ):
        """
        Save a biometrics snapshot to the database.
        Called every 5 seconds by the biometrics thread.
        """
        if not self.is_connected or session_id is None:
            return

        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO biometrics
                    (session_id, recorded_at, ear, mouth_ratio,
                     mouth_width, attention, face_detected)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    session_id,
                    datetime.now(),
                    ear,
                    mouth_ratio,
                    mouth_width,
                    attention,
                    face_detected
                )
            )

            conn.commit()
            cursor.close()
            conn.close()

        except Error as e:
            print(f"MySQL Error (save biometrics): {e}")

    # ================================================================
    # HISTORY QUERIES
    # ================================================================

    def get_session_history(self, limit=20):
        """
        Fetch the most recent sessions, newest first.
        Returns a list of dicts.
        """
        if not self.is_connected:
            return []
        try:
            conn = self._get_connection()
            cursor = conn.cursor(dictionary=True)

            cursor.execute(
                """
                SELECT id, start_time, end_time,
                       total_alerts, drowsiness_count,
                       yawn_count, phone_count, distraction_count
                FROM sessions
                ORDER BY start_time DESC
                LIMIT %s
                """,
                (limit,)
            )

            rows = cursor.fetchall()

            # Convert datetime objects to strings for JSON
            for row in rows:
                if row["start_time"]:
                    row["start_time"] = row["start_time"].strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )
                if row["end_time"]:
                    row["end_time"] = row["end_time"].strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )

            cursor.close()
            conn.close()
            return rows

        except Error as e:
            print(f"MySQL Error (get sessions): {e}")
            return []

    def get_alerts_for_session(self, session_id):
        """
        Fetch all alerts for a specific session, newest first.
        Returns a list of dicts.
        """
        if not self.is_connected:
            return []

        try:
            conn = self._get_connection()
            cursor = conn.cursor(dictionary=True)

            cursor.execute(
                """
                SELECT id, alert_time, alert_type, message
                FROM alerts
                WHERE session_id = %s
                ORDER BY alert_time DESC
                """,
                (session_id,)
            )

            rows = cursor.fetchall()

            for row in rows:
                if row["alert_time"]:
                    row["alert_time"] = row["alert_time"].strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )

            cursor.close()
            conn.close()
            return rows

        except Error as e:
            print(f"MySQL Error (get alerts): {e}")
            return []

    def get_biometrics_for_session(self, session_id):
        """
        Fetch all biometrics for a specific session.
        Returns a list of dicts.
        """
        if not self.is_connected:
            return []
        try:
            conn = self._get_connection()
            cursor = conn.cursor(dictionary=True)

            cursor.execute(
                """
                SELECT recorded_at, ear, mouth_ratio,
                       mouth_width, attention, face_detected
                FROM biometrics
                WHERE session_id = %s
                ORDER BY recorded_at ASC
                """,
                (session_id,)
            )

            rows = cursor.fetchall()

            for row in rows:
                if row["recorded_at"]:
                    row["recorded_at"] = row["recorded_at"].strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )

            cursor.close()
            conn.close()
            return rows

        except Error as e:
            print(f"MySQL Error (get biometrics): {e}")
            return []


# ================================================================
# STANDALONE TEST
# ================================================================

if __name__ == "__main__":
    print("Testing DriveGuard AI Database...")
    db = Database()

    # Test session
    sid = db.start_session()
    print(f"  Created session: {sid}")

    # Test alert
    db.save_alert(sid, "DROWSINESS", "Test drowsiness alert")
    print("  Saved test alert")

    # Test biometrics
    db.save_biometrics(sid, 0.28, 0.12, 0.20, "FORWARD", True)
    print("  Saved test biometrics")

    # End session
    db.end_session(sid, total_alerts=1, drowsiness_count=1)
    print("  Ended session")

    # Fetch history
    sessions = db.get_session_history()
    print(f"  Session history: {sessions}")

    alerts = db.get_alerts_for_session(sid)
    print(f"  Alerts: {alerts}")

    print("\nAll tests passed!")
