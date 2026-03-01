import React from 'react';
import Navbar from './Navbar';

const DashboardLayout = ({ children }) => {
    return (
        <div className="min-h-screen bg-[#F8FAFC] flex flex-col font-sans">
            <Navbar />

            <main className="flex-1 flex flex-col p-6 md:p-10 lg:p-12 max-w-[1600px] mx-auto w-full">
                {/* Subtle breadcrumb or spacer */}
                <div className="mb-8 flex items-center justify-between">
                    <div>
                        <h2 className="text-[11px] font-black uppercase tracking-[0.3em] text-primary-blue mb-1">Recruitment Pipeline</h2>
                        <div className="h-1 w-8 bg-primary-blue/30 rounded-full"></div>
                    </div>
                </div>

                <div className="animate-in fade-in slide-in-from-bottom-4 duration-700">
                    {children}
                </div>
            </main>

            <footer className="py-10 px-8 md:px-12 border-t border-border-subtle bg-white/50 backdrop-blur-sm flex flex-col md:flex-row items-center justify-between gap-6">
                <div className="flex items-center gap-8 order-2 md:order-1">
                    <div className="flex items-center gap-2 px-3 py-1.5 bg-success/5 border border-success/10 rounded-full">
                        <span className="w-1.5 h-1.5 rounded-full bg-success animate-pulse"></span>
                        <span className="text-[10px] font-bold text-success-text uppercase tracking-widest">API Status: Healthy</span>
                    </div>
                    <span className="text-[10px] font-semibold text-text-muted uppercase tracking-[0.2em] hidden sm:inline">Professional Enterprise Edition</span>
                </div>

                <div className="text-[10px] font-bold text-text-muted uppercase tracking-[0.3em] order-1 md:order-2">
                    © 2026 Paradigm IT Intelligence • Built for Excellence
                </div>
            </footer>
        </div>
    );
};

export default DashboardLayout;
