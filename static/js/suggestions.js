/**
 * suggestions.js - Controls the suggestions tab view.
 * Handles card rendering, impact scaling, and choice responses.
 */

class SuggestionsManager {
    constructor() {
        this.suggestions = [];
    }

    /**
     * Fetch daily recommendations from the database/Gemini.
     */
    async loadSuggestions() {
        const emptyState = document.getElementById("suggestions-empty-state");
        const listContainer = document.getElementById("suggestions-list");

        if (emptyState) {
            emptyState.style.display = "block";
            emptyState.textContent = "Analyzing patterns and generating recommendations...";
        }
        if (listContainer) listContainer.innerHTML = "";

        try {
            const data = await apiFetch("/api/suggestions");
            this.suggestions = data.suggestions || [];
            
            if (emptyState) emptyState.style.display = "none";
            this.renderSuggestions();
        } catch (error) {
            console.error("Failed to load suggestions:", error);
            if (emptyState) {
                emptyState.textContent = `Could not load suggestions: ${error.message}. Using offline recommendations.`;
                emptyState.style.display = "block";
            }
        }
    }

    /**
     * Render the cards list with relative impact bars.
     */
    renderSuggestions() {
        const container = document.getElementById("suggestions-list");
        if (!container) return;

        container.innerHTML = "";

        if (this.suggestions.length === 0) {
            const emptyEl = document.createElement("div");
            emptyEl.style.padding = "32px 16px";
            emptyEl.style.textAlign = "center";
            emptyEl.style.color = "var(--text-muted)";
            emptyEl.textContent = "All caught up! Check back tomorrow for new suggestions.";
            container.appendChild(emptyEl);
            return;
        }

        // Calculate maximum savings to scale relative impact bars
        const maxSaved = Math.max(...this.suggestions.map(s => s.co2_saved_kg)) || 1.0;

        this.suggestions.forEach((s, idx) => {
            const card = document.createElement("div");
            card.className = "suggestion-card";
            card.style.opacity = "0"; // Start hidden for GSAP transition

            const relativePct = Math.round((s.co2_saved_kg / maxSaved) * 100);
            
            // Build difficulty class tag
            const diffClass = `diff-${s.difficulty.toLowerCase()}`;
            
            // Render card structure
            card.innerHTML = `
                <div class="suggestion-header">
                    <div class="suggestion-tags">
                        <span class="tag ${diffClass}">${s.difficulty}</span>
                        <span class="tag" style="text-transform: capitalize;">${s.category}</span>
                    </div>
                    <div class="suggestion-impact-indicator">
                        <span class="impact-label">Impact</span>
                        <div class="impact-track">
                            <div class="impact-bar" style="width: ${relativePct}%;"></div>
                        </div>
                    </div>
                </div>

                <div class="suggestion-body">
                    <span class="suggestion-text">${s.suggestion_text}</span>
                    <span class="suggestion-reasoning">${s.reasoning}</span>
                </div>

                <div class="suggestion-footer">
                    <span class="suggestion-saving mono">${s.co2_saved_kg.toFixed(2)} kg saved</span>
                    <div class="suggestion-actions" id="actions-container-${s.id}">
                        <!-- Populated by buttons or static confirmation -->
                    </div>
                </div>
            `;

            container.appendChild(card);

            // Populate the action footer based on user's response state
            const actionsContainer = document.getElementById(`actions-container-${s.id}`);
            const stateText = s.user_response || "Pending";

            if (stateText === "Pending") {
                const rejectBtn = document.createElement("button");
                rejectBtn.className = "action-btn-sm";
                rejectBtn.textContent = "Not today";
                rejectBtn.addEventListener("click", () => this.postResponse(s.id, "Not possible today"));

                const acceptBtn = document.createElement("button");
                acceptBtn.className = "action-btn-sm primary";
                acceptBtn.textContent = "I'll do it";
                acceptBtn.addEventListener("click", () => this.postResponse(s.id, "I'll do it"));

                actionsContainer.appendChild(rejectBtn);
                actionsContainer.appendChild(acceptBtn);
            } else {
                const label = document.createElement("span");
                label.className = "mono";
                label.style.fontSize = "0.8rem";
                
                if (stateText === "I'll do it") {
                    label.style.color = "var(--emerald-light)";
                    label.textContent = "✓ Committed (Logged)";
                } else {
                    label.style.color = "var(--text-muted)";
                    label.textContent = "Dismissed";
                }
                actionsContainer.appendChild(label);
            }
        });

        // Trigger GSAP stagger entrance for suggestion cards
        const prefersMotion = state && state.prefersReducedMotion;
        gsap.fromTo(".suggestion-card", 
            { opacity: 0, y: prefersMotion ? 0 : 25 },
            { opacity: 1, y: 0, duration: prefersMotion ? 0 : 0.6, stagger: prefersMotion ? 0 : 0.08, ease: "power2.out" }
        );
    }

    /**
     * Submit a suggestion response back to the backend.
     */
    async postResponse(suggestionId, responseText) {
        // Optimistically disable buttons to prevent double submission
        const container = document.getElementById(`actions-container-${suggestionId}`);
        if (container) {
            container.innerHTML = `<span class="mono" style="font-size: 0.8rem; color: var(--smog-grey);">Recording...</span>`;
        }

        try {
            await apiFetch("/api/suggestions/respond", {
                method: "POST",
                body: {
                    suggestion_id: suggestionId,
                    response: responseText
                }
            });

            // Reload suggestions to redraw states and headers
            await this.loadSuggestions();
            
            // Also notify the Sky Gauge on the page of changes
            if (window.dashboardManager) {
                window.dashboardManager.loadDashboard();
            }
        } catch (error) {
            console.error("Failed to post suggestion response:", error);
            alert(`Response save failed: ${error.message}`);
            await this.loadSuggestions();
        }
    }
}

// Instantiate and bind suggestions manager
window.suggestionsManager = new SuggestionsManager();
