"""
Stage 2: LLM-Powered GitHub Verification Agent
Uses GitHub Trees API + Gemini 2.5 Pro to intelligently analyze candidate code.

Flow:
  1. Fetch repo list → pick top 3 repos by relevance
  2. Fetch file tree via Trees API → LLM selects top 5 high-signal files
  3. Download raw file content
  4. LLM rubric scoring with [reponame-filename] citations
"""
import json
import httpx
import asyncio
import base64
import re
from typing import Dict, Any, List, Optional
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from langsmith import traceable
from core.settings import settings
from config.logging_config import get_logger

logger = get_logger(__name__)

# Files/dirs to always ignore
NOISE_PATTERNS = {
    ".gitignore", ".gitattributes", ".prettierrc", ".eslintrc",
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    "LICENSE", "LICENSE.md", ".env", ".env.example",
    "node_modules", "__pycache__", ".next", "dist", "build",
    ".vscode", ".idea", ".git",
}
NOISE_EXTENSIONS = {".css", ".scss", ".svg", ".png", ".jpg", ".jpeg", ".gif", ".ico", ".woff", ".woff2", ".ttf", ".map"}


class Stage2GitHubAgent:
    """
    LLM-powered GitHub verification agent.
    Uses Trees API for efficient file discovery and Gemini 2.5 Pro for intelligent analysis.
    """

    def __init__(self):
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-pro",
            google_api_key=settings.GOOGLE_API_KEY,
            temperature=0.1,
            convert_system_message_to_human=True,
        )
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "AI-Recruitment-Stage2",
        }
        if settings.GITHUB_TOKEN:
            self.headers["Authorization"] = f"token {settings.GITHUB_TOKEN}"

    # ──────────────────────────────────────────────
    # GitHub API helpers
    # ──────────────────────────────────────────────

    def extract_github_username(self, url: str) -> Optional[str]:
        if not url:
            return None
        match = re.search(r"github\.com/([a-zA-Z0-9_-]+)", url)
        return match.group(1) if match else None

    def _fetch_repos(self, username: str) -> List[Dict]:
        """Fetch all public repos for a user."""
        url = f"https://api.github.com/users/{username}/repos?per_page=100&sort=updated"
        try:
            with httpx.Client(headers=self.headers, timeout=15.0) as client:
                resp = client.get(url)
                if resp.status_code == 404:
                    logger.warning(f"[STAGE 2] GitHub user {username} not found")
                    return []
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            logger.error(f"[STAGE 2] Failed to fetch repos for {username}: {e}")
            return []

    def _fetch_tree(self, username: str, repo_name: str, branch: str = "main") -> List[Dict]:
        """Fetch the full recursive file tree via Trees API."""
        url = f"https://api.github.com/repos/{username}/{repo_name}/git/trees/{branch}?recursive=1"
        try:
            with httpx.Client(headers=self.headers, timeout=15.0) as client:
                resp = client.get(url)
                if resp.status_code == 404:
                    # Try 'master' branch
                    url2 = f"https://api.github.com/repos/{username}/{repo_name}/git/trees/master?recursive=1"
                    resp = client.get(url2)
                if resp.status_code != 200:
                    return []
                data = resp.json()
                return data.get("tree", [])
        except Exception as e:
            logger.error(f"[STAGE 2] Failed to fetch tree for {repo_name}: {e}")
            return []

    def _download_raw_file(self, username: str, repo_name: str, file_path: str, branch: str = "main") -> str:
        """Download raw file content from GitHub."""
        url = f"https://raw.githubusercontent.com/{username}/{repo_name}/{branch}/{file_path}"
        try:
            with httpx.Client(headers=self.headers, timeout=10.0) as client:
                resp = client.get(url)
                if resp.status_code == 404:
                    url2 = f"https://raw.githubusercontent.com/{username}/{repo_name}/master/{file_path}"
                    resp = client.get(url2)
                if resp.status_code == 200:
                    return resp.text[:4000]  # Cap at 4KB
                return ""
        except Exception as e:
            logger.error(f"[STAGE 2] Failed to download {file_path}: {e}")
            return ""

    def _filter_tree(self, tree: List[Dict]) -> List[str]:
        """Filter the tree to keep only meaningful source files."""
        filtered = []
        for item in tree:
            if item.get("type") != "blob":
                continue
            path = item.get("path", "")
            basename = path.split("/")[-1]

            # Skip noise files
            if basename in NOISE_PATTERNS:
                continue
            # Skip noise extensions
            ext = "." + basename.split(".")[-1] if "." in basename else ""
            if ext in NOISE_EXTENSIONS:
                continue
            # Skip paths containing noise dirs
            if any(noise_dir in path.split("/") for noise_dir in ["node_modules", "__pycache__", ".git", "dist", "build", ".next"]):
                continue
            # Skip very large files (>100KB as indicated by size)
            if item.get("size", 0) > 100000:
                continue

            filtered.append(path)
        return filtered

    # ──────────────────────────────────────────────
    # LLM-powered analysis
    # ──────────────────────────────────────────────

    @traceable(name="Stage 2 - LLM File Selection")
    def _llm_select_files(self, repo_name: str, file_paths: List[str], jd_text: str) -> List[str]:
        """Use LLM to select the top 5 most JD-relevant files from a repo's file tree."""
        if not file_paths:
            return []

        # Cap the file list to prevent token overflow
        paths_str = "\n".join(file_paths[:200])

        system_prompt = """You are a technical recruiter's code analysis assistant.
Given a repository's file tree and a job description, select the TOP 5 files that are most likely
to demonstrate the candidate's technical skills relevant to this job.

SELECTION CRITERIA:
- Prefer source code files (.py, .js, .ts, .java, .go, .rs) over config files
- Prefer files in src/, app/, core/, lib/, api/ directories
- Prefer files that suggest AI/ML, backend, or domain-relevant work
- Ignore test files unless they show sophisticated testing patterns
- Ignore boilerplate (setup.py, __init__.py with no content, etc.)

RESPONSE FORMAT (STRICT JSON — no markdown):
{"selected_files": ["path/to/file1.py", "path/to/file2.js", ...]}

Return at most 5 files. If the repo has fewer meaningful files, return fewer."""

        user_msg = f"""REPOSITORY: {repo_name}

JOB DESCRIPTION:
{jd_text[:2000]}

FILE TREE:
{paths_str}

Select the top 5 most relevant files. Return ONLY valid JSON."""

        try:
            response = self.llm.invoke(
                [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=user_msg),
                ],
                config={
                    "run_name": "stage2-file-selection",
                    "tags": ["stage2", "file-selection"],
                    "metadata": {"repo_name": repo_name},
                },
            )
            content = response.content.strip()
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            result = json.loads(content)
            return result.get("selected_files", [])[:5]
        except Exception as e:
            logger.error(f"[STAGE 2] LLM file selection failed for {repo_name}: {e}")
            # Fallback: pick first 5 .py or .js files
            fallback = [p for p in file_paths if p.endswith((".py", ".js", ".ts"))][:5]
            return fallback

    @traceable(name="Stage 2 - LLM Rubric Scoring")
    def _llm_rubric_score(
        self,
        candidate_id: str,
        jd_text: str,
        repos_data: List[Dict],
    ) -> Dict[str, Any]:
        """Score the candidate's GitHub code against the JD with rubric and citations."""
        # Build code evidence block
        code_block = ""
        for repo in repos_data:
            for f in repo.get("files", []):
                code_block += f"\n--- [{repo['name']}-{f['path']}] ---\n"
                code_block += f["content"][:3000] + "\n"

        if not code_block.strip():
            return self._empty_result("No code files found")

        system_prompt = """You are an enterprise-grade AI code reviewer for recruitment.
Evaluate the candidate's GitHub code against the Job Description.

RUBRIC (each 0-25, total github_score = sum of all four, 0-100):
- code_quality: Clean code, proper structure, error handling, documentation
- jd_relevance: How well the code demonstrates skills required by the JD
- complexity: Sophistication of algorithms, architecture, and problem-solving
- best_practices: Design patterns, testing, security, performance awareness

RULES:
1. Score ONLY what you can see in the code. Do NOT assume.
2. Every strength and weakness MUST include a citation tag [reponame-filename] at the END.
3. Be strict — tutorial-level code should score LOW.
4. Provide specific code references in your justification.

RESPONSE FORMAT (STRICT JSON — no markdown):
{
  "github_score": <int 0-100, sum of rubric>,
  "rubric_scores": {
    "code_quality": <int 0-25>,
    "jd_relevance": <int 0-25>,
    "complexity": <int 0-25>,
    "best_practices": <int 0-25>
  },
  "strengths": [
    "✔ <strength with specific code reference> [reponame-filename]"
  ],
  "weaknesses": [
    "⚠ <weakness with specific detail> [reponame-filename]"
  ],
  "github_justification": "<2-3 sentence summary of the candidate's GitHub profile quality>"
}"""

        user_msg = f"""CANDIDATE ID: {candidate_id}

JOB DESCRIPTION:
{jd_text[:2000]}

CANDIDATE'S CODE FROM GITHUB:
{code_block[:12000]}

Evaluate this code against the JD. Return ONLY valid JSON."""

        try:
            response = self.llm.invoke(
                [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=user_msg),
                ],
                config={
                    "run_name": "stage2-rubric-scoring",
                    "tags": ["stage2", "rubric-scoring"],
                    "metadata": {"candidate_id": candidate_id},
                },
            )
            content = response.content.strip()
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            return json.loads(content)
        except Exception as e:
            logger.error(f"[STAGE 2] LLM rubric scoring failed for {candidate_id}: {e}")
            return self._empty_result(str(e))

    # ──────────────────────────────────────────────
    # Main evaluation pipeline
    # ──────────────────────────────────────────────

    @traceable(name="Stage 2 GitHub Agent - Full Evaluation")
    def evaluate(self, candidate_id: str, github_url: str, jd_text: str) -> Dict[str, Any]:
        """
        Full Stage 2 evaluation for a single candidate.
        Returns github_score, rubric_scores, strengths, weaknesses, repos, code_evidence.
        """
        username = self.extract_github_username(github_url)
        if not username:
            logger.warning(f"[STAGE 2] No GitHub username for {candidate_id}")
            return self._empty_result("No GitHub URL found")

        logger.info(f"[STAGE 2] Evaluating {candidate_id} (GitHub: {username})")

        # 1. Fetch repos
        repos = self._fetch_repos(username)
        if not repos:
            return self._empty_result("No repositories found")

        # Pick top 3 repos by stars + recency
        ai_keywords = ["ai", "ml", "llm", "rag", "langchain", "pytorch", "tensorflow", "agent", "transformer", "neural", "deep"]
        scored_repos = []
        for r in repos:
            name_desc = ((r.get("name") or "") + " " + (r.get("description") or "")).lower()
            ai_bonus = 50 if any(k in name_desc for k in ai_keywords) else 0
            score = (r.get("stargazers_count", 0) * 10) + (r.get("size", 0) / 100) + ai_bonus
            if not r.get("fork", False):
                scored_repos.append((r, score))

        scored_repos.sort(key=lambda x: x[1], reverse=True)
        top_repos = [r for r, _ in scored_repos[:3]]

        if not top_repos:
            return self._empty_result("No non-fork repositories found")

        # 2. For each repo: fetch tree → LLM file selection → download files
        repos_data = []
        code_evidence = []
        repo_links = []

        for repo in top_repos:
            repo_name = repo["name"]
            repo_url = repo.get("html_url", f"https://github.com/{username}/{repo_name}")

            logger.info(f"[STAGE 2] Analyzing repo: {username}/{repo_name}")

            # Fetch file tree
            tree = self._fetch_tree(username, repo_name)
            filtered_paths = self._filter_tree(tree)

            if not filtered_paths:
                logger.info(f"[STAGE 2] No meaningful files in {repo_name}")
                continue

            # LLM selects top 5 files
            selected_files = self._llm_select_files(repo_name, filtered_paths, jd_text)
            logger.info(f"[STAGE 2] Selected files from {repo_name}: {selected_files}")

            # Download selected files
            repo_files = []
            for fpath in selected_files:
                content = self._download_raw_file(username, repo_name, fpath)
                if content:
                    repo_files.append({
                        "path": fpath,
                        "content": content,
                    })
                    code_evidence.append({
                        "repo_name": repo_name,
                        "repo_url": repo_url,
                        "file_path": fpath,
                        "file_url": f"{repo_url}/blob/main/{fpath}",
                        "code_snippet": content[:2000],
                        "language": fpath.split(".")[-1] if "." in fpath else "text",
                    })

            repos_data.append({
                "name": repo_name,
                "url": repo_url,
                "description": repo.get("description", ""),
                "files": repo_files,
            })

            repo_links.append({
                "name": repo_name,
                "url": repo_url,
                "description": repo.get("description", ""),
                "stars": repo.get("stargazers_count", 0),
                "language": repo.get("language", "Unknown"),
            })

        if not repos_data:
            return self._empty_result("Could not fetch files from any repository")

        # 3. LLM rubric scoring
        scoring_result = self._llm_rubric_score(candidate_id, jd_text, repos_data)

        # 4. Package final output
        result = {
            "github_score": scoring_result.get("github_score", 0),
            "rubric_scores": scoring_result.get("rubric_scores", {}),
            "strengths": scoring_result.get("strengths", []),
            "weaknesses": scoring_result.get("weaknesses", []),
            "github_justification": scoring_result.get("github_justification", ""),
            "repos": repo_links,
            "code_evidence": code_evidence,
            "repo_count": len(repos),
            "ai_projects": len([r for r in repos if any(
                k in ((r.get("name") or "") + " " + (r.get("description") or "")).lower()
                for k in ai_keywords
            )]),
            "github_username": username,
        }

        logger.info(f"[STAGE 2] {candidate_id}: GitHub Score={result['github_score']}")
        return result

    async def evaluate_async(self, candidate_id: str, github_url: str, jd_text: str) -> Dict[str, Any]:
        """Async wrapper for concurrent batch processing."""
        return await asyncio.to_thread(self.evaluate, candidate_id, github_url, jd_text)

    def _empty_result(self, reason: str) -> Dict[str, Any]:
        return {
            "github_score": 0,
            "rubric_scores": {"code_quality": 0, "jd_relevance": 0, "complexity": 0, "best_practices": 0},
            "strengths": [],
            "weaknesses": [f"⚠ {reason}"],
            "github_justification": reason,
            "repos": [],
            "code_evidence": [],
            "repo_count": 0,
            "ai_projects": 0,
            "github_username": None,
        }
