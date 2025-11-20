/**
 * Email Rules Component
 * Create and manage email filtering rules with auto-actions
 */

import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import axios from 'axios';
import '../styles/EmailRules.css';

const EmailRules = ({ isOpen, onClose }) => {
  const { t } = useTranslation();
  const [rules, setRules] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [selectedRule, setSelectedRule] = useState(null);
  const [stats, setStats] = useState(null);

  // Form state
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    conditions: [{ field: 'from_addr', operator: 'contains', value: '' }],
    actions: [{ type: 'mark_status', params: { status: 'reported' } }],
    enabled: true,
    priority: 50,
  });

  // Load rules
  const loadRules = async () => {
    setLoading(true);
    setError(null);
    try {
      const [rulesRes, statsRes] = await Promise.all([
        axios.get('/rules/'),
        axios.get('/rules/stats/summary'),
      ]);
      setRules(rulesRes.data);
      setStats(statsRes.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load rules');
      console.error('Rules load error:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      loadRules();
    }
  }, [isOpen]);

  // Handle form changes
  const handleFieldChange = (field, value) => {
    setFormData((prev) => ({
      ...prev,
      [field]: value,
    }));
  };

  const handleConditionChange = (index, field, value) => {
    setFormData((prev) => {
      const newConditions = [...prev.conditions];
      newConditions[index] = { ...newConditions[index], [field]: value };
      return { ...prev, conditions: newConditions };
    });
  };

  const handleActionChange = (index, field, value) => {
    setFormData((prev) => {
      const newActions = [...prev.actions];
      if (field === 'type') {
        newActions[index] = { type: value, params: {} };
      } else {
        newActions[index] = { ...newActions[index], [field]: value };
      }
      return { ...prev, actions: newActions };
    });
  };

  const addCondition = () => {
    setFormData((prev) => ({
      ...prev,
      conditions: [
        ...prev.conditions,
        { field: 'from_addr', operator: 'contains', value: '' },
      ],
    }));
  };

  const removeCondition = (index) => {
    setFormData((prev) => ({
      ...prev,
      conditions: prev.conditions.filter((_, i) => i !== index),
    }));
  };

  const addAction = () => {
    setFormData((prev) => ({
      ...prev,
      actions: [
        ...prev.actions,
        { type: 'mark_status', params: { status: 'reported' } },
      ],
    }));
  };

  const removeAction = (index) => {
    setFormData((prev) => ({
      ...prev,
      actions: prev.actions.filter((_, i) => i !== index),
    }));
  };

  // Save rule
  const handleSaveRule = async () => {
    try {
      setLoading(true);
      setError(null);

      if (!formData.name) {
        setError('Rule name is required');
        setLoading(false);
        return;
      }

      if (formData.conditions.length === 0) {
        setError('At least one condition is required');
        setLoading(false);
        return;
      }

      if (formData.actions.length === 0) {
        setError('At least one action is required');
        setLoading(false);
        return;
      }

      if (selectedRule) {
        // Update existing rule
        await axios.put(`/rules/${selectedRule.id}`, formData);
        setSuccess('Rule updated successfully');
      } else {
        // Create new rule
        await axios.post('/rules/', formData);
        setSuccess('Rule created successfully');
      }

      setFormData({
        name: '',
        description: '',
        conditions: [{ field: 'from_addr', operator: 'contains', value: '' }],
        actions: [{ type: 'mark_status', params: { status: 'reported' } }],
        enabled: true,
        priority: 50,
      });
      setShowForm(false);
      setSelectedRule(null);
      setTimeout(() => setSuccess(null), 3000);
      await loadRules();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to save rule');
    } finally {
      setLoading(false);
    }
  };

  // Edit rule
  const handleEditRule = (rule) => {
    setSelectedRule(rule);
    setFormData({
      name: rule.name,
      description: rule.description,
      conditions: rule.conditions,
      actions: rule.actions,
      enabled: rule.enabled,
      priority: rule.priority,
    });
    setShowForm(true);
  };

  // Delete rule
  const handleDeleteRule = async (ruleId) => {
    if (!window.confirm('Are you sure you want to delete this rule?')) {
      return;
    }

    try {
      setLoading(true);
      await axios.delete(`/rules/${ruleId}`);
      setSuccess('Rule deleted successfully');
      setTimeout(() => setSuccess(null), 3000);
      await loadRules();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to delete rule');
    } finally {
      setLoading(false);
    }
  };

  // Toggle rule
  const handleToggleRule = async (rule) => {
    try {
      await axios.post(`/rules/${rule.id}/toggle`);
      await loadRules();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to toggle rule');
    }
  };

  // Test rule
  const handleTestRule = async (rule, emailId) => {
    try {
      const response = await axios.post(`/rules/${rule.id}/test?email_id=${emailId}`);
      alert(
        `Rule matches: ${response.data.matches}\n` +
          `Conditions matched:\n${response.data.conditions
            .map((c) => `- ${c.condition.field} ${c.condition.operator}: ${c.matched}`)
            .join('\n')}`
      );
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to test rule');
    }
  };

  if (!isOpen) return null;

  const fieldOptions = [
    { value: 'from_addr', label: 'Sender' },
    { value: 'subject', label: 'Subject' },
    { value: 'domain', label: 'Domain' },
    { value: 'score', label: 'Risk Score' },
    { value: 'urls_count', label: 'URLs Count' },
    { value: 'status', label: 'Status' },
  ];

  const operatorOptions = [
    { value: 'equals', label: 'Equals' },
    { value: 'contains', label: 'Contains' },
    { value: 'startswith', label: 'Starts with' },
    { value: 'endswith', label: 'Ends with' },
    { value: 'greater_than', label: 'Greater than' },
    { value: 'less_than', label: 'Less than' },
    { value: 'regex', label: 'Regex' },
  ];

  const actionTypeOptions = [
    { value: 'mark_status', label: 'Mark Status' },
    { value: 'auto_report', label: 'Auto Report' },
    { value: 'flag', label: 'Flag for Review' },
    { value: 'delete', label: 'Delete Email' },
    { value: 'add_label', label: 'Add Label' },
    { value: 'block_sender', label: 'Block Sender' },
    { value: 'trust_domain', label: 'Trust Domain' },
  ];

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="email-rules" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="rules-header">
          <h1>Email Rules</h1>
          <button className="close-btn" onClick={onClose}>
            ×
          </button>
        </div>

        {/* Messages */}
        {error && <div className="alert alert-error">{error}</div>}
        {success && <div className="alert alert-success">{success}</div>}

        {/* Content */}
        <div className="rules-content">
          {loading && <div className="loading-spinner">Loading...</div>}

          {!showForm && (
            <>
              {/* Stats */}
              {stats && (
                <div className="rules-stats">
                  <div className="stat-item">
                    <span className="stat-label">Total Rules</span>
                    <span className="stat-value">{stats.total_rules}</span>
                  </div>
                  <div className="stat-item">
                    <span className="stat-label">Enabled</span>
                    <span className="stat-value">{stats.enabled_rules}</span>
                  </div>
                  <div className="stat-item">
                    <span className="stat-label">Total Matches</span>
                    <span className="stat-value">{stats.total_matches}</span>
                  </div>
                </div>
              )}

              {/* Rules List */}
              <div className="rules-list">
                {rules.length === 0 ? (
                  <div className="empty-state">
                    <p>No rules created yet</p>
                    <button
                      className="btn btn-primary"
                      onClick={() => {
                        setShowForm(true);
                        setSelectedRule(null);
                        setFormData({
                          name: '',
                          description: '',
                          conditions: [{ field: 'from_addr', operator: 'contains', value: '' }],
                          actions: [{ type: 'mark_status', params: { status: 'reported' } }],
                          enabled: true,
                          priority: 50,
                        });
                      }}
                    >
                      Create First Rule
                    </button>
                  </div>
                ) : (
                  rules.map((rule) => (
                    <div key={rule.id} className="rule-card">
                      <div className="rule-header">
                        <div className="rule-title">
                          <input
                            type="checkbox"
                            checked={rule.enabled}
                            onChange={() => handleToggleRule(rule)}
                            className="rule-toggle"
                          />
                          <h3>{rule.name}</h3>
                          <span className="rule-priority">Priority: {rule.priority}</span>
                        </div>
                        <div className="rule-actions">
                          <button
                            className="btn-icon"
                            onClick={() => handleEditRule(rule)}
                            title="Edit"
                          >
                            ✎
                          </button>
                          <button
                            className="btn-icon btn-danger"
                            onClick={() => handleDeleteRule(rule.id)}
                            title="Delete"
                          >
                            🗑
                          </button>
                        </div>
                      </div>

                      {rule.description && <p className="rule-description">{rule.description}</p>}

                      <div className="rule-details">
                        <div className="detail-section">
                          <h4>Conditions</h4>
                          <ul className="conditions-list">
                            {rule.conditions.map((cond, idx) => (
                              <li key={idx}>
                                {cond.field} {cond.operator} {cond.value}
                              </li>
                            ))}
                          </ul>
                        </div>

                        <div className="detail-section">
                          <h4>Actions</h4>
                          <ul className="actions-list">
                            {rule.actions.map((action, idx) => (
                              <li key={idx}>{action.type}</li>
                            ))}
                          </ul>
                        </div>

                        <div className="detail-section">
                          <h4>Matched</h4>
                          <span className="matched-count">{rule.matched_count || 0} times</span>
                        </div>
                      </div>
                    </div>
                  ))
                )}
              </div>

              {rules.length > 0 && (
                <button
                  className="btn btn-primary btn-block"
                  onClick={() => {
                    setShowForm(true);
                    setSelectedRule(null);
                    setFormData({
                      name: '',
                      description: '',
                      conditions: [{ field: 'from_addr', operator: 'contains', value: '' }],
                      actions: [{ type: 'mark_status', params: { status: 'reported' } }],
                      enabled: true,
                      priority: 50,
                    });
                  }}
                >
                  + Add New Rule
                </button>
              )}
            </>
          )}

          {showForm && (
            <div className="rule-form">
              <h2>{selectedRule ? 'Edit Rule' : 'Create New Rule'}</h2>

              {/* Basic Info */}
              <div className="form-group">
                <label>Rule Name *</label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => handleFieldChange('name', e.target.value)}
                  placeholder="e.g., Block payment phishing"
                  className="form-input"
                />
              </div>

              <div className="form-group">
                <label>Description</label>
                <textarea
                  value={formData.description || ''}
                  onChange={(e) => handleFieldChange('description', e.target.value)}
                  placeholder="Optional description"
                  className="form-textarea"
                  rows="2"
                />
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label>Priority (0-100)</label>
                  <input
                    type="number"
                    min="0"
                    max="100"
                    value={formData.priority}
                    onChange={(e) => handleFieldChange('priority', parseInt(e.target.value))}
                    className="form-input"
                  />
                </div>

                <div className="form-group">
                  <label>Enabled</label>
                  <input
                    type="checkbox"
                    checked={formData.enabled}
                    onChange={(e) => handleFieldChange('enabled', e.target.checked)}
                    className="form-checkbox"
                  />
                </div>
              </div>

              {/* Conditions */}
              <div className="form-section">
                <h3>Conditions (All must match)</h3>
                {formData.conditions.map((cond, idx) => (
                  <div key={idx} className="condition-row">
                    <select
                      value={cond.field}
                      onChange={(e) => handleConditionChange(idx, 'field', e.target.value)}
                      className="form-select"
                    >
                      {fieldOptions.map((opt) => (
                        <option key={opt.value} value={opt.value}>
                          {opt.label}
                        </option>
                      ))}
                    </select>

                    <select
                      value={cond.operator}
                      onChange={(e) => handleConditionChange(idx, 'operator', e.target.value)}
                      className="form-select"
                    >
                      {operatorOptions.map((opt) => (
                        <option key={opt.value} value={opt.value}>
                          {opt.label}
                        </option>
                      ))}
                    </select>

                    <input
                      type="text"
                      value={cond.value}
                      onChange={(e) => handleConditionChange(idx, 'value', e.target.value)}
                      placeholder="Value"
                      className="form-input"
                    />

                    {formData.conditions.length > 1 && (
                      <button
                        type="button"
                        onClick={() => removeCondition(idx)}
                        className="btn-remove"
                      >
                        ✕
                      </button>
                    )}
                  </div>
                ))}

                <button
                  type="button"
                  onClick={addCondition}
                  className="btn btn-secondary btn-sm"
                >
                  + Add Condition
                </button>
              </div>

              {/* Actions */}
              <div className="form-section">
                <h3>Actions</h3>
                {formData.actions.map((action, idx) => (
                  <div key={idx} className="action-row">
                    <select
                      value={action.type}
                      onChange={(e) => handleActionChange(idx, 'type', e.target.value)}
                      className="form-select"
                    >
                      {actionTypeOptions.map((opt) => (
                        <option key={opt.value} value={opt.value}>
                          {opt.label}
                        </option>
                      ))}
                    </select>

                    {action.type === 'mark_status' && (
                      <select
                        value={action.params.status || 'reported'}
                        onChange={(e) =>
                          handleActionChange(idx, 'params', { status: e.target.value })
                        }
                        className="form-select"
                      >
                        <option value="reported">Mark as Reported</option>
                        <option value="pending">Mark as Pending</option>
                        <option value="analyzed">Mark as Analyzed</option>
                        <option value="false_positive">Mark as False Positive</option>
                      </select>
                    )}

                    {action.type === 'add_label' && (
                      <input
                        type="text"
                        placeholder="Label name"
                        value={action.params.label || ''}
                        onChange={(e) =>
                          handleActionChange(idx, 'params', { label: e.target.value })
                        }
                        className="form-input"
                      />
                    )}

                    {formData.actions.length > 1 && (
                      <button
                        type="button"
                        onClick={() => removeAction(idx)}
                        className="btn-remove"
                      >
                        ✕
                      </button>
                    )}
                  </div>
                ))}

                <button
                  type="button"
                  onClick={addAction}
                  className="btn btn-secondary btn-sm"
                >
                  + Add Action
                </button>
              </div>

              {/* Form Buttons */}
              <div className="form-buttons">
                <button className="btn btn-primary" onClick={handleSaveRule} disabled={loading}>
                  {loading ? 'Saving...' : 'Save Rule'}
                </button>
                <button
                  className="btn btn-secondary"
                  onClick={() => {
                    setShowForm(false);
                    setSelectedRule(null);
                  }}
                >
                  Cancel
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="rules-footer">
          <button className="btn btn-secondary" onClick={loadRules} disabled={loading}>
            {loading ? 'Refreshing...' : 'Refresh'}
          </button>
          <button className="btn btn-secondary" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
};

export default EmailRules;
