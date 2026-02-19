import React from 'react';
import { Upload, Link as LinkIcon } from 'lucide-react';

const EmptyState = () => {
    return (
        <section className="mt-4 md:mt-8 p-6 md:p-12 bg-bg-muted rounded-2xl border-2 border-dashed border-gray-200 flex flex-col items-center gap-6 text-center max-w-4xl mx-auto w-full mb-16">
            <div className="w-16 md:w-24 h-16 md:h-24 bg-white rounded-xl flex items-center justify-center shadow-soft relative overflow-hidden group">
                <div className="w-10 md:w-12 h-10 md:h-12 bg-primary-blue/10 rounded-full flex items-center justify-center group-hover:scale-110 transition-transform">
                    <div className="w-5 md:w-6 h-5 md:h-6 bg-primary-blue rounded rotate-45"></div>
                </div>
            </div>

            <div className="max-w-md">
                <h3 className="text-lg md:text-xl font-bold text-[#1A1A1A] mb-2">No candidates screened yet</h3>
                <p className="text-xs md:text-sm text-gray-500 leading-relaxed">
                    Start by uploading resume files or importing profiles via URL. Paradigm IT will extract intelligence and verify credentials automatically.
                </p>
            </div>

            <div className="flex gap-4">
                <button className="flex items-center gap-2 px-6 py-3 bg-white border border-gray-200 rounded-lg font-semibold text-sm hover:bg-gray-50 transition-colors shadow-sm active:scale-[0.98]">
                    <Upload size={16} />
                    <span>Upload CV</span>
                </button>
                <button className="flex items-center gap-2 px-6 py-3 bg-white border border-gray-200 rounded-lg font-semibold text-sm hover:bg-gray-50 transition-colors shadow-sm active:scale-[0.98]">
                    <LinkIcon size={16} />
                    <span>Import URL</span>
                </button>
            </div>
        </section>
    );
};

export default EmptyState;
