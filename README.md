# DriveGuard-AI-AI-Driver-Safety-System
AI-powered driver safety monitoring system using Python, OpenCV, MediaPipe, and YOLO to detect drowsiness, yawning, distraction, and mobile phones in real time, with voice alerts, buzzer warnings, and a Flask web dashboard.
DriveGuard AI – AI Driver Safety System

DriveGuard AI is a computer-vision-based driver monitoring system designed to identify potentially unsafe driving behaviors in real time and provide immediate voice and buzzer alerts.

Features

Drowsiness Detection: Uses facial landmarks and eye measurements to identify prolonged eye closure.

Yawning Detection: Analyzes mouth opening and duration to identify possible yawning.

Distraction Detection: Estimates head direction to identify prolonged looking away.

Mobile Phone Detection: Uses YOLO object detection to identify mobile phones in camera frames.

Voice and Buzzer Alerts: Warns the driver when potentially unsafe behavior is detected.

Live Dashboard: Displays camera video, monitoring status, event counters, and alert history.

Driving Duration Tracking: Planned enhancement for tracking driving time and suggesting breaks.

Technologies Used

Python

OpenCV

MediaPipe Face Mesh

YOLO

Flask

HTML, CSS, JavaScript

pyttsx3

Windows winsound

System Workflow

Capture live video from a camera using OpenCV.

Analyze facial landmarks using MediaPipe.

Calculate eye and mouth measurements to identify potential fatigue indicators.

Detect mobile phones using YOLO.

Trigger voice and buzzer alerts when configured detection conditions are met.

Display live monitoring information through a Flask web dashboard.

Installation

Prerequisites

Python 3.11 (or a compatible version for the selected dependencies)

Webcam

Windows OS for the current winsound implementation
