import { createContext, useContext, useState, useEffect } from 'react';

const ScreeningContext = createContext();

export const useScreening = () => {
  const context = useContext(ScreeningContext);
  if (!context) {
    throw new Error('useScreening must be used within a ScreeningProvider');
  }
  return context;
};

export const ScreeningProvider = ({ children }) => {
  const [isScreening, setIsScreening] = useState(false);
  const [isRunningStage2, setIsRunningStage2] = useState(false);
  const [results, setResults] = useState(null);
  const [isInitializing, setIsInitializing] = useState(true);
  const [healthStatus, setHealthStatus] = useState('unknown');
  const [selectedCandidateId, setSelectedCandidateId] = useState(null);
  const [error, setError] = useState(null);
  const [currentStep, setCurrentStep] = useState(0);

  const STAGES = [
    { id: 0, label: "System Initialization", description: "Setting up 3-Stage Funnel runtime..." },
    { id: 1, label: "Loading Candidate Data", description: "Ingesting candidate resumes and job specifications..." },
    { id: 2, label: "Stage 1: Flash Extraction & Scoring", description: "Gemini 2.0 Flash scoring all candidates against JD..." },
    { id: 3, label: "Funnel Gate: Shortlisting Top 60", description: "Filtering top candidates by base score..." },
    { id: 4, label: "Stage 2: GitHub Verification", description: "Verifying technical evidence from GitHub repos..." },
    { id: 5, label: "Stage 3: Enterprise Agent Evaluation", description: "Running unified evaluation, readiness, and skeptic agents..." },
    { id: 6, label: "Finalizing Results", description: "Persisting results and generating rankings..." },
  ];

  const API_BASE = 'http://localhost:8000/api';

  const checkHealth = async () => {
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 5000);

      const response = await fetch(`${API_BASE}/health`, { signal: controller.signal });
      clearTimeout(timeoutId);

      const data = await response.json();
      setHealthStatus(data.status);
    } catch (err) {
      console.error('Health check failed', err);
      setHealthStatus('error');
    }
  };

  const runScreening = async (evaluation_weights = null) => {
    setIsScreening(true);
    setResults(null);
    setCurrentStep(0);
    setError(null);

    try {
      const response = await fetch(`${API_BASE}/screen-stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ evaluation_weights }),
      });

      if (!response.ok) throw new Error('Failed to start screening');

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop(); // Keep potential partial line in buffer

        for (const line of lines) {
          if (!line.trim()) continue;
          try {
            const data = JSON.parse(line);

            if (data.error) {
              throw new Error(data.error);
            }

            if (data.step !== undefined) {
              setCurrentStep(data.step);
            }

            if (data.results) {
              setResults(data.results);
              if (data.results.ranking && data.results.ranking.length > 0) {
                setSelectedCandidateId(prev => prev || data.results.ranking[0].candidate_id);
              }
            }

            // Handle incremental batch updates (partial results)
            if (data.partial_results) {
              setResults(data.partial_results);
              if (!selectedCandidateId && data.partial_results.ranking && data.partial_results.ranking.length > 0) {
                setSelectedCandidateId(data.partial_results.ranking[0].candidate_id);
              }
            }
          } catch (e) {
            console.error('Error parsing stream chunk:', e);
          }
        }
      }

      setIsScreening(false);
    } catch (err) {
      console.error('Screening error:', err);
      setError(err.message);
      setIsScreening(false);
    }
  };

  const fetchResults = async () => {
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 10000);

      const response = await fetch(`${API_BASE}/results`, { signal: controller.signal });
      clearTimeout(timeoutId);

      if (response.ok) {
        const data = await response.json();
        if (data.ranking && data.ranking.length > 0) {
          setResults(data);
          setSelectedCandidateId(data.ranking[0].candidate_id);
          setCurrentStep(6); // Assume completed if we have results
        }
      } else {
        setError(`Backend responded with status: ${response.status}`);
      }
    } catch (err) {
      console.error('Failed to fetch existing results', err);
      setError(err.name === 'AbortError' ? 'Initialization timeout' : err.message);
    } finally {
      setIsInitializing(false);
    }
  };

  useEffect(() => {
    checkHealth();
    fetchResults();
    // Poll for health status every 10 seconds
    const interval = setInterval(checkHealth, 10000);
    return () => clearInterval(interval);
  }, []);

  const submitHRDecision = async (candidate_id, decision, notes) => {
    try {
      const response = await fetch(`${API_BASE}/hr-decision`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ candidate_id, decision, notes }),
      });
      if (!response.ok) throw new Error('Failed to submit HR decision');
      const data = await response.json();

      // Update local state results with the new decision
      if (results && results.evaluations[candidate_id]) {
        const updatedEvaluations = { ...results.evaluations };
        updatedEvaluations[candidate_id] = {
          ...updatedEvaluations[candidate_id],
          hr_decision: data.hr_decision
        };
        setResults({ ...results, evaluations: updatedEvaluations });
      }
      return data;
    } catch (err) {
      console.error('HR Decision error:', err);
      setError(err.message);
      throw err;
    }
  };

  const [isForceEvaluating, setIsForceEvaluating] = useState(false);

  const forceEvaluate = async (candidateId, evaluation_weights = null) => {
    setIsForceEvaluating(true);
    setError(null);

    try {
      const response = await fetch(`${API_BASE}/force-evaluate/${candidateId}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ evaluation_weights }),
      });

      if (!response.ok) throw new Error('Force evaluation failed');

      // After agent runs, always fetch fresh full results so ranking updates correctly
      const freshRes = await fetch(`${API_BASE}/results`);
      if (!freshRes.ok) throw new Error('Failed to refresh results after evaluation');

      const freshData = await freshRes.json();
      setResults(freshData);
      setSelectedCandidateId(candidateId);
      return freshData;
    } catch (err) {
      console.error('Force evaluation error:', err);
      setError(err.message);
      throw err;
    } finally {
      setIsForceEvaluating(false);
    }
  };

  const toggleRagOverride = async (candidateId, override) => {
    try {
      const response = await fetch(`${API_BASE}/rag-override/${candidateId}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ override }),
      });

      if (!response.ok) throw new Error('Failed to toggle RAG override');

      const data = await response.json();

      if (results && results.evaluations[candidateId]) {
        const updatedEvaluations = { ...results.evaluations };
        updatedEvaluations[candidateId] = {
          ...updatedEvaluations[candidateId],
          rag_override: data.rag_override
        };
        setResults({ ...results, evaluations: updatedEvaluations });
      }
      return data;
    } catch (err) {
      console.error('Toggle RAG Override error:', err);
      setError(err.message);
      throw err;
    }
  };

  const runStage2 = async () => {
    setIsRunningStage2(true);
    setError(null);

    try {
      const response = await fetch(`${API_BASE}/run-stage-2-stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });

      if (!response.ok) throw new Error(`Stage 2 failed: ${response.status}`);

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop();

        for (const line of lines) {
          if (!line.trim()) continue;
          try {
            const data = JSON.parse(line);
            if (data.error) throw new Error(data.error);
            if (data.step !== undefined) setCurrentStep(data.step);

            if (data.partial_results || data.results) {
              const incoming = data.partial_results || data.results;
              setResults(prev => {
                if (!prev) return incoming;
                // Merge: update evaluations, replace ranking
                const mergedEvals = { ...(prev.evaluations || {}), ...(incoming.evaluations || {}) };
                return {
                  ranking: incoming.ranking || prev.ranking,
                  evaluations: mergedEvals,
                };
              });
            }
          } catch (e) {
            console.error('Stage 2 stream parse error:', e);
          }
        }
      }
    } catch (err) {
      console.error('Stage 2 error:', err);
      setError(err.message);
    } finally {
      setIsRunningStage2(false);
    }
  };

  const value = {
    isScreening,
    isRunningStage2,
    isForceEvaluating,
    results,
    healthStatus,
    selectedCandidateId,
    setSelectedCandidateId,
    error,
    isInitializing,
    runScreening,
    runStage2,
    checkHealth,
    submitHRDecision,
    forceEvaluate,
    toggleRagOverride,
    currentStep,
    STAGES
  };

  return (
    <ScreeningContext.Provider value={value}>
      {children}
    </ScreeningContext.Provider>
  );
};
