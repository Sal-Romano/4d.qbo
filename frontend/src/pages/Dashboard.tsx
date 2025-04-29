import React, { useState, useEffect } from 'react';
import SyncTable from '../components/SyncTable';
import { syncService } from '../services/api';
import '../App.css';

// Interfaces
interface SyncResult {
  invoice_number: number;
  status: string;
  synced: boolean;
  action: string;
}

const Dashboard: React.FC = () => {
  const [syncResults, setSyncResults] = useState<SyncResult[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [lastSyncTime, setLastSyncTime] = useState<string>('Never');
  const [error, setError] = useState<string | null>(null);
  const [apiStatus, setApiStatus] = useState<boolean>(false);

  // Check API status on load
  useEffect(() => {
    const checkApiStatus = async () => {
      try {
        await syncService.checkStatus();
        setApiStatus(true);
      } catch (err) {
        setApiStatus(false);
        console.error('API status check failed:', err);
      }
    };

    checkApiStatus();
  }, []);

  // For demo purposes, loading sample data
  useEffect(() => {
    // This would normally come from an API call
    // Using the sample data for now
    const sampleData: SyncResult[] = [
      { invoice_number: 11338, status: "inactive", synced: true, action: "No Action" },
      { invoice_number: 11802, status: "active", synced: true, action: "No Action" },
      { invoice_number: 12044, status: "active", synced: true, action: "No Action" },
      { invoice_number: 12082, status: "completed", synced: true, action: "Created Invoice in QBO" },
      { invoice_number: 12085, status: "inactive", synced: true, action: "No Action" },
      { invoice_number: 12086, status: "active", synced: true, action: "No Action" }
    ];
    
    setSyncResults(sampleData);
    setLastSyncTime(new Date().toLocaleString());
  }, []);

  const handleManualSync = async () => {
    setLoading(true);
    setError(null);
    
    try {
      // In production, this would use the actual API
      if (apiStatus) {
        // Uncomment for production use
        // const response = await syncService.initiateSync();
        // setSyncResults(response);
      }
      
      // For demo:
      await new Promise(resolve => setTimeout(resolve, 2000));
      
      // Simulate new data
      const updatedData = [
        ...syncResults,
        { invoice_number: 12105, status: "completed", synced: true, action: "Created Invoice in QBO" }
      ];
      
      setSyncResults(updatedData);
      setLastSyncTime(new Date().toLocaleString());
    } catch (err) {
      setError('Failed to sync: ' + (err instanceof Error ? err.message : String(err)));
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = () => {
    // In a real app, this would clear authentication state
    window.location.href = '/';
  };

  return (
    <div className="container">
      <header>
        <div className="header-content">
          <h1>4D EMR to QuickBooks Online Sync Dashboard</h1>
          <button onClick={handleLogout} className="logout-btn">
            <i className="fas fa-sign-out-alt"></i> Logout
          </button>
        </div>
        <p>Last Successful Sync: {lastSyncTime}</p>
        <p className={apiStatus ? 'success' : 'error'}>
          API Status: {apiStatus ? 'Connected' : 'Disconnected'}
        </p>
      </header>
      
      <div className="controls">
        <button 
          onClick={handleManualSync} 
          disabled={loading}
        >
          {loading ? 'Syncing...' : 'Manual Sync'}
        </button>
      </div>
      
      {error && (
        <div className="error-message">{error}</div>
      )}
      
      <SyncTable results={syncResults} />
      
      <footer>
        <p>4D EMR to QuickBooks Online Integration - v0.1.0</p>
        <p>Sync interval: Every 15 minutes</p>
      </footer>
    </div>
  );
};

export default Dashboard; 