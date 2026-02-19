import React, { useState } from 'react';
import { NavLink } from 'react-router-dom';
import { useScreening } from '../../context/ScreeningContext';
import logo from '../../assets/paradigmlogo.jpg';
import { Menu, X } from 'lucide-react';

const Navbar = () => {
    const { healthStatus } = useScreening();
    const [isMenuOpen, setIsMenuOpen] = useState(false);

    const toggleMenu = () => setIsMenuOpen(!isMenuOpen);

    const navLinkClass = ({ isActive }) =>
        `text-sm font-medium h-full flex items-center transition-all px-1 border-b-2 ${isActive
            ? 'text-text-main border-primary-blue font-semibold font-bold'
            : 'text-text-muted hover:text-text-main border-transparent'
        }`;

    return (
        <nav className="h-16 flex items-center justify-between px-6 md:px-12 bg-white border-b border-gray-200 sticky top-0 z-50">
            <div className="flex items-center gap-6 md:gap-10 h-full">
                <div className="flex items-center gap-3">
                    <img src={logo} alt="Paradigm IT Logo" className="h-15 w-auto object-contain" />
                </div>

                {/* Desktop Menu */}
                <div className="hidden md:flex items-center gap-8 h-full">
                    <NavLink to="/" className={navLinkClass}>Dashboard</NavLink>
                    <NavLink to="/approved-candidates" className={navLinkClass}>Approved</NavLink>
                    <NavLink to="/candidates" className={navLinkClass}>Profiles</NavLink>
                </div>
            </div>

            <div className="flex items-center gap-4 md:gap-8 justify-center">
                {/* Status - Desktop Only */}
                <div className="hidden lg:flex items-center gap-2 px-3 py-1.5 bg-bg-muted border border-gray-200 rounded-full text-xs font-semibold self-center">
                    <span className={`w-2 h-2 rounded-full ${healthStatus === 'running' ? 'bg-success shadow-[0_0_8px_#10B981]' : 'bg-gray-300'}`}></span>
                    {healthStatus === 'running' ? 'System: Healthy' : 'System: Syncing...'}
                </div>

                <div className="hidden md:flex items-center gap-3 self-center">
                    <span className="text-sm font-medium">Mark Reynolds</span>
                    <div className="w-8 h-8 bg-gray-100 rounded-full flex items-center justify-center text-xs font-bold text-gray-500">MR</div>
                </div>

                {/* Mobile Menu Button */}
                <button className="md:hidden p-2 text-gray-600 self-center" onClick={toggleMenu}>
                    {isMenuOpen ? <X size={24} /> : <Menu size={24} />}
                </button>
            </div>

            {/* Mobile Menu Overlay */}
            {isMenuOpen && (
                <div className="absolute top-16 left-0 w-full bg-white border-b border-gray-200 shadow-lg md:hidden z-40">
                    <div className="flex flex-col p-4 gap-4">
                        <NavLink to="/" onClick={() => setIsMenuOpen(false)} className="text-base font-semibold">Dashboard</NavLink>
                        <NavLink to="/candidates" onClick={() => setIsMenuOpen(false)} className="text-base font-medium text-text-muted">Candidates</NavLink>
                        <NavLink to="/settings" onClick={() => setIsMenuOpen(false)} className="text-base font-medium text-text-muted">Settings</NavLink>
                        <hr className="border-gray-100" />
                        <div className="flex items-center gap-3 py-2">
                            <div className="w-8 h-8 bg-gray-100 rounded-full flex items-center justify-center text-xs font-bold text-gray-500">MR</div>
                            <span className="text-sm font-medium">Mark Reynolds</span>
                        </div>
                    </div>
                </div>
            )}
        </nav>
    );
};

export default Navbar;
