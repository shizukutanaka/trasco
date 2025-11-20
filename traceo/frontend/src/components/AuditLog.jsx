import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import axios from 'axios';

const AuditLog = ({ isOpen, onClose, token }) => {
  const { t } = useTranslation();
  const [logs, setLogs] = useState([]);
  const [stats, setStats] = useState(null);
  const [timeline, setTimeline] = useState(null);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState('logs');
  const [searchQuery, setSearchQuery] = useState('');
  const [filterAction, setFilterAction] = useState('');
  const [filterResource, setFilterResource] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [searchResults, setSearchResults] = useState(null);
  const [days, setDays] = useState(30);

  const API_BASE = process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000';

  const auditActions = [
    'login',
    'logout',
    'password_change',
    'email_verified',
    'profile_update',
    'preferences_update',
    'email_viewed',
    'email_deleted',
    'email_reported',
    'rule_created',
    'rule_updated',
    'rule_deleted',
    'webhook_created',
    'webhook_updated',
    'webhook_deleted',
    'admin_stats_viewed',
    'data_exported',
  ];

  const resourceTypes = [
    'email',
    'rule',
    'webhook',
    'profile',
    'user',
    'audit_logs',
    'system',
  ];

  // Load data on mount
  useEffect(() => {
    if (isOpen && token) {
      loadLogs();
      loadStats();
      loadTimeline();
    }
  }, [isOpen, token, days]);

  const loadLogs = async () => {
    setLoading(true);
    try {
      let url = `${API_BASE}/audit/logs?days=${days}`;
      if (filterAction) url += `&action=${filterAction}`;
      if (filterResource) url += `&resource_type=${filterResource}`;
      if (filterStatus) url += `&status=${filterStatus}`;

      const response = await axios.get(url, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setLogs(response.data);
    } catch (error) {
      console.error('Error loading audit logs:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadStats = async () => {
    try {
      const response = await axios.get(`${API_BASE}/audit/logs/stats?days=${days}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setStats(response.data);
    } catch (error) {
      console.error('Error loading stats:', error);
    }
  };

  const loadTimeline = async () => {
    try {
      const response = await axios.get(
        `${API_BASE}/audit/logs/timeline?days=${days}`,
        {
          headers: { Authorization: `Bearer ${token}` },
        }
      );
      setTimeline(response.data);
    } catch (error) {
      console.error('Error loading timeline:', error);
    }
  };

  const handleSearch = async () => {
    if (!searchQuery.trim()) return;

    setLoading(true);
    try {
      const response = await axios.get(
        `${API_BASE}/audit/logs/search?query=${encodeURIComponent(searchQuery)}`,
        {
          headers: { Authorization: `Bearer ${token}` },
        }
      );
      setSearchResults(response.data);
    } catch (error) {
      console.error('Error searching logs:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleExport = async (format) => {
    try {
      const response = await axios.get(
        `${API_BASE}/audit/logs/export?format=${format}&days=${days}`,
        {
          headers: { Authorization: `Bearer ${token}` },
        }
      );

      if (format === 'json') {
        const dataStr = JSON.stringify(response.data, null, 2);
        downloadFile(dataStr, `audit-logs-${new Date().toISOString().split('T')[0]}.json`);
      } else if (format === 'csv') {
        downloadFile(response.data.data, `audit-logs-${new Date().toISOString().split('T')[0]}.csv`);
      }
    } catch (error) {
      console.error('Error exporting logs:', error);
    }
  };

  const downloadFile = (content, filename) => {
    const element = document.createElement('a');
    element.setAttribute('href', 'data:text/plain;charset=utf-8,' + encodeURIComponent(content));
    element.setAttribute('download', filename);
    element.style.display = 'none';
    document.body.appendChild(element);
    element.click();
    document.body.removeChild(element);
  };

  const getActionColor = (action) => {
    if (action.includes('login') || action.includes('create')) return '#28a745';
    if (action.includes('delete')) return '#dc3545';
    if (action.includes('update')) return '#ffc107';
    if (action.includes('error')) return '#dc3545';
    return '#007bff';
  };

  const getStatusBadgeClass = (status) => {
    switch (status) {
      case 'success':
        return 'badge-success';
      case 'error':
        return 'badge-error';
      case 'warning':
        return 'badge-warning';
      default:
        return 'badge-default';
    }
  };

  if (!isOpen) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content audit-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>📋 {t('audit.title')}</h2>
          <button className="close-button" onClick={onClose}>
            ✕
          </button>
        </div>

        <div className="modal-body">
          {/* Tab Navigation */}
          <div className="audit-tabs">
            <button
              className={`tab-button ${activeTab === 'logs' ? 'active' : ''}`}
              onClick={() => setActiveTab('logs')}
            >
              {t('audit.recentActivity')}
            </button>
            <button
              className={`tab-button ${activeTab === 'stats' ? 'active' : ''}`}
              onClick={() => setActiveTab('stats')}
            >
              {t('audit.statistics')}
            </button>
            <button
              className={`tab-button ${activeTab === 'timeline' ? 'active' : ''}`}
              onClick={() => setActiveTab('timeline')}
            >
              {t('audit.timeline')}
            </button>
            <button
              className={`tab-button ${activeTab === 'search' ? 'active' : ''}`}
              onClick={() => setActiveTab('search')}
            >
              {t('audit.search')}
            </button>
          </div>

          {/* Period Selector */}
          <div className="audit-controls">
            <label>{t('audit.period')}</label>
            <select value={days} onChange={(e) => setDays(parseInt(e.target.value))}>
              <option value={7}>{t('audit.last7Days')}</option>
              <option value={30}>{t('audit.last30Days')}</option>
              <option value={90}>{t('audit.last90Days')}</option>
              <option value={180}>{t('audit.last180Days')}</option>
            </select>
            <button className="btn btn-primary btn-sm" onClick={() => handleExport('json')}>
              {t('audit.exportJson')}
            </button>
            <button className="btn btn-primary btn-sm" onClick={() => handleExport('csv')}>
              {t('audit.exportCsv')}
            </button>
          </div>

          {/* Logs Tab */}
          {activeTab === 'logs' && (
            <div className="audit-section">
              <div className="filter-controls">
                <select
                  value={filterAction}
                  onChange={(e) => setFilterAction(e.target.value)}
                  placeholder="Filter by action"
                >
                  <option value="">{t('audit.allActions')}</option>
                  {auditActions.map((action) => (
                    <option key={action} value={action}>
                      {t(`audit.action.${action}`) || action}
                    </option>
                  ))}
                </select>

                <select
                  value={filterResource}
                  onChange={(e) => setFilterResource(e.target.value)}
                >
                  <option value="">{t('audit.allResources')}</option>
                  {resourceTypes.map((type) => (
                    <option key={type} value={type}>
                      {type}
                    </option>
                  ))}
                </select>

                <select
                  value={filterStatus}
                  onChange={(e) => setFilterStatus(e.target.value)}
                >
                  <option value="">{t('audit.allStatuses')}</option>
                  <option value="success">{t('audit.success')}</option>
                  <option value="error">{t('audit.error')}</option>
                  <option value="warning">{t('audit.warning')}</option>
                </select>

                <button className="btn btn-primary btn-sm" onClick={loadLogs}>
                  {t('audit.applyFilters')}
                </button>
              </div>

              {loading ? (
                <div className="loading">{t('audit.loading')}</div>
              ) : logs.length === 0 ? (
                <div className="empty-state">
                  <p>{t('audit.noLogs')}</p>
                </div>
              ) : (
                <div className="audit-logs-list">
                  {logs.map((log) => (
                    <div key={log.id} className="audit-log-entry">
                      <div className="log-header">
                        <span
                          className="action-badge"
                          style={{ backgroundColor: getActionColor(log.action) }}
                        >
                          {t(`audit.action.${log.action}`) || log.action}
                        </span>
                        <span className={`status-badge ${getStatusBadgeClass(log.status)}`}>
                          {t(`audit.${log.status}`) || log.status}
                        </span>
                        <span className="log-time">
                          {new Date(log.created_at).toLocaleString()}
                        </span>
                      </div>
                      <div className="log-description">
                        {log.description}
                      </div>
                      {log.resource_type && (
                        <div className="log-meta">
                          <span className="resource-type">{log.resource_type}</span>
                          {log.resource_id && (
                            <span className="resource-id">ID: {log.resource_id}</span>
                          )}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Statistics Tab */}
          {activeTab === 'stats' && stats && (
            <div className="audit-section">
              <div className="stats-grid">
                <div className="stat-card">
                  <div className="stat-label">{t('audit.totalEvents')}</div>
                  <div className="stat-value">{stats.total_events}</div>
                </div>
                <div className="stat-card">
                  <div className="stat-label">{t('audit.successful')}</div>
                  <div className="stat-value" style={{ color: '#28a745' }}>
                    {stats.successful}
                  </div>
                </div>
                <div className="stat-card">
                  <div className="stat-label">{t('audit.errors')}</div>
                  <div className="stat-value" style={{ color: '#dc3545' }}>
                    {stats.errors}
                  </div>
                </div>
                <div className="stat-card">
                  <div className="stat-label">{t('audit.warnings')}</div>
                  <div className="stat-value" style={{ color: '#ffc107' }}>
                    {stats.warnings}
                  </div>
                </div>
                <div className="stat-card">
                  <div className="stat-label">{t('audit.successRate')}</div>
                  <div className="stat-value">{stats.success_rate.toFixed(1)}%</div>
                </div>
              </div>

              {stats.top_actions && Object.keys(stats.top_actions).length > 0 && (
                <div className="stats-section">
                  <h3>{t('audit.topActions')}</h3>
                  <div className="action-breakdown">
                    {Object.entries(stats.top_actions).map(([action, count]) => (
                      <div key={action} className="action-item">
                        <span className="action-name">{t(`audit.action.${action}`) || action}</span>
                        <div className="action-bar">
                          <div
                            className="bar-fill"
                            style={{
                              width: `${(count / Math.max(...Object.values(stats.top_actions))) * 100}%`,
                              backgroundColor: getActionColor(action),
                            }}
                          />
                        </div>
                        <span className="action-count">{count}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {stats.resource_breakdown && Object.keys(stats.resource_breakdown).length > 0 && (
                <div className="stats-section">
                  <h3>{t('audit.resourceBreakdown')}</h3>
                  <div className="resource-breakdown">
                    {Object.entries(stats.resource_breakdown).map(([resource, count]) => (
                      <div key={resource} className="resource-item">
                        <span className="resource-label">{resource}</span>
                        <span className="resource-count">{count}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Timeline Tab */}
          {activeTab === 'timeline' && timeline && (
            <div className="audit-section">
              <div className="timeline">
                {Object.entries(timeline.timeline)
                  .sort(([dateA], [dateB]) => dateB.localeCompare(dateA))
                  .map(([date, events]) => (
                    <div key={date} className="timeline-group">
                      <div className="timeline-date">{new Date(date).toLocaleDateString()}</div>
                      <div className="timeline-events">
                        {events.map((event, idx) => (
                          <div key={idx} className="timeline-event">
                            <div className="event-dot" style={{ backgroundColor: getActionColor(event.action) }} />
                            <div className="event-content">
                              <div className="event-title">
                                {t(`audit.action.${event.action}`) || event.action}
                              </div>
                              <div className="event-description">{event.description}</div>
                              <div className="event-time">
                                {new Date(event.time).toLocaleTimeString()}
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
              </div>
            </div>
          )}

          {/* Search Tab */}
          {activeTab === 'search' && (
            <div className="audit-section">
              <div className="search-container">
                <input
                  type="text"
                  placeholder={t('audit.searchPlaceholder')}
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
                  className="search-input"
                />
                <button className="btn btn-primary" onClick={handleSearch}>
                  {t('audit.search')}
                </button>
              </div>

              {searchResults && (
                <div className="search-results">
                  <div className="results-info">
                    {t('audit.found')} {searchResults.total_results} {t('audit.results')}
                  </div>
                  {searchResults.total_results === 0 ? (
                    <div className="empty-state">
                      <p>{t('audit.noResults')}</p>
                    </div>
                  ) : (
                    <div className="audit-logs-list">
                      {searchResults.results.map((log) => (
                        <div key={log.id} className="audit-log-entry">
                          <div className="log-header">
                            <span
                              className="action-badge"
                              style={{ backgroundColor: getActionColor(log.action) }}
                            >
                              {t(`audit.action.${log.action}`) || log.action}
                            </span>
                            <span className={`status-badge ${getStatusBadgeClass(log.status)}`}>
                              {t(`audit.${log.status}`) || log.status}
                            </span>
                            <span className="log-time">
                              {new Date(log.created_at).toLocaleString()}
                            </span>
                          </div>
                          <div className="log-description">
                            {log.description}
                          </div>
                          {log.resource_type && (
                            <div className="log-meta">
                              <span className="resource-type">{log.resource_type}</span>
                              {log.resource_id && (
                                <span className="resource-id">ID: {log.resource_id}</span>
                              )}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default AuditLog;
