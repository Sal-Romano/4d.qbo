import React from 'react';

interface SyncResult {
  invoice_number: number;
  status: string;
  synced: boolean;
  action: string;
}

interface SyncTableProps {
  results: SyncResult[];
}

const SyncTable: React.FC<SyncTableProps> = ({ results }) => {
  // Return empty state if no results
  if (!results || results.length === 0) {
    return (
      <div className="empty-state">
        <p>No sync results available.</p>
      </div>
    );
  }

  return (
    <div className="sync-table">
      <h2>Sync Results</h2>
      <table>
        <thead>
          <tr>
            <th>Invoice #</th>
            <th>Status</th>
            <th>Synced</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody>
          {results.map((result) => (
            <tr key={result.invoice_number}>
              <td>{result.invoice_number}</td>
              <td>
                <span className={`status ${result.status}`}>
                  {result.status.charAt(0).toUpperCase() + result.status.slice(1)}
                </span>
              </td>
              <td>
                {result.synced ? (
                  <span className="success">✓</span>
                ) : (
                  <span className="error">✗</span>
                )}
              </td>
              <td>{result.action}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default SyncTable; 