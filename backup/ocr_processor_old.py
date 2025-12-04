"""
OCR processing module supporting both Tesseract and Google Vision API
"""
import os
from typing import Optional, List
from PIL import Image

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

try:
    import pytesseract
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False

try:
    from google.cloud import vision
    from google.oauth2.service_account import Credentials
    import google.auth
    GOOGLE_VISION_AVAILABLE = True
except ImportError:
    GOOGLE_VISION_AVAILABLE = False

try:
    from pdf2image import convert_from_path
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False

try:
    from docx import Document
    DOCX_SUPPORT = True
except ImportError:
    DOCX_SUPPORT = False


class OCRProcessor:
    """Handles OCR processing using Tesseract and optionally Google Vision API"""
    
    def __init__(self, use_google_vision: bool = False):
        """
        Initialize OCR processor
        
        Args:
            use_google_vision: Whether to use Google Vision API (requires API key)
        """
        self.use_google_vision = use_google_vision and GOOGLE_VISION_AVAILABLE
        
        # Check if we have an API key for Google Vision
        if self.use_google_vision:
            api_key = os.getenv('GOOGLE_VISION_API_KEY')
            if api_key:
                print(f"🔑 Google Vision API key found - will use REST API")
                self.use_google_vision = True
            else:
                print(f"❌ No Google Vision API key found")
                self.use_google_vision = False
        
        if not self.use_google_vision:
            print(f"🔤 Using Tesseract OCR only")
    
    def process_pdf_to_images(self, pdf_path: str) -> List[Image.Image]:
        """
        Convert PDF pages to images
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            List of PIL Image objects, one per page
        """
        if not PDF_SUPPORT:
            raise Exception("PDF processing not available. Install pdf2image and poppler.")
        
        try:
            images = convert_from_path(pdf_path, dpi=200)
            return images
        except Exception as e:
            raise Exception(f"Error converting PDF to images: {str(e)}")
    
    def process_image_tesseract(self, image_path: str, lang: str = 'eng') -> str:
        """
        Process image using Tesseract OCR
        
        Args:
            image_path: Path to the image file
            lang: Language code for OCR (default: 'eng')
            
        Returns:
            Extracted text from the image
        """
        if not TESSERACT_AVAILABLE:
            return "Tesseract OCR is not installed. Please install pytesseract and Tesseract OCR."
        
        try:
            image = Image.open(image_path)
            text = pytesseract.image_to_string(image, lang=lang)
            return text
        except Exception as e:
            return f"Error processing image with Tesseract: {str(e)}"
    
    def process_image_google_vision(self, image_path: str) -> str:
        """
        Extract text from DOCX file with page/section information
        
        Args:
            docx_path: Path to the DOCX file
            
        Returns:
            Dictionary with extracted text and page information
        """
        if not DOCX_SUPPORT:
            return {
                'error': 'DOCX processing not available. Install python-docx.',
                'text': '',
                'type': 'docx'
            }
        
        try:
            doc = Document(docx_path)
            pages_data = []
            current_page = 1
            current_page_text = []
            
            for paragraph in doc.paragraphs:
                text = paragraph.text.strip()
                if not text:
                    continue
                    
                # Check for page break indicators or page numbers
                if any(indicator in text.lower() for indicator in ['page ', 'p.', '- page', '—page']):
                    # If we have accumulated text, save current page
                    if current_page_text:
                        pages_data.append({
                            'page_number': current_page,
                            'text': '\n'.join(current_page_text),
                            'total_pages': None  # Will be set after processing all pages
                        })
                        current_page += 1
                        current_page_text = []
                    
                    # Don't include page number lines in content
                    continue
                
                current_page_text.append(text)
            
            # Add final page if there's remaining text
            if current_page_text:
                pages_data.append({
                    'page_number': current_page,
                    'text': '\n'.join(current_page_text),
                    'total_pages': None
                })
            
            # Update total pages for all entries
            total_pages = len(pages_data)
            for page_data in pages_data:
                page_data['total_pages'] = total_pages
            
            # Create combined text
            combined_text = '\n\n'.join([f"--- Page {p['page_number']} ---\n{p['text']}" for p in pages_data])
            
            return {
                'pages': pages_data,
                'type': 'docx',
                'total_pages': total_pages,
                'text': combined_text,
                'source': 'docx_extraction'
            }
            
        except Exception as e:
            return {
                'error': f'Error processing DOCX: {str(e)}',
                'text': '',
                'type': 'docx'
            }
        """
        Process image using Google Vision API via REST API with API key
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Extracted text from the image
        """
        api_key = os.getenv('GOOGLE_VISION_API_KEY')
        if not api_key:
            return "Google Vision API key not found"
        
        try:
            import base64
            import requests
            
            # Read and encode image
            with open(image_path, 'rb') as image_file:
                content = image_file.read()
                encoded_image = base64.b64encode(content).decode('utf-8')
            
            # Prepare request
            url = f'https://vision.googleapis.com/v1/images:annotate?key={api_key}'
            headers = {'Content-Type': 'application/json'}
            data = {
                'requests': [{
                    'image': {'content': encoded_image},
                    'features': [{'type': 'TEXT_DETECTION'}]
                }]
            }
            
            # Make request
            response = requests.post(url, headers=headers, json=data)
            response.raise_for_status()
            
            result = response.json()
            
            # Extract text from response
            if 'responses' in result and result['responses']:
                annotations = result['responses'][0].get('textAnnotations', [])
                if annotations:
                    return annotations[0].get('description', '')
            
            return ""
            
        except Exception as e:
            error_msg = f"Error processing image with Google Vision: {str(e)}"
            print(f"❌ {error_msg}")
            return error_msg
    
    def process_image(self, file_path: str, lang: str = 'eng') -> dict:
        """
        Process image, PDF, or DOCX file using available methods
        
        Args:
            file_path: Path to the image, PDF, or DOCX file
            lang: Language code for OCR (default: 'eng')
            
        Returns:
            Dictionary with processing results from different methods
        """
        results = {}
        file_extension = os.path.splitext(file_path)[1].lower()
        
        # Handle DOCX files
        if file_extension == '.docx':
            print(f"📄 Processing DOCX file: {os.path.basename(file_path)}")
            return self.process_docx_to_text(file_path)
        
        # Handle PDF files - return page-by-page results
        elif file_extension == '.pdf':
            try:
                pdf_images = self.process_pdf_to_images(image_path)
                pages_data = []
                
                for i, image in enumerate(pdf_images):
                    page_result = {
                        'page_number': i + 1,
                        'total_pages': len(pdf_images)
                    }
                    
                    # Process with Tesseract
                    if TESSERACT_AVAILABLE:
                        page_text = self.process_image_tesseract_pil(image, lang)
                        page_result['tesseract'] = page_text
                    
                    # Process with Google Vision if enabled
                    if self.use_google_vision:
                        # Save temporary image for Google Vision
                        temp_image_path = f"{image_path}_temp_page_{i+1}.png"
                        image.save(temp_image_path)
                        try:
                            page_text_google = self.process_image_google_vision(temp_image_path)
                            page_result['google_vision'] = page_text_google
                        finally:
                            # Clean up temporary file
                            if os.path.exists(temp_image_path):
                                os.remove(temp_image_path)
                    
                    # Set primary text result for this page
                    if self.use_google_vision and 'google_vision' in page_result:
                        page_result['text'] = page_result['google_vision']
                    else:
                        page_result['text'] = page_result.get('tesseract', '')
                    
                    pages_data.append(page_result)
                
                results['pages'] = pages_data
                results['type'] = 'pdf'
                results['total_pages'] = len(pdf_images)
                
                # Create a combined text for backward compatibility
                combined_text = "\n\n".join([f"--- Page {p['page_number']} ---\n{p['text']}" for p in pages_data])
                results['text'] = combined_text
                
            except Exception as e:
                results['error'] = f"Error processing PDF: {str(e)}"
                results['text'] = ""
                results['type'] = 'pdf'
        
        # Handle regular image files
        else:
            # Try Tesseract
            tesseract_text = self.process_image_tesseract(image_path, lang)
            results['tesseract'] = tesseract_text
            
            # Try Google Vision if enabled
            if self.use_google_vision:
                google_text = self.process_image_google_vision(image_path)
                results['google_vision'] = google_text
            
            # Set primary text result
            if self.use_google_vision and 'google_vision' in results:
                results['text'] = results['google_vision']
            else:
                results['text'] = results['tesseract']
            
            results['type'] = 'image'
            results['page_number'] = 1
            results['total_pages'] = 1
        
        return results
    
    def process_image_tesseract_pil(self, image: Image.Image, lang: str = 'eng') -> str:
        """
        Process PIL Image object using Tesseract OCR
        
        Args:
            image: PIL Image object
            lang: Language code for OCR (default: 'eng')
            
        Returns:
            Extracted text from the image
        """
        if not TESSERACT_AVAILABLE:
            return "Tesseract OCR is not installed. Please install pytesseract and Tesseract OCR."
        
        try:
            text = pytesseract.image_to_string(image, lang=lang)
            return text
        except Exception as e:
            return f"Error processing image with Tesseract: {str(e)}"
