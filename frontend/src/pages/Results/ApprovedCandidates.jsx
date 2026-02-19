import React from 'react';
import { useScreening } from '../../context/ScreeningContext';
import { FileText, CheckCircle, ExternalLink, Calendar, MessageSquare, User, Sparkles } from 'lucide-react';

const ApprovedCandidates = () => {
    const { results } = useScreening();

    // Filter candidates who have been approved by HR
    const approvedCandidates = results ? Object.entries(results.evaluations)
        .filter(([_, evalData]) => evalData.hr_decision?.status === 'COMPLETED' && evalData.hr_decision?.decision === 'APPROVE')
        .map(([id, evalData]) => ({
            id,
            ...evalData,
            basicInfo: results.ranking.find(r => r.candidate_id === id)
        })) : [];

    return (
        <div className="flex-1 p-8 md:p-12 bg-white overflow-y-auto">
            <div className="max-w-6xl mx-auto">
                <div className="flex flex-col gap-2 mb-12">
                    <h1 className="text-3xl font-black text-[#1A1A1A] uppercase tracking-tighter">Approved Candidates</h1>
                    <p className="text-gray-400 font-medium">Historical archive of HR-finalized hiring decisions and audit trails.</p>
                </div>

                {approvedCandidates.length > 0 ? (
                    <div className="grid grid-cols-1 gap-6">
                        {approvedCandidates.map((candidate) => (
                            <div key={candidate.id} className="group border border-gray-100 rounded-[2.5rem] p-8 hover:shadow-2xl hover:shadow-gray-100 transition-all bg-white relative overflow-hidden">
                                <div className="absolute top-0 right-0 p-8">
                                    <div className="flex items-center gap-2 px-4 py-2 bg-green-50 rounded-full border border-green-100">
                                        <CheckCircle size={16} className="text-success-text" />
                                        <span className="text-[10px] font-black text-success-text uppercase tracking-widest">Decision: Approved</span>
                                    </div>
                                </div>

                                <div className="flex flex-col md:flex-row gap-8">
                                    <div className="w-20 h-20 bg-gray-50 rounded-[2rem] flex items-center justify-center text-gray-400 group-hover:bg-primary-blue group-hover:text-white transition-all duration-500">
                                        <User size={32} />
                                    </div>

                                    <div className="flex flex-col flex-1 gap-6">
                                        <div className="flex flex-col gap-1">
                                            <h3 className="text-2xl font-black text-[#1A1A1A] uppercase tracking-tighter">{candidate.basicInfo?.name}</h3>
                                            <div className="flex items-center gap-4 text-xs font-bold text-gray-400">
                                                <div className="flex items-center gap-1.5"><Calendar size={14} /> Approved {new Date(candidate.hr_decision.timestamp).toLocaleDateString()}</div>
                                                <div className="flex items-center gap-1.5 uppercase tracking-widest"><FileText size={14} /> ID: {candidate.id}</div>
                                            </div>
                                        </div>

                                        <div className="p-6 bg-gray-50 rounded-3xl border border-gray-100">
                                            <div className="flex items-start gap-3">
                                                <MessageSquare size={18} className="text-primary-blue mt-1" />
                                                <div className="flex flex-col gap-1">
                                                    <span className="text-[10px] font-black text-gray-400 uppercase tracking-widest">HR Final Notes</span>
                                                    <p className="text-sm font-medium text-slate-700 leading-relaxed italic">"{candidate.hr_decision.notes || 'No notes provided.'}"</p>
                                                </div>
                                            </div>
                                        </div>

                                        <div className="flex items-center gap-3 mt-2">
                                            <button
                                                onClick={async () => {
                                                    try {
                                                        const response = await fetch('http://127.0.0.1:8000/api/interview/create', {
                                                            method: 'POST',
                                                            headers: { 'Content-Type': 'application/json' },
                                                            body: JSON.stringify({
                                                                candidate_id: candidate.id,
                                                                candidate_name: candidate.basicInfo?.name,
                                                                candidate_email: candidate.id === 'C001' ? 'bunnylakshman1@gmail.com' : 'test@example.com' // Updated to user's email
                                                            })
                                                        });
                                                        if (response.ok) {
                                                            const data = await response.json();
                                                            alert(`Interview invite sent successfully to bunnylakshman1@gmail.com!\nRoom ID: ${data.room_id}`);
                                                        }
                                                    } catch (err) {
                                                        alert('Failed to send invite');
                                                    }
                                                }}
                                                className="flex items-center gap-2 px-6 py-3 bg-primary-blue text-white rounded-full text-[10px] font-black uppercase tracking-widest hover:bg-blue-600 transition-colors group/btn"
                                            >
                                                Invite to AI Interview <Sparkles size={14} className="group-hover/btn:scale-110 transition-transform" />
                                            </button>
                                            <button className="flex items-center gap-2 px-6 py-3 bg-[#1A1A1A] text-white rounded-full text-[10px] font-black uppercase tracking-widest hover:bg-primary-blue transition-colors group/btn">
                                                View Complete Report <ExternalLink size={14} className="group-hover/btn:translate-x-0.5 group-hover/btn:-translate-y-0.5 transition-transform" />
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                ) : (
                    <div className="flex flex-col items-center justify-center py-24 bg-gray-50 rounded-[3rem] border border-dashed border-gray-200">
                        <div className="w-16 h-16 bg-white rounded-2xl shadow-sm flex items-center justify-center text-gray-300 mb-6">
                            <FileText size={32} />
                        </div>
                        <h3 className="text-xl font-black text-[#1A1A1A] uppercase tracking-tighter mb-2">No Approved Candidates</h3>
                        <p className="text-gray-400 font-medium max-w-sm text-center px-6">Once you approve candidates from the screening results page, they will appear here as a historical record.</p>
                    </div>
                )}
            </div>
        </div>
    );
};

export default ApprovedCandidates;
