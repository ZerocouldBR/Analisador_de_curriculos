"""
API de gerenciamento de empresas (multi-tenant)

Endpoints para administradores gerenciarem empresas,
logos, planos, e configuracoes por empresa.
"""
import os
import re
import uuid
import logging

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

from app.db.database import get_db
from app.core.config import settings
from app.core.dependencies import get_current_user, require_permission, get_current_superuser
from app.db.models import User, Company, Role, AIUsageLog, AuditLog
from app.services.ai_usage_service import AIUsageService
from app.services.auth_service import AuthService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/companies", tags=["companies"])


# ============================================
# Schemas
# ============================================

class CompanyCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    cnpj: Optional[str] = Field(None, max_length=18)
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    website: Optional[str] = None
    plan: str = Field(default="free", description="Plano: free, basic, pro, enterprise")


class CompanyUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=200)
    cnpj: Optional[str] = Field(None, max_length=18)
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    website: Optional[str] = None
    plan: Optional[str] = None
    is_active: Optional[bool] = None
    settings_json: Optional[Dict[str, Any]] = None


class CompanyResponse(BaseModel):
    id: int
    name: str
    slug: str
    cnpj: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    logo_url: Optional[str] = None
    website: Optional[str] = None
    plan: str
    is_active: bool
    settings_json: Dict[str, Any] = {}
    user_count: Optional[int] = None
    candidate_count: Optional[int] = None

    class Config:
        from_attributes = True


class AIUsageSummaryResponse(BaseModel):
    company_id: int
    period_days: int
    currency: str
    total_tokens: int
    total_cost_usd: float
    total_cost_local: float
    total_requests: int
    by_operation: Dict[str, Any]
    limits: Dict[str, Any]
    pricing: Dict[str, float]


# ============================================
# Helpers
# ============================================

def _generate_slug(name: str) -> str:
    """Gera slug unico a partir do nome"""
    slug = re.sub(r'[^a-z0-9]+', '-', name.lower().strip())
    slug = slug.strip('-')
    return slug or "empresa"


def _is_company_admin_or_superuser(user: User, company_id: int) -> bool:
    """Verifica se o usuario e superuser ou company_admin/admin da empresa"""
    if user.is_superuser:
        return True
    if user.company_id != company_id:
        return False
    return AuthService.has_role(user, "company_admin") or AuthService.has_role(user, "admin")


# Roles que um company_admin pode atribuir/remover
COMPANY_ADMIN_ASSIGNABLE_ROLES = {"recruiter", "viewer"}


# ============================================
# Endpoints de Empresas
# ============================================

@router.get("/", response_model=List[CompanyResponse])
def list_companies(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    active_only: bool = Query(default=True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
):
    """
    Lista todas as empresas

    **Requer:** Superuser
    """
    query = db.query(Company)
    if active_only:
        query = query.filter(Company.is_active == True)

    companies = query.offset(skip).limit(limit).all()

    results = []
    for company in companies:
        resp = CompanyResponse.model_validate(company)
        resp.user_count = len(company.users)
        resp.candidate_count = len(company.candidates)
        results.append(resp)

    return results


@router.get("/me", response_model=CompanyResponse)
def get_my_company(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Retorna a empresa do usuario atual

    **Requer:** Autenticacao
    """
    if not current_user.company_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario nao esta associado a nenhuma empresa"
        )

    company = db.query(Company).filter(Company.id == current_user.company_id).first()
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Empresa nao encontrada"
        )

    resp = CompanyResponse.model_validate(company)
    resp.user_count = len(company.users)
    resp.candidate_count = len(company.candidates)
    return resp


@router.put("/me", response_model=CompanyResponse)
def update_my_company(
    company_update: CompanyUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("settings.update")),
):
    """
    Atualiza dados da empresa do usuario atual

    Permite que administradores da empresa editem os dados
    sem precisar de acesso superuser.

    **Requer permissao:** settings.update
    """
    if not current_user.company_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario nao esta associado a nenhuma empresa"
        )

    company = db.query(Company).filter(Company.id == current_user.company_id).first()
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Empresa nao encontrada"
        )

    update_data = company_update.model_dump(exclude_unset=True)
    # Nao permitir que admin mude o plano ou status
    update_data.pop("plan", None)
    update_data.pop("is_active", None)

    for field, value in update_data.items():
        setattr(company, field, value)

    if "name" in update_data:
        company.slug = _generate_slug(update_data["name"])
        existing = db.query(Company).filter(
            Company.slug == company.slug, Company.id != company.id
        ).first()
        if existing:
            company.slug = f"{company.slug}-{uuid.uuid4().hex[:6]}"

    db.commit()
    db.refresh(company)

    resp = CompanyResponse.model_validate(company)
    resp.user_count = len(company.users)
    resp.candidate_count = len(company.candidates)
    return resp


@router.get("/me/ai-usage", response_model=AIUsageSummaryResponse)
def get_my_ai_usage(
    days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Resumo de uso de IA da empresa do usuario atual

    **Requer:** Autenticacao
    """
    if not current_user.company_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario nao associado a nenhuma empresa"
        )

    summary = AIUsageService.get_company_usage_summary(
        db, current_user.company_id, days
    )
    return summary


@router.get("/me/users")
def list_my_company_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users.manage")),
):
    """
    Lista usuarios da empresa do usuario atual

    **Requer permissao:** users.manage (company_admin, admin ou superuser)
    """
    if not current_user.company_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario nao esta associado a nenhuma empresa"
        )

    users = db.query(User).filter(User.company_id == current_user.company_id).all()
    return [
        {
            "id": u.id,
            "name": u.name,
            "email": u.email,
            "status": u.status,
            "is_superuser": u.is_superuser,
            "roles": [r.name for r in u.roles],
        }
        for u in users
    ]


@router.get("/{company_id}", response_model=CompanyResponse)
def get_company(
    company_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
):
    """
    Obtem detalhes de uma empresa

    **Requer:** Superuser
    """
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Empresa {company_id} nao encontrada"
        )

    resp = CompanyResponse.model_validate(company)
    resp.user_count = len(company.users)
    resp.candidate_count = len(company.candidates)
    return resp


@router.post("/", response_model=CompanyResponse, status_code=status.HTTP_201_CREATED)
def create_company(
    company_data: CompanyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
):
    """
    Cria uma nova empresa

    **Requer:** Superuser
    """
    slug = _generate_slug(company_data.name)

    # Verificar slug unico
    existing = db.query(Company).filter(Company.slug == slug).first()
    if existing:
        slug = f"{slug}-{uuid.uuid4().hex[:6]}"

    # Verificar CNPJ unico
    if company_data.cnpj:
        existing_cnpj = db.query(Company).filter(Company.cnpj == company_data.cnpj).first()
        if existing_cnpj:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"CNPJ '{company_data.cnpj}' ja cadastrado"
            )

    company = Company(
        name=company_data.name,
        slug=slug,
        cnpj=company_data.cnpj,
        email=company_data.email,
        phone=company_data.phone,
        address=company_data.address,
        city=company_data.city,
        state=company_data.state,
        website=company_data.website,
        plan=company_data.plan,
    )
    db.add(company)
    db.commit()
    db.refresh(company)

    return CompanyResponse.model_validate(company)


@router.put("/{company_id}", response_model=CompanyResponse)
def update_company(
    company_id: int,
    company_update: CompanyUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
):
    """
    Atualiza uma empresa

    **Requer:** Superuser
    """
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Empresa {company_id} nao encontrada"
        )

    update_data = company_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(company, field, value)

    if "name" in update_data:
        company.slug = _generate_slug(update_data["name"])
        existing = db.query(Company).filter(
            Company.slug == company.slug, Company.id != company_id
        ).first()
        if existing:
            company.slug = f"{company.slug}-{uuid.uuid4().hex[:6]}"

    db.commit()
    db.refresh(company)

    resp = CompanyResponse.model_validate(company)
    resp.user_count = len(company.users)
    resp.candidate_count = len(company.candidates)
    return resp


@router.delete("/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_company(
    company_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
):
    """
    Desativa uma empresa (soft delete)

    **Requer:** Superuser
    """
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Empresa {company_id} nao encontrada"
        )

    company.is_active = False
    db.commit()


# ============================================
# Logo Upload
# ============================================

@router.post("/{company_id}/logo")
async def upload_company_logo(
    company_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Upload do logo da empresa

    Formatos: PNG, JPG, SVG, WEBP
    Tamanho max: configuravel via COMPANY_LOGO_MAX_SIZE_KB

    **Requer:** Superuser ou company_admin da mesma empresa
    """
    if not _is_company_admin_or_superuser(current_user, company_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso negado: superuser ou company_admin da empresa necessario"
        )
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Empresa {company_id} nao encontrada"
        )

    # Validar formato
    ext = file.filename.rsplit(".", 1)[-1].lower() if file.filename else ""
    if ext not in settings.company_logo_allowed_formats:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Formato '{ext}' nao permitido. Use: {', '.join(settings.company_logo_allowed_formats)}"
        )

    # Ler e validar tamanho
    content = await file.read()
    max_bytes = settings.company_logo_max_size_kb * 1024
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Logo excede {settings.company_logo_max_size_kb}KB"
        )

    # Salvar
    logo_dir = settings.company_logo_path
    os.makedirs(logo_dir, exist_ok=True)

    filename = f"company_{company_id}_{uuid.uuid4().hex[:8]}.{ext}"
    filepath = os.path.join(logo_dir, filename)

    # Remover logo anterior se existir
    if company.logo_url:
        old_path = company.logo_url
        if os.path.exists(old_path):
            try:
                os.remove(old_path)
            except OSError:
                pass

    with open(filepath, "wb") as f:
        f.write(content)

    company.logo_url = filepath
    db.commit()

    return {
        "status": "uploaded",
        "company_id": company_id,
        "logo_url": filepath,
        "size_kb": round(len(content) / 1024, 1),
    }


@router.delete("/{company_id}/logo", status_code=status.HTTP_204_NO_CONTENT)
def delete_company_logo(
    company_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
):
    """
    Remove o logo da empresa

    **Requer:** Superuser
    """
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Empresa {company_id} nao encontrada"
        )

    if company.logo_url and os.path.exists(company.logo_url):
        try:
            os.remove(company.logo_url)
        except OSError:
            pass

    company.logo_url = None
    db.commit()


@router.get("/{company_id}/logo")
def get_company_logo(
    company_id: int,
    db: Session = Depends(get_db),
):
    """
    Retorna o arquivo do logo da empresa

    **Acesso:** Publico (logos nao sao dados sensiveis)
    """
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Empresa {company_id} nao encontrada"
        )

    if not company.logo_url or not os.path.exists(company.logo_url):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Logo nao encontrado"
        )

    ext = company.logo_url.rsplit(".", 1)[-1].lower()
    media_types = {
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "svg": "image/svg+xml",
        "webp": "image/webp",
    }

    return FileResponse(
        company.logo_url,
        media_type=media_types.get(ext, "application/octet-stream"),
    )


# ============================================
# Associar usuarios a empresas
# ============================================

@router.post("/{company_id}/users/{user_id}")
def assign_user_to_company(
    company_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
):
    """
    Associa um usuario a uma empresa

    **Requer:** Superuser
    """
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Empresa {company_id} nao encontrada"
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Usuario {user_id} nao encontrado"
        )

    user.company_id = company_id
    db.commit()

    return {
        "status": "assigned",
        "user_id": user_id,
        "company_id": company_id,
        "company_name": company.name,
    }


@router.get("/{company_id}/users")
def list_company_users(
    company_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Lista usuarios de uma empresa

    **Requer:** Superuser ou company_admin da mesma empresa
    """
    if not _is_company_admin_or_superuser(current_user, company_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso negado: superuser ou company_admin da empresa necessario"
        )

    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Empresa {company_id} nao encontrada"
        )

    users = db.query(User).filter(User.company_id == company_id).all()
    return [
        {
            "id": u.id,
            "name": u.name,
            "email": u.email,
            "status": u.status,
            "is_superuser": u.is_superuser,
            "roles": [r.name for r in u.roles],
        }
        for u in users
    ]


# ============================================
# Uso de IA / Custos
# ============================================

@router.get("/{company_id}/ai-usage", response_model=AIUsageSummaryResponse)
def get_company_ai_usage(
    company_id: int,
    days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Resumo de uso e custos de IA da empresa

    **Requer:** Superuser ou company_admin da mesma empresa
    """
    if not _is_company_admin_or_superuser(current_user, company_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso negado: superuser ou company_admin da empresa necessario"
        )

    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Empresa {company_id} nao encontrada"
        )

    summary = AIUsageService.get_company_usage_summary(db, company_id, days)
    return summary


@router.post("/me/users/{user_id}/roles/{role_name}")
def assign_role_in_my_company(
    user_id: int,
    role_name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users.manage")),
):
    """
    Atribui um role a um usuario da mesma empresa

    company_admin so pode atribuir roles: recruiter, viewer
    Superuser pode atribuir qualquer role

    **Requer permissao:** users.manage
    """
    if not current_user.company_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario nao esta associado a nenhuma empresa"
        )

    # company_admin nao pode atribuir roles privilegiados
    if not current_user.is_superuser and role_name not in COMPANY_ADMIN_ASSIGNABLE_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Sem permissao para atribuir role '{role_name}'. Roles permitidos: {', '.join(COMPANY_ADMIN_ASSIGNABLE_ROLES)}"
        )

    # Verificar que o usuario alvo pertence a mesma empresa
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Usuario {user_id} nao encontrado"
        )

    if not current_user.is_superuser and target_user.company_id != current_user.company_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario nao pertence a sua empresa"
        )

    # Verificar que o role existe
    role = db.query(Role).filter(Role.name == role_name).first()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Role '{role_name}' nao encontrado"
        )

    # Verificar se ja tem o role
    if role in target_user.roles:
        return {
            "status": "already_assigned",
            "user_id": user_id,
            "role": role_name,
            "message": f"Usuario ja possui o role '{role_name}'"
        }

    target_user.roles.append(role)
    db.commit()

    # Audit log
    audit = AuditLog(
        user_id=current_user.id,
        action="assign_role",
        entity="user",
        entity_id=user_id,
        metadata_json={
            "role": role_name,
            "assigned_by": current_user.email,
            "company_id": current_user.company_id,
        }
    )
    db.add(audit)
    db.commit()

    return {
        "status": "assigned",
        "user_id": user_id,
        "role": role_name,
        "message": f"Role '{role_name}' atribuido ao usuario {target_user.email}"
    }


@router.delete("/me/users/{user_id}/roles/{role_name}")
def remove_role_in_my_company(
    user_id: int,
    role_name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users.manage")),
):
    """
    Remove um role de um usuario da mesma empresa

    company_admin so pode remover roles: recruiter, viewer
    Superuser pode remover qualquer role

    **Requer permissao:** users.manage
    """
    if not current_user.company_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario nao esta associado a nenhuma empresa"
        )

    # company_admin nao pode remover roles privilegiados
    if not current_user.is_superuser and role_name not in COMPANY_ADMIN_ASSIGNABLE_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Sem permissao para remover role '{role_name}'. Roles permitidos: {', '.join(COMPANY_ADMIN_ASSIGNABLE_ROLES)}"
        )

    # Verificar que o usuario alvo pertence a mesma empresa
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Usuario {user_id} nao encontrado"
        )

    if not current_user.is_superuser and target_user.company_id != current_user.company_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario nao pertence a sua empresa"
        )

    # Verificar que o role existe
    role = db.query(Role).filter(Role.name == role_name).first()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Role '{role_name}' nao encontrado"
        )

    if role not in target_user.roles:
        return {
            "status": "not_assigned",
            "user_id": user_id,
            "role": role_name,
            "message": f"Usuario nao possui o role '{role_name}'"
        }

    target_user.roles.remove(role)
    db.commit()

    # Audit log
    audit = AuditLog(
        user_id=current_user.id,
        action="remove_role",
        entity="user",
        entity_id=user_id,
        metadata_json={
            "role": role_name,
            "removed_by": current_user.email,
            "company_id": current_user.company_id,
        }
    )
    db.add(audit)
    db.commit()

    return {
        "status": "removed",
        "user_id": user_id,
        "role": role_name,
        "message": f"Role '{role_name}' removido do usuario {target_user.email}"
    }


# ============================================
# Configuracoes por empresa (admin view)
# ============================================

@router.get("/{company_id}/settings")
def get_company_settings(
    company_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Retorna configuracoes personalizadas da empresa

    **Requer:** Superuser ou company_admin da mesma empresa
    """
    if not _is_company_admin_or_superuser(current_user, company_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso negado: superuser ou company_admin da empresa necessario"
        )
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Empresa {company_id} nao encontrada"
        )

    return {
        "company_id": company_id,
        "company_name": company.name,
        "plan": company.plan,
        "logo_url": company.logo_url,
        "settings": company.settings_json or {},
        "global_config": {
            "multi_tenant_enabled": settings.multi_tenant_enabled,
            "ai_pricing_enabled": settings.ai_pricing_enabled,
            "ai_currency": settings.ai_currency,
            "ai_monthly_token_limit": settings.ai_monthly_token_limit,
            "ai_monthly_cost_limit": settings.ai_monthly_cost_limit,
            "embedding_mode": settings.embedding_mode.value,
            "vector_db_provider": settings.vector_db_provider.value,
        },
    }


@router.put("/{company_id}/settings")
def update_company_settings(
    company_id: int,
    new_settings: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Atualiza configuracoes personalizadas da empresa

    **Requer:** Superuser ou company_admin da mesma empresa
    """
    if not _is_company_admin_or_superuser(current_user, company_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso negado: superuser ou company_admin da empresa necessario"
        )
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Empresa {company_id} nao encontrada"
        )

    current_settings = company.settings_json or {}
    current_settings.update(new_settings)
    company.settings_json = current_settings

    db.commit()
    db.refresh(company)

    return {
        "status": "updated",
        "company_id": company_id,
        "settings": company.settings_json,
    }
