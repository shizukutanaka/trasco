/**
 * Admin Dashboard Component
 * System monitoring, statistics, and administrative operations
 */

import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import axios from 'axios';
import '../styles/AdminDashboard.css';

const AdminDashboard = ({ isOpen, onClose }) => {
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState('overview');
  const [loading, setLoading] = useState(false);
  const [stats, setStats] = useState(null);
  const [health, setHealth] = useState(null);
  const [trends, setTrends] = useState(null);
  const [topSenders, setTopSenders] = useState(null);
  const [topDomains, setTopDomains] = useState(null);
  const [summary, setSummary] = useState(null);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  // Load admin dashboard data
  const loadDashboardData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [statsRes, healthRes, trendsRes, sendersRes, domainsRes, summaryRes] =
        await Promise.all([
          axios.get('/admin/stats'),
          axios.get('/admin/health'),
          axios.get('/admin/trends?days=30'),
          axios.get('/admin/top-senders?limit=5'),
          axios.get('/admin/top-domains?limit=5'),
          axios.get('/admin/dashboard-summary'),
        ]);

      setStats(statsRes.data);
      setHealth(healthRes.data);
      setTrends(trendsRes.data);
      setTopSenders(sendersRes.data);
      setTopDomains(domainsRes.data);
      setSummary(summaryRes.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load dashboard data');
      console.error('Dashboard load error:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      loadDashboardData();
    }
  }, [isOpen]);

  const handleRebuildIndices = async () => {
    try {
      setLoading(true);
      await axios.post('/admin/rebuild-indices');
      setSuccess('Database indices rebuilt successfully');
      setTimeout(() => setSuccess(null), 3000);
      await loadDashboardData();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to rebuild indices');
    } finally {
      setLoading(false);
    }
  };

  const handleCleanupData = async (daysOld = 90) => {
    if (!window.confirm(`Delete data older than ${daysOld} days? This action cannot be undone.`)) {
      return;
    }
    try {
      setLoading(true);
      const response = await axios.post(`/admin/cleanup-old-data?days_old=${daysOld}`);
      setSuccess(
        `Cleanup completed: ${response.data.deleted_emails} emails, ${response.data.deleted_reports} reports deleted`
      );
      setTimeout(() => setSuccess(null), 3000);
      await loadDashboardData();
    } catch (err) {
      setError(err.response?.data?.detail || 'Cleanup failed');
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  const getHealthColor = (status) => {
    if (status === 'healthy' || status === 'ok') return '#10b981';
    if (status === 'degraded') return '#f59e0b';
    return '#ef4444';
  };

  const getRiskColor = (level) => {
    if (level === 'critical') return '#dc2626';
    if (level === 'high') return '#f97316';
    if (level === 'medium') return '#eab308';
    return '#22c55e';
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="admin-dashboard" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="admin-header">
          <h1>{t('admin.title')}</h1>
          <button className="close-btn" onClick={onClose}>×</button>
        </div>

        {/* Messages */}
        {error && <div className="alert alert-error">{error}</div>}
        {success && <div className="alert alert-success">{success}</div>}

        {/* Tab Navigation */}
        <div className="admin-tabs">
          <button
            className={`tab-btn ${activeTab === 'overview' ? 'active' : ''}`}
            onClick={() => setActiveTab('overview')}
          >
            {t('admin.dashboard')}
          </button>
          <button
            className={`tab-btn ${activeTab === 'health' ? 'active' : ''}`}
            onClick={() => setActiveTab('health')}
          >
            System Health
          </button>
          <button
            className={`tab-btn ${activeTab === 'threats' ? 'active' : ''}`}
            onClick={() => setActiveTab('threats')}
          >
            Top Threats
          </button>
          <button
            className={`tab-btn ${activeTab === 'maintenance' ? 'active' : ''}`}
            onClick={() => setActiveTab('maintenance')}
          >
            Maintenance
          </button>
        </div>

        {/* Content */}
        <div className="admin-content">
          {loading && <div className="loading-spinner">Loading...</div>}

          {/* Overview Tab */}
          {activeTab === 'overview' && summary && (
            <div className="overview-section">
              {/* Summary Cards */}
              <div className="stats-grid">
                <div className="stat-card">
                  <h3>{t('admin.users_count')}</h3>
                  <div className="stat-value">{summary.summary.total_users}</div>
                  <p className="stat-label">
                    {t('admin.active_users')}: {summary.summary.total_users}
                  </p>
                </div>

                <div className="stat-card">
                  <h3>{t('emails.found')}</h3>
                  <div className="stat-value">{summary.summary.total_emails}</div>
                  <p className="stat-label">
                    High Risk: {summary.summary.high_risk_emails}
                  </p>
                </div>

                <div className="stat-card">
                  <h3>{t('report.send')}</h3>
                  <div className="stat-value">{summary.summary.reports_pending}</div>
                  <p className="stat-label">Pending Reports</p>
                </div>

                <div className="stat-card">
                  <h3>Avg Risk Score</h3>
                  <div className="stat-value">{summary.summary.average_risk_score}</div>
                  <p className="stat-label">/100</p>
                </div>
              </div>

              {/* Email Status Distribution */}
              <div className="section-group">
                <h2>Email Statistics</h2>
                <div className="stats-row">
                  <div className="stat-column">
                    <h4>{t('status.pending')}</h4>
                    <p>{summary.statistics.emails_by_status.pending}</p>
                  </div>
                  <div className="stat-column">
                    <h4>{t('status.analyzed')}</h4>
                    <p>{summary.statistics.emails_by_status.analyzed}</p>
                  </div>
                  <div className="stat-column">
                    <h4>{t('status.reported')}</h4>
                    <p>{summary.statistics.emails_by_status.reported}</p>
                  </div>
                  <div className="stat-column">
                    <h4>{t('status.false_positive')}</h4>
                    <p>{summary.statistics.emails_by_status.false_positive}</p>
                  </div>
                </div>
              </div>

              {/* Risk Level Distribution */}
              <div className="section-group">
                <h2>{t('risk.critical')}</h2>
                <div className="risk-distribution">
                  <div className="risk-bar">
                    <div
                      className="risk-segment"
                      style={{
                        width: `${
                          (summary.statistics.emails_by_risk_level.critical /
                            summary.summary.total_emails) *
                          100
                        }%`,
                        backgroundColor: getRiskColor('critical'),
                      }}
                    >
                      <span className="risk-label">
                        {t('risk.critical')}: {summary.statistics.emails_by_risk_level.critical}
                      </span>
                    </div>
                    <div
                      className="risk-segment"
                      style={{
                        width: `${
                          (summary.statistics.emails_by_risk_level.high /
                            summary.summary.total_emails) *
                          100
                        }%`,
                        backgroundColor: getRiskColor('high'),
                      }}
                    >
                      <span className="risk-label">
                        {t('risk.high')}: {summary.statistics.emails_by_risk_level.high}
                      </span>
                    </div>
                    <div
                      className="risk-segment"
                      style={{
                        width: `${
                          (summary.statistics.emails_by_risk_level.medium /
                            summary.summary.total_emails) *
                          100
                        }%`,
                        backgroundColor: getRiskColor('medium'),
                      }}
                    >
                      <span className="risk-label">
                        {t('risk.medium')}: {summary.statistics.emails_by_risk_level.medium}
                      </span>
                    </div>
                    <div
                      className="risk-segment"
                      style={{
                        width: `${
                          (summary.statistics.emails_by_risk_level.low /
                            summary.summary.total_emails) *
                          100
                        }%`,
                        backgroundColor: getRiskColor('low'),
                      }}
                    >
                      <span className="risk-label">
                        {t('risk.low')}: {summary.statistics.emails_by_risk_level.low}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Health Tab */}
          {activeTab === 'health' && health && (
            <div className="health-section">
              <div className="health-status">
                <h2>System Status</h2>
                <div className="status-indicator">
                  <div
                    className="status-dot"
                    style={{ backgroundColor: getHealthColor(health.status) }}
                  ></div>
                  <span className="status-text">{health.status.toUpperCase()}</span>
                </div>
              </div>

              <div className="health-checks">
                {/* Database Health */}
                <div className="health-check-item">
                  <h3>Database</h3>
                  <div className="check-result">
                    <div
                      className="check-indicator"
                      style={{
                        backgroundColor: getHealthColor(health.checks.database?.status),
                      }}
                    ></div>
                    <span>{health.checks.database?.status}</span>
                  </div>
                  {health.checks.database?.error && (
                    <p className="error-text">{health.checks.database.error}</p>
                  )}
                </div>

                {/* Tables Health */}
                <div className="health-check-item">
                  <h3>Tables</h3>
                  <div className="check-result">
                    <div
                      className="check-indicator"
                      style={{
                        backgroundColor: getHealthColor(health.checks.tables?.status),
                      }}
                    ></div>
                    <span>{health.checks.tables?.status}</span>
                  </div>
                  {health.checks.tables?.error && (
                    <p className="error-text">{health.checks.tables.error}</p>
                  )}
                </div>
              </div>

              <p className="timestamp">
                Last check: {new Date(health.timestamp).toLocaleString()}
              </p>
            </div>
          )}

          {/* Threats Tab */}
          {activeTab === 'threats' && (
            <div className="threats-section">
              {/* Top Senders */}
              {topSenders && (
                <div className="threat-group">
                  <h2>Top Email Senders</h2>
                  <div className="threat-table">
                    <table>
                      <thead>
                        <tr>
                          <th>Sender</th>
                          <th>Count</th>
                          <th>Avg Risk Score</th>
                        </tr>
                      </thead>
                      <tbody>
                        {topSenders.top_senders.map((sender, idx) => (
                          <tr key={idx}>
                            <td className="sender-cell">{sender.sender}</td>
                            <td>{sender.count}</td>
                            <td>
                              <span
                                className="risk-badge"
                                style={{
                                  backgroundColor: getRiskColor(
                                    sender.average_risk_score >= 80
                                      ? 'critical'
                                      : sender.average_risk_score >= 60
                                      ? 'high'
                                      : sender.average_risk_score >= 40
                                      ? 'medium'
                                      : 'low'
                                  ),
                                }}
                              >
                                {sender.average_risk_score}
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* Top Domains */}
              {topDomains && (
                <div className="threat-group">
                  <h2>Top Domains</h2>
                  <div className="threat-table">
                    <table>
                      <thead>
                        <tr>
                          <th>Domain</th>
                          <th>Count</th>
                          <th>Avg Score</th>
                          <th>Max Score</th>
                        </tr>
                      </thead>
                      <tbody>
                        {topDomains.top_domains.map((domain, idx) => (
                          <tr key={idx}>
                            <td className="domain-cell">{domain.domain}</td>
                            <td>{domain.count}</td>
                            <td>
                              <span
                                className="risk-badge"
                                style={{
                                  backgroundColor: getRiskColor(
                                    domain.average_risk_score >= 80
                                      ? 'critical'
                                      : domain.average_risk_score >= 60
                                      ? 'high'
                                      : domain.average_risk_score >= 40
                                      ? 'medium'
                                      : 'low'
                                  ),
                                }}
                              >
                                {domain.average_risk_score}
                              </span>
                            </td>
                            <td>
                              <span
                                className="risk-badge"
                                style={{
                                  backgroundColor: getRiskColor(
                                    domain.max_risk_score >= 80
                                      ? 'critical'
                                      : domain.max_risk_score >= 60
                                      ? 'high'
                                      : domain.max_risk_score >= 40
                                      ? 'medium'
                                      : 'low'
                                  ),
                                }}
                              >
                                {domain.max_risk_score}
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Maintenance Tab */}
          {activeTab === 'maintenance' && (
            <div className="maintenance-section">
              <div className="maintenance-actions">
                <h2>Database Maintenance</h2>

                <div className="action-card">
                  <h3>Rebuild Database Indices</h3>
                  <p>Optimize database performance by rebuilding indices.</p>
                  <button
                    className="btn btn-primary"
                    onClick={handleRebuildIndices}
                    disabled={loading}
                  >
                    {loading ? 'Processing...' : 'Rebuild Indices'}
                  </button>
                </div>

                <div className="action-card">
                  <h3>Clean Up Old Data</h3>
                  <p>Permanently remove data older than specified days.</p>
                  <div className="action-buttons">
                    <button
                      className="btn btn-warning"
                      onClick={() => handleCleanupData(30)}
                      disabled={loading}
                    >
                      Delete 30+ days
                    </button>
                    <button
                      className="btn btn-warning"
                      onClick={() => handleCleanupData(90)}
                      disabled={loading}
                    >
                      Delete 90+ days
                    </button>
                    <button
                      className="btn btn-danger"
                      onClick={() => handleCleanupData(180)}
                      disabled={loading}
                    >
                      Delete 180+ days
                    </button>
                  </div>
                </div>

                <div className="info-box">
                  <h4>⚠️ Important</h4>
                  <p>
                    Cleanup operations permanently delete data. These actions cannot be
                    undone. Ensure you have backups before proceeding.
                  </p>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Refresh Button */}
        <div className="admin-footer">
          <button
            className="btn btn-secondary"
            onClick={loadDashboardData}
            disabled={loading}
          >
            {loading ? 'Refreshing...' : 'Refresh Data'}
          </button>
          <button className="btn btn-secondary" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
};

export default AdminDashboard;
