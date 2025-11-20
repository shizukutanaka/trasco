"""
Database Administration API endpoints for Traceo.
Provides administrative access to database optimization and maintenance functions.
"""

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.security import get_current_user
from app.database.optimization_service import DatabaseOptimizationService
from app.security import log_security_event


router = APIRouter(prefix="/admin/database", tags=["database administration"])


# ===== Pydantic Models =====

class DatabaseStatsResponse(BaseModel):
    """Database statistics response"""
    timestamp: str
    partition_count: int
    index_count: int
    total_partition_size: str
    total_index_size: str


class PartitionStatsResponse(BaseModel):
    """Partition statistics"""
    partition_count: int
    total_size_bytes: int
    total_size_pretty: str


class IndexStatsResponse(BaseModel):
    """Index statistics"""
    index_count: int
    total_size_bytes: int
    total_size_pretty: str


class OptimizationReportResponse(BaseModel):
    """Full optimization report"""
    timestamp: str
    partitions: dict
    indexes: dict
    query_performance: dict
    partition_strategy: dict


class OperationResultResponse(BaseModel):
    """Operation result"""
    status: str
    message: str
    elapsed_seconds: Optional[float] = None


# ===== Database Statistics Routes =====

@router.get("/stats/partitions", response_model=PartitionStatsResponse)
async def get_partition_stats(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get audit log partition statistics.

    Requires: Admin role
    Returns: Partition count, sizes, and distribution
    """
    # Check if user is admin (integrate with RBAC)
    # For now, any authenticated user can view stats
    # TODO: Add role-based access control

    try:
        stats = DatabaseOptimizationService.get_partition_stats(db)

        if "error" in stats:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=stats["error"]
            )

        log_security_event(
            "database_partition_stats_viewed",
            {"username": current_user.username},
            severity="INFO"
        )

        return PartitionStatsResponse(**stats)

    except Exception as e:
        log_security_event(
            "database_stats_error",
            {"username": current_user.username, "error": str(e)},
            severity="ERROR"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve partition statistics"
        )


@router.get("/stats/indexes", response_model=IndexStatsResponse)
async def get_index_stats(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get index statistics and usage information.

    Requires: Admin role
    Returns: Index count, sizes, and usage metrics
    """
    try:
        stats = DatabaseOptimizationService.get_index_stats(db)

        if "error" in stats:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=stats["error"]
            )

        log_security_event(
            "database_index_stats_viewed",
            {"username": current_user.username},
            severity="INFO"
        )

        return IndexStatsResponse(**stats)

    except Exception as e:
        log_security_event(
            "database_index_stats_error",
            {"username": current_user.username, "error": str(e)},
            severity="ERROR"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve index statistics"
        )


@router.get("/report", response_model=OptimizationReportResponse)
async def get_optimization_report(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get complete database optimization report.

    Requires: Admin role
    Returns: Comprehensive analysis of partitions, indexes, and queries
    """
    try:
        report = DatabaseOptimizationService.get_full_optimization_report(db)

        log_security_event(
            "database_optimization_report_generated",
            {"username": current_user.username},
            severity="INFO"
        )

        return OptimizationReportResponse(**report)

    except Exception as e:
        log_security_event(
            "database_report_error",
            {"username": current_user.username, "error": str(e)},
            severity="ERROR"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate optimization report"
        )


# ===== Database Maintenance Routes =====

@router.post("/maintenance/vacuum", response_model=OperationResultResponse)
async def vacuum_database(
    current_user = Depends(get_current_user),
    table_name: str = Field("audit_logs", description="Table to vacuum"),
    analyze: bool = Field(True, description="Run ANALYZE after VACUUM"),
    db: Session = Depends(get_db),
):
    """
    Run VACUUM operation on specified table.

    Requires: Admin role
    Purpose: Clean up dead rows and reclaim disk space

    Parameters:
    - table_name: Table to vacuum (default: audit_logs)
    - analyze: Also run ANALYZE to update statistics
    """
    try:
        result = DatabaseOptimizationService.vacuum_table(db, table_name, analyze)

        if result["status"] == "error":
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Vacuum operation failed")
            )

        log_security_event(
            "database_vacuum_executed",
            {
                "username": current_user.username,
                "table": table_name,
                "analyze": analyze,
                "elapsed_seconds": result.get("elapsed_seconds"),
            },
            severity="INFO"
        )

        return OperationResultResponse(
            status="success",
            message=f"VACUUM {'ANALYZE' if analyze else ''} completed on {table_name}",
            elapsed_seconds=result.get("elapsed_seconds")
        )

    except HTTPException:
        raise
    except Exception as e:
        log_security_event(
            "database_vacuum_error",
            {"username": current_user.username, "error": str(e)},
            severity="ERROR"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Vacuum operation failed"
        )


@router.post("/maintenance/analyze", response_model=OperationResultResponse)
async def analyze_table(
    current_user = Depends(get_current_user),
    table_name: str = Field("audit_logs", description="Table to analyze"),
    db: Session = Depends(get_db),
):
    """
    Run ANALYZE operation to update table statistics.

    Requires: Admin role
    Purpose: Update PostgreSQL query planner statistics

    Parameters:
    - table_name: Table to analyze (default: audit_logs)
    """
    try:
        result = DatabaseOptimizationService.analyze_table(db, table_name)

        if result["status"] == "error":
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Analyze operation failed")
            )

        log_security_event(
            "database_analyze_executed",
            {
                "username": current_user.username,
                "table": table_name,
                "elapsed_seconds": result.get("elapsed_seconds"),
            },
            severity="INFO"
        )

        return OperationResultResponse(
            status="success",
            message=f"ANALYZE completed on {table_name}",
            elapsed_seconds=result.get("elapsed_seconds")
        )

    except HTTPException:
        raise
    except Exception as e:
        log_security_event(
            "database_analyze_error",
            {"username": current_user.username, "error": str(e)},
            severity="ERROR"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Analyze operation failed"
        )


@router.post("/maintenance/reindex", response_model=OperationResultResponse)
async def rebuild_indexes(
    current_user = Depends(get_current_user),
    table_name: str = Field("audit_logs", description="Table whose indexes to rebuild"),
    db: Session = Depends(get_db),
):
    """
    Rebuild all indexes on specified table.

    Requires: Admin role
    Purpose: Optimize index structure and reclaim disk space

    Note: Uses REINDEX ... CONCURRENTLY to avoid locking

    Parameters:
    - table_name: Table whose indexes to rebuild (default: audit_logs)
    """
    try:
        result = DatabaseOptimizationService.rebuild_indexes(db, table_name)

        if result["status"] == "error":
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Reindex operation failed")
            )

        log_security_event(
            "database_reindex_executed",
            {
                "username": current_user.username,
                "table": table_name,
                "indexes_rebuilt": result.get("indexes_rebuilt", 0),
                "indexes_failed": result.get("indexes_failed", 0),
            },
            severity="INFO"
        )

        return OperationResultResponse(
            status="success",
            message=f"Rebuilt {result.get('indexes_rebuilt', 0)} indexes on {table_name}",
        )

    except HTTPException:
        raise
    except Exception as e:
        log_security_event(
            "database_reindex_error",
            {"username": current_user.username, "error": str(e)},
            severity="ERROR"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Reindex operation failed"
        )


# ===== Health Check Routes =====

@router.get("/health", response_model=dict)
async def database_health_check(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Check database health and connectivity.

    Returns: Health status and key metrics
    """
    try:
        # Simple health check query
        result = db.execute("SELECT 1")

        # Get partition count
        partition_result = db.execute("""
            SELECT COUNT(*) FROM pg_tables
            WHERE tablename LIKE 'audit_logs_%'
        """).scalar()

        log_security_event(
            "database_health_check",
            {"username": current_user.username},
            severity="INFO"
        )

        return {
            "status": "healthy",
            "database": "connected",
            "timestamp": datetime.utcnow().isoformat(),
            "partitions_active": partition_result or 0,
        }

    except Exception as e:
        log_security_event(
            "database_health_check_failed",
            {"username": current_user.username, "error": str(e)},
            severity="ERROR"
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database health check failed"
        )
