import React from 'react';
import { CheckCircle, Circle, Loader2 } from 'lucide-react';
import { useScreening } from '../../context/ScreeningContext';

const Processing = () => {
    const { STAGES, currentStep } = useScreening();

    return (
        <div className="flex flex-1 flex-col items-center justify-center p-14 bg-bg-muted overflow-y-auto">
            <div className="flex flex-col items-center gap-6 text-center mb-10 shrink-0">
                <div className="relative w-24 h-24 flex items-center justify-center">
                    <div className="z-10 text-primary-blue">
                        <Loader2 className="animate-spin" size={40} />
                    </div>
                    <div className="absolute w-full h-full rounded-full bg-[radial-gradient(circle,_rgba(0,102,255,0.2)_0%,_transparent_70%)] animate-pulse"></div>
                </div>

                <div className="flex flex-col gap-2">
                    <h2 className="text-2xl font-black text-[#1A1A1A]">Unified Intelligence Audit</h2>
                    <p className="text-gray-500 max-w-sm text-sm font-medium">Multiple AI agents are working together to evaluate your candidates.</p>
                </div>
            </div>

            <div className="w-full max-w-lg flex flex-col gap-3">
                {STAGES.map((stage, index) => {
                    const isCompleted = index < currentStep;
                    const isActive = index === currentStep;
                    const isPending = index > currentStep;

                    return (
                        <div
                            key={stage.id}
                            className={`flex items-center gap-4 p-4 rounded-2xl border transition-all duration-500 ${isActive
                                    ? 'bg-white border-primary-blue shadow-lg shadow-blue-50 scale-[1.02]'
                                    : isCompleted
                                        ? 'bg-success-light border-success-light/30 opacity-80'
                                        : 'bg-white border-gray-100 opacity-40'
                                }`}
                        >
                            <div className="shrink-0">
                                {isCompleted ? (
                                    <div className="p-1 bg-success-text text-white rounded-full">
                                        <CheckCircle size={16} />
                                    </div>
                                ) : isActive ? (
                                    <div className="text-primary-blue">
                                        <Loader2 className="animate-spin" size={20} />
                                    </div>
                                ) : (
                                    <div className="text-gray-300">
                                        <Circle size={20} />
                                    </div>
                                )}
                            </div>

                            <div className="flex flex-col">
                                <span className={`text-sm font-black ${isActive ? 'text-primary-blue' : isCompleted ? 'text-success-text' : 'text-gray-400'
                                    }`}>
                                    {stage.label}
                                </span>
                                {isActive && (
                                    <span className="text-xs text-gray-500 font-medium animate-pulse">
                                        {stage.description}
                                    </span>
                                )}
                            </div>
                        </div>
                    );
                })}
            </div>
        </div>
    );
};

export default Processing;
