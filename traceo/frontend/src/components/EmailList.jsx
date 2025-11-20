import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import '../styles/EmailList.css';

const EmailList = ({ emails, onSelectEmail, onRefresh, loading }) => {
  const { t } = useTranslation();
  const [sortBy, setSortBy] = useState('date');
  const [filterStatus, setFilterStatus] = useState('all');
  const [searchText, setSearchText] = useState('');

  const getRiskColor = (score) => {
    if (score >= 80) return '#d32f2f'; // Red
    if (score >= 60) return '#f57c00'; // Orange
    if (score >= 40) return '#fbc02d'; // Yellow
    return '#388e3c'; // Green
  };

  const getRiskLevel = (score) => {
    if (score >= 80) return t('risk.critical');
    if (score >= 60) return t('risk.high');
    if (score >= 40) return t('risk.medium');
    return t('risk.low');
  };

  const filteredEmails = emails.filter(email => {
    const matchesSearch =
      email.subject?.toLowerCase().includes(searchText.toLowerCase()) ||
      email.from_addr?.toLowerCase().includes(searchText.toLowerCase());

    const matchesFilter = filterStatus === 'all' || email.status === filterStatus;

    return matchesSearch && matchesFilter;
  });

  const sortedEmails = [...filteredEmails].sort((a, b) => {
    switch (sortBy) {
      case 'score':
        return b.score - a.score;
      case 'date':
        return new Date(b.received_date) - new Date(a.received_date);
      case 'sender':
        return a.from_addr.localeCompare(b.from_addr);
      default:
        return 0;
    }
  });

  const formatDate = (dateString) => {
    const date = new Date(dateString);
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], {
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const getStatusBadge = (status) => {
    const statusConfig = {
      'pending': { color: '#2196F3', label: t('status.pending') },
      'analyzed': { color: '#FF9800', label: t('status.analyzed') },
      'reported': { color: '#4CAF50', label: t('status.reported') },
      'false_positive': { color: '#9C27B0', label: t('status.false_positive') },
      'error': { color: '#f44336', label: t('status.error') }
    };
    const config = statusConfig[status] || statusConfig['pending'];
    return config;
  };

  return (
    <div className="email-list-container">
      <div className="email-list-header">
        <h2>{t('emails.list')}</h2>
        <button
          className="btn-refresh"
          onClick={onRefresh}
          disabled={loading}
          title={t('common.refresh')}
        >
          {loading ? '⟳' : '🔄'}
        </button>
      </div>

      <div className="email-list-controls">
        <div className="search-box">
          <input
            type="text"
            placeholder={t('emails.search')}
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            className="search-input"
          />
          <span className="search-icon">🔍</span>
        </div>

        <div className="filter-controls">
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value)}
            className="select-control"
          >
            <option value="date">{t('emails.sortByDate')}</option>
            <option value="score">{t('emails.sortByRisk')}</option>
            <option value="sender">{t('emails.sortBySender')}</option>
          </select>

          <select
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value)}
            className="select-control"
          >
            <option value="all">{t('emails.allStatus')}</option>
            <option value="pending">{t('status.pending')}</option>
            <option value="analyzed">{t('status.analyzed')}</option>
            <option value="reported">{t('status.reported')}</option>
            <option value="false_positive">{t('status.false_positive')}</option>
          </select>
        </div>

        <span className="email-count">
          {sortedEmails.length} {t('emails.found')}
        </span>
      </div>

      {sortedEmails.length === 0 ? (
        <div className="email-list-empty">
          <p>{t('emails.noEmails')}</p>
        </div>
      ) : (
        <table className="email-table">
          <thead>
            <tr>
              <th>{t('emails.sender')}</th>
              <th>{t('emails.subject')}</th>
              <th>{t('emails.date')}</th>
              <th>{t('emails.riskScore')}</th>
              <th>{t('emails.status')}</th>
              <th>{t('common.action')}</th>
            </tr>
          </thead>
          <tbody>
            {sortedEmails.map((email) => {
              const statusConfig = getStatusBadge(email.status);
              return (
                <tr
                  key={email.id}
                  className="email-row"
                  onClick={() => onSelectEmail(email)}
                >
                  <td className="cell-sender" title={email.from_addr}>
                    {email.from_addr}
                  </td>
                  <td className="cell-subject" title={email.subject}>
                    {email.subject}
                  </td>
                  <td className="cell-date">
                    {formatDate(email.received_date)}
                  </td>
                  <td className="cell-score">
                    <div
                      className="risk-badge"
                      style={{
                        backgroundColor: getRiskColor(email.score),
                        color: 'white'
                      }}
                    >
                      {email.score}
                      <span className="risk-label">
                        {getRiskLevel(email.score)}
                      </span>
                    </div>
                  </td>
                  <td className="cell-status">
                    <span
                      className="status-badge"
                      style={{ backgroundColor: statusConfig.color }}
                    >
                      {statusConfig.label}
                    </span>
                  </td>
                  <td className="cell-action">
                    <button
                      className="btn-view"
                      onClick={(e) => {
                        e.stopPropagation();
                        onSelectEmail(email);
                      }}
                    >
                      {t('common.view')}
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
};

export default EmailList;
