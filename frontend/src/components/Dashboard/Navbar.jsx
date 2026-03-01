import React, { useState } from 'react';
import { NavLink } from 'react-router-dom';
import { useScreening } from '../../context/ScreeningContext';
import { useAuth } from '../../context/AuthContext';
import logo from '../../assets/paradigmlogo.jpg';
import { Menu, X, Bell, User, LogOut } from 'lucide-react';

const Navbar = () => {
    const { healthStatus } = useScreening();
    const { currentUser, logout } = useAuth();
    const [isMenuOpen, setIsMenuOpen] = useState(false);

    const toggleMenu = () => setIsMenuOpen(!isMenuOpen);

    const getInitials = (name) => {
        if (!name) return '??';
        return name.split(' ').map(n => n[0]).join('').toUpperCase().substring(0, 2);
    };

    const navLinkClass = ({ isActive }) =>
        `text-sm font-medium h-full flex items-center transition-all px-2 relative group ${isActive
            ? 'text-primary-blue'
            : 'text-text-muted hover:text-text-main'
        }`;

    return (
        <nav className="h-20 flex items-center justify-between px-8 md:px-12 bg-white/80 backdrop-blur-xl border-b border-border-subtle sticky top-0 z-50">
            <div className="flex items-center gap-12 h-full">
                <NavLink to="/" className="flex items-center gap-3">
                    <img src={logo} alt="Paradigm IT Logo" className="h-15 w-auto" />
                    {/* <span className="text-xl font-bold tracking-tight text-[#0A0F1E]">Paradigm<span className="text-primary-blue">IT</span></span> */}
                </NavLink>

                {/* Desktop Menu */}
                <div className="hidden md:flex items-center gap-8 h-full">
                    <NavLink to="/" className={navLinkClass}>
                        Dashboard
                        <span className="absolute bottom-0 left-2 right-2 h-0.5 bg-primary-blue scale-x-0 group-hover:scale-x-100 transition-transform origin-left"></span>
                    </NavLink>
                    <NavLink to="/approved-candidates" className={navLinkClass}>
                        Approved
                        <span className="absolute bottom-0 left-2 right-2 h-0.5 bg-primary-blue scale-x-0 group-hover:scale-x-100 transition-transform origin-left"></span>
                    </NavLink>
                    <NavLink to="/candidates" className={navLinkClass}>
                        Profiles
                        <span className="absolute bottom-0 left-2 right-2 h-0.5 bg-primary-blue scale-x-0 group-hover:scale-x-100 transition-transform origin-left"></span>
                    </NavLink>
                </div>
            </div>

            <div className="flex items-center gap-6">
                {/* Health Indicator */}
                <div className="hidden lg:flex items-center gap-2.5 px-4 py-2 bg-primary-blue/5 border border-primary-blue/10 rounded-full">
                    <div className="relative">
                        <div className={`w-2.5 h-2.5 rounded-full ${healthStatus === 'running' ? 'bg-success' : 'bg-gray-300'}`}></div>
                        {healthStatus === 'running' && (
                            <div className="absolute inset-0 w-2.5 h-2.5 rounded-full bg-success animate-ping opacity-75"></div>
                        )}
                    </div>
                    <span className="text-[11px] font-bold text-primary-dark uppercase tracking-wider">
                        {healthStatus === 'running' ? 'Live System' : 'Connecting...'}
                    </span>
                </div>

                {/* User Section */}
                <div className="hidden md:flex items-center gap-4 pl-6 border-l border-border-subtle">
                    <div className="flex flex-col items-end">
                        <span className="text-sm font-bold text-[#0A0F1E]">{currentUser?.displayName || 'User Account'}</span>
                        <span className="text-[10px] text-text-muted font-medium uppercase tracking-[0.1em]">Enterprise Tier</span>
                    </div>

                    <button className="relative group">
                        {currentUser?.photoURL ? (
                            <img src={currentUser.photoURL} alt="Avatar" className="w-10 h-10 rounded-xl border border-border-subtle shadow-sm transition-transform group-hover:scale-105" />
                        ) : (
                            <div className="w-10 h-10 bg-primary-blue/10 border border-primary-blue/20 rounded-xl flex items-center justify-center text-sm font-bold text-primary-blue transition-transform group-hover:scale-105">
                                {getInitials(currentUser?.displayName)}
                            </div>
                        )}
                    </button>

                    <button
                        onClick={logout}
                        className="p-2 text-text-muted hover:text-red-500 transition-colors"
                        title="Sign Out"
                    >
                        <LogOut size={20} />
                    </button>
                </div>

                {/* Mobile Menu Button */}
                <button className="md:hidden p-2 text-[#0A0F1E]" onClick={toggleMenu}>
                    {isMenuOpen ? <X size={26} /> : <Menu size={26} />}
                </button>
            </div>

            {/* Mobile Menu Overlay */}
            {isMenuOpen && (
                <div className="absolute top-20 left-0 w-full bg-white border-b border-border-subtle shadow-2xl md:hidden z-40 animate-in slide-in-from-top duration-300">
                    <div className="flex flex-col p-6 gap-5">
                        <NavLink to="/" onClick={() => setIsMenuOpen(false)} className="text-lg font-bold text-[#0A0F1E]">Dashboard</NavLink>
                        <NavLink to="/approved-candidates" onClick={() => setIsMenuOpen(false)} className="text-lg font-medium text-text-muted">Approved</NavLink>
                        <NavLink to="/candidates" onClick={() => setIsMenuOpen(false)} className="text-lg font-medium text-text-muted">Profiles</NavLink>
                        <hr className="border-border-subtle" />
                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-4">
                                <div className="w-12 h-12 bg-primary-blue/10 rounded-2xl flex items-center justify-center text-base font-bold text-primary-blue">
                                    {getInitials(currentUser?.displayName)}
                                </div>
                                <div className="flex flex-col">
                                    <span className="text-base font-bold text-[#0A0F1E]">{currentUser?.displayName}</span>
                                    <span className="text-xs text-text-muted">Enterprise Member</span>
                                </div>
                            </div>
                            <button onClick={logout} className="p-3 bg-red-50 text-red-500 rounded-xl">
                                <LogOut size={22} />
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </nav>
    );
};

export default Navbar;
