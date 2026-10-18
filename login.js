/* ==============================================
   DriveGuard AI — Standalone Login Page Logic
   ============================================== */

const API_BASE = "";

document.addEventListener("DOMContentLoaded", () => {
  const tabSignIn = document.getElementById("tabSignIn");
  const tabRegister = document.getElementById("tabRegister");
  const formSignIn = document.getElementById("formSignIn");
  const formRegister = document.getElementById("formRegister");
  const loginDriverSelect = document.getElementById("loginDriverSelect");

  // Tab switching
  if (tabSignIn && tabRegister) {
    tabSignIn.addEventListener("click", () => {
      tabSignIn.classList.add("active");
      tabRegister.classList.remove("active");
      formSignIn.style.display = "flex";
      formRegister.style.display = "none";
    });

    tabRegister.addEventListener("click", () => {
      tabRegister.classList.add("active");
      tabSignIn.classList.remove("active");
      formRegister.style.display = "flex";
      formSignIn.style.display = "none";
    });
  }

  // Load registered drivers into select dropdown
  async function loadDrivers() {
    if (!loginDriverSelect) return;
    try {
      const res = await fetch(API_BASE + "/api/drivers");
      if (!res.ok) return;
      const data = await res.json();

      if (data.success && data.drivers && data.drivers.length > 0) {
        let optionsHtml = "";
        data.drivers.forEach((d) => {
          optionsHtml += `<option value="${d.driver_code}">${d.name} (${d.driver_code}) — ${d.vehicle_reg || 'TRK-904'}</option>`;
        });
        loginDriverSelect.innerHTML = optionsHtml;
      }
    } catch (err) {
      console.warn("Could not load drivers from API:", err);
    }
  }

  loadDrivers();

  // Sign In submit
  if (formSignIn) {
    formSignIn.addEventListener("submit", async (e) => {
      e.preventDefault();
      const driverCode = loginDriverSelect.value;
      const pin = document.getElementById("loginPin").value || "1234";

      try {
        const res = await fetch(API_BASE + "/api/driver/login", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ driver_code: driverCode, pin: pin })
        });
        const data = await res.json();

        if (res.ok && data.success) {
          if (data.driver) {
            localStorage.setItem("driveguard_driver", JSON.stringify(data.driver));
          }
          window.location.href = "/dashboard";
        } else {
          alert(data.message || "Invalid Driver Code or PIN!");
        }
      } catch (err) {
        alert("Server connection error. Launching fallback session.");
        window.location.href = "/dashboard";
      }
    });
  }

  // Register submit
  if (formRegister) {
    formRegister.addEventListener("submit", async (e) => {
      e.preventDefault();
      const driverCode = document.getElementById("regDriverCode").value.trim();
      const name = document.getElementById("regDriverName").value.trim();
      const vehicleReg = document.getElementById("regVehicleReg").value.trim() || "TRK-904";
      const pin = document.getElementById("regPin").value.trim() || "1234";

      try {
        const res = await fetch(API_BASE + "/api/driver/create", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            driver_code: driverCode,
            name: name,
            vehicle_reg: vehicleReg,
            pin: pin
          })
        });
        const data = await res.json();

        if (res.ok && data.success) {
          if (data.driver) {
            localStorage.setItem("driveguard_driver", JSON.stringify(data.driver));
          }
          window.location.href = "/dashboard";
        } else {
          alert(data.message || "Failed to register driver profile");
        }
      } catch (err) {
        alert("Server connection error.");
      }
    });
  }
});
