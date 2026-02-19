import React from 'react';
import { Zap } from 'lucide-react';
import { useScreening } from '../../context/ScreeningContext';

const Hero = () => {
    const { runScreening, isScreening } = useScreening();

    return (
        <section className="flex flex-col items-center text-center py-10 md:py-16 px-6 max-w-4xl mx-auto">
            <h1 className="text-3xl md:text-5xl font-bold tracking-tight text-[#1A1A1A] mb-4">
                AI Recruitment Intelligence
            </h1>
            <p className="text-base md:text-lg text-gray-500 max-w-2xl mb-8 md:mb-10 leading-relaxed">
                Accelerate your hiring with deep-context candidate evaluation grounded in real-world GitHub evidence and technical intelligence.
            </p>
            <button
                onClick={runScreening}
                disabled={isScreening}
                className="flex items-center gap-2 px-8 py-4 bg-primary-blue text-white rounded-lg font-bold text-base hover:bg-primary-dark transition-all active:scale-[0.98] disabled:bg-blue-300 shadow-lg shadow-blue-500/20"
            >
                {isScreening ? (
                    <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
                ) : (
                    <Zap size={20} className="fill-current" />
                )}
                <span>Run Screening</span>
            </button>
        </section>
    );
};

export default Hero;
