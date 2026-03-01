import pandas as pd
import os
from typing import List, Dict, Any
from config.logging_config import get_logger
from app.services.drive_downloader import drive_downloader

logger = get_logger(__name__)

class DataIngestionService:
    @staticmethod
    def parse_file(file_path: str) -> List[Dict[str, Any]]:
        """
        Parses a CSV or Excel file into a list of candidate dictionaries.
        Expected columns: candidate_id, name, skills, experience, projects, education, github_url
        """
        try:
            ext = os.path.splitext(file_path)[1].lower()
            if ext == '.csv':
                df = pd.read_csv(file_path)
            elif ext in ['.xlsx', '.xls']:
                df = pd.read_excel(file_path)
            else:
                raise ValueError(f"Unsupported file format: {ext}")

            # Normalize column names to lowercase and strip whitespace
            df.columns = [col.lower().strip().replace(' ', '_') for col in df.columns]

            # Mapping of possible column names to standard internal keys
            column_mapping = {
                'id': 'candidate_id',
                'candidate_id': 'candidate_id',
                'roll_number': 'candidate_id',
                'name': 'name',
                'full_name': 'name',
                'email_id_(personal)': 'email',
                'email': 'email',
                'skills': 'skills',
                'experience': 'experience',
                'work_experience': 'experience',
                'projects': 'projects',
                'education': 'education',
                'ug-course_name': 'education', # Fallback for base education
                'github': 'github_url',
                'github_url': 'github_url',
                'git-hub_account_url': 'github_url',
                'linkedin': 'linkedin_url',
                'linkedin_url': 'linkedin_url',
                'linkedin-account_url': 'linkedin_url',
                'upload_resume': 'resume_drive_url'
            }

            # Rename columns based on mapping
            current_columns = df.columns.tolist()
            rename_dict = {}
            for col in current_columns:
                if col in column_mapping:
                    rename_dict[col] = column_mapping[col]
            
            df = df.rename(columns=rename_dict)

            # Ensure minimal required columns exist
            required_columns = ['candidate_id', 'name']
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                raise ValueError(f"Missing required columns: {', '.join(missing_columns)}")

            # Fill NaNs with empty strings
            df = df.fillna('')

            # Convert to list of dicts
            candidates = df.to_dict(orient='records')
            
            # Additional formatting for internal consistency
            for cand in candidates:
                # If candidate_id is numeric, convert to string (e.g., C001) or keep Roll Number
                cand_id = cand.get('candidate_id', '')
                if isinstance(cand_id, (int, float)):
                    cand['candidate_id'] = f"C{int(cand_id):03d}"
                else:
                    cand['candidate_id'] = str(cand_id)

                # Fetch and extract text from Drive resume if available
                drive_url = cand.get('resume_drive_url', '')
                raw_resume_text = ""
                if drive_url and str(drive_url).lower() != 'nan':
                    logger.info(f"Extracting resume from Drive for {cand['candidate_id']}")
                    raw_resume_text = drive_downloader.download_and_extract_text(drive_url, cand['candidate_id'])
                
                # We save raw text as a 'raw_resume_text' field which can be used by the LlamaIndex builder
                cand['raw_resume_text'] = raw_resume_text
                
                # If skills/experience are missing (which they are in ParadigmIT.xlsx), we might need an LLM pass 
                # to extract these from the raw text. For now, we populate placeholders if empty.
                if not cand.get('skills'): cand['skills'] = "Refer to raw resume text"
                if not cand.get('experience'): cand['experience'] = "Refer to raw resume text"
                if not cand.get('projects'): cand['projects'] = "Refer to raw resume text"

                # Ensure links structure 
                github_url = str(cand.get('github_url', ''))
                linkedin_url = str(cand.get('linkedin_url', ''))
                
                if github_url.lower() == 'nan': github_url = ""
                if linkedin_url.lower() == 'nan': linkedin_url = ""

                cand['links'] = {
                    'github': github_url,
                    'linkedin': linkedin_url
                }

            logger.info(f"Successfully parsed {len(candidates)} candidates from {file_path}")
            return candidates

        except Exception as e:
            logger.error(f"Error parsing file {file_path}: {str(e)}")
            raise e

data_ingestion_service = DataIngestionService()
