/**
 * main.js - Core orchestrator for CarbonTread
 * Handles user session initialization, sidebar navigation, tab switching,
 * and the ambient canvas background effect.
 */

// Global State
const state = {
    userId: localStorage.getItem("carbonTread_userId") || "",
    onboardingCompleted: localStorage.getItem("carbonTread_onboardingCompleted") === "true",
    currentTab: "screen-dashboard",
    isInitialLoad: true,
    prefersReducedMotion: window.matchMedia("(prefers-reduced-motion: reduce)").matches
};

/**
 * Initialize the application on DOM load.
 */
document.addEventListener("DOMContentLoaded", () => {
    initSession().then(() => {
        setupNavigation();
        routeInitialScreen();
        new AmbientBackground();
    });
});

/**
 * Initialize user session UUID, generating a new one if missing.
 */
async function initSession() {
    const sessionIndicator = document.getElementById("session-indicator");
    
    // Add double click handler to reset session for testing
    if (sessionIndicator) {
        sessionIndicator.addEventListener("dblclick", resetSession);
    }

    if (state.userId) {
        updateSessionUI();
        return;
    }

    try {
        const response = await fetch("/api/session/init", {
            method: "POST",
            headers: { "Content-Type": "application/json" }
        });
        if (!response.ok) {
            throw new Error("Failed to initialize session on backend");
        }
        const data = await response.json();
        state.userId = data.user_id;
        localStorage.setItem("carbonTread_userId", state.userId);
        updateSessionUI();
    } catch (error) {
        console.error("Session initialization error:", error);
        alert("Session initialization failed. The server may be offline.");
    }
}

/**
 * Update the UI session indicators with active UUID.
 */
function updateSessionUI() {
    const sessionIndicator = document.getElementById("session-indicator");
    if (sessionIndicator && state.userId) {
        const shortId = state.userId.substring(0, 8) + "..." + state.userId.substring(state.userId.length - 4);
        sessionIndicator.textContent = `ID: ${shortId}`;
        sessionIndicator.title = `Full UUID: ${state.userId}\nDouble click to reset session.`;
    }
}

/**
 * Reset local storage session UUID and reload application.
 */
function resetSession() {
    if (confirm("Reset current carbon tracking session? All logged events will be detached from your device.")) {
        localStorage.removeItem("carbonTread_userId");
        localStorage.removeItem("carbonTread_onboardingCompleted");
        window.location.reload();
    }
}

/**
 * Wrap standard fetch to automatically append X-User-ID headers and handle errors uniformly.
 * @param {string} url - Target endpoint URL
 * @param {object} options - Custom fetch configuration
 * @returns {Promise<any>} Response body object
 */
async function apiFetch(url, options = {}) {
    if (!state.userId) {
        throw new Error("Cannot make API call: User ID not initialized");
    }

    // Initialize headers
    options.headers = options.headers || {};
    options.headers["X-User-ID"] = state.userId;
    
    if (options.body && typeof options.body === "object") {
        options.headers["Content-Type"] = "application/json";
        options.body = JSON.stringify(options.body);
    }

    const response = await fetch(url, options);
    const data = await response.json();

    if (!response.ok) {
        throw new Error(data.error || `HTTP error ${response.status}`);
    }

    return data;
}

/**
 * Set up click listeners for sidebar navigation links.
 */
function setupNavigation() {
    const navLinks = document.querySelectorAll(".nav-link");
    navLinks.forEach(link => {
        link.addEventListener("click", () => {
            const target = link.getAttribute("data-target");
            switchTab(target);
        });
    });
}

/**
 * Route user to the Onboarding Calibration flow or Home Dashboard based on state.
 */
function routeInitialScreen() {
    const onboardingOverlay = document.getElementById("onboarding-overlay");
    const appLayout = document.getElementById("app-layout");
    
    if (state.onboardingCompleted) {
        // Hide onboarding, show main app
        if (onboardingOverlay) onboardingOverlay.style.display = "none";
        if (appLayout) appLayout.style.display = "flex";
        switchTab("screen-dashboard");
    } else {
        // Show onboarding, hide main app
        if (onboardingOverlay) onboardingOverlay.style.display = "flex";
        if (appLayout) appLayout.style.display = "none";
        switchTab("screen-onboarding");
        if (window.onboardingManager) {
            window.onboardingManager.startCalibration();
        }
    }
}

// Map tab IDs to page titles
const TAB_TITLES = {
    "screen-dashboard": "Dashboard",
    "screen-suggestions": "Suggestions",
    "screen-insights": "Insights"
};

/**
 * Switch the active tab content view and fire refresh triggers with smooth transition.
 * @param {string} tabId - Target section element ID
 */
async function switchTab(tabId) {
    const targetEl = document.getElementById(tabId);
    if (!targetEl) return;

    if (state.currentTab === tabId && targetEl.classList.contains("visible")) {
        // Even if already on this tab, fire refresh on initial load
        fireTabRefresh(tabId);
        return;
    }

    // If switching from onboarding to main app, toggle layout visibility
    if (tabId !== "screen-onboarding") {
        const onboardingOverlay = document.getElementById("onboarding-overlay");
        const appLayout = document.getElementById("app-layout");
        if (onboardingOverlay) onboardingOverlay.style.display = "none";
        if (appLayout) appLayout.style.display = "flex";
    }
    
    // Exit transition for the currently visible screen using GSAP
    const activeScreen = document.getElementById(state.currentTab);
    const exitDuration = state.prefersReducedMotion ? 0 : 0.25;
    const exitY = state.prefersReducedMotion ? 0 : -15;

    if (activeScreen && activeScreen.id !== tabId) {
        gsap.to(activeScreen, { 
            opacity: 0, 
            y: exitY, 
            duration: exitDuration, 
            ease: "power2.in",
            onComplete: () => {
                activeScreen.classList.remove("active", "visible");
                gsap.set(activeScreen, { clearProps: "all" });
            }
        });
    }

    state.currentTab = tabId;

    // Display and fade-in the new screen
    const screen = document.getElementById(tabId);
    if (screen) {
        screen.classList.add("active");
        
        if (tabId === "screen-dashboard" && state.isInitialLoad) {
            state.isInitialLoad = false;
            // First time entrance stagger slide-in
            const initDuration = state.prefersReducedMotion ? 0 : 0.8;
            const initStagger = state.prefersReducedMotion ? 0 : 0.12;
            const initY = state.prefersReducedMotion ? 0 : 30;
            gsap.fromTo([".sidebar", ".content-header", ".focus-card", ".breakdown-card"],
                { opacity: 0, y: initY },
                { 
                    opacity: 1, 
                    y: 0, 
                    duration: initDuration, 
                    stagger: initStagger, 
                    ease: "power3.out",
                    onComplete: () => {
                        screen.classList.add("visible");
                    }
                }
            );
        } else {
            // Normal tab change transition
            const enterDuration = state.prefersReducedMotion ? 0 : 0.4;
            const enterY = state.prefersReducedMotion ? 0 : 15;
            gsap.fromTo(screen, 
                { opacity: 0, y: enterY },
                { 
                    opacity: 1, 
                    y: 0, 
                    duration: enterDuration, 
                    ease: "power2.out",
                    onComplete: () => {
                        screen.classList.add("visible");
                    }
                }
            );

            // Additional stagger animations for child elements
            if (tabId === "screen-insights") {
                const insightDuration = state.prefersReducedMotion ? 0 : 0.5;
                const insightStagger = state.prefersReducedMotion ? 0 : 0.1;
                const insightDelay = state.prefersReducedMotion ? 0 : 0.1;
                const insightY = state.prefersReducedMotion ? 0 : 20;
                gsap.fromTo(".insights-section",
                    { opacity: 0, y: insightY },
                    { opacity: 1, y: 0, duration: insightDuration, stagger: insightStagger, ease: "power2.out", delay: insightDelay }
                );
            }
        }
    }

    // Toggle active sidebar nav link styling and aria-current
    const navLinks = document.querySelectorAll(".nav-link");
    navLinks.forEach(link => {
        if (link.getAttribute("data-target") === tabId) {
            link.classList.add("active");
            link.setAttribute("aria-current", "page");
        } else {
            link.classList.remove("active");
            link.removeAttribute("aria-current");
        }
    });

    // Update page title in header
    const pageTitle = document.getElementById("page-title");
    if (pageTitle && TAB_TITLES[tabId]) {
        pageTitle.textContent = TAB_TITLES[tabId];
    }

    // Fire screen refresh triggers
    fireTabRefresh(tabId);
}

/**
 * Fire data refresh for the given tab.
 * @param {string} tabId - Target section element ID
 */
function fireTabRefresh(tabId) {
    if (tabId === "screen-dashboard" && window.dashboardManager) {
        window.dashboardManager.loadDashboard();
    } else if (tabId === "screen-suggestions" && window.suggestionsManager) {
        window.suggestionsManager.loadSuggestions();
    } else if (tabId === "screen-insights" && window.insightsManager) {
        window.insightsManager.loadInsights();
    }
}

// Attach switchTab globally for onboarding completion bypasses
window.switchTab = switchTab;

/**
 * AmbientBackground - Generates a modern floating organic blob animation using canvas.
 */
class AmbientBackground {
    constructor() {
        this.canvas = document.getElementById("ambient-canvas");
        if (!this.canvas) return;
        this.ctx = this.canvas.getContext("2d");
        this.blobs = [];
        this.resize();
        this.initBlobs();
        window.addEventListener("resize", () => this.resize());
        this.animate();
    }

    resize() {
        this.canvas.width = window.innerWidth;
        this.canvas.height = window.innerHeight;
    }

    initBlobs() {
        const colors = [
            "rgba(21, 128, 61, 0.03)",   // Emerald (faint)
            "rgba(6, 182, 212, 0.03)",    // Cyan (faint)
            "rgba(99, 102, 241, 0.02)",   // Indigo (faint)
            "rgba(244, 63, 94, 0.02)",     // Rose (faint)
            "rgba(245, 158, 11, 0.02)"     // Amber (faint)
        ];
        
        for (let i = 0; i < colors.length; i++) {
            this.blobs.push({
                x: Math.random() * this.canvas.width,
                y: Math.random() * this.canvas.height,
                radius: Math.random() * 350 + 250,
                color: colors[i],
                vx: (Math.random() - 0.5) * 0.25,
                vy: (Math.random() - 0.5) * 0.25
            });
        }
    }

    animate() {
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        
        this.blobs.forEach(blob => {
            blob.x += blob.vx;
            blob.y += blob.vy;
            
            // Bounce on boundaries
            if (blob.x < -150 || blob.x > this.canvas.width + 150) blob.vx *= -1;
            if (blob.y < -150 || blob.y > this.canvas.height + 150) blob.vy *= -1;
            
            // Gradient fill - blend into light background
            const grad = this.ctx.createRadialGradient(blob.x, blob.y, 0, blob.x, blob.y, blob.radius);
            grad.addColorStop(0, blob.color);
            grad.addColorStop(1, "rgba(247, 249, 251, 0)");
            
            this.ctx.fillStyle = grad;
            this.ctx.beginPath();
            this.ctx.arc(blob.x, blob.y, blob.radius, 0, Math.PI * 2);
            this.ctx.fill();
        });
        
        requestAnimationFrame(() => this.animate());
    }
}
