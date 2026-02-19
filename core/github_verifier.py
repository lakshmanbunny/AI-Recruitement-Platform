import httpx
import json
import re
import base64
from typing import List, Dict, Tuple
from core.llm_service import LLMService
from core.settings import settings
from config.logging_config import get_logger

logger = get_logger(__name__)

class GitHubVerifier:
    """
    Analyzes candidate GitHub profiles via an explainable 4-layer architecture.
    Now includes Content Extraction for Code Intelligence and authenticated requests.
    """
    def __init__(self):
        self.llm_service = LLMService()
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "Hiring-System-POC"
        }
        if settings.GITHUB_TOKEN:
            self.headers["Authorization"] = f"token {settings.GITHUB_TOKEN}"

    def extract_github_username(self, url: str) -> str | None:
        """Parses username from github.com/username or github.com/username/."""
        if not url:
            return None
        match = re.search(r"github\.com/([a-zA-Z0-9-]+)", url)
        return match.group(1) if match else None

    def fetch_repos(self, username: str) -> List[Dict]:
        """Fetches repositories from GitHub API (Synchronous)."""
        url = f"https://api.github.com/users/{username}/repos"
        logger.info(f"Fetching GitHub repos for {username}")
        try:
            with httpx.Client(headers=self.headers) as client:
                response = client.get(url, timeout=15.0)
                if response.status_code == 404:
                    logger.warning(f"GitHub user {username} not found")
                    return []
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Failed to fetch repos for {username}: {str(e)}")
            return []

    def fetch_readme(self, username: str, repo_name: str) -> str:
        """Fetches and decodes README content for a repository."""
        url = f"https://api.github.com/repos/{username}/{repo_name}/readme"
        try:
            with httpx.Client(headers=self.headers) as client:
                response = client.get(url, timeout=10.0)
                if response.status_code == 404:
                    return ""
                response.raise_for_status()
                data = response.json()
                content_b64 = data.get("content", "")
                return base64.b64decode(content_b64).decode("utf-8", errors="ignore")
        except Exception as e:
            logger.error(f"Failed to fetch README for {repo_name}: {str(e)}")
            return ""

    def fetch_code_snippets(self, username: str, repo_name: str) -> List[str]:
        """Fetches up to 3 code snippets from a repository (prefer .py, .js, .ipynb)."""
        url = f"https://api.github.com/repos/{username}/{repo_name}/contents"
        snippets = []
        target_exts = [".py", ".js", ".ipynb"]
        
        try:
            with httpx.Client(headers=self.headers) as client:
                response = client.get(url, timeout=10.0)
                if response.status_code != 200:
                    return []
                contents = response.json()
                
                # Filter for priority files
                files = [c for c in contents if c.get("type") == "file"]
                priority_files = [f for f in files if any(f.get("name", "").endswith(ext) for ext in target_exts)]
                other_files = [f for f in files if f not in priority_files]
                
                selected_files = (priority_files + other_files)[:3]
                
                for f in selected_files:
                    f_url = f.get("download_url")
                    if f_url:
                        # Headers are important even for download urls if they are private or hit limits
                        f_res = client.get(f_url, timeout=10.0)
                        if f_res.status_code == 200:
                            snippets.append(f_res.text[:2000]) # Cap snippet size
        except Exception as e:
            logger.error(f"Failed to fetch snippets for {repo_name}: {str(e)}")
            
        return snippets

    def analyze_repos(self, repos: List[Dict], username: str, evidence: List[Dict] = None) -> Tuple[Dict, Dict, Dict]:
        """
        3-Layer analysis: Raw Data -> Features -> Content Extraction. Evaluation is handled externally.
        """
        # 1. RAW DATA LAYER
        ai_keywords = ["ai", "ml", "llm", "rag", "langchain", "langgraph", "tensorflow", "pytorch", "genai", "agent", "transformer", "neural", "deep"]
        
        raw_data = {
            "username": username,
            "total_repos": len(repos),
            "repo_names": [r.get("name") for r in repos],
            "languages_used": list(set(r.get("language") for r in repos if r.get("language"))),
            "total_stars": sum(r.get("stargazers_count", 0) for r in repos),
            "total_forks": sum(r.get("forks_count", 0) for r in repos),
            "ai_relevant_repos": [r.get("name") for r in repos if any(k in (r.get("name") or "").lower() or k in (r.get("description") or "").lower() for k in ai_keywords)]
        }

        if not repos:
            return raw_data, {"activity_score": 0, "ai_relevance_score": 0, "repo_count": 0}, {"repos": []}

        # 2. FEATURE ENGINEERING LAYER
        ai_projects = [r for r in repos if any(k in (r.get("name") or "").lower() or k in (r.get("description") or "").lower() for k in ai_keywords)]
        ai_project_count = len(ai_projects)
        
        activity_score = min(100, (len(repos) * 10) + (raw_data["total_stars"] * 2) + (raw_data["total_forks"] * 5))
        ai_relevance_score = min(100, ai_project_count * 25)

        features = {
            "repo_count": len(repos),
            "ai_project_count": ai_project_count,
            "activity_score": activity_score,
            "ai_relevance_score": ai_relevance_score,
            "languages_match_count": len(raw_data["languages_used"])
        }

        # 3. CONTENT EXTRACTION LAYER (Top 3 AI repos)
        top_ai_repos = sorted(ai_projects, key=lambda x: x.get("stargazers_count", 0), reverse=True)[:3]
        code_data = {"repos": []}
        
        for r in top_ai_repos:
            repo_name = r.get("name")
            logger.info(f"Extracting content for {username}/{repo_name}")
            readme = self.fetch_readme(username, repo_name)
            snippets = self.fetch_code_snippets(username, repo_name)
            
            code_data["repos"].append({
                "name": repo_name,
                "url": r.get("html_url"),
                "description": r.get("description"),
                "readme": readme[:5000], # Cap size
                "code_snippets": snippets
            })

        # 4. DATA PACKAGING (Evaluation removed, now handled by Unified Agent)
        return raw_data, features, code_data
