"""
CRM 路由模块
提供用户信息查询、交互记录查询等接口
"""
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.crm_models import User, Interaction, UserProfile
from app.crm.analyzer import crm_analyzer

router = APIRouter(prefix="/api/v1/crm", tags=["crm"])


# ==================== Pydantic 模型 ====================

class UserResponse(BaseModel):
    """用户响应模型"""
    id: str
    username: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    nickname: Optional[str] = None
    source: str = "web"
    created_at: datetime
    last_active_at: datetime

class UserProfileResponse(BaseModel):
    """用户画像响应模型"""
    user_id: str
    name: Optional[str] = None
    gender: Optional[str] = None
    age_range: Optional[str] = None
    occupation: Optional[str] = None
    city: Optional[str] = None
    preferences: Optional[dict] = None
    intent: Optional[str] = None
    budget_range: Optional[str] = None
    tags: Optional[list] = None
    notes: Optional[str] = None
    updated_at: datetime

class InteractionResponse(BaseModel):
    """交互记录响应模型"""
    id: str
    user_id: str
    user_message: str
    assistant_message: str
    crm_analyzed: bool
    created_at: datetime

class UserCreateRequest(BaseModel):
    """创建用户请求"""
    username: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    nickname: Optional[str] = None
    source: str = "web"

class CRMStatsResponse(BaseModel):
    """CRM 统计响应"""
    total_users: int
    total_interactions: int
    analyzed_interactions: int
    users_with_profile: int


# ==================== 用户接口 ====================

@router.get("/users", response_model=List[UserResponse])
async def get_users(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """获取用户列表"""
    result = await db.execute(
        select(User).offset(skip).limit(limit).order_by(User.created_at.desc())
    )
    users = result.scalars().all()
    return users


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    db: AsyncSession = Depends(get_db)
):
    """获取用户详情"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    return user


@router.post("/users", response_model=UserResponse)
async def create_user(
    request: UserCreateRequest,
    db: AsyncSession = Depends(get_db)
):
    """创建新用户"""
    user = User(
        username=request.username,
        phone=request.phone,
        email=request.email,
        nickname=request.nickname,
        source=request.source
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


# ==================== 用户画像接口 ====================

@router.get("/users/{user_id}/profile", response_model=UserProfileResponse)
async def get_user_profile(
    user_id: str,
    db: AsyncSession = Depends(get_db)
):
    """获取用户画像"""
    result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == user_id)
    )
    profile = result.scalar_one_or_none()
    
    if not profile:
        raise HTTPException(status_code=404, detail="用户画像不存在")
    
    return profile


@router.put("/users/{user_id}/profile", response_model=UserProfileResponse)
async def update_user_profile(
    user_id: str,
    profile_data: dict,
    db: AsyncSession = Depends(get_db)
):
    """更新用户画像"""
    result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == user_id)
    )
    profile = result.scalar_one_or_none()
    
    if not profile:
        profile = UserProfile(user_id=user_id)
        db.add(profile)
    
    # 更新字段
    for key, value in profile_data.items():
        if hasattr(profile, key) and value is not None:
            setattr(profile, key, value)
    
    profile.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(profile)
    return profile


# ==================== 交互记录接口 ====================

@router.get("/interactions", response_model=List[InteractionResponse])
async def get_interactions(
    user_id: Optional[str] = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """获取交互记录列表"""
    query = select(Interaction)
    
    if user_id:
        query = query.where(Interaction.user_id == user_id)
    
    query = query.offset(skip).limit(limit).order_by(Interaction.created_at.desc())
    
    result = await db.execute(query)
    interactions = result.scalars().all()
    return interactions


@router.get("/interactions/{interaction_id}", response_model=InteractionResponse)
async def get_interaction(
    interaction_id: str,
    db: AsyncSession = Depends(get_db)
):
    """获取交互记录详情"""
    result = await db.execute(
        select(Interaction).where(Interaction.id == interaction_id)
    )
    interaction = result.scalar_one_or_none()
    
    if not interaction:
        raise HTTPException(status_code=404, detail="交互记录不存在")
    
    return interaction


# ==================== CRM 分析接口 ====================

@router.post("/analyze/{interaction_id}")
async def analyze_interaction(
    interaction_id: str,
    db: AsyncSession = Depends(get_db)
):
    """手动触发交互记录的 CRM 分析"""
    result = await db.execute(
        select(Interaction).where(Interaction.id == interaction_id)
    )
    interaction = result.scalar_one_or_none()
    
    if not interaction:
        raise HTTPException(status_code=404, detail="交互记录不存在")
    
    conversation = f"用户：{interaction.user_message}\n助手：{interaction.assistant_message}"
    
    profile = await crm_analyzer.analyze_and_save(
        db=db,
        interaction_id=interaction_id,
        user_id=interaction.user_id,
        conversation=conversation
    )
    
    return {
        "success": True,
        "message": "分析完成",
        "extracted_data": interaction.crm_extracted_data
    }


# ==================== 统计接口 ====================

@router.get("/stats", response_model=CRMStatsResponse)
async def get_crm_stats(
    db: AsyncSession = Depends(get_db)
):
    """获取 CRM 统计信息"""
    # 用户总数
    result = await db.execute(select(func.count(User.id)))
    total_users = result.scalar() or 0
    
    # 交互记录总数
    result = await db.execute(select(func.count(Interaction.id)))
    total_interactions = result.scalar() or 0
    
    # 已分析的交互记录数
    result = await db.execute(
        select(func.count(Interaction.id)).where(Interaction.crm_analyzed == True)
    )
    analyzed_interactions = result.scalar() or 0
    
    # 有画像的用户数
    result = await db.execute(select(func.count(UserProfile.id)))
    users_with_profile = result.scalar() or 0
    
    return CRMStatsResponse(
        total_users=total_users,
        total_interactions=total_interactions,
        analyzed_interactions=analyzed_interactions,
        users_with_profile=users_with_profile
    )
