import React from 'react';
import { Construction } from 'lucide-react';

const ComingSoon = ({ title }) => {
    return (
        <div className="flex flex-1 flex-col items-center justify-center p-14 bg-bg-muted text-center">
            <div className="w-20 h-20 bg-primary-blue/10 rounded-2xl flex items-center justify-center text-primary-blue mb-6">
                <Construction size={40} />
            </div>
            <h1 className="text-3xl font-bold text-[#1A1A1A] mb-2">{title}</h1>
            <p className="text-gray-500 max-w-sm">
                We're currently under construction. This feature will be available in a future version of the Paradigm IT Intelligent Dashboard.
            </p>
        </div>
    );
};

export default ComingSoon;
