import React, { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
    LiveKitRoom,
    VideoConference,
    RoomAudioRenderer,
    useDataChannel,
} from '@livekit/components-react';
import { Track } from 'livekit-client';
import '@livekit/components-styles';
import {
    Mic, MicOff, Video as VideoIcon, VideoOff, PhoneOff,
    Loader2, Sparkles, AlertCircle, Shield, Radio,
    Volume2, Cpu, Activity, Layout, MessageSquare
} from 'lucide-react';

// Transcription Overlay Component
const TranscriptionDisplay = () => {
    const { message } = useDataChannel('transcription');
    const [lastTranscript, setLastTranscript] = useState('');
    const [isVisible, setIsVisible] = useState(false);
    const timeoutRef = useRef(null);

    // Watch for new transcriptions
    useEffect(() => {
        if (message?.payload) {
            const text = new TextDecoder().decode(message.payload);
            if (text === 'CLEAR_TRANSCRIPTION') {
                setIsVisible(false);
            } else if (text.trim()) {
                setLastTranscript(text);
                setIsVisible(true);

                if (timeoutRef.current) clearTimeout(timeoutRef.current);
                timeoutRef.current = setTimeout(() => setIsVisible(false), 8000);
            }
        }
    }, [message]);

    if (!isVisible || !lastTranscript) return null;

    return (
        <div className="absolute bottom-32 left-1/2 -translate-x-1/2 z-40 w-full max-w-2xl px-6 pointer-events-none animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="bg-black/60 backdrop-blur-2xl border border-white/10 px-8 py-6 rounded-[2.5rem] shadow-2xl flex items-center gap-6 group transition-all">
                <div className="relative shrink-0">
                    <div className="w-16 h-16 bg-gradient-to-tr from-blue-600 to-indigo-500 rounded-full animate-pulse opacity-30 shadow-[0_0_30px_rgba(79,70,229,0.5)]" />
                    <div className="absolute inset-2 bg-[#020617] rounded-full flex items-center justify-center">
                        <MessageSquare size={24} className="text-blue-400" />
                    </div>
                </div>

                <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                        <span className="text-[10px] font-black uppercase tracking-[0.2em] text-blue-400">AI Heard You</span>
                        <div className="w-1.5 h-1.5 bg-blue-500 rounded-full animate-ping" />
                    </div>
                    <p className="text-white font-bold leading-relaxed text-lg italic">
                        "{lastTranscript}"
                    </p>
                </div>
            </div>
        </div>
    );
};

const InterviewRoom = () => {
    const { roomId } = useParams();
    const navigate = useNavigate();
    const [token, setToken] = useState(null);
    const [livekitUrl, setLivekitUrl] = useState('');
    const [identity, setIdentity] = useState('');
    const [error, setError] = useState(null);
    const [isJoined, setIsJoined] = useState(false);
    const [audioLevel, setAudioLevel] = useState(0);

    const API_BASE = 'http://127.0.0.1:8000/api';

    useEffect(() => {
        // Stimulate audio level for pre-join visual effect
        const interval = setInterval(() => {
            if (!token) setAudioLevel(Math.random() * 40 + 10);
        }, 150);
        return () => clearInterval(interval);
    }, [token]);

    const fetchToken = async () => {
        if (!identity.trim()) return;
        try {
            const configResponse = await fetch(`${API_BASE}/interview/config`);
            if (!configResponse.ok) throw new Error('Security context negotiation failed');
            const configData = await configResponse.json();
            setLivekitUrl(configData.livekit_url);

            const response = await fetch(`${API_BASE}/interview/token?room_id=${roomId}&identity=${identity}`);
            if (!response.ok) throw new Error('Session authorization denied');
            const data = await response.json();
            setToken(data.token);
        } catch (err) {
            setError(err.message);
        }
    };

    if (error) {
        return (
            <div className="min-h-screen bg-[#0F172A] flex items-center justify-center p-4 font-['Inter']">
                <div className="max-w-md w-full bg-[#1E293B] rounded-[2rem] shadow-2xl p-10 text-center border border-red-500/20 backdrop-blur-xl">
                    <div className="w-20 h-20 bg-red-500/10 text-red-400 rounded-3xl flex items-center justify-center mx-auto mb-8 animate-pulse">
                        <AlertCircle size={40} />
                    </div>
                    <h2 className="text-3xl font-black text-white mb-3">Protocol Error</h2>
                    <p className="text-slate-400 mb-10 leading-relaxed">{error}</p>
                    <button
                        onClick={() => navigate('/')}
                        className="w-full bg-white text-[#0F172A] py-5 rounded-2xl font-black text-lg hover:scale-[1.02] active:scale-[0.98] transition-all"
                    >
                        Return to Dashboard
                    </button>
                </div>
            </div>
        );
    }

    if (!token) {
        return (
            <div className="min-h-screen bg-[#0F172A] flex items-center justify-center p-6 font-['Inter'] selection:bg-blue-500/30">
                <div className="max-w-5xl w-full grid md:grid-cols-2 gap-8 items-center">
                    {/* Left Side: Preview UI */}
                    <div className="relative aspect-video bg-[#1E293B] rounded-[2.5rem] overflow-hidden border border-white/5 shadow-2xl group">
                        <div className="absolute inset-0 bg-gradient-to-t from-[#0F172A] via-transparent to-transparent flex flex-col justify-end p-8 z-10">
                            <div className="flex items-center gap-4 mb-2">
                                <div className="flex gap-1 items-end h-8">
                                    {[1, 2, 3, 4, 5].map((i) => (
                                        <div
                                            key={i}
                                            className="w-1.5 bg-emerald-400 rounded-full transition-all duration-150"
                                            style={{ height: `${(audioLevel * (i / 5)) + 20}%` }}
                                        />
                                    ))}
                                </div>
                                <span className="text-white/60 text-xs font-bold uppercase tracking-widest">Audio Systems Ready</span>
                            </div>
                        </div>
                        <div className="absolute inset-0 flex items-center justify-center text-white/20">
                            <VideoIcon size={80} strokeWidth={1} />
                        </div>
                        <div className="absolute top-6 left-6 z-20 bg-emerald-500/20 backdrop-blur-md border border-emerald-400/30 px-3 py-1.5 rounded-full flex items-center gap-2">
                            <div className="w-1.5 h-1.5 bg-emerald-400 rounded-full animate-ping" />
                            <span className="text-emerald-400 text-[10px] font-black uppercase tracking-widest">Live Preview</span>
                        </div>
                    </div>

                    {/* Right Side: Setup Controls */}
                    <div className="p-4">
                        <div className="mb-8 flex items-center gap-3 text-blue-400 bg-blue-500/10 w-fit px-4 py-2 rounded-2xl border border-blue-500/20">
                            <Sparkles size={18} />
                            <span className="text-xs font-black uppercase tracking-[0.2em]">Quantum Screening Engine</span>
                        </div>
                        <h1 className="text-5xl font-black text-white mb-6 leading-tight">
                            Your <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-indigo-400">Technical Session</span> is Ready.
                        </h1>
                        <p className="text-slate-400 text-lg mb-10 leading-relaxed max-w-md">
                            Welcome to Paradigm IT. Please enter your name to authenticate and join the secure interview channel.
                        </p>

                        <div className="space-y-6">
                            <div className="relative group">
                                <input
                                    type="text"
                                    placeholder="Full Name"
                                    value={identity}
                                    onChange={(e) => setIdentity(e.target.value)}
                                    className="w-full bg-[#1E293B] border border-white/5 rounded-2xl px-8 py-5 text-white text-xl font-bold focus:outline-none focus:ring-2 focus:ring-blue-500/50 transition-all placeholder:text-slate-600"
                                />
                                <div className="absolute right-6 top-1/2 -translate-y-1/2 text-slate-600">
                                    <Shield size={20} />
                                </div>
                            </div>

                            <button
                                onClick={fetchToken}
                                disabled={!identity.trim()}
                                className="w-full group bg-gradient-to-r from-blue-600 to-indigo-600 text-white py-6 rounded-2xl font-black text-xl shadow-[0_0_40px_-10px_rgba(37,99,235,0.4)] hover:shadow-[0_0_50px_-5px_rgba(37,99,235,0.6)] hover:scale-[1.01] active:scale-[0.99] transition-all disabled:opacity-50 disabled:grayscale disabled:hover:scale-100 flex items-center justify-center gap-3"
                            >
                                Authenticate & Join Room
                                <Layout size={20} className="group-hover:translate-x-1 transition-transform" />
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        );
    }

    return (
        <div className="h-screen bg-[#020617] overflow-hidden font-['Inter'] text-slate-200">
            <LiveKitRoom
                video={true}
                audio={true}
                token={token}
                serverUrl={livekitUrl}
                onConnected={() => setIsJoined(true)}
                onDisconnected={() => navigate('/')}
                className="h-full flex flex-col relative"
            >
                {/* Custom Modern Header */}
                <header className="absolute top-0 left-0 right-0 z-50 p-8 flex justify-between items-center pointer-events-none">
                    <div className="flex items-center gap-4 bg-black/40 backdrop-blur-xl border border-white/5 p-4 rounded-3xl pointer-events-auto">
                        <div className="w-10 h-10 bg-blue-600 rounded-xl flex items-center justify-center font-black text-white italic">P</div>
                        <div className="pr-4 border-r border-white/10">
                            <h2 className="text-sm font-black uppercase tracking-widest text-white">Paradigm IT</h2>
                            <p className="text-[10px] text-slate-500 font-bold uppercase tracking-widest leading-none">Enterprise HR</p>
                        </div>
                        <div className="flex items-center gap-3 pl-4">
                            <div className="w-2 h-2 bg-emerald-500 rounded-full animate-pulse shadow-[0_0_10px_rgba(16,185,129,0.5)]" />
                            <span className="text-[10px] font-black uppercase tracking-widest text-slate-400">Secure Channel</span>
                        </div>
                    </div>

                    <div className="bg-black/40 backdrop-blur-xl border border-white/5 px-6 py-3 rounded-2xl pointer-events-auto flex items-center gap-3">
                        <Radio size={14} className="text-blue-400" />
                        <span className="text-xs font-black uppercase tracking-widest text-slate-300">Session ID: <span className="text-white">{roomId}</span></span>
                    </div>
                </header>

                {/* Main Video Stage */}
                <main className="flex-1 flex items-center justify-center p-12 pt-28 pb-32">
                    <div className="w-full h-full relative max-w-6xl aspect-video rounded-[3rem] overflow-hidden shadow-[0_0_100px_-20px_rgba(0,0,0,1)] border border-white/5 group">
                        <VideoConference />
                        <RoomAudioRenderer />

                        {/* Overlay Controls (Simulated custom look for dev-only, VideoConference handles real UI) */}
                        <div className="absolute inset-0 pointer-events-none transition-opacity duration-700 opacity-100">
                            {/* Decorative Corner Borders */}
                            <div className="absolute top-0 left-0 w-16 h-16 border-t-4 border-l-4 border-white/10 rounded-tl-[3rem]" />
                            <div className="absolute top-0 right-0 w-16 h-16 border-t-4 border-r-4 border-white/10 rounded-tr-[3rem]" />
                            <div className="absolute bottom-0 left-0 w-16 h-16 border-b-4 border-l-4 border-white/10 rounded-bl-[3rem]" />
                            <div className="absolute bottom-0 right-0 w-16 h-16 border-b-4 border-r-4 border-white/10 rounded-br-[3rem]" />
                        </div>
                    </div>
                </main>

                <TranscriptionDisplay />
                {/* AI Interaction Zone */}
                <div className="absolute bottom-32 left-1/2 -translate-x-1/2 z-40 w-full max-w-2xl px-6 pointer-events-none">
                    <div className="bg-black/60 backdrop-blur-2xl border border-white/10 px-8 py-6 rounded-[2.5rem] shadow-2xl flex items-center gap-6 group transition-all">
                        {/* AI Orb */}
                        <div className="relative shrink-0">
                            <div className="w-16 h-16 bg-gradient-to-tr from-blue-600 to-indigo-500 rounded-full animate-[spin_3s_linear_infinite] opacity-30 shadow-[0_0_30px_rgba(79,70,229,0.5)]" />
                            <div className="absolute inset-2 bg-[#020617] rounded-full flex items-center justify-center">
                                <Activity size={24} className="text-blue-400 animate-pulse" />
                            </div>
                            <div className="absolute -inset-1 border border-blue-500/30 rounded-full animate-ping opacity-20" />
                        </div>

                        <div className="flex-1">
                            <div className="flex items-center gap-2 mb-1">
                                <span className="text-[10px] font-black uppercase tracking-[0.2em] text-blue-400">AI Interviewing</span>
                                <div className="flex gap-1">
                                    <div className="w-1 h-3 bg-blue-500/30 rounded-full animate-[bounce_1s_infinite]" />
                                    <div className="w-1 h-3 bg-blue-500/30 rounded-full animate-[bounce_1.2s_infinite]" />
                                    <div className="w-1 h-3 bg-blue-500/30 rounded-full animate-[bounce_0.8s_infinite]" />
                                </div>
                            </div>
                            <p className="text-white font-bold leading-relaxed text-lg">
                                Processing your response...
                            </p>
                        </div>
                    </div>
                </div>

                {/* Floating Dock Controls (Overlaying VideoConference controls) */}
                <div className="absolute bottom-10 left-1/2 -translate-x-1/2 z-50 flex items-center gap-4 bg-black/60 backdrop-blur-3xl border border-white/10 p-2 rounded-[2rem] shadow-2xl pointer-events-auto transition-transform hover:scale-105">
                    <button className="w-14 h-14 rounded-2xl bg-white/5 hover:bg-white/10 flex items-center justify-center transition-all text-slate-400 hover:text-white">
                        <Mic size={24} />
                    </button>
                    <button className="w-14 h-14 rounded-2xl bg-white/5 hover:bg-white/10 flex items-center justify-center transition-all text-slate-400 hover:text-white">
                        <VideoIcon size={24} />
                    </button>
                    <div className="w-px h-8 bg-white/10 mx-2" />
                    <button
                        onClick={() => navigate('/')}
                        className="h-14 px-8 rounded-2xl bg-red-600 hover:bg-red-500 text-white font-black uppercase tracking-widest text-xs flex items-center gap-3 transition-all shadow-[0_0_20px_rgba(220,38,38,0.3)]"
                    >
                        <PhoneOff size={18} />
                        Terminate Session
                    </button>
                </div>

                {/* Connecting Overlay */}
                {!isJoined && (
                    <div className="absolute inset-0 bg-[#020617] flex flex-col items-center justify-center z-[100] transition-opacity duration-1000">
                        <div className="relative mb-8">
                            <div className="w-24 h-24 border-4 border-blue-500/20 border-t-blue-500 rounded-full animate-spin" />
                            <div className="absolute inset-0 flex items-center justify-center font-black text-blue-500 italic text-xl">P</div>
                        </div>
                        <h2 className="text-3xl font-black text-white uppercase tracking-[0.3em] animate-pulse">Establishing Secure Stream</h2>
                        <p className="text-slate-500 mt-4 font-bold uppercase tracking-widest text-xs">Negotiating with AI Recruiter Cluster...</p>
                    </div>
                )}
            </LiveKitRoom>
        </div>
    );
};

export default InterviewRoom;
