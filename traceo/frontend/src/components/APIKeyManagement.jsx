import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import './APIKeyManagement.css';

const APIKeyManagement = ({ onClose }) => {
  const { t } = useTranslation();
  const [keys, setKeys] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showStatsModal, setShowStatsModal] = useState(false);
  const [showRotateModal, setShowRotateModal] = useState(false);
  const [showDisableModal, setShowDisableModal] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(false);

  const [formData, setFormData] = useState({
    name: '',
    description: '',
    tier: 'free',
    expires_in_days: null,
  });

  const [newKey, setNewKey] = useState(null);
  const [selectedKey, setSelectedKey] = useState(null);
  const [keyStats, setKeyStats] = useState(null);

  // Fetch API keys on mount
  useEffect(() => {
    fetchKeys();
  }, []);

  const fetchKeys = async () => {
    setLoading(true);
    try {
      const response = await fetch('/auth/api-keys', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
        },
      });

      if (!response.ok) throw new Error('Failed to fetch keys');

      const data = await response.json();
      setKeys(data);
      setError(null);
    } catch (err) {
      setError(t('apiKeyManagement.createFailed'));
      console.error('Error fetching keys:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateKey = async (e) => {
    e.preventDefault();
    setLoading(true);

    try {
      const response = await fetch('/auth/api-keys/create', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          name: formData.name,
          description: formData.description || null,
          tier: formData.tier,
          expires_in_days: formData.expires_in_days ? parseInt(formData.expires_in_days) : null,
          scopes: ['read', 'write'],
        }),
      });

      if (!response.ok) throw new Error('Failed to create key');

      const data = await response.json();
      setNewKey(data.plaintext_key);
      setFormData({ name: '', description: '', tier: 'free', expires_in_days: null });
      await fetchKeys();
    } catch (err) {
      setError(t('apiKeyManagement.createFailed'));
      console.error('Error creating key:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleRotateKey = async () => {
    if (!selectedKey) return;

    setLoading(true);
    try {
      const response = await fetch(`/auth/api-keys/${selectedKey.id}/rotate`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
        },
      });

      if (!response.ok) throw new Error('Failed to rotate key');

      const data = await response.json();
      setNewKey(data.plaintext_key);
      setShowRotateModal(false);
      await fetchKeys();
    } catch (err) {
      setError(t('apiKeyManagement.rotateFailed'));
    } finally {
      setLoading(false);
    }
  };

  const handleDisableKey = async () => {
    if (!selectedKey) return;

    setLoading(true);
    try {
      const response = await fetch(`/auth/api-keys/${selectedKey.id}/disable`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
        },
      });

      if (!response.ok) throw new Error('Failed to disable key');

      setShowDisableModal(false);
      await fetchKeys();
    } catch (err) {
      setError(t('apiKeyManagement.disableFailed'));
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteKey = async () => {
    if (!selectedKey) return;

    setLoading(true);
    try {
      const response = await fetch(`/auth/api-keys/${selectedKey.id}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
        },
      });

      if (!response.ok) throw new Error('Failed to delete key');

      setShowDeleteModal(false);
      await fetchKeys();
    } catch (err) {
      setError(t('apiKeyManagement.deleteFailed'));
    } finally {
      setLoading(false);
    }
  };

  const handleViewStats = async (key) => {
    setSelectedKey(key);
    setLoading(true);

    try {
      const response = await fetch(`/auth/api-keys/${key.id}/stats`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
        },
      });

      if (!response.ok) throw new Error('Failed to fetch stats');

      const data = await response.json();
      setKeyStats(data);
      setShowStatsModal(true);
    } catch (err) {
      setError(t('apiKeyManagement.createFailed'));
    } finally {
      setLoading(false);
    }
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    // Show toast notification
    alert(t('apiKeyManagement.copiedKey'));
  };

  const getTierInfo = (tier) => {
    const tierInfo = {
      free: t('apiKeyManagement.freeInfo'),
      pro: t('apiKeyManagement.proInfo'),
      enterprise: t('apiKeyManagement.enterpriseInfo'),
    };
    return tierInfo[tier] || '';
  };

  const formatDate = (dateString) => {
    if (!dateString) return t('apiKeyManagement.never');
    return new Date(dateString).toLocaleDateString();
  };

  return (
    <div className="api-key-container">
      <button className="btn-close" onClick={onClose}>×</button>

      <div className="api-key-card">
        <h2>{t('apiKeyManagement.title')}</h2>
        <p className="description">{t('apiKeyManagement.description')}</p>

        {/* Error Message */}
        {error && (
          <div className="alert alert-error">
            {error}
            <button onClick={() => setError(null)} style={{ marginLeft: '10px' }}>✕</button>
          </div>
        )}

        {/* Create Key Button */}
        <button
          className="btn btn-primary"
          onClick={() => setShowCreateModal(true)}
          disabled={loading}
        >
          {t('apiKeyManagement.createKey')}
        </button>

        {/* Keys Table */}
        {keys.length > 0 ? (
          <div className="keys-table-wrapper">
            <table className="keys-table">
              <thead>
                <tr>
                  <th>{t('apiKeyManagement.keyName')}</th>
                  <th>{t('apiKeyManagement.keyPrefix')}</th>
                  <th>{t('apiKeyManagement.keyTier')}</th>
                  <th>{t('apiKeyManagement.createdDate')}</th>
                  <th>{t('apiKeyManagement.lastUsed')}</th>
                  <th>{t('apiKeyManagement.status')}</th>
                  <th>{t('apiKeyManagement.actions')}</th>
                </tr>
              </thead>
              <tbody>
                {keys.map((key) => (
                  <tr key={key.id}>
                    <td>{key.name}</td>
                    <td className="key-prefix">{key.key_prefix}</td>
                    <td>
                      <span className={`tier-badge tier-${key.tier}`}>
                        {t(`apiKeyManagement.${key.tier}Tier`)}
                      </span>
                    </td>
                    <td>{formatDate(key.created_at)}</td>
                    <td>{formatDate(key.last_used)}</td>
                    <td>
                      <span className={`status-badge ${key.is_active ? 'active' : 'inactive'}`}>
                        {key.is_active ? t('apiKeyManagement.active') : t('apiKeyManagement.inactive')}
                      </span>
                    </td>
                    <td>
                      <div className="actions-buttons">
                        <button
                          className="btn-action btn-stats"
                          onClick={() => handleViewStats(key)}
                          title={t('apiKeyManagement.viewStats')}
                          disabled={loading}
                        >
                          📊
                        </button>
                        <button
                          className="btn-action btn-rotate"
                          onClick={() => {
                            setSelectedKey(key);
                            setShowRotateModal(true);
                          }}
                          title={t('apiKeyManagement.rotate')}
                          disabled={loading || !key.is_active}
                        >
                          🔄
                        </button>
                        <button
                          className="btn-action btn-disable"
                          onClick={() => {
                            setSelectedKey(key);
                            setShowDisableModal(true);
                          }}
                          title={t('apiKeyManagement.disable')}
                          disabled={loading || !key.is_active}
                        >
                          ⏸
                        </button>
                        <button
                          className="btn-action btn-delete"
                          onClick={() => {
                            setSelectedKey(key);
                            setShowDeleteModal(true);
                          }}
                          title={t('apiKeyManagement.delete')}
                          disabled={loading}
                        >
                          🗑
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="empty-state">
            <p>{t('apiKeyManagement.noKeys')}</p>
          </div>
        )}

        {/* Security Info */}
        <div className="security-section">
          <h3>{t('apiKeyManagement.security')}</h3>
          <p className="hint">{t('apiKeyManagement.securityInfo')}</p>
          <div className="best-practices">
            <strong>{t('apiKeyManagement.bestPractices')}:</strong>
            <ul>
              <li>{t('apiKeyManagement.bestPractice1')}</li>
              <li>{t('apiKeyManagement.bestPractice2')}</li>
              <li>{t('apiKeyManagement.bestPractice3')}</li>
              <li>{t('apiKeyManagement.bestPractice4')}</li>
              <li>{t('apiKeyManagement.bestPractice5')}</li>
            </ul>
          </div>
        </div>
      </div>

      {/* Create Key Modal */}
      {showCreateModal && (
        <div className="modal-overlay" onClick={() => setShowCreateModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <h3>{t('apiKeyManagement.createTitle')}</h3>
            <p>{t('apiKeyManagement.createDescription')}</p>

            {newKey ? (
              <div className="new-key-display">
                <div className="alert alert-success">
                  {t('apiKeyManagement.createSuccess')}
                </div>
                <p className="warning">{t('apiKeyManagement.keyCreatedDescription')}</p>
                <div className="key-display">
                  <input
                    type="text"
                    value={newKey}
                    readOnly
                    className="key-input"
                  />
                  <button
                    className="btn-copy"
                    onClick={() => copyToClipboard(newKey)}
                  >
                    📋
                  </button>
                </div>
                <div className="modal-actions">
                  <button
                    className="btn btn-primary"
                    onClick={() => {
                      setShowCreateModal(false);
                      setNewKey(null);
                    }}
                  >
                    {t('common.close')}
                  </button>
                </div>
              </div>
            ) : (
              <form onSubmit={handleCreateKey}>
                <div className="form-group">
                  <label>{t('apiKeyManagement.keyName')}</label>
                  <input
                    type="text"
                    placeholder={t('apiKeyManagement.keyNamePlaceholder')}
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    required
                    className="input"
                  />
                </div>

                <div className="form-group">
                  <label>{t('apiKeyManagement.keyDescription')}</label>
                  <input
                    type="text"
                    placeholder={t('apiKeyManagement.keyDescriptionPlaceholder')}
                    value={formData.description}
                    onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                    className="input"
                  />
                </div>

                <div className="form-group">
                  <label>{t('apiKeyManagement.keyTier')}</label>
                  <select
                    value={formData.tier}
                    onChange={(e) => setFormData({ ...formData, tier: e.target.value })}
                    className="input"
                  >
                    <option value="free">{t('apiKeyManagement.freeTier')}</option>
                    <option value="pro">{t('apiKeyManagement.proTier')}</option>
                    <option value="enterprise">{t('apiKeyManagement.enterpriseTier')}</option>
                  </select>
                  <p className="hint">{getTierInfo(formData.tier)}</p>
                </div>

                <div className="form-group">
                  <label>{t('apiKeyManagement.expiresIn')}</label>
                  <input
                    type="number"
                    min="1"
                    max="365"
                    placeholder="Days (optional)"
                    value={formData.expires_in_days || ''}
                    onChange={(e) => setFormData({ ...formData, expires_in_days: e.target.value })}
                    className="input"
                  />
                  <p className="hint">{t('apiKeyManagement.expirationInfo')}</p>
                </div>

                <div className="modal-actions">
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={() => setShowCreateModal(false)}
                  >
                    {t('common.cancel')}
                  </button>
                  <button
                    type="submit"
                    className="btn btn-primary"
                    disabled={!formData.name || loading}
                  >
                    {loading ? t('apiKeyManagement.creating') : t('apiKeyManagement.createButton')}
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}

      {/* Stats Modal */}
      {showStatsModal && keyStats && (
        <div className="modal-overlay" onClick={() => setShowStatsModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <h3>{t('apiKeyManagement.statsTitle')}</h3>

            <div className="stats-grid">
              <div className="stat-item">
                <label>{t('apiKeyManagement.requestsLifetime')}</label>
                <div className="stat-value">{keyStats.requests_lifetime}</div>
              </div>
              <div className="stat-item">
                <label>{t('apiKeyManagement.requestsThisMonth')}</label>
                <div className="stat-value">{keyStats.requests_this_month}</div>
              </div>
              <div className="stat-item">
                <label>{t('apiKeyManagement.monthlyQuota')}</label>
                <div className="stat-value">{keyStats.monthly_quota}</div>
              </div>
              <div className="stat-item">
                <label>{t('apiKeyManagement.quotaRemaining')}</label>
                <div className="stat-value">{keyStats.quota_remaining}</div>
              </div>
            </div>

            <div className="progress-bar">
              <div
                className="progress-fill"
                style={{ width: `${Math.min(keyStats.quota_percentage, 100)}%` }}
              ></div>
            </div>
            <p className="progress-text">
              {keyStats.quota_percentage.toFixed(1)}% {t('apiKeyManagement.quotaPercentage')}
            </p>

            {keyStats.last_used && (
              <p className="hint">
                {t('apiKeyManagement.lastUsed')}: {formatDate(keyStats.last_used)}
              </p>
            )}

            <div className="modal-actions">
              <button
                className="btn btn-primary"
                onClick={() => setShowStatsModal(false)}
              >
                {t('apiKeyManagement.closeStats')}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Rotate Modal */}
      {showRotateModal && selectedKey && (
        <div className="modal-overlay" onClick={() => setShowRotateModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <h3>{t('apiKeyManagement.rotateTitle')}</h3>
            <p>{t('apiKeyManagement.rotateDescription')}</p>
            <div className="alert alert-warning">{t('apiKeyManagement.rotateWarning')}</div>

            <div className="modal-actions">
              <button
                className="btn btn-secondary"
                onClick={() => setShowRotateModal(false)}
              >
                {t('common.cancel')}
              </button>
              <button
                className="btn btn-danger"
                onClick={handleRotateKey}
                disabled={loading}
              >
                {loading ? t('apiKeyManagement.rotating') : t('apiKeyManagement.rotateConfirm')}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Disable Modal */}
      {showDisableModal && selectedKey && (
        <div className="modal-overlay" onClick={() => setShowDisableModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <h3>{t('apiKeyManagement.disableTitle')}</h3>
            <p>{t('apiKeyManagement.disableDescription')}</p>
            <div className="alert alert-warning">{t('apiKeyManagement.disableWarning')}</div>

            <div className="modal-actions">
              <button
                className="btn btn-secondary"
                onClick={() => setShowDisableModal(false)}
              >
                {t('common.cancel')}
              </button>
              <button
                className="btn btn-danger"
                onClick={handleDisableKey}
                disabled={loading}
              >
                {loading ? t('apiKeyManagement.disabling') : t('apiKeyManagement.disableConfirm')}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Delete Modal */}
      {showDeleteModal && selectedKey && (
        <div className="modal-overlay" onClick={() => setShowDeleteModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <h3>{t('apiKeyManagement.deleteTitle')}</h3>
            <p>{t('apiKeyManagement.deleteDescription')}</p>
            <div className="alert alert-error">{t('apiKeyManagement.deleteWarning')}</div>

            <div className="modal-actions">
              <button
                className="btn btn-secondary"
                onClick={() => setShowDeleteModal(false)}
              >
                {t('common.cancel')}
              </button>
              <button
                className="btn btn-danger"
                onClick={handleDeleteKey}
                disabled={loading}
              >
                {loading ? t('apiKeyManagement.deleting') : t('apiKeyManagement.deleteConfirm')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default APIKeyManagement;
