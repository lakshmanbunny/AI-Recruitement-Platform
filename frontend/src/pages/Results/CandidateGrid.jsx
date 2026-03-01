import React, { useState, useEffect } from 'react';
import { Search, ChevronLeft, ChevronRight, ShieldAlert, ShieldCheck, CheckCircle, Database, FileText, Terminal, Star, Clock } from 'lucide-react';

const MiniMetric = ({ label, value, threshold }) => {
    if (value === undefined || value === null) return <div className="w-8 h-1 bg-gray-100 rounded-full" title="Pending" />;
    const passing = value >= threshold;
    const warn = value >= threshold * 0.85;
    const colorClass = passing ? 'bg-emerald-500' : warn ? 'bg-orange-500' : 'bg-red-500';
    return (
        <div className="flex flex-col gap-0.5 group relative" title={`${label}: ${(value * 100).toFixed(0)}% (Threshold: ${threshold * 100}%)`}>
            <div className={`w-8 h-1.5 rounded-full ${colorClass} opacity-80 group-hover:opacity-100 transition-opacity`} />
            <span className="text-[8px] font-bold text-gray-400 uppercase leading-none opacity-0 group-hover:opacity-100 absolute -bottom-3 left-0 whitespace-nowrap z-10 bg-white shadow-sm px-1 rounded">{label}</span>
        </div>
    );
};

const CandidateRow = ({ candidate, evalData, onSelect }) => {
    const [retrievalMetrics, setRetrievalMetrics] = useState(null);
    const [llmMetrics, setLlmMetrics] = useState(null);
    const [isLoading, setIsLoading] = useState(true);

    useEffect(() => {
        let isMounted = true;
        const fetchRowMetrics = async () => {
            setIsLoading(true);
            try {
                const [retRes, llmRes] = await Promise.all([
                    fetch(`http://localhost:8000/api/rag/retrieval-metrics/${candidate.candidate_id}`),
                    fetch(`http://localhost:8000/api/rag/llm-metrics/${candidate.candidate_id}`)
                ]);

                if (isMounted && retRes.ok) setRetrievalMetrics(await retRes.json());
                if (isMounted && llmRes.ok) setLlmMetrics(await llmRes.json());
            } catch (e) {
                console.error("Failed to fetch row metrics", e);
            } finally {
                if (isMounted) setIsLoading(false);
            }
        };
        fetchRowMetrics();
        return () => { isMounted = false; };
    }, [candidate.candidate_id]);

    const blocked = evalData?.evaluation_blocked;
    const decision = evalData?.final_synthesized_decision?.final_decision || evalData?.final_decision;
    const score = candidate.score;

    return (
        <tr className="hover:bg-blue-50/30 transition-colors border-b border-gray-100 group cursor-pointer" onClick={() => onSelect(candidate.candidate_id)}>
            {/* Candidate Info */}
            <td className="p-4 whitespace-nowrap">
                <div className="flex items-center gap-3">
                    <div className="w-10 h-10 bg-indigo-50 text-primary-blue rounded-xl flex items-center justify-center font-black text-lg border border-indigo-100/50">
                        {candidate.name.charAt(0)}
                    </div>
                    <div className="flex flex-col">
                        <span className="font-bold text-sm text-[#1A1A1A]">{candidate.name}</span>
                        <div className="flex items-center gap-2 text-xs text-gray-500">
                            <span className="font-bold text-primary-blue">Rank #{candidate.rank}</span>
                            <span>• {candidate.candidate_id}</span>
                        </div>
                    </div>
                </div>
            </td>

            {/* Overall Intelligence */}
            <td className="p-4 whitespace-nowrap">
                <div className="flex flex-col gap-1">
                    <div className="flex items-center justify-between text-xs font-bold w-24">
                        <span className={score >= 80 ? 'text-success-text' : score >= 60 ? 'text-primary-blue' : 'text-gray-500'}>
                            {score.toFixed(0)}/100
                        </span>
                    </div>
                    <div className="w-24 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                        <div
                            className={`h-full rounded-full ${score >= 80 ? 'bg-success-text' : score >= 60 ? 'bg-primary-blue' : 'bg-gray-400'}`}
                            style={{ width: `${Math.min(100, Math.max(0, score))}%` }}
                        />
                    </div>
                </div>
            </td>

            {/* 4 Pre-Agent RAG Metrics */}
            <td className="p-4 whitespace-nowrap">
                {isLoading ? (
                    <div className="animate-pulse flex gap-1"><div className="w-8 h-1.5 bg-gray-200 rounded-full" /><div className="w-8 h-1.5 bg-gray-200 rounded-full" /><div className="w-8 h-1.5 bg-gray-200 rounded-full" /><div className="w-8 h-1.5 bg-gray-200 rounded-full" /></div>
                ) : retrievalMetrics ? (
                    <div className="flex flex-col gap-1.5">
                        <div className="flex gap-1 pb-2">
                            <MiniMetric label="Coverage" value={retrievalMetrics.coverage} threshold={0.70} />
                            <MiniMetric label="Similarity" value={retrievalMetrics.similarity} threshold={0.70} />
                            <MiniMetric label="Diversity" value={retrievalMetrics.diversity} threshold={0.60} />
                            <MiniMetric label="Density" value={retrievalMetrics.density} threshold={0.50} />
                        </div>
                        <span className={`text-[9px] font-black uppercase tracking-widest px-2 py-0.5 rounded w-max ${retrievalMetrics.rag_health_status === 'HEALTHY' ? 'bg-green-50 text-green-600 border border-green-100' : 'bg-red-50 text-red-600 border border-red-100'}`}>
                            {retrievalMetrics.rag_health_status}
                        </span>
                    </div>
                ) : (
                    <span className="text-xs text-gray-400 font-medium">N/A</span>
                )}
            </td>

            {/* 4 Post-Agent LLM Metrics */}
            <td className="p-4 whitespace-nowrap">
                {blocked ? (
                    <div className="flex items-center gap-1.5 text-xs font-bold text-red-500 bg-red-50 px-2 py-1 rounded w-max">
                        <ShieldAlert size={14} /> BLOCKED
                    </div>
                ) : isLoading ? (
                    <div className="animate-pulse flex gap-1 pb-2"><div className="w-8 h-1 bg-gray-200 rounded-full" /><div className="w-8 h-1 bg-gray-200 rounded-full" /><div className="w-8 h-1 bg-gray-200 rounded-full" /><div className="w-8 h-1 bg-gray-200 rounded-full" /></div>
                ) : llmMetrics ? (
                    <div className="flex gap-1 pb-2 pt-1 mt-1">
                        <MiniMetric label="Faithfulness" value={llmMetrics.faithfulness} threshold={0.80} />
                        <MiniMetric label="Relevance" value={llmMetrics.answer_relevance} threshold={0.70} />
                        <MiniMetric label="Hallucination" value={llmMetrics.hallucination_score} threshold={0.90} />
                        <MiniMetric label="Utility" value={llmMetrics.context_utilization} threshold={0.70} />
                    </div>
                ) : (
                    <span className="text-xs text-gray-400 font-medium italic">Pending Audit</span>
                )}
            </td>

            {/* AI Decision Pill */}
            <td className="p-4 whitespace-nowrap">
                <span className={`px-3 py-1.5 rounded-lg text-[10px] font-black uppercase tracking-widest border border-transparent shadow-sm ${decision?.includes('APPROVE') ? 'bg-primary-blue text-white shadow-blue-200' :
                    decision?.includes('REJECT') ? 'bg-gray-100 text-gray-500' :
                        decision?.includes('HOLD') ? 'bg-orange-500 text-white shadow-orange-200' :
                            'bg-slate-800 text-white'
                    }`}>
                    {decision || 'PENDING'}
                </span>
            </td>

            {/* Actions */}
            <td className="p-4 whitespace-nowrap text-right">
                <button className="text-xs font-black text-gray-400 group-hover:text-primary-blue uppercase tracking-widest transition-colors flex items-center justify-end gap-1 w-full">
                    View Report <ChevronRight size={14} />
                </button>
            </td>
        </tr>
    );
};

const CandidateGrid = ({ results, onSelectCandidate }) => {
    const [searchTerm, setSearchTerm] = useState('');
    const [filterStatus, setFilterStatus] = useState('ALL'); // ALL, HEALTHY, BLOCKED
    const [currentPage, setCurrentPage] = useState(1);
    const rowsPerPage = 30;

    // Filter logic
    const filteredCandidates = results.ranking.filter(cand => {
        const matchesSearch = cand.name.toLowerCase().includes(searchTerm.toLowerCase()) || cand.candidate_id.toLowerCase().includes(searchTerm.toLowerCase());
        const evalData = results.evaluations[cand.candidate_id];
        const isBlocked = evalData?.evaluation_blocked;
        if (filterStatus === 'HEALTHY' && isBlocked) return false;
        if (filterStatus === 'BLOCKED' && !isBlocked) return false;
        return matchesSearch;
    });

    const totalPages = Math.max(1, Math.ceil(filteredCandidates.length / rowsPerPage));
    const paginatedCandidates = filteredCandidates.slice((currentPage - 1) * rowsPerPage, currentPage * rowsPerPage);

    return (
        <div className="flex-1 bg-gray-50/50 p-6 md:p-10 overflow-y-auto w-full h-full">
            <div className="max-w-7xl mx-auto flex flex-col h-full gap-6">

                {/* Header & Toolbar */}
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-white p-6 rounded-3xl border border-gray-100 shadow-sm">
                    <div className="flex flex-col">
                        <h1 className="text-2xl font-black text-[#1A1A1A] tracking-tight">Candidate Pipeline</h1>
                        <span className="text-sm text-gray-500 font-medium">Reviewing {filteredCandidates.length} high-volume profiles</span>
                    </div>

                    <div className="flex flex-col md:flex-row items-center gap-4">
                        <div className="relative">
                            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={16} />
                            <input
                                type="text"
                                placeholder="Search candidates..."
                                value={searchTerm}
                                onChange={e => { setSearchTerm(e.target.value); setCurrentPage(1); }}
                                className="pl-9 pr-4 py-2 bg-gray-50 border border-gray-200 rounded-xl text-sm font-medium focus:ring-2 focus:ring-primary-blue focus:border-transparent outline-none w-64 transition-all"
                            />
                        </div>

                        <div className="flex items-center gap-2 bg-gray-50 p-1 rounded-xl border border-gray-200">
                            {['ALL', 'HEALTHY', 'BLOCKED'].map(f => (
                                <button
                                    key={f}
                                    onClick={() => { setFilterStatus(f); setCurrentPage(1); }}
                                    className={`px-3 py-1.5 rounded-lg text-[10px] font-black uppercase tracking-widest transition-all ${filterStatus === f ? 'bg-white shadow-sm text-primary-blue' : 'text-gray-400 hover:text-gray-600'}`}
                                >
                                    {f}
                                </button>
                            ))}
                        </div>
                    </div>
                </div>

                {/* Data Grid */}
                <div className="bg-white rounded-[2rem] border border-gray-100 shadow-xl shadow-gray-100/30 overflow-hidden flex flex-col flex-1">
                    <div className="overflow-x-auto">
                        <table className="w-full text-left border-collapse">
                            <thead>
                                <tr className="border-b border-gray-100 bg-gray-50/50">
                                    <th className="p-4 text-[10px] font-black text-gray-400 uppercase tracking-widest pl-6">Candidate Profile</th>
                                    <th className="p-4 text-[10px] font-black text-gray-400 uppercase tracking-widest">Base Score</th>
                                    <th className="p-4 text-[10px] font-black text-gray-400 uppercase tracking-widest">Pre-Agent RAG (4)</th>
                                    <th className="p-4 text-[10px] font-black text-gray-400 uppercase tracking-widest">Post-Agent LLM (4)</th>
                                    <th className="p-4 text-[10px] font-black text-gray-400 uppercase tracking-widest">AI Synthesis</th>
                                    <th className="p-4 text-[10px] font-black text-gray-400 uppercase tracking-widest text-right pr-6">Action</th>
                                </tr>
                            </thead>
                            <tbody className="bg-white">
                                {paginatedCandidates.length > 0 ? paginatedCandidates.map(cand => (
                                    <CandidateRow
                                        key={cand.candidate_id}
                                        candidate={cand}
                                        evalData={results.evaluations[cand.candidate_id]}
                                        onSelect={onSelectCandidate}
                                    />
                                )) : (
                                    <tr>
                                        <td colSpan="6" className="p-12 text-center text-gray-400 font-medium">
                                            No candidates found matching criteria.
                                        </td>
                                    </tr>
                                )}
                            </tbody>
                        </table>
                    </div>

                    {/* Pagination Footer */}
                    <div className="mt-auto border-t border-gray-100 p-4 flex items-center justify-between bg-gray-50/30 px-6">
                        <span className="text-xs font-bold text-gray-500 uppercase tracking-widest">
                            Showing {(currentPage - 1) * rowsPerPage + 1} to {Math.min(currentPage * rowsPerPage, filteredCandidates.length)} of {filteredCandidates.length}
                        </span>
                        <div className="flex items-center gap-2">
                            <button
                                onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                                disabled={currentPage === 1}
                                className="p-2 border border-gray-200 rounded-xl bg-white text-gray-600 disabled:opacity-30 hover:bg-gray-50 transition-colors"
                            >
                                <ChevronLeft size={16} />
                            </button>
                            <span className="text-xs font-black text-[#1A1A1A] w-12 text-center">
                                {currentPage} / {totalPages}
                            </span>
                            <button
                                onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                                disabled={currentPage === totalPages}
                                className="p-2 border border-gray-200 rounded-xl bg-white text-gray-600 disabled:opacity-30 hover:bg-gray-50 transition-colors"
                            >
                                <ChevronRight size={16} />
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default CandidateGrid;
