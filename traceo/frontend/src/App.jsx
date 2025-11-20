import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import axios from 'axios';
import EmailList from './components/EmailList';
import EmailDetail from './components/EmailDetail';
import Settings from './components/Settings';
import AdminDashboard from './components/AdminDashboard';
import EmailRules from './components/EmailRules';
import Webhooks from './components/Webhooks';
import AuditLog from './components/AuditLog';
import './App.css';

const API_URL = process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000';

function App() {
  const { t, i18n } = useTranslation();

  // State Management
  const [emails, setEmails] = useState([]);
  const [selectedEmail, setSelectedEmail] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [showSettings, setShowSettings] = useState(false);
  const [showAdmin, setShowAdmin] = useState(false);
  const [showRules, setShowRules] = useState(false);
  const [showWebhooks, setShowWebhooks] = useState(false);
  const [showAudit, setShowAudit] = useState(false);
  const [stats, setStats] = useState(null);
  const [reportLoading, setReportLoading] = useState(false);
  const [token] = useState(localStorage.getItem('auth_token') || '');

  // API Configuration
  const axiosInstance = axios.create({
    baseURL: API_URL,
    headers: {
      'Content-Type': 'application/json',
    }
  });

  // Fetch emails on component mount and when language changes
  useEffect(() => {
    fetchEmails();
    fetchStats();
  }, [i18n.language]);

  /**
   * Fetch all emails from the API
   */
  const fetchEmails = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await axiosInstance.get('/emails');
      setEmails(response.data || []);
    } catch (err) {
      const errorMsg = err.response?.data?.detail || t('common.loading');
      setError(errorMsg);
      console.error('Error fetching emails:', err);
    } finally {
      setLoading(false);
    }
  };

  /**
   * Fetch statistics from the API
   */
  const fetchStats = async () => {
    try {
      const response = await axiosInstance.get('/admin/stats');
      setStats(response.data);
    } catch (err) {
      console.error('Error fetching stats:', err);
    }
  };

  /**
   * Send report for a specific email
   */
  const handleReportEmail = async (emailId) => {
    setReportLoading(true);
    try {
      const response = await axiosInstance.post('/report', {
        email_id: emailId,
        language: i18n.language
      });

      setSuccess(t('report.success'));
      setTimeout(() => setSuccess(null), 3000);

      // Refresh emails to get updated status
      await fetchEmails();
      await fetchStats();

      return true;
    } catch (err) {
      const errorMsg = err.response?.data?.detail || t('report.failed');
      setError(errorMsg);
      console.error('Error sending report:', err);
      return false;
    } finally {
      setReportLoading(false);
    }
  };

  /**
   * Delete an email
   */
  const handleDeleteEmail = async (emailId) => {
    try {
      await axiosInstance.delete(`/emails/${emailId}`);
      setSuccess(t('common.delete') + ' ' + t('report.success'));
      setTimeout(() => setSuccess(null), 2000);

      setEmails(emails.filter(email => email.id !== emailId));
      setSelectedEmail(null);
      await fetchStats();

      return true;
    } catch (err) {
      const errorMsg = err.response?.data?.detail || t('report.failed');
      setError(errorMsg);
      console.error('Error deleting email:', err);
      return false;
    }
  };

  /**
   * Change application language
   */
  const changeLanguage = (lang) => {
    i18n.changeLanguage(lang);
    localStorage.setItem('language', lang);
  };

  /**
   * Handle email selection
   */
  const handleSelectEmail = (email) => {
    setSelectedEmail(email);
  };

  /**
   * Clear error message
   */
  const dismissError = () => {
    setError(null);
  };

  /**
   * Clear success message
   */
  const dismissSuccess = () => {
    setSuccess(null);
  };

  return (
    <div className="app">
      {/* Header */}
      <header className="app-header">
        <div className="header-content">
          <div className="header-brand">
            <h1 className="app-title">
              <span className="brand-icon">🎯</span>
              {t('app_title')}
            </h1>
            <p className="app-subtitle">{t('app_description')}</p>
          </div>

          <div className="header-controls">
            {/* Statistics */}
            {stats && (
              <div className="header-stats">
                <div className="stat-item">
                  <span className="stat-value">{stats.total_emails || 0}</span>
                  <span className="stat-label">{t('dashboard.totalEmails')}</span>
                </div>
                <div className="stat-item">
                  <span className="stat-value" style={{ color: '#f44336' }}>
                    {stats.analyzed || 0}
                  </span>
                  <span className="stat-label">{t('dashboard.highRisk')}</span>
                </div>
                <div className="stat-item">
                  <span className="stat-value" style={{ color: '#4CAF50' }}>
                    {stats.reported || 0}
                  </span>
                  <span className="stat-label">{t('dashboard.reported')}</span>
                </div>
              </div>
            )}

            <div className="language-selector">
              <button
                onClick={() => changeLanguage('en')}
                className={`lang-btn ${i18n.language === 'en' ? 'active' : ''}`}
                title="English"
              >
                EN
              </button>
              <button
                onClick={() => changeLanguage('ja')}
                className={`lang-btn ${i18n.language === 'ja' ? 'active' : ''}`}
                title="日本語"
              >
                JA
              </button>
            </div>

            <button
              className="btn-admin"
              onClick={() => setShowAudit(true)}
              title="Audit Log"
            >
              📋 Audit
            </button>

            <button
              className="btn-admin"
              onClick={() => setShowWebhooks(true)}
              title="Webhooks"
            >
              🔔 Webhooks
            </button>

            <button
              className="btn-admin"
              onClick={() => setShowRules(true)}
              title="Email Rules"
            >
              📋 Rules
            </button>

            <button
              className="btn-admin"
              onClick={() => setShowAdmin(true)}
              title="Admin Dashboard"
            >
              📊 Admin
            </button>

            <button
              className="btn-settings"
              onClick={() => setShowSettings(true)}
              title={t('settings.title')}
            >
              ⚙️ {t('settings.title')}
            </button>
          </div>
        </div>
      </header>

      {/* Alert Messages */}
      {error && (
        <div className="alert alert-error">
          <span>{error}</span>
          <button className="alert-close" onClick={dismissError}>✕</button>
        </div>
      )}

      {success && (
        <div className="alert alert-success">
          <span>✓ {success}</span>
          <button className="alert-close" onClick={dismissSuccess}>✕</button>
        </div>
      )}

      {/* Main Content */}
      <main className="app-main">
        <div className="container">
          <EmailList
            emails={emails}
            onSelectEmail={handleSelectEmail}
            onRefresh={fetchEmails}
            loading={loading}
          />
        </div>
      </main>

      {/* Email Detail Modal */}
      {selectedEmail && (
        <EmailDetail
          email={selectedEmail}
          onClose={() => setSelectedEmail(null)}
          onReport={handleReportEmail}
          onDelete={handleDeleteEmail}
          loading={reportLoading}
        />
      )}

      {/* Settings Modal */}
      {showSettings && (
        <Settings
          onClose={() => setShowSettings(false)}
          config={{}}
        />
      )}

      {/* Admin Dashboard Modal */}
      {showAdmin && (
        <AdminDashboard
          isOpen={showAdmin}
          onClose={() => setShowAdmin(false)}
        />
      )}

      {/* Email Rules Modal */}
      {showRules && (
        <EmailRules
          isOpen={showRules}
          onClose={() => setShowRules(false)}
        />
      )}

      {/* Webhooks Modal */}
      {showWebhooks && (
        <Webhooks
          isOpen={showWebhooks}
          onClose={() => setShowWebhooks(false)}
          token={token}
        />
      )}

      {/* Audit Log Modal */}
      {showAudit && (
        <AuditLog
          isOpen={showAudit}
          onClose={() => setShowAudit(false)}
          token={token}
        />
      )}

      {/* Footer */}
      <footer className="app-footer">
        <div className="footer-content">
          <p>
            {t('app_title')} v1.0.0 •
            <a href="https://github.com/traceo-org/traceo" target="_blank" rel="noopener noreferrer">
              GitHub
            </a> •
            <a href="https://github.com/traceo-org/traceo/issues" target="_blank" rel="noopener noreferrer">
              {t('common.send')} {t('report.send')}
            </a>
          </p>
          <p>
            Made with ❤️ for email security
          </p>
        </div>
      </footer>
    </div>
  );
}

export default App;
