import React from 'react';
import { useScreening } from '../../context/ScreeningContext';
import { Award, Code, Database, FileText, MessageSquare, ExternalLink, ShieldAlert, ShieldCheck, ChevronDown, ChevronRight, Github, Terminal, Search, CheckCircle, RotateCw } from 'lucide-react';

const Results = () => {
    const { results, selectedCandidateId, setSelectedCandidateId, submitHRDecision, runScreening } = useScreening();
    const [hrNotes, setHrNotes] = React.useState('');
    const [isSubmitting, setIsSubmitting] = React.useState(false);

    React.useEffect(() => {
        setHrNotes('');
    }, [selectedCandidateId]);

    if (!results) return null;

    const selectedCandidate = results.evaluations[selectedCandidateId];
    const selectedCandidateBasic = results.ranking.find(c => c.candidate_id === selectedCandidateId);

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

    return (
        <div className="flex flex-col md:flex-row flex-1 overflow-hidden h-[calc(100vh-64px-60px)]">
            {/* Sidebar */}
            <aside className="w-full md:w-[360px] bg-bg-sidebar border-b md:border-b-0 md:border-r border-gray-200 flex flex-col shrink-0 overflow-y-auto md:overflow-visible h-1/3 md:h-auto">
                <div className="p-8 border-b border-gray-200 bg-white flex flex-col gap-4">
                    <div className="flex items-center justify-between">
                        <div className="flex flex-col">
                            <h3 className="text-lg font-bold text-[#1A1A1A]">Top Candidates</h3>
                            <span className="text-xs text-gray-500">{results.ranking.length} profiles prioritized</span>
                        </div>
                        <button
                            onClick={runScreening}
                            className="p-2 transition-all duration-300 rounded-xl bg-gray-50 text-gray-400 hover:bg-primary-blue hover:text-white group relative"
                            title="Re-run Screening"
                        >
                            <RotateCw size={18} className="group-hover:rotate-180 transition-transform duration-500" />
                        </button>
                    </div>
                </div>

                <div className="flex-1 overflow-y-auto">
                    {results.ranking.map((candidate) => (
                        <div
                            key={candidate.candidate_id}
                            className={`p-5 px-6 flex items-center gap-4 cursor-pointer border-l-4 transition-all hover:bg-white ${selectedCandidateId === candidate.candidate_id
                                ? 'bg-white border-primary-blue shadow-sm'
                                : 'border-transparent'
                                }`}
                            onClick={() => setSelectedCandidateId(candidate.candidate_id)}
                        >
                            <div className="w-11 h-11 bg-indigo-50 rounded-xl flex items-center justify-center font-bold text-primary-blue text-lg">
                                {candidate.name.charAt(0)}
                            </div>
                            <div className="flex flex-col">
                                <div className="font-semibold text-sm">{candidate.name}</div>
                                <div className={`text-xs ${selectedCandidateId === candidate.candidate_id ? 'text-primary-blue font-semibold' : 'text-gray-500'}`}>
                                    Intelligence: {candidate.score.toFixed(0)}/100
                                </div>
                            </div>
                        </div>
                    ))}
                </div>
            </aside>

            {/* Main Content */}
            <main className="flex-1 bg-white overflow-y-auto">
                {selectedCandidate ? (
                    <div className="max-w-4xl mx-auto p-6 md:p-14 w-full">
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

                        {selectedCandidate.final_synthesized_decision && (
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

                                        <div className="pt-8 border-t border-gray-100">
                                            <div className="flex flex-col gap-6">
                                                <div className="flex items-center justify-between">
                                                    <div className="flex flex-col gap-1">
                                                        <h4 className="text-sm font-black text-[#1A1A1A] uppercase tracking-wider">Human-In-The-Loop Action</h4>
                                                        <p className="text-sm text-gray-500 font-medium">Review AI recommendation and finalize the hiring decision.</p>
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
                                                )}
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </section>
                        )}

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

                        {selectedCandidate.interview_readiness && (
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
                                </div>
                            </CollapsibleSection>
                        )}

                        {selectedCandidate.skeptic_analysis && (
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
                                </div>
                            </CollapsibleSection>
                        )}

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

                        {selectedCandidate.ai_evidence && selectedCandidate.ai_evidence.length > 0 && (
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
                                                    <span className="text-[10px] font-black text-gray-500 uppercase tracking-widest">Repo: {evidence.repo}</span>
                                                    <span className="text-gray-300">|</span>
                                                    <span className="text-[10px] font-bold text-primary-blue">{evidence.file}</span>
                                                </div>
                                                <div className="px-2 py-0.5 bg-white border border-gray-200 rounded text-[9px] font-black text-gray-400 uppercase tracking-widest">
                                                    {evidence.type}
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
                        )}
                    </div>
                ) : (
                    <div className="h-full flex flex-col items-center justify-center gap-4 text-gray-400">
                        <MessageSquare size={48} className="opacity-20" />
                        <p className="font-medium">Select a candidate to view deep intelligence results.</p>
                    </div>
                )}
            </main>
        </div>
    );
};

// Simple Zap icon component
const Zap = ({ size }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" /></svg>
);

export default Results;
