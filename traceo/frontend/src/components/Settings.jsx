import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import '../styles/Settings.css';

const Settings = ({ onClose, config = {} }) => {
  const { t, i18n } = useTranslation();
  const [activeTab, setActiveTab] = useState('general');
  const [settings, setSettings] = useState({
    language: localStorage.getItem('language') || 'en',
    autoReport: localStorage.getItem('autoReport') !== 'false',
    scoreThreshold: localStorage.getItem('scoreThreshold') || '50',
    notifyEmail: localStorage.getItem('notifyEmail') || '',
    theme: localStorage.getItem('theme') || 'light',
    imapServer: localStorage.getItem('imapServer') || '',
    imapPort: localStorage.getItem('imapPort') || '993',
    imapUser: localStorage.getItem('imapUser') || '',
    smtpServer: localStorage.getItem('smtpServer') || '',
    smtpPort: localStorage.getItem('smtpPort') || '587',
    smtpUser: localStorage.getItem('smtpUser') || '',
  });

  const [saveStatus, setSaveStatus] = useState(null);
  const [testStatus, setTestStatus] = useState(null);

  const handleInputChange = (field, value) => {
    setSettings(prev => ({
      ...prev,
      [field]: value
    }));
  };

  const handleSave = () => {
    // Save to localStorage
    Object.entries(settings).forEach(([key, value]) => {
      localStorage.setItem(key, value);
    });

    // Update language
    if (settings.language !== i18n.language) {
      i18n.changeLanguage(settings.language);
    }

    setSaveStatus('success');
    setTimeout(() => setSaveStatus(null), 3000);
  };

  const handleTestConnection = async () => {
    setTestStatus('testing');
    try {
      // Test IMAP connection
      const response = await fetch('/api/test-imap', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          server: settings.imapServer,
          port: parseInt(settings.imapPort),
          user: settings.imapUser,
        })
      });

      if (response.ok) {
        setTestStatus('success');
      } else {
        setTestStatus('error');
      }
    } catch (error) {
      setTestStatus('error');
      console.error('Connection test failed:', error);
    }
    setTimeout(() => setTestStatus(null), 3000);
  };

  const languages = [
    { code: 'en', name: 'English' },
    { code: 'ja', name: '日本語' },
    { code: 'es', name: 'Español' },
    { code: 'fr', name: 'Français' },
    { code: 'de', name: 'Deutsch' },
    { code: 'pt', name: 'Português' },
    { code: 'zh', name: '中文' },
    { code: 'ko', name: '한국어' },
    { code: 'ru', name: 'Русский' },
    { code: 'ar', name: 'العربية' },
  ];

  return (
    <div className="settings-overlay" onClick={onClose}>
      <div className="settings-modal" onClick={(e) => e.stopPropagation()}>
        <div className="settings-header">
          <h2>{t('settings.title')}</h2>
          <button className="btn-close" onClick={onClose}>✕</button>
        </div>

        <div className="settings-tabs">
          <button
            className={`tab-btn ${activeTab === 'general' ? 'active' : ''}`}
            onClick={() => setActiveTab('general')}
          >
            {t('settings.general')}
          </button>
          <button
            className={`tab-btn ${activeTab === 'email' ? 'active' : ''}`}
            onClick={() => setActiveTab('email')}
          >
            {t('settings.email')}
          </button>
          <button
            className={`tab-btn ${activeTab === 'security' ? 'active' : ''}`}
            onClick={() => setActiveTab('security')}
          >
            {t('settings.security')}
          </button>
          <button
            className={`tab-btn ${activeTab === 'about' ? 'active' : ''}`}
            onClick={() => setActiveTab('about')}
          >
            {t('settings.about')}
          </button>
        </div>

        <div className="settings-content">
          {activeTab === 'general' && (
            <div className="settings-section">
              <h3>{t('settings.general')}</h3>

              <div className="setting-item">
                <label>{t('settings.language')}</label>
                <select
                  value={settings.language}
                  onChange={(e) => handleInputChange('language', e.target.value)}
                  className="setting-select"
                >
                  {languages.map(lang => (
                    <option key={lang.code} value={lang.code}>
                      {lang.name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="setting-item">
                <label>{t('settings.theme')}</label>
                <select
                  value={settings.theme}
                  onChange={(e) => handleInputChange('theme', e.target.value)}
                  className="setting-select"
                >
                  <option value="light">{t('settings.lightTheme')}</option>
                  <option value="dark">{t('settings.darkTheme')}</option>
                  <option value="auto">{t('settings.autoTheme')}</option>
                </select>
              </div>

              <div className="setting-item">
                <label>{t('settings.scoreThreshold')}</label>
                <input
                  type="number"
                  min="0"
                  max="100"
                  value={settings.scoreThreshold}
                  onChange={(e) => handleInputChange('scoreThreshold', e.target.value)}
                  className="setting-input"
                />
                <small>{t('settings.scoreThresholdHelp')}</small>
              </div>

              <div className="setting-item">
                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={settings.autoReport}
                    onChange={(e) => handleInputChange('autoReport', e.target.checked)}
                  />
                  {t('settings.autoReport')}
                </label>
                <small>{t('settings.autoReportHelp')}</small>
              </div>

              <div className="setting-item">
                <label>{t('settings.notifyEmail')}</label>
                <input
                  type="email"
                  value={settings.notifyEmail}
                  onChange={(e) => handleInputChange('notifyEmail', e.target.value)}
                  className="setting-input"
                  placeholder={t('settings.notifyEmailPlaceholder')}
                />
              </div>
            </div>
          )}

          {activeTab === 'email' && (
            <div className="settings-section">
              <h3>{t('settings.emailConfiguration')}</h3>

              <div className="config-group">
                <h4>{t('settings.imap')}</h4>

                <div className="setting-item">
                  <label>{t('settings.server')}</label>
                  <input
                    type="text"
                    value={settings.imapServer}
                    onChange={(e) => handleInputChange('imapServer', e.target.value)}
                    className="setting-input"
                    placeholder="imap.gmail.com"
                  />
                </div>

                <div className="setting-item">
                  <label>{t('settings.port')}</label>
                  <input
                    type="number"
                    value={settings.imapPort}
                    onChange={(e) => handleInputChange('imapPort', e.target.value)}
                    className="setting-input"
                    placeholder="993"
                  />
                </div>

                <div className="setting-item">
                  <label>{t('settings.username')}</label>
                  <input
                    type="email"
                    value={settings.imapUser}
                    onChange={(e) => handleInputChange('imapUser', e.target.value)}
                    className="setting-input"
                    placeholder="your@email.com"
                  />
                </div>
              </div>

              <div className="config-group">
                <h4>{t('settings.smtp')}</h4>

                <div className="setting-item">
                  <label>{t('settings.server')}</label>
                  <input
                    type="text"
                    value={settings.smtpServer}
                    onChange={(e) => handleInputChange('smtpServer', e.target.value)}
                    className="setting-input"
                    placeholder="smtp.gmail.com"
                  />
                </div>

                <div className="setting-item">
                  <label>{t('settings.port')}</label>
                  <input
                    type="number"
                    value={settings.smtpPort}
                    onChange={(e) => handleInputChange('smtpPort', e.target.value)}
                    className="setting-input"
                    placeholder="587"
                  />
                </div>

                <div className="setting-item">
                  <label>{t('settings.username')}</label>
                  <input
                    type="email"
                    value={settings.smtpUser}
                    onChange={(e) => handleInputChange('smtpUser', e.target.value)}
                    className="setting-input"
                    placeholder="your@email.com"
                  />
                </div>
              </div>

              <button
                className="btn-test-connection"
                onClick={handleTestConnection}
                disabled={testStatus === 'testing'}
              >
                {testStatus === 'testing' ? t('settings.testing') + '...' : t('settings.testConnection')}
              </button>

              {testStatus === 'success' && (
                <div className="status-message success">
                  ✓ {t('settings.connectionSuccess')}
                </div>
              )}
              {testStatus === 'error' && (
                <div className="status-message error">
                  ✗ {t('settings.connectionFailed')}
                </div>
              )}
            </div>
          )}

          {activeTab === 'security' && (
            <div className="settings-section">
              <h3>{t('settings.security')}</h3>
              <div className="security-info">
                <p>{t('settings.securityInfo')}</p>
                <ul>
                  <li>{t('settings.securityPoint1')}</li>
                  <li>{t('settings.securityPoint2')}</li>
                  <li>{t('settings.securityPoint3')}</li>
                  <li>{t('settings.securityPoint4')}</li>
                </ul>
              </div>
            </div>
          )}

          {activeTab === 'about' && (
            <div className="settings-section">
              <h3>{t('settings.about')}</h3>
              <div className="about-info">
                <p><strong>Traceo</strong> v1.0.0</p>
                <p>{t('settings.aboutText')}</p>
                <p>
                  <a href="https://github.com/traceo-org/traceo" target="_blank" rel="noopener noreferrer">
                    GitHub Repository →
                  </a>
                </p>
                <p>
                  <small>{t('settings.license')}</small>
                </p>
              </div>
            </div>
          )}
        </div>

        <div className="settings-actions">
          {saveStatus === 'success' && (
            <div className="status-message success">
              ✓ {t('settings.saved')}
            </div>
          )}
          <button className="btn-save" onClick={handleSave}>
            {t('common.save')}
          </button>
          <button className="btn-cancel" onClick={onClose}>
            {t('common.close')}
          </button>
        </div>
      </div>
    </div>
  );
};

export default Settings;
