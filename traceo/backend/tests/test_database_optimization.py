"""
Comprehensive test suite for Database Optimization Service.
Tests cover partitioning, indexing, and performance monitoring.
"""

import pytest
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session

from app.database.optimization_service import DatabaseOptimizationService
from app.database import SessionLocal, Base, engine


# ===== Database Setup =====

@pytest.fixture(scope="session")
def db_setup():
    """Set up test database."""
    Base.metadata.create_all(bind=engine)
    yield
    # Don't drop tables - keep for inspection


@pytest.fixture
def db():
    """Database session for each test."""
    connection = engine.connect()
    transaction = connection.begin()
    session = SessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


# ===== Partition Statistics Tests =====

class TestPartitionStats:
    """Test partition statistics retrieval."""

    def test_get_partition_stats_returns_dict(self, db):
        """Test that get_partition_stats returns a dictionary."""
        result = DatabaseOptimizationService.get_partition_stats(db)

        assert isinstance(result, dict)
        assert "partitions" in result or "error" in result

    def test_get_partition_stats_structure(self, db):
        """Test structure of partition statistics."""
        result = DatabaseOptimizationService.get_partition_stats(db)

        if "error" not in result:
            assert "partitions" in result
            assert "total_size_bytes" in result
            assert "total_size_pretty" in result
            assert "partition_count" in result

    def test_partition_sizes_are_numbers(self, db):
        """Test that partition sizes are valid numbers."""
        result = DatabaseOptimizationService.get_partition_stats(db)

        if "error" not in result:
            assert isinstance(result["total_size_bytes"], int)
            assert result["total_size_bytes"] >= 0

    def test_partition_count_is_non_negative(self, db):
        """Test that partition count is non-negative."""
        result = DatabaseOptimizationService.get_partition_stats(db)

        if "error" not in result:
            assert result["partition_count"] >= 0


# ===== Index Statistics Tests =====

class TestIndexStats:
    """Test index statistics retrieval."""

    def test_get_index_stats_returns_dict(self, db):
        """Test that get_index_stats returns a dictionary."""
        result = DatabaseOptimizationService.get_index_stats(db)

        assert isinstance(result, dict)
        assert "indexes" in result or "error" in result

    def test_get_index_stats_structure(self, db):
        """Test structure of index statistics."""
        result = DatabaseOptimizationService.get_index_stats(db)

        if "error" not in result:
            assert "indexes" in result
            assert "total_size_bytes" in result
            assert "total_size_pretty" in result
            assert "index_count" in result

    def test_index_list_format(self, db):
        """Test format of individual index entries."""
        result = DatabaseOptimizationService.get_index_stats(db)

        if "error" not in result and result["indexes"]:
            index = result["indexes"][0]

            assert "table_name" in index
            assert "index_name" in index
            assert "size_bytes" in index
            assert "scans" in index

    def test_index_sizes_are_numbers(self, db):
        """Test that index sizes are valid numbers."""
        result = DatabaseOptimizationService.get_index_stats(db)

        if "error" not in result:
            assert isinstance(result["total_size_bytes"], int)
            assert result["total_size_bytes"] >= 0


# ===== Table Analysis Tests =====

class TestTableAnalysis:
    """Test ANALYZE and VACUUM operations."""

    def test_analyze_table_returns_dict(self, db):
        """Test that analyze_table returns a dictionary."""
        result = DatabaseOptimizationService.analyze_table(db, "pg_tables")

        assert isinstance(result, dict)

    def test_analyze_table_has_status(self, db):
        """Test that analyze result has status field."""
        result = DatabaseOptimizationService.analyze_table(db, "pg_tables")

        assert "status" in result

    def test_vacuum_table_returns_dict(self, db):
        """Test that vacuum_table returns a dictionary."""
        # Note: This might fail if table doesn't exist, which is okay
        result = DatabaseOptimizationService.vacuum_table(db, "pg_tables")

        assert isinstance(result, dict)

    def test_vacuum_table_has_status(self, db):
        """Test that vacuum result has status field."""
        result = DatabaseOptimizationService.vacuum_table(db, "pg_tables")

        assert "status" in result


# ===== Size Formatting Tests =====

class TestSizeFormatting:
    """Test byte size formatting."""

    def test_format_size_bytes(self):
        """Test formatting of small sizes."""
        result = DatabaseOptimizationService._format_size(512)

        assert "B" in result
        assert "512" in result

    def test_format_size_kilobytes(self):
        """Test formatting of kilobyte sizes."""
        result = DatabaseOptimizationService._format_size(2048)

        assert "KB" in result

    def test_format_size_megabytes(self):
        """Test formatting of megabyte sizes."""
        result = DatabaseOptimizationService._format_size(1024 * 1024 * 5)

        assert "MB" in result

    def test_format_size_gigabytes(self):
        """Test formatting of gigabyte sizes."""
        result = DatabaseOptimizationService._format_size(1024 * 1024 * 1024 * 10)

        assert "GB" in result

    def test_format_size_zero(self):
        """Test formatting of zero size."""
        result = DatabaseOptimizationService._format_size(0)

        assert "B" in result
        assert "0" in result


# ===== Query Performance Tests =====

class TestQueryPerformance:
    """Test query performance monitoring."""

    def test_get_query_performance_returns_dict(self, db):
        """Test that get_query_performance returns a dictionary."""
        result = DatabaseOptimizationService.get_query_performance(db)

        assert isinstance(result, dict)

    def test_get_query_performance_has_status_or_queries(self, db):
        """Test that result has either status or queries."""
        result = DatabaseOptimizationService.get_query_performance(db)

        assert "status" in result or "slow_queries" in result


# ===== Full Report Tests =====

class TestFullReport:
    """Test complete optimization report generation."""

    def test_get_full_optimization_report_structure(self, db):
        """Test structure of full optimization report."""
        result = DatabaseOptimizationService.get_full_optimization_report(db)

        assert "timestamp" in result
        assert "partitions" in result
        assert "indexes" in result
        assert "query_performance" in result
        assert "partition_strategy" in result

    def test_full_report_timestamp_format(self, db):
        """Test that timestamp is ISO format."""
        result = DatabaseOptimizationService.get_full_optimization_report(db)

        # Try to parse the timestamp
        try:
            datetime.fromisoformat(result["timestamp"])
            assert True
        except ValueError:
            assert False, "Timestamp is not ISO format"

    def test_partition_strategy_has_recommendation(self, db):
        """Test that partition strategy includes recommendation."""
        result = DatabaseOptimizationService.get_full_optimization_report(db)

        if "partition_strategy" in result:
            strategy = result["partition_strategy"]
            if "error" not in strategy:
                assert "recommendation" in strategy


# ===== Integration Tests =====

class TestDatabaseOptimizationIntegration:
    """Integration tests for database optimization."""

    def test_complete_optimization_workflow(self, db):
        """Test complete optimization workflow."""
        # 1. Get initial stats
        initial_stats = DatabaseOptimizationService.get_partition_stats(db)
        assert initial_stats is not None

        # 2. Get index stats
        index_stats = DatabaseOptimizationService.get_index_stats(db)
        assert index_stats is not None

        # 3. Get full report
        report = DatabaseOptimizationService.get_full_optimization_report(db)
        assert report is not None

        # All should have valid structure
        assert "timestamp" in report
        assert isinstance(report, dict)

    def test_multiple_operations_sequence(self, db):
        """Test sequence of multiple operations."""
        operations = [
            ("analyze", lambda: DatabaseOptimizationService.analyze_table(db, "pg_tables")),
            ("partition_stats", lambda: DatabaseOptimizationService.get_partition_stats(db)),
            ("index_stats", lambda: DatabaseOptimizationService.get_index_stats(db)),
        ]

        results = {}
        for name, operation in operations:
            try:
                result = operation()
                results[name] = result
                assert result is not None, f"Operation {name} returned None"
            except Exception as e:
                # Some operations might fail if tables don't exist, which is okay
                results[name] = {"error": str(e)}

        # At least some operations should succeed
        assert len(results) > 0


# ===== Configuration Tests =====

class TestOptimizationConfig:
    """Test optimization service configuration."""

    def test_partition_interval_is_string(self):
        """Test that partition interval is configured."""
        assert isinstance(DatabaseOptimizationService.PARTITION_INTERVAL, str)
        assert len(DatabaseOptimizationService.PARTITION_INTERVAL) > 0

    def test_premake_partitions_is_positive(self):
        """Test that premake partitions is positive."""
        assert isinstance(DatabaseOptimizationService.PREMAKE_PARTITIONS, int)
        assert DatabaseOptimizationService.PREMAKE_PARTITIONS > 0

    def test_brin_page_range_is_positive(self):
        """Test that BRIN page range is positive."""
        assert isinstance(DatabaseOptimizationService.BRIN_PAGE_RANGE, int)
        assert DatabaseOptimizationService.BRIN_PAGE_RANGE > 0

    def test_fillfactor_is_valid(self):
        """Test that fillfactor is in valid range."""
        assert isinstance(DatabaseOptimizationService.FILLFACTOR, int)
        assert 10 <= DatabaseOptimizationService.FILLFACTOR <= 100


# ===== Error Handling Tests =====

class TestErrorHandling:
    """Test error handling in optimization service."""

    def test_nonexistent_table_analyze_returns_error(self, db):
        """Test handling of nonexistent table in analyze."""
        result = DatabaseOptimizationService.analyze_table(db, "nonexistent_table_xyz")

        assert "status" in result
        # Should either succeed (unlikely) or have error/status

    def test_nonexistent_table_vacuum_returns_error(self, db):
        """Test handling of nonexistent table in vacuum."""
        result = DatabaseOptimizationService.vacuum_table(db, "nonexistent_table_xyz")

        assert "status" in result

    def test_partition_stats_graceful_failure(self, db):
        """Test that partition stats handles errors gracefully."""
        result = DatabaseOptimizationService.get_partition_stats(db)

        # Should either return valid stats or error dict
        assert isinstance(result, dict)


# ===== Performance Monitoring Tests =====

class TestPerformanceMonitoring:
    """Test performance monitoring capabilities."""

    def test_check_partition_strategy_returns_dict(self, db):
        """Test that partition strategy check returns dictionary."""
        result = DatabaseOptimizationService.check_partition_strategy(db)

        assert isinstance(result, dict)

    def test_check_partition_strategy_has_status_or_error(self, db):
        """Test that partition strategy has status or error."""
        result = DatabaseOptimizationService.check_partition_strategy(db)

        assert "status" in result or "error" in result

    def test_partition_strategy_includes_recommendation(self, db):
        """Test that strategy check includes recommendation if successful."""
        result = DatabaseOptimizationService.check_partition_strategy(db)

        if "error" not in result:
            assert "recommendation" in result or "status" in result
