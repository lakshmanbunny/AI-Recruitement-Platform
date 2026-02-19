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
  const [results, setResults] = useState(null);
  const [isInitializing, setIsInitializing] = useState(true);
  const [healthStatus, setHealthStatus] = useState('unknown');
  const [selectedCandidateId, setSelectedCandidateId] = useState(null);
  const [error, setError] = useState(null);
  const [currentStep, setCurrentStep] = useState(0);

  const STAGES = [
    { id: 0, label: "System Initialization", description: "Setting up recruitment runtime and agent memory..." },
    { id: 1, label: "Data Ingestion", description: "Loading candidate resumes and job specifications..." },
    { id: 2, label: "Semantic Indexing", description: "Generating vector embeddings for candidate profiles..." },
    { id: 3, label: "Neural Retrieval", description: "Performing similarity search across candidate pool..." },
    { id: 4, label: "GitHub Validation", description: "Verifying technical evidence and code quality metrics..." },
    { id: 5, label: "Holistic Evaluation", description: "Running cross-agent technical assessment node..." },
    { id: 6, label: "Readiness Audit", description: "Evaluating production readiness and interview fit..." },
    { id: 7, label: "Skeptic Review", description: "Performing adversarial risk audit and risk detection..." },
    { id: 8, label: "Decision Synthesis", description: "Aggregating agent insights for final hiring consensus..." }
  ];

  const API_BASE = 'http://127.0.0.1:8000/api';

  const checkHealth = async () => {
    try {
      const response = await fetch(`${API_BASE}/health`);
      const data = await response.json();
      setHealthStatus(data.status);
    } catch (err) {
      console.error('Health check failed', err);
      setHealthStatus('error');
    }
  };

  const runScreening = async () => {
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
                setSelectedCandidateId(data.results.ranking[0].candidate_id);
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
      const response = await fetch(`${API_BASE}/results`);
      if (response.ok) {
        const data = await response.json();
        if (data.ranking && data.ranking.length > 0) {
          setResults(data);
          setSelectedCandidateId(data.ranking[0].candidate_id);
          setCurrentStep(8); // Assume completed if we have results
        }
      }
    } catch (err) {
      console.error('Failed to fetch existing results', err);
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

  const value = {
    isScreening,
    results,
    healthStatus,
    selectedCandidateId,
    setSelectedCandidateId,
    error,
    isInitializing,
    runScreening,
    checkHealth,
    submitHRDecision,
    currentStep,
    STAGES
  };

  return (
    <ScreeningContext.Provider value={value}>
      {children}
    </ScreeningContext.Provider>
  );
};
