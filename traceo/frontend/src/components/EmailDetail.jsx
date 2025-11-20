import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import '../styles/EmailDetail.css';

const EmailDetail = ({ email, onClose, onReport, onDelete, loading }) => {
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState('overview');
  const [reportSent, setReportSent] = useState(false);

  if (!email) return null;

  const getRiskColor = (score) => {
    if (score >= 80) return '#d32f2f';
    if (score >= 60) return '#f57c00';
    if (score >= 40) return '#fbc02d';
    return '#388e3c';
  };

  const getRiskLevel = (score) => {
    if (score >= 80) return t('risk.critical');
    if (score >= 60) return t('risk.high');
    if (score >= 40) return t('risk.medium');
    return t('risk.low');
  };

  const handleReport = async () => {
    if (await onReport(email.id)) {
      setReportSent(true);
      setTimeout(() => setReportSent(false), 3000);
    }
  };

  const handleDelete = async () => {
    if (window.confirm(t('emails.confirmDelete'))) {
      await onDelete(email.id);
      onClose();
    }
  };

  const formatDate = (dateString) => {
    const date = new Date(dateString);
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
  };

  return (
    <div className="email-detail-overlay" onClick={onClose}>
      <div className="email-detail-modal" onClick={(e) => e.stopPropagation()}>
        <div className="detail-header">
          <h2>{t('emails.details')}</h2>
          <button className="btn-close" onClick={onClose}>✕</button>
        </div>

        <div className="detail-content">
          {/* Risk Score Overview */}
          <div className="risk-overview">
            <div
              className="risk-score-large"
              style={{ backgroundColor: getRiskColor(email.score) }}
            >
              <div className="score-number">{email.score}</div>
              <div className="score-level">{getRiskLevel(email.score)}</div>
            </div>
            <div className="risk-info">
              <p><strong>{t('emails.status')}:</strong> {email.status}</p>
              <p><strong>{t('emails.date')}:</strong> {formatDate(email.received_date)}</p>
              {email.analyzed_date && (
                <p><strong>{t('emails.analyzed')}:</strong> {formatDate(email.analyzed_date)}</p>
              )}
            </div>
          </div>

          {/* Tabs */}
          <div className="detail-tabs">
            <button
              className={`tab-btn ${activeTab === 'overview' ? 'active' : ''}`}
              onClick={() => setActiveTab('overview')}
            >
              {t('emails.overview')}
            </button>
            <button
              className={`tab-btn ${activeTab === 'analysis' ? 'active' : ''}`}
              onClick={() => setActiveTab('analysis')}
            >
              {t('emails.analysis')}
            </button>
            <button
              className={`tab-btn ${activeTab === 'headers' ? 'active' : ''}`}
              onClick={() => setActiveTab('headers')}
            >
              {t('emails.headers')}
            </button>
            <button
              className={`tab-btn ${activeTab === 'technical' ? 'active' : ''}`}
              onClick={() => setActiveTab('technical')}
            >
              {t('emails.technical')}
            </button>
          </div>

          {/* Tab Content */}
          <div className="tab-content">
            {activeTab === 'overview' && (
              <div className="overview-section">
                <div className="detail-field">
                  <label>{t('emails.from')}:</label>
                  <div className="field-value email-addr">{email.from_addr}</div>
                </div>
                <div className="detail-field">
                  <label>{t('emails.to')}:</label>
                  <div className="field-value">
                    {email.to_addrs?.join(', ') || t('common.notAvailable')}
                  </div>
                </div>
                <div className="detail-field">
                  <label>{t('emails.subject')}:</label>
                  <div className="field-value">{email.subject}</div>
                </div>
                <div className="detail-field">
                  <label>{t('emails.date')}:</label>
                  <div className="field-value">{formatDate(email.received_date)}</div>
                </div>
              </div>
            )}

            {activeTab === 'analysis' && (
              <div className="analysis-section">
                <div className="analysis-item">
                  <h4>{t('emails.indicators')}</h4>
                  {email.indicators && email.indicators.length > 0 ? (
                    <ul className="indicators-list">
                      {email.indicators.map((indicator, idx) => (
                        <li key={idx} className="indicator-item">
                          <span className="indicator-icon">⚠️</span>
                          {indicator}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p>{t('emails.noIndicators')}</p>
                  )}
                </div>

                {email.analysis && (
                  <>
                    <div className="analysis-item">
                      <h4>{t('emails.scoreBreakdown')}</h4>
                      <div className="breakdown-chart">
                        {Object.entries(email.analysis.breakdown || {}).map(
                          ([key, value]) => (
                            <div key={key} className="breakdown-item">
                              <div className="breakdown-label">{key}</div>
                              <div className="breakdown-bar">
                                <div
                                  className="breakdown-fill"
                                  style={{ width: `${Math.min(value, 100)}%` }}
                                />
                              </div>
                              <div className="breakdown-value">{value}</div>
                            </div>
                          )
                        )}
                      </div>
                    </div>

                    {email.analysis.urls && email.analysis.urls.length > 0 && (
                      <div className="analysis-item">
                        <h4>{t('emails.urls')}</h4>
                        <ul className="urls-list">
                          {email.analysis.urls.map((url, idx) => (
                            <li key={idx} className="url-item">
                              <code>{url}</code>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </>
                )}
              </div>
            )}

            {activeTab === 'headers' && (
              <div className="headers-section">
                <pre className="headers-content">
                  {email.raw_headers || t('emails.noHeaders')}
                </pre>
              </div>
            )}

            {activeTab === 'technical' && (
              <div className="technical-section">
                {email.domain_info && (
                  <div className="analysis-item">
                    <h4>{t('emails.domainInfo')}</h4>
                    <div className="technical-grid">
                      {email.domain_info.registrar && (
                        <div className="tech-item">
                          <label>{t('emails.registrar')}:</label>
                          <span>{email.domain_info.registrar}</span>
                        </div>
                      )}
                      {email.domain_info.registered_date && (
                        <div className="tech-item">
                          <label>{t('emails.registeredDate')}:</label>
                          <span>{email.domain_info.registered_date}</span>
                        </div>
                      )}
                      {email.domain_info.country && (
                        <div className="tech-item">
                          <label>{t('emails.country')}:</label>
                          <span>{email.domain_info.country}</span>
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {email.ip_info && (
                  <div className="analysis-item">
                    <h4>{t('emails.ipInfo')}</h4>
                    <div className="technical-grid">
                      {email.ip_info.ip && (
                        <div className="tech-item">
                          <label>IP:</label>
                          <span>{email.ip_info.ip}</span>
                        </div>
                      )}
                      {email.ip_info.provider && (
                        <div className="tech-item">
                          <label>{t('emails.provider')}:</label>
                          <span>{email.ip_info.provider}</span>
                        </div>
                      )}
                      {email.ip_info.country && (
                        <div className="tech-item">
                          <label>{t('emails.country')}:</label>
                          <span>{email.ip_info.country}</span>
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Actions */}
        <div className="detail-actions">
          {reportSent && (
            <div className="report-status success">
              ✓ {t('emails.reportSent')}
            </div>
          )}
          {email.status === 'pending' || email.status === 'analyzed' ? (
            <button
              className="btn-report"
              onClick={handleReport}
              disabled={loading || reportSent}
            >
              {loading ? t('common.sending') + '...' : t('emails.sendReport')}
            </button>
          ) : (
            <div className="status-info">
              {t('emails.alreadyReported')}
            </div>
          )}
          <button
            className="btn-delete"
            onClick={handleDelete}
            disabled={loading}
          >
            {t('common.delete')}
          </button>
          <button className="btn-cancel" onClick={onClose}>
            {t('common.close')}
          </button>
        </div>
      </div>
    </div>
  );
};

export default EmailDetail;
