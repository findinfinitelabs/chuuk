"""
Flask application for Chuuk Dictionary OCR and Lookup
"""
import os
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

from ocr_processor import OCRProcessor
from jworg_lookup import JWOrgLookup
from publication_manager import PublicationManager

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['MAX_CONTENT_LENGTH'] = int(os.getenv('MAX_CONTENT_LENGTH', 16 * 1024 * 1024))  # 16MB default
app.config['UPLOAD_FOLDER'] = os.getenv('UPLOAD_FOLDER', 'uploads')

# Initialize services
pub_manager = PublicationManager(app.config['UPLOAD_FOLDER'])
ocr_processor = OCRProcessor(use_google_vision=bool(os.getenv('GOOGLE_APPLICATION_CREDENTIALS')))
jworg_lookup = JWOrgLookup()

# Allowed file extensions
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'tiff', 'pdf'}


def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/')
def index():
    """Home page"""
    publications = pub_manager.list_publications()
    return render_template('index.html', publications=publications)


@app.route('/publication/new', methods=['GET', 'POST'])
def new_publication():
    """Create a new publication"""
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description', '')
        
        if not title:
            flash('Title is required', 'error')
            return render_template('new_publication.html')
        
        pub_id = pub_manager.create_publication(title, description)
        flash('Publication created successfully', 'success')
        return redirect(url_for('view_publication', pub_id=pub_id))
    
    return render_template('new_publication.html')


@app.route('/publication/<pub_id>')
def view_publication(pub_id):
    """View a publication and its pages"""
    publication = pub_manager.get_publication(pub_id)
    
    if not publication:
        flash('Publication not found', 'error')
        return redirect(url_for('index'))
    
    return render_template('publication.html', publication=publication)


@app.route('/publication/<pub_id>/upload', methods=['POST'])
def upload_page(pub_id):
    """Upload a page to a publication"""
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
        ocr_results = None
        
        if process_ocr:
            lang = request.form.get('ocr_lang', 'eng')
            ocr_results = ocr_processor.process_image(file_path, lang)
        
        # Add page to publication
        pub_manager.add_page(pub_id, filename, ocr_results)
        
        flash('Page uploaded successfully', 'success')
        return jsonify({'success': True, 'filename': filename, 'ocr_results': ocr_results})
    
    return jsonify({'error': 'Invalid file type'}), 400


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


@app.route('/lookup', methods=['GET', 'POST'])
def lookup():
    """Word/phrase lookup page"""
    if request.method == 'POST':
        word = request.form.get('word')
        lang = request.form.get('lang', 'chk')
        
        if not word:
            flash('Please enter a word or phrase', 'error')
            return render_template('lookup.html')
        
        results = jworg_lookup.search_word(word, lang)
        return render_template('lookup.html', word=word, results=results, lang=lang)
    
    available_langs = jworg_lookup.get_available_languages()
    return render_template('lookup.html', available_langs=available_langs)


@app.route('/api/lookup/<word>')
def api_lookup(word):
    """API endpoint for word lookup"""
    lang = request.args.get('lang', 'chk')
    results = jworg_lookup.search_word(word, lang)
    return jsonify({'word': word, 'language': lang, 'results': results})


if __name__ == '__main__':
    # Create upload directory if it doesn't exist
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    
    # Run the application
    app.run(debug=True, host='0.0.0.0', port=5000)
