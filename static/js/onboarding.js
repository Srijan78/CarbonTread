/**
 * onboarding.js - Controls the onboarding calibration flow.
 * Guides the user through Part A (base profile) and Part B (7-day recap).
 */

class OnboardingManager {
    constructor() {
        this.currentStepId = "city";
        this.answers = {
            city: "",
            commute_mode: "",
            commute_fuel: null,
            distance_bucket: "",
            diet: "",
            ac_usage: "",
            cooking_fuel: "",
            transport_pattern: "",
            car_days: 0,
            recap_fuel: null,
            food_pattern: "",
            unusual_events: []
        };
        this.stepHistory = [];
        
        // Step configurations
        this.steps = {
            city: {
                question: "Which city do you live in?",
                options: [
                    { text: "Mumbai / MMR", value: "Mumbai" },
                    { text: "Delhi / NCR", value: "Delhi" },
                    { text: "Bengaluru", value: "Bengaluru" },
                    { text: "Chennai", value: "Chennai" },
                    { text: "Hyderabad", value: "Hyderabad" },
                    { text: "Pune", value: "Pune" },
                    { text: "Kolkata", value: "Kolkata" },
                    { text: "Other Metro/City", value: "Other" }
                ],
                next: () => "commute_mode"
            },
            commute_mode: {
                question: "What is your primary mode of daily commute?",
                options: [
                    { text: "Car (Personal)", value: "car" },
                    { text: "Two-Wheeler (Motorcycle/Scooter)", value: "bike" },
                    { text: "Auto Rickshaw", value: "auto" },
                    { text: "Bus", value: "bus" },
                    { text: "Metro Train", value: "metro" },
                    { text: "Work from Home (No regular commute)", value: "wfh" }
                ],
                next: (val) => val === "car" ? "commute_fuel" : "commute_distance"
            },
            commute_fuel: {
                question: "What fuel type does your car use?",
                options: [
                    { text: "Petrol", value: "petrol" },
                    { text: "Diesel", value: "diesel" },
                    { text: "CNG", value: "cng" },
                    { text: "Electric (EV)", value: "electric" }
                ],
                next: () => "commute_distance"
            },
            commute_distance: {
                question: "What is your typical daily commute distance (one-way)?",
                options: [
                    { text: "Short (0 - 5 km)", value: "0-5km" },
                    { text: "Medium (5 - 15 km)", value: "5-15km" },
                    { text: "Long (15 - 30 km)", value: "15-30km" },
                    { text: "Very Long (30+ km)", value: "30km+" }
                ],
                next: () => "diet"
            },
            diet: {
                question: "What describes your primary diet type?",
                options: [
                    { text: "Vegetarian (Egg-free/Plant-based focus)", value: "veg" },
                    { text: "Non-Vegetarian (Includes poultry, meat, fish)", value: "non-veg" },
                    { text: "Vegan (No animal products)", value: "vegan" }
                ],
                next: () => "ac_usage"
            },
            ac_usage: {
                question: "Do you use active air conditioning (AC) at home?",
                options: [
                    { text: "Yes, regularly", value: "yes" },
                    { text: "No, never", value: "no" },
                    { text: "Seasonal usage (hot months only)", value: "seasonal" }
                ],
                next: () => "cooking_fuel"
            },
            cooking_fuel: {
                question: "What cooking fuel is primarily used in your household?",
                options: [
                    { text: "LPG Cylinder Refills", value: "lpg" },
                    { text: "PNG (Piped Natural Gas)", value: "png" },
                    { text: "Induction (Electric cooktops)", value: "induction" },
                    { text: "Mixed fuels (e.g. LPG + Induction)", value: "mixed" }
                ],
                next: () => "SUBMIT_PART_A"
            },
            
            // --- Part B: 7-Day Retroactive Recap ---
            recap_transport: {
                question: "Let's log your last 7 days. How did you mostly travel this past week?",
                options: [
                    { text: "Mostly by private car", value: "mostly_car" },
                    { text: "Mostly by metro train or bus", value: "mostly_metro_bus" },
                    { text: "A mix of both car and transit", value: "mix" },
                    { text: "Mostly worked from home / WFH", value: "mostly_wfh" }
                ],
                next: (val) => {
                    if (val === "mix") return "recap_car_days";
                    // If car is mentioned but we do not know the fuel type (e.g. primary mode in Part A was NOT car), ask fuel
                    if (val === "mostly_car" && !this.answers.commute_fuel) return "recap_car_fuel";
                    return "recap_food";
                }
            },
            recap_car_days: {
                question: "How many days did you travel by car during the last 7 days?",
                options: [
                    { text: "1 - 2 days", value: 2 },
                    { text: "3 - 4 days", value: 4 },
                    { text: "5 - 6 days", value: 6 }
                ],
                next: () => !this.answers.commute_fuel ? "recap_car_fuel" : "recap_food"
            },
            recap_car_fuel: {
                question: "What fuel type was the car you traveled in this week?",
                options: [
                    { text: "Petrol", value: "petrol" },
                    { text: "Diesel", value: "diesel" },
                    { text: "CNG", value: "cng" },
                    { text: "Electric (EV)", value: "electric" }
                ],
                next: () => "recap_food"
            },
            recap_food: {
                question: "How would you describe your food pattern in the last 7 days?",
                options: [
                    { text: "Mostly vegetarian meals", value: "mostly_veg" },
                    { text: "Mostly non-vegetarian meals", value: "mostly_non_veg" },
                    { text: "Roughly half veg and half non-veg", value: "half_half" }
                ],
                next: () => "recap_unusual"
            },
            recap_unusual: {
                question: "Did you have any unusual travel or single large carbon activities this week?",
                options: [
                    { text: "No, typical week", value: "no" },
                    { text: "Yes, I had specific events to record", value: "yes" }
                ],
                next: (val) => val === "yes" ? "recap_unusual_add" : "SUBMIT_PART_B"
            },
            recap_unusual_add: {
                question: "Add unusual activities (unlimited)",
                type: "custom_unusual",
                next: () => "SUBMIT_PART_B"
            }
        };
    }

    /**
     * Start the calibration flow.
     */
    startCalibration() {
        this.currentStepId = "city";
        this.stepHistory = [];
        this.renderStep();
        this.updateSkyGaugeOnboarding(0);
    }

    /**
     * Render the current step card.
     */
    renderStep() {
        const questionTitle = document.getElementById("calibration-question-title");
        const optionsContainer = document.getElementById("calibration-options-container");
        const prevBtn = document.getElementById("onboarding-prev-btn");
        const nextBtn = document.getElementById("onboarding-next-btn");

        if (!questionTitle || !optionsContainer || !prevBtn || !nextBtn) return;

        const currentStep = this.steps[this.currentStepId];
        questionTitle.textContent = currentStep.question;
        optionsContainer.innerHTML = "";

        // Enable / Disable Back Button
        prevBtn.disabled = this.stepHistory.length === 0;

        // Custom renderer for unusual events step
        if (currentStep.type === "custom_unusual") {
            this.renderCustomUnusual(optionsContainer);
            nextBtn.textContent = "Complete Onboarding";
            nextBtn.disabled = false;
            return;
        }

        nextBtn.textContent = "Next";
        
        // Render standard options
        currentStep.options.forEach((opt, idx) => {
            const btn = document.createElement("button");
            btn.className = "option-row animate-fade-in";
            btn.style.setProperty("--i", idx);
            btn.textContent = opt.text;
            
            // Check if option was previously selected
            const currentSelected = this.answers[this.currentStepId];
            if (currentSelected === opt.value) {
                btn.classList.add("selected");
            }

            btn.addEventListener("click", () => {
                // Clear selection on other buttons
                const siblings = optionsContainer.querySelectorAll(".option-row");
                siblings.forEach(s => s.classList.remove("selected"));
                btn.classList.add("selected");
                
                // Store chosen answer
                this.answers[this.currentStepId] = opt.value;
                nextBtn.disabled = false;
            });
            optionsContainer.appendChild(btn);
        });

        // Next button disabled until an option is selected
        const currentAns = this.answers[this.currentStepId];
        nextBtn.disabled = currentAns === undefined || currentAns === "" || currentAns === null;
    }

    /**
     * Render the custom multi-event logger view for recap unusual activities.
     */
    renderCustomUnusual(container) {
        container.innerHTML = `
            <div style="display: flex; flex-direction: column; gap: 12px; margin-bottom: 16px;">
                <div class="form-group">
                    <label class="form-label" for="unusual-type">Event Type</label>
                    <select id="unusual-type" class="form-select">
                        <option value="flight">Domestic Flight (km)</option>
                        <option value="big_purchase">Big Consumer Purchase (e.g. AC/TV/Laptop)</option>
                        <option value="other">Other Notable Event (e.g. big party)</option>
                    </select>
                </div>
                <div class="form-group">
                    <label class="form-label" id="unusual-val-label" for="unusual-value">Distance (km)</label>
                    <input type="number" id="unusual-value" class="form-input" min="0" value="1000">
                </div>
                <button id="add-unusual-btn" type="button" class="btn-secondary" style="border-color: var(--sky-clear); color: var(--sky-clear);">+ Add Event</button>
            </div>
            
            <div id="unusual-list-container" style="border-top: 1px solid var(--border-color); padding-top: 12px; display: none;">
                <div class="form-label" style="margin-bottom: 8px;">Added Events This Week:</div>
                <ul id="unusual-list" style="list-style: none; display: flex; flex-direction: column; gap: 8px;"></ul>
            </div>
        `;

        const typeSelect = document.getElementById("unusual-type");
        const valInput = document.getElementById("unusual-value");
        const valLabel = document.getElementById("unusual-val-label");
        const addBtn = document.getElementById("add-unusual-btn");
        const listContainer = document.getElementById("unusual-list-container");
        const listUl = document.getElementById("unusual-list");

        // Swap labels/values based on select category
        typeSelect.addEventListener("change", () => {
            if (typeSelect.value === "flight") {
                valLabel.textContent = "Distance (km)";
                valInput.value = "1000";
                valInput.style.display = "block";
            } else {
                valLabel.textContent = "No quantity required";
                valInput.style.display = "none";
            }
        });

        // Add handler
        addBtn.addEventListener("click", () => {
            const evType = typeSelect.value;
            const evVal = evType === "flight" ? parseFloat(valInput.value) : 1;
            const unit = evType === "flight" ? "km" : "event";

            if (isNaN(evVal) || evVal <= 0) {
                alert("Please enter a valid numeric value.");
                return;
            }

            const newEvent = { type: evType, value: evVal, unit: unit };
            this.answers.unusual_events.push(newEvent);
            this.updateUnusualList(listContainer, listUl);
        });

        this.updateUnusualList(listContainer, listUl);
    }

    /**
     * Refresh the rendering list of added unusual events.
     */
    updateUnusualList(container, list) {
        if (!container || !list) return;
        list.innerHTML = "";

        if (this.answers.unusual_events.length === 0) {
            container.style.display = "none";
            return;
        }

        container.style.display = "block";
        this.answers.unusual_events.forEach((ev, index) => {
            const li = document.createElement("li");
            li.style.display = "flex";
            li.style.justify = "space-between";
            li.style.alignItems = "center";
            li.style.padding = "8px";
            li.style.backgroundColor = "var(--ink-base)";
            li.style.border = "1px solid var(--border-color)";
            li.style.fontSize = "0.85rem";

            const label = ev.type === "flight" ? `Domestic Flight (${ev.value} km)` : `Unusual activity: ${ev.type}`;
            li.innerHTML = `
                <span>${label}</span>
                <button type="button" class="sheet-close" style="font-size: 1.1rem; padding: 0 4px;" data-index="${index}">&times;</button>
            `;

            li.querySelector("button").addEventListener("click", (e) => {
                const idx = parseInt(e.target.getAttribute("data-index"));
                this.answers.unusual_events.splice(idx, 1);
                this.updateUnusualList(container, list);
            });

            list.appendChild(li);
        });
    }

    /**
     * Animate horizontal screen slide transitions.
     */
    async changeStep(nextStepId, direction = "next") {
        const card = document.getElementById("onboarding-calibration-card");
        if (card) {
            card.classList.add(direction === "next" ? "slide-out-left" : "slide-out-right");
            await new Promise(resolve => setTimeout(resolve, 150));
        }

        this.currentStepId = nextStepId;
        this.renderStep();
        this.updateSkyGaugeOnboarding();

        if (card) {
            card.classList.remove("slide-out-left", "slide-out-right");
            card.classList.add(direction === "next" ? "slide-in-right" : "slide-in-left");
            setTimeout(() => {
                card.classList.remove("slide-in-right", "slide-in-left");
            }, 300);
        }
    }

    /**
     * Handle navigation when user clicks the "Next" button.
     */
    async handleNext() {
        const currentStep = this.steps[this.currentStepId];
        const currentAns = this.answers[this.currentStepId];
        const nextStepId = currentStep.next(currentAns);

        if (nextStepId === "SUBMIT_PART_A") {
            await this.submitPartA();
        } else if (nextStepId === "SUBMIT_PART_B") {
            await this.submitPartB();
        } else if (nextStepId === "PART_B_COMPLETE") {
            await this.submitPartB();
        } else {
            this.stepHistory.push(this.currentStepId);
            await this.changeStep(nextStepId, "next");
        }
    }

    /**
     * Handle navigation when user clicks the "Back" button.
     */
    async handlePrev() {
        if (this.stepHistory.length > 0) {
            const prevStepId = this.stepHistory.pop();
            await this.changeStep(prevStepId, "prev");
        }
    }

    /**
     * Calculate and display incremental progress on the Sky Gauge during calibration.
     */
    updateSkyGaugeOnboarding() {
        const fill = document.getElementById("sky-gauge-fill");
        const label = document.getElementById("sky-gauge-percentage-label");
        if (!fill || !label) return;

        // Visual progress mapping based on calibration phases
        const stepsList = Object.keys(this.steps);
        const currentIndex = stepsList.indexOf(this.currentStepId);
        
        let percentage = 0;
        if (currentIndex !== -1) {
            percentage = Math.round((currentIndex / stepsList.length) * 100);
        }

        fill.style.width = `${percentage}%`;
        label.textContent = `${percentage}% Calibrated`;

        // Update progressbar ARIA states
        const container = document.getElementById("sky-gauge-container");
        if (container) {
            container.setAttribute("aria-valuenow", percentage);
            container.setAttribute("aria-valuetext", `${percentage}% Calibrated`);
        }
    }

    /**
     * Send Part A profile information to the backend.
     */
    async submitPartA() {
        try {
            const body = {
                city: this.answers.city,
                commute_mode: this.answers.commute_mode,
                commute_fuel: this.answers.commute_fuel,
                distance_bucket: this.answers.commute_distance,
                diet: this.answers.diet,
                ac_usage: this.answers.ac_usage,
                cooking_fuel: this.answers.cooking_fuel
            };

            await apiFetch("/api/onboarding/profile", {
                method: "POST",
                body: body
            });

            // Transition to Part B
            this.stepHistory.push(this.currentStepId);
            this.currentStepId = "recap_transport";
            this.renderStep();
            this.updateSkyGaugeOnboarding();
        } catch (error) {
            console.error("Part A submission failed:", error);
            alert(`Calibration failed: ${error.message}`);
        }
    }

    /**
     * Send Part B recap data to the backend and finish onboarding.
     */
    async submitPartB() {
        try {
            const body = {
                transport_pattern: this.answers.recap_transport,
                car_days: this.answers.car_days || 0,
                recap_fuel: this.answers.recap_fuel,
                food_pattern: this.answers.recap_food,
                unusual_events: this.answers.unusual_events
            };

            await apiFetch("/api/onboarding/recap", {
                method: "POST",
                body: body
            });

            // Complete calibration setup
            localStorage.setItem("carbonTread_onboardingCompleted", "true");
            state.onboardingCompleted = true;
            
            // Show main nav
            const appNav = document.getElementById("app-nav");
            if (appNav) appNav.style.display = "flex";

            // Route to dashboard
            window.switchTab("screen-dashboard");
        } catch (error) {
            console.error("Part B submission failed:", error);
            alert(`Recap saving failed: ${error.message}`);
        }
    }
}

// Instantiate and bind onboarding manager
window.onboardingManager = new OnboardingManager();

// Bind button clicks in onboarding
document.addEventListener("DOMContentLoaded", () => {
    const prevBtn = document.getElementById("onboarding-prev-btn");
    const nextBtn = document.getElementById("onboarding-next-btn");

    if (prevBtn) {
        prevBtn.addEventListener("click", () => window.onboardingManager.handlePrev());
    }
    if (nextBtn) {
        nextBtn.addEventListener("click", () => window.onboardingManager.handleNext());
    }
});
