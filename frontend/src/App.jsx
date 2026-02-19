import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { ScreeningProvider, useScreening } from './context/ScreeningContext';
import DashboardLayout from './components/Dashboard/DashboardLayout';
import Dashboard from './pages/Dashboard/Dashboard';
import Processing from './pages/Processing/Processing';
import Results from './pages/Results/Results';
import ApprovedCandidates from './pages/Results/ApprovedCandidates';
import ComingSoon from './pages/Shared/ComingSoon';
import InterviewRoom from './pages/InterviewRoom';
import './index.css';

const AppContent = () => {
  const { isScreening, results, isInitializing } = useScreening();

  if (isInitializing) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-[#0F172A] text-white">
        <div className="flex flex-col items-center gap-4">
          <div className="w-12 h-12 border-4 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
          <p className="text-blue-400 font-medium animate-pulse">Initializing Recruitment Intelligence...</p>
        </div>
      </div>
    );
  }

  return (
    <Router>
      <Routes>
        {/* Full-screen route for Interview - NO LAYOUT WRAPPER */}
        <Route path="/interview/:roomId" element={<InterviewRoom />} />

        {/* All other routes wrapped in DashboardLayout */}
        <Route
          path="*"
          element={
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
          }
        />
      </Routes>
    </Router>
  );
};

const App = () => {
  return (
    <ScreeningProvider>
      <AppContent />
    </ScreeningProvider>
  );
};

export default App;
