import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { ScreeningProvider, useScreening } from './context/ScreeningContext';
import { AuthProvider, useAuth } from './context/AuthContext';
import DashboardLayout from './components/Dashboard/DashboardLayout';
import Dashboard from './pages/Dashboard/Dashboard';
import Processing from './pages/Processing/Processing';
import Results from './pages/Results/Results';
import ApprovedCandidates from './pages/Results/ApprovedCandidates';
import ComingSoon from './pages/Shared/ComingSoon';
import InterviewRoom from './pages/InterviewRoom';
import Landing from './pages/Landing/Landing';
import './index.css';

// Protected Route Component
const ProtectedRoute = ({ children }) => {
  const { currentUser } = useAuth();

  if (!currentUser) {
    return <Navigate to="/login" />;
  }

  return children;
};

// Route wrapper for authenticated users trying to access login page
const AuthRoute = ({ children }) => {
  const { currentUser } = useAuth();

  if (currentUser) {
    return <Navigate to="/" />;
  }

  return children;
};

const AppContent = () => {
  const { isScreening, results, isInitializing, error } = useScreening();

  if (isInitializing) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-white">
        <div className="flex flex-col items-center gap-8 max-w-md w-full px-6">
          <div className="relative">
            <div className="w-20 h-20 border-[3px] border-primary-blue/10 rounded-[24px] absolute inset-0"></div>
            <div className="w-20 h-20 border-[3px] border-primary-blue border-t-transparent rounded-[24px] animate-spin"></div>
            <div className="absolute inset-x-0 -bottom-1 h-1 bg-white"></div>
          </div>
          <div className="flex flex-col items-center gap-4 text-center">
            <div className="flex flex-col items-center gap-2">
              <p className="text-[#0A0F1E] font-black text-xs uppercase tracking-[0.4em]">Initializing</p>
              <p className="text-primary-blue font-bold text-[10px] uppercase tracking-[0.2em] animate-pulse">Recruitment Intelligence Runtime</p>
            </div>

            {error && (
              <div className="mt-4 p-4 bg-red-50 rounded-xl border border-red-100 animate-in fade-in slide-in-from-bottom-2 duration-500">
                <p className="text-red-600 text-[11px] font-medium mb-3">System Boot Interrupt: {error}</p>
                <div className="flex gap-2 justify-center">
                  <button
                    onClick={() => window.location.reload()}
                    className="px-4 py-2 bg-red-600 text-white text-[10px] font-bold uppercase tracking-wider rounded-lg hover:bg-red-700 transition-colors"
                  >
                    Retry Connection
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }

  return (
    <Router>
      <Routes>
        {/* Public Routes */}
        <Route
          path="/login"
          element={
            <AuthRoute>
              <Landing />
            </AuthRoute>
          }
        />

        {/* Protected Routes - Full screen */}
        <Route
          path="/interview/:roomId"
          element={
            <ProtectedRoute>
              <InterviewRoom />
            </ProtectedRoute>
          }
        />

        {/* Protected Routes - Dashboard Layout */}
        <Route
          path="*"
          element={
            <ProtectedRoute>
              <DashboardLayout>
                <Routes>
                  <Route path="/" element={
                    isScreening ? <Navigate to="/processing" /> :
                      results ? <Navigate to="/results" /> :
                        <Dashboard />
                  } />
                  <Route path="/processing" element={
                    isScreening ? <Processing /> :
                      results ? <Navigate to="/results" /> :
                        <Navigate to="/" />
                  } />
                  <Route path="/results" element={
                    results ? <Results /> :
                      isScreening ? <Navigate to="/processing" /> :
                        <Navigate to="/" />
                  } />
                  <Route path="/approved-candidates" element={<ApprovedCandidates />} />
                  <Route path="/candidates" element={<ComingSoon title="Candidates Intelligence" />} />
                  <Route path="/settings" element={<ComingSoon title="System Settings" />} />
                  <Route path="*" element={<Navigate to="/" />} />
                </Routes>
              </DashboardLayout>
            </ProtectedRoute>
          }
        />
      </Routes>
    </Router>
  );
};

const App = () => {
  return (
    <AuthProvider>
      <ScreeningProvider>
        <AppContent />
      </ScreeningProvider>
    </AuthProvider>
  );
};

export default App;
