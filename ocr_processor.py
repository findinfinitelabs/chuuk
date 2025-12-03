"""
OCR processing module supporting both Tesseract and Google Vision API
"""
import os
from typing import Optional
from PIL import Image

try:
    import pytesseract
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False

try:
    from google.cloud import vision
    GOOGLE_VISION_AVAILABLE = True
except ImportError:
    GOOGLE_VISION_AVAILABLE = False


class OCRProcessor:
    """Handles OCR processing using Tesseract and optionally Google Vision API"""
    
    def __init__(self, use_google_vision: bool = False):
        """
        Initialize OCR processor
        
        Args:
            use_google_vision: Whether to use Google Vision API (requires credentials)
        """
        self.use_google_vision = use_google_vision and GOOGLE_VISION_AVAILABLE
        
        if self.use_google_vision:
            self.vision_client = vision.ImageAnnotatorClient()
        else:
            self.vision_client = None
    
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
        Process image using Google Vision API
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Extracted text from the image
        """
        if not self.vision_client:
            return "Google Vision API not available or not configured"
        
        try:
            with open(image_path, 'rb') as image_file:
                content = image_file.read()
            
            image = vision.Image(content=content)
            response = self.vision_client.text_detection(image=image)
            texts = response.text_annotations
            
            if texts:
                return texts[0].description
            else:
                return ""
        except Exception as e:
            return f"Error processing image with Google Vision: {str(e)}"
    
    def process_image(self, image_path: str, lang: str = 'eng') -> dict:
        """
        Process image using available OCR methods
        
        Args:
            image_path: Path to the image file
            lang: Language code for OCR (default: 'eng')
            
        Returns:
            Dictionary with OCR results from different methods
        """
        results = {}
        
        # Try Tesseract
        tesseract_text = self.process_image_tesseract(image_path, lang)
        results['tesseract'] = tesseract_text
        
        # Try Google Vision if enabled
        if self.use_google_vision:
            google_text = self.process_image_google_vision(image_path)
            results['google_vision'] = google_text
        
        return results
