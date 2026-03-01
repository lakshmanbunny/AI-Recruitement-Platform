import os
import re
import re
import subprocess
import PyPDF2
from config.logging_config import get_logger

logger = get_logger(__name__)

class DriveDownloader:
    def __init__(self, download_dir=None):
        if download_dir is None:
            # Save inside the workspace so it is preserved
            # __file__ is backend/app/services/drive_downloader.py
            # 1: services, 2: app, 3: backend
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            self.download_dir = os.path.join(base_dir, "data", "resumes")
        else:
            self.download_dir = download_dir
        
        if not os.path.exists(self.download_dir):
            os.makedirs(self.download_dir)

    def extract_id_from_url(self, url: str) -> str:
        """
        Extracts the Google Drive file ID from a URL.
        """
        if not url or str(url).lower() == 'nan':
            return None
            
        # Match common Google Drive URL patterns
        match = re.search(r'(?:id=|/d/|/file/d/)([^/&?]+)', str(url))
        if match:
            return match.group(1)
        return None

    def download_and_extract_text(self, url: str, candidate_id: str) -> str:
        """
        Downloads a PDF from Google Drive and extracts its text.
        """
        file_id = self.extract_id_from_url(url)
        if not file_id:
            logger.warning(f"Could not extract Drive ID from URL: {url}")
            return ""

        output_path = os.path.join(self.download_dir, f"{candidate_id}.pdf")
        
        try:
            # Check if we already have it to avoid EDR network crashes on loops
            if not os.path.exists(output_path):
                logger.info(f"Downloading resume for {candidate_id} from Drive ID: {file_id} via CLI subprocess...")
                # Use subprocess to call gdown CLI because the Python API crashes due to EDR hooks
                result = subprocess.run(
                    ["gdown", file_id, "-O", output_path],
                    capture_output=True,
                    text=True
                )
                if result.returncode != 0:
                    logger.error(f"gdown CLI failed: {result.stderr}")
            else:
                logger.info(f"Using cached resume for {candidate_id}")
            
            if not os.path.exists(output_path):
                logger.error(f"Download failed for {candidate_id}, file not found.")
                return ""
                
            # Extract text
            text = self._extract_text_from_pdf(output_path)
            return text
            
        except Exception as e:
            logger.error(f"Error downloading/extracting resume for {candidate_id}: {str(e)}")
            return ""
            
    def _extract_text_from_pdf(self, file_path: str) -> str:
        """
        Extracts raw text from a PDF file.
        """
        try:
            text = ""
            with open(file_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                for page in reader.pages:
                    extracted = page.extract_text()
                    if extracted:
                        text += extracted + "\n"
            return text.strip()
        except Exception as e:
            logger.error(f"Error extracting text from PDF {file_path}: {str(e)}")
            return ""

drive_downloader = DriveDownloader()
