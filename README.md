# Chuuk Dictionary OCR & Lookup

A web application for digitizing and cross-referencing Chuukese dictionary pages using OCR technology and online resources.

## Features

- 📚 **Upload & Manage Publications**: Upload and organize dictionary publications with 400+ pages
- 🔍 **Dual OCR Processing**: Process scanned pages using both Tesseract OCR and Google Vision API
- 🌐 **Cross-Reference Lookup**: Search words and phrases across JW.org Chuukese resources
- 💾 **Organized Storage**: Store and manage your digitized dictionary content
- 🎯 **Multi-language Support**: Support for multiple languages including Chuukese, English, and others

## Prerequisites

- Python 3.8 or higher
- Tesseract OCR installed on your system
- (Optional) Google Cloud Vision API credentials for enhanced OCR

## Installation

### 1. Install Tesseract OCR

**Ubuntu/Debian:**

```bash
sudo apt-get update
sudo apt-get install tesseract-ocr
```

**macOS:**

```bash
brew install tesseract
```

**Windows:**
Download and install from: <https://github.com/UB-Mannheim/tesseract/wiki>

### 2. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 3. (Optional) Set Up Google Cloud Vision API

1. Create a project in Google Cloud Console
2. Enable the Cloud Vision API
3. Create a service account and download the JSON key file
4. Set the path to your credentials in `.env` file

### 4. Configure Environment Variables

Copy the example environment file:

```bash
cp .env.example .env
```

Edit `.env` and update the following:

- `GOOGLE_APPLICATION_CREDENTIALS`: Path to your Google Cloud service account JSON key (optional)
- `FLASK_SECRET_KEY`: A random secret key for Flask sessions
- `UPLOAD_FOLDER`: Directory for storing uploaded files (default: uploads)

## Usage

### Start the Application

```bash
python app.py
```

The application will be available at: <http://localhost:5002>

### Upload a Dictionary Publication

1. Click "New Publication" in the navigation menu
2. Enter a title and optional description
3. Click "Create Publication"
4. Upload dictionary pages by clicking or dragging files into the upload area
5. Choose whether to process OCR automatically
6. Select the appropriate language for OCR processing

### Lookup Words and Phrases

1. Click "Word Lookup" in the navigation menu
2. Enter a word or phrase to search
3. Select the language (Chuukese, English, etc.)
4. Click "Search"
5. View results from JW.org resources with direct links

## Project Structure

```js
chuuk/
├── app.py                    # Main Flask application
├── ocr_processor.py          # OCR processing module
├── jworg_lookup.py           # JW.org word lookup module
├── publication_manager.py    # Publication management module
├── requirements.txt          # Python dependencies
├── .env.example              # Example environment configuration
├── templates/                # HTML templates
│   ├── base.html
│   ├── index.html
│   ├── new_publication.html
│   ├── publication.html
│   └── lookup.html
├── static/                   # Static files (CSS, JS, images)
└── uploads/                  # Uploaded files and publications

```

## API Endpoints

- `GET /` - Home page with publication list
- `GET /publication/new` - Create new publication form
- `POST /publication/new` - Create new publication
- `GET /publication/<id>` - View publication and its pages
- `POST /publication/<id>/upload` - Upload page to publication
- `POST /ocr/process` - Process OCR on a specific page
- `GET /lookup` - Word lookup page
- `POST /lookup` - Search for word/phrase
- `GET /api/lookup/<word>` - API endpoint for word lookup

## Technologies Used

- **Flask**: Web framework
- **Tesseract OCR**: Open-source OCR engine
- **Google Cloud Vision API**: Advanced OCR and image analysis
- **Pillow**: Image processing
- **Requests**: HTTP library for web scraping

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

See LICENSE file for details.

## Support

For issues and questions, please open an issue on GitHub.
