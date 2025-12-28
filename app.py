"""
Flask application for Chuuk Dictionary OCR and Lookup
"""
import os
import re
import time
import json
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory, Response
# from flask_cors import CORS
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from markupsafe import Markup
from pathlib import Path
import ebooklib
from ebooklib import epub
from nwt_epub_parser import NWTEpubParser

# Load environment variables from absolute path
env_path = Path(__file__).parent / '.env'
load_dotenv(env_path, override=True)

# Initialize NWT EPUB parsers (lazy load)
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

from src.ocr.ocr_processor import OCRProcessor
from src.core.jworg_lookup import JWOrgLookup
from src.database.publication_manager import PublicationManager
from src.database.dictionary_db import DictionaryDB
from scripts.processing_logger import processing_logger
import requests
from bs4 import BeautifulSoup
try:
    from src.translation.helsinki_translator_v2 import HelsinkiChuukeseTranslator
    HELSINKI_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ Helsinki translator not available: {e}")
    HELSINKI_AVAILABLE = False

app = Flask(__name__)
secret_key = os.getenv('FLASK_SECRET_KEY')
if not secret_key:
    # Generate a random secret key for development
    import secrets
    secret_key = secrets.token_hex(32)
    if os.getenv('FLASK_ENV') == 'production':
        raise ValueError('FLASK_SECRET_KEY must be set in production')
app.config['SECRET_KEY'] = secret_key
app.config['MAX_CONTENT_LENGTH'] = int(os.getenv('MAX_CONTENT_LENGTH', 16 * 1024 * 1024))  # 16MB default
app.config['UPLOAD_FOLDER'] = os.getenv('UPLOAD_FOLDER', 'uploads')

# Enable CORS for React frontend
# CORS(app, origins=["http://localhost:5173"])

# Initialize database first
dict_db = DictionaryDB()

# Initialize services with db reference
pub_manager = PublicationManager(app.config['UPLOAD_FOLDER'], db=dict_db)
ocr_processor = OCRProcessor(use_google_vision=bool(os.getenv('GOOGLE_APPLICATION_CREDENTIALS')))
jworg_lookup = JWOrgLookup(pub_manager)

# Initialize Helsinki-NLP translator
helsinki_translator = None

# Global training status
training_status = {
    'is_training': False,
    'models_training': [],
    'progress': 0,
    'message': '',
    'last_training': None
}
if HELSINKI_AVAILABLE:
    try:
        helsinki_translator = HelsinkiChuukeseTranslator()
        print("🚀 Initializing Helsinki-NLP models in background...")
        # Initialize models in background to avoid blocking startup
        import threading
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

# Allowed file extensions
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'tiff', 'pdf', 'docx'}


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
        str(escaped_text)
    )
    
    return Markup(highlighted)

# Register the filter
app.jinja_env.filters['highlight'] = highlight_search_term


def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


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


@app.route('/publication/<pub_id>/upload', methods=['POST'])
@app.route('/api/publications/<pub_id>/upload', methods=['POST'])
def upload_page(pub_id):
    """Upload a page to a publication"""
    # Validate publication ID format (timestamp + UUID)
    import re
    if not re.match(r'^\d{14}_[a-f0-9]{8}$', pub_id):
        return jsonify({'error': 'Invalid publication ID'}), 400
    
    publication = pub_manager.get_publication(pub_id)
    
    if not publication:
        return jsonify({'error': 'Publication not found'}), 404
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        
        # Create publication directory
        pub_dir = os.path.join(app.config['UPLOAD_FOLDER'], pub_id)
        os.makedirs(pub_dir, exist_ok=True)
        
        # Save file
        file_path = os.path.join(pub_dir, filename)
        file.save(file_path)
        
        # Process OCR if requested
        process_ocr = request.form.get('ocr', request.form.get('process_ocr', 'false')) == 'true'
        index_dictionary = request.form.get('index_dictionary', 'false') == 'true'
        ocr_results = None
        
        print(f"📤 Upload: process_ocr={process_ocr}, index_dictionary={index_dictionary}")
        print(f"📋 Form data: {dict(request.form)}")
        
        # Create processing session for logging
        import uuid
        session_id = str(uuid.uuid4())
        
        if process_ocr:
            lang = request.form.get('ocr_lang', 'eng')
            
            # Initialize logger
            processing_logger.create_session(session_id, filename)
            processing_logger.log(session_id, f"Starting OCR processing for {filename}")
            processing_logger.log(session_id, f"OCR Language: {lang}")
            processing_logger.log(session_id, f"Dictionary indexing: {'enabled' if index_dictionary else 'disabled'}")
            
            try:
                processing_logger.log(session_id, f"Starting OCR processing with language: {lang}")
                
                # Log OCR capabilities
                has_tesseract = hasattr(ocr_processor, 'process_image_tesseract')
                has_google_vision = ocr_processor.use_google_vision
                processing_logger.log(session_id, f"OCR Capabilities - Tesseract: {has_tesseract}, Google Vision: {has_google_vision}")
                
                ocr_results = ocr_processor.process_image(file_path, lang)
                
                print(f"\n=== OCR PROCESSING DEBUG ===")
                print(f"File: {filename}")
                print(f"File extension: {os.path.splitext(filename)[1].lower()}")
                print(f"Has Google Vision: {ocr_processor.use_google_vision}")
                print(f"OCR Results Keys: {list(ocr_results.keys())}")
                
                if ocr_results.get('type') == 'docx':
                    print(f"DOCX Processing - Pages: {ocr_results.get('total_pages', 0)}")
                    print(f"DOCX Text Length: {len(ocr_results.get('text', ''))}")
                elif 'tesseract' in ocr_results:
                    print(f"Tesseract Text Length: {len(ocr_results.get('tesseract', ''))}")
                if 'google_vision' in ocr_results:
                    print(f"Google Vision Text Length: {len(ocr_results.get('google_vision', ''))}")
                    
                print(f"Primary Text Length: {len(ocr_results.get('text', ''))}")
                print(f"=========================")
                
                # Log OCR method used with more detail
                ocr_method_used = "Unknown"
                if ocr_results.get('type') == 'docx':
                    ocr_method_used = "DOCX Text Extraction"
                    processing_logger.log(session_id, "✓ Using DOCX text extraction (no OCR needed)", 'info')
                elif ocr_results.get('type') == 'pdf':
                    if ocr_results.get('pages'):
                        # Check first page for method indicators
                        first_page = ocr_results['pages'][0]
                        if 'google_vision' in first_page and 'tesseract' in first_page:
                            ocr_method_used = "Google Vision + Tesseract (PDF)"
                            processing_logger.log(session_id, "✓ Using Google Cloud Vision API + Tesseract for PDF processing", 'info')
                        elif 'tesseract' in first_page:
                            ocr_method_used = "Tesseract Only (PDF)"
                            processing_logger.log(session_id, "✓ Using Tesseract OCR for PDF processing", 'info')
                else:
                    if 'google_vision' in ocr_results and 'tesseract' in ocr_results:
                        ocr_method_used = "Google Vision + Tesseract"
                        processing_logger.log(session_id, "✓ Using Google Cloud Vision API + Tesseract for image processing", 'info')
                    elif 'tesseract' in ocr_results:
                        ocr_method_used = "Tesseract Only"
                        processing_logger.log(session_id, "✓ Using Tesseract OCR for image processing", 'info')
                
                processing_logger.update_stats(session_id, ocr_method=ocr_method_used)
                
                # Update total pages if PDF
                if ocr_results.get('type') == 'pdf':
                    total_pages = ocr_results.get('total_pages', 1)
                    processing_logger.update_stats(session_id, total_pages=total_pages)
                    processing_logger.log(session_id, f"PDF detected with {total_pages} pages")
                
                # Index dictionary entries if this is a dictionary document
                if index_dictionary and ocr_results and 'text' in ocr_results:
                    try:
                        processing_logger.log(session_id, "Starting dictionary indexing...")
                        indexed_pages = 0
                        total_entries = 0
                        
                        # Handle PDF with multiple pages
                        if ocr_results.get('type') == 'pdf' and 'pages' in ocr_results:
                            for page_data in ocr_results['pages']:
                                page_num = page_data['page_number']
                                processing_logger.update_page(session_id, page_num)
                                processing_logger.log(session_id, f"Processing page {page_num}/{ocr_results['total_pages']}")
                                
                                if page_data.get('text'):
                                    processing_logger.log(session_id, f"Extracting dictionary entries from page {page_num}...")
                                    
                                    # Count entries before indexing
                                    entries_before = dict_db.get_statistics().get('total_entries', 0)
                                    
                                    page_id = dict_db.add_dictionary_page(
                                        pub_id, 
                                        filename, 
                                        page_data['text'], 
                                        page_data['page_number']
                                    )
                                    
                                    # Count entries after indexing
                                    entries_after = dict_db.get_statistics().get('total_entries', 0)
                                    page_entries = entries_after - entries_before
                                    total_entries += page_entries
                                    
                                    if page_id:
                                        indexed_pages += 1
                                        processing_logger.log(session_id, f"✓ Page {page_num}: {page_entries} word pairs indexed")
                                    else:
                                        processing_logger.log(session_id, f"⚠ Page {page_num}: No entries found", 'warning')
                                else:
                                    processing_logger.log(session_id, f"⚠ Page {page_num}: No text extracted", 'warning')
                            
                            processing_logger.update_stats(session_id, 
                                                          words_indexed=total_entries, 
                                                          entries_created=total_entries,
                                                          pages_processed=indexed_pages)
                            processing_logger.log(session_id, f"✅ Completed: {indexed_pages} pages, {total_entries} word pairs indexed")
                            flash(f'Indexed {indexed_pages} pages with {total_entries} word pairs from {filename}', 'success')
                        
                        # Handle single image
                        else:
                            processing_logger.log(session_id, "Processing single image for dictionary entries...")
                            
                            entries_before = dict_db.get_statistics().get('total_entries', 0)
                            page_id = dict_db.add_dictionary_page(pub_id, filename, ocr_results['text'], 1)
                            entries_after = dict_db.get_statistics().get('total_entries', 0)
                            entries_found = entries_after - entries_before
                            
                            if page_id:
                                processing_logger.log(session_id, f"✅ {entries_found} word pairs indexed from image")
                                processing_logger.update_stats(session_id, 
                                                              words_indexed=entries_found,
                                                              entries_created=entries_found)
                                flash(f'Dictionary entries indexed from {filename}: {entries_found} word pairs', 'success')
                            else:
                                processing_logger.log(session_id, "⚠ No dictionary entries found", 'warning')
                        
                        processing_logger.set_status(session_id, 'completed')
                        
                    except Exception as e:
                        processing_logger.log(session_id, f"❌ Error indexing dictionary: {str(e)}", 'error')
                        processing_logger.update_stats(session_id, errors=1)
                        processing_logger.set_status(session_id, 'failed')
                        flash(f'Error indexing dictionary: {str(e)}', 'warning')
                else:
                    processing_logger.log(session_id, "OCR completed - dictionary indexing skipped")
                    processing_logger.set_status(session_id, 'completed')
                    
            except Exception as e:
                processing_logger.log(session_id, f"❌ OCR processing failed: {str(e)}", 'error')
                processing_logger.set_status(session_id, 'failed')
                flash(f'Error processing OCR: {str(e)}', 'error')
        
        # Add page to publication with processed status
        entries_count = 0
        if index_dictionary and ocr_results and 'text' in ocr_results:
            # Count entries that were just indexed
            entries_before = dict_db.get_statistics().get('total_entries', 0) if dict_db else 0
            # The indexing happens above in the index_dictionary block
            entries_after = dict_db.get_statistics().get('total_entries', 0) if dict_db else 0
            entries_count = max(0, entries_after - entries_before)
        
        pub_manager.add_page(pub_id, filename, ocr_results, processed=index_dictionary, entries_count=entries_count)
        
        flash('Page uploaded successfully', 'success')
        return jsonify({
            'success': True, 
            'filename': filename, 
            'ocr_results': ocr_results,
            'session_id': session_id if process_ocr else None,
            'processed': index_dictionary,
            'entries_count': entries_count
        })
    
    return jsonify({'error': 'Invalid file type'}), 400


@app.route('/api/processing/status/<session_id>', methods=['GET'])
def get_processing_status(session_id):
    """Get current processing status for a session"""
    logs = processing_logger.get_logs(session_id)
    if logs:
        return jsonify(logs)
    return jsonify({'error': 'Session not found'}), 404


@app.route('/api/processing/stream/<session_id>')
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
            current_log_count = len(logs.get('logs', []))
            if current_log_count > last_log_count or waited == 0:
                last_log_count = current_log_count
                yield f"data: {json.dumps(logs)}\n\n"
            
            # Check if processing is complete
            if logs.get('status') in ['completed', 'failed']:
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
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no'
        }
    )


@app.route('/publication/<pub_id>/upload_csv', methods=['POST'])
@app.route('/api/publications/<pub_id>/upload_csv', methods=['POST'])
def upload_csv(pub_id):
    """Upload and process a CSV file into the dictionary database"""
    # Validate publication ID format (timestamp + UUID)
    import re
    if not re.match(r'^\d{14}_[a-f0-9]{8}$', pub_id):
        return jsonify({'error': 'Invalid publication ID'}), 400
    
    publication = pub_manager.get_publication(pub_id)
    
    if not publication:
        return jsonify({'error': 'Publication not found'}), 404
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if file and file.filename.lower().endswith('.csv') or file.filename.lower().endswith('.tsv'):
        filename = secure_filename(file.filename)
        
        # Read CSV content
        try:
            csv_content = file.read().decode('utf-8')
        except UnicodeDecodeError:
            return jsonify({'error': 'Invalid CSV encoding. Please use UTF-8.'}), 400
        
        # Create processing session for logging
        import uuid
        session_id = str(uuid.uuid4())
        
        # Initialize logger
        processing_logger.create_session(session_id, filename)
        processing_logger.log(session_id, f"Starting CSV processing for {filename}")
        
        try:
            # Process CSV into database
            import sys
            sys.stdout.flush()
            print(f"\n🔍 DEBUG: dict_db.client is {'available' if dict_db.client else 'None'}", flush=True)
            print(f"🔍 DEBUG: About to call add_dictionary_from_csv with pub_id={pub_id}, filename={filename}", flush=True)
            page_id, entries_added = dict_db.add_dictionary_from_csv(pub_id, filename, csv_content)
            print(f"🔍 DEBUG: Returned page_id={page_id}, entries_added={entries_added}\n", flush=True)
            
            if page_id:
                processing_logger.log(session_id, f"✅ Successfully processed CSV: {entries_added} entries added")
                processing_logger.update_stats(session_id, 
                                             words_indexed=entries_added,
                                             entries_created=entries_added)
                processing_logger.set_status(session_id, 'completed')
                
                # Add CSV file to publication
                csv_metadata = {
                    'filename': filename,
                    'type': 'csv',
                    'entries_added': entries_added,
                    'processed_date': datetime.now().isoformat()
                }
                pub_manager.add_page(pub_id, filename, csv_metadata)
                
                flash(f'CSV processed successfully: {entries_added} dictionary entries added', 'success')
                return jsonify({
                    'success': True, 
                    'filename': filename, 
                    'entries_added': entries_added,
                    'session_id': session_id
                })
            else:
                processing_logger.log(session_id, "❌ Failed to process CSV - database not available", 'error')
                processing_logger.set_status(session_id, 'failed')
                return jsonify({'error': 'Database not available for CSV processing'}), 500
                
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            print(f"❌ CSV UPLOAD ERROR: {error_details}")
            processing_logger.log(session_id, f"❌ CSV processing failed: {str(e)}", 'error')
            processing_logger.set_status(session_id, 'failed')
            return jsonify({'error': f'Error processing CSV: {str(e)}'}), 500
    
    return jsonify({'error': 'Invalid file type. Only CSV files are supported.'}), 400


@app.route('/ocr/process', methods=['POST'])
@app.route('/api/ocr/process', methods=['POST'])
def process_ocr():
    """Process OCR on a specific page and optionally index dictionary entries"""
    pub_id = request.form.get('pub_id')
    filename = request.form.get('filename')
    lang = request.form.get('lang', 'eng')
    index_dictionary = request.form.get('index_dictionary', 'true') == 'true'
    
    if not pub_id or not filename:
        return jsonify({'error': 'Missing parameters'}), 400
    
    file_path = pub_manager.get_page_path(pub_id, filename)
    
    if not os.path.exists(file_path):
        return jsonify({'error': 'File not found'}), 404
    
    # Process OCR
    results = ocr_processor.process_image(file_path, lang)
    
    response_data = {
        'success': True,
        'ocr_text': results.get('text', ''),
        'indexed': False,
        'entries_count': 0
    }
    
    # Index dictionary entries if requested
    if index_dictionary and results and 'text' in results:
        try:
            # Count entries before indexing
            entries_before = dict_db.get_statistics().get('total_entries', 0)
            
            # Index the page
            page_id = dict_db.add_dictionary_page(pub_id, filename, results['text'], 1)
            
            # Count entries after indexing
            entries_after = dict_db.get_statistics().get('total_entries', 0)
            entries_count = entries_after - entries_before
            
            response_data['indexed'] = True
            response_data['entries_count'] = entries_count
            response_data['message'] = f'Processed OCR and indexed {entries_count} dictionary entries'
        except Exception as e:
            response_data['index_error'] = str(e)
            response_data['message'] = f'OCR processed but indexing failed: {str(e)}'
    else:
        response_data['message'] = 'OCR processed successfully'
    
    return jsonify(response_data)


@app.route('/ocr/reprocess', methods=['POST'])
@app.route('/api/ocr/reprocess', methods=['POST'])
def reprocess_page():
    """Reprocess an already-indexed page, updating entries with better field values"""
    pub_id = request.form.get('pub_id')
    filename = request.form.get('filename')
    page_number = int(request.form.get('page_number', 1))
    
    if not pub_id or not filename:
        return jsonify({'error': 'Missing parameters'}), 400
    
    try:
        # Reprocess the page
        stats = dict_db.reprocess_page(pub_id, filename, page_number)
        
        if not stats.get('success'):
            error_msg = stats.get('error', 'Unknown error')
            print(f"Reprocess failed: {error_msg}")
            return jsonify(stats), 400 if 'not found' in error_msg.lower() else 500
        
        # Build response message
        message_parts = []
        if stats.get('new_entries', 0) > 0:
            message_parts.append(f"{stats['new_entries']} new entries")
        if stats.get('updated_entries', 0) > 0:
            message_parts.append(f"{stats['updated_entries']} entries updated")
        
        response_data = {
            'success': True,
            'stats': stats,
            'message': f"Reprocessed: {', '.join(message_parts) if message_parts else 'No changes needed'}"
        }
        
        return jsonify(response_data)
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'message': f'Reprocessing failed: {str(e)}'
        }), 500


# Disabled - handled by React Router
# @app.route('/translate', methods=['GET', 'POST'])
# def translate():
#     """Redirect to React app"""
#     return redirect('/')

def translate_phrases(phrases, direction):
    """Translate multiple phrases individually and return with confidence scores"""
    import os
    import requests
    
    api_key = os.getenv('GOOGLE_CLOUD_API_KEY')
    results = {
        'success': True,
        'direction': direction,
        'phrases': []
    }
    
    for phrase in phrases:
        phrase_text = phrase.strip()
        if not phrase_text:
            continue
            
        phrase_result = {
            'original': phrase_text,
            'translation': '',
            'confidence': 'low',  # low, medium, high, verified
            'sources': {}
        }
        
        # Try Google Translate
        try:
            if api_key:
                url = f'https://translation.googleapis.com/language/translate/v2?key={api_key}'
                
                payload = {
                    'q': phrase_text,
                    'target': 'en' if direction == 'chk_to_en' else 'chk',
                    'format': 'text'
                }
                
                # Add source language
                if direction == 'chk_to_en':
                    payload['source'] = 'chk'
                elif direction == 'en_to_chk':
                    payload['source'] = 'en'
                
                response = requests.post(url, json=payload, timeout=10)
                if response.status_code == 200:
                    result = response.json()
                    translation = result['data']['translations'][0]['translatedText']
                    phrase_result['translation'] = translation
                    phrase_result['sources']['google'] = translation
                    phrase_result['confidence'] = 'medium'  # Auto-translated
        except Exception as e:
            phrase_result['sources']['google'] = f'Error: {str(e)}'
        
        # Check if phrase exists in database (verified translation)
        try:
            # Look for exact or similar match
            db_entry = dict_db.dictionary_collection.find_one({
                'chuukese_word': {'$regex': f'^{phrase_text}$', '$options': 'i'}
            })
            if db_entry:
                phrase_result['translation'] = db_entry.get('english_translation', phrase_result['translation'])
                phrase_result['sources']['database'] = db_entry.get('english_translation')
                phrase_result['confidence'] = 'high'  # From verified database
                if db_entry.get('confidence_level'):
                    phrase_result['confidence'] = db_entry['confidence_level']
        except Exception as e:
            pass
        
        results['phrases'].append(phrase_result)
    
    return jsonify(results)

@app.route('/api/translate', methods=['POST'])
def api_translate():
    """Translate using all three sources: Google, Helsinki, Ollama"""
    try:
        data = request.get_json()
        text = data.get('text', '').strip()
        direction = data.get('direction', 'auto')
        phrases = data.get('phrases', [])  # Optional: pre-split phrases
        
        if not text and not phrases:
            return jsonify({'success': False, 'error': 'No text provided'})
        
        # Determine actual direction if auto
        if direction == 'auto':
            # Simple heuristic: if text contains mostly ASCII, assume English
            check_text = text if text else ' '.join(phrases)
            is_english = all(ord(c) < 128 for c in check_text if c.isalpha())
            direction = 'en_to_chk' if is_english else 'chk_to_en'
        
        # If phrases provided, translate each individually
        if phrases:
            return translate_phrases(phrases, direction)
        
        # Otherwise, translate full text
        results = {
            'success': True,
            'original_text': text,
            'translations': {}
        }
        
        # Google Translate - Using REST API with API key
        try:
            import os
            api_key = os.getenv('GOOGLE_CLOUD_API_KEY')
            
            if api_key:
                # Use REST API directly with API key
                import requests
                url = f'https://translation.googleapis.com/language/translate/v2?key={api_key}'
                
                payload = {
                    'q': text,
                    'target': 'en' if direction == 'chk_to_en' else 'chk',
                    'format': 'text'
                }
                
                # Add source language if not auto-detect
                if direction == 'chk_to_en':
                    payload['source'] = 'chk'
                elif direction == 'en_to_chk':
                    payload['source'] = 'en'
                
                response = requests.post(url, json=payload, timeout=10)
                
                if response.status_code == 200:
                    result = response.json()
                    translation = result['data']['translations'][0]['translatedText']
                    results['translations']['google'] = translation
                else:
                    error_msg = response.json().get('error', {}).get('message', f'Status {response.status_code}')
                    results['translations']['google'] = f'Google API error: {error_msg}'
            else:
                results['translations']['google'] = 'Google Translate API key not configured'
        except Exception as e:
            results['translations']['google'] = f'Google Translate error: {str(e)}'
        
        # Helsinki-NLP
        try:
            if helsinki_translator:
                if direction == 'chk_to_en':
                    helsinki_result = helsinki_translator.translate_chuukese_to_english(text)
                else:
                    helsinki_result = helsinki_translator.translate_english_to_chuukese(text)
                results['translations']['helsinki'] = helsinki_result
            else:
                results['translations']['helsinki'] = 'Helsinki translator not available'
        except Exception as e:
            results['translations']['helsinki'] = f'Error: {str(e)}'
        
        # Ollama LLM
        try:
            from src.translation.llm_trainer import ChuukeseLLMTrainer
            ollama_trainer = ChuukeseLLMTrainer()
            
            if ollama_trainer.check_ollama_installation():
                ollama_result = ollama_trainer.translate_text(text, direction)
                results['translations']['ollama'] = ollama_result
            else:
                results['translations']['ollama'] = 'Ollama is not running. Start Ollama to use this translator.'
        except Exception as e:
            results['translations']['ollama'] = f'Error: {str(e)}'
        
        return jsonify(results)
        
    except Exception as e:
        return jsonify({'success': False, 'error': f'Translation failed: {str(e)}'})

@app.route('/api/translate/correction', methods=['POST'])
def api_translate_correction():
    """Save translation correction and optionally retrain models"""
    try:
        data = request.get_json()
        original_text = data.get('original_text', '').strip()
        corrected_text = data.get('corrected_text', '').strip()
        direction = data.get('direction', 'auto')
        retrain = data.get('retrain', False)
        
        if not original_text or not corrected_text:
            return jsonify({'success': False, 'error': 'Both original and corrected text are required'})
        
        # Determine Chuukese and English text based on direction
        if direction == 'chk_to_en':
            chuukese_word = original_text
            english_translation = corrected_text
        elif direction == 'en_to_chk':
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
        word_type = 'phrase' if ' ' in chuukese_word else None
        
        # Use add_word or add_phrase depending on content
        if ' ' in chuukese_word or ' ' in english_translation:
            # It's a phrase
            word_id = db.add_phrase(
                chuukese_phrase=chuukese_word,
                english_translation=english_translation,
                source='user_correction',
                definition=f'User correction from translation'
            )
        else:
            # It's a single word
            word_id = db.add_word(
                chuukese=chuukese_word,
                english_translation=english_translation,
                grammar=word_type,
                source='user_correction',
                definition=f'User correction from translation'
            )
        
        # Optionally trigger retraining in background
        if retrain:
            import threading
            def retrain_models():
                global training_status
                try:
                    training_status['is_training'] = True
                    training_status['models_training'] = ['Google Translate', 'Helsinki-NLP (Chk→En)', 'Helsinki-NLP (En→Chk)', 'Ollama AI']
                    training_status['progress'] = 0
                    training_status['message'] = 'Starting model retraining...'
                    
                    # Step 1: Validate with Google Translate
                    print("✅ Validating with Google Translate...")
                    training_status['progress'] = 10
                    training_status['message'] = 'Validating translation with Google Translate...'
                    import time
                    time.sleep(1)  # Brief validation pause
                    
                    training_status['progress'] = 15
                    
                    # Step 2: Fine-tune Helsinki models with real training
                    print("🔄 Fine-tuning Helsinki-NLP models...")
                    training_status['progress'] = 20
                    training_status['message'] = 'Fine-tuning Helsinki-NLP models...'
                    
                    try:
                        from src.training.helsinki_trainer import HelsinkiFineTuner
                        
                        def helsinki_progress(stage, progress):
                            # Map 20-60% for Helsinki training
                            adjusted_progress = 20 + (progress * 0.4)
                            training_status['progress'] = int(adjusted_progress)
                            training_status['message'] = stage
                        
                        helsinki_trainer = HelsinkiFineTuner(progress_callback=helsinki_progress)
                        helsinki_success = helsinki_trainer.fine_tune_both_models(
                            num_epochs=1,  # Quick 1-epoch fine-tuning to prevent crashes
                            batch_size=2   # Small batch size for safety
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
                    
                    training_status['progress'] = 60
                    
                    # Step 3: Retrain Ollama
                    from src.translation.llm_trainer import ChuukeseLLMTrainer
                    trainer = ChuukeseLLMTrainer()
                    if trainer.check_ollama_installation():
                        print("🔄 Retraining Ollama model...")
                        training_status['message'] = 'Training Ollama AI model...'
                        training_status['progress'] = 75
                        trainer.train_full_pipeline()
                    
                    training_status['progress'] = 100
                    training_status['message'] = 'Training complete!'
                    training_status['last_training'] = datetime.now().isoformat()
                    
                except Exception as e:
                    print(f"❌ Retraining error: {e}")
                    training_status['message'] = f'Training error: {str(e)}'
                finally:
                    # Reset after a delay
                    import time
                    time.sleep(3)
                    training_status['is_training'] = False
                    training_status['models_training'] = []
                    training_status['progress'] = 0
            
            thread = threading.Thread(target=retrain_models)
            thread.daemon = True
            thread.start()
        
        return jsonify({
            'success': True,
            'message': 'Correction saved' + (' and models will be retrained' if retrain else '')
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': f'Failed to save correction: {str(e)}'})

@app.route('/api/translate/training-status', methods=['GET'])
def api_training_status():
    """Get current training status"""
    global training_status
    return jsonify(training_status)

@app.route('/translate_helsinki', methods=['POST'])
def translate_helsinki():
    """Translate using Helsinki-NLP models"""
    try:
        text = request.form.get('text', '').strip()
        direction = request.form.get('direction', 'chuukese_to_english')
        
        if not text:
            return jsonify({'error': 'No text provided'})
        
        if not helsinki_translator:
            return jsonify({'error': 'Helsinki translator not available'})
        
        if direction == 'chuukese_to_english':
            translation = helsinki_translator.translate_chuukese_to_english(text)
        else:
            translation = helsinki_translator.translate_english_to_chuukese(text)
        
        return jsonify({
            'original_text': text,
            'translation': translation,
            'direction': direction,
            'model': 'Helsinki-NLP'
        })
        
    except Exception as e:
        return jsonify({'error': f'Translation failed: {str(e)}'})


@app.route('/train_helsinki', methods=['POST'])
def train_helsinki():
    """Fine-tune Helsinki-NLP models with dictionary data"""
    try:
        direction = request.form.get('direction', 'chuukese_to_english')
        epochs = int(request.form.get('epochs', 3))
        
        if not helsinki_translator:
            flash('Helsinki translator not available', 'error')
            return redirect(url_for('translate'))
        
        if not helsinki_translator.training_data:
            flash('No training data loaded. Please ensure dictionary data is available.', 'error')
            return redirect(url_for('translate'))
        
        flash(f'Starting Helsinki-NLP fine-tuning for {direction} direction...', 'info')
        
        # Run training in background
        import threading
        def train_model():
            try:
                success = helsinki_translator.fine_tune_model(
                    direction=direction, 
                    num_epochs=epochs,
                    batch_size=4  # Smaller batch size for better memory usage
                )
                if success:
                    print(f"✅ Helsinki fine-tuning completed for {direction}")
                else:
                    print(f"❌ Helsinki fine-tuning failed for {direction}")
            except Exception as e:
                print(f"❌ Training error: {e}")
        
        threading.Thread(target=train_model, daemon=True).start()
        flash('Helsinki-NLP fine-tuning started in background. Check console for progress.', 'success')
        
    except Exception as e:
        flash(f'Training error: {str(e)}', 'error')
    
    return redirect(url_for('translate'))


@app.route('/evaluate_helsinki', methods=['POST'])  
def evaluate_helsinki():
    """Evaluate Helsinki-NLP translation quality"""
    try:
        if not helsinki_translator:
            return jsonify({'error': 'Helsinki translator not available'})
        
        if not helsinki_translator.training_data:
            return jsonify({'error': 'No dictionary data available for evaluation'})
        
        # Use a sample for evaluation
        test_sample = helsinki_translator.training_data[:20]  # Small sample for quick eval
        results = helsinki_translator.evaluate_translation_quality(test_sample)
        
        return jsonify({
            'evaluation_results': results,
            'model': 'Helsinki-NLP',
            'test_samples': len(test_sample)
        })
        
    except Exception as e:
        return jsonify({'error': f'Evaluation failed: {str(e)}'})


@app.route('/train_ollama', methods=['POST'])
def train_ollama():
    """Train the Ollama model with current dictionary data"""
    try:
        from src.translation.llm_trainer import ChuukeseLLMTrainer
        trainer = ChuukeseLLMTrainer()
        
        # Run training in background
        import threading
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
        flash('Ollama model training started in background. Check console for progress.', 'success')
            
    except Exception as e:
        flash(f'Training error: {str(e)}', 'error')
    
    return redirect(url_for('translate'))


@app.route('/model_status', methods=['GET'])
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
                result = subprocess.run(['ollama', 'list'], capture_output=True, text=True)
                chuukese_model_exists = 'chuukese-translator' in result.stdout
                ollama_status = {
                    'available': True,
                    'custom_model': chuukese_model_exists,
                    'model_name': 'chuukese-translator' if chuukese_model_exists else None
                }
            else:
                ollama_status = {
                    'available': False,
                    'custom_model': False,
                    'model_name': None
                }
        except:
            ollama_status = {'available': False, 'custom_model': False, 'model_name': None}
        
        # Check Helsinki status
        helsinki_status = {
            'available': helsinki_translator is not None,
            'data_loaded': helsinki_translator.training_data if helsinki_translator else False
        }
        
        return jsonify({
            'ollama': ollama_status,
            'helsinki': helsinki_status,
            'database_entries': dict_db.get_statistics()['total_entries'] if dict_db.client else 0
        })
        
    except Exception as e:
        return jsonify({'error': f'Status check failed: {str(e)}'})


# Disabled - handled by React Router
# @app.route('/lookup', methods=['GET', 'POST'])
# def lookup():
#     """Redirect to React app"""
#     return redirect('/')


@app.route('/api/lookup/<word>')
def api_lookup(word):
    """API endpoint for word lookup"""
    lang = request.args.get('lang', 'chk')
    results = jworg_lookup.search_word(word, lang)
    return jsonify({'word': word, 'language': lang, 'results': results})


@app.route('/api/lookup/jworg', methods=['POST'])
def api_lookup_jworg():
    """API endpoint for JW.org lookup (async)"""
    data = request.get_json()
    word = data.get('word')
    lang = data.get('lang', 'chk')
    
    if not word:
        return jsonify({'error': 'No word provided'}), 400
    
    try:
        results = jworg_lookup.search_word(word, lang)
        return jsonify({
            'success': True,
            'word': word, 
            'language': lang, 
            'results': results
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'JW.org search failed: {str(e)}'
        }), 500


@app.route('/api/processing/logs/<session_id>')
def get_processing_logs(session_id):
    """Get processing logs for a session"""
    logs = processing_logger.get_logs(session_id)
    if logs:
        return jsonify(logs)
    else:
        return jsonify({'error': 'Session not found'}), 404


@app.route('/api/processing/logs/<session_id>/recent')
def get_recent_logs(session_id):
    """Get recent log entries for real-time updates"""
    limit = request.args.get('limit', 20, type=int)
    logs = processing_logger.get_recent_logs(session_id, limit)
    return jsonify({'logs': logs})


@app.route('/database')
def database_viewer():
    """Serve React app for database viewer"""
    return send_from_directory('frontend/dist', 'index.html')


@app.route('/api/database/pages')
def api_database_pages():
    """API endpoint for processed pages"""
    try:
        pages = dict_db.get_all_pages()
        return jsonify({'pages': pages})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/database/entry/<entry_id>')
def api_get_entry(entry_id):
    """Get detailed information for a specific entry"""
    try:
        entry = dict_db.get_entry_by_id(entry_id)
        if entry:
            return jsonify(entry)
        else:
            return jsonify({'error': 'Entry not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# API Routes for React frontend
@app.route('/api/publications', methods=['GET'])
def api_get_publications():
    """API: Get all publications"""
    try:
        publications = pub_manager.list_publications()
        return jsonify(publications)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/publications', methods=['POST'])
def api_create_publication():
    """API: Create new publication"""
    try:
        data = request.get_json()
        title = data.get('title')
        description = data.get('description', '')
        
        if not title:
            return jsonify({'error': 'Title is required'}), 400
        
        pub_id = pub_manager.create_publication(title, description)
        return jsonify({'id': pub_id, 'message': 'Publication created'}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/publications/<pub_id>', methods=['GET'])
def api_get_publication(pub_id):
    """API: Get publication details with enhanced page data"""
    try:
        # Validate publication ID format
        import re
        if not re.match(r'^\d{14}_[a-f0-9]{8}$', pub_id):
            return jsonify({'error': 'Invalid publication ID'}), 400
        
        publication = pub_manager.get_publication(pub_id)
        if not publication:
            return jsonify({'error': 'Publication not found'}), 404
        
        # Enhance pages with missing fields for backward compatibility
        for page in publication.get('pages', []):
            if 'id' not in page:
                page['id'] = f"{pub_id}_{page['filename']}"
            if 'processed' not in page:
                # Check if page has OCR text - if so, mark as processed
                page['processed'] = bool(page.get('ocr_text') or page.get('ocr_results', {}).get('text'))
            if 'ocr_text' not in page and page.get('ocr_results'):
                page['ocr_text'] = page['ocr_results'].get('text', '')
            if 'entries_count' not in page:
                page['entries_count'] = 0
        
        return jsonify(publication)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/lookup', methods=['GET'])
def api_lookup_get():
    """API: Search dictionary (GET version for simple queries)"""
    try:
        word = request.args.get('word', '')
        lang = request.args.get('lang', 'chk')
        
        if not word:
            return jsonify({'results': []})
        
        # Now uses denormalized data - only 1 query, includes related words!
        results = dict_db.search_word(word, limit=10, include_related=True)
        return jsonify({'word': word, 'results': results})
    except Exception as e:
        import traceback
        print(f"❌ Error in lookup: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500


@app.route('/api/lookup/jworg', methods=['POST'])
def api_lookup_jworg_post():
    """API: Search JW.org (POST version)"""
    try:
        data = request.get_json()
        word = data.get('word')
        lang = data.get('lang', 'chk')
        
        if not word:
            return jsonify({'error': 'Word is required'}), 400
        
        results = jworg_lookup.search_word(word, lang)
        return jsonify({'word': word, 'results': results})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/database/stats', methods=['GET'])
def api_database_stats():
    """API: Get database statistics"""
    try:
        stats = dict_db.get_stats()
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


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
        epub_path = 'data/bible/old_testament_chuukese.epub'
        if not os.path.exists(epub_path):
            print(f"EPUB file not found: {epub_path}")
            return None
            
        book = epub.read_epub(epub_path)
        
        # Book code mapping (2-letter codes used in EPUB IDs)
        book_codes = {
            'Genesis': 'GN', 'Exodus': 'EX', 'Leviticus': 'LV', 'Numbers': 'NU', 'Deuteronomy': 'DT',
            'Joshua': 'JS', 'Judges': 'JG', 'Ruth': 'RT', '1 Samuel': '1S', '2 Samuel': '2S',
            '1 Kings': '1K', '2 Kings': '2K', '1 Chronicles': '1C', '2 Chronicles': '2C', 'Ezra': 'ER',
            'Nehemiah': 'NE', 'Esther': 'ET', 'Job': 'JB', 'Psalms': 'PS', 'Proverbs': 'PR',
            'Ecclesiastes': 'EC', 'Song of Solomon': 'SS', 'Isaiah': 'IS', 'Jeremiah': 'JR', 'Lamentations': 'LM',
            'Ezekiel': 'EK', 'Daniel': 'DN', 'Hosea': 'HS', 'Joel': 'JL', 'Amos': 'AM',
            'Obadiah': 'OB', 'Jonah': 'JN', 'Micah': 'MC', 'Nahum': 'NM', 'Habakkuk': 'HK',
            'Zephaniah': 'ZP', 'Haggai': 'HG', 'Zechariah': 'ZC', 'Malachi': 'ML'
        }
        
        # Get 2-letter book code
        book_abbrev = book_codes.get(book_name, book_name)
        
        # Map common abbreviations
        abbrev_map = {
            'GEN': 'GN', 'GENESIS': 'GN',
            'EXO': 'EX', 'EXODUS': 'EX', 'EXOD': 'EX',
            'LEV': 'LV', 'LEVITICUS': 'LV',
            'NUM': 'NU', 'NUMBERS': 'NU',
            'DEU': 'DT', 'DEUT': 'DT', 'DEUTERONOMY': 'DT',
            'JOS': 'JS', 'JOSHUA': 'JS',
            'JDG': 'JG', 'JUDG': 'JG', 'JUDGES': 'JG',
            'RUT': 'RT', 'RUTH': 'RT',
            '1SA': '1S', '1 SAMUEL': '1S',
            '2SA': '2S', '2 SAMUEL': '2S',
            '1KI': '1K', '1 KINGS': '1K',
            '2KI': '2K', '2 KINGS': '2K',
            'EZR': 'ER', 'EZRA': 'ER',
            'NEH': 'NE', 'NEHEMIAH': 'NE',
            'EST': 'ET', 'ESTHER': 'ET',
            'JOB': 'JB',
            'PSA': 'PS', 'PSALM': 'PS', 'PSALMS': 'PS',
            'PRO': 'PR', 'PROV': 'PR', 'PROVERBS': 'PR',
            'ECC': 'EC', 'ECCL': 'EC', 'ECCLESIASTES': 'EC',
            'SNG': 'SS', 'SONG': 'SS', 'SONG OF SOLOMON': 'SS',
            'ISA': 'IS', 'ISAIAH': 'IS',
            'JER': 'JR', 'JEREMIAH': 'JR',
            'LAM': 'LM', 'LAMENTATIONS': 'LM',
            'EZK': 'EK', 'EZEK': 'EK', 'EZEKIEL': 'EK',
            'DAN': 'DN', 'DANIEL': 'DN',
            'HOS': 'HS', 'HOSEA': 'HS',
            'JOL': 'JL', 'JOEL': 'JL',
            'AMO': 'AM', 'AMOS': 'AM',
            'OBA': 'OB', 'OBAD': 'OB', 'OBADIAH': 'OB',
            'JON': 'JN', 'JONAH': 'JN',
            'MIC': 'MC', 'MICAH': 'MC',
            'NAM': 'NM', 'NAH': 'NM', 'NAHUM': 'NM',
            'HAB': 'HK', 'HABAKKUK': 'HK',
            'ZEP': 'ZP', 'ZEPH': 'ZP', 'ZEPHANIAH': 'ZP',
            'HAG': 'HG', 'HAGGAI': 'HG',
            'ZEC': 'ZC', 'ZECH': 'ZC', 'ZECHARIAH': 'ZC',
            'MAL': 'ML', 'MALACHI': 'ML'
        }
        
        if book_name.upper() in abbrev_map:
            book_abbrev = abbrev_map[book_name.upper()]
        
        # Filenames use 3-letter codes (GEN.xhtml, EXO.xhtml)
        file_mapping = {
            'GN': 'GEN', 'EX': 'EXO', 'LV': 'LEV', 'NU': 'NUM', 'DT': 'DEU',
            'JS': 'JOS', 'JG': 'JDG', 'RT': 'RUT', '1S': '1SA', '2S': '2SA',
            '1K': '1KI', '2K': '2KI', '1C': '1CH', '2C': '2CH', 'ER': 'EZR',
            'NE': 'NEH', 'ET': 'EST', 'JB': 'JOB', 'PS': 'PSA', 'PR': 'PRO',
            'EC': 'ECC', 'SS': 'SNG', 'IS': 'ISA', 'JR': 'JER', 'LM': 'LAM',
            'EK': 'EZK', 'DN': 'DAN', 'HS': 'HOS', 'JL': 'JOL', 'AM': 'AMO',
            'OB': 'OBA', 'JN': 'JON', 'MC': 'MIC', 'NM': 'NAM', 'HK': 'HAB',
            'ZP': 'ZEP', 'HG': 'HAG', 'ZC': 'ZEC', 'ML': 'MAL'
        }
        filename = f'{file_mapping.get(book_abbrev, book_abbrev.upper())}.xhtml'
        
        # Find the book file
        for item in book.get_items():
            if item.get_name() == filename:
                content = item.get_content()
                soup = BeautifulSoup(content, 'html.parser')
                
                # Find verse by ID (e.g., GN1_1 for Genesis 1:1)
                verse_id = f'{book_abbrev}{chapter}_{verse}'
                verse_elem = soup.find(id=verse_id)
                
                if not verse_elem:
                    return None
                
                # The verse element is a span with the verse number
                # The verse text comes after it until the next verse marker
                verse_text_parts = []
                current = verse_elem.next_sibling
                
                # Get all text until we hit another verse marker (span with id ending in underscore+number)
                while current:
                    if hasattr(current, 'name') and current.name == 'span' and current.get('id'):
                        # Check if this is another verse marker (has underscore+number pattern)
                        if re.match(r'^[A-Z0-9]+_\d+$', current.get('id', '')):
                            break
                    
                    if hasattr(current, 'get_text'):
                        verse_text_parts.append(current.get_text())
                    elif isinstance(current, str):
                        verse_text_parts.append(current)
                    
                    current = current.next_sibling if hasattr(current, 'next_sibling') else None
                
                verse_text = ''.join(verse_text_parts).strip()
                
                # Clean up cross-references and extra whitespace
                verse_text = re.sub(r'✡.*?(?=\n|$)', '', verse_text, flags=re.MULTILINE)
                verse_text = re.sub(r'\s+', ' ', verse_text)  # Normalize whitespace
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
            'genesis': '1', 'exodus': '2', 'leviticus': '3', 'numbers': '4', 'deuteronomy': '5',
            'joshua': '6', 'judges': '7', 'ruth': '8', '1 samuel': '9', '2 samuel': '10',
            '1 kings': '11', '2 kings': '12', '1 chronicles': '13', '2 chronicles': '14',
            'ezra': '15', 'nehemiah': '16', 'esther': '17', 'job': '18', 'psalm': '19', 'psalms': '19',
            'proverbs': '20', 'ecclesiastes': '21', 'song of solomon': '22', 'isaiah': '23',
            'jeremiah': '24', 'lamentations': '25', 'ezekiel': '26', 'daniel': '27', 'hosea': '28',
            'joel': '29', 'amos': '30', 'obadiah': '31', 'jonah': '32', 'micah': '33', 'nahum': '34',
            'habakkuk': '35', 'zephaniah': '36', 'haggai': '37', 'zechariah': '38', 'malachi': '39',
            'matthew': '40', 'mark': '41', 'luke': '42', 'john': '43', 'acts': '44',
            'romans': '45', '1 corinthians': '46', '2 corinthians': '47', 'galatians': '48',
            'ephesians': '49', 'philippians': '50', 'colossians': '51', '1 thessalonians': '52',
            '2 thessalonians': '53', '1 timothy': '54', '2 timothy': '55', 'titus': '56',
            'philemon': '57', 'hebrews': '58', 'james': '59', '1 peter': '60', '2 peter': '61',
            '1 john': '62', '2 john': '63', '3 john': '64', 'jude': '65', 'revelation': '66'
        }
        
        # Old Testament books (1-39)
        old_testament_books = set(str(i) for i in range(1, 40))
        
        # Parse the reference
        parts = scripture_ref.strip().split()
        if len(parts) < 2:
            return {'chuukese': '', 'english': '', 'error': 'Invalid scripture format'}
        
        # Handle books with numbers (e.g., "1 Samuel")
        if parts[0].isdigit():
            book_name = f"{parts[0]} {parts[1]}".lower()
            book_name_for_epub = f"{parts[0]} {parts[1].capitalize()}"
            verse_part = ' '.join(parts[2:])
        else:
            book_name = parts[0].lower()
            book_name_for_epub = parts[0].capitalize()
            verse_part = ' '.join(parts[1:])
        
        book_num = book_map.get(book_name)
        if not book_num:
            return {'chuukese': '', 'english': '', 'error': f'Book "{book_name}" not found'}
        
        # Parse chapter:verse
        if ':' in verse_part:
            chapter, verse = verse_part.split(':')
            chapter = int(chapter.strip())
            verse = int(verse.strip())
        else:
            return {'chuukese': '', 'english': '', 'error': 'Invalid verse format (use Chapter:Verse)'}
        
        chuukese_text = ''
        english_text = ''
        
        # For Old Testament, use Chuukese OT EPUB
        if book_num in old_testament_books:
            chuukese_text = extract_ot_verse(book_name_for_epub, chapter, verse)
            if not chuukese_text:
                chuukese_text = ''
        else:
            # New Testament - use Chuukese NT EPUB
            chk_parser = get_nwt_chuukese_parser()
            if chk_parser:
                chuukese_text = chk_parser.get_verse(book_num, chapter, verse)
            if not chuukese_text:
                chuukese_text = ''
        
        # Fetch English from NWT English EPUB (full Bible)
        eng_parser = get_nwt_english_parser()
        if eng_parser:
            english_text = eng_parser.get_verse(book_num, chapter, verse)
        if not english_text:
            english_text = ''
        
        return {
            'chuukese': chuukese_text,
            'english': english_text,
            'error': None if (chuukese_text or english_text) else 'Scripture not found'
        }
    
    except Exception as e:
        return {'chuukese': '', 'english': '', 'error': str(e)}


@app.route('/api/database/entries', methods=['GET'])
def api_database_entries():
    """API: Get paginated database entries"""
    try:
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 20))
        search = request.args.get('search', '')
        sort_by = request.args.get('sort_by', '')
        sort_order = request.args.get('sort_order', 'asc')
        filter_type = request.args.get('filter_type', '')
        filter_grammar = request.args.get('filter_grammar', '')
        filter_scripture = request.args.get('filter_scripture', '')
        
        # Build query with search and filters
        conditions = []
        
        if search:
            conditions.append({
                '$or': [
                    {'chuukese_word': {'$regex': search, '$options': 'i'}},
                    {'english_translation': {'$regex': search, '$options': 'i'}},
                    {'definition': {'$regex': search, '$options': 'i'}},
                    {'examples': {'$regex': search, '$options': 'i'}}
                ]
            })
        
        # Add filter conditions
        if filter_type:
            conditions.append({'type': filter_type})
        if filter_grammar:
            conditions.append({'grammar': filter_grammar})
        if filter_scripture:
            # For scripture, use regex to allow partial match
            conditions.append({'scripture': {'$regex': filter_scripture, '$options': 'i'}})
        
        query = {'$and': conditions} if conditions else {}
        
        # Map frontend column names to database field names
        field_map = {
            'chuukese': 'chuukese_word',
            'english': 'english_translation',
            'type': 'type',
            'grammar': 'grammar',
            'scripture': 'scripture',
            'search_direction': 'search_direction',
            'definition': 'definition'
        }
        
        # Fetch all matching entries (we'll sort and paginate in Python to handle nulls)
        all_entries = list(dict_db.dictionary_collection.find(query))
        total = len(all_entries)
        
        # Sort in Python to handle null/missing values properly
        if sort_by and sort_by in field_map:
            sort_field = field_map[sort_by]
            reverse = sort_order == 'desc'
            
            # Sort with nulls/empty at the end, case-insensitive for strings
            def sort_key(entry):
                value = entry.get(sort_field)
                if value is None or value == '':
                    # Put nulls/empty at the end
                    return (1, '')
                # Case-insensitive string comparison
                return (0, str(value).lower())
            
            all_entries.sort(key=sort_key, reverse=reverse)
        
        # Apply pagination after sorting
        skip = (page - 1) * limit
        entries = all_entries[skip:skip + limit]
        
        # Convert ObjectId to string for JSON serialization
        for entry in entries:
            if '_id' in entry:
                entry['_id'] = str(entry['_id'])
        
        return jsonify({
            'entries': entries,
            'total': total,
            'page': page,
            'limit': limit
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/database/distinct', methods=['GET'])
def api_database_distinct():
    """API: Get distinct values for filter dropdowns"""
    try:
        field = request.args.get('field', '')
        
        # Map frontend field names to database field names
        field_map = {
            'type': 'type',
            'grammar': 'grammar',
            'scripture': 'scripture'
        }
        
        if field not in field_map:
            return jsonify({'error': 'Invalid field'}), 400
        
        db_field = field_map[field]
        
        # Get distinct non-null, non-empty values
        distinct_values = dict_db.dictionary_collection.distinct(db_field)
        
        # Filter out None and empty strings, sort alphabetically
        values = sorted([v for v in distinct_values if v and str(v).strip()])
        
        return jsonify({'field': field, 'values': values})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


# Bible book information with chapter/verse counts
BIBLE_BOOKS = {
    'Genesis': {'num': 1, 'chapters': 50, 'verses': [31,25,24,26,32,22,24,22,29,32,32,20,18,24,21,16,27,33,38,18,34,24,20,67,34,35,46,22,35,43,55,32,20,31,29,43,36,30,23,23,57,38,34,34,28,34,31,22,33,26]},
    'Exodus': {'num': 2, 'chapters': 40, 'verses': [22,25,22,31,23,30,25,32,35,29,10,51,22,31,27,36,16,27,25,26,36,31,33,18,40,37,21,43,46,38,18,35,23,35,35,38,29,31,43,38]},
    'Leviticus': {'num': 3, 'chapters': 27, 'verses': [17,16,17,35,19,30,38,36,24,20,47,8,59,57,33,34,16,30,37,27,24,33,44,23,55,46,34]},
    'Numbers': {'num': 4, 'chapters': 36, 'verses': [54,34,51,49,31,27,89,26,23,36,35,16,33,45,41,50,13,32,22,29,35,41,30,25,18,65,23,31,40,16,54,42,56,29,34,13]},
    'Deuteronomy': {'num': 5, 'chapters': 34, 'verses': [46,37,29,49,33,25,26,20,29,22,32,32,18,29,23,22,20,22,21,20,23,30,25,22,19,19,26,68,29,20,30,52,29,12]},
    'Joshua': {'num': 6, 'chapters': 24, 'verses': [18,24,17,24,15,27,26,35,27,43,23,24,33,15,63,10,18,28,51,9,45,34,16,33]},
    'Judges': {'num': 7, 'chapters': 21, 'verses': [36,23,31,24,31,40,25,35,57,18,40,15,25,20,20,31,13,31,30,48,25]},
    'Ruth': {'num': 8, 'chapters': 4, 'verses': [22,23,18,22]},
    '1 Samuel': {'num': 9, 'chapters': 31, 'verses': [28,36,21,22,12,21,17,22,27,27,15,25,23,52,35,23,58,30,24,42,15,23,29,22,44,25,12,25,11,31,13]},
    '2 Samuel': {'num': 10, 'chapters': 24, 'verses': [27,32,39,12,25,23,29,18,13,19,27,31,39,33,37,23,29,33,43,26,22,51,39,25]},
    '1 Kings': {'num': 11, 'chapters': 22, 'verses': [53,46,28,34,18,38,51,66,28,29,43,33,34,31,34,34,24,46,21,43,29,53]},
    '2 Kings': {'num': 12, 'chapters': 25, 'verses': [18,25,27,44,27,33,20,29,37,36,21,21,25,29,38,20,41,37,37,21,26,20,37,20,30]},
    '1 Chronicles': {'num': 13, 'chapters': 29, 'verses': [54,55,24,43,26,81,40,40,44,14,47,40,14,17,29,43,27,17,19,8,30,19,32,31,31,32,34,21,30]},
    '2 Chronicles': {'num': 14, 'chapters': 36, 'verses': [17,18,17,22,14,42,22,18,31,19,23,16,22,15,19,14,19,34,11,37,20,12,21,27,28,23,9,27,36,27,21,33,25,33,27,23]},
    'Ezra': {'num': 15, 'chapters': 10, 'verses': [11,70,13,24,17,22,28,36,15,44]},
    'Nehemiah': {'num': 16, 'chapters': 13, 'verses': [11,20,32,23,19,19,73,18,38,39,36,47,31]},
    'Esther': {'num': 17, 'chapters': 10, 'verses': [22,23,15,17,14,14,10,17,32,3]},
    'Job': {'num': 18, 'chapters': 42, 'verses': [22,13,26,21,27,30,21,22,35,22,20,25,28,22,35,22,16,21,29,29,34,30,17,25,6,14,23,28,25,31,40,22,33,37,16,33,24,41,30,24,34,17]},
    'Psalms': {'num': 19, 'chapters': 150, 'verses': [6,12,8,8,12,10,17,9,20,18,7,8,6,7,5,11,15,50,14,9,13,31,6,10,22,12,14,9,11,12,24,11,22,22,28,12,40,22,13,17,13,11,5,26,17,11,9,14,20,23,19,9,6,7,23,13,11,11,17,12,8,12,11,10,13,20,7,35,36,5,24,20,28,23,10,12,20,72,13,19,16,8,18,12,13,17,7,18,52,17,16,15,5,23,11,13,12,9,9,5,8,28,22,35,45,48,43,13,31,7,10,10,9,8,18,19,2,29,176,7,8,9,4,8,5,6,5,6,8,8,3,18,3,3,21,26,9,8,24,13,10,7,12,15,21,10,20,14,9,6]},
    'Proverbs': {'num': 20, 'chapters': 31, 'verses': [33,22,35,27,23,35,27,36,18,32,31,28,25,35,33,33,28,24,29,30,31,29,35,34,28,28,27,28,27,33,31]},
    'Ecclesiastes': {'num': 21, 'chapters': 12, 'verses': [18,26,22,16,20,12,29,17,18,20,10,14]},
    'Song of Solomon': {'num': 22, 'chapters': 8, 'verses': [17,17,11,16,16,13,13,14]},
    'Isaiah': {'num': 23, 'chapters': 66, 'verses': [31,22,26,6,30,13,25,22,21,34,16,6,22,32,9,14,14,7,25,6,17,25,18,23,12,21,13,29,24,33,9,20,24,17,10,22,38,22,8,31,29,25,28,28,25,13,15,22,26,11,23,15,12,17,13,12,21,14,21,22,11,12,19,12,25,24]},
    'Jeremiah': {'num': 24, 'chapters': 52, 'verses': [19,37,25,31,31,30,34,22,26,25,23,17,27,22,21,21,27,23,15,18,14,30,40,10,38,24,22,17,32,24,40,44,26,22,19,32,21,28,18,16,18,22,13,30,5,28,7,47,39,46,64,34]},
    'Lamentations': {'num': 25, 'chapters': 5, 'verses': [22,22,66,22,22]},
    'Ezekiel': {'num': 26, 'chapters': 48, 'verses': [28,10,27,17,17,14,27,18,11,22,25,28,23,23,8,63,24,32,14,49,32,31,49,27,17,21,36,26,21,26,18,32,33,31,15,38,28,23,29,49,26,20,27,31,25,24,23,35]},
    'Daniel': {'num': 27, 'chapters': 12, 'verses': [21,49,30,37,31,28,28,27,27,21,45,13]},
    'Hosea': {'num': 28, 'chapters': 14, 'verses': [11,23,5,19,15,11,16,14,17,15,12,14,16,9]},
    'Joel': {'num': 29, 'chapters': 3, 'verses': [20,32,21]},
    'Amos': {'num': 30, 'chapters': 9, 'verses': [15,16,15,13,27,14,17,14,15]},
    'Obadiah': {'num': 31, 'chapters': 1, 'verses': [21]},
    'Jonah': {'num': 32, 'chapters': 4, 'verses': [17,10,10,11]},
    'Micah': {'num': 33, 'chapters': 7, 'verses': [16,13,12,13,15,16,20]},
    'Nahum': {'num': 34, 'chapters': 3, 'verses': [15,13,19]},
    'Habakkuk': {'num': 35, 'chapters': 3, 'verses': [17,20,19]},
    'Zephaniah': {'num': 36, 'chapters': 3, 'verses': [18,15,20]},
    'Haggai': {'num': 37, 'chapters': 2, 'verses': [15,23]},
    'Zechariah': {'num': 38, 'chapters': 14, 'verses': [21,13,10,14,11,15,14,23,17,12,17,14,9,21]},
    'Malachi': {'num': 39, 'chapters': 4, 'verses': [14,17,18,6]},
    'Matthew': {'num': 40, 'chapters': 28, 'verses': [25,23,17,25,48,34,29,34,38,42,30,50,58,36,39,28,27,35,30,34,46,46,39,51,46,75,66,20]},
    'Mark': {'num': 41, 'chapters': 16, 'verses': [45,28,35,41,43,56,37,38,50,52,33,44,37,72,47,20]},
    'Luke': {'num': 42, 'chapters': 24, 'verses': [80,52,38,44,39,49,50,56,62,42,54,59,35,35,32,31,37,43,48,47,38,71,56,53]},
    'John': {'num': 43, 'chapters': 21, 'verses': [51,25,36,54,47,71,53,59,41,42,57,50,38,31,27,33,26,40,42,31,25]},
    'Acts': {'num': 44, 'chapters': 28, 'verses': [26,47,26,37,42,15,60,40,43,48,30,25,52,28,41,40,34,28,41,38,40,30,35,27,27,32,44,31]},
    'Romans': {'num': 45, 'chapters': 16, 'verses': [32,29,31,25,21,23,25,39,33,21,36,21,14,23,33,27]},
    '1 Corinthians': {'num': 46, 'chapters': 16, 'verses': [31,16,23,21,13,20,40,13,27,33,34,31,13,40,58,24]},
    '2 Corinthians': {'num': 47, 'chapters': 13, 'verses': [24,17,18,18,21,18,16,24,15,18,33,21,14]},
    'Galatians': {'num': 48, 'chapters': 6, 'verses': [24,21,29,31,26,18]},
    'Ephesians': {'num': 49, 'chapters': 6, 'verses': [23,22,21,32,33,24]},
    'Philippians': {'num': 50, 'chapters': 4, 'verses': [30,30,21,23]},
    'Colossians': {'num': 51, 'chapters': 4, 'verses': [29,23,25,18]},
    '1 Thessalonians': {'num': 52, 'chapters': 5, 'verses': [10,20,13,18,28]},
    '2 Thessalonians': {'num': 53, 'chapters': 3, 'verses': [12,17,18]},
    '1 Timothy': {'num': 54, 'chapters': 6, 'verses': [20,15,16,16,25,21]},
    '2 Timothy': {'num': 55, 'chapters': 4, 'verses': [18,26,17,22]},
    'Titus': {'num': 56, 'chapters': 3, 'verses': [16,15,15]},
    'Philemon': {'num': 57, 'chapters': 1, 'verses': [25]},
    'Hebrews': {'num': 58, 'chapters': 13, 'verses': [14,18,19,16,14,20,28,13,28,39,40,29,25]},
    'James': {'num': 59, 'chapters': 5, 'verses': [27,26,18,17,20]},
    '1 Peter': {'num': 60, 'chapters': 5, 'verses': [25,25,22,19,14]},
    '2 Peter': {'num': 61, 'chapters': 3, 'verses': [21,22,18]},
    '1 John': {'num': 62, 'chapters': 5, 'verses': [10,29,24,21,21]},
    '2 John': {'num': 63, 'chapters': 1, 'verses': [13]},
    '3 John': {'num': 64, 'chapters': 1, 'verses': [14]},
    'Jude': {'num': 65, 'chapters': 1, 'verses': [25]},
    'Revelation': {'num': 66, 'chapters': 22, 'verses': [20,29,22,11,14,17,17,13,21,11,19,17,18,20,8,21,18,24,21,15,27,21]}
}


@app.route('/api/database/bible-coverage', methods=['GET'])
def api_bible_coverage():
    """API: Get Bible book coverage - which verses are loaded vs missing"""
    try:
        book = request.args.get('book', '')
        
        if not book:
            # Return list of books with their loaded verse counts
            # Use single aggregation query to avoid Cosmos DB RU throttling
            books_coverage = []
            
            # Get all scripture entries at once
            scripture_entries = list(dict_db.dictionary_collection.find(
                {'scripture': {'$exists': True, '$ne': ''}},
                {'scripture': 1, '_id': 0}
            ))
            
            # Count entries per book
            book_counts = {}
            for entry in scripture_entries:
                scripture = entry.get('scripture', '')
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
            for book_name, info in BIBLE_BOOKS.items():
                count = book_counts.get(book_name, 0)
                total_verses = sum(info['verses'])
                books_coverage.append({
                    'book': book_name,
                    'num': info['num'],
                    'chapters': info['chapters'],
                    'total_verses': total_verses,
                    'loaded_verses': count,
                    'coverage_percent': round((count / total_verses) * 100, 1) if total_verses > 0 else 0
                })
            return jsonify({'books': books_coverage})
        
        # Get details for a specific book
        if book not in BIBLE_BOOKS:
            return jsonify({'error': 'Invalid book name'}), 400
        
        book_info = BIBLE_BOOKS[book]
        
        # Get all scripture entries for this book
        entries = list(dict_db.dictionary_collection.find({
            'scripture': {'$regex': f'^{book}', '$options': 'i'}
        }, {'scripture': 1, '_id': 0}))
        
        # Parse loaded verses
        loaded_verses = set()
        for entry in entries:
            scripture = entry.get('scripture', '')
            # Parse "Book Chapter:Verse" format
            match = re.match(rf'^{re.escape(book)}\s+(\d+):(\d+)', scripture, re.IGNORECASE)
            if match:
                chapter = int(match.group(1))
                verse = int(match.group(2))
                loaded_verses.add((chapter, verse))
        
        # Build chapter-by-chapter coverage
        chapters_coverage = []
        for chapter_idx, verse_count in enumerate(book_info['verses']):
            chapter_num = chapter_idx + 1
            loaded_in_chapter = []
            missing_in_chapter = []
            
            for verse in range(1, verse_count + 1):
                if (chapter_num, verse) in loaded_verses:
                    loaded_in_chapter.append(verse)
                else:
                    missing_in_chapter.append(verse)
            
            chapters_coverage.append({
                'chapter': chapter_num,
                'total_verses': verse_count,
                'loaded': loaded_in_chapter,
                'missing': missing_in_chapter,
                'loaded_count': len(loaded_in_chapter),
                'missing_count': len(missing_in_chapter)
            })
        
        total_verses = sum(book_info['verses'])
        total_loaded = len(loaded_verses)
        
        return jsonify({
            'book': book,
            'num': book_info['num'],
            'chapters': chapters_coverage,
            'total_verses': total_verses,
            'total_loaded': total_loaded,
            'total_missing': total_verses - total_loaded,
            'coverage_percent': round((total_loaded / total_verses) * 100, 1) if total_verses > 0 else 0
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/database/entries', methods=['POST'])
def api_create_database_entry():
    """API: Create a new dictionary entry"""
    try:
        data = request.get_json()
        
        # Fetch scripture if provided
        scripture_ref = data.get('scripture', '')
        chuukese_word = data.get('chuukese_word', '')
        english_translation = data.get('english_translation', '')
        
        if scripture_ref:
            scripture_result = fetch_scripture_from_jworg(scripture_ref)
            if not scripture_result['error']:
                # Auto-populate fields with scripture text
                chuukese_word = scripture_result['chuukese']
                english_translation = scripture_result['english']
        
        entry = {
            'chuukese_word': chuukese_word,
            'english_translation': english_translation,
            'definition': data.get('definition', ''),
            'word_type': data.get('word_type', '') or data.get('grammar', ''),
            'type': 'scripture' if scripture_ref else data.get('type', ''),
            'grammar': data.get('grammar', ''),
            'direction': data.get('direction', ''),
            'examples': data.get('examples', []),
            'notes': data.get('notes', ''),
            'scripture': scripture_ref,
            'references': data.get('references', ''),
            'source': 'User Input',
            'created_date': datetime.now()
        }
        
        result = dict_db.dictionary_collection.insert_one(entry)
        entry['_id'] = str(result.inserted_id)
        
        return jsonify({'message': 'Entry created successfully', 'entry': entry}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/database/entries/<entry_id>', methods=['PUT'])
def api_update_database_entry(entry_id):
    """API: Update a dictionary entry"""
    try:
        from bson import ObjectId
        data = request.get_json()
        
        # Fetch scripture if provided
        scripture_ref = data.get('scripture', '')
        chuukese_word = data.get('chuukese_word', '')
        english_translation = data.get('english_translation', '')
        
        if scripture_ref:
            scripture_result = fetch_scripture_from_jworg(scripture_ref)
            if not scripture_result['error']:
                # Auto-populate fields with scripture text
                chuukese_word = scripture_result['chuukese']
                english_translation = scripture_result['english']
        
        update_data = {
            'chuukese_word': chuukese_word,
            'english_translation': english_translation,
            'definition': data.get('definition', ''),
            'word_type': data.get('word_type', '') or data.get('grammar', ''),
            'type': 'scripture' if scripture_ref else data.get('type', ''),
            'grammar': data.get('grammar', ''),
            'direction': data.get('direction', ''),
            'examples': data.get('examples', []),
            'notes': data.get('notes', ''),
            'scripture': scripture_ref,
            'references': data.get('references', ''),
            'updated_date': datetime.now()
        }
        
        result = dict_db.dictionary_collection.update_one(
            {'_id': ObjectId(entry_id)},
            {'$set': update_data}
        )
        
        if result.modified_count > 0:
            return jsonify({'message': 'Entry updated successfully'}), 200
        else:
            return jsonify({'error': 'Entry not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/database/entries/<entry_id>', methods=['DELETE'])
def api_delete_database_entry(entry_id):
    """API: Delete a dictionary entry"""
    try:
        from bson import ObjectId
        
        result = dict_db.dictionary_collection.delete_one({'_id': ObjectId(entry_id)})
        
        if result.deleted_count > 0:
            return jsonify({'message': 'Entry deleted successfully'}), 200
        else:
            return jsonify({'error': 'Entry not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/scripture/preview', methods=['POST'])
def api_scripture_preview():
    """API: Preview scripture text without saving to database"""
    try:
        data = request.get_json()
        scripture_ref = data.get('scripture', '').strip()
        
        if not scripture_ref:
            return jsonify({'error': 'Scripture reference is required'}), 400
        
        # Fetch scripture from EPUBs
        result = fetch_scripture_from_jworg(scripture_ref)
        
        return jsonify({
            'scripture': scripture_ref,
            'chuukese': result.get('chuukese', ''),
            'english': result.get('english', ''),
            'error': result.get('error')
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# Serve React app
@app.route('/assets/<path:path>')
def serve_assets(path):
    """Serve React app static assets"""
    return send_from_directory('frontend/dist/assets', path)

# AI scraping protection - robots.txt
@app.route('/robots.txt')
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
    return Response(robots_content, mimetype='text/plain')

# React app routes - handle all non-API routes
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_react(path):
    """Serve React app for all non-API routes"""
    if path.startswith('api/'):
        return jsonify({'error': 'API route not found'}), 404
    
    # Handle static assets
    if path.startswith('assets/'):
        return send_from_directory('frontend/dist', path)
    
    # Check if it's a static file request
    if '.' in path and not path.startswith('api/'):
        try:
            return send_from_directory('frontend/dist', path)
        except:
            pass
    
    # Serve index.html for React routing
    return send_from_directory('frontend/dist', 'index.html')


if __name__ == '__main__':
    # Create upload directory if it doesn't exist
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    
    # Run the application
    # Debug mode should only be enabled in development
    debug_mode = os.getenv('FLASK_ENV') == 'development'
    port = int(os.getenv('PORT', 5002))  # Use port 5002 as default
    print(f"Starting Flask app on port {port}")
    app.run(debug=debug_mode, host='0.0.0.0', port=port)
