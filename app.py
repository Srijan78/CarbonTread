from flask import Flask, Response
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from services.db import init_db
from config import Config

# Initialize Flask-Limiter globally
limiter = Limiter(key_func=get_remote_address)


def create_app() -> Flask:
    """Create, configure, and return the Flask application instance."""
    app = Flask(__name__, static_folder="static", static_url_path="")
    app.config.from_object(Config)

    # Initialize SQLite database schema
    init_db()

    # Initialize rate limiting
    limiter.init_app(app)

    # Register blueprints
    from routes.onboarding_routes import onboarding_bp
    from routes.onboarding_recap_routes import onboarding_recap_bp
    from routes.dashboard_routes import dashboard_bp
    from routes.event_routes import event_bp
    from routes.event_extraction_routes import event_extraction_bp
    from routes.suggestion_routes import suggestion_bp
    from routes.insight_routes import insight_bp
    from routes.insight_narrative_routes import insight_narrative_bp

    app.register_blueprint(onboarding_bp)
    app.register_blueprint(onboarding_recap_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(event_bp)
    app.register_blueprint(event_extraction_bp)
    app.register_blueprint(suggestion_bp)
    app.register_blueprint(insight_bp)
    app.register_blueprint(insight_narrative_bp)

    # Apply rate limiter "20 per minute" to API routes interacting with external APIs (Gemini/Weather)
    # This protects rate quotas for extraction, suggestions, and stories
    limiter.limit("20 per minute")(event_extraction_bp)
    limiter.limit("20 per minute")(suggestion_bp)
    limiter.limit("20 per minute")(insight_narrative_bp)

    @app.route("/")
    def serve_index() -> Response:
        """Serve the frontend single-page application entry point."""
        return app.send_static_file("index.html")

    @app.after_request
    def add_security_headers(response: Response) -> Response:
        """Inject strict security headers and Content-Security-Policy globally."""
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # CSP rules allowing local assets, Google Fonts, GSAP CDN, and Gemini API requests
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "connect-src 'self' https://generativelanguage.googleapis.com; "
            "img-src 'self' data:;"
        )
        return response

    return app


# Create the app instance for standard WSGI servers
app: Flask = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
