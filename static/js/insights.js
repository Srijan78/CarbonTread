/**
 * insights.js - Controls the insights tab view.
 * Handles confidence data quality reporting, warning nudges, and weekly field log narratives.
 */

class InsightsManager {
    constructor() {
        this.confidenceData = null;
        this.narrativeData = null;
    }

    /**
     * Load confidence reports and narrative stories.
     */
    async loadInsights() {
        await Promise.all([
            this.loadConfidenceReport(),
            this.loadWeeklyStory()
        ]);
    }

    /**
     * Retrieve confidence metrics and draw the warning nudge box.
     */
    async loadConfidenceReport() {
        try {
            const data = await apiFetch("/api/insights/confidence");
            this.confidenceData = data;
            this.renderConfidenceReport();
        } catch (error) {
            console.error("Failed to load confidence report:", error);
        }
    }

    /**
     * Update the HTML table rows and append active warnings for LOW confidence categories.
     */
    renderConfidenceReport() {
        if (!this.confidenceData) return;

        const data = this.confidenceData.categories;
        const nudgeBox = document.getElementById("insights-nudge-box");
        if (nudgeBox) nudgeBox.innerHTML = "";

        const categories = ["transport", "food", "energy"];
        categories.forEach(cat => {
            const badge = document.getElementById(`report-conf-${cat}`);
            const source = document.getElementById(`report-source-${cat}`);
            const catData = data[cat];

            if (badge && catData) {
                const tier = catData.confidence.toLowerCase();
                const isConfirmed = (tier === "high" || tier === "medium");
                badge.textContent = isConfirmed ? "Confirmed" : "Estimated";
                badge.className = "confidence-chip " + (isConfirmed ? "confirmed" : "estimated");
            }

            if (source && catData) {
                source.textContent = catData.source;
            }

            // Append warning nudges for LOW tracking categories
            if (nudgeBox && catData && catData.confidence === "LOW") {
                const nudgeDiv = document.createElement("div");
                nudgeDiv.className = "nudge-text animate-fade-in";
                nudgeDiv.style.setProperty("--i", nudgeBox.children.length);
                nudgeDiv.style.padding = "12px 16px";
                nudgeDiv.style.backgroundColor = "rgba(15, 23, 42, 0.02)";
                nudgeDiv.style.borderLeft = "3px solid var(--text-muted)";
                nudgeDiv.style.borderRadius = "4px";
                nudgeDiv.innerHTML = `<strong>${cat.toUpperCase()}:</strong> ${catData.nudge}`;
                nudgeBox.appendChild(nudgeDiv);
            }
        });
    }

    /**
     * Pick an emoji icon based on keywords in the bullet header text.
     */
    _bulletIcon(headerText) {
        const h = (headerText || "").toLowerCase();
        if (h.includes("transport") || h.includes("commut") || h.includes("travel") || h.includes("metro") || h.includes("transit")) return "🚇";
        if (h.includes("diet") || h.includes("food") || h.includes("eat") || h.includes("vegetarian") || h.includes("vegan")) return "🥗";
        if (h.includes("energy") || h.includes("home") || h.includes("electric") || h.includes("gas") || h.includes("lpg") || h.includes("ac") || h.includes("cooling")) return "⚡";
        if (h.includes("summary") || h.includes("week") || h.includes("overall") || h.includes("footprint")) return "📊";
        if (h.includes("track") || h.includes("quality") || h.includes("confiden") || h.includes("data")) return "🎯";
        if (h.includes("recommend") || h.includes("tip") || h.includes("action") || h.includes("improve")) return "💡";
        return "📌";
    }

    /**
     * Retrieve cached or newly generated weekly narratives from the backend.
     * Parse the bulleted text and render each bullet as a styled visual card.
     */
    async loadWeeklyStory() {
        const emptyState = document.getElementById("narrative-empty-state");
        const card = document.getElementById("narrative-card");
        const bulletsContainer = document.getElementById("narrative-bullets");

        if (emptyState) {
            emptyState.style.display = "block";
            emptyState.textContent = "Generating your weekly AI summary...";
        }
        if (card) card.style.display = "none";

        try {
            const data = await apiFetch("/api/insights/narrative");
            this.narrativeData = data;

            if (emptyState) emptyState.style.display = "none";

            if (card && bulletsContainer) {
                bulletsContainer.innerHTML = "";

                // Split on bullet character '•' and filter empty strings
                const raw = data.narrative || "";
                const parts = raw.split("•").map(s => s.trim()).filter(Boolean);

                if (parts.length === 0) {
                    // Fallback: show entire text as a single card
                    const fallback = document.createElement("div");
                    fallback.className = "narrative-bullet-card";
                    fallback.innerHTML = `<div class="nbc-icon">📊</div><div class="nbc-body"><p class="nbc-text">${raw}</p></div>`;
                    bulletsContainer.appendChild(fallback);
                } else {
                    parts.forEach((part, idx) => {
                        // Extract bold header from <b>Header:</b> pattern
                        const headerMatch = part.match(/^<b>(.*?)<\/b>\s*/i);
                        let header = "";
                        let body = part;

                        if (headerMatch) {
                            header = headerMatch[1].replace(/:$/, "").trim();
                            body = part.slice(headerMatch[0].length).replace(/<br\/?\s*>/gi, "").trim();
                        } else {
                            // No bold tag — split on first period if it's short enough to be a header
                            const dotIdx = part.indexOf(".");
                            if (dotIdx > 0 && dotIdx < 60) {
                                header = part.slice(0, dotIdx + 1);
                                body = part.slice(dotIdx + 1).trim();
                            } else {
                                body = part.replace(/<br\/?\s*>/gi, "").trim();
                            }
                        }

                        const icon = this._bulletIcon(header || body);

                        const bCard = document.createElement("div");
                        bCard.className = "narrative-bullet-card";
                        bCard.innerHTML = `
                            <div class="nbc-icon">${icon}</div>
                            <div class="nbc-body">
                                ${header ? `<div class="nbc-header">${header}</div>` : ""}
                                <p class="nbc-text">${body}</p>
                            </div>
                        `;
                        bulletsContainer.appendChild(bCard);
                    });
                }

                card.style.display = "block";

                // GSAP stagger entrance animation
                if (typeof gsap !== "undefined") {
                    const prefersMotion = state && state.prefersReducedMotion;
                    gsap.from(".narrative-bullet-card", {
                        opacity: 0,
                        y: prefersMotion ? 0 : 18,
                        duration: prefersMotion ? 0 : 0.45,
                        stagger: prefersMotion ? 0 : 0.13,
                        ease: "power2.out"
                    });
                }
            }
        } catch (error) {
            console.error("Failed to load weekly narrative:", error);
            if (emptyState) {
                emptyState.textContent = `Couldn't load AI summary: ${error.message}. Log more activities to get insights.`;
                emptyState.style.display = "block";
            }
        }
    }
}

// Instantiate and bind insights manager
window.insightsManager = new InsightsManager();
