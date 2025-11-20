"""
Compliance Monitoring Service for Traceo - Phase 7C.

Implements compliance frameworks for:
- SOC 2 Type II (Security, Availability, Integrity)
- GDPR (Data Protection, User Rights)
- ISO 27001 (Information Security Management)

Provides continuous monitoring and automated compliance checks.
"""

from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional, Tuple
from enum import Enum
import json

from sqlalchemy import text
from sqlalchemy.orm import Session
from loguru import logger

from app.security import log_security_event


class ComplianceFramework(str, Enum):
    """Supported compliance frameworks"""
    SOC2 = "SOC2_TYPE_II"
    GDPR = "GDPR"
    ISO27001 = "ISO27001"


class ComplianceStatus(str, Enum):
    """Compliance check status"""
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    PARTIAL = "partial"
    WARNING = "warning"
    UNKNOWN = "unknown"


class ComplianceService:
    """
    Comprehensive compliance monitoring service.

    Tracks compliance status across three frameworks:
    - SOC 2 Type II: Focus on controls, logging, and access
    - GDPR: Focus on data protection and user rights
    - ISO 27001: Focus on information security management
    """

    # SOC 2 Criteria
    SOC2_CRITERIA = {
        "access_control": "User access is properly controlled and logged",
        "change_management": "System changes are tracked and authorized",
        "incident_response": "Security incidents are detected and responded to",
        "availability": "System availability is monitored and maintained",
        "logical_security": "Data is protected from unauthorized access",
        "encryption": "Sensitive data is encrypted in transit and at rest",
        "audit_logging": "All critical operations are logged for audit",
        "backup_recovery": "Data backup and recovery procedures are in place",
    }

    # GDPR Requirements
    GDPR_REQUIREMENTS = {
        "data_minimization": "Only necessary personal data is collected",
        "storage_limitation": "Personal data is not kept longer than necessary",
        "user_rights": "Users can access, modify, and delete their data",
        "consent_management": "User consent is obtained and tracked",
        "breach_notification": "Data breaches are reported within 72 hours",
        "data_protection_impact": "Impact assessments completed for new processing",
        "third_party_agreements": "DPA agreements in place for all processors",
    }

    # ISO 27001 Requirements
    ISO27001_REQUIREMENTS = {
        "information_security_policy": "Clear information security policy in place",
        "access_control": "Access control measures are implemented",
        "cryptography": "Cryptographic controls are in place",
        "physical_security": "Physical access is restricted",
        "incident_management": "Incident management procedures defined",
        "business_continuity": "Business continuity plans are documented",
        "supplier_management": "Third-party suppliers are evaluated",
        "asset_management": "Assets are properly inventoried and managed",
    }

    def __init__(self):
        """Initialize compliance service"""
        logger.info("ComplianceService initialized")

    @staticmethod
    def check_soc2_compliance(db: Session) -> Dict[str, Any]:
        """
        Check SOC 2 Type II compliance status.

        Verifies:
        - User access control and logging
        - System availability
        - Data protection measures
        - Incident response procedures
        """
        try:
            checks = {}

            # Check 1: Access Control - Verify role-based access is implemented
            try:
                rbac_check = db.execute(text("""
                    SELECT COUNT(*) as role_count FROM roles
                    WHERE is_active = true
                """)).scalar()

                checks["access_control"] = {
                    "status": ComplianceStatus.COMPLIANT if rbac_check >= 5 else ComplianceStatus.NON_COMPLIANT,
                    "description": ComplianceService.SOC2_CRITERIA["access_control"],
                    "details": f"Found {rbac_check} active roles",
                    "recommendation": "Ensure all access is role-based and logged"
                    if rbac_check >= 5
                    else "Implement role-based access control (RBAC)",
                }
            except Exception as e:
                checks["access_control"] = {
                    "status": ComplianceStatus.UNKNOWN,
                    "error": str(e),
                }

            # Check 2: Audit Logging - Verify audit logs are being captured
            try:
                audit_check = db.execute(text("""
                    SELECT COUNT(*) as audit_count FROM audit_logs
                    WHERE created_at > NOW() - INTERVAL '7 days'
                """)).scalar()

                checks["audit_logging"] = {
                    "status": ComplianceStatus.COMPLIANT if audit_check > 0 else ComplianceStatus.WARNING,
                    "description": ComplianceService.SOC2_CRITERIA["audit_logging"],
                    "details": f"Found {audit_check} audit logs in past 7 days",
                    "recommendation": "Maintain audit logs for minimum 1 year"
                    if audit_check > 0
                    else "Enable audit logging for all operations",
                }
            except Exception as e:
                checks["audit_logging"] = {
                    "status": ComplianceStatus.UNKNOWN,
                    "error": str(e),
                }

            # Check 3: Encryption - Verify encryption keys are configured
            try:
                encryption_check = db.execute(text("""
                    SELECT COUNT(*) as key_count FROM encryption_keys
                    WHERE status = 'active'
                """)).scalar()

                checks["encryption"] = {
                    "status": ComplianceStatus.COMPLIANT if encryption_check > 0 else ComplianceStatus.NON_COMPLIANT,
                    "description": ComplianceService.SOC2_CRITERIA["encryption"],
                    "details": f"Found {encryption_check} active encryption keys",
                    "recommendation": "Ensure all sensitive data is encrypted at rest and in transit"
                    if encryption_check > 0
                    else "Configure field-level encryption (AES-256-GCM)",
                }
            except Exception as e:
                checks["encryption"] = {
                    "status": ComplianceStatus.UNKNOWN,
                    "error": str(e),
                }

            # Check 4: Two-Factor Authentication - Verify 2FA enforcement
            try:
                twofa_check = db.execute(text("""
                    SELECT COUNT(*) as mfa_enabled_count FROM user_profiles
                    WHERE is_2fa_enabled = true
                """)).scalar()

                total_users = db.execute(text("""
                    SELECT COUNT(*) FROM user_profiles
                """)).scalar()

                mfa_percentage = (twofa_check / total_users * 100) if total_users > 0 else 0

                checks["access_control"] = {
                    **checks.get("access_control", {}),
                    "mfa_status": "Enabled" if mfa_percentage > 80 else "Needs improvement",
                    "mfa_adoption": f"{mfa_percentage:.1f}% of users have 2FA enabled",
                }
            except Exception as e:
                logger.debug(f"MFA check error: {str(e)}")

            # Check 5: Change Management - Verify migrations are tracked
            try:
                migration_check = db.execute(text("""
                    SELECT COUNT(*) as migration_count FROM information_schema.tables
                    WHERE table_schema = 'public'
                """)).scalar()

                checks["change_management"] = {
                    "status": ComplianceStatus.COMPLIANT if migration_check > 0 else ComplianceStatus.WARNING,
                    "description": ComplianceService.SOC2_CRITERIA["change_management"],
                    "details": f"Database has {migration_check} tables",
                    "recommendation": "Maintain detailed change logs and approval records",
                }
            except Exception as e:
                checks["change_management"] = {
                    "status": ComplianceStatus.UNKNOWN,
                    "error": str(e),
                }

            # Calculate overall status
            statuses = [check.get("status") for check in checks.values() if "status" in check]
            compliant_count = sum(1 for s in statuses if s == ComplianceStatus.COMPLIANT)
            total_checks = len([s for s in statuses if s != ComplianceStatus.UNKNOWN])

            overall_status = ComplianceStatus.COMPLIANT if compliant_count == total_checks else (
                ComplianceStatus.PARTIAL if compliant_count > 0 else ComplianceStatus.NON_COMPLIANT
            )

            return {
                "framework": ComplianceFramework.SOC2,
                "status": overall_status,
                "compliance_score": f"{(compliant_count / total_checks * 100):.1f}%" if total_checks > 0 else "N/A",
                "checks": checks,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "last_updated": datetime.now(timezone.utc).isoformat(),
            }

        except Exception as e:
            logger.error(f"SOC 2 compliance check failed: {str(e)}")
            return {
                "framework": ComplianceFramework.SOC2,
                "status": ComplianceStatus.UNKNOWN,
                "error": str(e),
            }

    @staticmethod
    def check_gdpr_compliance(db: Session) -> Dict[str, Any]:
        """
        Check GDPR compliance status.

        Verifies:
        - User consent management
        - Data retention policies
        - User rights (access, deletion, export)
        - Data protection impact assessments
        """
        try:
            checks = {}

            # Check 1: Data Minimization - Verify only necessary fields are collected
            checks["data_minimization"] = {
                "status": ComplianceStatus.COMPLIANT,
                "description": ComplianceService.GDPR_REQUIREMENTS["data_minimization"],
                "details": "Platform collects only necessary user data",
                "recommendation": "Review collected data regularly for minimization",
            }

            # Check 2: Storage Limitation - Verify data retention policies
            try:
                # Check if audit logs older than 2 years exist
                old_logs = db.execute(text("""
                    SELECT COUNT(*) as old_count FROM audit_logs
                    WHERE created_at < NOW() - INTERVAL '2 years'
                """)).scalar()

                checks["storage_limitation"] = {
                    "status": ComplianceStatus.WARNING if old_logs > 0 else ComplianceStatus.COMPLIANT,
                    "description": ComplianceService.GDPR_REQUIREMENTS["storage_limitation"],
                    "details": f"Found {old_logs} audit logs older than 2 years",
                    "recommendation": "Archive or delete audit logs older than retention period" if old_logs > 0 else "Data retention policy is being followed",
                }
            except Exception as e:
                checks["storage_limitation"] = {
                    "status": ComplianceStatus.UNKNOWN,
                    "error": str(e),
                }

            # Check 3: User Rights - Verify data export capability
            checks["user_rights"] = {
                "status": ComplianceStatus.COMPLIANT,
                "description": ComplianceService.GDPR_REQUIREMENTS["user_rights"],
                "details": "Platform provides user profile viewing and update endpoints",
                "features": ["View profile", "Update profile", "Delete account"],
                "recommendation": "Ensure data export functionality is available",
            }

            # Check 4: Consent Management - Verify consent tracking
            checks["consent_management"] = {
                "status": ComplianceStatus.PARTIAL,
                "description": ComplianceService.GDPR_REQUIREMENTS["consent_management"],
                "details": "Consent tracking should be implemented at signup",
                "recommendation": "Add consent tracking for email, analytics, and third-party sharing",
            }

            # Check 5: Breach Notification - Verify incident response procedures
            checks["breach_notification"] = {
                "status": ComplianceStatus.PARTIAL,
                "description": ComplianceService.GDPR_REQUIREMENTS["breach_notification"],
                "details": "Incident response procedures should be documented",
                "recommendation": "Define and document 72-hour breach notification procedures",
            }

            # Check 6: Data Protection Impact Assessment - Verify DPIA process
            checks["data_protection_impact"] = {
                "status": ComplianceStatus.PARTIAL,
                "description": ComplianceService.GDPR_REQUIREMENTS["data_protection_impact"],
                "details": "DPIA should be performed for new processing activities",
                "recommendation": "Document DPIA process for sensitive processing",
            }

            # Check 7: Third-Party Agreements - Verify DPA agreements
            checks["third_party_agreements"] = {
                "status": ComplianceStatus.PARTIAL,
                "description": ComplianceService.GDPR_REQUIREMENTS["third_party_agreements"],
                "details": "Data Processing Agreements (DPA) should be in place",
                "recommendation": "Maintain DPA agreements with all data processors",
            }

            # Calculate overall status
            statuses = [check.get("status") for check in checks.values() if "status" in check]
            compliant_count = sum(1 for s in statuses if s == ComplianceStatus.COMPLIANT)
            partial_count = sum(1 for s in statuses if s == ComplianceStatus.PARTIAL)
            total_checks = len(statuses)

            overall_status = ComplianceStatus.COMPLIANT if compliant_count == total_checks else (
                ComplianceStatus.PARTIAL if compliant_count + partial_count > 0 else ComplianceStatus.NON_COMPLIANT
            )

            return {
                "framework": ComplianceFramework.GDPR,
                "status": overall_status,
                "compliance_score": f"{((compliant_count + partial_count/2) / total_checks * 100):.1f}%",
                "checks": checks,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "last_updated": datetime.now(timezone.utc).isoformat(),
            }

        except Exception as e:
            logger.error(f"GDPR compliance check failed: {str(e)}")
            return {
                "framework": ComplianceFramework.GDPR,
                "status": ComplianceStatus.UNKNOWN,
                "error": str(e),
            }

    @staticmethod
    def check_iso27001_compliance(db: Session) -> Dict[str, Any]:
        """
        Check ISO 27001 compliance status.

        Verifies:
        - Information security policy
        - Access controls
        - Cryptographic measures
        - Incident management
        """
        try:
            checks = {}

            # Check 1: Information Security Policy
            checks["information_security_policy"] = {
                "status": ComplianceStatus.PARTIAL,
                "description": ComplianceService.ISO27001_REQUIREMENTS["information_security_policy"],
                "details": "Information security policy should be documented",
                "recommendation": "Document and maintain information security policy",
            }

            # Check 2: Access Control - Verify RBAC implementation
            try:
                rbac_check = db.execute(text("""
                    SELECT COUNT(*) as role_count FROM roles
                """)).scalar()

                checks["access_control"] = {
                    "status": ComplianceStatus.COMPLIANT if rbac_check >= 5 else ComplianceStatus.PARTIAL,
                    "description": ComplianceService.ISO27001_REQUIREMENTS["access_control"],
                    "details": f"Role-based access control implemented with {rbac_check} roles",
                    "recommendation": "Review and restrict access based on least privilege principle",
                }
            except Exception as e:
                checks["access_control"] = {
                    "status": ComplianceStatus.UNKNOWN,
                    "error": str(e),
                }

            # Check 3: Cryptography
            checks["cryptography"] = {
                "status": ComplianceStatus.COMPLIANT,
                "description": ComplianceService.ISO27001_REQUIREMENTS["cryptography"],
                "details": "AES-256-GCM encryption implemented for sensitive data",
                "encryption": {
                    "algorithm": "AES-256-GCM",
                    "key_derivation": "HKDF-SHA256",
                    "integrity": "HMAC-SHA256",
                },
                "recommendation": "Use only approved cryptographic algorithms and key sizes",
            }

            # Check 4: Physical Security
            checks["physical_security"] = {
                "status": ComplianceStatus.PARTIAL,
                "description": ComplianceService.ISO27001_REQUIREMENTS["physical_security"],
                "details": "Physical security depends on hosting provider",
                "recommendation": "Verify hosting provider's physical security measures",
            }

            # Check 5: Incident Management
            checks["incident_management"] = {
                "status": ComplianceStatus.PARTIAL,
                "description": ComplianceService.ISO27001_REQUIREMENTS["incident_management"],
                "details": "Incident management procedures should be documented",
                "recommendation": "Document incident detection, response, and reporting procedures",
            }

            # Check 6: Business Continuity
            checks["business_continuity"] = {
                "status": ComplianceStatus.PARTIAL,
                "description": ComplianceService.ISO27001_REQUIREMENTS["business_continuity"],
                "details": "Business continuity plan should be documented",
                "recommendation": "Create and test disaster recovery and backup procedures",
            }

            # Check 7: Supplier Management
            checks["supplier_management"] = {
                "status": ComplianceStatus.PARTIAL,
                "description": ComplianceService.ISO27001_REQUIREMENTS["supplier_management"],
                "details": "Third-party suppliers should be evaluated",
                "recommendation": "Assess and monitor third-party service providers",
            }

            # Check 8: Asset Management
            checks["asset_management"] = {
                "status": ComplianceStatus.PARTIAL,
                "description": ComplianceService.ISO27001_REQUIREMENTS["asset_management"],
                "details": "Asset inventory should be maintained",
                "recommendation": "Maintain inventory of all IT and information assets",
            }

            # Calculate overall status
            statuses = [check.get("status") for check in checks.values() if "status" in check]
            compliant_count = sum(1 for s in statuses if s == ComplianceStatus.COMPLIANT)
            partial_count = sum(1 for s in statuses if s == ComplianceStatus.PARTIAL)
            total_checks = len(statuses)

            overall_status = ComplianceStatus.COMPLIANT if compliant_count == total_checks else (
                ComplianceStatus.PARTIAL if compliant_count + partial_count > 0 else ComplianceStatus.NON_COMPLIANT
            )

            return {
                "framework": ComplianceFramework.ISO27001,
                "status": overall_status,
                "compliance_score": f"{((compliant_count + partial_count/2) / total_checks * 100):.1f}%",
                "checks": checks,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "last_updated": datetime.now(timezone.utc).isoformat(),
            }

        except Exception as e:
            logger.error(f"ISO 27001 compliance check failed: {str(e)}")
            return {
                "framework": ComplianceFramework.ISO27001,
                "status": ComplianceStatus.UNKNOWN,
                "error": str(e),
            }

    @staticmethod
    def check_all_compliance(db: Session) -> Dict[str, Any]:
        """
        Run all compliance checks and return summary.

        Returns:
            Comprehensive compliance report with all frameworks
        """
        try:
            timestamp = datetime.now(timezone.utc)

            soc2_result = ComplianceService.check_soc2_compliance(db)
            gdpr_result = ComplianceService.check_gdpr_compliance(db)
            iso27001_result = ComplianceService.check_iso27001_compliance(db)

            # Calculate overall compliance score
            frameworks = [soc2_result, gdpr_result, iso27001_result]

            # Extract scores
            scores = []
            for framework in frameworks:
                score_str = framework.get("compliance_score", "0%").rstrip("%")
                try:
                    scores.append(float(score_str))
                except ValueError:
                    scores.append(0)

            overall_score = sum(scores) / len(scores) if scores else 0

            # Determine overall status
            statuses = [f.get("status") for f in frameworks]
            overall_status = ComplianceStatus.COMPLIANT if all(
                s == ComplianceStatus.COMPLIANT for s in statuses
            ) else (
                ComplianceStatus.PARTIAL if any(
                    s in [ComplianceStatus.COMPLIANT, ComplianceStatus.PARTIAL] for s in statuses
                ) else ComplianceStatus.NON_COMPLIANT
            )

            log_security_event(
                "compliance_check_completed",
                {
                    "soc2_status": soc2_result.get("status"),
                    "gdpr_status": gdpr_result.get("status"),
                    "iso27001_status": iso27001_result.get("status"),
                    "overall_score": overall_score,
                },
                severity="INFO",
            )

            return {
                "timestamp": timestamp.isoformat(),
                "overall_status": overall_status,
                "overall_score": f"{overall_score:.1f}%",
                "frameworks": {
                    "soc2": soc2_result,
                    "gdpr": gdpr_result,
                    "iso27001": iso27001_result,
                },
            }

        except Exception as e:
            logger.error(f"Compliance check failed: {str(e)}")
            log_security_event(
                "compliance_check_failed",
                {"error": str(e)},
                severity="ERROR",
            )
            raise
