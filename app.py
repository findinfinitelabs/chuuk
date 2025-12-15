"""
Flask application for Chuuk Dictionary OCR and Lookup
"""
import os
import re
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory
# from flask_cors import CORS
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from markupsafe import Markup

from src.ocr.ocr_processor import OCRProcessor
from src.core.jworg_lookup import JWOrgLookup
from src.database.publication_manager import PublicationManager
from src.database.dictionary_db import DictionaryDB
from scripts.processing_logger import processing_logger
try:
    from src.translation.helsinki_translator_v2 import HelsinkiChuukeseTranslator
    HELSINKI_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ Helsinki translator not available: {e}")
    HELSINKI_AVAILABLE = False

# Load environment variables
load_dotenv()

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

# Initialize services
pub_manager = PublicationManager(app.config['UPLOAD_FOLDER'])
ocr_processor = OCRProcessor(use_google_vision=bool(os.getenv('GOOGLE_APPLICATION_CREDENTIALS')))
dict_db = DictionaryDB()
jworg_lookup = JWOrgLookup(pub_manager)

# Initialize Helsinki-NLP translator
helsinki_translator = None
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


@app.route('/')
def index():
    """Serve React app"""
    return send_from_directory('frontend/dist', 'index.html')


@app.route('/<path:path>')
def serve_static(path):
    """Serve static files from React build"""
    return send_from_directory('frontend/dist', path)


@app.route('/publication/new', methods=['GET', 'POST'])
def new_publication():
    """Redirect to React app"""
    return redirect('/')


@app.route('/publication/<pub_id>')
def view_publication(pub_id):
    """Redirect to React app"""
    return redirect('/')


@app.route('/publication/<pub_id>/upload', methods=['POST'])
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
        process_ocr = request.form.get('process_ocr', 'false') == 'true'
        index_dictionary = request.form.get('index_dictionary', 'false') == 'true'
        ocr_results = None
        
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
        
        # Add page to publication
        pub_manager.add_page(pub_id, filename, ocr_results)
        
        flash('Page uploaded successfully', 'success')
        return jsonify({
            'success': True, 
            'filename': filename, 
            'ocr_results': ocr_results,
            'session_id': session_id if process_ocr else None
        })
    
    return jsonify({'error': 'Invalid file type'}), 400


@app.route('/publication/<pub_id>/upload_csv', methods=['POST'])
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
    
    if file and file.filename.lower().endswith('.csv'):
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
            page_id, entries_added = dict_db.add_dictionary_from_csv(pub_id, filename, csv_content)
            
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
            processing_logger.log(session_id, f"❌ CSV processing failed: {str(e)}", 'error')
            processing_logger.set_status(session_id, 'failed')
            return jsonify({'error': f'Error processing CSV: {str(e)}'}), 500
    
    return jsonify({'error': 'Invalid file type. Only CSV files are supported.'}), 400


@app.route('/ocr/process', methods=['POST'])
def process_ocr():
    """Process OCR on a specific page"""
    pub_id = request.form.get('pub_id')
    filename = request.form.get('filename')
    lang = request.form.get('lang', 'eng')
    
    if not pub_id or not filename:
        return jsonify({'error': 'Missing parameters'}), 400
    
    file_path = pub_manager.get_page_path(pub_id, filename)
    
    if not os.path.exists(file_path):
        return jsonify({'error': 'File not found'}), 404
    
    results = ocr_processor.process_image(file_path, lang)
    return jsonify({'success': True, 'results': results})


@app.route('/translate', methods=['GET', 'POST'])
def translate():
    """Redirect to React app"""
    return redirect('/')

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


@app.route('/lookup', methods=['GET', 'POST'])
def lookup():
    """Redirect to React app"""
    return redirect('/')


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


@app.route('/api/processing/status/<session_id>')
def get_processing_status(session_id):
    """Get current processing status"""
    session_data = processing_logger.get_logs(session_id)
    if session_data:
        return jsonify({
            'status': session_data.get('status', 'unknown'),
            'current_page': session_data.get('current_page', 0),
            'total_pages': session_data.get('total_pages', 1),
            'stats': session_data.get('stats', {}),
            'progress_percentage': round((session_data.get('current_page', 0) / session_data.get('total_pages', 1)) * 100, 1)
        })
    else:
        return jsonify({'error': 'Session not found'}), 404


@app.route('/database')
def database_viewer():
    """Serve React app for database viewer"""
    return send_from_directory('frontend/dist', 'index.html')


@app.route('/api/database/entries')
def api_database_entries():
    """API endpoint for paginated dictionary entries"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        search = request.args.get('search', '')
        
        entries = dict_db.get_entries_paginated(page, per_page, search)
        return jsonify(entries)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


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
    """API: Get publication details"""
    try:
        # Validate publication ID format
        import re
        if not re.match(r'^\d{14}_[a-f0-9]{8}$', pub_id):
            return jsonify({'error': 'Invalid publication ID'}), 400
        
        publication = pub_manager.get_publication(pub_id)
        if not publication:
            return jsonify({'error': 'Publication not found'}), 404
        
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
        
        results = dict_db.search_word(word, limit=10)
        return jsonify({'word': word, 'results': results})
    except Exception as e:
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


# Serve React app
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_react(path):
    """Serve React app for all non-API routes"""
    if path.startswith('api/'):
        return jsonify({'error': 'API route not found'}), 404
    
    # Serve index.html for React routing
    return send_from_directory('../frontend/dist', 'index.html')


if __name__ == '__main__':
    # Create upload directory if it doesn't exist
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    
    # Run the application
    # Debug mode should only be enabled in development
    debug_mode = os.getenv('FLASK_ENV') == 'development'
    port = int(os.getenv('PORT', 5002))  # Use port 5002 as default
    print(f"Starting Flask app on port {port}")
    app.run(debug=debug_mode, host='0.0.0.0', port=port)
