import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import axios from 'axios';

const Webhooks = ({ isOpen, onClose, token }) => {
  const { t } = useTranslation();
  const [webhooks, setWebhooks] = useState([]);
  const [loading, setLoading] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [selectedWebhook, setSelectedWebhook] = useState(null);
  const [formData, setFormData] = useState({
    name: '',
    url: '',
    events: [],
    enabled: true,
    secret: '',
    retry_count: 3,
    timeout_seconds: 10,
  });
  const [showHistory, setShowHistory] = useState(false);
  const [historyWebhookId, setHistoryWebhookId] = useState(null);
  const [history, setHistory] = useState([]);
  const [stats, setStats] = useState(null);
  const [testing, setTesting] = useState(false);

  const API_BASE = process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000';

  const webhookEvents = [
    'rule_triggered',
    'high_risk_detected',
    'email_flagged',
    'email_reported',
    'system_alert',
  ];

  // Load webhooks on mount
  useEffect(() => {
    if (isOpen && token) {
      loadWebhooks();
      loadStats();
    }
  }, [isOpen, token]);

  const loadWebhooks = async () => {
    setLoading(true);
    try {
      const response = await axios.get(`${API_BASE}/webhooks/`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setWebhooks(response.data);
    } catch (error) {
      console.error('Error loading webhooks:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadStats = async () => {
    try {
      const response = await axios.get(`${API_BASE}/webhooks/stats/summary`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setStats(response.data);
    } catch (error) {
      console.error('Error loading stats:', error);
    }
  };

  const loadHistory = async (webhookId) => {
    try {
      const response = await axios.get(
        `${API_BASE}/webhooks/${webhookId}/events`,
        {
          headers: { Authorization: `Bearer ${token}` },
        }
      );
      setHistory(response.data.events);
      setHistoryWebhookId(webhookId);
      setShowHistory(true);
    } catch (error) {
      console.error('Error loading history:', error);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      if (selectedWebhook) {
        await axios.put(
          `${API_BASE}/webhooks/${selectedWebhook.id}`,
          formData,
          {
            headers: { Authorization: `Bearer ${token}` },
          }
        );
      } else {
        await axios.post(`${API_BASE}/webhooks/`, formData, {
          headers: { Authorization: `Bearer ${token}` },
        });
      }
      resetForm();
      loadWebhooks();
      loadStats();
    } catch (error) {
      console.error('Error saving webhook:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (webhookId) => {
    if (!window.confirm(t('webhooks.confirmDelete'))) return;

    try {
      await axios.delete(`${API_BASE}/webhooks/${webhookId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      loadWebhooks();
      loadStats();
    } catch (error) {
      console.error('Error deleting webhook:', error);
    }
  };

  const handleTest = async (webhookId) => {
    setTesting(true);
    try {
      await axios.post(
        `${API_BASE}/webhooks/${webhookId}/test`,
        {},
        {
          headers: { Authorization: `Bearer ${token}` },
        }
      );
      alert(t('webhooks.testSent'));
      loadWebhooks();
    } catch (error) {
      console.error('Error testing webhook:', error);
      alert(t('webhooks.testFailed'));
    } finally {
      setTesting(false);
    }
  };

  const handleEdit = (webhook) => {
    setSelectedWebhook(webhook);
    setFormData({
      name: webhook.name,
      url: webhook.url,
      events: webhook.events,
      enabled: webhook.enabled,
      secret: webhook.secret || '',
      retry_count: webhook.retry_count,
      timeout_seconds: webhook.timeout_seconds,
    });
    setShowForm(true);
  };

  const resetForm = () => {
    setSelectedWebhook(null);
    setFormData({
      name: '',
      url: '',
      events: [],
      enabled: true,
      secret: '',
      retry_count: 3,
      timeout_seconds: 10,
    });
    setShowForm(false);
  };

  const handleEventToggle = (event) => {
    setFormData((prev) => ({
      ...prev,
      events: prev.events.includes(event)
        ? prev.events.filter((e) => e !== event)
        : [...prev.events, event],
    }));
  };

  if (!isOpen) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>🔔 {t('webhooks.title')}</h2>
          <button className="close-button" onClick={onClose}>
            ✕
          </button>
        </div>

        <div className="modal-body">
          {/* Stats Section */}
          {stats && (
            <div className="webhook-stats">
              <div className="stat-card">
                <div className="stat-value">{stats.total_webhooks}</div>
                <div className="stat-label">{t('webhooks.totalWebhooks')}</div>
              </div>
              <div className="stat-card">
                <div className="stat-value">{stats.enabled_webhooks}</div>
                <div className="stat-label">{t('webhooks.enabledWebhooks')}</div>
              </div>
              <div className="stat-card">
                <div className="stat-value">
                  {stats.success_rate.toFixed(1)}%
                </div>
                <div className="stat-label">{t('webhooks.successRate')}</div>
              </div>
              <div className="stat-card">
                <div className="stat-value">
                  {stats.total_successful_deliveries}
                </div>
                <div className="stat-label">
                  {t('webhooks.successfulDeliveries')}
                </div>
              </div>
            </div>
          )}

          {/* Form Section */}
          {showForm && (
            <div className="webhook-form-section">
              <h3>{selectedWebhook ? t('webhooks.editWebhook') : t('webhooks.newWebhook')}</h3>
              <form onSubmit={handleSubmit} className="webhook-form">
                <div className="form-group">
                  <label>{t('webhooks.name')}</label>
                  <input
                    type="text"
                    required
                    minLength={1}
                    maxLength={100}
                    value={formData.name}
                    onChange={(e) =>
                      setFormData({ ...formData, name: e.target.value })
                    }
                    placeholder={t('webhooks.namePlaceholder')}
                  />
                </div>

                <div className="form-group">
                  <label>{t('webhooks.url')}</label>
                  <input
                    type="url"
                    required
                    value={formData.url}
                    onChange={(e) =>
                      setFormData({ ...formData, url: e.target.value })
                    }
                    placeholder={t('webhooks.urlPlaceholder')}
                  />
                </div>

                <div className="form-group">
                  <label>{t('webhooks.events')}</label>
                  <div className="event-checkboxes">
                    {webhookEvents.map((event) => (
                      <label key={event} className="checkbox-label">
                        <input
                          type="checkbox"
                          checked={formData.events.includes(event)}
                          onChange={() => handleEventToggle(event)}
                        />
                        {t(`webhooks.event.${event}`)}
                      </label>
                    ))}
                  </div>
                </div>

                <div className="form-row">
                  <div className="form-group">
                    <label>{t('webhooks.retryCount')}</label>
                    <input
                      type="number"
                      min={0}
                      max={10}
                      value={formData.retry_count}
                      onChange={(e) =>
                        setFormData({
                          ...formData,
                          retry_count: parseInt(e.target.value),
                        })
                      }
                    />
                  </div>

                  <div className="form-group">
                    <label>{t('webhooks.timeoutSeconds')}</label>
                    <input
                      type="number"
                      min={5}
                      max={60}
                      value={formData.timeout_seconds}
                      onChange={(e) =>
                        setFormData({
                          ...formData,
                          timeout_seconds: parseInt(e.target.value),
                        })
                      }
                    />
                  </div>
                </div>

                <div className="form-group">
                  <label>{t('webhooks.secret')}</label>
                  <input
                    type="password"
                    value={formData.secret}
                    onChange={(e) =>
                      setFormData({ ...formData, secret: e.target.value })
                    }
                    placeholder={t('webhooks.secretPlaceholder')}
                  />
                  <small>{t('webhooks.secretHint')}</small>
                </div>

                <div className="form-group checkbox-group">
                  <label className="checkbox-label">
                    <input
                      type="checkbox"
                      checked={formData.enabled}
                      onChange={(e) =>
                        setFormData({ ...formData, enabled: e.target.checked })
                      }
                    />
                    {t('webhooks.enabled')}
                  </label>
                </div>

                <div className="form-actions">
                  <button
                    type="submit"
                    className="btn btn-primary"
                    disabled={loading}
                  >
                    {selectedWebhook ? t('webhooks.update') : t('webhooks.create')}
                  </button>
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={resetForm}
                    disabled={loading}
                  >
                    {t('webhooks.cancel')}
                  </button>
                </div>
              </form>
            </div>
          )}

          {/* Webhooks List */}
          <div className="webhooks-list-section">
            <div className="section-header">
              <h3>{t('webhooks.webhooks')}</h3>
              <button
                className="btn btn-primary btn-sm"
                onClick={() => setShowForm(!showForm)}
              >
                {showForm ? t('webhooks.hideForm') : t('webhooks.addWebhook')}
              </button>
            </div>

            {loading ? (
              <div className="loading">{t('webhooks.loading')}</div>
            ) : webhooks.length === 0 ? (
              <div className="empty-state">
                <p>{t('webhooks.noWebhooks')}</p>
              </div>
            ) : (
              <div className="webhooks-grid">
                {webhooks.map((webhook) => (
                  <div key={webhook.id} className="webhook-card">
                    <div className="webhook-header">
                      <h4>{webhook.name}</h4>
                      <div className="webhook-status">
                        {webhook.enabled ? (
                          <span className="status-badge active">
                            {t('webhooks.active')}
                          </span>
                        ) : (
                          <span className="status-badge inactive">
                            {t('webhooks.inactive')}
                          </span>
                        )}
                      </div>
                    </div>

                    <div className="webhook-info">
                      <p className="webhook-url">
                        <strong>{t('webhooks.url')}:</strong> {webhook.url}
                      </p>
                      <p>
                        <strong>{t('webhooks.events')}:</strong>{' '}
                        {webhook.events.join(', ')}
                      </p>
                      <p>
                        <strong>{t('webhooks.delivery')}:</strong>{' '}
                        {webhook.successful_deliveries} {t('webhooks.successful')} /{' '}
                        {webhook.failed_deliveries} {t('webhooks.failed')}
                      </p>
                      {webhook.last_delivery && (
                        <p>
                          <strong>{t('webhooks.lastDelivery')}:</strong>{' '}
                          {new Date(webhook.last_delivery).toLocaleString()}
                        </p>
                      )}
                    </div>

                    <div className="webhook-actions">
                      <button
                        className="btn btn-sm btn-primary"
                        onClick={() => handleEdit(webhook)}
                      >
                        {t('webhooks.edit')}
                      </button>
                      <button
                        className="btn btn-sm btn-warning"
                        onClick={() => handleTest(webhook.id)}
                        disabled={testing}
                      >
                        {t('webhooks.test')}
                      </button>
                      <button
                        className="btn btn-sm btn-info"
                        onClick={() => loadHistory(webhook.id)}
                      >
                        {t('webhooks.history')}
                      </button>
                      <button
                        className="btn btn-sm btn-danger"
                        onClick={() => handleDelete(webhook.id)}
                      >
                        {t('webhooks.delete')}
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* History Modal */}
          {showHistory && (
            <div className="history-modal">
              <div className="history-header">
                <h3>{t('webhooks.deliveryHistory')}</h3>
                <button
                  className="close-button"
                  onClick={() => setShowHistory(false)}
                >
                  ✕
                </button>
              </div>
              <div className="history-content">
                {history.length === 0 ? (
                  <p>{t('webhooks.noHistory')}</p>
                ) : (
                  <table className="history-table">
                    <thead>
                      <tr>
                        <th>{t('webhooks.eventType')}</th>
                        <th>{t('webhooks.status')}</th>
                        <th>{t('webhooks.statusCode')}</th>
                        <th>{t('webhooks.retries')}</th>
                        <th>{t('webhooks.timestamp')}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {history.map((event) => (
                        <tr key={event.id}>
                          <td>{event.event_type}</td>
                          <td>
                            <span
                              className={`status-badge ${
                                event.success ? 'active' : 'inactive'
                              }`}
                            >
                              {event.success
                                ? t('webhooks.success')
                                : t('webhooks.failed')}
                            </span>
                          </td>
                          <td>{event.status_code || 'N/A'}</td>
                          <td>{event.retry_count}</td>
                          <td>
                            {new Date(event.created_at).toLocaleString()}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default Webhooks;
