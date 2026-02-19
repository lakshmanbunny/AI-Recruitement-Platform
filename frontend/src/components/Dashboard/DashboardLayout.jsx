import React from 'react';
import Navbar from './Navbar';

const DashboardLayout = ({ children }) => {
    return (
        <div className="min-h-screen bg-white flex flex-col">
            <Navbar />
            <main className="flex-1 flex flex-col overflow-y-auto">
                {children}
            </main>
            <footer className="py-8 px-12 border-t border-gray-100 bg-gray-50 flex items-center justify-between text-[11px] font-medium text-gray-400 uppercase tracking-widest">
                <div className="flex items-center gap-4">
                    <span className="flex items-center gap-1.5">
                        <span className="w-1.5 h-1.5 rounded-full bg-success"></span>
                        API Connected
                    </span>
                    <span>Last Sync: Just now</span>
                </div>
                <div>© 2026 Paradigm IT Intelligence • Professional Edition</div>
            </footer>
        </div>
    );
};

export default DashboardLayout;
