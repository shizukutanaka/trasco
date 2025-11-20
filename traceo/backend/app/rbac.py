"""
Role-Based Access Control (RBAC) System for Traceo.
Implements fine-grained permission management for enterprise security.
"""

from datetime import datetime
from typing import Optional, List
from enum import Enum
from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Table, ForeignKey
from loguru import logger

from app.database import get_db, Base
from app.security import get_current_user
from app.user_profiles import UserProfile


router = APIRouter(prefix="/rbac", tags=["rbac"])


# ===== Enums =====

class PermissionEnum(str, Enum):
    """System permissions"""
    # Email management
    EMAIL_VIEW = "email:view"
    EMAIL_CREATE = "email:create"
    EMAIL_UPDATE = "email:update"
    EMAIL_DELETE = "email:delete"
    EMAIL_EXPORT = "email:export"

    # Rules management
    RULE_VIEW = "rule:view"
    RULE_CREATE = "rule:create"
    RULE_UPDATE = "rule:update"
    RULE_DELETE = "rule:delete"
    RULE_TEST = "rule:test"

    # Webhook management
    WEBHOOK_VIEW = "webhook:view"
    WEBHOOK_CREATE = "webhook:create"
    WEBHOOK_UPDATE = "webhook:update"
    WEBHOOK_DELETE = "webhook:delete"
    WEBHOOK_TEST = "webhook:test"

    # User management
    USER_VIEW = "user:view"
    USER_CREATE = "user:create"
    USER_UPDATE = "user:update"
    USER_DELETE = "user:delete"

    # Admin operations
    ADMIN_STATS = "admin:stats"
    ADMIN_HEALTH = "admin:health"
    ADMIN_CLEANUP = "admin:cleanup"
    ADMIN_REBUILD = "admin:rebuild"

    # Audit logs
    AUDIT_VIEW = "audit:view"
    AUDIT_EXPORT = "audit:export"
    AUDIT_CLEANUP = "audit:cleanup"

    # Settings
    SETTINGS_UPDATE = "settings:update"
    SETTINGS_VIEW = "settings:view"


class RoleEnum(str, Enum):
    """Predefined system roles"""
    USER = "user"
    ANALYST = "analyst"
    ADMINISTRATOR = "admin"
    AUDITOR = "auditor"
    API_SERVICE = "api_service"


# ===== Association Tables =====

role_permissions = Table(
    'role_permissions',
    Base.metadata,
    Column('role_id', Integer, ForeignKey('roles.id'), primary_key=True),
    Column('permission_id', Integer, ForeignKey('permissions.id'), primary_key=True)
)

user_roles = Table(
    'user_roles',
    Base.metadata,
    Column('user_id', Integer, ForeignKey('user_profiles.id'), primary_key=True),
    Column('role_id', Integer, ForeignKey('roles.id'), primary_key=True)
)


# ===== Database Models =====

class Permission(Base):
    """Permission model"""
    __tablename__ = "permissions"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String, unique=True, index=True)  # email:view
    name = Column(String)  # "View Emails"
    description = Column(String, nullable=True)
    resource = Column(String)  # email, rule, webhook, user, etc.
    action = Column(String)  # view, create, update, delete, etc.
    created_at = Column(DateTime, default=datetime.utcnow)


class Role(Base):
    """Role model"""
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String, unique=True, index=True)  # admin, user, analyst
    name = Column(String)  # Administrator, User, Analyst
    description = Column(String, nullable=True)
    is_system = Column(Boolean, default=False)  # System roles can't be deleted
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ===== Pydantic Models =====

class PermissionResponse(BaseModel):
    """Permission response"""
    id: int
    code: str
    name: str
    description: Optional[str]
    resource: str
    action: str

    class Config:
        from_attributes = True


class RoleResponse(BaseModel):
    """Role response"""
    id: int
    code: str
    name: str
    description: Optional[str]
    is_system: bool
    created_at: datetime

    class Config:
        from_attributes = True


class RoleDetailResponse(BaseModel):
    """Role with permissions"""
    id: int
    code: str
    name: str
    description: Optional[str]
    is_system: bool
    permissions: List[PermissionResponse]

    class Config:
        from_attributes = True


class RoleCreate(BaseModel):
    """Create role"""
    code: str
    name: str
    description: Optional[str] = None
    permissions: List[str] = []  # Permission codes


class RoleUpdate(BaseModel):
    """Update role"""
    name: Optional[str] = None
    description: Optional[str] = None
    permissions: Optional[List[str]] = None


class UserRoleResponse(BaseModel):
    """User with roles"""
    id: int
    username: str
    email: str
    roles: List[RoleResponse]
    permissions: List[str]  # Flattened permission codes

    class Config:
        from_attributes = True


# ===== RBAC Service =====

class RBACService:
    """Service for RBAC operations"""

    @staticmethod
    def init_system_roles(db: Session):
        """Initialize system default roles"""
        if db.query(Role).filter(Role.code == RoleEnum.USER.value).first():
            return  # Already initialized

        # Define role permission mappings
        role_permissions_map = {
            RoleEnum.USER.value: [
                "email:view",
                "rule:view", "rule:create", "rule:update", "rule:delete", "rule:test",
                "webhook:view", "webhook:create", "webhook:update", "webhook:delete", "webhook:test",
                "audit:view", "audit:export",
                "settings:view", "settings:update",
            ],
            RoleEnum.ANALYST.value: [
                "email:view", "email:update", "email:export",
                "rule:view", "rule:create", "rule:update", "rule:delete", "rule:test",
                "webhook:view", "webhook:create", "webhook:update", "webhook:delete", "webhook:test",
                "audit:view", "audit:export",
                "settings:view",
            ],
            RoleEnum.ADMINISTRATOR.value: [p.value for p in PermissionEnum],
            RoleEnum.AUDITOR.value: [
                "audit:view", "audit:export",
                "email:view",
                "user:view",
                "admin:stats", "admin:health",
            ],
            RoleEnum.API_SERVICE.value: [
                "email:view", "email:create",
                "rule:view",
                "webhook:view", "webhook:create",
                "audit:view",
            ]
        }

        # Create permissions
        permission_map = {}
        for permission in PermissionEnum:
            perm_code = permission.value
            resource, action = perm_code.split(":")

            existing = db.query(Permission).filter(Permission.code == perm_code).first()
            if not existing:
                perm = Permission(
                    code=perm_code,
                    name=f"{action.capitalize()} {resource.capitalize()}",
                    resource=resource,
                    action=action,
                )
                db.add(perm)
                db.commit()
                db.refresh(perm)
                permission_map[perm_code] = perm
            else:
                permission_map[perm_code] = existing

        # Create roles with permissions
        for role_code, permissions in role_permissions_map.items():
            existing_role = db.query(Role).filter(Role.code == role_code).first()
            if not existing_role:
                role = Role(
                    code=role_code,
                    name=role_code.capitalize(),
                    is_system=True,
                )
                db.add(role)
                db.commit()
                db.refresh(role)

                # Assign permissions
                for perm_code in permissions:
                    if perm_code in permission_map:
                        role.permissions = db.query(Permission).filter(
                            Permission.code.in_(permissions)
                        ).all()

                db.add(role)
                db.commit()

        logger.info("RBAC system roles initialized")

    @staticmethod
    def get_user_permissions(user_id: int, db: Session) -> List[str]:
        """Get all permissions for a user (from all roles)"""
        user = db.query(UserProfile).filter(UserProfile.id == user_id).first()
        if not user:
            return []

        # Get all roles for user
        roles = db.query(Role).join(
            user_roles,
            Role.id == user_roles.c.role_id
        ).filter(user_roles.c.user_id == user_id).all()

        # Get all permissions from all roles
        permissions = set()
        for role in roles:
            role_perms = db.query(Permission.code).join(
                role_permissions,
                Permission.id == role_permissions.c.permission_id
            ).filter(role_permissions.c.role_id == role.id).all()

            for perm in role_perms:
                permissions.add(perm[0])

        return list(permissions)

    @staticmethod
    def has_permission(user_id: int, permission: str, db: Session) -> bool:
        """Check if user has specific permission"""
        permissions = RBACService.get_user_permissions(user_id, db)
        return permission in permissions

    @staticmethod
    def assign_role(user_id: int, role_code: str, db: Session) -> bool:
        """Assign role to user"""
        role = db.query(Role).filter(Role.code == role_code).first()
        if not role:
            return False

        user = db.query(UserProfile).filter(UserProfile.id == user_id).first()
        if not user:
            return False

        # Check if user already has role
        existing = db.query(user_roles).filter(
            user_roles.c.user_id == user_id,
            user_roles.c.role_id == role.id
        ).first()

        if not existing:
            stmt = user_roles.insert().values(user_id=user_id, role_id=role.id)
            db.execute(stmt)
            db.commit()
            logger.info(f"Assigned role {role_code} to user {user_id}")

        return True

    @staticmethod
    def remove_role(user_id: int, role_code: str, db: Session) -> bool:
        """Remove role from user"""
        role = db.query(Role).filter(Role.code == role_code).first()
        if not role:
            return False

        stmt = user_roles.delete().where(
            (user_roles.c.user_id == user_id) &
            (user_roles.c.role_id == role.id)
        )
        db.execute(stmt)
        db.commit()
        logger.info(f"Removed role {role_code} from user {user_id}")
        return True


# ===== API Routes =====

@router.get("/permissions", response_model=List[PermissionResponse])
async def list_permissions(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all system permissions"""
    # Check if user is admin
    if not RBACService.has_permission(current_user.id, PermissionEnum.ADMIN_STATS.value, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized"
        )

    permissions = db.query(Permission).all()
    return permissions


@router.get("/roles", response_model=List[RoleResponse])
async def list_roles(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all roles"""
    if not RBACService.has_permission(current_user.id, PermissionEnum.ADMIN_STATS.value, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized"
        )

    roles = db.query(Role).all()
    return roles


@router.get("/roles/{role_id}", response_model=RoleDetailResponse)
async def get_role(
    role_id: int,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get role details with permissions"""
    if not RBACService.has_permission(current_user.id, PermissionEnum.ADMIN_STATS.value, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized"
        )

    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    return role


@router.post("/roles", response_model=RoleDetailResponse, status_code=status.HTTP_201_CREATED)
async def create_role(
    role_data: RoleCreate,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create new role"""
    if not RBACService.has_permission(current_user.id, PermissionEnum.ADMIN_STATS.value, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized"
        )

    # Check if role exists
    existing = db.query(Role).filter(Role.code == role_data.code).first()
    if existing:
        raise HTTPException(status_code=400, detail="Role already exists")

    role = Role(
        code=role_data.code,
        name=role_data.name,
        description=role_data.description,
    )
    db.add(role)
    db.commit()
    db.refresh(role)

    # Assign permissions
    if role_data.permissions:
        permissions = db.query(Permission).filter(
            Permission.code.in_(role_data.permissions)
        ).all()

        for perm in permissions:
            stmt = role_permissions.insert().values(
                role_id=role.id,
                permission_id=perm.id
            )
            db.execute(stmt)

        db.commit()
        db.refresh(role)

    logger.info(f"Created role: {role.code}")
    return role


@router.get("/users/{user_id}/roles", response_model=UserRoleResponse)
async def get_user_roles(
    user_id: int,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get user roles and permissions"""
    # Users can only view their own roles unless they're admin
    if current_user.id != user_id:
        if not RBACService.has_permission(current_user.id, PermissionEnum.ADMIN_STATS.value, db):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized"
            )

    user = db.query(UserProfile).filter(UserProfile.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Get roles
    roles = db.query(Role).join(
        user_roles,
        Role.id == user_roles.c.role_id
    ).filter(user_roles.c.user_id == user_id).all()

    # Get permissions
    permissions = RBACService.get_user_permissions(user_id, db)

    return UserRoleResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        roles=roles,
        permissions=permissions,
    )


@router.post("/users/{user_id}/roles/{role_code}", status_code=status.HTTP_204_NO_CONTENT)
async def assign_user_role(
    user_id: int,
    role_code: str,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Assign role to user"""
    if not RBACService.has_permission(current_user.id, PermissionEnum.USER_UPDATE.value, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized"
        )

    success = RBACService.assign_role(user_id, role_code, db)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to assign role")


@router.delete("/users/{user_id}/roles/{role_code}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_user_role(
    user_id: int,
    role_code: str,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Remove role from user"""
    if not RBACService.has_permission(current_user.id, PermissionEnum.USER_UPDATE.value, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized"
        )

    success = RBACService.remove_role(user_id, role_code, db)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to remove role")
