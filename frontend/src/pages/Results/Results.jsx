import React from 'react';
import { useScreening } from '../../context/ScreeningContext';
import { Award, Code, Database, FileText, MessageSquare, ExternalLink, ShieldAlert, ShieldCheck, ChevronDown, ChevronRight, Github, Terminal, Search, CheckCircle, RotateCw, Zap, ArrowLeft } from 'lucide-react';
import CandidateGrid from './CandidateGrid';

const CollapsibleSection = ({ title, icon: Icon, children, defaultOpen = false, count }) => {
    const [isOpen, setIsOpen] = React.useState(defaultOpen);
    return (
        <div className={`flex flex-col border border-gray-100 rounded-3xl overflow-hidden transition-all duration-300 mb-6 ${isOpen ? 'bg-white shadow-xl shadow-gray-50' : 'bg-gray-50/50 hover:bg-white hover:shadow-md'}`}>
            <button
                onClick={() => setIsOpen(!isOpen)}
                className="flex items-center justify-between p-6 w-full text-left transition-colors"
            >
                <div className="flex items-center gap-4">
                    <div className={`p-2 rounded-xl ${isOpen ? 'bg-primary-blue text-white' : 'bg-white border border-gray-100 text-gray-400'}`}>
                        <Icon size={20} />
                    </div>
                    <div className="flex items-center gap-3">
                        <h3 className="text-base font-black text-[#1A1A1A] uppercase tracking-wider">{title}</h3>
                        {count !== undefined && (
                            <span className={`px-2 py-0.5 rounded-full text-[10px] font-black ${isOpen ? 'bg-blue-50 text-primary-blue' : 'bg-white text-gray-400 border border-gray-100'}`}>
                                {count}
                            </span>
                        )}
                    </div>
                </div>
                {isOpen ? <ChevronDown size={20} className="text-gray-400" /> : <ChevronRight size={20} className="text-gray-400" />}
            </button>
            {isOpen && (
                <div className="px-6 pb-8 pt-2 animate-in fade-in slide-in-from-top-2 duration-300">
                    {children}
                </div>
            )}
        </div>
    );
};

const BulletList = ({ items, variant = 'info' }) => {
    if (!items || !Array.isArray(items)) return null;
    return (
        <ul className="flex flex-col gap-3">
            {items.map((item, i) => (
                <li key={i} className="flex items-start gap-3 bg-white p-3 rounded-xl border border-gray-50 shadow-sm border-l-4 border-l-primary-blue/30">
                    <div className={`mt-1.5 shrink-0 w-1.5 h-1.5 rounded-full ${variant === 'success' ? 'bg-success-text' :
                        variant === 'danger' ? 'bg-red-500' :
                            variant === 'warning' ? 'bg-orange-500' : 'bg-primary-blue'
                        }`} />
                    <span className="text-sm font-medium text-slate-700 leading-relaxed">{item}</span>
                </li>
            ))}
        </ul>
    );
};

const Results = () => {
    const {
        results,
        selectedCandidateId,
        setSelectedCandidateId,
        submitHRDecision,
        runScreening,
        runStage2,
        isRunningStage2,
        forceEvaluate,
        toggleRagOverride,
        isForceEvaluating
    } = useScreening();

    const [bgJobStatus, setBgJobStatus] = React.useState(null);
    const [hrNotes, setHrNotes] = React.useState('');
    const [isSubmitting, setIsSubmitting] = React.useState(false);
    const [retrievalMetrics, setRetrievalMetrics] = React.useState(null);

    // Enterprise LLM Audit States
    const [llmMetrics, setLlmMetrics] = React.useState(null);
    const [llmJobStatus, setLlmJobStatus] = React.useState(null);
    const [isTriggeringLlmEval, setIsTriggeringLlmEval] = React.useState(false);

    // HR Configurable Evaluation Weights
    const [evaluationWeights, setEvaluationWeights] = React.useState({
        resume_match: 0.40,
        github_quality: 0.30,
        experience_depth: 0.15,
        skill_relevance: 0.15
    });

    if (!results) return null;

    // Derived data
    const selectedCandidate = results.evaluations[selectedCandidateId];
    const selectedCandidateBasic = results.ranking.find(c => c.candidate_id === selectedCandidateId);

    // Detailed Retrieval Metrics Polling
    React.useEffect(() => {
        if (!selectedCandidateId) return;

        const fetchMetrics = async () => {
            try {
                // 1. Fetch Deterministic Metrics
                const res = await fetch(`http://localhost:8000/api/rag/retrieval-metrics/${selectedCandidateId}`);
                if (res.ok) {
                    const data = await res.json();
                    setRetrievalMetrics(data);
                }

                // 2. Fetch LLM-based Audit Metrics
                const llmRes = await fetch(`http://localhost:8000/api/rag/llm-metrics/${selectedCandidateId}`);
                if (llmRes.ok) {
                    const llmData = await llmRes.json();
                    setLlmMetrics(llmData);
                }

                // 3. Check LLM Job Status
                const jobRes = await fetch(`http://localhost:8000/api/rag/llm-evaluation-status/${selectedCandidateId}`);
                if (jobRes.ok) {
                    const jobData = await jobRes.json();
                    setLlmJobStatus(jobData);
                }
            } catch (e) {
                console.error("Failed to fetch evaluation metrics", e);
            }
        };

        fetchMetrics();
        const interval = setInterval(fetchMetrics, 5000);
        return () => clearInterval(interval);
    }, [selectedCandidateId]);

    // Background Evaluation Status Polling (Workflow/Indexing)
    React.useEffect(() => {
        if (!selectedCandidateId) return;

        const checkStatus = async () => {
            try {
                const res = await fetch(`http://localhost:8000/api/rag/evaluation-status/${selectedCandidateId}`);
                if (res.ok) {
                    const data = await res.json();
                    setBgJobStatus(data);
                }
            } catch (e) {
                console.error("Status check failed", e);
            }
        };

        checkStatus();
        const statusInterval = setInterval(checkStatus, 5000 * 2);
        return () => clearInterval(statusInterval);
    }, [selectedCandidateId]);

    const runLlmEvaluation = async () => {
        setIsTriggeringLlmEval(true);
        setLlmMetrics(null); // Clear previous metrics to show loading state
        setLlmJobStatus({ status: 'PENDING' }); // Set optimistic pending status
        try {
            const res = await fetch(`http://localhost:8000/api/rag/run-llm-evaluation`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ candidate_ids: [selectedCandidateId], evaluation_weights: evaluationWeights })
            });
            if (res.ok) {
                const job = await res.json();
                setLlmJobStatus(job);
            }
        } catch (e) {
            console.error("Failed to trigger LLM audit", e);
        } finally {
            setIsTriggeringLlmEval(false);
        }
    };
    if (!selectedCandidateId) {
        return (
            <div className="flex flex-col flex-1">
                {/* Stage 2 Button — at the top of candidate grid */}
                <div className="max-w-7xl w-full mx-auto px-6 pt-4">
                    <div className="p-5 bg-gradient-to-r from-gray-900 to-gray-800 rounded-2xl border border-gray-700 flex items-center justify-between">
                        <div className="flex flex-col gap-1">
                            <h3 className="text-white text-sm font-black uppercase tracking-widest">Stage 2: GitHub Verification</h3>
                            <p className="text-gray-400 text-xs font-medium">Analyze top 60 candidates' GitHub repos with AI-powered code review (Gemini 2.5 Pro)</p>
                        </div>
                        <button
                            onClick={() => runStage2()}
                            disabled={isRunningStage2}
                            className="px-6 py-3 bg-white text-gray-900 text-[11px] font-black uppercase tracking-widest rounded-xl hover:bg-gray-100 transition-all disabled:opacity-50 flex items-center gap-2 shadow-lg"
                        >
                            {isRunningStage2 ? (
                                <><RotateCw size={14} className="animate-spin" /> Verifying...</>
                            ) : (
                                <><Github size={14} /> Run Stage 2</>
                            )}
                        </button>
                    </div>
                </div>
                <CandidateGrid results={results} onSelectCandidate={setSelectedCandidateId} />
            </div>
        );
    }

    return (
        <div className="flex flex-col flex-1 overflow-hidden h-[calc(100vh-64px-60px)]">
            {/* Main Content - Full Width Detail View */}
            <main className="flex-1 bg-white overflow-y-auto">
                {selectedCandidate ? (
                    <div className="max-w-5xl mx-auto p-6 md:p-10 w-full">
                        <button
                            onClick={() => setSelectedCandidateId(null)}
                            className="mb-8 flex items-center gap-2 text-sm font-black uppercase tracking-widest text-gray-400 hover:text-primary-blue transition-colors group w-max"
                        >
                            <div className="bg-gray-50 border border-gray-100 p-1.5 rounded-lg group-hover:border-blue-100 group-hover:bg-blue-50 transition-colors">
                                <ArrowLeft size={16} />
                            </div>
                            Back to Pipeline Grid
                        </button>

                        {!selectedCandidate.final_synthesized_decision && (
                            <div className={`mb-8 p-4 rounded-2xl border flex flex-col md:flex-row items-center justify-between gap-4 shadow-sm transition-all duration-300 ${selectedCandidate.evaluation_blocked ? 'bg-red-50/50 border-red-100' : 'bg-blue-50/50 border-blue-100'}`}>
                                <div className="flex items-center gap-4">
                                    <div className={`p-2.5 rounded-xl shadow-sm ${selectedCandidate.evaluation_blocked ? 'bg-red-500 text-white' : 'bg-primary-blue text-white'}`}>
                                        {bgJobStatus?.status === 'RUNNING' || bgJobStatus?.status === 'PENDING' ? (
                                            <RotateCw size={20} className="animate-spin" />
                                        ) : selectedCandidate.evaluation_blocked ? (
                                            <ShieldAlert size={20} />
                                        ) : (
                                            <ShieldCheck size={20} />
                                        )}
                                    </div>
                                    <div className="flex flex-col">
                                        <div className="flex items-center gap-2">
                                            <h3 className={`text-xs font-black uppercase tracking-[0.15em] ${selectedCandidate.evaluation_blocked ? 'text-red-700' : 'text-primary-blue'}`}>
                                                {bgJobStatus?.status === 'RUNNING' || bgJobStatus?.status === 'PENDING' ? 'Audit In Progress' : selectedCandidate.evaluation_blocked ? 'Safety Gate: Blocked' : 'Safety Gate: Active'}
                                            </h3>
                                            {selectedCandidate.evaluation_blocked && (
                                                <span className="px-1.5 py-0.5 bg-red-600 text-white text-[8px] font-black rounded uppercase">Quality Lock</span>
                                            )}
                                        </div>
                                        <p className="text-[11px] font-bold text-gray-500 leading-tight mt-0.5 max-w-md">
                                            {bgJobStatus?.status === 'RUNNING' || bgJobStatus?.status === 'PENDING'
                                                ? 'Our agents are currently profiling the candidate data.'
                                                : selectedCandidate.evaluation_blocked
                                                    ? 'Insufficient retrieval signatures. Deep evaluation suspended to prevent hallucination.'
                                                    : 'Retrieval quality validated. Candidate eligible for deep-context AI screening.'}
                                        </p>
                                    </div>
                                </div>
                                <div className="flex items-center gap-3">
                                    <button
                                        onClick={() => forceEvaluate(selectedCandidateId, evaluationWeights)}
                                        disabled={bgJobStatus?.status === 'RUNNING' || bgJobStatus?.status === 'PENDING' || isForceEvaluating || isTriggeringLlmEval}
                                        className={`px-5 py-2.5 rounded-xl font-black text-[10px] uppercase tracking-widest shadow-sm transition-all flex items-center gap-2 ${selectedCandidate.evaluation_blocked
                                            ? 'bg-white text-red-600 border border-red-100 hover:bg-red-50'
                                            : 'bg-primary-blue text-white hover:bg-blue-700 shadow-blue-100'} disabled:opacity-50`}
                                    >
                                        {(isForceEvaluating || isTriggeringLlmEval) ? (
                                            <RotateCw size={14} className="animate-spin" />
                                        ) : selectedCandidate.evaluation_blocked ? (
                                            <Zap size={14} />
                                        ) : (
                                            <CheckCircle size={14} />
                                        )}
                                        {isForceEvaluating ? 'Evaluating...' : isTriggeringLlmEval ? 'Processing' : selectedCandidate.evaluation_blocked ? 'Force Run Agents' : 'Execute AI Audit'}
                                    </button>
                                </div>
                            </div>
                        )}

                        <header className="mb-10">
                            <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
                                <div className="flex flex-col gap-1">
                                    <h1 className="text-3xl md:text-5xl font-black tracking-tight text-[#1A1A1A]">{selectedCandidateBasic?.name}</h1>
                                    <p className="text-xl text-gray-500 font-medium">Top-tier technical profile validated by AI Audit.</p>
                                </div>
                                <div className="flex flex-col items-center md:items-end gap-2">
                                    <span className="text-[10px] font-bold text-gray-400 uppercase tracking-widest">Global Rank</span>
                                    <div className="w-14 h-14 bg-primary-blue text-white rounded-2xl flex items-center justify-center text-2xl font-black shadow-lg shadow-blue-100">
                                        #{selectedCandidateBasic?.rank}
                                    </div>
                                </div>
                            </div>
                        </header>

                        {
                            selectedCandidate.final_synthesized_decision && (
                                <section className="mb-12">
                                    <div className="p-1 bg-gradient-to-r from-blue-600 to-indigo-600 rounded-[2rem] shadow-xl shadow-blue-50">
                                        <div className="bg-white rounded-[1.9rem] p-8 md:p-10 flex flex-col gap-8">
                                            <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-6 border-b border-gray-100 pb-8">
                                                <div className="flex items-center gap-4">
                                                    <div className="p-3 bg-blue-50 rounded-2xl text-primary-blue">
                                                        <ShieldCheck size={32} />
                                                    </div>
                                                    <div className="flex flex-col">
                                                        <span className="text-[11px] font-black text-primary-blue uppercase tracking-[0.2em]">Final Hiring Decision</span>
                                                        <h2 className={`text-3xl md:text-4xl font-black ${selectedCandidate.final_synthesized_decision.final_decision.includes('REJECT') || selectedCandidate.final_synthesized_decision.final_decision.includes('HOLD') ? 'text-red-600' : 'text-success-text'
                                                            }`}>
                                                            {selectedCandidate.hr_decision?.status === 'COMPLETED' ? `HR DECISION: ${selectedCandidate.hr_decision.decision}` : selectedCandidate.final_synthesized_decision.final_decision}
                                                        </h2>
                                                    </div>
                                                </div>
                                                <div className="flex flex-col items-end">
                                                    <span className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-1">
                                                        {selectedCandidate.hr_decision?.status === 'COMPLETED' ? 'Decision Finalized' : 'Synthesis Confidence'}
                                                    </span>
                                                    <div className="text-3xl font-black text-[#1A1A1A]">
                                                        {selectedCandidate.hr_decision?.status === 'COMPLETED' ? '✓' : `${selectedCandidate.final_synthesized_decision.confidence}%`}
                                                    </div>
                                                </div>
                                            </div>

                                            <div className="flex flex-col gap-6">
                                                <div className="flex items-center gap-2">
                                                    <div className={`px-3 py-1 rounded-full text-[10px] font-bold uppercase tracking-widest border ${selectedCandidate.final_synthesized_decision.risk_level === 'HIGH' ? 'bg-red-50 text-red-600 border-red-100' :
                                                        selectedCandidate.final_synthesized_decision.risk_level === 'MEDIUM' ? 'bg-orange-50 text-orange-600 border-orange-100' :
                                                            'bg-green-50 text-green-600 border-green-100'
                                                        }`}>
                                                        Risk Level: {selectedCandidate.final_synthesized_decision.risk_level}
                                                    </div>
                                                    <div className="px-3 py-1 bg-gray-50 text-gray-500 border border-gray-100 rounded-full text-[10px] font-bold uppercase tracking-widest">
                                                        Classification: {selectedCandidate.final_synthesized_decision.candidate_classification}
                                                    </div>
                                                </div>

                                                <div className="flex flex-col gap-4">
                                                    <h4 className="text-[10px] font-black text-gray-400 uppercase tracking-[0.2em]">Executive Synthesis</h4>
                                                    <BulletList items={selectedCandidate.final_synthesized_decision.decision_reasoning} variant="info" />
                                                </div>
                                            </div>

                                        </div>
                                    </div>
                                </section>
                            )
                        }

                        <section className="mb-12">
                            <div className="p-1 bg-gradient-to-r from-gray-200 to-gray-300 rounded-[2rem] shadow-xl shadow-gray-50">
                                <div className="bg-white rounded-[1.9rem] p-8 md:p-10 flex flex-col gap-6">
                                    <div className="flex items-center justify-between">
                                        <div className="flex flex-col gap-1">
                                            <h4 className="text-sm font-black text-[#1A1A1A] uppercase tracking-wider">Human-In-The-Loop Action</h4>
                                            <p className="text-sm text-gray-500 font-medium">Review candidate metrics and finalize the hiring decision.</p>
                                        </div>
                                        {selectedCandidate.hr_decision?.status === 'COMPLETED' && (
                                            <div className="px-4 py-2 bg-success-light text-success-text rounded-xl font-black text-xs uppercase tracking-widest border border-success-text/20">
                                                Final Status: {selectedCandidate.hr_decision.decision}
                                            </div>
                                        )}
                                    </div>

                                    {selectedCandidate.hr_decision?.status !== 'COMPLETED' ? (
                                        <div className="flex flex-col gap-4">
                                            <textarea
                                                className="w-full p-4 bg-gray-50 border border-gray-200 rounded-2xl text-sm font-medium focus:ring-2 focus:ring-primary-blue focus:border-transparent transition-all outline-none"
                                                placeholder="Add internal notes for this decision..."
                                                rows={2}
                                                value={hrNotes}
                                                onChange={(e) => setHrNotes(e.target.value)}
                                            />
                                            <div className="flex items-center gap-3">
                                                <button
                                                    onClick={() => {
                                                        setIsSubmitting(true);
                                                        submitHRDecision(selectedCandidateId, 'APPROVE', hrNotes).finally(() => setIsSubmitting(false));
                                                    }}
                                                    disabled={isSubmitting}
                                                    className="flex-1 py-4 bg-success-text text-white rounded-2xl font-black text-sm uppercase tracking-widest hover:bg-emerald-700 transition-all shadow-lg shadow-emerald-100 disabled:opacity-50"
                                                >
                                                    Approve Candidate
                                                </button>
                                                <button
                                                    onClick={() => {
                                                        setIsSubmitting(true);
                                                        submitHRDecision(selectedCandidateId, 'HOLD', hrNotes).finally(() => setIsSubmitting(false));
                                                    }}
                                                    disabled={isSubmitting}
                                                    className="flex-1 py-4 bg-orange-500 text-white rounded-2xl font-black text-sm uppercase tracking-widest hover:bg-orange-600 transition-all shadow-lg shadow-orange-100 disabled:opacity-50"
                                                >
                                                    Hold for Review
                                                </button>
                                                <button
                                                    onClick={() => {
                                                        setIsSubmitting(true);
                                                        submitHRDecision(selectedCandidateId, 'REJECT', hrNotes).finally(() => setIsSubmitting(false));
                                                    }}
                                                    disabled={isSubmitting}
                                                    className="flex-1 py-4 bg-red-600 text-white rounded-2xl font-black text-sm uppercase tracking-widest hover:bg-red-700 transition-all shadow-lg shadow-red-100 disabled:opacity-50"
                                                >
                                                    Reject Profile
                                                </button>
                                            </div>
                                        </div>
                                    ) : (
                                        <div className="flex flex-col gap-6">
                                            <div className="p-6 bg-gray-50 rounded-2xl border border-dashed border-gray-200">
                                                <div className="flex flex-col gap-2">
                                                    <div className="text-[10px] font-bold text-gray-400 uppercase tracking-widest">Decision Notes</div>
                                                    <p className="text-sm font-medium text-slate-700 italic">
                                                        {selectedCandidate.hr_decision.notes || "No additional notes provided."}
                                                    </p>
                                                    <div className="text-[10px] text-gray-400 mt-2">
                                                        Actioned on: {new Date(selectedCandidate.hr_decision.timestamp).toLocaleString()}
                                                    </div>
                                                </div>
                                            </div>

                                            {/* Interview Trigger Orchestration Phase 8 */}
                                            {selectedCandidate.hr_decision.decision === 'APPROVE' && (
                                                <div className="pt-6 border-t border-gray-200 flex flex-col gap-4">
                                                    <div className="flex items-center justify-between">
                                                        <h4 className="text-sm font-black text-[#1A1A1A] uppercase tracking-wider">Dynamic Interview Action</h4>
                                                        <span className={`px-3 py-1 rounded-full text-[10px] font-bold uppercase tracking-widest ${selectedCandidate.interview_status === 'PENDING' ? 'bg-orange-50 text-orange-600' :
                                                            selectedCandidate.interview_status === 'APPROVED' ? 'bg-blue-50 text-blue-600' :
                                                                selectedCandidate.interview_status === 'INTERVIEW_SENT' ? 'bg-indigo-50 text-indigo-600' :
                                                                    'bg-green-50 text-green-600'
                                                            }`}>
                                                            {selectedCandidate.interview_status?.replace('_', ' ')}
                                                        </span>
                                                    </div>

                                                    {selectedCandidate.interview_status === 'PENDING' && (
                                                        <button
                                                            onClick={async () => {
                                                                setIsSubmitting(true);
                                                                try {
                                                                    const res = await fetch(`http://localhost:8000/api/candidate/${selectedCandidateId}/approve-interview`, { method: 'POST' });
                                                                    if (res.ok) alert("Interview Approved & Sent!");
                                                                    runScreening(evaluationWeights);
                                                                } catch (e) { console.error(e) }
                                                                finally { setIsSubmitting(false); }
                                                            }}
                                                            disabled={isSubmitting || selectedCandidate.evaluation_locked}
                                                            className="w-full py-4 bg-primary-blue text-white rounded-2xl font-black text-sm uppercase tracking-widest hover:bg-blue-700 transition-all shadow-lg shadow-blue-100 disabled:opacity-50"
                                                        >
                                                            {isSubmitting ? 'Processing...' : 'Approve for LiveKit Interview'}
                                                        </button>
                                                    )}

                                                    {selectedCandidate.interview_status === 'INTERVIEW_SENT' && (
                                                        <div className="flex flex-col gap-2">
                                                            <p className="text-xs text-gray-500 font-medium text-center">Invitation sent to candidate's email. Waiting for them to join.</p>
                                                            <button
                                                                onClick={() => alert("Simulated Resend")}
                                                                className="w-full py-3 bg-white text-primary-blue border border-primary-blue rounded-xl font-bold text-sm uppercase tracking-wider hover:bg-blue-50 transition-all"
                                                            >
                                                                Resend Invite
                                                            </button>
                                                        </div>
                                                    )}

                                                    {selectedCandidate.interview_status === 'INTERVIEW_COMPLETED' && (
                                                        <button
                                                            onClick={() => window.open(`/interview-results/${selectedCandidate.interview_session_id}`, '_blank')}
                                                            className="w-full py-4 bg-black text-white rounded-2xl font-black text-sm uppercase tracking-widest hover:bg-gray-800 transition-all shadow-lg shadow-gray-200"
                                                        >
                                                            View LiveKit Interview Results
                                                        </button>
                                                    )}
                                                </div>
                                            )}
                                        </div>
                                    )}
                                </div>
                            </div>
                        </section>

                        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-12">
                            <div className="p-6 bg-bg-muted border border-gray-200 rounded-2xl">
                                <div className="flex items-center gap-2 text-gray-500 text-[13px] font-bold mb-2">
                                    <FileText size={16} />
                                    <span>Resume Score</span>
                                </div>
                                <div className="text-3xl font-bold">{selectedCandidate.resume_score}/100</div>
                            </div>
                            <div className="p-6 bg-bg-muted border border-gray-200 rounded-2xl">
                                <div className="flex items-center gap-2 text-gray-500 text-[13px] font-bold mb-2">
                                    <Database size={16} />
                                    <span>GitHub Score</span>
                                </div>
                                <div className="text-3xl font-bold">{selectedCandidate.github_score}/100</div>
                            </div>
                            <div className="p-6 bg-bg-muted border border-gray-200 rounded-2xl">
                                <div className="flex items-center gap-2 text-gray-500 text-[13px] font-bold mb-2">
                                    <Code size={16} />
                                    <span>Repositories</span>
                                </div>
                                <div className="text-3xl font-bold">{selectedCandidate.repo_count} Total</div>
                            </div>
                        </div>

                        <CollapsibleSection title="Hiring Justification" icon={Award}>
                            <BulletList items={selectedCandidate.justification} variant="success" />
                        </CollapsibleSection>

                        {/* Resume Content Section */}
                        {selectedCandidate.raw_resume_text && (
                            <CollapsibleSection title="Resume Content" icon={FileText} defaultOpen={false}>
                                <div className="flex flex-col gap-4">
                                    {(() => {
                                        try {
                                            const parsed = JSON.parse(selectedCandidate.raw_resume_text);
                                            return (
                                                <>
                                                    {parsed.document_title && (
                                                        <div className="pb-3 border-b border-gray-100">
                                                            <h4 className="text-lg font-black text-[#1A1A1A]">{parsed.document_title}</h4>
                                                        </div>
                                                    )}
                                                    {parsed.sections?.map((section, idx) => (
                                                        <div key={idx} className="flex flex-col gap-2">
                                                            <div className="flex items-center gap-2">
                                                                <span className="px-2 py-0.5 bg-blue-50 text-primary-blue text-[9px] font-black uppercase tracking-widest rounded">
                                                                    {section.heading}
                                                                </span>
                                                            </div>
                                                            <div className="text-[13px] text-gray-700 leading-relaxed whitespace-pre-line pl-2 border-l-2 border-blue-100">
                                                                {section.content}
                                                            </div>
                                                        </div>
                                                    ))}
                                                </>
                                            );
                                        } catch {
                                            return (
                                                <div className="text-[13px] text-gray-700 leading-relaxed whitespace-pre-line">
                                                    {selectedCandidate.raw_resume_text}
                                                </div>
                                            );
                                        }
                                    })()}
                                </div>
                            </CollapsibleSection>
                        )}

                        {/* GitHub Evidence — only shows after Stage 2 */}
                        {selectedCandidate.github_score > 0 && (
                            <>
                                {/* GitHub Repo Links */}
                                {selectedCandidate.repos?.length > 0 && (
                                    <CollapsibleSection title="GitHub Evidence Tracking" icon={Github} defaultOpen={true} count={selectedCandidate.repos.length}>
                                        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                                            {selectedCandidate.repos.map((repo, idx) => (
                                                <a key={idx} href={repo.url} target="_blank" rel="noopener noreferrer"
                                                    className="p-4 border border-gray-200 rounded-2xl hover:border-blue-300 hover:shadow-md transition-all group">
                                                    <div className="flex items-center gap-2 mb-2">
                                                        <Github size={16} className="text-gray-400 group-hover:text-primary-blue transition-colors" />
                                                        <span className="text-sm font-bold text-[#1A1A1A] group-hover:text-primary-blue transition-colors">{repo.name}</span>
                                                    </div>
                                                    <p className="text-[11px] text-gray-500 leading-relaxed mb-3 line-clamp-2">{repo.description || 'No description'}</p>
                                                    <div className="flex items-center gap-3 text-[10px] font-bold text-gray-400">
                                                        {repo.language && <span className="px-2 py-0.5 bg-blue-50 text-primary-blue rounded">{repo.language}</span>}
                                                        {repo.stars > 0 && <span>⭐ {repo.stars}</span>}
                                                        <ExternalLink size={10} className="ml-auto text-gray-300 group-hover:text-primary-blue" />
                                                    </div>
                                                </a>
                                            ))}
                                        </div>
                                    </CollapsibleSection>
                                )}

                                {/* GitHub Rubric Scores */}
                                {(selectedCandidate.github_rubric || (typeof selectedCandidate.github_features === 'object' && selectedCandidate.github_features?.rubric_scores)) && (() => {
                                    const rubric = selectedCandidate.github_rubric || selectedCandidate.github_features?.rubric_scores || {};
                                    const strengths = selectedCandidate.github_strengths || selectedCandidate.github_features?.strengths || [];
                                    const weaknesses = selectedCandidate.github_weaknesses || selectedCandidate.github_features?.weaknesses || [];
                                    const justification = selectedCandidate.github_justification || selectedCandidate.github_features?.github_justification || '';
                                    return (
                                        <CollapsibleSection title="GitHub Rubric & Analysis" icon={Code} defaultOpen={true}>
                                            <div className="flex flex-col gap-6">
                                                {/* Rubric Score Cards */}
                                                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                                                    {[
                                                        { label: 'Code Quality', value: rubric.code_quality || 0, max: 25 },
                                                        { label: 'JD Relevance', value: rubric.jd_relevance || 0, max: 25 },
                                                        { label: 'Complexity', value: rubric.complexity || 0, max: 25 },
                                                        { label: 'Best Practices', value: rubric.best_practices || 0, max: 25 },
                                                    ].map((m, i) => {
                                                        const pct = (m.value / m.max) * 100;
                                                        const color = pct >= 70 ? 'text-green-600 bg-green-50 border-green-100' : pct >= 40 ? 'text-orange-600 bg-orange-50 border-orange-100' : 'text-red-600 bg-red-50 border-red-100';
                                                        return (
                                                            <div key={i} className={`p-4 rounded-2xl border flex flex-col gap-1.5 ${color}`}>
                                                                <div className="text-[10px] font-bold uppercase tracking-wider opacity-70">{m.label}</div>
                                                                <div className="text-2xl font-black">{m.value}/{m.max}</div>
                                                            </div>
                                                        );
                                                    })}
                                                </div>

                                                {/* Justification */}
                                                {justification && (
                                                    <p className="text-[13px] text-gray-600 leading-relaxed italic border-l-2 border-gray-200 pl-3">{justification}</p>
                                                )}

                                                {/* Strengths */}
                                                {strengths.length > 0 && (
                                                    <div>
                                                        <h5 className="text-[10px] font-black text-green-600 uppercase tracking-widest mb-2">Strengths</h5>
                                                        <BulletList items={strengths} variant="success" />
                                                    </div>
                                                )}

                                                {/* Weaknesses */}
                                                {weaknesses.length > 0 && (
                                                    <div>
                                                        <h5 className="text-[10px] font-black text-orange-600 uppercase tracking-widest mb-2">Weaknesses</h5>
                                                        <BulletList items={weaknesses} variant="warning" />
                                                    </div>
                                                )}
                                            </div>
                                        </CollapsibleSection>
                                    );
                                })()}

                                {/* AI Code Transparency — Show actual code */}
                                {selectedCandidate.code_evidence?.length > 0 && (
                                    <CollapsibleSection title="AI Code Transparency" icon={Terminal} defaultOpen={false} count={selectedCandidate.code_evidence.length}>
                                        <div className="flex flex-col gap-4">
                                            {selectedCandidate.code_evidence.map((ev, idx) => (
                                                <div key={idx} className="border border-gray-200 rounded-xl overflow-hidden">
                                                    <div className="flex items-center justify-between px-4 py-2 bg-gray-50 border-b border-gray-200">
                                                        <div className="flex items-center gap-2">
                                                            <Github size={12} className="text-gray-400" />
                                                            <span className="text-[11px] font-bold text-gray-700">{ev.repo_name}/{ev.file_path}</span>
                                                            <span className="px-1.5 py-0.5 bg-blue-50 text-primary-blue text-[9px] font-bold rounded">{ev.language}</span>
                                                        </div>
                                                        <a href={ev.file_url} target="_blank" rel="noopener noreferrer"
                                                            className="text-[10px] font-bold text-gray-400 hover:text-primary-blue flex items-center gap-1">
                                                            View on GitHub <ExternalLink size={10} />
                                                        </a>
                                                    </div>
                                                    <pre className="p-4 text-[11px] leading-relaxed text-gray-700 bg-gray-900 text-gray-300 overflow-x-auto max-h-[300px] overflow-y-auto font-mono">
                                                        <code>{ev.code_snippet}</code>
                                                    </pre>
                                                </div>
                                            ))}
                                        </div>
                                    </CollapsibleSection>
                                )}
                            </>
                        )}

                        {false && (selectedCandidate.rag_quality || retrievalMetrics) && (
                            <CollapsibleSection title="RAG Intelligence Audit" icon={Search} defaultOpen={true}>
                                <div className="flex flex-col gap-8">
                                    {/* Deterministic Retrieval Metrics */}
                                    {retrievalMetrics && (
                                        <div className="flex flex-col gap-4">
                                            <div className="flex items-center gap-2">
                                                <h4 className="text-sm font-black uppercase tracking-wider text-slate-800">Retrieval Quality Gate</h4>
                                                <span className={`px-2 py-0.5 rounded text-[10px] font-black uppercase ${retrievalMetrics.rag_health_status === 'HEALTHY' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
                                                    {retrievalMetrics.rag_health_status}
                                                </span>
                                            </div>
                                            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                                                {[
                                                    { label: 'JD Coverage', value: retrievalMetrics.coverage, threshold: 0.70, icon: FileText },
                                                    { label: 'Similarity', value: retrievalMetrics.similarity, threshold: 0.70, icon: CheckCircle },
                                                    { label: 'Diversity', value: retrievalMetrics.diversity, threshold: 0.60, icon: Database },
                                                    { label: 'Density', value: retrievalMetrics.density, threshold: 0.50, icon: Search }
                                                ].map((m, i) => {
                                                    const val = m.value || 0;
                                                    const passing = val >= m.threshold;
                                                    return (
                                                        <div key={i} className={`p-4 rounded-2xl border flex flex-col gap-1.5 ${passing ? 'bg-blue-50/40 border-blue-100' : 'bg-red-50/40 border-red-200'}`}>
                                                            <div className="flex items-center gap-2 text-gray-500 text-[10px] font-bold uppercase tracking-wider">
                                                                <m.icon size={12} />
                                                                {m.label}
                                                            </div>
                                                            <div className={`text-2xl font-black ${passing ? 'text-primary-blue' : 'text-red-600'}`}>
                                                                {(val * 100).toFixed(0)}%
                                                            </div>
                                                            <div className="text-[10px] font-bold text-gray-400 flex items-center gap-1">
                                                                {passing
                                                                    ? <span className="text-blue-500">✓ Threshold: ≥{(m.threshold * 100).toFixed(0)}%</span>
                                                                    : <span className="text-red-400">✗ Threshold: ≥{(m.threshold * 100).toFixed(0)}%</span>
                                                                }
                                                            </div>
                                                        </div>
                                                    );
                                                })}
                                            </div>
                                            <div className="flex justify-end">
                                                <button
                                                    onClick={() => toggleRagOverride(selectedCandidateId, !selectedCandidate.rag_override)}
                                                    className={`text-[10px] font-black uppercase tracking-widest px-3 py-1.5 rounded-lg border transition-all ${selectedCandidate.rag_override ? 'bg-orange-500 text-white border-orange-600' : 'bg-white text-gray-400 border-gray-200 hover:border-orange-300 hover:text-orange-500'}`}
                                                >
                                                    {selectedCandidate.rag_override ? '✓ RAG Gate Overridden' : 'Override RAG Gate'}
                                                </button>
                                            </div>
                                        </div>
                                    )}

                                    {/* Separator if both metrics exist */}
                                    {retrievalMetrics && <div className="border-t border-gray-100"></div>}

                                    {/* Action Button to run LLM Eval if no metrics yet, or to rerun if wanted */}
                                    {!llmMetrics && (!llmJobStatus || llmJobStatus.status === 'none' || llmJobStatus.status === 'FAILED') && (
                                        <div className="flex flex-col items-center justify-center p-8 bg-indigo-50/50 rounded-2xl border border-indigo-100 gap-4">
                                            <div className="flex flex-col items-center text-center max-w-lg gap-2">
                                                <h4 className="text-lg font-black text-indigo-900">Post-LLM Evaluation Audit</h4>
                                                <p className="text-sm text-indigo-700 font-medium">
                                                    Run a deep-dive evaluation using Gemini to strictly judge the LLM's faithfulness and context utilization.
                                                </p>
                                            </div>
                                            <button
                                                onClick={runLlmEvaluation}
                                                disabled={isTriggeringLlmEval || (retrievalMetrics && retrievalMetrics.rag_health_status !== 'HEALTHY' && !selectedCandidate.rag_override)}
                                                className="px-6 py-3 bg-primary-blue text-white font-black text-sm uppercase tracking-widest rounded-xl hover:bg-blue-700 transition-colors shadow-lg shadow-blue-200 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                                            >
                                                <ShieldCheck size={18} />
                                                {isTriggeringLlmEval ? 'Triggering...' : 'Run Enterprise RAG Audit'}
                                            </button>
                                            {retrievalMetrics && retrievalMetrics.rag_health_status !== 'HEALTHY' && !selectedCandidate.rag_override && (
                                                <span className="text-[10px] font-bold text-red-500 uppercase">
                                                    Cannot run Audit: Retrieval Gate Failed.
                                                </span>
                                            )}
                                            {llmJobStatus?.status === 'FAILED' && (
                                                <span className="text-[10px] font-bold text-red-500 uppercase mt-2">
                                                    Previous Audit Failed: {llmJobStatus.error}
                                                </span>
                                            )}
                                        </div>
                                    )}

                                    {/* Polling State */}
                                    {llmJobStatus && (llmJobStatus.status === 'PENDING' || llmJobStatus.status === 'RUNNING') && (
                                        <div className="flex items-center gap-4 p-6 bg-blue-50 border border-blue-100 rounded-2xl">
                                            <RotateCw className="animate-spin text-primary-blue mx-2" size={24} />
                                            <div className="flex flex-col">
                                                <span className="text-sm font-black text-blue-900 uppercase">Running Intelligence Audit</span>
                                                <span className="text-xs font-medium text-blue-700">Evaluating faithfulness, relevance, and hallucinations via Gemini. Please wait...</span>
                                            </div>
                                        </div>
                                    )}

                                    {/* Enterprise LLM RAG Audit Metric Cards */}
                                    {llmMetrics && (
                                        <div className="flex flex-col gap-4 animate-in fade-in slide-in-from-bottom-4 duration-500">
                                            <div className="flex items-center justify-between">
                                                <h4 className="text-sm font-black uppercase tracking-wider text-slate-800">Post-LLM Evaluation Metrics</h4>
                                                <span className="text-xs font-bold text-gray-400">Powered by Gemini 2.5 Pro</span>
                                            </div>
                                            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                                                {[
                                                    { label: 'Faithfulness', value: llmMetrics.faithfulness, threshold: 0.80, icon: ShieldCheck },
                                                    { label: 'Relevance', value: llmMetrics.answer_relevance, threshold: 0.70, icon: CheckCircle },
                                                    { label: 'Hallucination', value: llmMetrics.hallucination_score, threshold: 0.90, icon: ShieldAlert },
                                                    { label: 'Utility', value: llmMetrics.context_utilization, threshold: 0.70, icon: Database }
                                                ].map((m, i) => {
                                                    const val = m.value || 0;
                                                    const passing = val >= m.threshold;
                                                    const warn = val >= m.threshold * 0.85;
                                                    return (
                                                        <div key={i} className={`p-4 rounded-2xl border flex flex-col gap-1.5 ${passing ? 'bg-green-50/40 border-green-100' : warn ? 'bg-orange-50/40 border-orange-100' : 'bg-red-50/40 border-red-200'}`}>
                                                            <div className="flex items-center gap-2 text-gray-400 text-[10px] font-bold uppercase tracking-wider whitespace-nowrap">
                                                                <m.icon size={12} />
                                                                {m.label}
                                                            </div>
                                                            <div className={`text-2xl font-black ${passing ? 'text-emerald-600' : warn ? 'text-orange-500' : 'text-red-600'}`}>
                                                                {(val * 100).toFixed(0)}%
                                                            </div>
                                                            <div className="text-[10px] font-bold text-gray-400 flex items-center gap-1">
                                                                {passing
                                                                    ? <span className="text-emerald-500">✓ Threshold: ≥{(m.threshold * 100).toFixed(0)}%</span>
                                                                    : <span className="text-red-400">✗ Threshold: ≥{(m.threshold * 100).toFixed(0)}%</span>
                                                                }
                                                            </div>
                                                        </div>
                                                    );
                                                })}
                                            </div>

                                            {/* Health Status Bar */}
                                            <div className={`p-5 rounded-[1.5rem] border flex md:flex-row flex-col items-start md:items-center justify-between gap-4 mt-2 ${llmMetrics.rag_health_status === 'GOOD' ? 'bg-green-50/50 border-green-100' :
                                                llmMetrics.rag_health_status === 'WARN' ? 'bg-orange-50/50 border-orange-100' : 'bg-red-50/50 border-red-100'
                                                }`}>
                                                <div className="flex items-center gap-4">
                                                    <div className={`p-3 rounded-xl ${llmMetrics.rag_health_status === 'GOOD' ? 'bg-emerald-500 text-white' :
                                                        llmMetrics.rag_health_status === 'WARN' ? 'bg-orange-500 text-white' : 'bg-red-600 text-white'
                                                        }`}>
                                                        <Terminal size={18} />
                                                    </div>
                                                    <div className="flex flex-col gap-1">
                                                        <div className="flex items-center gap-2">
                                                            <span className="text-[10px] font-black uppercase tracking-[0.2em] opacity-60">Audit Output</span>
                                                            <span className={`px-2 py-0.5 rounded-md text-[9px] font-black uppercase ${llmMetrics.rag_health_status === 'GOOD' ? 'bg-white text-emerald-600' :
                                                                llmMetrics.rag_health_status === 'WARN' ? 'bg-white text-orange-500' : 'bg-white text-red-600'
                                                                }`}>
                                                                {llmMetrics.rag_health_status}
                                                            </span>
                                                        </div>
                                                        <div className="text-sm font-bold text-slate-800">
                                                            Final LLM Judge Score: {((llmMetrics.overall_score || 0) * 100).toFixed(0)}%
                                                        </div>
                                                    </div>
                                                </div>
                                                <div className="px-5 py-3 bg-white/60 rounded-xl text-xs font-medium italic text-slate-600 border border-black/5 shadow-sm max-w-sm">
                                                    "{llmMetrics.explanation}"
                                                </div>
                                            </div>

                                            <div className="flex justify-end mt-1">
                                                <button onClick={runLlmEvaluation} disabled={isTriggeringLlmEval} className="text-xs font-bold text-gray-400 hover:text-primary-blue uppercase tracking-widest transition-colors flex items-center gap-1">
                                                    <RotateCw size={12} className={isTriggeringLlmEval ? 'animate-spin' : ''} />
                                                    Re-run Audit
                                                </button>
                                            </div>
                                        </div>
                                    )}
                                </div>
                            </CollapsibleSection>
                        )
                        }

                        {
                            selectedCandidate.interview_readiness && (
                                <CollapsibleSection title="AI Recommendation Summary" icon={MessageSquare} count={selectedCandidate.interview_readiness.risk_factors.length + selectedCandidate.interview_readiness.skill_gaps.length}>
                                    <div className="flex flex-col gap-8">
                                        <div className="flex flex-wrap items-center justify-between gap-4 p-6 bg-gray-50 rounded-2xl border border-gray-100">
                                            <div className="flex flex-col">
                                                <span className="text-[10px] font-bold text-gray-400 uppercase tracking-widest">Status</span>
                                                <div className={`text-lg font-extrabold ${selectedCandidate.interview_readiness.hire_readiness_level === 'HIGH' ? 'text-success-text' :
                                                    selectedCandidate.interview_readiness.hire_readiness_level === 'MEDIUM' ? 'text-blue-600' : 'text-orange-500'
                                                    }`}>
                                                    {selectedCandidate.interview_readiness.hire_readiness_level} READY
                                                </div>
                                            </div>
                                            <div className="flex flex-col text-right">
                                                <span className="text-[10px] font-bold text-gray-400 uppercase tracking-widest">Confidence</span>
                                                <div className="text-lg font-extrabold text-[#1A1A1A]">
                                                    {selectedCandidate.interview_readiness.confidence_score}%
                                                </div>
                                            </div>
                                            <div className="flex flex-col text-right">
                                                <span className="text-[10px] font-bold text-gray-400 uppercase tracking-widest">Recommendation</span>
                                                <div className="px-3 py-1 bg-white rounded text-xs font-bold text-slate-700 ring-1 ring-gray-100">
                                                    {selectedCandidate.interview_readiness.final_hiring_recommendation}
                                                </div>
                                            </div>
                                        </div>

                                        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                                            <div className="flex flex-col gap-4">
                                                <h4 className="text-[10px] font-black text-gray-400 uppercase tracking-widest">Risk Factors & Gaps</h4>
                                                <BulletList items={[...selectedCandidate.interview_readiness.risk_factors, ...selectedCandidate.interview_readiness.skill_gaps]} variant="danger" />
                                            </div>
                                            <div className="flex flex-col gap-4">
                                                <h4 className="text-[10px] font-black text-gray-400 uppercase tracking-widest">Interview Focus Areas</h4>
                                                <BulletList items={selectedCandidate.interview_readiness.interview_focus_areas} variant="info" />
                                            </div>
                                        </div>

                                        <div className="flex flex-col gap-4 border-t border-gray-100 pt-6">
                                            <h4 className="text-[10px] font-black text-gray-400 uppercase tracking-widest">Executive Summary Findings</h4>
                                            <BulletList items={selectedCandidate.interview_readiness.executive_summary} variant="success" />
                                        </div>

                                        {/* Audit Metrics for Readiness */}
                                        {selectedCandidate.interview_readiness.judge_audit && (
                                            <div className="flex flex-col gap-3 p-4 bg-slate-50 rounded-2xl border border-slate-100">
                                                <div className="flex items-center justify-between">
                                                    <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest">Readiness Agent Audit</span>
                                                    <span className="text-[9px] font-bold text-slate-400 italic">Faithfulness & Grounding</span>
                                                </div>
                                                <div className="grid grid-cols-4 gap-3">
                                                    {[
                                                        { label: 'Faith', value: selectedCandidate.interview_readiness.judge_audit.faithfulness },
                                                        { label: 'Rel', value: selectedCandidate.interview_readiness.judge_audit.relevance },
                                                        { label: 'Hallu', value: selectedCandidate.interview_readiness.judge_audit.hallucination },
                                                        { label: 'Util', value: selectedCandidate.interview_readiness.judge_audit.utility }
                                                    ].map((m, i) => (
                                                        <div key={i} className="flex flex-col items-center p-2 bg-white rounded-xl border border-slate-100 shadow-sm">
                                                            <span className="text-[8px] font-black text-slate-400 uppercase">{m.label}</span>
                                                            <span className={`text-xs font-black ${m.value >= 0.8 ? 'text-emerald-600' : 'text-slate-600'}`}>
                                                                {(m.value * 100).toFixed(0)}%
                                                            </span>
                                                        </div>
                                                    ))}
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                </CollapsibleSection>
                            )
                        }

                        {
                            selectedCandidate.skeptic_analysis && (
                                <CollapsibleSection title="AI Skeptic Audit" icon={ShieldAlert} count={selectedCandidate.skeptic_analysis.major_concerns.length}>
                                    <div className="flex flex-col gap-8">
                                        <div className="flex items-center justify-between p-6 bg-orange-50 rounded-2xl border border-orange-100">
                                            <div className="flex flex-col">
                                                <span className="text-[10px] font-bold text-orange-400 uppercase tracking-widest">Risk Severity Level</span>
                                                <div className={`text-lg font-black ${selectedCandidate.skeptic_analysis.risk_level === 'HIGH' ? 'text-orange-700' : 'text-orange-500'}`}>
                                                    {selectedCandidate.skeptic_analysis.risk_level}
                                                </div>
                                            </div>
                                            <div className="px-4 py-2 bg-white border border-orange-100 rounded-xl text-[10px] font-black text-orange-600 uppercase tracking-widest">
                                                Adversarial Probe: Active
                                            </div>
                                        </div>

                                        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                                            <div className="flex flex-col gap-4">
                                                <h4 className="text-[10px] font-black text-orange-400 uppercase tracking-widest">Major Concerns</h4>
                                                <BulletList items={selectedCandidate.skeptic_analysis.major_concerns} variant="danger" />
                                            </div>
                                            <div className="flex flex-col gap-4">
                                                <h4 className="text-[10px] font-black text-orange-400 uppercase tracking-widest">Hidden Risks</h4>
                                                <BulletList items={selectedCandidate.skeptic_analysis.hidden_risks} variant="warning" />
                                            </div>
                                        </div>

                                        <div className="flex flex-col gap-4 border-t border-orange-100 pt-6">
                                            <h4 className="text-[10px] font-black text-orange-400 uppercase tracking-widest">Skeptic Warnings</h4>
                                            <BulletList items={selectedCandidate.skeptic_analysis.skeptic_recommendation} variant="danger" />
                                        </div>

                                        {/* Audit Metrics for Skeptic */}
                                        {selectedCandidate.skeptic_analysis.judge_audit && (
                                            <div className="flex flex-col gap-3 p-4 bg-orange-50/30 rounded-2xl border border-orange-100">
                                                <div className="flex items-center justify-between">
                                                    <span className="text-[10px] font-black text-orange-400 uppercase tracking-widest">Skeptic Agent Audit</span>
                                                    <span className="text-[9px] font-bold text-orange-400 italic">Faithfulness & Grounding</span>
                                                </div>
                                                <div className="grid grid-cols-4 gap-3">
                                                    {[
                                                        { label: 'Faith', value: selectedCandidate.skeptic_analysis.judge_audit.faithfulness },
                                                        { label: 'Rel', value: selectedCandidate.skeptic_analysis.judge_audit.relevance },
                                                        { label: 'Hallu', value: selectedCandidate.skeptic_analysis.judge_audit.hallucination },
                                                        { label: 'Util', value: selectedCandidate.skeptic_analysis.judge_audit.utility }
                                                    ].map((m, i) => (
                                                        <div key={i} className="flex flex-col items-center p-2 bg-white rounded-xl border border-orange-100 shadow-sm">
                                                            <span className="text-[8px] font-black text-orange-400 uppercase">{m.label}</span>
                                                            <span className={`text-xs font-black ${m.value >= 0.8 ? 'text-orange-600' : 'text-slate-600'}`}>
                                                                {(m.value * 100).toFixed(0)}%
                                                            </span>
                                                        </div>
                                                    ))}
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                </CollapsibleSection>
                            )
                        }

                        <CollapsibleSection title="GitHub Evidence Tracking" icon={Code} count={selectedCandidate.repos.length}>
                            <div className="flex flex-col gap-8">
                                {selectedCandidateBasic?.github_url && (
                                    <div className="p-6 bg-gray-50 rounded-2xl border border-gray-100 flex items-center justify-between">
                                        <div className="flex items-center gap-4">
                                            <div className="w-12 h-12 bg-white shadow-sm rounded-2xl flex items-center justify-center text-gray-700 border border-gray-100">
                                                <Github size={24} />
                                            </div>
                                            <div className="flex flex-col">
                                                <span className="text-[10px] font-bold text-gray-400 uppercase tracking-widest">Verified Profile</span>
                                                <div className="text-base font-black text-[#1A1A1A]">
                                                    {selectedCandidateBasic.github_url.replace('https://', '').replace('http://', '')}
                                                </div>
                                            </div>
                                        </div>
                                        <a
                                            href={selectedCandidateBasic.github_url.startsWith('http') ? selectedCandidateBasic.github_url : `https://${selectedCandidateBasic.github_url}`}
                                            target="_blank"
                                            rel="noopener noreferrer"
                                            className="flex items-center gap-2 text-primary-blue font-black text-[11px] uppercase tracking-widest hover:underline"
                                        >
                                            Open Profile <ExternalLink size={14} />
                                        </a>
                                    </div>
                                )}

                                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                    {selectedCandidate.repos.map((repo, idx) => (
                                        <a
                                            key={idx}
                                            href={repo.url}
                                            target="_blank"
                                            rel="noopener noreferrer"
                                            className="p-5 bg-white border border-gray-100 rounded-2xl shadow-sm hover:border-primary-blue hover:shadow-xl transition-all flex flex-col gap-3 group"
                                        >
                                            <div className="flex items-center justify-between">
                                                <div className="font-black text-sm text-[#1A1A1A] group-hover:text-primary-blue transition-colors flex items-center gap-2">
                                                    <div className="w-8 h-8 bg-gray-50 rounded-lg flex items-center justify-center text-gray-400 group-hover:bg-blue-50 group-hover:text-primary-blue transition-colors">
                                                        <CheckCircle size={14} />
                                                    </div>
                                                    {repo.name}
                                                </div>
                                                <span className="text-[10px] font-bold text-gray-400">★ {repo.stars}</span>
                                            </div>

                                            <div className="text-xs text-gray-500 line-clamp-2 leading-relaxed font-medium">{repo.description || 'Verified production-grade repository.'}</div>

                                            <div className="flex items-center justify-between mt-2 pt-3 border-t border-gray-50">
                                                <span className="text-[10px] font-black text-primary-blue uppercase tracking-widest bg-blue-50 px-2 py-0.5 rounded-md">
                                                    {repo.language || 'Codebase'}
                                                </span>
                                                <span className="text-[9px] font-black text-success-text uppercase tracking-widest">
                                                    AI AGENT MATCH
                                                </span>
                                            </div>
                                        </a>
                                    ))}
                                </div>
                            </div>
                        </CollapsibleSection>

                        {
                            selectedCandidate.ai_evidence && selectedCandidate.ai_evidence.length > 0 && (
                                <CollapsibleSection title="AI Evidence Transparency" icon={Search} count={selectedCandidate.ai_evidence.length}>
                                    <div className="flex flex-col gap-6">
                                        <div className="flex flex-col gap-2 p-4 bg-blue-50 rounded-2xl border border-blue-100 mb-2">
                                            <div className="flex items-center gap-2 text-primary-blue">
                                                <Terminal size={16} />
                                                <span className="text-xs font-black uppercase tracking-widest">Source Context Extraction</span>
                                            </div>
                                            <p className="text-xs text-blue-800 font-medium">The following raw data was retrieved via RAG to synthesize the final decision.</p>
                                        </div>

                                        {selectedCandidate.ai_evidence.map((evidence, i) => (
                                            <div key={i} className="flex flex-col border border-gray-100 rounded-2xl overflow-hidden bg-white shadow-sm">
                                                <div className="flex items-center justify-between px-4 py-3 bg-gray-50 border-b border-gray-100">
                                                    <div className="flex items-center gap-2">
                                                        <span className="text-[10px] font-black text-gray-500 uppercase tracking-widest">
                                                            {evidence.source?.includes("GitHub") ? "Repo:" : "Section:"} {evidence.repo || evidence.section || "General"}
                                                        </span>
                                                    </div>
                                                    <div className="px-2 py-0.5 bg-white border border-gray-200 rounded text-[9px] font-black text-gray-400 uppercase tracking-widest">
                                                        {evidence.source || 'RETRIEVED CHUNK'}
                                                    </div>
                                                </div>
                                                <div className="p-4 overflow-x-auto">
                                                    <pre className="text-[11px] font-mono text-slate-600 leading-relaxed whitespace-pre-wrap">
                                                        {evidence.snippet}
                                                    </pre>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </CollapsibleSection>
                            )
                        }
                    </div >
                ) : (
                    <div className="max-w-5xl mx-auto p-6 md:p-10 w-full flex flex-col items-center justify-center gap-4 h-full">
                        <RotateCw size={24} className="animate-spin text-gray-300" />
                        <p className="text-sm text-gray-400 font-bold">Loading candidate data...</p>
                        <button onClick={() => setSelectedCandidateId(null)} className="text-xs font-bold text-primary-blue hover:underline mt-2">← Back to Pipeline Grid</button>
                    </div>
                )}
            </main >
        </div >
    );
};

// Results component export
export default Results;
