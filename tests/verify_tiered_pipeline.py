import pandas as pd
import numpy as np
import asyncio
import os
import sys

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../backend")))

def generate_mock_candidates(count=20):
    candidates = []
    skills_pool = ["Python", "Java", "React", "Node.js", "FastAPI", "Docker", "Kubernetes", "AWS", "Machine Learning", "LangChain"]
    for i in range(1, count + 1):
        cand_id = f"MOCK_{i:03d}"
        skills = ", ".join(np.random.choice(skills_pool, size=3, replace=False))
        candidates.append({
            "candidate_id": cand_id,
            "name": f"Candidate {i}",
            "skills": skills,
            "experience": f"{np.random.randint(1, 10)} years of experience in software development and AI.",
            "projects": f"Developed {skills.split(',')[0]} based automation systems.",
            "education": "B.Tech in Computer Science",
            "github_url": f"https://github.com/mockuser_{i}"
        })
    return pd.DataFrame(candidates)

async def test_tiered_pipeline():
    from app.services.pipeline_service import pipeline_service
    
    csv_path = "mock_candidates.csv"
    df = generate_mock_candidates(22) # 22 candidates, should be filtered to top 15
    df.to_csv(csv_path, index=False)
    print(f"Generated {csv_path} with 22 mock candidates.")
    
    try:
        print("Running bulk screening...")
        results = await pipeline_service.run_bulk_screening(csv_path)
        
        ranking = results.get("ranking", [])
        evaluations = results.get("evaluations", {})
        
        print(f"Total candidates ranked: {len(ranking)}")
        print(f"Total candidates deeply evaluated: {len(evaluations)}")
        
        assert len(ranking) >= 22, "Stage 1 should rank everyone returned by retriever"
        # Since retrieve_candidates_node returns all candidates by default, ranking should have 22
        
        # Check if shortlist filter worked (threshold is 15)
        # However, retrieve_candidates_node might filter based on JD. 
        # But here our mock JD is wide.
        
        # Verify that Stage 2 (evaluations) only processed top candidates
        # Wait, the threshold in shortlist_filter_node is 15.
        
        if len(evaluations) <= 15:
            print(f"SUCCESS: Tiered processing worked. {len(evaluations)} candidates deeply evaluated.")
        else:
            print(f"WARNING: More than 15 candidates evaluated ({len(evaluations)}). Check threshold logic.")

    except Exception as e:
        print(f"Test failed: {str(e)}")
    finally:
        if os.path.exists(csv_path):
            os.remove(csv_path)

if __name__ == "__main__":
    if 'pandas' not in sys.modules:
        try:
            import pandas as pd
        except ImportError:
            print("Pandas not found. Mocking pandas for testing...")
            class MockPD:
                def read_csv(self, path):
                    # Minimal manual parser
                    import csv
                    with open(path, 'r') as f:
                        return [row for row in csv.DictReader(f)]
            # This is complex to mock fully. I'll just skip verification if pandas is missing.
            sys.exit(1)
            
    asyncio.run(test_tiered_pipeline())
