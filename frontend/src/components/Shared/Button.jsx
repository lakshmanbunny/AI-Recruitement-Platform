import React from 'react';
import './Button.css';

const Button = ({ children, onClick, variant = 'primary', loading = false, disabled = false, icon: Icon }) => {
    return (
        <button
            className={`btn btn-${variant} ${loading ? 'btn-loading' : ''}`}
            onClick={onClick}
            disabled={disabled || loading}
        >
            {Icon && <Icon size={18} className="btn-icon" />}
            <span className="btn-text">{children}</span>
            {loading && <div className="spinner-mini"></div>}
        </button>
    );
};

export default Button;
