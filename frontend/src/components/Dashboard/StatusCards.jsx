import React from 'react';
import { ShieldCheck, Cpu } from 'lucide-react';

const StatusCards = () => {
    return (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 w-full max-w-4xl mx-auto mb-16 px-6">
            <div className="p-6 bg-white border border-gray-200 rounded-xl shadow-soft flex flex-col gap-3">
                <div className="flex items-center gap-3">
                    <div className="w-9 h-9 bg-blue-50 text-blue-500 rounded-lg flex items-center justify-center">
                        <ShieldCheck size={20} />
                    </div>
                    <span className="text-xs font-bold text-gray-400 uppercase tracking-wider">System Status</span>
                </div>
                <div className="flex items-center gap-2">
                    <span className="text-3xl font-bold tracking-tight">Healthy</span>
                    <div className="w-2 h-2 rounded-full bg-success animate-pulse"></div>
                </div>
                <p className="text-xs text-gray-500">Pipeline is fully operational and ready.</p>
            </div>

            <div className="p-6 bg-white border border-gray-200 rounded-xl shadow-soft flex flex-col gap-3">
                <div className="flex items-center gap-3">
                    <div className="w-9 h-9 bg-purple-50 text-purple-500 rounded-lg flex items-center justify-center">
                        <Cpu size={20} />
                    </div>
                    <span className="text-xs font-bold text-gray-400 uppercase tracking-wider">AI Engine</span>
                </div>
                <div className="flex items-center gap-2">
                    <span className="text-3xl font-bold tracking-tight">Gemini 2.0</span>
                    <span className="px-2 py-0.5 bg-purple-100 text-purple-600 text-[10px] font-bold rounded uppercase">Active</span>
                </div>
                <p className="text-xs text-gray-500">Unified Intelligence Agent initialized.</p>
            </div>
        </div>
    );
};

export default StatusCards;
