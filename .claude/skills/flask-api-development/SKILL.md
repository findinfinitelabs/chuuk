---
name: flask-api-development
description: Build Flask REST APIs with authentication, file handling, database integration, and production deployment. Use when creating or modifying API endpoints, implementing authentication, or working with the Flask backend for the Chuuk Dictionary application.
---

# Flask API Development

## Overview

Build and maintain the Flask REST API backend for the Chuuk Dictionary application. Covers route organization, authentication, database integration, file handling, and production deployment patterns.

## Application Structure

```text
chuuk/
├── app.py                    # Main Flask application (3700+ lines)
├── src/
│   ├── core/
│   │   └── jworg_lookup.py   # JW.org word lookup
│   ├── database/
│   │   ├── db_factory.py     # Database connection factory
│   │   ├── dictionary_db.py  # Dictionary operations
│   │   └── publication_manager.py
│   ├── ocr/
│   │   └── ocr_processor.py  # OCR processing
│   ├── translation/
│   │   ├── helsinki_translator_v2.py
│   │   └── hybrid_translator.py
│   └── utils/
│       └── nwt_epub_parser.py
├── config/
│   └── users.json            # User configuration
└── requirements.txt
```

## Flask Application Setup

### Basic Configuration

```python
"""Flask application for Chuuk Dictionary OCR and Lookup"""
import os
import secrets
from flask import Flask
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables
env_path = Path(__file__).parent / '.env'
load_dotenv(env_path, override=True)

app = Flask(__name__)

# Configuration
secret_key = os.getenv('FLASK_SECRET_KEY')
if not secret_key:
    secret_key = secrets.token_hex(32)
    if os.getenv('FLASK_ENV') == 'production':
        raise ValueError('FLASK_SECRET_KEY must be set in production')

app.config['SECRET_KEY'] = secret_key
app.config['MAX_CONTENT_LENGTH'] = int(os.getenv('MAX_CONTENT_LENGTH', 16 * 1024 * 1024))
app.config['UPLOAD_FOLDER'] = os.getenv('UPLOAD_FOLDER', 'uploads')
app.config['SESSION_COOKIE_SECURE'] = os.getenv('FLASK_ENV') == 'production'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = 86400 * 7  # 7 days
```

### Lazy Loading Pattern

```python
# Lazy load expensive resources
_nwt_english_parser = None
_nwt_chuukese_parser = None

def get_nwt_english_parser():
    global _nwt_english_parser
    if _nwt_english_parser is None:
        epub_path = 'data/bible/nwt_E.epub'
        if os.path.exists(epub_path):
            _nwt_english_parser = NWTEpubParser(epub_path)
    return _nwt_english_parser

def get_nwt_chuukese_parser():
    global _nwt_chuukese_parser
    if _nwt_chuukese_parser is None:
        epub_path = 'data/bible/nwt_TE.epub'
        if os.path.exists(epub_path):
            _nwt_chuukese_parser = NWTEpubParser(epub_path)
    return _nwt_chuukese_parser
```

## Authentication

### Magic Link Authentication

```python
import secrets
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone, timedelta
from functools import wraps
from flask import session, request, jsonify

# In-memory storage (use Redis in production)
active_sessions = {}  # {email: session_id}
magic_links = {}  # {token: {'email': email, 'expires': datetime}}
MAGIC_LINK_EXPIRY_MINUTES = 15

def send_magic_link_email(email: str, magic_token: str, base_url: str) -> bool:
    """Send magic link email to user."""
    smtp_host = os.getenv('SMTP_HOST', 'smtp.gmail.com')
    smtp_port = int(os.getenv('SMTP_PORT', 587))
    smtp_user = os.getenv('SMTP_USER')
    smtp_password = os.getenv('SMTP_PASSWORD')
    from_email = os.getenv('SMTP_FROM', smtp_user)
    
    if not smtp_user or not smtp_password:
        # Dev mode - log the link
        print(f"Magic link for {email}: {base_url}/auth/magic/{magic_token}")
        return True
    
    magic_url = f"{base_url}/auth/magic/{magic_token}"
    
    msg = MIMEMultipart('alternative')
    msg['Subject'] = 'Chuuk Dictionary - Login Link'
    msg['From'] = from_email
    msg['To'] = email
    
    html_content = f"""
    <div style="font-family: Arial; max-width: 500px; padding: 20px;">
        <h2>Chuuk Dictionary Login</h2>
        <p>Click the button below to sign in:</p>
        <a href="{magic_url}" style="display: inline-block; background: #228be6; 
           color: white; padding: 12px 24px; text-decoration: none; border-radius: 4px;">
           Sign In
        </a>
        <p style="color: #666; font-size: 12px; margin-top: 20px;">
            This link expires in {MAGIC_LINK_EXPIRY_MINUTES} minutes.
        </p>
    </div>
    """
    
    msg.attach(MIMEText(html_content, 'html'))
    
    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(msg)
        return True
    except Exception as e:
        print(f"Email error: {e}")
        return False

@app.route('/auth/request-magic-link', methods=['POST'])
def request_magic_link():
    """Request a magic link for login."""
    data = request.get_json()
    email = data.get('email', '').strip().lower()
    
    if not email:
        return jsonify({'error': 'Email required'}), 400
    
    # Verify user is allowed
    if not is_user_allowed(email):
        return jsonify({'error': 'User not authorized'}), 403
    
    # Generate magic token
    token = secrets.token_urlsafe(32)
    magic_links[token] = {
        'email': email,
        'expires': datetime.now(timezone.utc) + timedelta(minutes=MAGIC_LINK_EXPIRY_MINUTES)
    }
    
    # Send email
    base_url = request.url_root.rstrip('/')
    if send_magic_link_email(email, token, base_url):
        return jsonify({'message': 'Magic link sent'})
    else:
        return jsonify({'error': 'Failed to send email'}), 500

@app.route('/auth/magic/<token>')
def verify_magic_link(token):
    """Verify magic link and create session."""
    link_data = magic_links.get(token)
    
    if not link_data:
        return jsonify({'error': 'Invalid or expired link'}), 400
    
    if datetime.now(timezone.utc) > link_data['expires']:
        del magic_links[token]
        return jsonify({'error': 'Link expired'}), 400
    
    email = link_data['email']
    
    # Create session
    session_id = secrets.token_urlsafe(32)
    session['user_email'] = email
    session['session_id'] = session_id
    session.permanent = True
    
    # Track active session
    active_sessions[email] = session_id
    
    # Cleanup used token
    del magic_links[token]
    
    return redirect('/')
```

### Authentication Decorator

```python
def login_required(f):
    """Decorator to require authentication."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_email' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        
        email = session['user_email']
        session_id = session.get('session_id')
        
        # Verify session is still active
        if active_sessions.get(email) != session_id:
            session.clear()
            return jsonify({'error': 'Session expired'}), 401
        
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """Decorator to require admin role."""
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        email = session['user_email']
        if not is_admin(email):
            return jsonify({'error': 'Admin access required'}), 403
        return f(*args, **kwargs)
    return decorated_function
```

## API Routes

### Dictionary Endpoints

```python
from flask import request, jsonify
from src.database.dictionary_db import DictionaryDB

db = DictionaryDB()

@app.route('/api/dictionary/search')
def search_dictionary():
    """Search dictionary entries."""
    query = request.args.get('query', '').strip()
    limit = int(request.args.get('limit', 50))
    search_type = request.args.get('type', 'fuzzy')
    
    if not query:
        return jsonify({'entries': [], 'total': 0})
    
    try:
        entries = db.search_entries(query, search_type=search_type, limit=limit)
        
        # Convert ObjectId to string for JSON serialization
        for entry in entries:
            entry['_id'] = str(entry['_id'])
        
        return jsonify({
            'entries': entries,
            'total': len(entries),
            'query': query
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/dictionary/entry/<word>')
def get_dictionary_entry(word):
    """Get single dictionary entry."""
    entry = db.get_entry(word)
    
    if entry:
        entry['_id'] = str(entry['_id'])
        return jsonify(entry)
    
    return jsonify({'error': 'Entry not found'}), 404

@app.route('/api/dictionary/entry', methods=['POST'])
@login_required
def create_dictionary_entry():
    """Create new dictionary entry."""
    data = request.get_json()
    
    required_fields = ['chuukese_word', 'english_definition']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'Missing required field: {field}'}), 400
    
    try:
        entry_id = db.add_entry(data)
        return jsonify({'id': entry_id, 'message': 'Entry created'}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/dictionary/entry/<word>', methods=['PUT'])
@login_required
def update_dictionary_entry(word):
    """Update dictionary entry."""
    data = request.get_json()
    
    if db.update_entry(word, data):
        return jsonify({'message': 'Entry updated'})
    
    return jsonify({'error': 'Entry not found'}), 404

@app.route('/api/dictionary/entry/<word>', methods=['DELETE'])
@admin_required
def delete_dictionary_entry(word):
    """Delete dictionary entry (admin only)."""
    if db.delete_entry(word):
        return jsonify({'message': 'Entry deleted'})
    
    return jsonify({'error': 'Entry not found'}), 404
```

### Translation Endpoints

```python
from src.translation.helsinki_translator_v2 import HelsinkiChuukeseTranslator

# Lazy load translator
_translator = None

def get_translator():
    global _translator
    if _translator is None:
        _translator = HelsinkiChuukeseTranslator()
        _translator.setup_models()
    return _translator

@app.route('/api/translate', methods=['POST'])
def translate_text():
    """Translate text between Chuukese and English."""
    data = request.get_json()
    
    text = data.get('text', '').strip()
    direction = data.get('direction', 'chk_to_en')
    
    if not text:
        return jsonify({'error': 'No text provided'}), 400
    
    if direction not in ['chk_to_en', 'en_to_chk']:
        return jsonify({'error': 'Invalid direction'}), 400
    
    try:
        translator = get_translator()
        translated = translator.translate(text, direction)
        
        return jsonify({
            'original': text,
            'translated': translated,
            'direction': direction,
            'model_used': 'helsinki-nlp-finetuned'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/translate/batch', methods=['POST'])
def translate_batch():
    """Translate multiple texts."""
    data = request.get_json()
    
    texts = data.get('texts', [])
    direction = data.get('direction', 'chk_to_en')
    
    if not texts:
        return jsonify({'error': 'No texts provided'}), 400
    
    results = []
    translator = get_translator()
    
    for text in texts:
        try:
            translated = translator.translate(text, direction)
            results.append({
                'original': text,
                'translated': translated,
                'success': True
            })
        except Exception as e:
            results.append({
                'original': text,
                'error': str(e),
                'success': False
            })
    
    return jsonify({'results': results})
```

### File Upload Handling

```python
from werkzeug.utils import secure_filename
from flask import send_from_directory

ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'gif', 'docx'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/api/upload', methods=['POST'])
@login_required
def upload_file():
    """Upload document for OCR processing."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'error': 'File type not allowed'}), 400
    
    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    
    # Create upload directory if needed
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    
    file.save(filepath)
    
    return jsonify({
        'message': 'File uploaded',
        'filename': filename,
        'filepath': filepath
    }), 201

@app.route('/uploads/<filename>')
def serve_upload(filename):
    """Serve uploaded file."""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)
```

### Database Statistics

```python
@app.route('/api/database/stats')
def get_database_stats():
    """Get database statistics."""
    try:
        stats = db.get_statistics()
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/database/distinct/<field>')
def get_distinct_values(field):
    """Get distinct values for a field."""
    allowed_fields = ['part_of_speech', 'grammar_type', 'source']
    
    if field not in allowed_fields:
        return jsonify({'error': 'Field not allowed'}), 400
    
    try:
        values = db.get_distinct_values(field)
        return jsonify({'field': field, 'values': values})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
```

## Error Handling

```python
from flask import jsonify
from werkzeug.exceptions import HTTPException

@app.errorhandler(Exception)
def handle_exception(e):
    """Global exception handler."""
    # Pass through HTTP errors
    if isinstance(e, HTTPException):
        return jsonify({'error': e.description}), e.code
    
    # Log unexpected errors
    app.logger.error(f'Unhandled exception: {str(e)}')
    
    # Return generic error in production
    if os.getenv('FLASK_ENV') == 'production':
        return jsonify({'error': 'Internal server error'}), 500
    
    # Return detailed error in development
    return jsonify({'error': str(e)}), 500

@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Resource not found'}), 404

@app.errorhandler(400)
def bad_request(e):
    return jsonify({'error': 'Bad request'}), 400

@app.errorhandler(401)
def unauthorized(e):
    return jsonify({'error': 'Authentication required'}), 401

@app.errorhandler(403)
def forbidden(e):
    return jsonify({'error': 'Access denied'}), 403
```

## CORS Configuration

```python
from flask_cors import CORS

# Development CORS - allow React dev server
if os.getenv('FLASK_ENV') != 'production':
    CORS(app, origins=['http://localhost:5173'], supports_credentials=True)
else:
    # Production - restrict to known domains
    CORS(app, origins=['https://your-domain.com'], supports_credentials=True)
```

## Production Deployment

### Gunicorn Configuration

```python
# gunicorn.conf.py
bind = "0.0.0.0:8000"
workers = 2
worker_class = "sync"
timeout = 300
accesslog = "-"
errorlog = "-"
capture_output = True
```

### Running in Production

```bash
# With Gunicorn
gunicorn --bind 0.0.0.0:8000 --workers 2 --timeout 300 app:app

# With uWSGI
uwsgi --http :8000 --wsgi-file app.py --callable app --processes 2
```

## Best Practices

### Security

1. **Always validate input**: Never trust client data
2. **Use HTTPS in production**: Enable secure cookies
3. **Rate limiting**: Prevent abuse of expensive endpoints
4. **Sanitize file uploads**: Validate file types and sizes
5. **Don't expose stack traces**: Return generic errors in production

### Performance

1. **Lazy load resources**: Initialize expensive objects on first use
2. **Connection pooling**: Reuse database connections
3. **Caching**: Cache expensive computations
4. **Pagination**: Limit response sizes

### Code Organization

1. **Use blueprints**: Split routes into logical modules
2. **Dependency injection**: Pass dependencies explicitly
3. **Configuration management**: Use environment variables
4. **Logging**: Log important events and errors

## Dependencies

- `Flask==3.0.0`: Web framework
- `Werkzeug==3.0.1`: WSGI utilities
- `flask-cors==4.0.0`: CORS support
- `gunicorn==21.2.0`: Production server
- `python-dotenv==1.0.0`: Environment variables
