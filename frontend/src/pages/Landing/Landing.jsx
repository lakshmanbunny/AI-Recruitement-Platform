import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import logo from '../../assets/paradigmlogo.jpg';

const Landing = () => {
    const { loginWithGoogle } = useAuth();
    const navigate = useNavigate();
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        return () => {
            setError('');
            setLoading(false);
        };
    }, []);

    const handleGoogleLogin = async () => {
        try {
            setError('');
            setLoading(true);
            await loginWithGoogle();
            navigate('/');
        } catch (err) {
            console.error("LOG: Auth error:", err);
            if (err.code === 'auth/configuration-not-found') {
                setError('Authentication Error: Please enable the Google Sign-In provider in your Firebase Console.');
            } else {
                setError(err.message || 'Failed to sign in. Please check your configuration.');
            }
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="relative w-full h-screen overflow-hidden bg-white flex flex-col items-center justify-center font-sans tracking-tight">
            {/* Soft Ambient Background Elements */}
            <div className="absolute top-[-20%] left-[-10%] w-[60%] h-[60%] bg-primary-blue/5 blur-[120px] rounded-full"></div>
            <div className="absolute bottom-[-10%] right-[-10%] w-[50%] h-[50%] bg-primary-light/20 blur-[100px] rounded-full"></div>

            {/* Subtle Grid Pattern */}
            <div className="absolute inset-0 opacity-[0.03] pointer-events-none"
                style={{ backgroundImage: 'radial-gradient(#0066FF 1px, transparent 1px)', backgroundSize: '48px 48px' }}>
            </div>

            <div className="relative z-10 flex flex-col items-center justify-center p-12 md:p-20 max-w-2xl w-full">
                {/* Brand Identity */}
                <div className="mb-12 flex flex-col items-center gap-6">
                    <img src={logo} alt="Paradigm IT" className="h-16 w-auto drop-shadow-sm" />
                    <div className="h-1 w-12 bg-primary-blue rounded-full"></div>
                </div>

                <div className="text-center space-y-6 mb-16">
                    <h1 className="text-5xl md:text-6xl font-black text-[#0A0F1E] tracking-tighter leading-[1.1]">
                        Talent <span className="text-primary-blue">Intelligence</span> <br className="hidden md:block" /> Simplified.
                    </h1>

                    <p className="text-text-muted max-w-lg mx-auto text-base md:text-lg font-medium leading-relaxed">
                        The ultimate enterprise bridge between sophisticated AI workflows and high-performance recruitment.
                    </p>
                </div>

                {error && (
                    <div className="mb-10 w-full p-5 bg-red-50 border border-red-100 rounded-2xl text-red-500 text-sm text-center font-bold shadow-sm animate-in fade-in slide-in-from-top-2">
                        {error}
                    </div>
                )}

                <div className="w-full max-w-sm">
                    <button
                        onClick={handleGoogleLogin}
                        disabled={loading}
                        className="group relative flex items-center justify-center gap-4 w-full py-5 bg-[#0A0F1E] hover:bg-[#1A2645] text-white rounded-2xl font-bold transition-all duration-300 shadow-2xl hover:shadow-primary-blue/20 active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        {loading ? (
                            <div className="w-6 h-6 border-3 border-white border-t-transparent rounded-full animate-spin"></div>
                        ) : (
                            <>
                                <svg viewBox="0 0 24 24" className="w-5 h-5 fill-current" xmlns="http://www.w3.org/2000/svg">
                                    <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
                                    <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
                                    <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
                                    <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
                                </svg>
                                <span>Get Started with Google</span>
                            </>
                        )}
                    </button>

                    <div className="mt-10 flex items-center justify-center gap-3">
                        <div className="w-2 h-2 rounded-full bg-primary-blue animate-pulse"></div>
                        <p className="text-[#0A0F1E] text-[10px] font-black uppercase tracking-[0.4em]">Enterprise Portal</p>
                    </div>
                </div>
            </div>

            {/* Bottom Branding Bar */}
            <div className="absolute bottom-12 w-full px-12 flex justify-between items-center text-[10px] font-black text-text-muted uppercase tracking-[0.3em]">
                <div>© 2026 Paradigm IT</div>
                <div className="flex gap-8">
                    <span className="hover:text-primary-blue cursor-pointer transition-colors">Privacy</span>
                    <span className="hover:text-primary-blue cursor-pointer transition-colors">Security</span>
                </div>
            </div>
        </div>
    );
};

export default Landing;
