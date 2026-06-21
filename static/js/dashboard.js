/**
 * dashboard.js - Handles dashboard loading, UI metric mapping,
 * SVG budget ring animation, and horizontal breakdown bar rendering.
 */

class DashboardManager {
    constructor() {
        this.dashboardData = null;
        // Circumference of the budget ring: 2 * π * 100 ≈ 628.3
        this.RING_CIRCUMFERENCE = 628.3;
    }

    /**
     * Fetch the daily dashboard carbon breakdown and render statistics.
     */
    async loadDashboard() {
        try {
            const data = await apiFetch("/api/dashboard");
            this.dashboardData = data;
            this.renderDashboard();
        } catch (error) {
            console.error("Failed to load dashboard data:", error);
            // Graceful degradation
            const el = document.getElementById("dashboard-total-emissions");
            if (el) el.textContent = "--";
        }
    }

    /**
     * Render the active metrics on the screen: SVG ring, breakdown bars, and values.
     */
    renderDashboard() {
        if (!this.dashboardData) return;

        const data = this.dashboardData;
        const duration = (state && state.prefersReducedMotion) ? 0 : 1.5;

        // 1. Update total emissions number (counting up via GSAP)
        const emissionsVal = document.getElementById("dashboard-total-emissions");
        if (emissionsVal) {
            const currentVal = parseFloat(emissionsVal.textContent) || 0;
            const obj = { value: currentVal };
            gsap.killTweensOf(obj);
            gsap.to(obj, {
                value: data.total_co2_kg,
                duration: duration,
                ease: "power3.out",
                onUpdate: () => {
                    emissionsVal.textContent = obj.value.toFixed(2);
                }
            });
        }

        // 2. Update budget ratio text
        const budgetRatio = document.getElementById("dashboard-budget-ratio");
        if (budgetRatio) {
            budgetRatio.textContent = `${data.budget_pct.toFixed(1)}% of your ${data.budget_kg}kg budget`;
            if (data.over_budget) {
                budgetRatio.classList.add("over-budget");
            } else {
                budgetRatio.classList.remove("over-budget");
            }
        }

        // 3. Animate the confidence semicircular dial (GSAP strokeDashoffset tween)
        const confFill = document.getElementById("confidence-dial-fill");
        const confNum = document.getElementById("confidence-percentage-num");
        if (confFill && confNum) {
            const clarityPct = data.sky_gauge_clarity_pct || 0;
            const dialCircumference = 251.3;
            const targetOffset = dialCircumference * (1 - clarityPct / 100);

            gsap.killTweensOf(confFill);

            // Set initial state to full dashoffset (empty dial) then animate fill
            gsap.fromTo(confFill,
                { strokeDashoffset: dialCircumference },
                {
                    strokeDashoffset: targetOffset,
                    duration: duration,
                    ease: "power3.out"
                }
            );

            // Animate count-up of percentage text
            const currentPct = parseInt(confNum.textContent) || 0;
            const pctObj = { value: currentPct };
            gsap.killTweensOf(pctObj);
            gsap.to(pctObj, {
                value: clarityPct,
                duration: duration,
                ease: "power3.out",
                onUpdate: () => {
                    confNum.textContent = `${Math.round(pctObj.value)}%`;
                }
            });
        }

        // 4. Update category values, confidence accent styles, and confidence footer labels
        const categories = ["transport", "food", "energy"];

        categories.forEach(cat => {
            const valEl = document.getElementById(`value-${cat}`);
            const badgeEl = document.getElementById(`conf-badge-${cat}`);
            const cardEl = document.getElementById(`card-${cat}`);
            const catData = data.categories[cat];

            // Update emission value (counting up via GSAP)
            if (valEl && catData) {
                const currentCatVal = parseFloat(valEl.textContent) || 0;
                const catObj = { value: currentCatVal };
                gsap.killTweensOf(catObj);
                gsap.to(catObj, {
                    value: catData.co2_kg,
                    duration: duration,
                    ease: "power3.out",
                    onUpdate: () => {
                        valEl.textContent = catObj.value.toFixed(2);
                    }
                });
            }

            // Update confidence accent class on card (confirmed=green, estimated=grey)
            if (catData) {
                const tier = catData.confidence.toLowerCase();
                const isConfirmed = (tier === "high" || tier === "medium");

                if (cardEl) {
                    if (isConfirmed) {
                        cardEl.classList.add("confirmed");
                        cardEl.classList.remove("estimated");
                    } else {
                        cardEl.classList.add("estimated");
                        cardEl.classList.remove("confirmed");
                    }
                }

                // Update text label inside card footer
                if (badgeEl) {
                    badgeEl.textContent = isConfirmed ? "Confirmed" : "Estimated";
                }
            }
        });
    }

    /**
     * Confirm today's default baseline profile on the backend (Log Standard Day).
     */
    async confirmUsualDay() {
        const confirmBtn = document.getElementById("dashboard-usual-day-btn");
        if (confirmBtn) confirmBtn.disabled = true;

        try {
            const data = await apiFetch("/api/event/confirm_baseline", {
                method: "POST"
            });
            if (data.status === "baseline confirmed") {
                // Refresh dashboard to show high confidence scores
                await this.loadDashboard();
            }
        } catch (error) {
            console.error("Failed to confirm baseline usual day:", error);
            alert(`Could not confirm usual day: ${error.message}`);
        } finally {
            if (confirmBtn) confirmBtn.disabled = false;
        }
    }
}

// Instantiate and bind dashboard manager
window.dashboardManager = new DashboardManager();

// Bind dashboard button triggers
document.addEventListener("DOMContentLoaded", () => {
    const usualDayBtn = document.getElementById("dashboard-usual-day-btn");
    if (usualDayBtn) {
        usualDayBtn.addEventListener("click", () => window.dashboardManager.confirmUsualDay());
    }
});
