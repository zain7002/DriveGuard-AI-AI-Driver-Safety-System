/* ==============================================
   DriveGuard AI — Dashboard Logic
   Polls /api/status every 500ms · Updates UI
   ============================================== */

// ── Configuration ──────────────────────────────
const API_BASE = "";  // Relative — served by Flask on same origin
const POLL_INTERVAL = 500; // milliseconds

// ── DOM References ─────────────────────────────
const $ = (id) => document.getElementById(id);

const dom = {
  // Header
  systemStatus: $("systemStatus"),
  statusDot:    $("statusDot"),
  statusText:   $("statusText"),
  datetime:     $("datetime"),
  btnReset:     $("btnReset"),

  // Camera
  cameraFeed:    $("cameraFeed"),
  cameraOffline: $("cameraOffline"),
  btnFullscreen: $("btnFullscreen"),
  cameraPanel:   $("cameraPanel"),
  badgeLive:     $("badgeLive"),

  // Status cards
  cardFace:        $("cardFace"),
  cardDrowsiness:  $("cardDrowsiness"),
  cardYawning:     $("cardYawning"),
  cardPhone:       $("cardPhone"),
  cardDistraction: $("cardDistraction"),
  cardAttention:   $("cardAttention"),

  valFace:        $("valFace"),
  valDrowsiness:  $("valDrowsiness"),
  valYawning:     $("valYawning"),
  valPhone:       $("valPhone"),
  valDistraction: $("valDistraction"),
  valAttention:   $("valAttention"),

  // Biometrics
  bioEar:         $("bioEar"),
  bioMouth:       $("bioMouth"),
  bioMouthW:      $("bioMouthW"),
  bioAttention:   $("bioAttention"),
  bioFaceStatus:  $("bioFaceStatus"),
  barEar:         $("barEar"),
  barMouth:       $("barMouth"),
  barMouthW:      $("barMouthW"),

  // Counters
  numTotal:      $("numTotal"),
  numDrowsiness: $("numDrowsiness"),
  numYawning:    $("numYawning"),
  numPhone:      $("numPhone"),
  numDistraction:$("numDistraction"),
  cntTotal:      $("cntTotal"),
  cntDrowsiness: $("cntDrowsiness"),
  cntYawning:    $("cntYawning"),
  cntPhone:      $("cntPhone"),
  cntDistraction:$("cntDistraction"),

  // Alerts
  alertList:       $("alertList"),
  alertEmpty:      $("alertEmpty"),
  alertCountBadge: $("alertCountBadge"),

  // Threat Level & Context Bar
  threatBadge:     $("threatBadge"),
  threatDesc:      $("threatDesc"),
  segment0:        $("segment0"),
  segment1:        $("segment1"),
  segment2:        $("segment2"),
  contextPill:     $("contextPill"),
  contextPillText: $("contextPillText"),

  // Rest Break Module
  valDriveDuration: $("valDriveDuration"),
  valBreakPercent:  $("valBreakPercent"),
  barBreak:         $("barBreak"),
  breakPill:        $("breakPill"),
  msgBreakStatus:   $("msgBreakStatus"),
  btnLogBreak:      $("btnLogBreak"),

  // Driver Profile & Login Modal
  driverName:       $("driverName"),
  driverCode:       $("driverCode"),
  driverVehicle:    $("driverVehicle"),
  driverScoreBadge: $("driverScoreBadge"),
  driverScoreVal:   $("driverScoreVal"),
  driverScoreGrade: $("driverScoreGrade"),
  btnSwitchDriver:  $("btnSwitchDriver"),
  loginModal:       $("loginModal"),
  loginForm:        $("loginForm"),
  selectDriver:     $("selectDriver"),
  groupDriverCode:  $("groupDriverCode"),
  groupDriverName:  $("groupDriverName"),
  groupVehicleReg:  $("groupVehicleReg"),
  inputDriverCode:  $("inputDriverCode"),
  inputDriverName:  $("inputDriverName"),
  inputVehicleReg:  $("inputVehicleReg"),
  inputPin:         $("inputPin"),

  // HUD Elements
  hudEarPill:       $("hudEarPill"),
  hudStatusPill:    $("hudStatusPill"),
  hudVisionPill:    $("hudVisionPill"),
  cameraWrapper:    $("cameraWrapper"),

  // Perimeter Alarm Vignette
  alarmVignette:    $("alarmVignette"),

  // Floating Command Dock
  floatingDock:      $("floatingDock"),
  dockBtnAudio:      $("dockBtnAudio"),
  dockAudioIcon:     $("dockAudioIcon"),
  dockAudioLabel:    $("dockAudioLabel"),
  dockBtnVision:     $("dockBtnVision"),
  dockVisionLabel:   $("dockVisionLabel"),
  dockBtnReset:      $("dockBtnReset"),
  dockBtnSim:        $("dockBtnSim"),
  dockBtnFullscreen: $("dockBtnFullscreen"),

  // Demo Sandbox Drawer
  sandboxDrawer:     $("sandboxDrawer"),
  btnCloseSandbox:   $("btnCloseSandbox"),

  // Toast
  toastContainer: $("toastContainer"),
};

// ── State ──────────────────────────────────────
let isOnline = false;
let cameraLoaded = false;
let previousAlertCount = 0;    // track new alerts for toast
let previousData = null;       // for detecting status changes

// ── Clock ──────────────────────────────────────
function updateClock() {
  const now = new Date();
  const options = {
    weekday: "short",
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  };
  dom.datetime.textContent = now.toLocaleDateString("en-US", options);
}
updateClock();
setInterval(updateClock, 1000);

// ── Camera Stream Handling ─────────────────────
// Detect if the MJPEG stream fails to load
dom.cameraFeed.addEventListener("load", () => {
  cameraLoaded = true;
  dom.cameraOffline.classList.remove("visible");
  dom.badgeLive.style.display = "inline-flex";
});

dom.cameraFeed.addEventListener("error", () => {
  cameraLoaded = false;
  dom.cameraOffline.classList.add("visible");
  dom.badgeLive.style.display = "none";
  // Retry after a few seconds
  setTimeout(() => {
    dom.cameraFeed.src = "/video_feed?" + Date.now();
  }, 3000);
});

// ── Fullscreen Toggle ──────────────────────────
dom.btnFullscreen.addEventListener("click", () => {
  dom.cameraPanel.classList.toggle("fullscreen");
  // Press Escape to exit
  if (dom.cameraPanel.classList.contains("fullscreen")) {
    const onEsc = (e) => {
      if (e.key === "Escape") {
        dom.cameraPanel.classList.remove("fullscreen");
        document.removeEventListener("keydown", onEsc);
      }
    };
    document.addEventListener("keydown", onEsc);
  }
});

// ── System Status Indicator ────────────────────
function setOnlineStatus(online) {
  if (online === isOnline) return;
  isOnline = online;
  dom.systemStatus.className = "system-status " + (online ? "online" : "offline");
  dom.statusText.textContent = online ? "Online" : "Offline";
}

// ── Status Card Helpers ────────────────────────

/**
 * Sets a status card's visual state.
 * @param {HTMLElement} card  — the .status-card element
 * @param {HTMLElement} valEl — the .status-value element
 * @param {"normal"|"warning"|"caution"} state
 * @param {string} label — text to display
 */
function setCardState(card, valEl, state, label) {
  card.className = "status-card glass-card " + state;
  valEl.textContent = label;
}

// ── Counter Animation ──────────────────────────
function animateCounter(el, newVal) {
  const current = parseInt(el.textContent, 10) || 0;
  if (current === newVal) return;
  el.textContent = newVal;
  // Quick scale pop
  el.style.transform = "scale(1.25)";
  setTimeout(() => { el.style.transform = "scale(1)"; }, 200);
}

// ── Biometric Progress Bars ────────────────────
function updateBiometrics(data) {
  // EAR — typical range 0.15–0.40, map to 0–100%
  const ear = data.ear ?? 0;
  dom.bioEar.textContent = ear.toFixed(3);
  dom.barEar.style.width = Math.min(ear / 0.4 * 100, 100).toFixed(1) + "%";
  // Color shift: low EAR = danger
  if (ear < 0.2) {
    dom.barEar.style.background = "linear-gradient(90deg, var(--red), var(--orange))";
  } else {
    dom.barEar.style.background = "";  // reset to default CSS gradient
  }

  // Mouth ratio — typical range 0–0.6
  const mr = data.mouth_ratio ?? 0;
  dom.bioMouth.textContent = mr.toFixed(3);
  dom.barMouth.style.width = Math.min(mr / 0.5 * 100, 100).toFixed(1) + "%";

  // Mouth width — typical range 0–0.6
  const mw = data.mouth_width ?? 0;
  dom.bioMouthW.textContent = mw.toFixed(3);
  dom.barMouthW.style.width = Math.min(mw / 0.5 * 100, 100).toFixed(1) + "%";

  // Text-based biometrics
  dom.bioAttention.textContent = data.attention ?? "—";
  dom.bioFaceStatus.textContent = data.face ?? "—";
}

// ── Alert History ──────────────────────────────
function updateAlerts(alerts) {
  if (!alerts || alerts.length === 0) {
    dom.alertEmpty.style.display = "flex";
    dom.alertCountBadge.textContent = "0 events";
    return;
  }
  dom.alertEmpty.style.display = "none";
  dom.alertCountBadge.textContent = alerts.length + " event" + (alerts.length !== 1 ? "s" : "");

  // Rebuild alert list (newest first — assume backend returns newest first,
  // or we reverse if needed)
  const fragment = document.createDocumentFragment();

  alerts.forEach((alert) => {
    const entry = document.createElement("div");
    entry.className = "alert-entry";
    entry.innerHTML = `
      <div class="alert-icon">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/>
          <line x1="12" y1="9" x2="12" y2="13"/>
          <line x1="12" y1="17" x2="12.01" y2="17"/>
        </svg>
      </div>
      <div class="alert-body">
        <div class="alert-type">${escapeHtml(alert.type || "Alert")}</div>
        <div class="alert-msg">${escapeHtml(alert.message || "")}</div>
      </div>
      <div class="alert-time">${escapeHtml(alert.time || "")}</div>
    `;
    fragment.appendChild(entry);
  });

  // Keep the empty-state element but clear other entries
  const children = Array.from(dom.alertList.children);
  children.forEach((child) => {
    if (child.id !== "alertEmpty") child.remove();
  });
  dom.alertList.prepend(fragment);
}

// ── Toast Notifications ────────────────────────
/**
 * Shows a small toast notification.
 * @param {string} message
 * @param {"warning"|"success"|"info"} type
 */
function showToast(message, type = "info") {
  const toast = document.createElement("div");
  toast.className = "toast toast-" + type;
  const iconMap = {
    warning: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>`,
    success: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 11-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>`,
    info:    `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/></svg>`,
  };
  toast.innerHTML = (iconMap[type] || iconMap.info) + `<span>${escapeHtml(message)}</span>`;
  dom.toastContainer.appendChild(toast);

  // Auto-dismiss after 4s
  setTimeout(() => {
    toast.style.animation = "toastOut .3s ease-in forwards";
    toast.addEventListener("animationend", () => toast.remove());
  }, 4000);
}

// ── HTML Escaping ──────────────────────────────
function escapeHtml(str) {
  const div = document.createElement("div");
  div.appendChild(document.createTextNode(str));
  return div.innerHTML;
}

// ── Main Status Update ─────────────────────────
function processStatus(data) {
  // 0. Context Mirror Check & Graduated Threat Stage
  const isMirrorCheck = !!data.is_mirror_check;
  const alertStage = data.alert_stage ?? 0;
  const alertLevel = data.alert_level || "NORMAL";

  if (dom.contextPill) {
    if (isMirrorCheck && data.mirror_direction) {
      dom.contextPill.style.display = "flex";
      dom.contextPillText.textContent = `Mirror Check (${data.mirror_direction})`;
    } else {
      dom.contextPill.style.display = "none";
    }
  }

  if (dom.threatBadge) {
    if (alertStage === 2 || alertLevel === "CRITICAL") {
      dom.threatBadge.className = "threat-badge stage-critical";
      dom.threatBadge.textContent = "STAGE 2 • CRITICAL ALARM";
      dom.threatDesc.textContent = "Immediate safety intervention triggered!";
      dom.segment0.className = "threat-segment segment-0 active";
      dom.segment1.className = "threat-segment segment-1 active";
      dom.segment2.className = "threat-segment segment-2 active";
    } else if (alertStage === 1 || alertLevel === "WARNING") {
      dom.threatBadge.className = "threat-badge stage-warning";
      dom.threatBadge.textContent = "STAGE 1 • CAUTION";
      dom.threatDesc.textContent = "Early fatigue or distraction detected";
      dom.segment0.className = "threat-segment segment-0 active";
      dom.segment1.className = "threat-segment segment-1 active";
      dom.segment2.className = "threat-segment segment-2";
    } else if (isMirrorCheck) {
      dom.threatBadge.className = "threat-badge stage-normal";
      dom.threatBadge.textContent = "STAGE 0 • MIRROR CHECK";
      dom.threatDesc.textContent = `Normal glance: ${data.mirror_direction} mirror (${data.distraction_duration || 0.5}s)`;
      dom.segment0.className = "threat-segment segment-0 active";
      dom.segment1.className = "threat-segment segment-1";
      dom.segment2.className = "threat-segment segment-2";
    } else {
      dom.threatBadge.className = "threat-badge stage-normal";
      dom.threatBadge.textContent = "STAGE 0 • NORMAL";
      dom.threatDesc.textContent = "Driver focused & attentive";
      dom.segment0.className = "threat-segment segment-0 active";
      dom.segment1.className = "threat-segment segment-1";
      dom.segment2.className = "threat-segment segment-2";
    }
  }

  // Dynamic Perimeter Mood Lighting Vignette
  if (dom.alarmVignette) {
    if (alertStage === 2 || alertLevel === "CRITICAL") {
      dom.alarmVignette.className = "alarm-vignette stage-critical";
    } else if (alertStage === 1 || alertLevel === "WARNING") {
      dom.alarmVignette.className = "alarm-vignette stage-warning";
    } else if (isMirrorCheck) {
      dom.alarmVignette.className = "alarm-vignette stage-mirror";
    } else {
      dom.alarmVignette.className = "alarm-vignette";
    }
  }

  // 1. Face Detection
  const faceNormal = (typeof data.face === "string")
    ? data.face.toUpperCase().includes("FACE DETECTED")
    : !!data.face;
  const faceText = (typeof data.face === "string") ? data.face : (data.face ? "Detected" : "No Face");
  setCardState(
    dom.cardFace, dom.valFace,
    faceNormal ? "normal" : "warning",
    faceText
  );

  // 2. Drowsiness
  const drowsy = !!data.drowsiness;
  setCardState(
    dom.cardDrowsiness, dom.valDrowsiness,
    drowsy ? "warning" : "normal",
    drowsy ? "Drowsiness Detected!" : "Alert"
  );

  // 3. Yawning
  const yawning = !!data.yawning;
  setCardState(
    dom.cardYawning, dom.valYawning,
    yawning ? "warning" : "normal",
    yawning ? "Yawning Detected!" : "Normal"
  );

  // 4. Phone Usage
  const phone = !!data.phone;
  setCardState(
    dom.cardPhone, dom.valPhone,
    phone ? "warning" : "normal",
    phone ? "Phone Detected!" : "No Phone"
  );

  // 5. Distraction & Context Mirror Check
  const attention = (typeof data.attention === "string") ? data.attention.toUpperCase() : "";
  const distracted = (attention.includes("LEFT") || attention.includes("RIGHT")) && !isMirrorCheck;
  
  if (isMirrorCheck) {
    setCardState(
      dom.cardDistraction, dom.valDistraction,
      "normal",
      "Mirror Check (" + data.mirror_direction + ")"
    );
  } else {
    setCardState(
      dom.cardDistraction, dom.valDistraction,
      distracted ? "caution" : "normal",
      distracted ? "Looking " + data.attention : "Focused"
    );
  }

  // 6. Driver Attention (overall)
  const attentionOk = attention === "FORWARD" || attention === "CENTER" || isMirrorCheck;
  setCardState(
    dom.cardAttention, dom.valAttention,
    attentionOk ? "normal" : (distracted ? "caution" : "normal"),
    isMirrorCheck ? "MIRROR CHECK" : (data.attention || "—")
  );

  // 7. Driving Duration & Rest Break Module
  if (dom.valDriveDuration && data.drive_duration_formatted) {
    dom.valDriveDuration.textContent = data.drive_duration_formatted;
  }
  if (dom.valBreakPercent) {
    const pct = data.break_progress_percent ?? 0;
    dom.valBreakPercent.textContent = pct + "%";
    if (dom.barBreak) dom.barBreak.style.width = Math.min(100, pct) + "%";
  }
  if (dom.breakPill) {
    const bStatus = data.break_status || "OPTIMAL";
    if (bStatus === "OVERDUE") {
      dom.breakPill.className = "break-pill pill-overdue";
      dom.breakPill.textContent = "OVERDUE";
      if (dom.msgBreakStatus) dom.msgBreakStatus.textContent = "⚠️ REST BREAK OVERDUE! Please pull over safely.";
    } else if (bStatus === "ADVISORY") {
      dom.breakPill.className = "break-pill pill-advisory";
      dom.breakPill.textContent = "ADVISORY";
      if (dom.msgBreakStatus) dom.msgBreakStatus.textContent = "Rest break recommended soon (2+ hrs driving).";
    } else {
      dom.breakPill.className = "break-pill pill-optimal";
      dom.breakPill.textContent = "OPTIMAL";
      if (dom.msgBreakStatus) dom.msgBreakStatus.textContent = "Continuous driving time is optimal. Drive safely!";
    }
  }

  // 8. Biometrics
  updateBiometrics(data);

  // 9. Driver Profile & Safety Score Badge
  if (data.driver) {
    if (dom.driverName) dom.driverName.textContent = data.driver.name || "Alex Johnson";
    if (dom.driverCode) dom.driverCode.textContent = data.driver.driver_code || "DRV-101";
    if (dom.driverVehicle) dom.driverVehicle.textContent = data.driver.vehicle_reg || "TRK-904";
  }
  if (dom.driverScoreBadge && data.safety_score !== undefined) {
    const score = data.safety_score;
    const grade = data.safety_grade || "A";
    if (dom.driverScoreVal) dom.driverScoreVal.textContent = `${score}%`;
    if (dom.driverScoreGrade) dom.driverScoreGrade.textContent = grade;
    dom.driverScoreBadge.className = `driver-score-pill score-${grade.toLowerCase()}`;
  }

  // 10. Live Camera HUD Pills
  if (dom.hudEarPill && data.ear !== undefined) {
    dom.hudEarPill.textContent = "EAR: " + (typeof data.ear === "number" ? data.ear.toFixed(3) : "--");
  }
  if (dom.hudStatusPill) {
    const lvl = data.alert_level || "ATTENTIVE";
    dom.hudStatusPill.textContent = "STATUS: " + (lvl === "MIRROR_CHECK" ? "MIRROR CHECK" : lvl);
    if (lvl === "CRITICAL") {
      dom.hudStatusPill.style.color = "#ef4444";
      dom.cameraPanel.classList.add("hud-critical-pulse");
    } else if (lvl === "WARNING") {
      dom.hudStatusPill.style.color = "#f59e0b";
      dom.cameraPanel.classList.remove("hud-critical-pulse");
    } else {
      dom.hudStatusPill.style.color = "#00f0ff";
      dom.cameraPanel.classList.remove("hud-critical-pulse");
    }
  }

  // 8. Event Counters
  const totalAlerts = data.total_alerts ?? 0;
  animateCounter(dom.numTotal, totalAlerts);
  animateCounter(dom.numDrowsiness, data.drowsiness_count ?? 0);
  animateCounter(dom.numYawning, data.yawn_count ?? 0);
  animateCounter(dom.numPhone, data.phone_count ?? 0);
  animateCounter(dom.numDistraction, data.distraction_count ?? 0);

  // Highlight counters that have counts
  dom.cntTotal.classList.toggle("has-count", totalAlerts > 0);
  dom.cntDrowsiness.classList.toggle("has-count", (data.drowsiness_count ?? 0) > 0);
  dom.cntYawning.classList.toggle("has-count", (data.yawn_count ?? 0) > 0);
  dom.cntPhone.classList.toggle("has-count", (data.phone_count ?? 0) > 0);
  dom.cntDistraction.classList.toggle("has-count", (data.distraction_count ?? 0) > 0);

  // 9. Show toast for new alerts & trigger synthesized audio
  if (totalAlerts > previousAlertCount && previousAlertCount >= 0) {
    playCockpitBeep(alertStage === 2 ? "critical" : "warning");
    // Determine what kind of alert was triggered
    if (drowsy)    showToast("Drowsiness detected!", "warning");
    if (yawning)   showToast("Yawning detected!", "warning");
    if (phone)     showToast("Phone usage detected!", "warning");
    if (distracted) showToast("Driver distraction detected!", "warning");
    if (!faceNormal) showToast("No face detected!", "warning");
  }
  previousAlertCount = totalAlerts;

  // 10. Alert History
  updateAlerts(data.alerts);

  previousData = data;
}

// ── API Polling ────────────────────────────────
async function pollStatus() {
  if (isSimulationActive) return;
  try {
    const res = await fetch(API_BASE + "/api/status", { cache: "no-store" });
    if (!res.ok) throw new Error("HTTP " + res.status);
    const data = await res.json();

    setOnlineStatus(true);
    processStatus(data);
  } catch (err) {
    setOnlineStatus(false);
    // Don't spam the console
    // console.warn("DriveGuard API unreachable:", err.message);
  }
}

// Start polling loop
setInterval(pollStatus, POLL_INTERVAL);
// Run immediately once
pollStatus();

// ── Reset Session ──────────────────────────────
dom.btnReset.addEventListener("click", async () => {
  dom.btnReset.disabled = true;
  dom.btnReset.style.opacity = "0.5";

  try {
    const res = await fetch(API_BASE + "/api/reset", { method: "POST" });
    if (!res.ok) throw new Error("HTTP " + res.status);

    // Reset local state
    previousAlertCount = 0;
    previousData = null;

    // Clear alert list
    const children = Array.from(dom.alertList.children);
    children.forEach((child) => { if (child.id !== "alertEmpty") child.remove(); });
    dom.alertEmpty.style.display = "flex";
    dom.alertCountBadge.textContent = "0 events";

    // Reset counters immediately
    [dom.numTotal, dom.numDrowsiness, dom.numYawning, dom.numPhone, dom.numDistraction]
      .forEach((el) => { el.textContent = "0"; });
    [dom.cntTotal, dom.cntDrowsiness, dom.cntYawning, dom.cntPhone, dom.cntDistraction]
      .forEach((el) => { el.classList.remove("has-count"); });

    showToast("Session reset successfully!", "success");
  } catch (err) {
    showToast("Failed to reset session — is Flask running?", "warning");
  } finally {
    dom.btnReset.disabled = false;
    dom.btnReset.style.opacity = "";
  }
});

// ── Session History (MySQL) ────────────────────
const historyDom = {
  body:               $("sessionHistoryBody"),
  empty:              $("historyEmpty"),
  badge:              $("historyCountBadge"),
  btnRefresh:         $("btnRefreshHistory"),
  modal:              $("sessionModal"),
  modalSessionId:     $("modalSessionId"),
  modalSessionDate:   $("modalSessionDate"),
  modalSessionDuration: $("modalSessionDuration"),
  modalAlertsCount:   $("modalAlertsCount"),
  modalAlertList:     $("modalAlertList"),
  btnCloseModal:      $("btnCloseModal"),
};

async function fetchSessionHistory() {
  if (!historyDom.body) return;
  
  try {
    const res = await fetch(API_BASE + "/api/history/sessions");
    if (!res.ok) return;
    const data = await res.json();
    
    if (!data.success || !data.sessions || data.sessions.length === 0) {
      historyDom.empty.style.display = "flex";
      historyDom.badge.textContent = "0 sessions";
      historyDom.body.innerHTML = "";
      return;
    }

    historyDom.empty.style.display = "none";
    historyDom.badge.textContent = `${data.sessions.length} session${data.sessions.length > 1 ? 's' : ''}`;
    
    let html = "";
    data.sessions.forEach((s) => {
      const startTime = s.start_time ? new Date(s.start_time).toLocaleString() : "Unknown";
      const duration = s.duration_seconds ? `${Math.floor(s.duration_seconds / 60)}m ${s.duration_seconds % 60}s` : (s.end_time ? "Ended" : "Active");
      
      html += `
        <tr onclick="openSessionDetails(${s.id})">
          <td>#${s.id}</td>
          <td>${escapeHtml(startTime)}</td>
          <td>${escapeHtml(duration)}</td>
          <td><span class="count-pill ${s.total_alerts > 0 ? 'alert' : ''}">${s.total_alerts}</span></td>
          <td><span class="count-pill ${s.drowsiness_count > 0 ? 'alert' : ''}">${s.drowsiness_count}</span></td>
          <td><span class="count-pill ${s.yawn_count > 0 ? 'alert' : ''}">${s.yawn_count}</span></td>
          <td><span class="count-pill ${s.phone_count > 0 ? 'alert' : ''}">${s.phone_count}</span></td>
          <td><button class="btn-view" onclick="event.stopPropagation(); openSessionDetails(${s.id})">View</button></td>
        </tr>
      `;
    });
    
    historyDom.body.innerHTML = html;
  } catch (err) {
    console.error("Error fetching session history:", err);
  }
}

async function openSessionDetails(sessionId) {
  if (!historyDom.modal) return;

  try {
    const res = await fetch(`${API_BASE}/api/history/session/${sessionId}`);
    if (!res.ok) throw new Error("Failed to fetch details");
    const data = await res.json();

    if (!data.success || !data.session) return;

    const s = data.session;
    historyDom.modalSessionId.textContent = `#${s.id}`;
    historyDom.modalSessionDate.textContent = s.start_time ? new Date(s.start_time).toLocaleString() : "—";
    historyDom.modalSessionDuration.textContent = s.duration_seconds ? `${Math.floor(s.duration_seconds / 60)}m ${s.duration_seconds % 60}s` : "Active";
    historyDom.modalAlertsCount.textContent = s.total_alerts;

    let alertHtml = "";
    if (data.alerts && data.alerts.length > 0) {
      data.alerts.forEach((a) => {
        const timeStr = a.timestamp ? new Date(a.timestamp).toLocaleTimeString() : "";
        alertHtml += `
          <div class="alert-entry">
            <div class="alert-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/>
                <line x1="12" y1="9" x2="12" y2="13"/>
                <line x1="12" y1="17" x2="12.01" y2="17"/>
              </svg>
            </div>
            <div class="alert-body">
              <div class="alert-type">${escapeHtml(a.alert_type)}</div>
              <div class="alert-msg">${escapeHtml(a.message)}</div>
            </div>
            <div class="alert-time">${escapeHtml(timeStr)}</div>
          </div>
        `;
      });
    } else {
      alertHtml = `<p style="color: var(--text-muted); text-align: center; padding: 1rem;">No alerts recorded for this session.</p>`;
    }

    historyDom.modalAlertList.innerHTML = alertHtml;
    historyDom.modal.classList.add("visible");
  } catch (err) {
    showToast("Failed to load session details", "warning");
  }
}

if (historyDom.btnCloseModal) {
  historyDom.btnCloseModal.addEventListener("click", () => {
    historyDom.modal.classList.remove("visible");
  });
}

if (historyDom.modal) {
  historyDom.modal.addEventListener("click", (e) => {
    if (e.target === historyDom.modal) {
      historyDom.modal.classList.remove("visible");
    }
  });
}

if (historyDom.btnRefresh) {
  historyDom.btnRefresh.addEventListener("click", fetchSessionHistory);
}

// Log Rest Break Click Handler
if (dom.btnLogBreak) {
  dom.btnLogBreak.addEventListener("click", async () => {
    try {
      const res = await fetch(API_BASE + "/api/log_break", { method: "POST" });
      if (res.ok) {
        showToast("Rest break logged! Continuous drive timer reset.", "success");
      }
    } catch (err) {
      showToast("Failed to log rest break.", "warning");
    }
  });
}

// ── Driver Authentication & Switch Driver Logic ──
if (dom.btnSwitchDriver) {
  dom.btnSwitchDriver.addEventListener("click", () => {
    localStorage.removeItem("driveguard_driver");
    window.location.href = "/login";
  });
}

if (dom.selectDriver) {
  dom.selectDriver.addEventListener("change", (e) => {
    const isNew = e.target.value === "NEW";
    if (dom.groupDriverCode) dom.groupDriverCode.style.display = isNew ? "flex" : "none";
    if (dom.groupDriverName) dom.groupDriverName.style.display = isNew ? "flex" : "none";
    if (dom.groupVehicleReg) dom.groupVehicleReg.style.display = isNew ? "flex" : "none";
  });
}

if (dom.loginForm) {
  dom.loginForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const selectedVal = dom.selectDriver.value;
    const pin = dom.inputPin.value || "1234";

    try {
      let endpoint = "/api/driver/login";
      let payload = {};

      if (selectedVal === "NEW") {
        endpoint = "/api/driver/create";
        payload = {
          driver_code: dom.inputDriverCode.value.trim(),
          name: dom.inputDriverName.value.trim(),
          vehicle_reg: dom.inputVehicleReg.value.trim() || "TRK-904",
          pin: pin
        };
      } else {
        payload = {
          driver_code: selectedVal,
          pin: pin
        };
      }

      const res = await fetch(API_BASE + endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const data = await res.json();

      if (res.ok && data.success) {
        showToast(data.message || "Driver authenticated!", "success");
        if (dom.loginModal) dom.loginModal.classList.remove("visible");
        pollStatus();
      } else {
        showToast(data.message || "Authentication failed", "warning");
      }
    } catch (err) {
      showToast("Authentication error — check server", "warning");
    }
  });
}

// Initial fetch & periodical refresh for session history
fetchSessionHistory();
setInterval(fetchSessionHistory, 10000);

// ================================================================
// FLOATING COMMAND DOCK & SIMULATION SANDBOX (Tesla & Fleet Command)
// ================================================================

// ── Audio Cockpit Alert Synthesizer ──
let audioEnabled = true;
let audioCtx = null;

function playCockpitBeep(type = "warning") {
  if (!audioEnabled) return;
  try {
    if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    if (audioCtx.state === "suspended") audioCtx.resume();
    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();
    osc.connect(gain);
    gain.connect(audioCtx.destination);

    if (type === "critical") {
      osc.type = "sawtooth";
      osc.frequency.setValueAtTime(880, audioCtx.currentTime);
      osc.frequency.exponentialRampToValueAtTime(440, audioCtx.currentTime + 0.22);
      gain.gain.setValueAtTime(0.12, audioCtx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.22);
      osc.start();
      osc.stop(audioCtx.currentTime + 0.22);
    } else {
      osc.type = "sine";
      osc.frequency.setValueAtTime(587.33, audioCtx.currentTime);
      gain.gain.setValueAtTime(0.08, audioCtx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.15);
      osc.start();
      osc.stop(audioCtx.currentTime + 0.15);
    }
  } catch (e) {}
}

// ── Audio Toggle Button ──
if (dom.dockBtnAudio) {
  dom.dockBtnAudio.addEventListener("click", () => {
    audioEnabled = !audioEnabled;
    dom.dockAudioIcon.textContent = audioEnabled ? "🔊" : "🔇";
    dom.dockAudioLabel.textContent = audioEnabled ? "AUDIO: ON" : "AUDIO: MUTE";
    dom.dockBtnAudio.classList.toggle("active", audioEnabled);
    showToast(audioEnabled ? "Cockpit Audio Alerts Enabled" : "Cockpit Audio Muted", "info");
  });
}

// ── Camera Vision Mode Cycler ──
const visionModes = ["RGB", "NIGHT", "THERMAL", "MATRIX"];
let currentVisionIndex = 0;

if (dom.dockBtnVision) {
  dom.dockBtnVision.addEventListener("click", () => {
    currentVisionIndex = (currentVisionIndex + 1) % visionModes.length;
    const mode = visionModes[currentVisionIndex];
    if (dom.dockVisionLabel) dom.dockVisionLabel.textContent = `MODE: ${mode}`;

    if (dom.cameraFeed) {
      dom.cameraFeed.classList.remove("filter-night-vision", "filter-thermal", "filter-matrix");
      if (mode === "NIGHT") dom.cameraFeed.classList.add("filter-night-vision");
      else if (mode === "THERMAL") dom.cameraFeed.classList.add("filter-thermal");
      else if (mode === "MATRIX") dom.cameraFeed.classList.add("filter-matrix");
    }

    if (dom.cameraWrapper) {
      dom.cameraWrapper.classList.toggle("mode-night-vision", mode === "NIGHT");
    }

    if (dom.hudVisionPill) {
      if (mode === "NIGHT") {
        dom.hudVisionPill.textContent = "🌙 NIGHT VISION (NIR-940nm)";
        dom.hudVisionPill.style.color = "#10b981";
        dom.hudVisionPill.style.borderColor = "rgba(16, 185, 129, 0.6)";
        dom.hudVisionPill.style.boxShadow = "0 0 10px rgba(16, 185, 129, 0.35)";
      } else if (mode === "THERMAL") {
        dom.hudVisionPill.textContent = "🔥 THERMAL SPECTRUM";
        dom.hudVisionPill.style.color = "#ff3366";
        dom.hudVisionPill.style.borderColor = "rgba(255, 51, 102, 0.6)";
        dom.hudVisionPill.style.boxShadow = "0 0 10px rgba(255, 51, 102, 0.35)";
      } else if (mode === "MATRIX") {
        dom.hudVisionPill.textContent = "⚡ MATRIX HUD";
        dom.hudVisionPill.style.color = "#00f0ff";
        dom.hudVisionPill.style.borderColor = "rgba(0, 240, 255, 0.6)";
        dom.hudVisionPill.style.boxShadow = "0 0 10px rgba(0, 240, 255, 0.35)";
      } else {
        dom.hudVisionPill.textContent = "MODE: RGB";
        dom.hudVisionPill.style.color = "";
        dom.hudVisionPill.style.borderColor = "";
        dom.hudVisionPill.style.boxShadow = "";
      }
    }

    showToast(`Camera HUD Vision Mode: ${mode === "NIGHT" ? "🌙 Tactical Night Vision" : mode}`, "info");
  });
}

// ── Quick Reset Button on Dock ──
if (dom.dockBtnReset) {
  dom.dockBtnReset.addEventListener("click", () => {
    if (dom.btnReset) dom.btnReset.click();
  });
}

// ── Fullscreen Button on Dock ──
if (dom.dockBtnFullscreen) {
  dom.dockBtnFullscreen.addEventListener("click", () => {
    if (dom.btnFullscreen) dom.btnFullscreen.click();
  });
}

// ── Simulation Drawer Open / Close ──
if (dom.dockBtnSim) {
  dom.dockBtnSim.addEventListener("click", () => {
    if (dom.sandboxDrawer) {
      dom.sandboxDrawer.classList.toggle("visible");
      dom.dockBtnSim.classList.toggle("active", dom.sandboxDrawer.classList.contains("visible"));
    }
  });
}

if (dom.btnCloseSandbox) {
  dom.btnCloseSandbox.addEventListener("click", () => {
    if (dom.sandboxDrawer) dom.sandboxDrawer.classList.remove("visible");
    if (dom.dockBtnSim) dom.dockBtnSim.classList.remove("active");
  });
}

// ── Interactive Simulation Actions (Viva Demo Mode) ──
let isSimulationActive = false;
let simTimer = null;

document.querySelectorAll(".btn-sim-action").forEach((btn) => {
  btn.addEventListener("click", () => {
    const trigger = btn.getAttribute("data-trigger");
    triggerSimulation(trigger);
  });
});

function triggerSimulation(type) {
  if (type === "clear") {
    isSimulationActive = false;
    clearTimeout(simTimer);
    showToast("Live AI Vision Monitoring Restored", "success");
    pollStatus();
    return;
  }

  isSimulationActive = true;
  clearTimeout(simTimer);

  let simData = {};
  if (type === "drowsy") {
    simData = {
      face: "FACE DETECTED",
      drowsiness: true,
      yawning: false,
      phone: false,
      attention: "CENTER",
      ear: 0.14,
      mouth_ratio: 0.08,
      mouth_width: 0.32,
      alert_stage: 2,
      alert_level: "CRITICAL",
      is_mirror_check: false,
      score: 82,
      grade: "B",
      drive_duration_formatted: "01h 45m 12s",
      break_progress_percent: 65
    };
    showToast("🚨 Simulation: Critical Drowsiness Triggered!", "warning");
    playCockpitBeep("critical");
  } else if (type === "phone") {
    simData = {
      face: "FACE DETECTED",
      drowsiness: false,
      yawning: false,
      phone: true,
      attention: "CENTER",
      ear: 0.32,
      mouth_ratio: 0.11,
      mouth_width: 0.33,
      alert_stage: 2,
      alert_level: "CRITICAL",
      is_mirror_check: false,
      score: 85,
      grade: "B",
      drive_duration_formatted: "01h 45m 12s",
      break_progress_percent: 65
    };
    showToast("📱 Simulation: Phone Usage Triggered!", "warning");
    playCockpitBeep("critical");
  } else if (type === "yawn") {
    simData = {
      face: "FACE DETECTED",
      drowsiness: false,
      yawning: true,
      phone: false,
      attention: "CENTER",
      ear: 0.28,
      mouth_ratio: 0.44,
      mouth_width: 0.22,
      alert_stage: 1,
      alert_level: "WARNING",
      is_mirror_check: false,
      score: 93,
      grade: "A",
      drive_duration_formatted: "01h 45m 12s",
      break_progress_percent: 65
    };
    showToast("🥱 Simulation: Yawning Episode Triggered!", "warning");
    playCockpitBeep("warning");
  } else if (type === "distract") {
    simData = {
      face: "FACE DETECTED",
      drowsiness: false,
      yawning: false,
      phone: false,
      attention: "RIGHT",
      distraction_duration: 2.2,
      ear: 0.31,
      mouth_ratio: 0.10,
      mouth_width: 0.34,
      alert_stage: 2,
      alert_level: "CRITICAL",
      is_mirror_check: false,
      score: 88,
      grade: "B",
      drive_duration_formatted: "01h 45m 12s",
      break_progress_percent: 65
    };
    showToast("👀 Simulation: Off-Road Distraction Triggered!", "warning");
    playCockpitBeep("critical");
  } else if (type === "mirror") {
    simData = {
      face: "FACE DETECTED",
      drowsiness: false,
      yawning: false,
      phone: false,
      attention: "LEFT",
      distraction_duration: 0.7,
      ear: 0.32,
      mouth_ratio: 0.10,
      mouth_width: 0.33,
      alert_stage: 0,
      alert_level: "MIRROR_CHECK",
      is_mirror_check: true,
      mirror_direction: "LEFT",
      score: 98,
      grade: "A",
      drive_duration_formatted: "01h 45m 12s",
      break_progress_percent: 65
    };
    showToast("🔍 Simulation: Mirror Check Glance (No False Alarm)", "info");
  }

  processStatus(simData);

  // Auto clear simulation after 7 seconds
  simTimer = setTimeout(() => {
    isSimulationActive = false;
  }, 7000);
}


