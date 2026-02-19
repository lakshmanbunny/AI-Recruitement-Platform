import Header from '../Header/Header';
import './MainLayout.css';

const MainLayout = ({ children }) => {
    return (
        <div className="layout-wrapper">
            <Header />
            <main className="layout-content">
                {children}
            </main>
        </div>
    );
};

export default MainLayout;
