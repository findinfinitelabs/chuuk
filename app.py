from __future__ import annotations

"""
Flask application for Chuuk Dictionary OCR and Lookup
"""

import os
import re
import time
import json
import uuid
import threading
import secrets
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone, timedelta
from functools import wraps
from flask import (
    Flask,
    request,
    redirect,
    url_for,
    flash,
    jsonify,
    send_from_directory,
    Response,
    session,
)

# from flask_cors import CORS
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from markupsafe import Markup
from pathlib import Path
from ebooklib import epub
from src.utils.nwt_epub_parser import NWTEpubParser

# Load environment variables from absolute path
env_path = Path(__file__).parent / ".env"
load_dotenv(env_path, override=True)

# Initialize NWT EPUB parsers (lazy load)
_nwt_english_parser = None
_nwt_chuukese_parser = None


def get_nwt_english_parser():
    global _nwt_english_parser
    if _nwt_english_parser is None:
        epub_path = "data/bible/nwt_E.epub"
        if os.path.exists(epub_path):
            _nwt_english_parser = NWTEpubParser(epub_path)
    return _nwt_english_parser


def get_nwt_chuukese_parser():
    global _nwt_chuukese_parser
    if _nwt_chuukese_parser is None:
        epub_path = "data/bible/nwt_TE.epub"
        if os.path.exists(epub_path):
            _nwt_chuukese_parser = NWTEpubParser(epub_path)
    return _nwt_chuukese_parser


from src.ocr.ocr_processor import OCRProcessor
from src.core.jworg_lookup import JWOrgLookup
from src.database.publication_manager import PublicationManager
from src.database.dictionary_db import DictionaryDB
from scripts.processing_logger import processing_logger
from pymongo.errors import DuplicateKeyError, OperationFailure
import requests
from bs4 import BeautifulSoup

try:
    from src.translation.helsinki_translator_v2 import HelsinkiChuukeseTranslator

    HELSINKI_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ Helsinki translator not available: {e}")
    HELSINKI_AVAILABLE = False

# Feature flag: set OLLAMA_ENABLED=true in env to re-enable Ollama integration.
# Default is false — Ollama is resource-heavy and optional.
OLLAMA_ENABLED = os.getenv("OLLAMA_ENABLED", "false").lower() == "true"

app = Flask(__name__)
secret_key = os.getenv("FLASK_SECRET_KEY")
if not secret_key:
    # Generate a random secret key for development
    secret_key = secrets.token_hex(32)
    if os.getenv("FLASK_ENV") == "production":
        raise ValueError("FLASK_SECRET_KEY must be set in production")
app.config["SECRET_KEY"] = secret_key
app.config["MAX_CONTENT_LENGTH"] = int(os.getenv("MAX_CONTENT_LENGTH", 16 * 1024 * 1024))  # 16MB default
app.config["UPLOAD_FOLDER"] = os.getenv("UPLOAD_FOLDER", "uploads")
app.config["SESSION_COOKIE_SECURE"] = os.getenv("FLASK_ENV") == "production"
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["PERMANENT_SESSION_LIFETIME"] = 86400 * 7  # 7 days

# ============================================================================
# Single Active Session + Magic Link Storage
# ============================================================================
# In-memory store for active sessions and magic links
# In production, consider using Redis or database storage
active_sessions = {}  # {email: session_id}
magic_links = {}  # {token: {'email': email, 'expires': datetime}}
MAGIC_LINK_EXPIRY_MINUTES = 15


def send_magic_link_email(email: str, magic_token: str, base_url: str) -> bool:
    """Send magic link email to user"""
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", 587))
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    from_email = os.getenv("SMTP_FROM", smtp_user)

    if not smtp_user or not smtp_password:
        print(f"⚠️ SMTP not configured. Magic link for {email}: {base_url}/auth/magic/{magic_token}")
        return True  # Still return True for dev mode

    magic_url = f"{base_url}/auth/magic/{magic_token}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Chuuk Dictionary - Login Link"
    msg["From"] = from_email
    msg["To"] = email

    text_content = f"""
Chuuk Dictionary Login

Click the link below to sign in to your account:

{magic_url}

This link expires in {MAGIC_LINK_EXPIRY_MINUTES} minutes.

If you didn't request this link, you can safely ignore this email.
"""

    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; background-color: #1a1b1e; color: #fff; padding: 20px; }}
        .container {{ max-width: 500px; margin: 0 auto; background: #25262b; padding: 30px; border-radius: 8px; }}
        .button {{ display: inline-block; background: #228be6; color: white; padding: 12px 24px;
                   text-decoration: none; border-radius: 4px; margin: 20px 0; }}
        .footer {{ color: #909296; font-size: 12px; margin-top: 20px; }}
    </style>
</head>
<body>
    <div class="container">
        <h2>Chuuk Dictionary Login</h2>
        <p>Click the button below to sign in to your account:</p>
        <a href="{magic_url}" class="button">Sign In</a>
        <p class="footer">This link expires in {MAGIC_LINK_EXPIRY_MINUTES} minutes.<br>
        If you didn't request this link, you can safely ignore this email.</p>
    </div>
</body>
</html>
"""

    msg.attach(MIMEText(text_content, "plain"))
    msg.attach(MIMEText(html_content, "html"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(msg)
        print(f"✅ Magic link email sent to {email}")
        return True
    except Exception as e:
        print(f"❌ Failed to send magic link email: {e}")
        return False


# Enable CORS for React frontend
# CORS(app, origins=["http://localhost:5173"])

# Initialize database first
dict_db = DictionaryDB()

# Initialize services with db reference
pub_manager = PublicationManager(app.config["UPLOAD_FOLDER"], db=dict_db)
ocr_processor = OCRProcessor(use_google_vision=bool(os.getenv("GOOGLE_APPLICATION_CREDENTIALS")))
jworg_lookup = JWOrgLookup(pub_manager)

# Initialize Helsinki-NLP translator
helsinki_translator = None

# Global training status
training_status = {
    "is_training": False,
    "models_training": [],
    "progress": 0,
    "message": "",
    "last_training": None,
    "epoch_current": None,
    "epoch_total": None,
    "epoch_step_pct": None,
    "epoch_loss": None,
    "current_direction": None,
}
# Lock to guard training_status across threads
training_status_lock = threading.Lock()

# Cache for expensive Cosmos DB queries to avoid rate limiting
# Cache expires after 5 minutes
distinct_values_cache = {}
CACHE_EXPIRY_SECONDS = 300  # 5 minutes


def get_cached_distinct_values(field: str, db_field: str) -> list | None:
    """Get cached distinct values or return None if expired/missing"""
    cache_key = f"distinct_{field}"
    if cache_key in distinct_values_cache:
        cached_data = distinct_values_cache[cache_key]
        # Check if cache is still valid
        if (datetime.now(timezone.utc) - cached_data["timestamp"]).total_seconds() < CACHE_EXPIRY_SECONDS:
            return cached_data["values"]
    return None


def set_cached_distinct_values(field: str, values: list):
    """Cache distinct values with timestamp"""
    cache_key = f"distinct_{field}"
    distinct_values_cache[cache_key] = {"values": values, "timestamp": datetime.now(timezone.utc)}


if HELSINKI_AVAILABLE:
    try:
        helsinki_translator = HelsinkiChuukeseTranslator()
        print("🚀 Initializing Helsinki-NLP models in background...")

        # Initialize models in background to avoid blocking startup
        def init_models():
            if helsinki_translator.setup_models():
                print("✅ Helsinki-NLP models ready!")
                helsinki_translator.load_dictionary_data()
            else:
                print("❌ Failed to initialize Helsinki models")

        threading.Thread(target=init_models, daemon=True).start()
    except Exception as e:
        print(f"⚠️ Helsinki translator initialization failed: {e}")
        helsinki_translator = None

# Start continuous training engine in background
_continuous_trainer = None
try:
    from src.training.continuous_trainer import ContinuousTrainer
    _continuous_trainer = ContinuousTrainer.get_instance()
    _continuous_trainer.start_scheduler()
    print("🔄 Continuous training engine started")
except Exception as _ct_err:
    print(f"⚠️ Continuous trainer init failed: {_ct_err}")

# Allowed file extensions
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "bmp", "tiff", "pdf", "docx"}

# ============================================================================
# Authentication Functions
# ============================================================================

# Initialize UserDB for Cosmos DB authentication
_user_db = None
_auto_sync_completed = False


def get_user_db():
    """Get UserDB instance with lazy initialization"""
    global _user_db
    if _user_db is None:
        try:
            from src.database.user_db import UserDB

            _user_db = UserDB()
            if _user_db.is_connected():
                print("✅ Using Cosmos DB for user authentication")
            else:
                print("⚠️ UserDB not connected, using file fallback")
                _user_db = None
        except Exception as e:
            print(f"⚠️ Failed to initialize UserDB: {e}, using file fallback")
            _user_db = None
    return _user_db


def auto_sync_users_to_cosmos():
    """Automatically sync users from config file to Cosmos DB if connected"""
    global _auto_sync_completed

    # Only run once per app startup
    if _auto_sync_completed:
        return

    user_db = get_user_db()
    if not user_db or not user_db.is_connected():
        _auto_sync_completed = True
        return

    # Load users from file
    users_file = Path(__file__).parent / "config" / "users.json"
    if not users_file.exists():
        _auto_sync_completed = True
        return

    try:
        with open(users_file) as f:
            data = json.load(f)
            file_users = data.get("users", [])

        if not file_users:
            _auto_sync_completed = True
            return

        # Get existing users from Cosmos DB
        db_users = user_db.get_all_users()
        db_emails = {u["email"].lower() for u in db_users}

        # Sync any missing users
        synced_count = 0
        for file_user in file_users:
            email = file_user.get("email", "").lower()
            if email and email not in db_emails:
                if user_db.create_user(file_user.copy()):
                    synced_count += 1
                    print(f"🔄 Auto-synced user to Cosmos DB: {email}")

        if synced_count > 0:
            print(f"✅ Auto-synced {synced_count} user(s) from config file to Cosmos DB")

    except Exception as e:
        print(f"⚠️ Auto-sync failed: {e}")
    finally:
        _auto_sync_completed = True


def load_users():
    """Load users from Cosmos DB, with fallback to config file"""
    # Auto-sync users from file to Cosmos DB if connected
    auto_sync_users_to_cosmos()

    # Try Cosmos DB first
    user_db = get_user_db()
    if user_db and user_db.is_connected():
        users = user_db.get_all_users()
        if users:
            return users
        # If no users in DB, check if we should migrate from file
        print("ℹ️ No users in Cosmos DB yet")

    # Fallback: Check for environment variable (for Docker without Cosmos DB)
    users_json = os.getenv("APP_USERS_JSON")
    if users_json:
        try:
            data = json.loads(users_json)
            return data.get("users", []) if isinstance(data, dict) else data
        except json.JSONDecodeError:
            print("⚠️ Failed to parse APP_USERS_JSON environment variable")

    # Fallback: Local config file (for local development)
    users_file = Path(__file__).parent / "config" / "users.json"
    if users_file.exists():
        with open(users_file) as f:
            data = json.load(f)
            return data.get("users", [])

    # No users configured - log warning
    print("⚠️ No users configured. Set up Cosmos DB users or create config/users.json")
    return []


def save_users(users):
    """Save users - only used for local file-based storage"""
    users_file = Path(__file__).parent / "config" / "users.json"
    with open(users_file, "w") as f:
        json.dump({"users": users}, f, indent=2)


def update_user_terms_acceptance(email, terms_accepted_at):
    """Update user's terms acceptance timestamp"""
    # Try Cosmos DB first
    user_db = get_user_db()
    if user_db and user_db.is_connected():
        return user_db.update_terms_acceptance(email, terms_accepted_at)

    # Fallback to file-based
    users = load_users()
    for user in users:
        if user["email"].lower() == email.lower():
            user["terms_accepted"] = True
            user["terms_accepted_at"] = terms_accepted_at
            save_users(users)
            return True
    return False


# Initials lookup cache (email → initials)
_initials_cache = {}


def _cosmos_retry(fn, *args, max_retries: int = 5, **kwargs):
    """Call fn(*args, **kwargs), retrying up to max_retries times on Cosmos 429s."""
    import re as _re_mod
    for attempt in range(max_retries):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            err = str(exc)
            if "16500" not in err and "RetryAfterMs" not in err:
                raise
            if attempt == max_retries - 1:
                raise
            match = _re_mod.search(r"RetryAfterMs=(\d+)", err)
            wait = max(int(match.group(1)) / 1000.0 if match else 1.0,
                       0.2 * (2 ** attempt))
            time.sleep(min(wait, 10.0))


def _get_user_initials(email: str | None = None) -> str:
    """Return 2-letter initials for the logged-in user or given email.
    Falls back to 'AI' for system/upload actions."""
    email = email or session.get("user_email", "")
    if not email:
        return "AI"
    email_lower = email.lower()
    if email_lower in _initials_cache:
        return _initials_cache[email_lower]
    # Check config/users.json first
    try:
        cfg_path = os.path.join(os.path.dirname(__file__), "config", "users.json")
        with open(cfg_path) as f:
            users_cfg = json.load(f).get("users", [])
        for u in users_cfg:
            if u.get("email", "").lower() == email_lower:
                initials = u.get("initials", "")
                if initials:
                    _initials_cache[email_lower] = initials
                    return initials
    except Exception:
        pass
    # Derive from name in session
    name = session.get("user_name", "")
    if name:
        parts = name.split()
        initials = "".join(p[0].upper() for p in parts[:2])
        if initials:
            _initials_cache[email_lower] = initials
            return initials
    return "AI"


def authenticate_user(email, access_code):
    """Authenticate user by email and access code"""
    # Try Cosmos DB first
    user_db = get_user_db()
    if user_db and user_db.is_connected():
        user = user_db.authenticate_user(email, access_code)
        if user:
            return user

    # Fallback to file-based
    users = load_users()
    for user in users:
        if user["email"].lower() == email.lower() and user["access_code"] == access_code:
            return user
    return None


def login_required(f):
    """Decorator to require login for routes"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("logged_in"):
            if request.is_json or request.path.startswith("/api/"):
                return jsonify({"error": "Authentication required", "redirect": "/login"}), 401
            return redirect("/login")
        return f(*args, **kwargs)

    return decorated_function


def role_required(*allowed_roles):
    """Decorator to require specific roles for routes

    Roles hierarchy:
    - admin: Full access to everything
    - translator: Everything except publications management
    - user: Home, Word Lookup, AI Translation only
    """

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not session.get("logged_in"):
                if request.is_json or request.path.startswith("/api/"):
                    return jsonify({"error": "Authentication required", "redirect": "/login"}), 401
                return redirect("/login")

            user_role = session.get("user_role", "user")
            if user_role not in allowed_roles:
                if request.is_json or request.path.startswith("/api/"):
                    return jsonify({"error": "Access denied. Insufficient permissions."}), 403
                return jsonify({"error": "Access denied"}), 403

            return f(*args, **kwargs)

        return decorated_function

    return decorator


# Role permissions mapping
ROLE_PERMISSIONS = {
    "user": ["home", "lookup", "sentences", "translate", "grammar"],
    "translator": ["home", "lookup", "sentences", "translate", "database", "game", "grammar", "ai_training"],
    "admin": [
        "home",
        "lookup",
        "sentences",
        "translate",
        "database",
        "game",
        "publications",
        "new_publication",
        "grammar",
        "admin_users",
        "ai_training",
    ],
}


@app.route("/api/auth/login", methods=["POST"])
def api_login():
    """API endpoint for login - enforces single active session"""
    data = request.get_json()
    email = data.get("email", "").strip()
    access_code = data.get("access_code", "").strip()
    terms_accepted = data.get("terms_accepted", False)
    terms_accepted_at = data.get("terms_accepted_at")

    if not email or not access_code:
        return jsonify({"error": "Email and access code are required"}), 400

    user = authenticate_user(email, access_code)
    if user:
        # Update terms acceptance if provided
        if terms_accepted and terms_accepted_at:
            update_user_terms_acceptance(email, terms_accepted_at)

        # Record login time for activity tracking
        user_db = get_user_db()
        if user_db and user_db.is_connected():
            user_db.record_login(email)

        # Generate unique session ID for single active session enforcement
        new_session_id = secrets.token_hex(32)

        # Invalidate any existing session for this user (single active session)
        old_session = active_sessions.get(user["email"].lower())
        if old_session:
            print(f"🔐 Invalidating previous session for {user['email']}")

        # Store new session ID
        active_sessions[user["email"].lower()] = new_session_id

        session["logged_in"] = True
        session["user_email"] = user["email"]
        session["user_name"] = user.get("name", email)
        session["user_role"] = user.get("role", "user")
        session["session_id"] = new_session_id  # Store session ID for validation
        session.permanent = True
        user_role = user.get("role", "user")
        permissions = ROLE_PERMISSIONS.get(user_role, ROLE_PERMISSIONS["user"])
        return jsonify(
            {
                "success": True,
                "user": {"email": user["email"], "name": user.get("name", email), "role": user_role},
                "permissions": permissions,
            }
        )
    else:
        return jsonify({"error": "Invalid email or access code"}), 401


@app.route("/api/auth/check-terms", methods=["POST"])
def api_check_terms():
    """Check if user has already accepted terms"""
    data = request.get_json()
    email = data.get("email", "").strip()

    if not email:
        return jsonify({"error": "Email is required"}), 400

    users = load_users()
    for user in users:
        if user["email"].lower() == email.lower():
            has_accepted = user.get("terms_accepted", False)
            accepted_at = user.get("terms_accepted_at")
            return jsonify({"has_accepted": has_accepted, "accepted_at": accepted_at})

    return jsonify({"has_accepted": False})


@app.route("/api/auth/request-magic-link", methods=["POST"])
def api_request_magic_link():
    """Request a magic link for passwordless login"""
    data = request.get_json()
    email = data.get("email", "").strip().lower()

    if not email:
        return jsonify({"error": "Email is required"}), 400

    # Check if user exists
    users = load_users()
    user = next((u for u in users if u["email"].lower() == email), None)

    if not user:
        # Don't reveal if email exists or not for security
        return jsonify({"success": True, "message": "If this email is registered, a login link has been sent."})

    # Generate magic link token
    token = secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc) + timedelta(minutes=MAGIC_LINK_EXPIRY_MINUTES)

    # Store magic link
    magic_links[token] = {"email": user["email"], "expires": expires}

    # Get base URL
    base_url = request.url_root.rstrip("/")

    # Send email
    if send_magic_link_email(user["email"], token, base_url):
        return jsonify({"success": True, "message": "Login link sent to your email."})
    else:
        return jsonify({"error": "Failed to send email. Please try again."}), 500


@app.route("/auth/magic/<token>")
def api_verify_magic_link(token):
    """Verify magic link and create session"""
    if token not in magic_links:
        return redirect("/?error=invalid_link")

    link_data = magic_links[token]

    # Check if expired
    if datetime.now(timezone.utc) > link_data["expires"]:
        del magic_links[token]
        return redirect("/?error=link_expired")

    # Find user
    users = load_users()
    user = next((u for u in users if u["email"].lower() == link_data["email"].lower()), None)

    if not user:
        del magic_links[token]
        return redirect("/?error=user_not_found")

    # Delete used token (one-time use)
    del magic_links[token]

    # Generate unique session ID for single active session enforcement
    new_session_id = secrets.token_hex(32)

    # Invalidate any existing session for this user
    old_session = active_sessions.get(user["email"].lower())
    if old_session:
        print(f"🔐 Invalidating previous session for {user['email']} (magic link login)")

    active_sessions[user["email"].lower()] = new_session_id

    # Create session
    session["logged_in"] = True
    session["user_email"] = user["email"]
    session["user_name"] = user.get("name", user["email"])
    session["user_role"] = user.get("role", "user")
    session["session_id"] = new_session_id
    session.permanent = True

    return redirect("/")


@app.route("/api/auth/logout", methods=["POST"])
def api_logout():
    """API endpoint for logout"""
    # Record session end for activity tracking
    user_email = session.get("user_email", "").lower()
    if user_email:
        user_db = get_user_db()
        if user_db and user_db.is_connected():
            duration = user_db.record_logout(user_email)
            if duration is not None:
                print(f"📊 Session ended for {user_email}: {duration} minutes")

    # Remove from active sessions
    if user_email in active_sessions:
        del active_sessions[user_email]
    session.clear()
    return jsonify({"success": True})


@app.route("/api/auth/track-page", methods=["POST"])
@login_required
def api_track_page():
    """Track page access for the current user"""
    user_email = session.get("user_email", "")
    if not user_email:
        return jsonify({"error": "Not authenticated"}), 401

    data = request.get_json()
    page_path = data.get("page", "").strip()

    if not page_path:
        return jsonify({"error": "Page path is required"}), 400

    user_db = get_user_db()
    if user_db and user_db.is_connected():
        user_db.record_page_access(user_email, page_path)

    return jsonify({"success": True})


@app.route("/api/auth/status", methods=["GET"])
def api_auth_status():
    """Check authentication status - also validates single active session"""
    if session.get("logged_in"):
        user_email = session.get("user_email", "").lower()
        session_id = session.get("session_id")

        # Validate this is still the active session
        if active_sessions.get(user_email) != session_id:
            # Session was invalidated (user logged in elsewhere)
            session.clear()
            return jsonify({"authenticated": False, "error": "Session expired. You logged in from another device."})

        user_role = session.get("user_role", "user")
        permissions = ROLE_PERMISSIONS.get(user_role, ROLE_PERMISSIONS["user"])
        return jsonify(
            {
                "authenticated": True,
                "user": {"email": session.get("user_email"), "name": session.get("user_name"), "role": user_role},
                "permissions": permissions,
            }
        )
    return jsonify({"authenticated": False})


# ============================================================================
# Admin User Management API
# ============================================================================


@app.route("/api/admin/users", methods=["GET"])
@role_required("admin")
def api_get_users():
    """Get all users (admin only)"""
    user_db = get_user_db()
    if user_db and user_db.is_connected():
        users = user_db.get_all_users()
        # Remove access_code from response for security
        safe_users = []
        for user in users:
            safe_user = {k: v for k, v in user.items() if k != "access_code"}
            safe_users.append(safe_user)
        return jsonify({"users": safe_users})
    else:
        # Fallback to file-based
        users = load_users()
        safe_users = []
        for user in users:
            safe_user = {k: v for k, v in user.items() if k != "access_code"}
            safe_users.append(safe_user)
        return jsonify({"users": safe_users})


@app.route("/api/admin/users", methods=["POST"])
@role_required("admin")
def api_create_user():
    """Create a new user (admin only)"""
    data = request.get_json()
    email = data.get("email", "").strip().lower()
    name = data.get("name", "").strip()
    role = data.get("role", "user")

    if not email:
        return jsonify({"error": "Email is required"}), 400

    # Validate role
    if role not in ["user", "translator", "admin"]:
        return jsonify({"error": "Invalid role. Must be user, translator, or admin"}), 400

    # Generate random access code
    access_code = secrets.token_urlsafe(18)  # ~24 character code

    user_data = {
        "email": email,
        "name": name or email.split("@")[0],
        "role": role,
        "access_code": access_code,
        "terms_accepted": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    user_db = get_user_db()
    if user_db and user_db.is_connected():
        if user_db.get_user_by_email(email):
            return jsonify({"error": "User already exists"}), 409

        if user_db.create_user(user_data):
            return jsonify(
                {
                    "success": True,
                    "user": {"email": email, "name": user_data["name"], "role": role},
                    "access_code": access_code,  # Return once so admin can share
                }
            )
        else:
            return jsonify({"error": "Failed to create user"}), 500
    else:
        # Fallback to file-based
        users = load_users()
        for user in users:
            if user["email"].lower() == email:
                return jsonify({"error": "User already exists"}), 409

        users.append(user_data)
        save_users(users)
        return jsonify(
            {
                "success": True,
                "user": {"email": email, "name": user_data["name"], "role": role},
                "access_code": access_code,
            }
        )


@app.route("/api/admin/users/<email>", methods=["DELETE"])
@role_required("admin")
def api_delete_user(email):
    """Delete a user (admin only)"""
    email = email.lower()

    # Prevent deleting yourself
    if email == session.get("user_email", "").lower():
        return jsonify({"error": "Cannot delete your own account"}), 400

    user_db = get_user_db()
    if user_db and user_db.is_connected():
        if user_db.delete_user(email):
            return jsonify({"success": True})
        else:
            return jsonify({"error": "User not found"}), 404
    else:
        # Fallback to file-based
        users = load_users()
        original_count = len(users)
        users = [u for u in users if u["email"].lower() != email]

        if len(users) < original_count:
            save_users(users)
            return jsonify({"success": True})
        else:
            return jsonify({"error": "User not found"}), 404


# ============================================================================


def highlight_search_term(text, search_term):
    """Highlight search term in text with underline"""
    if not search_term or not text:
        return text

    # Escape HTML in the original text first
    from markupsafe import escape

    escaped_text = escape(str(text))

    # Create case-insensitive pattern
    pattern = re.compile(re.escape(search_term), re.IGNORECASE)

    # Replace with underlined version
    highlighted = pattern.sub(
        lambda m: f'<u style="text-decoration: underline; text-decoration-color: #003d82; text-decoration-thickness: 2px; text-underline-offset: 3px;">{m.group(0)}</u>',
        str(escaped_text),
    )

    return Markup(highlighted)


# Register the filter
app.jinja_env.filters["highlight"] = highlight_search_term


def allowed_file(filename):
    """Check if file extension is allowed"""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# Removed conflicting index route - handled by serve_react below


# Disabled - handled by React Router
# @app.route('/publication/new', methods=['GET', 'POST'])
# def new_publication():
#     """Redirect to React app"""
#     return redirect('/')


# Disabled - handled by React Router
# @app.route('/publication/<pub_id>')
# def view_publication(pub_id):
#     """Redirect to React app"""
#     return redirect('/')


@app.route("/publication/<pub_id>/upload", methods=["POST"])
@app.route("/api/publications/<pub_id>/upload", methods=["POST"])
def upload_page(pub_id):
    """Upload a page to a publication"""
    # Validate publication ID format (timestamp + UUID)
    if not re.match(r"^\d{14}_[a-f0-9]{8}$", pub_id):
        return jsonify({"error": "Invalid publication ID"}), 400

    publication = pub_manager.get_publication(pub_id)

    if not publication:
        return jsonify({"error": "Publication not found"}), 404

    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]

    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)

        # Create publication directory
        pub_dir = os.path.join(app.config["UPLOAD_FOLDER"], pub_id)
        os.makedirs(pub_dir, exist_ok=True)

        # Save file
        file_path = os.path.join(pub_dir, filename)
        file.save(file_path)

        # Process OCR if requested
        process_ocr = request.form.get("ocr", request.form.get("process_ocr", "false")) == "true"
        index_dictionary = request.form.get("index_dictionary", "false") == "true"
        ocr_results = None

        print(f"📤 Upload: process_ocr={process_ocr}, index_dictionary={index_dictionary}")
        print(f"📋 Form data: {dict(request.form)}")

        # Create processing session for logging
        session_id = str(uuid.uuid4())

        if process_ocr:
            lang = request.form.get("ocr_lang", "eng")

            # Initialize logger
            processing_logger.create_session(session_id, filename)
            processing_logger.log(session_id, f"Starting OCR processing for {filename}")
            processing_logger.log(session_id, f"OCR Language: {lang}")
            processing_logger.log(session_id, f"Dictionary indexing: {'enabled' if index_dictionary else 'disabled'}")

            try:
                processing_logger.log(session_id, f"Starting OCR processing with language: {lang}")

                # Log OCR capabilities
                has_tesseract = hasattr(ocr_processor, "process_image_tesseract")
                has_google_vision = ocr_processor.use_google_vision
                processing_logger.log(
                    session_id, f"OCR Capabilities - Tesseract: {has_tesseract}, Google Vision: {has_google_vision}"
                )

                ocr_results = ocr_processor.process_image(file_path, lang)

                print("\n=== OCR PROCESSING DEBUG ===")
                print(f"File: {filename}")
                print(f"File extension: {os.path.splitext(filename)[1].lower()}")
                print(f"Has Google Vision: {ocr_processor.use_google_vision}")
                print(f"OCR Results Keys: {list(ocr_results.keys())}")

                if ocr_results.get("type") == "docx":
                    print(f"DOCX Processing - Pages: {ocr_results.get('total_pages', 0)}")
                    print(f"DOCX Text Length: {len(ocr_results.get('text', ''))}")
                elif "tesseract" in ocr_results:
                    print(f"Tesseract Text Length: {len(ocr_results.get('tesseract', ''))}")
                if "google_vision" in ocr_results:
                    print(f"Google Vision Text Length: {len(ocr_results.get('google_vision', ''))}")

                print(f"Primary Text Length: {len(ocr_results.get('text', ''))}")
                print("=========================")

                # Log OCR method used with more detail
                ocr_method_used = "Unknown"
                if ocr_results.get("type") == "docx":
                    ocr_method_used = "DOCX Text Extraction"
                    processing_logger.log(session_id, "✓ Using DOCX text extraction (no OCR needed)", "info")
                elif ocr_results.get("type") == "pdf":
                    if ocr_results.get("pages"):
                        # Check first page for method indicators
                        first_page = ocr_results["pages"][0]
                        if "google_vision" in first_page and "tesseract" in first_page:
                            ocr_method_used = "Google Vision + Tesseract (PDF)"
                            processing_logger.log(
                                session_id, "✓ Using Google Cloud Vision API + Tesseract for PDF processing", "info"
                            )
                        elif "tesseract" in first_page:
                            ocr_method_used = "Tesseract Only (PDF)"
                            processing_logger.log(session_id, "✓ Using Tesseract OCR for PDF processing", "info")
                else:
                    if "google_vision" in ocr_results and "tesseract" in ocr_results:
                        ocr_method_used = "Google Vision + Tesseract"
                        processing_logger.log(
                            session_id, "✓ Using Google Cloud Vision API + Tesseract for image processing", "info"
                        )
                    elif "tesseract" in ocr_results:
                        ocr_method_used = "Tesseract Only"
                        processing_logger.log(session_id, "✓ Using Tesseract OCR for image processing", "info")

                processing_logger.update_stats(session_id, ocr_method=ocr_method_used)

                # Update total pages if PDF
                if ocr_results.get("type") == "pdf":
                    total_pages = ocr_results.get("total_pages", 1)
                    processing_logger.update_stats(session_id, total_pages=total_pages)
                    processing_logger.log(session_id, f"PDF detected with {total_pages} pages")

                # Index dictionary entries if this is a dictionary document
                if index_dictionary and ocr_results and "text" in ocr_results:
                    try:
                        processing_logger.log(session_id, "Starting dictionary indexing...")
                        indexed_pages = 0
                        total_entries = 0

                        # Handle PDF with multiple pages
                        if ocr_results.get("type") == "pdf" and "pages" in ocr_results:
                            for page_data in ocr_results["pages"]:
                                page_num = page_data["page_number"]
                                processing_logger.update_page(session_id, page_num)
                                processing_logger.log(
                                    session_id, f"Processing page {page_num}/{ocr_results['total_pages']}"
                                )

                                if page_data.get("text"):
                                    processing_logger.log(
                                        session_id, f"Extracting dictionary entries from page {page_num}..."
                                    )

                                    # Count entries before indexing
                                    entries_before = dict_db.get_statistics().get("total_entries", 0)

                                    page_id = dict_db.add_dictionary_page(
                                        pub_id, filename, page_data["text"], page_data["page_number"]
                                    )

                                    # Count entries after indexing
                                    entries_after = dict_db.get_statistics().get("total_entries", 0)
                                    page_entries = entries_after - entries_before
                                    total_entries += page_entries

                                    if page_id:
                                        indexed_pages += 1
                                        processing_logger.log(
                                            session_id, f"✓ Page {page_num}: {page_entries} word pairs indexed"
                                        )
                                    else:
                                        processing_logger.log(
                                            session_id, f"⚠ Page {page_num}: No entries found", "warning"
                                        )
                                else:
                                    processing_logger.log(
                                        session_id, f"⚠ Page {page_num}: No text extracted", "warning"
                                    )

                            processing_logger.update_stats(
                                session_id,
                                words_indexed=total_entries,
                                entries_created=total_entries,
                                pages_processed=indexed_pages,
                            )
                            processing_logger.log(
                                session_id, f"✅ Completed: {indexed_pages} pages, {total_entries} word pairs indexed"
                            )
                            flash(
                                f"Indexed {indexed_pages} pages with {total_entries} word pairs from {filename}",
                                "success",
                            )

                        # Handle single image
                        else:
                            processing_logger.log(session_id, "Processing single image for dictionary entries...")

                            entries_before = dict_db.get_statistics().get("total_entries", 0)
                            page_id = dict_db.add_dictionary_page(pub_id, filename, ocr_results["text"], 1)
                            entries_after = dict_db.get_statistics().get("total_entries", 0)
                            entries_found = entries_after - entries_before

                            if page_id:
                                processing_logger.log(session_id, f"✅ {entries_found} word pairs indexed from image")
                                processing_logger.update_stats(
                                    session_id, words_indexed=entries_found, entries_created=entries_found
                                )
                                flash(
                                    f"Dictionary entries indexed from {filename}: {entries_found} word pairs", "success"
                                )
                            else:
                                processing_logger.log(session_id, "⚠ No dictionary entries found", "warning")

                        processing_logger.set_status(session_id, "completed")

                    except Exception as e:
                        processing_logger.log(session_id, f"❌ Error indexing dictionary: {str(e)}", "error")
                        processing_logger.update_stats(session_id, errors=1)
                        processing_logger.set_status(session_id, "failed")
                        flash(f"Error indexing dictionary: {str(e)}", "warning")
                else:
                    processing_logger.log(session_id, "OCR completed - dictionary indexing skipped")
                    processing_logger.set_status(session_id, "completed")

            except Exception as e:
                processing_logger.log(session_id, f"❌ OCR processing failed: {str(e)}", "error")
                processing_logger.set_status(session_id, "failed")
                flash(f"Error processing OCR: {str(e)}", "error")

        # Add page to publication with processed status
        entries_count = 0
        if index_dictionary and ocr_results and "text" in ocr_results:
            # Count entries that were just indexed
            entries_before = dict_db.get_statistics().get("total_entries", 0) if dict_db else 0
            # The indexing happens above in the index_dictionary block
            entries_after = dict_db.get_statistics().get("total_entries", 0) if dict_db else 0
            entries_count = max(0, entries_after - entries_before)

        pub_manager.add_page(pub_id, filename, ocr_results, processed=index_dictionary, entries_count=entries_count)

        flash("Page uploaded successfully", "success")
        return jsonify(
            {
                "success": True,
                "filename": filename,
                "ocr_results": ocr_results,
                "session_id": session_id if process_ocr else None,
                "processed": index_dictionary,
                "entries_count": entries_count,
            }
        )

    return jsonify({"error": "Invalid file type"}), 400


@app.route("/api/processing/status/<session_id>", methods=["GET"])
def get_processing_status(session_id):
    """Get current processing status for a session"""
    logs = processing_logger.get_logs(session_id)
    if logs:
        return jsonify(logs)
    return jsonify({"error": "Session not found"}), 404


@app.route("/api/processing/stream/<session_id>")
def stream_processing_status(session_id):
    """Stream processing status updates via Server-Sent Events"""

    def generate():
        last_log_count = 0
        max_wait = 120  # 2 minutes timeout
        waited = 0

        while waited < max_wait:
            logs = processing_logger.get_logs(session_id)

            if not logs:
                yield f"data: {json.dumps({'error': 'Session not found'})}\n\n"
                break

            # Send update if there are new logs
            current_log_count = len(logs.get("logs", []))
            if current_log_count > last_log_count or waited == 0:
                last_log_count = current_log_count
                yield f"data: {json.dumps(logs)}\n\n"

            # Check if processing is complete
            if logs.get("status") in ["completed", "failed"]:
                yield f"data: {json.dumps(logs)}\n\n"
                break

            time.sleep(0.5)
            waited += 0.5

        # Send final status
        final_logs = processing_logger.get_logs(session_id)
        if final_logs:
            yield f"data: {json.dumps(final_logs)}\n\n"

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@app.route("/publication/<pub_id>/upload_csv", methods=["POST"])
@app.route("/api/publications/<pub_id>/upload_csv", methods=["POST"])
def upload_csv(pub_id):
    """Upload and process a CSV file into the dictionary database"""
    # Validate publication ID format (timestamp + UUID)
    if not re.match(r"^\d{14}_[a-f0-9]{8}$", pub_id):
        return jsonify({"error": "Invalid publication ID"}), 400

    publication = pub_manager.get_publication(pub_id)

    if not publication:
        return jsonify({"error": "Publication not found"}), 404

    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]

    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400

    # Get optional confidence score from form data (default 100%)
    confidence_score = int(request.form.get("confidence_score", 100))

    if file and file.filename.lower().endswith(".csv") or file.filename.lower().endswith(".tsv"):
        filename = secure_filename(file.filename)

        # Read CSV content
        try:
            csv_content = file.read().decode("utf-8")
        except UnicodeDecodeError:
            return jsonify({"error": "Invalid CSV encoding. Please use UTF-8."}), 400

        # Create processing session for logging
        session_id = str(uuid.uuid4())

        # Initialize logger
        processing_logger.create_session(session_id, filename)
        processing_logger.log(session_id, f"Starting CSV processing for {filename} with confidence {confidence_score}%")

        try:
            # Process CSV into database
            import sys

            sys.stdout.flush()
            print(f"\n🔍 DEBUG: dict_db.client is {'available' if dict_db.client else 'None'}", flush=True)
            print(
                f"🔍 DEBUG: About to call add_dictionary_from_csv with pub_id={pub_id}, filename={filename}, confidence_score={confidence_score}",
                flush=True,
            )
            page_id, entries_added = dict_db.add_dictionary_from_csv(
                pub_id, filename, csv_content, confidence_score=confidence_score
            )
            print(f"🔍 DEBUG: Returned page_id={page_id}, entries_added={entries_added}\n", flush=True)

            if page_id:
                processing_logger.log(session_id, f"✅ Successfully processed CSV: {entries_added} entries added")
                processing_logger.update_stats(session_id, words_indexed=entries_added, entries_created=entries_added)
                processing_logger.set_status(session_id, "completed")

                # Add CSV file to publication
                csv_metadata = {
                    "filename": filename,
                    "type": "csv",
                    "entries_added": entries_added,
                    "processed_date": datetime.now().isoformat(),
                }
                pub_manager.add_page(pub_id, filename, csv_metadata)

                flash(f"CSV processed successfully: {entries_added} dictionary entries added", "success")
                return jsonify(
                    {"success": True, "filename": filename, "entries_added": entries_added, "session_id": session_id}
                )
            else:
                processing_logger.log(session_id, "❌ Failed to process CSV - database not available", "error")
                processing_logger.set_status(session_id, "failed")
                return jsonify({"error": "Database not available for CSV processing"}), 500

        except Exception as e:
            import traceback

            error_details = traceback.format_exc()
            print(f"❌ CSV UPLOAD ERROR: {error_details}")
            processing_logger.log(session_id, f"❌ CSV processing failed: {str(e)}", "error")
            processing_logger.set_status(session_id, "failed")
            return jsonify({"error": f"Error processing CSV: {str(e)}"}), 500

    return jsonify({"error": "Invalid file type. Only CSV files are supported."}), 400


@app.route("/ocr/process", methods=["POST"])
@app.route("/api/ocr/process", methods=["POST"])
def process_ocr():
    """Process OCR on a specific page and optionally index dictionary entries"""
    pub_id = request.form.get("pub_id")
    filename = request.form.get("filename")
    lang = request.form.get("lang", "eng")
    index_dictionary = request.form.get("index_dictionary", "true") == "true"

    if not pub_id or not filename:
        return jsonify({"error": "Missing parameters"}), 400

    file_path = pub_manager.get_page_path(pub_id, filename)

    if not os.path.exists(file_path):
        return jsonify({"error": "File not found"}), 404

    # Process OCR
    results = ocr_processor.process_image(file_path, lang)

    response_data = {"success": True, "ocr_text": results.get("text", ""), "indexed": False, "entries_count": 0}

    # Index dictionary entries if requested
    if index_dictionary and results and "text" in results:
        try:
            # Count entries before indexing
            entries_before = dict_db.get_statistics().get("total_entries", 0)

            # Index the page
            dict_db.add_dictionary_page(pub_id, filename, results["text"], 1)

            # Count entries after indexing
            entries_after = dict_db.get_statistics().get("total_entries", 0)
            entries_count = entries_after - entries_before

            response_data["indexed"] = True
            response_data["entries_count"] = entries_count
            response_data["message"] = f"Processed OCR and indexed {entries_count} dictionary entries"
        except Exception as e:
            response_data["index_error"] = str(e)
            response_data["message"] = f"OCR processed but indexing failed: {str(e)}"
    else:
        response_data["message"] = "OCR processed successfully"

    return jsonify(response_data)


@app.route("/ocr/reprocess", methods=["POST"])
@app.route("/api/ocr/reprocess", methods=["POST"])
def reprocess_page():
    """Reprocess an already-indexed page, updating entries with better field values"""
    pub_id = request.form.get("pub_id")
    filename = request.form.get("filename")
    page_number = int(request.form.get("page_number", 1))

    if not pub_id or not filename:
        return jsonify({"error": "Missing parameters"}), 400

    try:
        # Reprocess the page
        stats = dict_db.reprocess_page(pub_id, filename, page_number)

        if not stats.get("success"):
            error_msg = stats.get("error", "Unknown error")
            print(f"Reprocess failed: {error_msg}")
            return jsonify(stats), 400 if "not found" in error_msg.lower() else 500

        # Build response message
        message_parts = []
        if stats.get("new_entries", 0) > 0:
            message_parts.append(f"{stats['new_entries']} new entries")
        if stats.get("updated_entries", 0) > 0:
            message_parts.append(f"{stats['updated_entries']} entries updated")

        response_data = {
            "success": True,
            "stats": stats,
            "message": f"Reprocessed: {', '.join(message_parts) if message_parts else 'No changes needed'}",
        }

        return jsonify(response_data)

    except Exception as e:
        return jsonify({"success": False, "error": str(e), "message": f"Reprocessing failed: {str(e)}"}), 500


@app.route("/api/publications/<pub_id>/update-confidence", methods=["POST"])
def update_publication_confidence(pub_id):
    """Bulk update confidence scores for all entries from a specific publication"""

    def batch_update_collection(collection, query, confidence_score, collection_name):
        """Update documents in batches to avoid Cosmos DB rate limiting"""
        updated_count = 0
        batch_size = 50
        max_retries = 5

        # Get all document IDs first
        docs = list(collection.find(query, {"_id": 1}))
        total_docs = len(docs)

        if total_docs == 0:
            return 0, 0  # (found, modified)

        print(f"   [{collection_name}] Found {total_docs} documents to update")

        for i in range(0, total_docs, batch_size):
            batch_ids = [doc["_id"] for doc in docs[i : i + batch_size]]
            batch_num = i // batch_size + 1
            total_batches = (total_docs + batch_size - 1) // batch_size

            retries = max_retries
            while retries > 0:
                try:
                    result = collection.update_many(
                        {"_id": {"$in": batch_ids}}, {"$set": {"confidence_score": confidence_score}}
                    )
                    updated_count += result.modified_count
                    print(f"   [{collection_name}] Batch {batch_num}/{total_batches}: {result.modified_count} updated")
                    break
                except Exception as e:
                    error_str = str(e)
                    if "16500" in error_str:
                        retries -= 1
                        retry_match = re.search(r"RetryAfterMs=(\d+)", error_str)
                        delay = max(int(retry_match.group(1)) / 1000.0 if retry_match else 1.0, 1.0)
                        delay = min(delay * (2 ** (max_retries - retries)), 10.0)
                        print(f"   [{collection_name}] Rate limited, waiting {delay:.1f}s ({retries} retries left)")
                        time.sleep(delay)
                    else:
                        print(f"   [{collection_name}] Error: {e}")
                        break

            time.sleep(0.3)  # Small delay between batches

        return total_docs, updated_count  # (found, modified)

    try:
        data = request.get_json()
        confidence_score = data.get("confidence_score", 100)
        filename = data.get("filename")  # Optional: limit to specific file

        if not isinstance(confidence_score, (int, float)) or confidence_score < 0 or confidence_score > 100:
            return jsonify({"error": "Invalid confidence score. Must be between 0 and 100."}), 400

        # Build query filter
        query = {"publication_id": pub_id}
        if filename:
            query["filename"] = filename

        print(f"📊 Updating confidence for publication {pub_id} to {confidence_score}%")
        print(f"   Query: {query}")

        dict_found, dict_modified = 0, 0
        phrases_found, phrases_modified = 0, 0
        paragraphs_found, paragraphs_modified = 0, 0

        # Update all matching entries in dictionary_collection
        if dict_db.dictionary_collection is not None:
            dict_found, dict_modified = batch_update_collection(
                dict_db.dictionary_collection, query, confidence_score, "dictionary"
            )

        # Update all matching entries in phrases_collection
        if dict_db.phrases_collection is not None:
            phrases_found, phrases_modified = batch_update_collection(
                dict_db.phrases_collection, query, confidence_score, "phrases"
            )

        # Update all matching entries in paragraphs_collection
        if hasattr(dict_db, "paragraphs_collection") and dict_db.paragraphs_collection is not None:
            paragraphs_found, paragraphs_modified = batch_update_collection(
                dict_db.paragraphs_collection, query, confidence_score, "paragraphs"
            )

        total_found = dict_found + phrases_found + paragraphs_found
        total_modified = dict_modified + phrases_modified + paragraphs_modified
        print(f"✅ Total: {total_found} entries processed, {total_modified} changed to {confidence_score}%")

        # Show "found" count in message (more meaningful than "modified" when values already match)
        return jsonify(
            {
                "success": True,
                "message": f"Set {total_found} entries to {confidence_score}% confidence ({total_modified} changed)",
                "stats": {
                    "dictionary_entries": dict_found,
                    "phrase_entries": phrases_found,
                    "paragraph_entries": paragraphs_found,
                    "total": total_found,
                    "modified": total_modified,
                },
            }
        )

    except Exception as e:
        import traceback

        print(f"❌ Error updating confidence: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# Disabled - handled by React Router
# @app.route('/translate', methods=['GET', 'POST'])
# def translate():
#     """Redirect to React app"""
#     return redirect('/')


def translate_phrases(phrases, direction):
    """Translate multiple phrases individually and return with confidence scores"""
    api_key = os.getenv("GOOGLE_CLOUD_API_KEY")
    results = {"success": True, "direction": direction, "phrases": []}

    for phrase in phrases:
        phrase_text = phrase.strip()
        if not phrase_text:
            continue

        phrase_result = {
            "original": phrase_text,
            "translation": "",
            "confidence": "low",  # low, medium, high, verified
            "sources": {},
        }

        # Try Google Translate
        try:
            if api_key:
                url = f"https://translation.googleapis.com/language/translate/v2?key={api_key}"

                payload = {"q": phrase_text, "target": "en" if direction == "chk_to_en" else "chk", "format": "text"}

                # Add source language
                if direction == "chk_to_en":
                    payload["source"] = "chk"
                elif direction == "en_to_chk":
                    payload["source"] = "en"

                response = requests.post(url, json=payload, timeout=10)
                if response.status_code == 200:
                    result = response.json()
                    translation = result["data"]["translations"][0]["translatedText"]
                    phrase_result["translation"] = translation
                    phrase_result["sources"]["google"] = translation
                    phrase_result["confidence"] = "medium"  # Auto-translated
        except Exception as e:
            phrase_result["sources"]["google"] = f"Error: {str(e)}"

        # Check if phrase exists in database (verified translation)
        try:
            # Look for exact or similar match
            db_entry = dict_db.dictionary_collection.find_one(
                {"chuukese_word": {"$regex": f"^{re.escape(phrase_text)}$", "$options": "i"}}
            )
            if db_entry:
                phrase_result["translation"] = db_entry.get("english_translation", phrase_result["translation"])
                phrase_result["sources"]["database"] = db_entry.get("english_translation")
                phrase_result["confidence"] = "high"  # From verified database
                if db_entry.get("confidence_level"):
                    phrase_result["confidence"] = db_entry["confidence_level"]
        except Exception:
            pass

        results["phrases"].append(phrase_result)

    return jsonify(results)


@app.route("/api/translate", methods=["POST"])
def api_translate():
    """Translate using all three sources: Google, Helsinki, Ollama"""
    try:
        data = request.get_json()
        text = data.get("text", "").strip()
        direction = data.get("direction", "auto")
        phrases = data.get("phrases", [])  # Optional: pre-split phrases

        if not text and not phrases:
            return jsonify({"success": False, "error": "No text provided"})

        # Determine actual direction if auto
        if direction == "auto":
            # Simple heuristic: if text contains mostly ASCII, assume English
            check_text = text if text else " ".join(phrases)
            is_english = all(ord(c) < 128 for c in check_text if c.isalpha())
            direction = "en_to_chk" if is_english else "chk_to_en"

        # If phrases provided, translate each individually
        if phrases:
            return translate_phrases(phrases, direction)

        # Otherwise, translate full text
        results = {"success": True, "original_text": text, "translations": {}}

        # Google Translate - Using REST API with API key
        try:
            api_key = os.getenv("GOOGLE_CLOUD_API_KEY")

            if api_key:
                # Use REST API directly with API key
                url = f"https://translation.googleapis.com/language/translate/v2?key={api_key}"

                payload = {"q": text, "target": "en" if direction == "chk_to_en" else "chk", "format": "text"}

                # Add source language if not auto-detect
                if direction == "chk_to_en":
                    payload["source"] = "chk"
                elif direction == "en_to_chk":
                    payload["source"] = "en"

                response = requests.post(url, json=payload, timeout=10)

                if response.status_code == 200:
                    result = response.json()
                    translation = result["data"]["translations"][0]["translatedText"]
                    results["translations"]["google"] = translation
                else:
                    error_msg = response.json().get("error", {}).get("message", f"Status {response.status_code}")
                    results["translations"]["google"] = f"Google API error: {error_msg}"
            else:
                results["translations"]["google"] = "Google Translate API key not configured"
        except Exception as e:
            results["translations"]["google"] = f"Google Translate error: {str(e)}"

        # Helsinki-NLP
        try:
            if helsinki_translator:
                if direction == "chk_to_en":
                    helsinki_result = helsinki_translator.translate_chuukese_to_english(text)
                else:
                    helsinki_result = helsinki_translator.translate_english_to_chuukese(text)
                results["translations"]["helsinki"] = helsinki_result
            else:
                results["translations"]["helsinki"] = "Helsinki translator not available"
        except Exception as e:
            results["translations"]["helsinki"] = f"Error: {str(e)}"

        # Ollama LLM (disabled by default; set OLLAMA_ENABLED=true to activate)
        if not OLLAMA_ENABLED:
            results["translations"]["ollama"] = {"available": False, "reason": "Ollama disabled (OLLAMA_ENABLED=false)"}
        else:
            try:
                from src.translation.llm_trainer import ChuukeseLLMTrainer

                ollama_trainer = ChuukeseLLMTrainer()

                if ollama_trainer.check_ollama_installation():
                    ollama_result = ollama_trainer.translate_text(text, direction)
                    results["translations"]["ollama"] = ollama_result
                else:
                    results["translations"]["ollama"] = "Ollama is not running. Start Ollama to use this translator."
            except Exception as e:
                results["translations"]["ollama"] = f"Error: {str(e)}"

        return jsonify(results)

    except Exception as e:
        return jsonify({"success": False, "error": f"Translation failed: {str(e)}"})


@app.route("/api/translate/correction", methods=["POST"])
def api_translate_correction():
    """Save translation correction and optionally retrain models"""
    try:
        data = request.get_json()
        original_text = data.get("original_text", "").strip()
        corrected_text = data.get("corrected_text", "").strip()
        direction = data.get("direction", "auto")
        retrain = data.get("retrain", False)

        if not original_text or not corrected_text:
            return jsonify({"success": False, "error": "Both original and corrected text are required"})

        # Determine Chuukese and English text based on direction
        if direction == "chk_to_en":
            chuukese_word = original_text
            english_translation = corrected_text
        elif direction == "en_to_chk":
            chuukese_word = corrected_text
            english_translation = original_text
        else:
            # Auto-detect: assume English input
            is_english = all(ord(c) < 128 for c in original_text if c.isalpha())
            if is_english:
                chuukese_word = corrected_text
                english_translation = original_text
            else:
                chuukese_word = original_text
                english_translation = corrected_text

        # Save to database
        from src.database.dictionary_db import DictionaryDB

        db = DictionaryDB()

        # Determine if it's a phrase or single word
        word_type = "phrase" if " " in chuukese_word else None

        # Use add_word or add_phrase depending on content
        if " " in chuukese_word or " " in english_translation:
            # It's a phrase
            word_id = db.add_phrase(
                chuukese_phrase=chuukese_word,
                english_translation=english_translation,
                source="user_correction",
                definition="User correction from translation",
            )
        else:
            # It's a single word
            word_id = db.add_word(
                chuukese=chuukese_word,
                english_translation=english_translation,
                grammar=word_type,
                source="user_correction",
                definition="User correction from translation",
            )

        # Optionally trigger retraining in background
        if retrain:

            def retrain_models():
                global training_status
                try:
                    training_status["is_training"] = True
                    training_status["models_training"] = [
                        "Google Translate",
                        "Helsinki-NLP (Chk→En)",
                        "Helsinki-NLP (En→Chk)",
                        "Ollama AI",
                    ]
                    training_status["progress"] = 0
                    training_status["message"] = "Starting model retraining..."

                    # Step 1: Validate with Google Translate
                    print("✅ Validating with Google Translate...")
                    training_status["progress"] = 10
                    training_status["message"] = "Validating translation with Google Translate..."
                    import time

                    time.sleep(1)  # Brief validation pause

                    training_status["progress"] = 15

                    # Step 2: Fine-tune Helsinki models with real training
                    print("🔄 Fine-tuning Helsinki-NLP models...")
                    training_status["progress"] = 20
                    training_status["message"] = "Fine-tuning Helsinki-NLP models..."
                    training_status["epoch_current"] = None
                    training_status["epoch_total"] = None
                    training_status["current_direction"] = "chk_to_en"

                    try:
                        from src.training.helsinki_trainer import HelsinkiFineTuner

                        def helsinki_progress(
                            stage, progress, epoch=None, total_epochs=None, epoch_step_pct=None, epoch_loss=None
                        ):
                            # Map 20-60% for Helsinki training
                            if progress is not None:
                                adjusted_progress = 20 + (progress * 0.4)
                                training_status["progress"] = int(adjusted_progress)
                            training_status["message"] = stage
                            if epoch is not None:
                                training_status["epoch_current"] = epoch
                            if total_epochs is not None:
                                training_status["epoch_total"] = total_epochs
                            if epoch_step_pct is not None:
                                training_status["epoch_step_pct"] = epoch_step_pct
                            if epoch_loss is not None:
                                training_status["epoch_loss"] = epoch_loss

                        helsinki_trainer = HelsinkiFineTuner(progress_callback=helsinki_progress)
                        helsinki_success = helsinki_trainer.fine_tune_both_models(
                            num_epochs=1,  # Quick 1-epoch fine-tuning to prevent crashes
                            batch_size=2,  # Small batch size for safety
                        )

                        if helsinki_success:
                            print("✅ Helsinki models fine-tuned successfully")
                            # Reload the translator to use the new fine-tuned models
                            if helsinki_translator:
                                print("🔄 Reloading Helsinki translator with fine-tuned models...")
                                helsinki_translator.reload_models()
                        else:
                            print("⚠️  Helsinki fine-tuning had issues, continuing...")
                    except Exception as e:
                        print(f"⚠️  Helsinki fine-tuning error: {e}")
                        import traceback

                        traceback.print_exc()
                        # Continue with Ollama training even if Helsinki fails

                    training_status["progress"] = 60
                    training_status["epoch_current"] = None
                    training_status["epoch_total"] = None
                    training_status["current_direction"] = None

                    # Step 3: Retrain Ollama (skipped when OLLAMA_ENABLED=false)
                    if OLLAMA_ENABLED:
                        from src.translation.llm_trainer import ChuukeseLLMTrainer

                        trainer = ChuukeseLLMTrainer()
                        if trainer.check_ollama_installation():
                            print("\ud83d\udd04 Retraining Ollama model...")
                            training_status["message"] = "Training Ollama AI model..."
                            training_status["progress"] = 75
                            trainer.train_full_pipeline()
                    else:
                        print("\u23ed\ufe0f  Ollama retraining skipped (OLLAMA_ENABLED=false)")
                        training_status["progress"] = 75

                    training_status["progress"] = 100
                    training_status["message"] = "Training complete!"
                    training_status["last_training"] = datetime.now().isoformat()

                except Exception as e:
                    print(f"❌ Retraining error: {e}")
                    training_status["message"] = f"Training error: {str(e)}"
                finally:
                    # Reset after a delay
                    import time

                    time.sleep(3)
                    training_status["is_training"] = False
                    training_status["models_training"] = []
                    training_status["progress"] = 0

            thread = threading.Thread(target=retrain_models)
            thread.daemon = True
            thread.start()

        return jsonify(
            {"success": True, "message": "Correction saved" + (" and models will be retrained" if retrain else "")}
        )

    except Exception as e:
        return jsonify({"success": False, "error": f"Failed to save correction: {str(e)}"})


@app.route("/api/translate/training-status", methods=["GET"])
def api_training_status():
    """Get current training status"""
    global training_status
    return jsonify(training_status)


# ============================================================================
# AI Training Routes  (/api/ai-training/*)
# ============================================================================

def _get_trainer():
    """Return the global ContinuousTrainer instance, or None if unavailable."""
    return _continuous_trainer


@app.route("/api/ai-training/status", methods=["GET"])
def api_ai_training_status():
    """Return live training status from the ContinuousTrainer."""
    trainer = _get_trainer()
    if not trainer:
        return jsonify({"error": "Training engine not available"}), 503
    return jsonify(trainer.get_status())


@app.route("/api/ai-training/start", methods=["POST"])
def api_ai_training_start():
    """Manually trigger a full fine-tune run (both directions)."""
    if not session.get("logged_in"):
        return jsonify({"error": "Unauthorized"}), 401
    user_role = session.get("user_role", "user")
    if "ai_training" not in ROLE_PERMISSIONS.get(user_role, []):
        return jsonify({"error": "Forbidden"}), 403

    trainer = _get_trainer()
    if not trainer:
        return jsonify({"error": "Training engine not available"}), 503
    if trainer.is_training:
        return jsonify({"success": False, "message": "Training already in progress",
                        "run_id": trainer._current_run.run_id if trainer._current_run else None})

    data = request.get_json(silent=True) or {}
    num_epochs = int(data.get("num_epochs", 3))
    batch_size = int(data.get("batch_size", 2))
    run_id = trainer.run_full_training_async(
        trigger="manual", num_epochs=num_epochs, batch_size=batch_size
    )
    return jsonify({"success": True, "run_id": run_id, "message": "Training started"})


@app.route("/api/ai-training/lora-teach", methods=["POST"])
def api_ai_training_lora_teach():
    """Quick LoRA update to teach one translation pair immediately."""
    if not session.get("logged_in"):
        return jsonify({"error": "Unauthorized"}), 401
    user_role = session.get("user_role", "user")
    if "ai_training" not in ROLE_PERMISSIONS.get(user_role, []):
        return jsonify({"error": "Forbidden"}), 403

    data = request.get_json(silent=True) or {}
    chuukese = (data.get("chuukese") or "").strip()
    english = (data.get("english") or "").strip()
    direction = data.get("direction", "both")

    if not chuukese or not english:
        return jsonify({"error": "chuukese and english are required"}), 400
    if direction not in ("both", "chk_to_en", "en_to_chk"):
        return jsonify({"error": "direction must be both|chk_to_en|en_to_chk"}), 400

    trainer = _get_trainer()
    if not trainer:
        return jsonify({"error": "Training engine not available"}), 503

    # Run synchronously in a thread and wait briefly, then return
    result_holder = {}
    def _teach():
        result_holder["result"] = trainer.teach_pair_lora(chuukese, english, direction)
    t = threading.Thread(target=_teach, daemon=True)
    t.start()
    # Return immediately — the caller can poll /status for completion
    return jsonify({"success": True,
                    "message": f"LoRA teach queued for '{chuukese}' ↔ '{english}'"})


@app.route("/api/ai-training/history", methods=["GET"])
def api_ai_training_history():
    """Return recent training run history."""
    trainer = _get_trainer()
    if not trainer:
        return jsonify({"error": "Training engine not available"}), 503
    limit = min(int(request.args.get("limit", 20)), 50)
    return jsonify({"runs": trainer.get_run_history(limit=limit)})


@app.route("/api/ai-training/sources", methods=["GET"])
def api_ai_training_sources():
    """Return pair-count breakdown per training data source."""
    trainer = _get_trainer()
    if not trainer:
        return jsonify({"error": "Training engine not available"}), 503
    return jsonify(trainer.get_training_data_stats())


@app.route("/api/ai-training/merge-lora", methods=["POST"])
def api_ai_training_merge_lora():
    """Trigger a full fine-tune to merge pending LoRA adapters into the base weights."""
    if not session.get("logged_in"):
        return jsonify({"error": "Unauthorized"}), 401
    user_role = session.get("user_role", "user")
    if "ai_training" not in ROLE_PERMISSIONS.get(user_role, []):
        return jsonify({"error": "Forbidden"}), 403

    trainer = _get_trainer()
    if not trainer:
        return jsonify({"error": "Training engine not available"}), 503
    if trainer.is_training:
        return jsonify({"success": False, "message": "Training already in progress"})
    run_id = trainer.run_full_training_async(trigger="lora_merge")
    return jsonify({"success": True, "run_id": run_id,
                    "message": "LoRA merge triggered — running full fine-tune"})


@app.route("/api/ai-training/stream", methods=["GET"])
def api_ai_training_stream():
    """
    SSE endpoint: streams training progress events as they happen.
    Connect with EventSource('/api/ai-training/stream').
    """
    import queue as _queue

    q: _queue.Queue = _queue.Queue(maxsize=100)

    def _on_event(event: dict):
        try:
            q.put_nowait(event)
        except _queue.Full:
            pass

    trainer = _get_trainer()
    if trainer:
        trainer.register_progress_callback(_on_event)

    def _generate():
        import json as _json
        import time as _time
        # Send initial status immediately
        if trainer:
            yield f"data: {_json.dumps({'type': 'status', **trainer.get_status()})}\n\n"
        heartbeat_interval = 15
        last_heartbeat = _time.monotonic()
        while True:
            try:
                event = q.get(timeout=1.0)
                yield f"data: {_json.dumps(event)}\n\n"
                last_heartbeat = _time.monotonic()
            except _queue.Empty:
                if _time.monotonic() - last_heartbeat >= heartbeat_interval:
                    yield ": heartbeat\n\n"
                    last_heartbeat = _time.monotonic()

    return Response(stream_with_context(_generate()), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.route("/translate_helsinki", methods=["POST"])
def translate_helsinki():
    """Translate using Helsinki-NLP models"""
    try:
        text = request.form.get("text", "").strip()
        direction = request.form.get("direction", "chuukese_to_english")

        if not text:
            return jsonify({"error": "No text provided"})

        if not helsinki_translator:
            return jsonify({"error": "Helsinki translator not available"})

        if direction == "chuukese_to_english":
            translation = helsinki_translator.translate_chuukese_to_english(text)
        else:
            translation = helsinki_translator.translate_english_to_chuukese(text)

        return jsonify(
            {"original_text": text, "translation": translation, "direction": direction, "model": "Helsinki-NLP"}
        )

    except Exception as e:
        return jsonify({"error": f"Translation failed: {str(e)}"})


@app.route("/train_helsinki", methods=["POST"])
def train_helsinki():
    """Fine-tune Helsinki-NLP models with dictionary data"""
    try:
        direction = request.form.get("direction", "chuukese_to_english")
        epochs = int(request.form.get("epochs", 3))

        if not helsinki_translator:
            flash("Helsinki translator not available", "error")
            return redirect(url_for("translate"))

        if not helsinki_translator.training_data:
            flash("No training data loaded. Please ensure dictionary data is available.", "error")
            return redirect(url_for("translate"))

        flash(f"Starting Helsinki-NLP fine-tuning for {direction} direction...", "info")

        # Run training in background
        def train_model():
            try:
                success = helsinki_translator.fine_tune_model(
                    direction=direction, num_epochs=epochs, batch_size=4  # Smaller batch size for better memory usage
                )
                if success:
                    print(f"✅ Helsinki fine-tuning completed for {direction}")
                else:
                    print(f"❌ Helsinki fine-tuning failed for {direction}")
            except Exception as e:
                print(f"❌ Training error: {e}")

        threading.Thread(target=train_model, daemon=True).start()
        flash("Helsinki-NLP fine-tuning started in background. Check console for progress.", "success")

    except Exception as e:
        flash(f"Training error: {str(e)}", "error")

    return redirect(url_for("translate"))


@app.route("/evaluate_helsinki", methods=["POST"])
def evaluate_helsinki():
    """Evaluate Helsinki-NLP translation quality"""
    try:
        if not helsinki_translator:
            return jsonify({"error": "Helsinki translator not available"})

        if not helsinki_translator.training_data:
            return jsonify({"error": "No dictionary data available for evaluation"})

        # Use a sample for evaluation
        test_sample = helsinki_translator.training_data[:20]  # Small sample for quick eval
        results = helsinki_translator.evaluate_translation_quality(test_sample)

        return jsonify({"evaluation_results": results, "model": "Helsinki-NLP", "test_samples": len(test_sample)})

    except Exception as e:
        return jsonify({"error": f"Evaluation failed: {str(e)}"})


@app.route("/train_ollama", methods=["POST"])
def train_ollama():
    """Train the Ollama model with current dictionary data"""
    try:
        from src.translation.llm_trainer import ChuukeseLLMTrainer

        trainer = ChuukeseLLMTrainer()

        # Run training in background
        def train_model():
            try:
                success = trainer.train_full_pipeline()
                if success:
                    print("✅ Ollama training completed successfully!")
                else:
                    print("❌ Ollama training failed")
            except Exception as e:
                print(f"❌ Ollama training error: {e}")

        threading.Thread(target=train_model, daemon=True).start()
        flash("Ollama model training started in background. Check console for progress.", "success")

    except Exception as e:
        flash(f"Training error: {str(e)}", "error")

    return redirect(url_for("translate"))


@app.route("/model_status", methods=["GET"])
def model_status():
    """Check the status of available translation models"""
    try:
        import subprocess
        from src.translation.llm_trainer import ChuukeseLLMTrainer

        # Check Ollama status
        ollama_status = {}
        try:
            trainer = ChuukeseLLMTrainer()
            ollama_running = trainer.check_ollama_installation()

            if ollama_running:
                # Check if our custom model exists
                result = subprocess.run(["ollama", "list"], capture_output=True, text=True)
                chuukese_model_exists = "chuukese-translator" in result.stdout
                ollama_status = {
                    "available": True,
                    "custom_model": chuukese_model_exists,
                    "model_name": "chuukese-translator" if chuukese_model_exists else None,
                }
            else:
                ollama_status = {"available": False, "custom_model": False, "model_name": None}
        except Exception:
            ollama_status = {"available": False, "custom_model": False, "model_name": None}

        # Check Helsinki status
        helsinki_status = {
            "available": helsinki_translator is not None,
            "data_loaded": helsinki_translator.training_data if helsinki_translator else False,
        }

        return jsonify(
            {
                "ollama": ollama_status,
                "helsinki": helsinki_status,
                "database_entries": dict_db.get_statistics()["total_entries"] if dict_db.client else 0,
            }
        )

    except Exception as e:
        return jsonify({"error": f"Status check failed: {str(e)}"})


# Disabled - handled by React Router
# @app.route('/lookup', methods=['GET', 'POST'])
# def lookup():
#     """Redirect to React app"""
#     return redirect('/')


@app.route("/api/lookup/<word>")
def api_lookup(word):
    """API endpoint for word lookup"""
    lang = request.args.get("lang", "chk")
    results = jworg_lookup.search_word(word, lang)
    return jsonify({"word": word, "language": lang, "results": results})


@app.route("/api/lookup/jworg", methods=["POST"])
def api_lookup_jworg():
    """API endpoint for JW.org lookup (async)"""
    data = request.get_json()
    word = data.get("word")
    lang = data.get("lang", "chk")

    if not word:
        return jsonify({"error": "No word provided"}), 400

    try:
        results = jworg_lookup.search_word(word, lang)
        return jsonify({"success": True, "word": word, "language": lang, "results": results})
    except Exception as e:
        return jsonify({"success": False, "error": f"JW.org search failed: {str(e)}"}), 500


@app.route("/api/processing/logs/<session_id>")
def get_processing_logs(session_id):
    """Get processing logs for a session"""
    logs = processing_logger.get_logs(session_id)
    if logs:
        return jsonify(logs)
    else:
        return jsonify({"error": "Session not found"}), 404


@app.route("/api/processing/logs/<session_id>/recent")
def get_recent_logs(session_id):
    """Get recent log entries for real-time updates"""
    limit = request.args.get("limit", 20, type=int)
    logs = processing_logger.get_recent_logs(session_id, limit)
    return jsonify({"logs": logs})


@app.route("/database")
def database_viewer():
    """Serve React app for database viewer"""
    return send_from_directory("frontend/dist", "index.html")


@app.route("/api/database/pages")
def api_database_pages():
    """API endpoint for processed pages"""
    try:
        pages = dict_db.get_all_pages()
        return jsonify({"pages": pages})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/database/entry/<entry_id>")
def api_get_entry(entry_id):
    """Get detailed information for a specific entry"""
    try:
        entry = dict_db.get_entry_by_id(entry_id)
        if entry:
            return jsonify(entry)
        else:
            return jsonify({"error": "Entry not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# API Routes for React frontend
@app.route("/api/publications", methods=["GET"])
def api_get_publications():
    """API: Get all publications"""
    try:
        publications = pub_manager.list_publications()
        return jsonify(publications)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/publications", methods=["POST"])
def api_create_publication():
    """API: Create new publication"""
    try:
        data = request.get_json()
        title = data.get("title")
        description = data.get("description", "")

        if not title:
            return jsonify({"error": "Title is required"}), 400

        pub_id = pub_manager.create_publication(title, description)
        return jsonify({"id": pub_id, "message": "Publication created"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/publications/<pub_id>", methods=["GET"])
def api_get_publication(pub_id):
    """API: Get publication details with enhanced page data"""
    try:
        # Validate publication ID format
        if not re.match(r"^\d{14}_[a-f0-9]{8}$", pub_id):
            return jsonify({"error": "Invalid publication ID"}), 400

        publication = pub_manager.get_publication(pub_id)
        if not publication:
            return jsonify({"error": "Publication not found"}), 404

        # Enhance pages with missing fields for backward compatibility
        for page in publication.get("pages", []):
            if "id" not in page:
                page["id"] = f"{pub_id}_{page['filename']}"
            if "processed" not in page:
                # Check if page has OCR text - if so, mark as processed
                page["processed"] = bool(page.get("ocr_text") or page.get("ocr_results", {}).get("text"))
            if "ocr_text" not in page and page.get("ocr_results"):
                page["ocr_text"] = page["ocr_results"].get("text", "")
            if "entries_count" not in page:
                page["entries_count"] = 0

        return jsonify(publication)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/lookup", methods=["GET"])
def api_lookup_get():
    """API: Search dictionary (GET version for simple queries)"""
    try:
        word = request.args.get("word", "")
        request.args.get("lang", "chk")
        limit = int(request.args.get("limit", 50))  # Increased default limit
        exact_match = request.args.get("exact", "false").lower() == "true"

        if not word:
            return jsonify({"results": []})

        # Now uses denormalized data - only 1 query, includes related words!
        results = dict_db.search_word(word, limit=limit, include_related=True, exact_match=exact_match)

        # Sort results alphabetically by chuukese_word
        results.sort(key=lambda x: (x.get("chuukese_word", "") or "").lower())

        return jsonify({"word": word, "results": results})
    except Exception as e:
        import traceback

        print(f"❌ Error in lookup: {str(e)}")
        print(traceback.format_exc())
        return jsonify({"error": str(e)}), 500


@app.route("/api/lookup/jworg", methods=["POST"])
def api_lookup_jworg_post():
    """API: Search JW.org (POST version)"""
    try:
        data = request.get_json()
        word = data.get("word")
        lang = data.get("lang", "chk")

        if not word:
            return jsonify({"error": "Word is required"}), 400

        results = jworg_lookup.search_word(word, lang)
        return jsonify({"word": word, "results": results})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/grammar/types", methods=["GET"])
def api_grammar_types():
    """API: Get grammar types with counts and examples"""
    try:
        # Aggregate grammar types from dictionary collection
        pipeline = [
            {"$match": {"grammar": {"$exists": True, "$ne": "", "$ne": None}}},
            {
                "$group": {
                    "_id": "$grammar",
                    "count": {"$sum": 1},
                    "examples": {
                        "$push": {"chuukese_word": "$chuukese_word", "english_translation": "$english_translation"}
                    },
                }
            },
            {
                "$project": {
                    "grammar": "$_id",
                    "count": 1,
                    "examples": {"$slice": ["$examples", 12]},  # Limit examples to 12
                }
            },
            {"$sort": {"count": -1}},
        ]

        results = list(dict_db.dictionary_collection.aggregate(pipeline))

        grammar_types = []
        for r in results:
            grammar_types.append(
                {"grammar": r.get("grammar", "Unknown"), "count": r.get("count", 0), "examples": r.get("examples", [])}
            )

        return jsonify({"grammar_types": grammar_types})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/database/stats", methods=["GET"])
def api_database_stats():
    """API: Get database statistics (cached 60s to avoid Cosmos rate limits)"""
    try:
        cache = app.config.setdefault("_stats_cache", {})
        cached = cache.get("data")
        cached_at = cache.get("at", 0)
        if cached and (datetime.now(timezone.utc).timestamp() - cached_at) < 60:
            return jsonify(cached)
        stats = dict_db.get_stats()
        # Only cache if the result is valid (not an empty fallback)
        if stats.get("total_entries", 0) > 0 or stats.get("grammar_breakdown"):
            cache["data"] = stats
            cache["at"] = datetime.now(timezone.utc).timestamp()
        return jsonify(stats)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def extract_ot_verse(book_name, chapter, verse):
    """
    Extract a verse from Old Testament EPUB

    Args:
        book_name: Book name like "Genesis" or abbreviation like "GEN"
        chapter: Chapter number (int)
        verse: Verse number (int)

    Returns:
        str: Verse text in Chuukese, or None if not found
    """
    try:
        epub_path = "data/bible/old_testament_chuukese.epub"
        if not os.path.exists(epub_path):
            print(f"EPUB file not found: {epub_path}")
            return None

        book = epub.read_epub(epub_path)

        # Book code mapping (2-letter codes used in EPUB IDs)
        book_codes = {
            "Genesis": "GN",
            "Exodus": "EX",
            "Leviticus": "LV",
            "Numbers": "NU",
            "Deuteronomy": "DT",
            "Joshua": "JS",
            "Judges": "JG",
            "Ruth": "RT",
            "1 Samuel": "1S",
            "2 Samuel": "2S",
            "1 Kings": "1K",
            "2 Kings": "2K",
            "1 Chronicles": "1C",
            "2 Chronicles": "2C",
            "Ezra": "ER",
            "Nehemiah": "NE",
            "Esther": "ET",
            "Job": "JB",
            "Psalms": "PS",
            "Proverbs": "PR",
            "Ecclesiastes": "EC",
            "Song of Solomon": "SS",
            "Isaiah": "IS",
            "Jeremiah": "JR",
            "Lamentations": "LM",
            "Ezekiel": "EK",
            "Daniel": "DN",
            "Hosea": "HS",
            "Joel": "JL",
            "Amos": "AM",
            "Obadiah": "OB",
            "Jonah": "JN",
            "Micah": "MC",
            "Nahum": "NM",
            "Habakkuk": "HK",
            "Zephaniah": "ZP",
            "Haggai": "HG",
            "Zechariah": "ZC",
            "Malachi": "ML",
        }

        # Get 2-letter book code
        book_abbrev = book_codes.get(book_name, book_name)

        # Map common abbreviations
        abbrev_map = {
            "GEN": "GN",
            "GENESIS": "GN",
            "EXO": "EX",
            "EXODUS": "EX",
            "EXOD": "EX",
            "LEV": "LV",
            "LEVITICUS": "LV",
            "NUM": "NU",
            "NUMBERS": "NU",
            "DEU": "DT",
            "DEUT": "DT",
            "DEUTERONOMY": "DT",
            "JOS": "JS",
            "JOSHUA": "JS",
            "JDG": "JG",
            "JUDG": "JG",
            "JUDGES": "JG",
            "RUT": "RT",
            "RUTH": "RT",
            "1SA": "1S",
            "1 SAMUEL": "1S",
            "2SA": "2S",
            "2 SAMUEL": "2S",
            "1KI": "1K",
            "1 KINGS": "1K",
            "2KI": "2K",
            "2 KINGS": "2K",
            "EZR": "ER",
            "EZRA": "ER",
            "NEH": "NE",
            "NEHEMIAH": "NE",
            "EST": "ET",
            "ESTHER": "ET",
            "JOB": "JB",
            "PSA": "PS",
            "PSALM": "PS",
            "PSALMS": "PS",
            "PRO": "PR",
            "PROV": "PR",
            "PROVERBS": "PR",
            "ECC": "EC",
            "ECCL": "EC",
            "ECCLESIASTES": "EC",
            "SNG": "SS",
            "SONG": "SS",
            "SONG OF SOLOMON": "SS",
            "ISA": "IS",
            "ISAIAH": "IS",
            "JER": "JR",
            "JEREMIAH": "JR",
            "LAM": "LM",
            "LAMENTATIONS": "LM",
            "EZK": "EK",
            "EZEK": "EK",
            "EZEKIEL": "EK",
            "DAN": "DN",
            "DANIEL": "DN",
            "HOS": "HS",
            "HOSEA": "HS",
            "JOL": "JL",
            "JOEL": "JL",
            "AMO": "AM",
            "AMOS": "AM",
            "OBA": "OB",
            "OBAD": "OB",
            "OBADIAH": "OB",
            "JON": "JN",
            "JONAH": "JN",
            "MIC": "MC",
            "MICAH": "MC",
            "NAM": "NM",
            "NAH": "NM",
            "NAHUM": "NM",
            "HAB": "HK",
            "HABAKKUK": "HK",
            "ZEP": "ZP",
            "ZEPH": "ZP",
            "ZEPHANIAH": "ZP",
            "HAG": "HG",
            "HAGGAI": "HG",
            "ZEC": "ZC",
            "ZECH": "ZC",
            "ZECHARIAH": "ZC",
            "MAL": "ML",
            "MALACHI": "ML",
        }

        if book_name.upper() in abbrev_map:
            book_abbrev = abbrev_map[book_name.upper()]

        # Filenames use 3-letter codes (GEN.xhtml, EXO.xhtml)
        file_mapping = {
            "GN": "GEN",
            "EX": "EXO",
            "LV": "LEV",
            "NU": "NUM",
            "DT": "DEU",
            "JS": "JOS",
            "JG": "JDG",
            "RT": "RUT",
            "1S": "1SA",
            "2S": "2SA",
            "1K": "1KI",
            "2K": "2KI",
            "1C": "1CH",
            "2C": "2CH",
            "ER": "EZR",
            "NE": "NEH",
            "ET": "EST",
            "JB": "JOB",
            "PS": "PSA",
            "PR": "PRO",
            "EC": "ECC",
            "SS": "SNG",
            "IS": "ISA",
            "JR": "JER",
            "LM": "LAM",
            "EK": "EZK",
            "DN": "DAN",
            "HS": "HOS",
            "JL": "JOL",
            "AM": "AMO",
            "OB": "OBA",
            "JN": "JON",
            "MC": "MIC",
            "NM": "NAM",
            "HK": "HAB",
            "ZP": "ZEP",
            "HG": "HAG",
            "ZC": "ZEC",
            "ML": "MAL",
        }
        filename = f"{file_mapping.get(book_abbrev, book_abbrev.upper())}.xhtml"

        # Find the book file
        for item in book.get_items():
            if item.get_name() == filename:
                content = item.get_content()
                soup = BeautifulSoup(content, "html.parser")

                # Find verse by ID (e.g., GN1_1 for Genesis 1:1)
                verse_id = f"{book_abbrev}{chapter}_{verse}"
                verse_elem = soup.find(id=verse_id)

                if not verse_elem:
                    return None

                # The verse element is a span with the verse number
                # The verse text comes after it until the next verse marker
                verse_text_parts = []
                current = verse_elem.next_sibling

                # Get all text until we hit another verse marker (span with id ending in underscore+number)
                while current:
                    if hasattr(current, "name") and current.name == "span" and current.get("id"):
                        # Check if this is another verse marker (has underscore+number pattern)
                        if re.match(r"^[A-Z0-9]+_\d+$", current.get("id", "")):
                            break

                    if hasattr(current, "get_text"):
                        verse_text_parts.append(current.get_text())
                    elif isinstance(current, str):
                        verse_text_parts.append(current)

                    current = current.next_sibling if hasattr(current, "next_sibling") else None

                verse_text = "".join(verse_text_parts).strip()

                # Clean up cross-references and extra whitespace
                verse_text = re.sub(r"✡.*?(?=\n|$)", "", verse_text, flags=re.MULTILINE)
                verse_text = re.sub(r"\s+", " ", verse_text)  # Normalize whitespace
                verse_text = verse_text.strip()

                return verse_text

        return None

    except Exception as e:
        print(f"Error extracting OT verse: {e}")
        import traceback

        traceback.print_exc()
        return None


def fetch_scripture_from_jworg(scripture_ref):
    """
    Fetch scripture text from JW.org in both Chuukese and English
    For Old Testament (Genesis-Malachi), uses local EPUB for Chuukese text

    Args:
        scripture_ref: Scripture reference like "Genesis 1:1"

    Returns:
        dict: {'chuukese': str, 'english': str, 'error': str or None}
    """
    try:
        # Parse scripture reference (e.g., "Genesis 1:1")
        # Map common book names to JW.org codes
        book_map = {
            "genesis": "1",
            "exodus": "2",
            "leviticus": "3",
            "numbers": "4",
            "deuteronomy": "5",
            "joshua": "6",
            "judges": "7",
            "ruth": "8",
            "1 samuel": "9",
            "2 samuel": "10",
            "1 kings": "11",
            "2 kings": "12",
            "1 chronicles": "13",
            "2 chronicles": "14",
            "ezra": "15",
            "nehemiah": "16",
            "esther": "17",
            "job": "18",
            "psalm": "19",
            "psalms": "19",
            "proverbs": "20",
            "ecclesiastes": "21",
            "song of solomon": "22",
            "isaiah": "23",
            "jeremiah": "24",
            "lamentations": "25",
            "ezekiel": "26",
            "daniel": "27",
            "hosea": "28",
            "joel": "29",
            "amos": "30",
            "obadiah": "31",
            "jonah": "32",
            "micah": "33",
            "nahum": "34",
            "habakkuk": "35",
            "zephaniah": "36",
            "haggai": "37",
            "zechariah": "38",
            "malachi": "39",
            "matthew": "40",
            "mark": "41",
            "luke": "42",
            "john": "43",
            "acts": "44",
            "romans": "45",
            "1 corinthians": "46",
            "2 corinthians": "47",
            "galatians": "48",
            "ephesians": "49",
            "philippians": "50",
            "colossians": "51",
            "1 thessalonians": "52",
            "2 thessalonians": "53",
            "1 timothy": "54",
            "2 timothy": "55",
            "titus": "56",
            "philemon": "57",
            "hebrews": "58",
            "james": "59",
            "1 peter": "60",
            "2 peter": "61",
            "1 john": "62",
            "2 john": "63",
            "3 john": "64",
            "jude": "65",
            "revelation": "66",
        }

        # Old Testament books (1-39)
        old_testament_books = {str(i) for i in range(1, 40)}

        # Parse the reference using regex to handle multi-word book names (e.g. "Song of Solomon 1:1")
        m = re.match(r'^(.+?)\s+(\d+):(\d+)$', scripture_ref.strip())
        if not m:
            return {"chuukese": "", "english": "", "error": "Invalid scripture format (use 'Book Chapter:Verse')"}

        book_name_raw = m.group(1).strip()   # e.g. "Song of Solomon", "1 Samuel", "Genesis"
        chapter = int(m.group(2))
        verse = int(m.group(3))

        book_name = book_name_raw.lower()        # for book_map lookup
        book_name_for_epub = book_name_raw       # for EPUB lookup (preserve original casing)

        book_num = book_map.get(book_name)
        if not book_num:
            return {"chuukese": "", "english": "", "error": f'Book "{book_name_raw}" not found'}

        chuukese_text = ""
        english_text = ""

        # For Old Testament, use Chuukese OT EPUB
        if book_num in old_testament_books:
            chuukese_text = extract_ot_verse(book_name_for_epub, chapter, verse)
            if not chuukese_text:
                chuukese_text = ""
        else:
            # New Testament - use Chuukese NT EPUB
            chk_parser = get_nwt_chuukese_parser()
            if chk_parser:
                chuukese_text = chk_parser.get_verse(book_num, chapter, verse)
            if not chuukese_text:
                chuukese_text = ""

        # Fetch English from NWT English EPUB (full Bible)
        eng_parser = get_nwt_english_parser()
        if eng_parser:
            english_text = eng_parser.get_verse(book_num, chapter, verse)
        if not english_text:
            english_text = ""

        return {
            "chuukese": chuukese_text,
            "english": english_text,
            "error": None if (chuukese_text or english_text) else "Scripture not found",
        }

    except Exception as e:
        return {"chuukese": "", "english": "", "error": str(e)}


@app.route("/api/database/entries", methods=["GET"])
def api_database_entries():
    """API: Get paginated database entries (with rate limit handling)"""
    try:
        page = int(request.args.get("page", 1))
        limit = int(request.args.get("limit", 20))
        search = request.args.get("search", "")
        sort_by = request.args.get("sort_by", "")
        sort_order = request.args.get("sort_order", "asc")
        filter_type = request.args.get("filter_type", "")
        filter_type = request.args.get("type", filter_type)  # Support both parameter names
        filter_grammar = request.args.get("filter_grammar", "")
        filter_grammar_modifier = request.args.get("filter_grammar_modifier", "")
        filter_scripture = request.args.get("filter_scripture", "")
        source_type = request.args.get("source_type", "")  # Add source_type filter
        exact_match = request.args.get("exact", "false").lower() == "true"  # Exact match toggle

        try:
            # Build query with search and filters
            conditions = []

            if search:
                if exact_match:
                    # Exact match - use case-insensitive equality
                    conditions.append(
                        {
                            "$or": [
                                {"chuukese_word": {"$regex": f"^{search}$", "$options": "i"}},
                                {"english_translation": {"$regex": f"^{search}$", "$options": "i"}},
                            ]
                        }
                    )
                else:
                    # Partial match - use contains regex
                    conditions.append(
                        {
                            "$or": [
                                {"chuukese_word": {"$regex": search, "$options": "i"}},
                                {"english_translation": {"$regex": search, "$options": "i"}},
                                {"definition": {"$regex": search, "$options": "i"}},
                                {"examples": {"$regex": search, "$options": "i"}},
                            ]
                        }
                    )

            # Add filter conditions
            if filter_type:
                conditions.append({"type": filter_type})
            if filter_grammar:
                conditions.append({"grammar": filter_grammar})
            if filter_grammar_modifier:
                conditions.append({"grammar_modifier": filter_grammar_modifier})
            if filter_scripture:
                # For scripture, use regex to allow partial match
                conditions.append({"scripture": {"$regex": filter_scripture, "$options": "i"}})
            if source_type:
                conditions.append({"source_type": source_type})

            query = {"$and": conditions} if conditions else {}

            # Map frontend column names to database field names
            field_map = {
                "chuukese": "chuukese_word",
                "english": "english_translation",
                "type": "type",
                "grammar": "grammar",
                "scripture": "scripture",
                "search_direction": "search_direction",
                "definition": "definition",
            }

            # Determine which collection(s) to query based on type filter
            # Sentences and phrases are in phrases_collection, words in dictionary_collection
            all_entries = []

            if filter_type in ["sentence", "phrase", "question"]:
                # Query phrases_collection for sentences/phrases
                # Adjust search fields for phrases_collection
                phrase_query = query.copy()
                if search and "$and" in phrase_query:
                    # Update search fields for phrases_collection
                    phrase_query["$and"] = [
                        (
                            cond
                            if "$or" not in cond
                            else {
                                "$or": [
                                    {"chuukese_sentence": {"$regex": search, "$options": "i"}},
                                    {"chuukese_phrase": {"$regex": search, "$options": "i"}},
                                    {"english_translation": {"$regex": search, "$options": "i"}},
                                    {"definition": {"$regex": search, "$options": "i"}},
                                ]
                            }
                        )
                        for cond in phrase_query["$and"]
                    ]
                all_entries = list(dict_db.phrases_collection.find(phrase_query))
            elif filter_type == "word":
                # Query dictionary_collection for words
                all_entries = list(dict_db.dictionary_collection.find(query))
            else:
                # No filter - query both collections
                # First get from phrases_collection
                phrase_query = query.copy()
                if search and ("$and" in phrase_query or len(phrase_query) == 0):
                    conditions_copy = conditions.copy() if conditions else []
                    # Add phrase-specific search if there's a search term
                    if search:
                        phrase_search = {
                            "$or": [
                                {"chuukese_sentence": {"$regex": search, "$options": "i"}},
                                {"chuukese_phrase": {"$regex": search, "$options": "i"}},
                                {"english_translation": {"$regex": search, "$options": "i"}},
                                {"definition": {"$regex": search, "$options": "i"}},
                            ]
                        }
                        phrase_conditions = [c for c in conditions_copy if "$or" not in c]
                        phrase_conditions.append(phrase_search)
                        phrase_query = {"$and": phrase_conditions} if phrase_conditions else {}

                phrases = list(dict_db.phrases_collection.find(phrase_query))
                words = list(dict_db.dictionary_collection.find(query))
                all_entries = phrases + words

        except Exception as db_error:
            print(f"Database query error (likely rate limit): {db_error}")
            # Return empty results with error message instead of crashing
            return (
                jsonify(
                    {
                        "entries": [],
                        "total": 0,
                        "page": page,
                        "limit": limit,
                        "error": "Rate limit exceeded - please try again in a moment",
                    }
                ),
                200,
            )  # Return 200 to avoid UI errors

        total = len(all_entries)

        # Sort in Python to handle null/missing values properly
        def _type_rank(entry):
            """Words=0, Phrases=1, Sentences/Questions=2 for grouped default sort"""
            t = (entry.get("type") or "").lower()
            if t == "word":
                return 0
            if t in ("phrase",):
                return 1
            if t in ("sentence", "question"):
                return 2
            return 3

        def _chuukese_alpha(entry):
            v = (
                entry.get("chuukese_word")
                or entry.get("chuukese_sentence")
                or entry.get("chuukese_phrase")
                or entry.get("chuukese")
                or ""
            )
            return str(v).lower()

        if sort_by and sort_by in field_map:
            sort_field = field_map[sort_by]
            reverse = sort_order == "desc"

            if sort_by == "chuukese":
                # Default: group by type (word → phrase → sentence) then alpha within group
                all_entries.sort(key=lambda e: (_type_rank(e), _chuukese_alpha(e)), reverse=reverse)
            else:
                # Sort with nulls/empty at the end, case-insensitive for strings
                def sort_key(entry):
                    value = entry.get(sort_field)
                    if sort_field == "chuukese_word" and not value:
                        value = entry.get("chuukese_sentence") or entry.get("chuukese_phrase") or entry.get("chuukese")
                    if value is None or value == "":
                        return (1, "")
                    return (0, str(value).lower())

                all_entries.sort(key=sort_key, reverse=reverse)
        else:
            # No sort_by specified — apply default grouped sort
            all_entries.sort(key=lambda e: (_type_rank(e), _chuukese_alpha(e)))

        # Apply pagination after sorting
        skip = (page - 1) * limit
        entries = all_entries[skip : skip + limit]

        # Normalize field names for frontend display
        normalized_entries = []
        for entry in entries:
            normalized = {
                "_id": str(entry["_id"]) if "_id" in entry else "",
                "chuukese_word": entry.get("chuukese_word")
                or entry.get("chuukese_sentence")
                or entry.get("chuukese_phrase")
                or entry.get("chuukese")
                or "",
                "english_translation": entry.get("english_translation") or entry.get("english") or "",
                "type": entry.get("type", ""),
                "grammar": entry.get("grammar", ""),
                "grammar_modifier": entry.get("grammar_modifier", ""),
                "scripture": entry.get("scripture", ""),
                "search_direction": entry.get("search_direction", ""),
                "definition": entry.get("definition", ""),
                "source_type": entry.get("source_type", ""),
                "confidence": entry.get("confidence", ""),
                "confidence_score": entry.get("confidence_score", ""),
                "date_added": entry.get("date_added") or entry.get("created_date"),
                "examples": entry.get("examples", []),
                "notes": entry.get("notes", ""),
                "references": entry.get("references", ""),
                "user_confirmed": entry.get("user_confirmed", False),
                "is_base_word": entry.get("is_base_word", False),
                "edited_by": entry.get("edited_by", ""),
            }
            normalized_entries.append(normalized)

        return jsonify({"entries": normalized_entries, "total": total, "page": page, "limit": limit})
    except Exception as e:
        import traceback

        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/database/distinct", methods=["GET"])
def api_database_distinct():
    """API: Get distinct values for filter dropdowns (with caching to reduce Cosmos DB load)"""
    try:
        field = request.args.get("field", "")

        # Map frontend field names to database field names
        field_map = {
            "type": "type",
            "grammar": "grammar",
            "grammar_modifier": "grammar_modifier",
            "scripture": "scripture",
        }

        if field not in field_map:
            return jsonify({"error": "Invalid field"}), 400

        db_field = field_map[field]

        # Try to get from cache first to avoid expensive Cosmos DB queries
        cached_values = get_cached_distinct_values(field, db_field)
        if cached_values is not None:
            return jsonify({"field": field, "values": cached_values, "cached": True})

        # Cache miss - query database
        try:
            # Get distinct non-null, non-empty values
            distinct_values = dict_db.dictionary_collection.distinct(db_field)

            # Filter out None and empty strings, sort alphabetically
            values = sorted([v for v in distinct_values if v and str(v).strip()])

            # Cache the results
            set_cached_distinct_values(field, values)

            return jsonify({"field": field, "values": values, "cached": False})
        except Exception as db_error:
            # If database query fails (e.g., rate limit), return empty list
            # This prevents the UI from breaking
            print(f"Database query failed for distinct {field}: {db_error}")
            return jsonify({"field": field, "values": [], "error": "Rate limit - using cached data"})
    except Exception as e:
        import traceback

        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


def _load_bible_books():
    """Load Bible book data from config/bible_books.json."""
    _path = Path(__file__).parent / "config" / "bible_books.json"
    with open(_path, encoding="utf-8") as _f:
        return json.load(_f)["books"]


# Bible book information with chapter/verse counts (loaded from config/bible_books.json)
BIBLE_BOOKS = _load_bible_books()


@app.route("/api/database/bible-coverage", methods=["GET"])
def api_bible_coverage():
    """API: Get Bible book coverage - which verses are loaded vs missing (cached to reduce RU consumption)"""
    try:
        book = request.args.get("book", "")

        if not book:
            # Return list of books with their loaded verse counts
            # Try cache first
            cache_key = "bible_coverage_summary"
            if cache_key in distinct_values_cache:
                cached_data = distinct_values_cache[cache_key]
                if (datetime.now(timezone.utc) - cached_data["timestamp"]).total_seconds() < CACHE_EXPIRY_SECONDS:
                    return jsonify({"books": cached_data["values"], "cached": True})

            try:
                # Get all scripture entries at once
                scripture_entries = list(
                    dict_db.dictionary_collection.find(
                        {"scripture": {"$exists": True, "$ne": ""}}, {"scripture": 1, "_id": 0}
                    )
                )

                # Count entries per book
                book_counts = {}
                for entry in scripture_entries:
                    scripture = entry.get("scripture", "")
                    # Extract book name from scripture (e.g., "Genesis 1:1" -> "Genesis")
                    if scripture:
                        parts = scripture.split()
                        if len(parts) >= 2:
                            # Handle books with numbers like "1 Samuel"
                            if parts[0].isdigit():
                                book_name = f"{parts[0]} {parts[1]}"
                            else:
                                book_name = parts[0]
                            book_counts[book_name] = book_counts.get(book_name, 0) + 1

                # Build coverage list
                books_coverage = []
                for book_name, info in BIBLE_BOOKS.items():
                    count = book_counts.get(book_name, 0)
                    total_verses = sum(info["verses"])
                    books_coverage.append(
                        {
                            "book": book_name,
                            "num": info["num"],
                            "chapters": info["chapters"],
                            "total_verses": total_verses,
                            "loaded_verses": count,
                            "coverage_percent": round((count / total_verses) * 100, 1) if total_verses > 0 else 0,
                        }
                    )

                # Cache the results
                distinct_values_cache[cache_key] = {"values": books_coverage, "timestamp": datetime.now(timezone.utc)}

                return jsonify({"books": books_coverage, "cached": False})
            except Exception as db_error:
                print(f"Database query failed for bible coverage: {db_error}")
                # Return empty list on rate limit
                return jsonify({"books": [], "error": "Rate limit - please try again later"})

        # Get details for a specific book (not cached due to complexity)
        if book not in BIBLE_BOOKS:
            return jsonify({"error": "Invalid book name"}), 400

        book_info = BIBLE_BOOKS[book]

        try:
            # Get all scripture entries for this book
            entries = list(
                dict_db.dictionary_collection.find(
                    {"scripture": {"$regex": f"^{book}", "$options": "i"}}, {"scripture": 1, "_id": 0}
                )
            )

            # Parse loaded verses
            loaded_verses = set()
            for entry in entries:
                scripture = entry.get("scripture", "")
                # Parse "Book Chapter:Verse" format
                match = re.match(rf"^{re.escape(book)}\s+(\d+):(\d+)", scripture, re.IGNORECASE)
                if match:
                    chapter = int(match.group(1))
                    verse = int(match.group(2))
                    loaded_verses.add((chapter, verse))

            # Build chapter-by-chapter coverage
            chapters_coverage = []
            for chapter_idx, verse_count in enumerate(book_info["verses"]):
                chapter_num = chapter_idx + 1
                loaded_in_chapter = []
                missing_in_chapter = []

                for verse in range(1, verse_count + 1):
                    if (chapter_num, verse) in loaded_verses:
                        loaded_in_chapter.append(verse)
                    else:
                        missing_in_chapter.append(verse)

                chapters_coverage.append(
                    {
                        "chapter": chapter_num,
                        "total_verses": verse_count,
                        "loaded": loaded_in_chapter,
                        "missing": missing_in_chapter,
                        "loaded_count": len(loaded_in_chapter),
                        "missing_count": len(missing_in_chapter),
                    }
                )

            total_verses = sum(book_info["verses"])
            total_loaded = len(loaded_verses)

            return jsonify(
                {
                    "book": book,
                    "num": book_info["num"],
                    "chapters": chapters_coverage,
                    "total_verses": total_verses,
                    "total_loaded": total_loaded,
                    "total_missing": total_verses - total_loaded,
                    "coverage_percent": round((total_loaded / total_verses) * 100, 1) if total_verses > 0 else 0,
                }
            )
        except Exception as db_error:
            print(f"Database query failed for book detail: {db_error}")
            return jsonify({"error": "Rate limit - please try again later"}), 500
    except Exception as e:
        import traceback

        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/database/entries", methods=["POST"])
def api_create_database_entry():
    """API: Create a new dictionary entry (upserts based on chuukese_word)"""
    try:
        data = request.get_json()

        # Fetch scripture if provided
        scripture_ref = data.get("scripture", "")
        chuukese_word = data.get("chuukese_word", "")
        english_translation = data.get("english_translation", "")

        if scripture_ref:
            scripture_result = fetch_scripture_from_jworg(scripture_ref)
            if not scripture_result["error"]:
                # Auto-populate fields with scripture text
                chuukese_word = scripture_result["chuukese"]
                english_translation = scripture_result["english"]

        # Prepare the update data
        # Normalize grammar type
        raw_grammar = data.get("grammar", "")
        normalized_grammar = dict_db._normalize_grammar(raw_grammar) if raw_grammar else None

        # Handle examples - ensure it's an array
        examples = data.get("examples", [])
        if isinstance(examples, str):
            # If it's a string, split by newlines
            examples = [ex.strip() for ex in examples.split("\n") if ex.strip()]
        elif not isinstance(examples, list):
            examples = []

        update_data = {
            "chuukese_word": chuukese_word,
            "english_translation": english_translation,
            "definition": data.get("definition", ""),
            "word_type": normalized_grammar or data.get("word_type", ""),
            "type": "scripture" if scripture_ref else data.get("type", ""),
            "grammar": normalized_grammar,
            "direction": data.get("direction", ""),
            "examples": examples,
            "notes": data.get("notes", ""),
            "scripture": scripture_ref,
            "references": data.get("references", ""),
            "user_confirmed": bool(data.get("user_confirmed", False)),
            "is_base_word": bool(data.get("is_base_word", False)),
            "updated_date": datetime.now(),
            "edited_by": _get_user_initials(),
        }

        # Add confidence fields if provided
        if "confidence_score" in data and data["confidence_score"] is not None:
            update_data["confidence_score"] = data["confidence_score"]
            # Calculate confidence level based on score
            score = data["confidence_score"]
            if score >= 90:
                update_data["confidence_level"] = "verified"
            elif score >= 70:
                update_data["confidence_level"] = "high"
            elif score >= 40:
                update_data["confidence_level"] = "medium"
            else:
                update_data["confidence_level"] = "low"

        # Use upsert: update if exists, insert if not
        result = dict_db.dictionary_collection.update_one(
            {"chuukese_word": chuukese_word},
            {"$set": update_data, "$setOnInsert": {"created_date": datetime.now()}},
            upsert=True,
        )

        # Get the entry to return
        entry = dict_db.dictionary_collection.find_one({"chuukese_word": chuukese_word})
        if entry:
            entry["_id"] = str(entry["_id"])

        message = "Entry updated successfully" if result.matched_count > 0 else "Entry created successfully"
        return jsonify({"message": message, "entry": entry, "upserted": result.matched_count == 0}), (
            200 if result.matched_count > 0 else 201
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/database/entries/<entry_id>", methods=["PUT"])
def api_update_database_entry(entry_id):
    """API: Update a dictionary entry"""
    try:
        from bson import ObjectId
        from bson.errors import InvalidId

        data = request.get_json()

        # Fetch scripture if provided
        scripture_ref = data.get("scripture", "")
        chuukese_word = data.get("chuukese_word", "")
        english_translation = data.get("english_translation", "")

        if scripture_ref:
            scripture_result = fetch_scripture_from_jworg(scripture_ref)
            if not scripture_result["error"]:
                # Auto-populate fields with scripture text
                chuukese_word = scripture_result["chuukese"]
                english_translation = scripture_result["english"]

        # Normalize grammar type
        raw_grammar = data.get("grammar", "")
        normalized_grammar = dict_db._normalize_grammar(raw_grammar) if raw_grammar else None

        # Handle examples - ensure it's an array
        examples = data.get("examples", [])
        if isinstance(examples, str):
            # If it's a string, split by newlines
            examples = [ex.strip() for ex in examples.split("\n") if ex.strip()]
        elif not isinstance(examples, list):
            examples = []

        update_data = {
            "chuukese_word": chuukese_word,
            "english_translation": english_translation,
            "definition": data.get("definition", ""),
            "word_type": normalized_grammar or data.get("word_type", ""),
            "type": "scripture" if scripture_ref else data.get("type", ""),
            "grammar": normalized_grammar,
            "direction": data.get("direction", ""),
            "examples": examples,
            "notes": data.get("notes", ""),
            "scripture": scripture_ref,
            "references": data.get("references", ""),
            "user_confirmed": bool(data.get("user_confirmed", False)),
            "is_base_word": bool(data.get("is_base_word", False)),
            "updated_date": datetime.now(),
            "edited_by": _get_user_initials(),
        }

        # Add confidence fields if provided
        if "confidence_score" in data and data["confidence_score"] is not None:
            update_data["confidence_score"] = data["confidence_score"]
            # Calculate confidence level based on score
            score = data["confidence_score"]
            if score >= 90:
                update_data["confidence_level"] = "verified"
            elif score >= 70:
                update_data["confidence_level"] = "high"
            elif score >= 40:
                update_data["confidence_level"] = "medium"
            else:
                update_data["confidence_level"] = "low"

        # Try to find the entry in different collections with flexible ID handling
        result = None
        collections_to_try = [dict_db.dictionary_collection, dict_db.phrases_collection]

        for collection in collections_to_try:
            # Try string ID first (for custom IDs like sentence_*)
            result = collection.update_one({"_id": entry_id}, {"$set": update_data})
            if result.matched_count > 0:
                break

            # Try ObjectId if string didn't match
            try:
                obj_id = ObjectId(entry_id)
                result = collection.update_one({"_id": obj_id}, {"$set": update_data})
                if result.matched_count > 0:
                    break
            except InvalidId:
                continue

        if result and result.matched_count > 0:
            return jsonify({"message": "Entry updated successfully"}), 200
        else:
            return jsonify({"error": "Entry not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/database/entries/<entry_id>", methods=["DELETE"])
def api_delete_database_entry(entry_id):
    """API: Delete a dictionary entry"""
    try:
        from bson import ObjectId
        from bson.errors import InvalidId

        # Try to find and delete the entry in different collections with flexible ID handling
        result = None
        collections_to_try = [dict_db.dictionary_collection, dict_db.phrases_collection]

        for collection in collections_to_try:
            # Try string ID first (for custom IDs like sentence_*)
            result = collection.delete_one({"_id": entry_id})
            if result.deleted_count > 0:
                break

            # Try ObjectId if string didn't match
            try:
                obj_id = ObjectId(entry_id)
                result = collection.delete_one({"_id": obj_id})
                if result.deleted_count > 0:
                    break
            except InvalidId:
                continue

        if result and result.deleted_count > 0:
            return jsonify({"message": "Entry deleted successfully"}), 200
        else:
            return jsonify({"error": "Entry not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/database/export", methods=["GET"])
def api_database_export():
    """API: Export database entries to JSON format"""
    try:
        import json

        # Get filter parameters (same as entries endpoint)
        search = request.args.get("search", "")
        filter_type = request.args.get("filter_type", "")
        filter_grammar = request.args.get("filter_grammar", "")
        filter_scripture = request.args.get("filter_scripture", "")

        # Build query
        conditions = []
        if search:
            conditions.append(
                {
                    "$or": [
                        {"chuukese_word": {"$regex": search, "$options": "i"}},
                        {"english_translation": {"$regex": search, "$options": "i"}},
                        {"definition": {"$regex": search, "$options": "i"}},
                    ]
                }
            )
        if filter_type:
            conditions.append({"type": filter_type})
        if filter_grammar:
            conditions.append({"grammar": filter_grammar})
        if filter_scripture:
            conditions.append({"scripture": {"$regex": filter_scripture, "$options": "i"}})

        query = {"$and": conditions} if conditions else {}

        # Get entries from dictionary collection
        entries = list(dict_db.dictionary_collection.find(query))

        # Also get from phrases collection if no type filter or if type is sentence/phrase
        if not filter_type or filter_type in ["sentence", "phrase", "question"]:
            try:
                phrase_entries = list(dict_db.phrases_collection.find(query))
                entries.extend(phrase_entries)
            except Exception as phrase_err:
                print(f"Warning: Could not query phrases collection: {phrase_err}")

        # Normalize entries for export
        export_data = []
        for entry in entries:
            row = {
                "_id": str(entry.get("_id", "")),
                "chuukese_word": entry.get("chuukese_word")
                or entry.get("chuukese_sentence")
                or entry.get("chuukese_phrase")
                or "",
                "english_translation": entry.get("english_translation") or entry.get("english") or "",
                "definition": entry.get("definition", ""),
                "type": entry.get("type", ""),
                "grammar": entry.get("grammar", ""),
                "scripture": entry.get("scripture", ""),
                "examples": entry.get("examples", []) if isinstance(entry.get("examples"), list) else [],
                "notes": entry.get("notes", ""),
                "confidence_score": entry.get("confidence_score"),
                "user_confirmed": entry.get("user_confirmed"),
                "is_base_word": entry.get("is_base_word"),
            }
            export_data.append(row)

        # Return as downloadable JSON
        from flask import Response

        return Response(
            json.dumps(export_data, indent=2, ensure_ascii=False),
            mimetype="application/json",
            headers={
                "Content-Disposition": f'attachment; filename=chuuk_dictionary_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
            },
        )
    except Exception as e:
        import traceback

        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/database/import", methods=["POST"])
def api_database_import():
    """API: Import/upsert database entries from JSON"""
    try:
        import json
        from bson import ObjectId
        from bson.errors import InvalidId

        if "file" not in request.files:
            return jsonify({"error": "No file provided"}), 400

        file = request.files["file"]
        if not file.filename.endswith(".json"):
            return jsonify({"error": "File must be a JSON file"}), 400

        # Read JSON content
        content = file.read().decode("utf-8")
        entries_data = json.loads(content)

        if not isinstance(entries_data, list):
            return jsonify({"error": "JSON must be an array of entries"}), 400

        updated_count = 0
        inserted_count = 0
        error_count = 0
        errors = []
        changes = []  # Track detailed changes

        for row_num, row in enumerate(entries_data, start=1):
            try:
                entry_id = str(row.get("_id", "") or "").strip()
                chuukese_word = str(row.get("chuukese_word", "") or "").strip()
                english_translation = str(row.get("english_translation", "") or "").strip()

                if not chuukese_word and not english_translation:
                    errors.append(f"Row {row_num}: Missing both chuukese_word and english_translation")
                    error_count += 1
                    continue

                # Build the update document
                update_doc = {
                    "chuukese_word": chuukese_word,
                    "english_translation": english_translation,
                }

                # Add optional fields if present
                if row.get("definition"):
                    update_doc["definition"] = str(row["definition"]).strip()
                if row.get("type"):
                    update_doc["type"] = str(row["type"]).strip()
                if row.get("grammar"):
                    update_doc["grammar"] = str(row["grammar"]).strip()
                if row.get("scripture"):
                    update_doc["scripture"] = str(row["scripture"]).strip()
                if row.get("notes"):
                    update_doc["notes"] = str(row["notes"]).strip()
                if row.get("examples"):
                    # Examples should be an array in JSON
                    if isinstance(row["examples"], list):
                        update_doc["examples"] = row["examples"]
                    else:
                        update_doc["examples"] = [str(row["examples"])]
                if row.get("confidence_score") is not None:
                    try:
                        update_doc["confidence_score"] = float(row["confidence_score"])
                    except (ValueError, TypeError):
                        pass
                if row.get("user_confirmed") is not None:
                    update_doc["user_confirmed"] = bool(row["user_confirmed"])
                if row.get("is_base_word") is not None:
                    update_doc["is_base_word"] = bool(row["is_base_word"])

                update_doc["last_modified"] = datetime.now().isoformat()

                # Determine target collection based on type
                entry_type = row.get("type", "").strip().lower()
                if entry_type in ["sentence", "phrase", "question"]:
                    collection = dict_db.phrases_collection
                else:
                    collection = dict_db.dictionary_collection

                # Helper to track changes between old and new
                def get_field_changes(existing_doc, new_doc):
                    field_changes = []
                    track_fields = [
                        "chuukese_word",
                        "english_translation",
                        "definition",
                        "type",
                        "grammar",
                        "scripture",
                        "notes",
                        "examples",
                        "confidence_score",
                        "user_confirmed",
                        "is_base_word",
                    ]
                    for field in track_fields:
                        old_val = existing_doc.get(field)
                        new_val = new_doc.get(field)
                        # Normalize for comparison
                        if old_val is None:
                            old_val = (
                                ""
                                if field not in ["examples", "confidence_score", "user_confirmed", "is_base_word"]
                                else old_val
                            )
                        if isinstance(old_val, list) and isinstance(new_val, list):
                            if old_val != new_val:
                                field_changes.append({"field": field, "old": old_val, "new": new_val})
                        elif str(old_val) != str(new_val) if new_val is not None else False:
                            field_changes.append({"field": field, "old": old_val, "new": new_val})
                    return field_changes

                # Upsert based on _id if provided
                if entry_id:
                    # Try to find by ID
                    existing = None
                    try:
                        # Try ObjectId first
                        obj_id = ObjectId(entry_id)
                        existing = collection.find_one({"_id": obj_id})
                        if existing:
                            field_changes = get_field_changes(existing, update_doc)
                            if field_changes:
                                changes.append(
                                    {
                                        "_id": entry_id,
                                        "chuukese_word": chuukese_word,
                                        "action": "updated",
                                        "field_changes": field_changes,
                                    }
                                )
                            collection.update_one({"_id": obj_id}, {"$set": update_doc})
                            updated_count += 1
                            continue
                    except InvalidId:
                        pass

                    # Try string ID
                    existing = collection.find_one({"_id": entry_id})
                    if existing:
                        field_changes = get_field_changes(existing, update_doc)
                        if field_changes:
                            changes.append(
                                {
                                    "_id": entry_id,
                                    "chuukese_word": chuukese_word,
                                    "action": "updated",
                                    "field_changes": field_changes,
                                }
                            )
                        collection.update_one({"_id": entry_id}, {"$set": update_doc})
                        updated_count += 1
                        continue

                    # Also check the other collection
                    other_collection = (
                        dict_db.phrases_collection
                        if collection == dict_db.dictionary_collection
                        else dict_db.dictionary_collection
                    )
                    try:
                        obj_id = ObjectId(entry_id)
                        existing = other_collection.find_one({"_id": obj_id})
                        if existing:
                            field_changes = get_field_changes(existing, update_doc)
                            if field_changes:
                                changes.append(
                                    {
                                        "_id": entry_id,
                                        "chuukese_word": chuukese_word,
                                        "action": "updated",
                                        "field_changes": field_changes,
                                    }
                                )
                            other_collection.update_one({"_id": obj_id}, {"$set": update_doc})
                            updated_count += 1
                            continue
                    except InvalidId:
                        pass

                    existing = other_collection.find_one({"_id": entry_id})
                    if existing:
                        field_changes = get_field_changes(existing, update_doc)
                        if field_changes:
                            changes.append(
                                {
                                    "_id": entry_id,
                                    "chuukese_word": chuukese_word,
                                    "action": "updated",
                                    "field_changes": field_changes,
                                }
                            )
                        other_collection.update_one({"_id": entry_id}, {"$set": update_doc})
                        updated_count += 1
                        continue

                # No existing entry found or no ID provided - insert new
                update_doc["date_added"] = datetime.now().isoformat()
                collection.insert_one(update_doc)
                changes.append(
                    {
                        "_id": str(update_doc.get("_id", "")),
                        "chuukese_word": chuukese_word,
                        "action": "inserted",
                        "field_changes": [],
                    }
                )
                inserted_count += 1

            except Exception as row_error:
                errors.append(f"Row {row_num}: {str(row_error)}")
                error_count += 1

        return jsonify(
            {
                "success": True,
                "updated": updated_count,
                "inserted": inserted_count,
                "errors": error_count,
                "error_details": errors[:10],  # Limit error details to first 10
                "changes": changes,  # Detailed change report
            }
        )
    except Exception as e:
        import traceback

        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/scripture/preview", methods=["POST"])
def api_scripture_preview():
    """API: Preview scripture text without saving to database"""
    try:
        data = request.get_json()
        scripture_ref = data.get("scripture", "").strip()

        if not scripture_ref:
            return jsonify({"error": "Scripture reference is required"}), 400

        # Fetch scripture from EPUBs
        result = fetch_scripture_from_jworg(scripture_ref)

        return jsonify(
            {
                "scripture": scripture_ref,
                "chuukese": result.get("chuukese", ""),
                "english": result.get("english", ""),
                "error": result.get("error"),
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Serve React app
@app.route("/assets/<path:path>")
def serve_assets(path):
    """Serve React app static assets"""
    return send_from_directory("frontend/dist/assets", path)


# AI scraping protection - robots.txt
@app.route("/robots.txt")
def robots_txt():
    """Serve robots.txt to block AI crawlers and scrapers"""
    robots_content = """# Block AI training crawlers and scrapers
User-agent: GPTBot
Disallow: /

User-agent: ChatGPT-User
Disallow: /

User-agent: CCBot
Disallow: /

User-agent: Google-Extended
Disallow: /

User-agent: anthropic-ai
Disallow: /

User-agent: Claude-Web
Disallow: /

User-agent: Bytespider
Disallow: /

User-agent: Omgilibot
Disallow: /

User-agent: FacebookBot
Disallow: /

User-agent: Diffbot
Disallow: /

User-agent: Amazonbot
Disallow: /

User-agent: PerplexityBot
Disallow: /

User-agent: YouBot
Disallow: /

User-agent: Applebot-Extended
Disallow: /

User-agent: ClaudeBot
Disallow: /

User-agent: Cohere-AI
Disallow: /

# Allow regular search engines
User-agent: Googlebot
Allow: /

User-agent: Bingbot
Allow: /

User-agent: *
Allow: /

# Sitemap (optional)
# Sitemap: https://chuuk.findinfinite.com/sitemap.xml
"""
    return Response(robots_content, mimetype="text/plain")


# =============================================================================
# Translation Game / Brochure Matching API
# =============================================================================


@app.route("/api/brochures/sentences", methods=["GET"])
def api_get_brochure_sentences():
    """API: Get sentences from English and Chuukese brochures for matching game"""
    try:
        import json
        from pathlib import Path

        # Load sentences from JSON file
        sentences_file = Path(__file__).parent / "data" / "brochure_sentences.json"

        if not sentences_file.exists():
            return jsonify({"error": "Brochure sentences not found. Run extract_brochure_sentences.py first."}), 404

        with open(sentences_file, encoding="utf-8") as f:
            data = json.load(f)

        return jsonify({"english": data["english"], "chuukese": data["chuukese"], "metadata": data["metadata"]}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/articles/fetch", methods=["POST"])
def api_fetch_article():
    """API: Fetch article content from wol.jw.org in English and Chuukese"""
    try:
        data = request.get_json()
        english_url = data.get("url") or data.get("englishUrl")
        chuukese_url = data.get("chuukeseUrl")

        if not english_url:
            return jsonify({"error": "English URL is required"}), 400

        if "wol.jw.org" not in english_url:
            return jsonify({"error": "Only wol.jw.org URLs are supported"}), 400

        def fetch_content(target_url):
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Connection": "keep-alive",
            }
            response = requests.get(target_url, headers=headers, timeout=60)
            response.raise_for_status()
            return response.text

        def find_chuukese_url(html):
            """Try to find Chuukese version link in the English page"""
            soup = BeautifulSoup(html, "html.parser")
            # Look for language selector links
            all_links = soup.find_all("a", href=True)
            for link in all_links:
                href = link.get("href", "")
                if "/chk/" in href and "/lp-te/" in href:
                    if href.startswith("http"):
                        return href
                    else:
                        return f"https://wol.jw.org{href}"
            return None

        def extract_endnote_scripture_refs(element):
            """Extract scripture references from endnote/footnote sections - each as separate entry"""
            scripture_refs = []
            for link in element.find_all("a", href=True):
                href = link.get("href", "")
                text = link.get_text(strip=True)
                # Check if this is a scripture reference link (in endnotes/footnotes)
                if ("/bc/" in href or "/nwtsty/" in href or "/bible/" in href) and re.search(r"\d+:\d+", text):
                    if text and len(text) > 1:
                        scripture_refs.append(text)
            return scripture_refs

        def is_endnote_section(element):
            """Check if element is part of an endnote/footnote section"""
            # Check for common endnote indicators
            text = element.get_text(strip=True)
            if text.startswith("PWAL") or text.startswith("SEE ALSO"):
                return True
            # Check parent classes
            parent = element.find_parent(class_=re.compile(r"footnote|endnote|groupFootnote|boxContent"))
            return parent is not None

        def parse_sentences(html):
            soup = BeautifulSoup(html, "html.parser")
            article = soup.find("article") or soup.find("div", class_="bodyTxt")

            if not article:
                return [], None

            title_elem = soup.find("h1")
            title = title_elem.get_text(strip=True) if title_elem else "Untitled"

            paragraphs = article.find_all(["p", "li"])
            sentences = []

            for idx, para in enumerate(paragraphs):
                text = para.get_text(separator=" ", strip=True)

                # Remove zero-width characters and other invisible Unicode
                text = re.sub(r"[\u200b\u200c\u200d\u00ad\ufeff\u2060]", "", text)

                # Clean bullet points but preserve content
                text = re.sub(r"^[•●◦▪▫■□‣⁃∙]+\s*", "", text)  # Remove leading bullets
                text = re.sub(r"^\*+\s*", "", text)  # Remove asterisk bullets
                text = re.sub(r"\s+", " ", text)  # Normalize whitespace
                text = text.strip()

                if len(text) < 15:
                    continue

                # Check if this is an endnote section - handle differently
                if is_endnote_section(para):
                    # Extract each scripture reference as its own line
                    endnote_refs = extract_endnote_scripture_refs(para)
                    for ref in endnote_refs:
                        sentences.append(
                            {
                                "id": len(sentences) + 1,
                                "text": f"📖 {ref}",
                                "paragraph_index": idx,
                                "is_scripture_ref": True,
                            }
                        )
                    continue

                # KEY FIX: Keep em-dash (—) and hyphen-dash (-) scripture references attached to sentences
                # Pattern matches: sentence ending + em-dash/hyphen + scripture reference
                # Examples: "...kapas allim."—Féf. 5:42  or  "...example."—1 Cor. 15:33

                # STEP 1: Protect ALL scripture references from being split
                # This includes inline refs, em-dash refs, and parenthetical refs
                # Book names loaded from config/scripture_books.json
                from src.utils.scripture_parser import get_scripture_reference_pattern

                any_scripture_pattern = get_scripture_reference_pattern()
                protected_refs = []

                def protect_any_scripture(match):
                    placeholder = f"<<<REF_{len(protected_refs)}>>>"
                    protected_refs.append(match.group(0))
                    return placeholder

                # First protect all inline scripture references
                text_protected = re.sub(any_scripture_pattern, protect_any_scripture, text)

                # Also protect em-dash + scripture that might have already been partially matched
                # Pattern: punctuation + em-dash + placeholder (already protected scripture)
                emdash_pattern = r"([.!?])\s*(—|–|-)\s*(<<<REF_\d+>>>)"
                text_protected = re.sub(emdash_pattern, r"\1\2\3", text_protected)

                # Protect parenthetical scriptures: ( placeholder ) or ( text with placeholder )
                # These should stay together with surrounding sentence
                protected_parens = []  # Separate list for parenthetical references
                paren_pattern = r"\(\s*(<<<REF_\d+>>>(?:\s*;\s*<<<REF_\d+>>>)*)\s*\)"

                def protect_paren(match):
                    placeholder = f"<<<PAREN_{len(protected_parens)}>>>"
                    protected_parens.append(match.group(1))  # Store the inner content (just the REF placeholders)
                    return placeholder

                text_protected = re.sub(paren_pattern, protect_paren, text_protected)

                # Now split on sentence boundaries (. ! ?) followed by space
                # But not at our placeholders (which start with <) and not after book abbreviations
                sent_list = re.split(r"(?<=[.!?])\s+(?![<])", text_protected)

                for sent in sent_list:
                    # First restore parenthetical placeholders (which contain REF placeholders)
                    for i, paren_content in enumerate(protected_parens):
                        sent = sent.replace(f"<<<PAREN_{i}>>>", f"({paren_content})")

                    # Then restore scripture references
                    for i, ref in enumerate(protected_refs):
                        sent = sent.replace(f"<<<REF_{i}>>>", ref)

                    sent = sent.strip()
                    if len(sent) > 20:
                        sentences.append({"id": len(sentences) + 1, "text": sent, "paragraph_index": idx})

            return sentences, title

        # Fetch English
        print(f"📖 Fetching English article from: {english_url}")
        english_html = fetch_content(english_url)
        english_sentences, english_title = parse_sentences(english_html)
        print(f"   Found {len(english_sentences)} English sentences")

        # Get Chuukese URL - try provided URL, then search, then return error
        if not chuukese_url:
            print("   🔍 Looking for Chuukese version link...")
            chuukese_url = find_chuukese_url(english_html)

        if not chuukese_url:
            return (
                jsonify(
                    {
                        "error": "Chuukese URL not found. Please provide the Chuukese article URL.",
                        "english": {"url": english_url, "title": english_title, "sentences": english_sentences},
                    }
                ),
                400,
            )

        # Fetch Chuukese
        print(f"📖 Fetching Chuukese article from: {chuukese_url}")
        chuukese_html = fetch_content(chuukese_url)
        chuukese_sentences, chuukese_title = parse_sentences(chuukese_html)
        print(f"   Found {len(chuukese_sentences)} Chuukese sentences")

        return (
            jsonify(
                {
                    "success": True,
                    "english": {"url": english_url, "title": english_title, "sentences": english_sentences},
                    "chuukese": {"url": chuukese_url, "title": chuukese_title, "sentences": chuukese_sentences},
                }
            ),
            200,
        )

    except Exception as e:
        print(f"❌ Error fetching article: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/brochures/match", methods=["POST"])
def api_save_brochure_match():
    """API: Save a translation match from the game"""
    try:
        data = request.get_json()

        english_text = data.get("english_text", "")
        chuukese_text = data.get("chuukese_text", "")
        source = data.get("source", "translation_game")

        # Create a proper database entry in phrases_collection
        phrase_data = {
            "_id": f"sentence_{hash(chuukese_text) & 0x7FFFFFFF}_{hash(english_text) & 0x7FFFFFFF}",
            "chuukese_sentence": chuukese_text.strip(),
            "chuukese_word": chuukese_text.strip(),  # For compatibility with dictionary display
            "english_translation": english_text.strip(),
            "type": "sentence",
            "confidence": 1.0,  # 100% confidence when user confirms
            "confidence_score": 100,  # 100% confidence score
            "grammar": "phrase",
            "search_direction": "chk_to_en",
            "definition": "",  # Leave blank, user_confirmed flag indicates source
            "source": source,
            "source_type": "translation_game",
            "date_added": datetime.now(timezone.utc),
            "date_modified": datetime.now(timezone.utc),
            "created_date": datetime.now(timezone.utc),
            "user_confirmed": True,
            "edited_by": _get_user_initials(),
            "game_metadata": {
                "english_id": data.get("english_id"),
                "chuukese_ids": data.get("chuukese_ids", []),
                "original_english_text": data.get("original_english_text"),
                "was_edited": data.get("original_english_text") and english_text != data.get("original_english_text"),
                "user_id": data.get("user_id", "anonymous"),
                "timestamp": datetime.now(timezone.utc),
            },
        }

        try:
            # Save to phrases collection (sentences are stored there)
            result = dict_db.phrases_collection.insert_one(phrase_data)
            phrase_id = str(result.inserted_id)
        except DuplicateKeyError:
            # If duplicate, update existing entry
            phrase_id = phrase_data["_id"]
            dict_db.phrases_collection.update_one(
                {"_id": phrase_id},
                {"$set": {"date_modified": datetime.now(timezone.utc), "confidence": 1.0, "user_confirmed": True}},
            )

        # Also save to game matches for statistics
        match_data = {
            "english_id": data.get("english_id"),
            "chuukese_ids": data.get("chuukese_ids", []),
            "english_text": english_text,
            "original_english_text": data.get("original_english_text"),
            "chuukese_text": chuukese_text,
            "is_correct": data.get("is_correct", True),
            "user_id": data.get("user_id", "anonymous"),
            "was_edited": data.get("original_english_text") and english_text != data.get("original_english_text"),
            "phrase_id": phrase_id,
            "timestamp": datetime.now(timezone.utc),
        }

        dict_db.db["brochure_matches"].insert_one(match_data)

        return (
            jsonify(
                {
                    "message": "Match saved successfully",
                    "phrase_id": phrase_id,
                    "entry_type": "sentence",
                    "confidence": 1.0,
                }
            ),
            201,
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/translate/word-suggestions", methods=["POST"])
def api_word_suggestions():
    """Translate each Chuukese token via Helsinki and cross-reference against the matched English sentence.
    Returns per-token suggestions: matched English word(s) + grammar recommendation."""
    try:
        data = request.get_json()
        chuukese_tokens = data.get("chuukese_tokens", [])  # list of individual Chuukese words
        english_sentence = data.get("english_sentence", "")  # full matched English sentence

        if not chuukese_tokens or not english_sentence:
            return jsonify({"error": "chuukese_tokens and english_sentence are required"}), 400

        if not helsinki_translator:
            return jsonify({"error": "Helsinki translator not available"}), 503

        # Normalised English words for matching (lowercase, strip punctuation)
        import re as _re

        def _norm(w):
            return _re.sub(r"[^a-z']", "", w.lower())

        english_words = english_sentence.split()
        english_norms = [_norm(w) for w in english_words]

        def suggest_grammar(english_word: str) -> str:
            """Simple POS heuristic based on the English word."""
            w = english_word.lower().rstrip("s")
            # Pronouns
            if w in (
                "i",
                "you",
                "he",
                "she",
                "it",
                "we",
                "they",
                "me",
                "him",
                "her",
                "us",
                "them",
                "my",
                "your",
                "his",
                "its",
                "our",
                "their",
            ):
                return "pronoun"
            # Common verbs
            if w in (
                "is",
                "was",
                "were",
                "be",
                "been",
                "being",
                "have",
                "has",
                "had",
                "do",
                "does",
                "did",
                "will",
                "would",
                "can",
                "could",
                "shall",
                "should",
                "may",
                "might",
                "must",
                "go",
                "come",
                "say",
                "get",
                "make",
                "know",
                "think",
                "take",
                "see",
                "want",
                "give",
                "use",
                "find",
                "tell",
                "ask",
                "seem",
                "feel",
                "try",
                "leave",
                "call",
            ):
                return "verb"
            # Verb suffixes
            if english_word.lower().endswith(("ing", "ed", "fy", "ize", "ise", "en")):
                return "verb"
            # Adjective suffixes
            if english_word.lower().endswith(("ful", "less", "ous", "ive", "al", "ble", "ic", "ish", "like")):
                return "adjective"
            # Adverb suffixes
            if english_word.lower().endswith("ly"):
                return "adverb"
            # Noun suffixes
            if english_word.lower().endswith(
                ("tion", "sion", "ness", "ment", "ity", "er", "or", "ist", "ism", "age", "ure")
            ):
                return "noun"
            # Articles / prepositions / conjunctions
            if w in (
                "a",
                "an",
                "the",
                "of",
                "in",
                "on",
                "at",
                "to",
                "for",
                "with",
                "by",
                "from",
                "into",
                "over",
                "under",
                "and",
                "but",
                "or",
                "so",
                "yet",
                "nor",
                "although",
                "because",
                "since",
                "while",
                "if",
                "when",
                "that",
            ):
                return "particle" if w in ("a", "an", "the") else "preposition"
            return "noun"  # default

        suggestions = []
        for token in chuukese_tokens:
            token = token.strip()
            if not token:
                continue

            # First check if word already exists in dictionary
            existing = dict_db.dictionary_collection.find_one(
                {"chuukese_word": {"$regex": f"^{_re.escape(token)}$", "$options": "i"}},
                {"english_translation": 1, "grammar": 1},
            )
            if existing:
                suggestions.append(
                    {
                        "chuukese": token,
                        "helsinki_translation": existing.get("english_translation", ""),
                        "matched_english_words": [],
                        "grammar_suggestion": existing.get("grammar", "noun"),
                        "in_dictionary": True,
                        "confidence": "high",
                    }
                )
                continue

            # Translate via Helsinki
            try:
                translation = helsinki_translator.translate_chuukese_to_english(token).strip()
            except Exception:
                translation = ""

            # Cross-reference against words in the English sentence
            translation_words = [_norm(w) for w in translation.split() if _norm(w)]
            matched = [
                english_words[i]
                for i, en in enumerate(english_norms)
                if en and any(en == tw or en.startswith(tw[:4]) for tw in translation_words if len(tw) >= 4)
            ]

            grammar = (
                suggest_grammar(matched[0])
                if matched
                else (suggest_grammar(translation.split()[0]) if translation else "noun")
            )

            suggestions.append(
                {
                    "chuukese": token,
                    "helsinki_translation": translation,
                    "matched_english_words": matched,
                    "grammar_suggestion": grammar,
                    "in_dictionary": False,
                    "confidence": "high" if matched else "low",
                }
            )

        return jsonify({"suggestions": suggestions})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/brochures/match/words", methods=["GET"])
def api_lookup_word_pairs():
    """Look up existing dictionary entries for a list of Chuukese tokens.
    Returns matched entries so the frontend can pre-populate linked pairs."""
    try:
        tokens_param = request.args.get("chuukese_tokens", "")
        if not tokens_param:
            return jsonify({"pairs": []}), 200

        tokens = [t.strip() for t in tokens_param.split(",") if t.strip()]
        pairs = []
        for token in tokens:
            entry = dict_db.dictionary_collection.find_one(
                {"chuukese_word": {"$regex": f"^{re.escape(token)}$", "$options": "i"}},
                {"chuukese_word": 1, "english_translation": 1, "grammar": 1, "definition": 1,
                 "confidence_score": 1, "verified": 1}
            )
            if entry:
                pairs.append({
                    "chuukese": entry.get("chuukese_word", token),
                    "english": entry.get("english_translation", ""),
                    "grammar": entry.get("grammar", "noun") or "noun",
                    "description": entry.get("definition", "") or "",
                    "confidence_score": entry.get("confidence_score", 0),
                    "verified": entry.get("verified", False),
                })
        return jsonify({"pairs": pairs}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/brochures/match/words", methods=["POST"])
def api_save_word_pairs():
    """Save individual word pairs extracted from a validated sentence match.
    Each pair is upserted into dictionary_collection at confidence 100 / verified."""
    try:
        data = request.get_json()
        word_pairs = data.get("word_pairs", [])  # [{chuukese, english, grammar}]
        source_sentence_id = data.get("source_sentence_id", "")

        if not word_pairs:
            return jsonify({"error": "word_pairs is required"}), 400

        saved = []
        skipped = []

        for pair in word_pairs:
            chuukese_word = (pair.get("chuukese") or "").strip()
            english_translation = (pair.get("english") or "").strip()
            grammar = (pair.get("grammar") or "noun").strip()
            description = (pair.get("description") or "").strip()

            if not chuukese_word or not english_translation:
                continue

            entry = {
                "chuukese_word": chuukese_word,
                "english_translation": english_translation,
                "grammar": grammar,
                "definition": description,
                "confidence_score": 100,
                "confidence_level": "verified",
                "verified": True,
                "user_confirmed": True,
                "source": "translation_game_word_pair",
                "source_sentence_id": source_sentence_id,
                "updated_date": datetime.now(timezone.utc),
            }

            existing = dict_db.dictionary_collection.find_one(
                {"chuukese_word": {"$regex": f"^{re.escape(chuukese_word)}$", "$options": "i"}}
            )

            if existing:
                # Append new translation to definition/notes if different from current
                existing_translation = existing.get("english_translation", "").strip()
                existing_definition = existing.get("definition", "").strip()
                update_fields = {
                    "grammar": grammar,
                    "confidence_score": 100,
                    "confidence_level": "verified",
                    "verified": True,
                    "user_confirmed": True,
                    "updated_date": datetime.now(timezone.utc),
                    "edited_by": _get_user_initials(),
                }
                # Only update primary translation if field was empty
                if not existing_translation:
                    update_fields["english_translation"] = english_translation
                elif english_translation.lower() != existing_translation.lower():
                    # Different meaning — append to notes/definition on a new line
                    note_line = f"Also: {english_translation} (translation game)"
                    if note_line not in existing_definition:
                        update_fields["definition"] = (existing_definition + "\n" + note_line).strip()
                # Always write description if provided (overrides existing definition)
                if description:
                    update_fields["definition"] = description
                dict_db.dictionary_collection.update_one({"_id": existing["_id"]}, {"$set": update_fields})
                skipped.append(chuukese_word)
            else:
                entry["created_date"] = datetime.now(timezone.utc)
                entry["edited_by"] = _get_user_initials()
                dict_db.dictionary_collection.insert_one(entry)
                saved.append(chuukese_word)

        return jsonify({"saved": saved, "updated": skipped, "total": len(saved) + len(skipped)}), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/brochures/stats", methods=["GET"])
def api_get_brochure_stats():
    """API: Get user statistics for the translation game"""
    try:
        user_id = request.args.get("user_id", "anonymous")

        # Get total matches
        total_matches = dict_db.db["brochure_matches"].count_documents({"user_id": user_id})

        # Get correct matches
        correct_matches = dict_db.db["brochure_matches"].count_documents({"user_id": user_id, "is_correct": True})

        # Calculate score (10 points per correct match)
        score = correct_matches * 10

        # Calculate accuracy
        accuracy = (correct_matches / total_matches * 100) if total_matches > 0 else 0

        return (
            jsonify(
                {
                    "user_id": user_id,
                    "total_matches": total_matches,
                    "correct_matches": correct_matches,
                    "incorrect_matches": total_matches - correct_matches,
                    "score": score,
                    "accuracy": round(accuracy, 1),
                }
            ),
            200,
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# =============================================================================
# Verb Example Lookup API
# =============================================================================
@app.route("/api/verbs/lookup-examples", methods=["POST"])
@login_required
def lookup_verb_examples():
    """Search for example sentences containing a verb phrase or just the verb"""
    try:
        data = request.get_json()
        phrase = data.get("phrase", "").strip()
        verb = data.get("verb", "").strip()

        if not phrase and not verb:
            return jsonify({"error": "Phrase or verb is required"}), 400

        results = []

        # Search in paragraphs collection
        if dict_db and dict_db.paragraphs_collection is not None:
            # First try exact phrase match
            if phrase:
                cursor = dict_db.paragraphs_collection.find(
                    {"chuukese_paragraph": {"$regex": phrase, "$options": "i"}},
                    {"_id": 0, "chuukese_paragraph": 1, "english_paragraph": 1, "source": 1},
                ).limit(5)

                for doc in cursor:
                    results.append(
                        {
                            "chuukese": doc.get("chuukese_paragraph", ""),
                            "english": doc.get("english_paragraph", ""),
                            "source": doc.get("source", "Unknown"),
                            "matchType": "phrase",
                        }
                    )

            # If no results or need more, try just the verb
            if len(results) < 5 and verb:
                already_found = {r["chuukese"] for r in results}
                cursor = dict_db.paragraphs_collection.find(
                    {"chuukese_paragraph": {"$regex": verb, "$options": "i"}},
                    {"_id": 0, "chuukese_paragraph": 1, "english_paragraph": 1, "source": 1},
                ).limit(10 - len(results))

                for doc in cursor:
                    chk = doc.get("chuukese_paragraph", "")
                    if chk not in already_found:
                        results.append(
                            {
                                "chuukese": chk,
                                "english": doc.get("english_paragraph", ""),
                                "source": doc.get("source", "Unknown"),
                                "matchType": "verb",
                            }
                        )

        # Also search in phrases collection
        if dict_db and dict_db.phrases_collection is not None and len(results) < 5:
            search_term = phrase if phrase else verb
            if search_term:
                already_found = {r["chuukese"] for r in results}
                cursor = dict_db.phrases_collection.find(
                    {"chuukese": {"$regex": search_term, "$options": "i"}},
                    {"_id": 0, "chuukese": 1, "english": 1, "source": 1},
                ).limit(5)

                for doc in cursor:
                    chk = doc.get("chuukese", "")
                    if chk not in already_found:
                        results.append(
                            {
                                "chuukese": chk,
                                "english": doc.get("english", ""),
                                "source": doc.get("source", "Phrases"),
                                "matchType": "phrase" if phrase and phrase in chk else "verb",
                            }
                        )

        return (
            jsonify(
                {"phrase": phrase, "verb": verb, "results": results[:10], "totalFound": len(results)}  # Max 10 results
            ),
            200,
        )

    except Exception as e:
        import traceback

        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# =============================================================================
# React app routes - handle all non-API routes
# =============================================================================
@app.route("/api/sentences/analyze", methods=["POST"])
@login_required
def analyze_sentence():
    """Analyze a Chuukese sentence word by word"""
    try:
        data = request.get_json()
        sentence = data.get("sentence", "").strip()

        if not sentence:
            return jsonify({"error": "Sentence is required"}), 400

        # Split sentence into words (handle punctuation)
        words = re.findall(r"\b[\w\u00C0-\u024F]+\b", sentence)

        if not words:
            return jsonify({"error": "No valid words found in sentence"}), 400

        # Look up each word in dictionary
        word_analyses = []
        found_words = []
        grammar_sequence = []

        for word in words:
            # Try exact match first
            result = dict_db.dictionary_collection.find_one(
                {"chuukese_word": {"$regex": f"^{re.escape(word)}$", "$options": "i"}}
            )

            # If not found, try without case sensitivity
            if not result:
                result = dict_db.dictionary_collection.find_one(
                    {"chuukese_word": {"$regex": f"^{re.escape(word)}", "$options": "i"}}
                )

            if result:
                # Prepare full entry for modal display
                full_entry = {
                    "entry_id": str(result["_id"]),
                    "notes": result.get("notes", ""),
                    "examples": result.get("examples", ""),
                    "english": result.get("english_translation", ""),
                    "grammar": result.get("grammar", ""),
                    "definition": result.get("definition", ""),
                    "pronunciation": result.get("pronunciation", ""),
                    "source": result.get("source", ""),
                    "etymology": result.get("etymology", ""),
                    "usage": result.get("usage", ""),
                    "synonyms": result.get("synonyms", ""),
                    "antonyms": result.get("antonyms", ""),
                    "related_words": result.get("related_words", ""),
                }

                word_analyses.append(
                    {
                        "original": word,
                        "english": result.get("english_translation", "unknown"),
                        "grammar": result.get("grammar", "unknown"),
                        "grammar_modifier": result.get("grammar_modifier"),
                        "definition": result.get("definition", ""),
                        "found": True,
                        "full_entry": full_entry,
                    }
                )
                found_words.append(result.get("english_translation", word))
                grammar_sequence.append(result.get("grammar", "unknown"))
            else:
                word_analyses.append({"original": word, "english": word, "grammar": "unknown", "found": False})
                found_words.append(word)
                grammar_sequence.append("unknown")

        # Analyze sentence structure
        structure_info = analyze_sentence_structure(grammar_sequence, word_analyses)

        # Rearrange translation based on Chuukese grammar
        rearranged = rearrange_translation(word_analyses, grammar_sequence)

        # Find phrases in the sentence
        phrases = find_phrases_in_sentence(sentence, words)

        return jsonify(
            {
                "original_sentence": sentence,
                "word_by_word": word_analyses,
                "phrases": phrases,
                "rearranged_translation": rearranged,
                "structure_info": structure_info,
            }
        )

    except Exception as e:
        print(f"Error analyzing sentence: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/sentences/analyze-url", methods=["POST"])
@login_required
def analyze_article_url():
    """
    Fetch a Chuukese article and stream word-by-word analysis paragraph-by-paragraph.
    Optionally fetches the parallel English article for real-sentence alignment.

    Response is newline-delimited JSON (NDJSON):
      {"type":"meta",  "title":"...", "url":"...", "english_url":"...", "paragraph_count": N}
      {"type":"paragraph", "index": N, "sentences":[{..., "english_text":"...", "english_tokens":[...]}], ...}
      {"type":"done", "total_sentences": N}
      {"type":"error", "message":"..."}
    """
    from flask import stream_with_context
    import json as _json

    data = request.get_json(silent=True) or {}
    url = data.get("url", "").strip()
    english_url_param = data.get("english_url", "").strip()

    if not url:
        return jsonify({"error": "URL is required"}), 400
    if not url.startswith(("http://", "https://")):
        return jsonify({"error": "URL must start with http:// or https://"}), 400

    _dict_db = dict_db

    def derive_english_url(chk_url):
        """Auto-derive English wol.jw.org URL from a Chuukese one."""
        m = re.search(r"/(\d{5,})(?:\?|$|/)", chk_url)
        if m:
            return f"https://wol.jw.org/en/wol/d/r1/lp-e/{m.group(1)}"
        return None

    def generate():
        from src.utils.scripture_parser import get_scripture_reference_pattern

        def emit(obj):
            return _json.dumps(obj, ensure_ascii=False) + "\n"

        fetch_headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

        def safe_fetch(target_url):
            try:
                r = requests.get(target_url, headers=fetch_headers, timeout=30)
                r.raise_for_status()
                return r.text, None
            except requests.exceptions.Timeout:
                return None, "Request timed out"
            except requests.exceptions.ConnectionError:
                return None, "Could not connect"
            except requests.exceptions.HTTPError as e:
                return None, f"HTTP {e.response.status_code}"
            except Exception as e:
                return None, str(e)

        def parse_paragraphs(html):
            """Return list of (tag, cleaned_text) for meaningful elements."""
            soup = BeautifulSoup(html, "html.parser")
            article = (
                soup.find("article")
                or soup.find("div", class_="bodyTxt")
                or soup.find("main")
                or soup.find("body")
            )
            if not article:
                return [], soup
            result = []
            for elem in article.find_all(["h2", "h3", "p", "li"]):
                raw = elem.get_text(separator=" ", strip=True)
                raw = re.sub(r"[\u200b\u200c\u200d\u00ad\ufeff\u2060]", "", raw)
                raw = re.sub(r"\s+", " ", raw).strip()
                if len(raw) >= 10:
                    result.append((elem.name, raw))
            return result, soup

        def split_sentences(raw_text, scripture_pattern):
            """Split a paragraph into sentence strings, protecting scripture refs."""
            protected_refs = []

            def protect(m, _r=protected_refs):
                ph = f"<<<S{len(_r)}>>>"
                _r.append(m.group(0))
                return ph

            protected = re.sub(scripture_pattern, protect, raw_text)
            parts = re.split(r"(?<=[.!?])\s+(?![<])", protected)
            out = []
            for part in parts:
                for i, ref in enumerate(protected_refs):
                    part = part.replace(f"<<<S{i}>>>", ref)
                part = part.strip()
                if len(part) >= 10:
                    out.append(part)
            return out

        def _fuzzy_token_match(tok_clean: str, trans_word: str) -> bool:
            """True if tok_clean and trans_word are close enough to count as aligned."""
            if tok_clean == trans_word:
                return True
            # stem prefix: share at least 4 leading chars (handles go/going, run/running)
            stem_len = min(len(tok_clean), len(trans_word), 5)
            if stem_len >= 4 and tok_clean[:stem_len] == trans_word[:stem_len]:
                return True
            from difflib import SequenceMatcher
            return SequenceMatcher(None, tok_clean, trans_word).ratio() >= 0.82

        def _find_dict_entry(word: str):
            """Return best-matching dictionary entry for a Chuukese word."""
            # 1. Exact case-insensitive match
            result = _cosmos_retry(
                _dict_db.dictionary_collection.find_one,
                {"chuukese_word": {"$regex": f"^{re.escape(word)}$", "$options": "i"}},
            )
            if result:
                return result

            # 2. Fuzzy fallback: fetch candidates sharing the first 4 chars, score with difflib
            if len(word) >= 4:
                from difflib import SequenceMatcher
                prefix = word[:4]
                candidates = list(
                    _cosmos_retry(
                        lambda: list(
                            _dict_db.dictionary_collection.find(
                                {"chuukese_word": {"$regex": f"^{re.escape(prefix)}", "$options": "i"}},
                                {"chuukese_word": 1, "english_translation": 1, "grammar": 1,
                                 "grammar_modifier": 1, "definition": 1},
                            ).limit(30)
                        )
                    )
                )
                if candidates:
                    best = max(
                        candidates,
                        key=lambda c: SequenceMatcher(None, word.lower(), c["chuukese_word"].lower()).ratio(),
                    )
                    if SequenceMatcher(None, word.lower(), best["chuukese_word"].lower()).ratio() >= 0.75:
                        return best
            return None

        def analyze_words(sentence_text, eng_tokens=None):
            """Look up each word in the dictionary; optionally compute token alignment."""
            words = re.findall(r"\b[\w\u00C0-\u024F]+\b", sentence_text)
            analyses = []
            english_parts = []
            # Pre-clean English tokens once for alignment
            clean_eng = [re.sub(r"[^\w]", "", t.lower()) for t in (eng_tokens or [])]

            for word in words:
                result = _find_dict_entry(word)
                if result:
                    english = result.get("english_translation", "")
                    # Token alignment: fuzzy-match each translation word against English tokens
                    token_indices = []
                    if clean_eng:
                        trans_words = re.sub(r"[^\w\s]", "", english.lower()).split()
                        for i, tok_clean in enumerate(clean_eng):
                            if tok_clean and any(_fuzzy_token_match(tok_clean, tw) for tw in trans_words if tw):
                                token_indices.append(i)
                    analyses.append({
                        "original": word,
                        "english": english,
                        "grammar": result.get("grammar", ""),
                        "grammar_modifier": result.get("grammar_modifier"),
                        "definition": result.get("definition", ""),
                        "found": True,
                        "entry_id": str(result["_id"]),
                        "english_token_indices": token_indices,
                    })
                    english_parts.append(english)
                else:
                    analyses.append({
                        "original": word,
                        "english": word,
                        "grammar": "",
                        "found": False,
                        "entry_id": None,
                        "english_token_indices": [],
                    })
                    english_parts.append(word)
            return analyses, " ".join(english_parts)

        try:
            # ── Fetch Chuukese article ───────────────────────────────────────
            chk_html, err = safe_fetch(url)
            if err:
                yield emit({"type": "error", "message": err})
                return

            chk_paragraphs, chk_soup = parse_paragraphs(chk_html)
            if not chk_paragraphs:
                yield emit({"type": "error", "message": "No readable content found in the article"})
                return

            title_elem = chk_soup.find("h1")
            title = title_elem.get_text(strip=True) if title_elem else "Untitled"

            breadcrumb_parts = []
            for bc in chk_soup.select(".breadcrumbs a, nav[aria-label] a, .nav-breadcrumb a"):
                t = bc.get_text(strip=True)
                if t:
                    breadcrumb_parts.append(t)
            source_label = " › ".join(breadcrumb_parts) if breadcrumb_parts else ""

            # ── Fetch English article (optional) ────────────────────────────
            resolved_english_url = english_url_param or derive_english_url(url)
            english_para_sentences: dict[int, list[str]] = {}
            english_title = None

            if resolved_english_url:
                eng_html, eng_err = safe_fetch(resolved_english_url)
                if eng_html:
                    eng_paragraphs, eng_soup = parse_paragraphs(eng_html)
                    eng_title_elem = eng_soup.find("h1")
                    english_title = eng_title_elem.get_text(strip=True) if eng_title_elem else None
                    scripture_pattern_en = get_scripture_reference_pattern()
                    for i, (tag, raw) in enumerate(eng_paragraphs):
                        english_para_sentences[i] = split_sentences(raw, scripture_pattern_en)
                else:
                    resolved_english_url = None  # couldn't fetch — treat as unavailable

            # ── Emit meta ────────────────────────────────────────────────────
            yield emit({
                "type": "meta",
                "title": title,
                "url": url,
                "source_label": source_label,
                "paragraph_count": len(chk_paragraphs),
                "english_url": resolved_english_url,
                "english_title": english_title,
                "has_english": bool(english_para_sentences),
            })

            # ── Stream one paragraph at a time ───────────────────────────────
            scripture_pattern = get_scripture_reference_pattern()
            total_sentences = 0

            for idx, (tag, raw_text) in enumerate(chk_paragraphs):
                is_heading = tag in ("h2", "h3")
                chk_sent_texts = split_sentences(raw_text, scripture_pattern)
                eng_sent_texts = english_para_sentences.get(idx, [])

                sentences = []
                for si, part in enumerate(chk_sent_texts):
                    inline_refs = re.findall(scripture_pattern, part)
                    text_only = re.sub(scripture_pattern, "", part)
                    text_only = re.sub(r"[\u2014\u2013—–-]\s*$", "", text_only).strip()

                    # Aligned English sentence (positional)
                    english_text = eng_sent_texts[si] if si < len(eng_sent_texts) else None
                    # Tokenize English for word-level highlighting (split on whitespace)
                    english_tokens = english_text.split() if english_text else None

                    word_analyses, english_assembled = analyze_words(text_only, english_tokens)
                    sentences.append({
                        "chuukese": part,
                        "text_only": text_only,
                        "words": word_analyses,
                        "english_assembled": english_assembled,
                        "english_text": english_text,
                        "english_tokens": english_tokens,
                        "scriptures": inline_refs,
                    })

                total_sentences += len(sentences)
                yield emit({
                    "type": "paragraph",
                    "index": idx,
                    "is_heading": is_heading,
                    "raw_text": raw_text,
                    "sentences": sentences,
                    "sentence_count": len(sentences),
                })

            yield emit({"type": "done", "total_sentences": total_sentences})

        except Exception as e:
            print(f"Error in analyze_article_url stream: {e}")
            yield emit({"type": "error", "message": str(e)})

    return Response(
        stream_with_context(generate()),
        mimetype="application/x-ndjson",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )


# =============================================================================
# Article Analysis persistence  (/api/article-analyses)
# =============================================================================

def _get_article_analyses_collection():
    """Return (or lazily create) the article_analyses collection."""
    if dict_db.db is None:
        return None
    return dict_db.db["article_analyses"]


def _get_article_analysis_paragraphs_collection():
    """Return the collection that stores paragraph payloads per analysis."""
    if dict_db.db is None:
        return None
    return dict_db.db["article_analysis_paragraphs"]


def _serialize_article_analysis_metadata(docs):
    serialized = []
    for doc in docs:
        doc["_id"] = str(doc["_id"])
        created_at = doc.get("created_at")
        if isinstance(created_at, datetime):
            doc["created_at"] = created_at.isoformat()
        serialized.append(doc)
    return serialized


def _is_cosmos_excluded_order_by_error(exc):
    message = str(exc).lower()
    return (
        "order-by item is excluded" in message
        or "index path corresponding to the specified order-by item is excluded" in message
    )


def _article_analysis_created_at_sort_key(doc):
    created_at = doc.get("created_at")
    if isinstance(created_at, str):
        try:
            return datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        except ValueError:
            return datetime.min.replace(tzinfo=timezone.utc)
    if created_at:
        return created_at
    return datetime.min.replace(tzinfo=timezone.utc)


def _load_article_analysis_paragraphs(analysis_id, fallback_doc=None):
    """Load paragraph payloads from the split collection, falling back to embedded docs."""
    paragraphs_col = _get_article_analysis_paragraphs_collection()
    if paragraphs_col is None:
        return (fallback_doc or {}).get("paragraphs", [])

    paragraph_docs = list(paragraphs_col.find({"analysis_id": analysis_id}))
    if not paragraph_docs:
        return (fallback_doc or {}).get("paragraphs", [])

    paragraph_docs.sort(key=lambda doc: doc.get("paragraph_index", 0))
    return [doc.get("paragraph", {}) for doc in paragraph_docs]


@app.route("/api/article-analyses", methods=["GET"])
@login_required
def list_article_analyses():
    """List all saved article analyses (metadata only, no paragraph data)."""
    try:
        col = _get_article_analyses_collection()
        if col is None:
            return jsonify([])
        projection = {
            "_id": 1,
            "chuukese_title": 1,
            "english_title": 1,
            "url": 1,
            "english_url": 1,
            "source_label": 1,
            "paragraph_count": 1,
            "sentence_count": 1,
            "created_at": 1,
            "has_english": 1,
        }

        try:
            docs = list(col.find({}, projection).sort("created_at", -1).limit(100))
        except Exception as exc:
            if not _is_cosmos_excluded_order_by_error(exc):
                raise
            # Cosmos Mongo can reject order-by on excluded index paths; fall back to
            # an unsorted query and order the small result set in memory.
            docs = list(col.find({}, projection).limit(100))
            docs.sort(key=_article_analysis_created_at_sort_key, reverse=True)

        return jsonify(_serialize_article_analysis_metadata(docs))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/article-analyses/<analysis_id>", methods=["GET"])
@login_required
def get_article_analysis(analysis_id):
    """Retrieve a full saved analysis by ID."""
    try:
        from bson import ObjectId
        from bson.errors import InvalidId

        col = _get_article_analyses_collection()
        if col is None:
            return jsonify({"error": "Database unavailable"}), 503

        try:
            oid = ObjectId(analysis_id)
        except InvalidId:
            return jsonify({"error": "Invalid ID"}), 400

        doc = col.find_one({"_id": oid})
        if not doc:
            return jsonify({"error": "Analysis not found"}), 404

        doc["paragraphs"] = _load_article_analysis_paragraphs(oid, fallback_doc=doc)
        doc["_id"] = str(doc["_id"])
        if isinstance(doc.get("created_at"), datetime):
            doc["created_at"] = doc["created_at"].isoformat()
        return jsonify(doc)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/article-analyses", methods=["POST"])
@login_required
def save_article_analysis():
    """
    Upsert a completed article analysis.
    Keyed on `url` — re-analysing the same article overwrites the previous record.
    """
    try:
        data = request.get_json(silent=True) or {}
        url = data.get("url", "").strip()
        if not url:
            return jsonify({"error": "url is required"}), 400

        col = _get_article_analyses_collection()
        if col is None:
            return jsonify({"error": "Database unavailable"}), 503

        paragraphs_col = _get_article_analysis_paragraphs_collection()
        if paragraphs_col is None:
            return jsonify({"error": "Database unavailable"}), 503

        now = datetime.now(timezone.utc)
        paragraphs = data.get("paragraphs", [])

        doc = {
            "url": url,
            "chuukese_title": data.get("chuukese_title", ""),
            "english_title": data.get("english_title", ""),
            "english_url": data.get("english_url", ""),
            "source_label": data.get("source_label", ""),
            "has_english": data.get("has_english", False),
            "paragraph_count": data.get("paragraph_count", 0),
            "sentence_count": data.get("sentence_count", 0),
            "updated_at": now,
        }

        result = col.update_one(
            {"url": url},
            {"$set": doc, "$setOnInsert": {"created_at": now}},
            upsert=True,
        )

        analysis_oid = result.upserted_id
        if analysis_oid is None:
            existing = col.find_one({"url": url}, {"_id": 1})
            analysis_oid = existing["_id"] if existing else None

        if analysis_oid is None:
            return jsonify({"error": "Failed to resolve saved analysis ID"}), 500

        paragraphs_col.delete_many({"analysis_id": analysis_oid})
        if paragraphs:
            paragraphs_col.insert_many(
                [
                    {
                        "analysis_id": analysis_oid,
                        "paragraph_index": index,
                        "paragraph": paragraph,
                        "updated_at": now,
                    }
                    for index, paragraph in enumerate(paragraphs)
                ]
            )

        return jsonify({"success": True, "id": str(analysis_oid)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/article-analyses/<analysis_id>", methods=["DELETE"])
@login_required
def delete_article_analysis(analysis_id):
    """Delete a saved analysis (admin only)."""
    try:
        if session.get("user_role") != "admin":
            return jsonify({"error": "Admin access required"}), 403

        from bson import ObjectId
        from bson.errors import InvalidId

        col = _get_article_analyses_collection()
        if col is None:
            return jsonify({"error": "Database unavailable"}), 503

        try:
            oid = ObjectId(analysis_id)
        except InvalidId:
            return jsonify({"error": "Invalid ID"}), 400

        paragraphs_col = _get_article_analysis_paragraphs_collection()
        if paragraphs_col is not None:
            paragraphs_col.delete_many({"analysis_id": oid})

        result = col.delete_one({"_id": oid})
        if result.deleted_count == 0:
            return jsonify({"error": "Not found"}), 404
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/dictionary/add", methods=["POST"])
@login_required
def add_dictionary_word():
    """Add a new word to dictionary from sentence analysis"""
    try:
        data = request.get_json()

        chuukese_word = data.get("chuukese_word", "").strip()
        english_translation = data.get("english_translation", "").strip()
        definition = data.get("definition", "").strip()
        grammar = data.get("grammar", "").strip()

        if not chuukese_word or not english_translation or not grammar:
            return jsonify({"error": "Chuukese word, English translation, and grammar type are required"}), 400

        # Check if word already exists
        existing = _cosmos_retry(
            dict_db.dictionary_collection.find_one,
            {"chuukese_word": {"$regex": f"^{re.escape(chuukese_word)}$", "$options": "i"}},
        )

        if existing:
            # Word exists — update it instead of rejecting
            update_fields = {
                "english_translation": english_translation,
                "definition": definition,
                "grammar": grammar,
                "updated_date": datetime.now(),
                "edited_by": _get_user_initials(),
            }
            _cosmos_retry(
                dict_db.dictionary_collection.update_one,
                {"_id": existing["_id"]}, {"$set": update_fields},
            )
            return jsonify({"success": True, "message": "Word updated successfully", "entry_id": str(existing["_id"])}), 200

        # Prepare the new entry
        confidence_score = data.get("confidence", 100)

        # Create examples array with the sentence
        chuukese_example = data.get("chuukese_example", "")
        examples = [chuukese_example] if chuukese_example else []

        new_entry = {
            "chuukese_word": chuukese_word,
            "english_translation": english_translation,
            "definition": definition,
            "grammar": grammar,
            "confidence_score": confidence_score,
            "confidence_level": "verified" if confidence_score >= 90 else "high",
            "verified": data.get("verified", True),
            "examples": examples,
            "type": data.get("type", "sentence"),
            "source": "User Input - Sentence Analysis",
            "created_date": datetime.now(),
            "updated_date": datetime.now(),
            "added_by": session.get("user_email", "unknown"),
            "edited_by": _get_user_initials(),
        }

        # Insert into database
        result = _cosmos_retry(dict_db.dictionary_collection.insert_one, new_entry)

        if result.inserted_id:
            return (
                jsonify(
                    {
                        "success": True,
                        "message": "Word added successfully to dictionary",
                        "entry_id": str(result.inserted_id),
                    }
                ),
                201,
            )
        else:
            return jsonify({"error": "Failed to add word to dictionary"}), 500

    except Exception as e:
        print(f"Error adding word to dictionary: {str(e)}")
        import traceback

        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/dictionary/update", methods=["PUT"])
@login_required
def update_dictionary_word():
    """Update an existing dictionary entry from sentence analysis"""
    try:
        from bson import ObjectId
        from bson.errors import InvalidId

        data = request.get_json()

        entry_id = data.get("entry_id", "").strip()
        if not entry_id:
            return jsonify({"error": "entry_id is required"}), 400

        try:
            object_id = ObjectId(entry_id)
        except InvalidId:
            return jsonify({"error": "Invalid entry ID"}), 400

        update_fields = {}
        for field in ("english_translation", "grammar", "definition", "notes"):
            if field in data and data[field] is not None:
                value = data[field].strip() if isinstance(data[field], str) else data[field]
                update_fields[field] = value

        if not update_fields:
            return jsonify({"error": "No fields to update"}), 400

        if "grammar" in update_fields:
            raw = update_fields["grammar"]
            update_fields["grammar"] = dict_db._normalize_grammar(raw) if raw else raw

        update_fields["updated_date"] = datetime.now()
        update_fields["updated_by"] = session.get("username", "unknown")

        result = _cosmos_retry(
            dict_db.dictionary_collection.update_one,
            {"_id": object_id}, {"$set": update_fields},
        )

        if result.matched_count == 0:
            return jsonify({"error": "Entry not found"}), 404

        return jsonify({"success": True, "message": "Entry updated successfully"}), 200

    except Exception as e:
        print(f"Error updating dictionary word: {str(e)}")
        return jsonify({"error": str(e)}), 500


def analyze_sentence_structure(grammar_sequence: list[str], word_analyses: list[dict]) -> str:
    """Analyze the grammatical structure of the sentence"""
    # Count grammar types
    grammar_counts = {}
    for grammar in grammar_sequence:
        grammar_counts[grammar] = grammar_counts.get(grammar, 0) + 1

    # Build structure description
    parts = []
    has_verb = "verb" in grammar_sequence
    has_noun = "noun" in grammar_sequence
    has_subject_marker = any(w.get("grammar") == "pronoun" for w in word_analyses)

    if has_verb and has_noun:
        verb_pos = grammar_sequence.index("verb")
        noun_positions = [i for i, g in enumerate(grammar_sequence) if g == "noun"]

        if noun_positions and verb_pos < noun_positions[0]:
            parts.append("Verb-Object-Subject (VOS) order typical of Chuukese")
        else:
            parts.append("Non-standard word order detected")
    elif has_verb:
        parts.append("Contains verb")

    # Add grammar composition
    grammar_list = [
        f"{count} {grammar}{'s' if count > 1 else ''}"
        for grammar, count in grammar_counts.items()
        if grammar != "unknown"
    ]
    if grammar_list:
        parts.append(f"Composition: {', '.join(grammar_list)}")

    return ". ".join(parts) if parts else "Unable to determine sentence structure"


def rearrange_translation(word_analyses: list[dict], grammar_sequence: list[str]) -> str:
    """Rearrange word-by-word translation to grammatical English"""
    words = [w["english"] for w in word_analyses]

    # If no grammatical information, return as-is
    if "verb" not in grammar_sequence:
        return " ".join(words).capitalize()

    # Try to identify VOS pattern and convert to SVO
    try:
        verb_idx = grammar_sequence.index("verb")

        # Look for object (noun after verb)
        object_idx = None
        subject_idx = None

        for i in range(verb_idx + 1, len(grammar_sequence)):
            if grammar_sequence[i] == "noun" and object_idx is None:
                object_idx = i
            elif grammar_sequence[i] in ["noun", "pronoun"] and object_idx is not None:
                subject_idx = i
                break

        # Rearrange if we found VOS pattern
        if verb_idx is not None and object_idx is not None and subject_idx is not None:
            # Subject - Verb - Object
            rearranged = [words[subject_idx], words[verb_idx], words[object_idx]]  # Subject  # Verb  # Object

            # Add other words
            for i, word in enumerate(words):
                if i not in [verb_idx, object_idx, subject_idx]:
                    rearranged.append(word)

            result = " ".join(rearranged)
            return result.capitalize()
    except Exception:
        pass

    # Default: return words in original order
    return " ".join(words).capitalize()


def find_phrases_in_sentence(sentence: str, words: list[str]) -> list[dict]:
    """Logically break down the sentence into meaningful phrases based on grammar"""
    phrases_found = []

    try:
        # Re-lookup words with their grammar to build phrases
        word_data = []
        for word in words:
            result = dict_db.collection.find_one({"chuukese_word": {"$regex": f"^{re.escape(word)}$", "$options": "i"}})
            if result:
                word_data.append(
                    {
                        "word": word,
                        "english": result.get("english_translation", word),
                        "grammar": result.get("grammar", "unknown"),
                        "grammar_modifier": result.get("grammar_modifier"),
                    }
                )
            else:
                word_data.append({"word": word, "english": word, "grammar": "unknown", "grammar_modifier": None})

        # Pattern 1: Verb + Object (Noun) - VOS pattern
        for i in range(len(word_data) - 1):
            if word_data[i]["grammar"] == "verb":
                # Look for noun after verb
                for j in range(i + 1, min(i + 4, len(word_data))):
                    if word_data[j]["grammar"] == "noun":
                        phrase_words = word_data[i : j + 1]
                        phrase = " ".join([w["word"] for w in phrase_words])
                        english = " ".join([w["english"] for w in phrase_words])
                        phrases_found.append(
                            {
                                "phrase": phrase,
                                "english": english,
                                "type": "Verb + Object",
                                "explanation": f'Action phrase: "{word_data[i]["english"]}" acting on "{word_data[j]["english"]}"',
                            }
                        )
                        break

        # Pattern 2: Adjective + Noun
        for i in range(len(word_data) - 1):
            if word_data[i]["grammar"] == "adjective" and word_data[i + 1]["grammar"] == "noun":
                phrase = f"{word_data[i]['word']} {word_data[i+1]['word']}"
                english = f"{word_data[i]['english']} {word_data[i+1]['english']}"
                phrases_found.append(
                    {
                        "phrase": phrase,
                        "english": english,
                        "type": "Descriptive Phrase",
                        "explanation": f'Describes a noun: "{word_data[i]["english"]}" modifying "{word_data[i+1]["english"]}"',
                    }
                )

        # Pattern 3: Preposition + Noun (Locational phrase)
        for i in range(len(word_data) - 1):
            if word_data[i]["grammar"] == "preposition" and word_data[i + 1]["grammar"] == "noun":
                phrase = f"{word_data[i]['word']} {word_data[i+1]['word']}"
                english = f"{word_data[i]['english']} {word_data[i+1]['english']}"
                phrases_found.append(
                    {
                        "phrase": phrase,
                        "english": english,
                        "type": "Locational Phrase",
                        "explanation": f'Location or direction: "{word_data[i]["english"]}" with "{word_data[i+1]["english"]}"',
                    }
                )

        # Pattern 4: Pronoun + Verb (Subject-Verb)
        for i in range(len(word_data) - 1):
            if word_data[i]["grammar"] == "pronoun" and word_data[i + 1]["grammar"] == "verb":
                phrase = f"{word_data[i]['word']} {word_data[i+1]['word']}"
                english = f"{word_data[i]['english']} {word_data[i+1]['english']}"
                phrases_found.append(
                    {
                        "phrase": phrase,
                        "english": english,
                        "type": "Subject-Verb",
                        "explanation": f'Who does what: "{word_data[i]["english"]}" performs "{word_data[i+1]["english"]}"',
                    }
                )

        # Pattern 5: Number + Classifier + Noun
        for i in range(len(word_data) - 2):
            if (
                word_data[i]["grammar"] in ["numeral", "number"]
                and word_data[i + 1]["grammar"] == "classifier"
                and word_data[i + 2]["grammar"] == "noun"
            ):
                phrase = f"{word_data[i]['word']} {word_data[i+1]['word']} {word_data[i+2]['word']}"
                english = f"{word_data[i]['english']} {word_data[i+1]['english']} {word_data[i+2]['english']}"
                phrases_found.append(
                    {
                        "phrase": phrase,
                        "english": english,
                        "type": "Counting Phrase",
                        "explanation": f'Counting with classifier: "{word_data[i]["english"]}" of "{word_data[i+2]["english"]}"',
                    }
                )

    except Exception as e:
        print(f"Error finding phrases: {str(e)}")

    return phrases_found


# Catch-all route for React (must be last)
@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_react(path):
    """Serve React app for all non-API routes"""
    if path.startswith("api/"):
        return jsonify({"error": "API route not found"}), 404

    # Handle static assets
    if path.startswith("assets/"):
        return send_from_directory("frontend/dist", path)

    # Check if it's a static file request
    if "." in path and not path.startswith("api/"):
        try:
            return send_from_directory("frontend/dist", path)
        except Exception:
            pass

    # Serve index.html for React routing
    return send_from_directory("frontend/dist", "index.html")


if __name__ == "__main__":
    # Create upload directory if it doesn't exist
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    # Run the application
    # Debug mode should only be enabled in development
    debug_mode = os.getenv("FLASK_ENV") == "development"
    port = int(os.getenv("PORT", 5002))  # Use port 5002 as default
    print(f"Starting Flask app on port {port}")
    app.run(debug=debug_mode, host="0.0.0.0", port=port)
