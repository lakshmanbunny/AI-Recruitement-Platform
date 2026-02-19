import React from 'react';
import Hero from '../../components/Dashboard/Hero';
import StatusCards from '../../components/Dashboard/StatusCards';
import EmptyState from '../../components/Dashboard/EmptyState';

const Dashboard = () => {
    return (
        <div className="flex flex-col flex-1 bg-white">
            <Hero />
            <StatusCards />
            <EmptyState />
        </div>
    );
};

export default Dashboard;
