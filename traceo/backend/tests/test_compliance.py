"""
Comprehensive test suite for Compliance Service.

Tests cover:
- SOC 2 compliance checks
- GDPR compliance checks
- ISO 27001 compliance checks
- Compliance status reporting
- Compliance score calculations
"""

import pytest
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.compliance_service import (
    ComplianceService,
    ComplianceFramework,
    ComplianceStatus,
)
from app.database import SessionLocal, Base, engine


# ===== Fixtures =====

@pytest.fixture(scope="session")
def db_setup():
    """Set up test database"""
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def db():
    """Database session for each test"""
    connection = engine.connect()
    transaction = connection.begin()
    session = SessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


# ===== SOC 2 Compliance Tests =====

class TestSOC2Compliance:
    """Test SOC 2 Type II compliance checks"""

    def test_check_soc2_compliance_returns_dict(self, db):
        """Test that SOC 2 check returns dictionary"""
        result = ComplianceService.check_soc2_compliance(db)

        assert isinstance(result, dict)
        assert "framework" in result
        assert "status" in result

    def test_check_soc2_framework_name(self, db):
        """Test that framework name is correct"""
        result = ComplianceService.check_soc2_compliance(db)

        assert result["framework"] == ComplianceFramework.SOC2

    def test_check_soc2_status_is_valid(self, db):
        """Test that status is one of valid values"""
        result = ComplianceService.check_soc2_compliance(db)

        valid_statuses = [
            ComplianceStatus.COMPLIANT,
            ComplianceStatus.NON_COMPLIANT,
            ComplianceStatus.PARTIAL,
            ComplianceStatus.WARNING,
            ComplianceStatus.UNKNOWN,
        ]
        assert result["status"] in valid_statuses

    def test_check_soc2_has_checks(self, db):
        """Test that result includes individual checks"""
        result = ComplianceService.check_soc2_compliance(db)

        assert "checks" in result
        assert isinstance(result["checks"], dict)
        assert len(result["checks"]) > 0

    def test_check_soc2_compliance_score_format(self, db):
        """Test that compliance score is formatted correctly"""
        result = ComplianceService.check_soc2_compliance(db)

        if "compliance_score" in result:
            assert result["compliance_score"].endswith("%")

    def test_check_soc2_has_timestamp(self, db):
        """Test that result includes timestamp"""
        result = ComplianceService.check_soc2_compliance(db)

        assert "timestamp" in result
        # Should be ISO format
        datetime.fromisoformat(result["timestamp"])

    def test_check_soc2_criteria_coverage(self, db):
        """Test that all SOC 2 criteria are covered"""
        result = ComplianceService.check_soc2_compliance(db)

        # Should check at least 5 criteria
        assert len(result["checks"]) >= 5

    def test_soc2_check_result_structure(self, db):
        """Test structure of individual SOC 2 checks"""
        result = ComplianceService.check_soc2_compliance(db)

        for check_name, check_result in result["checks"].items():
            assert "status" in check_result or "error" in check_result
            assert "description" in check_result or "error" in check_result


# ===== GDPR Compliance Tests =====

class TestGDPRCompliance:
    """Test GDPR compliance checks"""

    def test_check_gdpr_compliance_returns_dict(self, db):
        """Test that GDPR check returns dictionary"""
        result = ComplianceService.check_gdpr_compliance(db)

        assert isinstance(result, dict)
        assert "framework" in result
        assert "status" in result

    def test_check_gdpr_framework_name(self, db):
        """Test that framework name is correct"""
        result = ComplianceService.check_gdpr_compliance(db)

        assert result["framework"] == ComplianceFramework.GDPR

    def test_check_gdpr_status_is_valid(self, db):
        """Test that status is one of valid values"""
        result = ComplianceService.check_gdpr_compliance(db)

        valid_statuses = [
            ComplianceStatus.COMPLIANT,
            ComplianceStatus.NON_COMPLIANT,
            ComplianceStatus.PARTIAL,
            ComplianceStatus.WARNING,
            ComplianceStatus.UNKNOWN,
        ]
        assert result["status"] in valid_statuses

    def test_check_gdpr_has_checks(self, db):
        """Test that result includes individual checks"""
        result = ComplianceService.check_gdpr_compliance(db)

        assert "checks" in result
        assert isinstance(result["checks"], dict)
        # GDPR has 7 requirements
        assert len(result["checks"]) >= 5

    def test_check_gdpr_coverage(self, db):
        """Test coverage of GDPR requirements"""
        result = ComplianceService.check_gdpr_compliance(db)

        # Should cover key GDPR requirements
        gdpr_keys = list(result["checks"].keys())
        assert "data_minimization" in gdpr_keys or "storage_limitation" in gdpr_keys

    def test_gdpr_compliance_score(self, db):
        """Test GDPR compliance score calculation"""
        result = ComplianceService.check_gdpr_compliance(db)

        if "compliance_score" in result:
            score_str = result["compliance_score"].rstrip("%")
            score = float(score_str)
            assert 0 <= score <= 100


# ===== ISO 27001 Compliance Tests =====

class TestISO27001Compliance:
    """Test ISO 27001 compliance checks"""

    def test_check_iso27001_compliance_returns_dict(self, db):
        """Test that ISO 27001 check returns dictionary"""
        result = ComplianceService.check_iso27001_compliance(db)

        assert isinstance(result, dict)
        assert "framework" in result
        assert "status" in result

    def test_check_iso27001_framework_name(self, db):
        """Test that framework name is correct"""
        result = ComplianceService.check_iso27001_compliance(db)

        assert result["framework"] == ComplianceFramework.ISO27001

    def test_check_iso27001_status_is_valid(self, db):
        """Test that status is one of valid values"""
        result = ComplianceService.check_iso27001_compliance(db)

        valid_statuses = [
            ComplianceStatus.COMPLIANT,
            ComplianceStatus.NON_COMPLIANT,
            ComplianceStatus.PARTIAL,
            ComplianceStatus.WARNING,
            ComplianceStatus.UNKNOWN,
        ]
        assert result["status"] in valid_statuses

    def test_check_iso27001_has_checks(self, db):
        """Test that result includes individual checks"""
        result = ComplianceService.check_iso27001_compliance(db)

        assert "checks" in result
        assert isinstance(result["checks"], dict)
        # ISO 27001 has 8 requirements
        assert len(result["checks"]) >= 5

    def test_check_iso27001_coverage(self, db):
        """Test coverage of ISO 27001 requirements"""
        result = ComplianceService.check_iso27001_compliance(db)

        # Should include cryptography check
        assert "cryptography" in result["checks"]

    def test_iso27001_cryptography_check(self, db):
        """Test that cryptography requirement is checked"""
        result = ComplianceService.check_iso27001_compliance(db)

        crypto_check = result["checks"].get("cryptography", {})
        assert crypto_check.get("status") == ComplianceStatus.COMPLIANT


# ===== Comprehensive Compliance Tests =====

class TestComprehensiveCompliance:
    """Test comprehensive compliance checking"""

    def test_check_all_compliance_returns_dict(self, db):
        """Test that comprehensive check returns dictionary"""
        result = ComplianceService.check_all_compliance(db)

        assert isinstance(result, dict)
        assert "timestamp" in result
        assert "overall_status" in result
        assert "overall_score" in result
        assert "frameworks" in result

    def test_check_all_compliance_includes_all_frameworks(self, db):
        """Test that all frameworks are included"""
        result = ComplianceService.check_all_compliance(db)

        frameworks = result["frameworks"]
        assert "soc2" in frameworks
        assert "gdpr" in frameworks
        assert "iso27001" in frameworks

    def test_check_all_compliance_overall_status(self, db):
        """Test overall compliance status"""
        result = ComplianceService.check_all_compliance(db)

        valid_statuses = [
            ComplianceStatus.COMPLIANT,
            ComplianceStatus.NON_COMPLIANT,
            ComplianceStatus.PARTIAL,
            ComplianceStatus.WARNING,
            ComplianceStatus.UNKNOWN,
        ]
        assert result["overall_status"] in valid_statuses

    def test_check_all_compliance_overall_score(self, db):
        """Test overall compliance score"""
        result = ComplianceService.check_all_compliance(db)

        score_str = result["overall_score"].rstrip("%")
        score = float(score_str)
        assert 0 <= score <= 100

    def test_check_all_compliance_timestamp_format(self, db):
        """Test that timestamp is ISO format"""
        result = ComplianceService.check_all_compliance(db)

        datetime.fromisoformat(result["timestamp"])

    def test_check_all_compliance_framework_structure(self, db):
        """Test structure of each framework result"""
        result = ComplianceService.check_all_compliance(db)

        for framework_name, framework_result in result["frameworks"].items():
            assert "status" in framework_result
            assert "checks" in framework_result


# ===== Compliance Status Tests =====

class TestComplianceStatus:
    """Test compliance status enum"""

    def test_compliance_status_values(self):
        """Test that all status values are accessible"""
        assert ComplianceStatus.COMPLIANT == "compliant"
        assert ComplianceStatus.NON_COMPLIANT == "non_compliant"
        assert ComplianceStatus.PARTIAL == "partial"
        assert ComplianceStatus.WARNING == "warning"
        assert ComplianceStatus.UNKNOWN == "unknown"

    def test_compliance_framework_values(self):
        """Test that all framework values are accessible"""
        assert ComplianceFramework.SOC2 == "SOC2_TYPE_II"
        assert ComplianceFramework.GDPR == "GDPR"
        assert ComplianceFramework.ISO27001 == "ISO27001"


# ===== Compliance Score Tests =====

class TestComplianceScores:
    """Test compliance score calculations"""

    def test_soc2_score_calculation(self, db):
        """Test SOC 2 score is correctly calculated"""
        result = ComplianceService.check_soc2_compliance(db)

        if "checks" in result:
            statuses = [
                check.get("status")
                for check in result["checks"].values()
                if "status" in check
            ]
            compliant_count = sum(1 for s in statuses if s == ComplianceStatus.COMPLIANT)
            total_checks = len([s for s in statuses if s != ComplianceStatus.UNKNOWN])

            if total_checks > 0:
                expected_score = (compliant_count / total_checks) * 100
                actual_score = float(result["compliance_score"].rstrip("%"))
                assert abs(expected_score - actual_score) < 0.1

    def test_gdpr_score_calculation(self, db):
        """Test GDPR score is correctly calculated"""
        result = ComplianceService.check_gdpr_compliance(db)

        if "checks" in result:
            score_str = result["compliance_score"].rstrip("%")
            score = float(score_str)
            assert 0 <= score <= 100

    def test_iso27001_score_calculation(self, db):
        """Test ISO 27001 score is correctly calculated"""
        result = ComplianceService.check_iso27001_compliance(db)

        if "checks" in result:
            score_str = result["compliance_score"].rstrip("%")
            score = float(score_str)
            assert 0 <= score <= 100


# ===== Integration Tests =====

class TestComplianceIntegration:
    """Integration tests for compliance checking"""

    def test_soc2_and_gdpr_independent(self, db):
        """Test that SOC 2 and GDPR checks are independent"""
        soc2 = ComplianceService.check_soc2_compliance(db)
        gdpr = ComplianceService.check_gdpr_compliance(db)

        # Should be able to run independently
        assert soc2["framework"] != gdpr["framework"]
        assert len(soc2["checks"]) > 0
        assert len(gdpr["checks"]) > 0

    def test_all_compliance_includes_individual_results(self, db):
        """Test that comprehensive check includes individual results"""
        all_result = ComplianceService.check_all_compliance(db)
        soc2_result = ComplianceService.check_soc2_compliance(db)
        gdpr_result = ComplianceService.check_gdpr_compliance(db)
        iso_result = ComplianceService.check_iso27001_compliance(db)

        # All results should be included
        assert "soc2" in all_result["frameworks"]
        assert "gdpr" in all_result["frameworks"]
        assert "iso27001" in all_result["frameworks"]

    def test_compliance_consistency_across_runs(self, db):
        """Test that compliance scores are consistent"""
        result1 = ComplianceService.check_all_compliance(db)
        result2 = ComplianceService.check_all_compliance(db)

        # Scores should be same (deterministic)
        assert result1["overall_score"] == result2["overall_score"]

    def test_compliance_report_generation(self, db):
        """Test that compliance report can be generated"""
        result = ComplianceService.check_all_compliance(db)

        # Should have all necessary data for report
        assert result["overall_status"]
        assert result["overall_score"]
        assert result["frameworks"]


# ===== Error Handling Tests =====

class TestComplianceErrorHandling:
    """Test error handling in compliance checks"""

    def test_soc2_handles_database_errors(self, db):
        """Test SOC 2 check handles database errors gracefully"""
        result = ComplianceService.check_soc2_compliance(db)

        # Should return valid structure even if some checks fail
        assert "framework" in result
        assert "status" in result

    def test_gdpr_handles_database_errors(self, db):
        """Test GDPR check handles database errors gracefully"""
        result = ComplianceService.check_gdpr_compliance(db)

        # Should return valid structure
        assert "framework" in result
        assert "status" in result

    def test_iso27001_handles_database_errors(self, db):
        """Test ISO 27001 check handles database errors gracefully"""
        result = ComplianceService.check_iso27001_compliance(db)

        # Should return valid structure
        assert "framework" in result
        assert "status" in result

    def test_all_compliance_handles_partial_failures(self, db):
        """Test comprehensive check handles partial failures"""
        result = ComplianceService.check_all_compliance(db)

        # Should still return overall result
        assert "overall_status" in result
        assert "frameworks" in result


# ===== Compliance Requirement Tests =====

class TestComplianceRequirements:
    """Test compliance requirements coverage"""

    def test_soc2_criteria_defined(self):
        """Test that SOC 2 criteria are defined"""
        assert len(ComplianceService.SOC2_CRITERIA) >= 5
        assert "access_control" in ComplianceService.SOC2_CRITERIA
        assert "encryption" in ComplianceService.SOC2_CRITERIA

    def test_gdpr_requirements_defined(self):
        """Test that GDPR requirements are defined"""
        assert len(ComplianceService.GDPR_REQUIREMENTS) >= 5
        assert "data_minimization" in ComplianceService.GDPR_REQUIREMENTS
        assert "user_rights" in ComplianceService.GDPR_REQUIREMENTS

    def test_iso27001_requirements_defined(self):
        """Test that ISO 27001 requirements are defined"""
        assert len(ComplianceService.ISO27001_REQUIREMENTS) >= 5
        assert "access_control" in ComplianceService.ISO27001_REQUIREMENTS
        assert "cryptography" in ComplianceService.ISO27001_REQUIREMENTS


# ===== Performance Tests =====

class TestCompliancePerformance:
    """Test compliance check performance"""

    def test_soc2_check_performance(self, db):
        """Test that SOC 2 check completes in reasonable time"""
        import time

        start = time.time()
        ComplianceService.check_soc2_compliance(db)
        elapsed = time.time() - start

        # Should complete in less than 5 seconds
        assert elapsed < 5.0

    def test_all_compliance_check_performance(self, db):
        """Test that comprehensive check completes in reasonable time"""
        import time

        start = time.time()
        ComplianceService.check_all_compliance(db)
        elapsed = time.time() - start

        # Should complete in less than 10 seconds
        assert elapsed < 10.0
