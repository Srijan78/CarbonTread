/**
 * logger.js - Manages the bottom-sheet Event Logger.
 * Handles category sub-forms, AI text extraction, and counterfactual compare animations.
 */

class LoggerManager {
    constructor() {
        this.activeCategory = "transport";
        this.activeMethod = "manual"; // "manual" or "ai"
    }

    /**
     * Open the bottom sheet and reset form states.
     */
    openLogger() {
        const backdrop = document.getElementById("logger-backdrop");
        const sheet = document.getElementById("logger-sheet");
        const prefersMotion = state && state.prefersReducedMotion;
        if (backdrop && sheet) {
            backdrop.classList.add("open");
            sheet.classList.add("open");

            gsap.killTweensOf([backdrop, sheet]);
            const backdropDuration = prefersMotion ? 0 : 0.3;
            const sheetDuration = prefersMotion ? 0 : 0.4;
            const sheetStartScale = prefersMotion ? 1 : 0.9;
            gsap.fromTo(backdrop, { opacity: 0 }, { opacity: 1, duration: backdropDuration, ease: "power2.out" });
            gsap.fromTo(sheet, 
                { opacity: 0, scale: sheetStartScale }, 
                { opacity: 1, scale: 1, duration: sheetDuration, ease: prefersMotion ? "none" : "back.out(1.2)" }
            );
        }
        
        // Hide comparison display initially
        const cfDisplay = document.getElementById("counterfactual-display");
        if (cfDisplay) cfDisplay.style.display = "none";
        
        this.resetForms();
    }

    /**
     * Close the bottom sheet and update metrics.
     */
    closeLogger() {
        const backdrop = document.getElementById("logger-backdrop");
        const sheet = document.getElementById("logger-sheet");
        const prefersMotion = state && state.prefersReducedMotion;
        if (backdrop && sheet) {
            gsap.killTweensOf([backdrop, sheet]);
            const duration = prefersMotion ? 0 : 0.25;
            gsap.to(backdrop, { opacity: 0, duration: duration, ease: "power2.in" });
            gsap.to(sheet, { 
                opacity: 0, 
                scale: prefersMotion ? 1 : 0.9, 
                duration: duration, 
                ease: "power2.in",
                onComplete: () => {
                    backdrop.classList.remove("open");
                    sheet.classList.remove("open");
                }
            });
        }
        // Always reload dashboard when logger closes to sync changes
        if (window.dashboardManager) {
            window.dashboardManager.loadDashboard();
        }
    }

    /**
     * Reset form fields and selections to default.
     */
    resetForms() {
        // Reset manual forms
        document.getElementById("form-transport").reset();
        document.getElementById("form-food").reset();
        document.getElementById("form-energy").reset();
        document.getElementById("ai-text-input").value = "";
        
        // Ensure transport is active default
        this.setCategory("transport");
        this.setMethod("manual");
        this.toggleFuelTypeVisibility();
    }

    /**
     * Set active logging category (transport, food, energy).
     */
    setCategory(category) {
        this.activeCategory = category;

        // Toggle category select button states
        const buttons = document.querySelectorAll(".cat-select-btn");
        buttons.forEach(btn => {
            if (btn.getAttribute("data-category") === category) {
                btn.classList.add("active");
            } else {
                btn.classList.remove("active");
            }
        });

        // Show active category subform
        const forms = document.querySelectorAll(".logger-form");
        forms.forEach(form => {
            if (form.id === `form-${category}`) {
                form.classList.add("active");
            } else {
                form.classList.remove("active");
            }
        });
    }

    /**
     * Set logging method (structured vs AI free text).
     */
    setMethod(method) {
        this.activeMethod = method;
        const manualBtn = document.getElementById("method-manual-btn");
        const aiBtn = document.getElementById("method-ai-btn");
        const manualSection = document.getElementById("logger-manual-section");
        const aiSection = document.getElementById("logger-ai-section");

        if (method === "manual") {
            if (manualSection) {
                manualSection.style.display = "block";
                setTimeout(() => manualSection.classList.add("visible"), 20);
            }
            if (aiSection) {
                aiSection.classList.remove("visible");
                aiSection.style.display = "none";
            }
            
            if (manualBtn) {
                manualBtn.classList.add("active");
            }
            if (aiBtn) {
                aiBtn.classList.remove("active");
            }
        } else {
            if (manualSection) {
                manualSection.classList.remove("visible");
                manualSection.style.display = "none";
            }
            if (aiSection) {
                aiSection.style.display = "flex";
                setTimeout(() => aiSection.classList.add("visible"), 20);
            }
            
            if (aiBtn) {
                aiBtn.classList.add("active");
            }
            if (manualBtn) {
                manualBtn.classList.remove("active");
            }
        }
    }

    /**
     * Conditionally display fuel type select depending on transport mode.
     */
    toggleFuelTypeVisibility() {
        const mode = document.getElementById("commute-mode").value;
        const fuelContainer = document.getElementById("fuel-type-container");
        if (mode === "car" || mode === "uber_ola") {
            fuelContainer.style.display = "flex";
        } else {
            fuelContainer.style.display = "none";
        }
    }

    /**
     * Handle manual structured form submissions.
     */
    async handleManualSubmit(e) {
        e.preventDefault();
        
        let payload = { category: this.activeCategory };

        if (this.activeCategory === "transport") {
            const mode = document.getElementById("commute-mode").value;
            const distance = parseFloat(document.getElementById("commute-distance").value);
            const fuel = document.getElementById("commute-fuel").value;
            
            payload.subtype = mode;
            payload.value = distance;
            payload.unit = "km";
            if (mode === "car" || mode === "uber_ola") {
                payload.fuel_type = fuel;
            }
        } else if (this.activeCategory === "food") {
            const choice = document.getElementById("food-pattern-choice").value;
            
            payload.subtype = choice;
            payload.value = 1;
            payload.unit = "day";
        } else if (this.activeCategory === "energy") {
            const subtype = document.getElementById("energy-subtype").value;
            const val = parseFloat(document.getElementById("energy-value").value);
            
            payload.subtype = subtype;
            payload.value = val;
            
            // Map units based on subtype
            const unitMap = {
                electricity_bill: "kWh",
                lpg_refill: "cylinder",
                png_usage: "m3",
                ac_usage: "hours"
            };
            payload.unit = unitMap[subtype] || "units";
        }

        try {
            const response = await apiFetch("/api/event/log", {
                method: "POST",
                body: payload
            });

            // If transport comparison exists, show counterfactual animations
            if (response.counterfactual) {
                this.renderCounterfactual(response.counterfactual, payload.subtype, payload.value);
            } else {
                this.closeLogger();
            }
        } catch (error) {
            console.error("Log submission failed:", error);
            alert(`Log failed: ${error.message}`);
        }
    }

    /**
     * Parse and submit unstructured free text.
     */
    async handleAISubmit() {
        const text = document.getElementById("ai-text-input").value.trim();
        if (!text) {
            alert("Please enter a description of your activity.");
            return;
        }

        const submitBtn = document.getElementById("ai-submit-btn");
        submitBtn.disabled = true;
        submitBtn.textContent = "Extracting details...";

        try {
            await apiFetch("/api/event/extract", {
                method: "POST",
                body: { text: text }
            });

            this.closeLogger();
        } catch (error) {
            console.error("AI extraction failed:", error);
            alert(`Extraction Error: ${error.message}`);
        } finally {
            submitBtn.disabled = false;
            submitBtn.textContent = "Extract & Log Activity";
        }
    }

    /**
     * Draw the counterfactual comparison horizontal bars and trigger the settle animation.
     */
    renderCounterfactual(cf, mode, distance) {
        const cfDisplay = document.getElementById("counterfactual-display");
        const container = document.getElementById("counterfactual-bars-container");
        const summary = document.getElementById("counterfactual-savings-summary");
        const prefersMotion = state && state.prefersReducedMotion;

        if (!cfDisplay || !container || !summary) return;

        cfDisplay.style.display = "block";
        container.innerHTML = "";

        const maxCO2 = Math.max(cf.car_co2, cf.metro_co2, cf.bus_co2) || 1.0;
        
        // Define bar configurations
        const bars = [
            { label: `Your Trip (${mode})`, value: cf.car_co2, class: "original" },
            { label: "Metro Alternative", value: cf.metro_co2, class: "alt" },
            { label: "Bus Alternative", value: cf.bus_co2, class: "alt" }
        ];

        bars.forEach((bar, idx) => {
            const targetPct = Math.round((bar.value / maxCO2) * 100);
            
            const row = document.createElement("div");
            row.className = "cf-row";
            row.innerHTML = `
                <div class="cf-label-row">
                    <span>${bar.label}</span>
                    <span class="mono">${bar.value.toFixed(2)} kg</span>
                </div>
                <div class="cf-bar-track">
                    <div class="cf-bar ${bar.class}" style="width: 0%;"></div>
                </div>
            `;
            container.appendChild(row);

            // GSAP bar width expand animation
            const barEl = row.querySelector(".cf-bar");
            if (barEl) {
                gsap.fromTo(barEl, 
                    { width: "0%" }, 
                    { 
                        width: `${targetPct}%`, 
                        duration: prefersMotion ? 0 : 0.8, 
                        ease: "power2.out", 
                        delay: prefersMotion ? 0 : (0.1 + idx * 0.1)
                    }
                );
            }
        });

        // Set static savings helper
        const maxSaved = Math.max(cf.metro_saved, cf.bus_saved);
        if (maxSaved > 0) {
            summary.textContent = `By choosing Metro or Bus, you could save up to ${maxSaved.toFixed(2)} kg CO2 on this trip.`;
            summary.style.display = "block";
            // Animate details fade-in
            gsap.fromTo(summary, { opacity: 0 }, { opacity: 1, duration: prefersMotion ? 0 : 0.4, delay: prefersMotion ? 0 : 0.5 });
        } else {
            summary.style.display = "none";
        }
    }
}

// Instantiate and bind logger manager
window.loggerManager = new LoggerManager();

// Bind bottom sheet UI listeners
document.addEventListener("DOMContentLoaded", () => {
    const backdrop = document.getElementById("logger-backdrop");
    const openBtn = document.getElementById("dashboard-open-logger-btn");
    const closeBtn = document.getElementById("logger-close-btn");

    if (openBtn) openBtn.addEventListener("click", () => window.loggerManager.openLogger());
    if (closeBtn) closeBtn.addEventListener("click", () => window.loggerManager.closeLogger());
    if (backdrop) backdrop.addEventListener("click", () => window.loggerManager.closeLogger());

    // Category selectors
    const catBtns = document.querySelectorAll(".cat-select-btn");
    catBtns.forEach(btn => {
        btn.addEventListener("click", () => {
            const cat = btn.getAttribute("data-category");
            window.loggerManager.setCategory(cat);
        });
    });

    // Method selectors
    const manualBtn = document.getElementById("method-manual-btn");
    const aiBtn = document.getElementById("method-ai-btn");
    if (manualBtn) manualBtn.addEventListener("click", () => window.loggerManager.setMethod("manual"));
    if (aiBtn) aiBtn.addEventListener("click", () => window.loggerManager.setMethod("ai"));

    // Commute mode changer (fuel visibility)
    const commuteModeSelect = document.getElementById("commute-mode");
    if (commuteModeSelect) {
        commuteModeSelect.addEventListener("change", () => window.loggerManager.toggleFuelTypeVisibility());
    }

    // Energy subtype label updater
    const energySelect = document.getElementById("energy-subtype");
    const energyLabel = document.getElementById("energy-value-label");
    if (energySelect && energyLabel) {
        energySelect.addEventListener("change", () => {
            const sub = energySelect.value;
            if (sub === "electricity_bill") {
                energyLabel.textContent = "Units Consumed (kWh)";
            } else if (sub === "lpg_refill") {
                energyLabel.textContent = "Number of Cylinders (14.2kg)";
            } else if (sub === "png_usage") {
                energyLabel.textContent = "SCM / Piped Gas Quantity (m³)";
            } else if (sub === "ac_usage") {
                energyLabel.textContent = "Duration Used (Hours)";
            }
        });
    }

    // Submit handlers
    const transForm = document.getElementById("form-transport");
    const foodForm = document.getElementById("form-food");
    const energyForm = document.getElementById("form-energy");

    if (transForm) transForm.addEventListener("submit", (e) => window.loggerManager.handleManualSubmit(e));
    if (foodForm) foodForm.addEventListener("submit", (e) => window.loggerManager.handleManualSubmit(e));
    if (energyForm) energyForm.addEventListener("submit", (e) => window.loggerManager.handleManualSubmit(e));

    const aiSubmitBtn = document.getElementById("ai-submit-btn");
    if (aiSubmitBtn) aiSubmitBtn.addEventListener("click", () => window.loggerManager.handleAISubmit());
});
