"""
Servico de rastreamento de uso e custos de IA

Registra todos os usos de API de IA (embeddings, chat, LLM)
e calcula custos por empresa/usuario.

Todas as configuracoes de precos vem de app.core.config.settings.
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.config import settings
from app.db.models import AIUsageLog

logger = logging.getLogger(__name__)


class AIUsageService:
    """Rastreia uso e custos de IA por empresa e usuario"""

    @staticmethod
    def calculate_cost(
        operation: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
    ) -> Dict[str, float]:
        """
        Calcula custo baseado na operacao e tokens

        Returns:
            Dict com cost_usd e cost_local
        """
        cost_usd = 0.0

        if operation == "embedding":
            cost_usd = (input_tokens / 1000) * settings.ai_price_embedding_input
        elif operation == "chat":
            cost_usd = (
                (input_tokens / 1000) * settings.ai_price_chat_input
                + (output_tokens / 1000) * settings.ai_price_chat_output
            )
        elif operation in ("llm_query", "job_analysis"):
            cost_usd = (
                (input_tokens / 1000) * settings.ai_price_llm_input
                + (output_tokens / 1000) * settings.ai_price_llm_output
            )

        cost_local = cost_usd * settings.ai_currency_exchange_rate

        return {
            "cost_usd": round(cost_usd, 8),
            "cost_local": round(cost_local, 6),
        }

    @staticmethod
    def log_usage(
        db: Session,
        company_id: int,
        operation: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        model: Optional[str] = None,
        user_id: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AIUsageLog:
        """
        Registra uso de IA no banco

        Args:
            db: Sessao do banco
            company_id: ID da empresa
            operation: Tipo de operacao (embedding, chat, llm_query, job_analysis)
            input_tokens: Tokens de entrada
            output_tokens: Tokens de saida
            model: Modelo utilizado
            user_id: ID do usuario (opcional)
            metadata: Dados extras
        """
        if not settings.ai_pricing_enabled:
            return None

        total_tokens = input_tokens + output_tokens
        costs = AIUsageService.calculate_cost(operation, input_tokens, output_tokens)

        log = AIUsageLog(
            company_id=company_id,
            user_id=user_id,
            operation=operation,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            cost_usd=costs["cost_usd"],
            cost_local=costs["cost_local"],
            currency=settings.ai_currency,
            metadata_json=metadata,
        )
        db.add(log)
        db.commit()
        db.refresh(log)
        return log

    @staticmethod
    def get_company_usage_summary(
        db: Session,
        company_id: int,
        days: int = 30,
    ) -> Dict[str, Any]:
        """
        Resume de uso de IA da empresa nos ultimos N dias

        Returns:
            Dict com totais de tokens, custos por operacao, etc.
        """
        since = datetime.now(timezone.utc) - timedelta(days=days)

        logs = db.query(
            AIUsageLog.operation,
            func.sum(AIUsageLog.input_tokens).label("total_input"),
            func.sum(AIUsageLog.output_tokens).label("total_output"),
            func.sum(AIUsageLog.total_tokens).label("total_tokens"),
            func.sum(AIUsageLog.cost_usd).label("total_cost_usd"),
            func.sum(AIUsageLog.cost_local).label("total_cost_local"),
            func.count(AIUsageLog.id).label("request_count"),
        ).filter(
            AIUsageLog.company_id == company_id,
            AIUsageLog.created_at >= since,
        ).group_by(AIUsageLog.operation).all()

        by_operation = {}
        total_tokens = 0
        total_cost_usd = 0.0
        total_cost_local = 0.0
        total_requests = 0

        for row in logs:
            by_operation[row.operation] = {
                "input_tokens": row.total_input or 0,
                "output_tokens": row.total_output or 0,
                "total_tokens": row.total_tokens or 0,
                "cost_usd": round(float(row.total_cost_usd or 0), 6),
                "cost_local": round(float(row.total_cost_local or 0), 4),
                "request_count": row.request_count,
            }
            total_tokens += row.total_tokens or 0
            total_cost_usd += float(row.total_cost_usd or 0)
            total_cost_local += float(row.total_cost_local or 0)
            total_requests += row.request_count

        # Verificar limites
        limits = {}
        if settings.ai_monthly_token_limit > 0:
            limits["monthly_token_limit"] = settings.ai_monthly_token_limit
            limits["tokens_used"] = total_tokens
            limits["tokens_remaining"] = max(0, settings.ai_monthly_token_limit - total_tokens)
            limits["token_usage_pct"] = round(
                (total_tokens / settings.ai_monthly_token_limit) * 100, 1
            )

        if settings.ai_monthly_cost_limit > 0:
            limits["monthly_cost_limit"] = settings.ai_monthly_cost_limit
            limits["cost_used"] = round(total_cost_local, 4)
            limits["cost_remaining"] = round(
                max(0, settings.ai_monthly_cost_limit - total_cost_local), 4
            )
            limits["cost_usage_pct"] = round(
                (total_cost_local / settings.ai_monthly_cost_limit) * 100, 1
            )

        return {
            "company_id": company_id,
            "period_days": days,
            "currency": settings.ai_currency,
            "exchange_rate": settings.ai_currency_exchange_rate,
            "total_tokens": total_tokens,
            "total_cost_usd": round(total_cost_usd, 6),
            "total_cost_local": round(total_cost_local, 4),
            "total_requests": total_requests,
            "by_operation": by_operation,
            "limits": limits,
            "pricing": {
                "embedding_input_per_1k": settings.ai_price_embedding_input,
                "llm_input_per_1k": settings.ai_price_llm_input,
                "llm_output_per_1k": settings.ai_price_llm_output,
                "chat_input_per_1k": settings.ai_price_chat_input,
                "chat_output_per_1k": settings.ai_price_chat_output,
            },
        }

    @staticmethod
    def check_limits(
        db: Session,
        company_id: int,
    ) -> Dict[str, Any]:
        """
        Verifica se a empresa atingiu limites de uso

        Returns:
            Dict com allowed (bool) e motivo se bloqueado
        """
        if settings.ai_monthly_token_limit == 0 and settings.ai_monthly_cost_limit == 0:
            return {"allowed": True}

        since = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        totals = db.query(
            func.sum(AIUsageLog.total_tokens).label("total_tokens"),
            func.sum(AIUsageLog.cost_local).label("total_cost"),
        ).filter(
            AIUsageLog.company_id == company_id,
            AIUsageLog.created_at >= since,
        ).first()

        used_tokens = totals.total_tokens or 0
        used_cost = float(totals.total_cost or 0)

        if settings.ai_monthly_token_limit > 0 and used_tokens >= settings.ai_monthly_token_limit:
            return {
                "allowed": False,
                "reason": "token_limit_exceeded",
                "used": used_tokens,
                "limit": settings.ai_monthly_token_limit,
            }

        if settings.ai_monthly_cost_limit > 0 and used_cost >= settings.ai_monthly_cost_limit:
            return {
                "allowed": False,
                "reason": "cost_limit_exceeded",
                "used": round(used_cost, 4),
                "limit": settings.ai_monthly_cost_limit,
            }

        return {"allowed": True}
