import React from 'react';
import './Header.css';
import { Layout, LogOut, Settings, User } from 'lucide-react';
import { useScreening } from '../../context/ScreeningContext';

const Header = () => {
    const { healthStatus } = useScreening();

    return (
        <header className="main-header">
            <div className="header-left">
                <div className="logo">
                    <span className="logo-icon">▲</span>
                    <span className="logo-text">LUNARIS AI</span>
                </div>
                <nav className="header-nav">
                    <a href="/" className="nav-item active">Dashboard</a>
                    <a href="/candidates" className="nav-item">Candidates</a>
                    <a href="/reports" className="nav-item">Reports</a>
                </nav>
            </div>

            <div className="header-right">
                <div className={`health-badge ${healthStatus}`}>
                    <span className="status-dot"></span>
                    {healthStatus === 'running' ? 'System: Healthy' : 'System: Syncing...'}
                </div>

                <div className="user-profile">
                    <span className="user-name">Mark Reynolds</span>
                    <div className="avatar">MR</div>
                </div>
            </div>
        </header>
    );
};

export default Header;
