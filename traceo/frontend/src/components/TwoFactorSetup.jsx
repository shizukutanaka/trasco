/**
 * Two-Factor Authentication (2FA) Setup Component
 * Handles TOTP setup, backup code generation and storage, and 2FA management
 */

import React, { useState, useEffect } from "react";
import axios from "axios";
import { useTranslation } from "react-i18next";
import "../styles/TwoFactorSetup.css";

const TwoFactorSetup = ({ onClose, currentUser }) => {
  const { t } = useTranslation();
  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  // Step 1: QR Code & Secret
  const [secret, setSecret] = useState("");
  const [qrCode, setQrCode] = useState("");
  const [backupCodesGenerated, setBackupCodesGenerated] = useState([]);

  // Step 2: TOTP Verification
  const [totpInput, setTotpInput] = useState("");
  const [verifying, setVerifying] = useState(false);

  // Step 3: Backup Codes Display
  const [displayBackupCodes, setDisplayBackupCodes] = useState([]);

  // 2FA Status
  const [twoFaStatus, setTwoFaStatus] = useState(null);
  const [showStatusModal, setShowStatusModal] = useState(false);
  const [showDisableModal, setShowDisableModal] = useState(false);
  const [showRegenerateModal, setShowRegenerateModal] = useState(false);
  const [disablePassword, setDisablePassword] = useState("");
  const [regenerateTotpInput, setRegenerateTotpInput] = useState("");

  // Fetch 2FA status on mount
  useEffect(() => {
    fetch2FAStatus();
  }, []);

  const fetch2FAStatus = async () => {
    try {
      const response = await axios.get("/api/auth/2fa/status");
      setTwoFaStatus(response.data);
    } catch (err) {
      console.error("Failed to fetch 2FA status:", err);
    }
  };

  // Step 1: Initiate 2FA setup
  const handleInitiateSetup = async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await axios.post("/api/auth/2fa/setup");

      setSecret(response.data.secret);
      setQrCode(response.data.qr_code);
      setBackupCodesGenerated(response.data.backup_codes);
      setStep(2);
      setSuccess("Setup initiated. Please scan the QR code.");
    } catch (err) {
      setError(
        err.response?.data?.detail || "Failed to initiate 2FA setup"
      );
    } finally {
      setLoading(false);
    }
  };

  // Step 2: Confirm TOTP
  const handleConfirmTotp = async () => {
    if (!totpInput || totpInput.length < 6) {
      setError("Please enter a valid 6-digit code");
      return;
    }

    setVerifying(true);
    setError(null);

    try {
      const response = await axios.post("/api/auth/2fa/confirm", {
        token: totpInput,
      });

      setDisplayBackupCodes(response.data.backup_codes);
      setStep(3);
      setSuccess("TOTP verified! Save your backup codes.");
    } catch (err) {
      setError(
        err.response?.data?.detail || "Invalid TOTP code. Please try again."
      );
    } finally {
      setVerifying(false);
    }
  };

  // Step 3: Complete setup
  const handleCompleteSetup = async () => {
    setSuccess("2FA enabled successfully!");
    setTimeout(() => {
      setStep(1);
      setSecret("");
      setQrCode("");
      setTotpInput("");
      setDisplayBackupCodes([]);
      setBackupCodesGenerated([]);
      fetch2FAStatus();
      onClose();
    }, 2000);
  };

  // Disable 2FA
  const handleDisable2FA = async () => {
    if (!disablePassword) {
      setError("Please enter your password");
      return;
    }

    setLoading(true);
    setError(null);

    try {
      await axios.post("/api/auth/2fa/disable", {
        password: disablePassword,
      });

      setSuccess("2FA disabled successfully");
      setShowDisableModal(false);
      setDisablePassword("");
      fetch2FAStatus();
    } catch (err) {
      setError(
        err.response?.data?.detail || "Failed to disable 2FA"
      );
    } finally {
      setLoading(false);
    }
  };

  // Regenerate backup codes
  const handleRegenerateBackupCodes = async () => {
    if (!regenerateTotpInput) {
      setError("Please enter your TOTP code");
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await axios.post("/api/auth/2fa/regenerate-codes", {
        token: regenerateTotpInput,
      });

      setDisplayBackupCodes(response.data.backup_codes);
      setShowRegenerateModal(false);
      setRegenerateTotpInput("");
      setSuccess("Backup codes regenerated successfully!");
      fetch2FAStatus();
    } catch (err) {
      setError(
        err.response?.data?.detail || "Failed to regenerate backup codes"
      );
    } finally {
      setLoading(false);
    }
  };

  // Copy to clipboard
  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    setSuccess("Copied to clipboard!");
    setTimeout(() => setSuccess(null), 2000);
  };

  // Download backup codes
  const downloadBackupCodes = () => {
    const content = `${t("twoFactorAuth.backupCodes")}\n\n${displayBackupCodes.join("\n")}\n\nGenerated: ${new Date().toISOString()}`;
    const element = document.createElement("a");
    element.setAttribute("href", "data:text/plain;charset=utf-8," + encodeURIComponent(content));
    element.setAttribute("download", "traceo-backup-codes.txt");
    element.style.display = "none";
    document.body.appendChild(element);
    element.click();
    document.body.removeChild(element);
  };

  // Print backup codes
  const printBackupCodes = () => {
    const printWindow = window.open("", "", "height=400,width=600");
    printWindow.document.write(
      `<pre>${t("twoFactorAuth.backupCodes")}\n\n${displayBackupCodes.join("\n")}</pre>`
    );
    printWindow.document.close();
    printWindow.print();
  };

  return (
    <div className="two-factor-container">
      {/* Status Overview */}
      {!showStatusModal && step === 1 && !twoFaStatus?.is_enabled && (
        <div className="twofa-card">
          <h2>{t("twoFactorAuth.setupTitle")}</h2>
          <p className="description">{t("twoFactorAuth.setupDescription")}</p>
          <button
            className="btn btn-primary"
            onClick={handleInitiateSetup}
            disabled={loading}
          >
            {loading ? t("common.loading") : t("twoFactorAuth.setup")}
          </button>
        </div>
      )}

      {/* Step 1: QR Code */}
      {step === 1 && qrCode && (
        <div className="twofa-card">
          <h3>{t("twoFactorAuth.step1")}</h3>
          <p>{t("twoFactorAuth.step1Description")}</p>

          <div className="qr-code-container">
            <img
              src={`data:image/png;base64,${qrCode}`}
              alt="TOTP QR Code"
              className="qr-code"
            />
          </div>

          <div className="secret-section">
            <label>{t("twoFactorAuth.orEnterManually")}</label>
            <div className="secret-display">
              <code>{secret}</code>
              <button
                className="btn-copy"
                onClick={() => copyToClipboard(secret)}
                title="Copy secret"
              >
                📋
              </button>
            </div>
          </div>

          <p className="hint">
            {t("twoFactorAuth.authenticatorApps")}:
            <br />
            Google Authenticator, Authy, Microsoft Authenticator
          </p>

          <button
            className="btn btn-primary"
            onClick={() => setStep(2)}
          >
            {t("common.send")} →
          </button>
        </div>
      )}

      {/* Step 2: Verify TOTP */}
      {step === 2 && (
        <div className="twofa-card">
          <h3>{t("twoFactorAuth.step2")}</h3>
          <p>{t("twoFactorAuth.step2Description")}</p>

          <div className="form-group">
            <label>{t("twoFactorAuth.verificationCode")}</label>
            <input
              type="text"
              maxLength="6"
              placeholder="000000"
              value={totpInput}
              onChange={(e) => setTotpInput(e.target.value.replace(/\D/g, ""))}
              className="input"
            />
          </div>

          {error && <div className="alert alert-error">{error}</div>}

          <button
            className="btn btn-primary"
            onClick={handleConfirmTotp}
            disabled={verifying || totpInput.length < 6}
          >
            {verifying ? t("twoFactorAuth.verifyingCode") : t("common.send")}
          </button>
        </div>
      )}

      {/* Step 3: Backup Codes */}
      {step === 3 && displayBackupCodes.length > 0 && (
        <div className="twofa-card">
          <h3>{t("twoFactorAuth.step3")}</h3>
          <p>{t("twoFactorAuth.step3Description")}</p>

          <div className="alert alert-warning">
            {t("twoFactorAuth.backupCodesWarning")}
          </div>

          <div className="backup-codes-container">
            <div className="backup-codes-grid">
              {displayBackupCodes.map((code, index) => (
                <div key={index} className="backup-code">
                  <code>{code}</code>
                </div>
              ))}
            </div>
          </div>

          <div className="backup-actions">
            <button
              className="btn btn-secondary"
              onClick={() => copyToClipboard(displayBackupCodes.join("\n"))}
            >
              📋 {t("twoFactorAuth.backupCodes")}
            </button>
            <button
              className="btn btn-secondary"
              onClick={downloadBackupCodes}
            >
              ⬇️ {t("twoFactorAuth.downloadCodes")}
            </button>
            <button
              className="btn btn-secondary"
              onClick={printBackupCodes}
            >
              🖨️ {t("twoFactorAuth.printCodes")}
            </button>
          </div>

          {success && <div className="alert alert-success">{success}</div>}

          <button
            className="btn btn-primary"
            onClick={handleCompleteSetup}
          >
            {t("twoFactorAuth.confirmSetup")}
          </button>
        </div>
      )}

      {/* 2FA Status */}
      {twoFaStatus && (
        <div className="twofa-status-card">
          <h3>{t("twoFactorAuth.title")}</h3>

          <div className="status-info">
            <div className="status-item">
              <span className="label">{t("twoFactorAuth.status")}:</span>
              <span className={`status ${twoFaStatus.is_enabled ? "enabled" : "disabled"}`}>
                {twoFaStatus.is_enabled
                  ? t("twoFactorAuth.enabled")
                  : t("twoFactorAuth.disabled")}
              </span>
            </div>

            {twoFaStatus.is_enabled && (
              <>
                <div className="status-item">
                  <span className="label">{t("twoFactorAuth.unusedBackupCodes")}:</span>
                  <span className="value">{twoFaStatus.unused_backup_codes}</span>
                </div>

                <div className="status-item">
                  <span className="label">{t("twoFactorAuth.lastUpdated")}:</span>
                  <span className="value">
                    {twoFaStatus.last_updated
                      ? new Date(twoFaStatus.last_updated).toLocaleDateString()
                      : t("twoFactorAuth.never")}
                  </span>
                </div>
              </>
            )}
          </div>

          {twoFaStatus.is_enabled && (
            <div className="status-actions">
              <button
                className="btn btn-secondary"
                onClick={() => setShowRegenerateModal(true)}
              >
                🔄 {t("twoFactorAuth.regenerateCodes")}
              </button>
              <button
                className="btn btn-danger"
                onClick={() => setShowDisableModal(true)}
              >
                ✕ {t("twoFactorAuth.disable")}
              </button>
            </div>
          )}
        </div>
      )}

      {/* Disable 2FA Modal */}
      {showDisableModal && (
        <div className="modal-overlay">
          <div className="modal-content">
            <h3>{t("twoFactorAuth.disableConfirm")}</h3>
            <p>{t("twoFactorAuth.disableWarning")}</p>

            <div className="form-group">
              <label>{t("twoFactorAuth.disablePassword")}</label>
              <input
                type="password"
                value={disablePassword}
                onChange={(e) => setDisablePassword(e.target.value)}
                className="input"
                placeholder="Enter your password"
              />
            </div>

            {error && <div className="alert alert-error">{error}</div>}

            <div className="modal-actions">
              <button
                className="btn btn-primary"
                onClick={handleDisable2FA}
                disabled={loading || !disablePassword}
              >
                {loading ? t("twoFactorAuth.disabling") : t("twoFactorAuth.disable")}
              </button>
              <button
                className="btn btn-secondary"
                onClick={() => {
                  setShowDisableModal(false);
                  setDisablePassword("");
                  setError(null);
                }}
              >
                {t("common.cancel")}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Regenerate Codes Modal */}
      {showRegenerateModal && (
        <div className="modal-overlay">
          <div className="modal-content">
            <h3>{t("twoFactorAuth.regenerateTitle")}</h3>
            <p>{t("twoFactorAuth.regenerateDescription")}</p>

            <div className="alert alert-warning">
              {t("twoFactorAuth.regenerateWarning")}
            </div>

            <div className="form-group">
              <label>{t("twoFactorAuth.enterTotpToRegenerate")}</label>
              <input
                type="text"
                maxLength="6"
                placeholder="000000"
                value={regenerateTotpInput}
                onChange={(e) => setRegenerateTotpInput(e.target.value.replace(/\D/g, ""))}
                className="input"
              />
            </div>

            {error && <div className="alert alert-error">{error}</div>}

            <div className="modal-actions">
              <button
                className="btn btn-primary"
                onClick={handleRegenerateBackupCodes}
                disabled={loading || regenerateTotpInput.length < 6}
              >
                {loading ? t("twoFactorAuth.regenerating") : t("twoFactorAuth.regenerateCodes")}
              </button>
              <button
                className="btn btn-secondary"
                onClick={() => {
                  setShowRegenerateModal(false);
                  setRegenerateTotpInput("");
                  setError(null);
                }}
              >
                {t("common.cancel")}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Display new codes after regeneration */}
      {displayBackupCodes.length > 0 && showRegenerateModal && (
        <div className="new-codes-display">
          <h4>{t("twoFactorAuth.backupCodes")}</h4>
          <div className="backup-codes-grid">
            {displayBackupCodes.map((code, index) => (
              <div key={index} className="backup-code">
                <code>{code}</code>
              </div>
            ))}
          </div>

          <div className="backup-actions">
            <button
              className="btn btn-secondary"
              onClick={() => copyToClipboard(displayBackupCodes.join("\n"))}
            >
              📋 Copy
            </button>
            <button className="btn btn-secondary" onClick={downloadBackupCodes}>
              ⬇️ Download
            </button>
            <button className="btn btn-secondary" onClick={printBackupCodes}>
              🖨️ Print
            </button>
          </div>
        </div>
      )}

      {/* Close button */}
      <button
        className="btn-close"
        onClick={onClose}
        title="Close"
      >
        ✕
      </button>
    </div>
  );
};

export default TwoFactorSetup;
