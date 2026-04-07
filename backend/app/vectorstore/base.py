"""
Interface abstrata para Vector Store

Define o contrato que todos os provedores devem implementar.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


@dataclass
class VectorSearchResult:
    """Resultado de uma busca vetorial"""
    id: str
    score: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    content: Optional[str] = None


class VectorStore(ABC):
    """
    Interface abstrata para armazenamento e busca vetorial

    Todos os provedores (pgvector, Supabase, Qdrant) implementam esta interface.
    """

    @abstractmethod
    async def initialize(self) -> None:
        """
        Inicializa o store (criar colecao/tabela/indice se necessario).
        Chamado uma vez no startup da aplicacao.
        """
        ...

    @abstractmethod
    async def upsert(
        self,
        id: str,
        vector: List[float],
        metadata: Optional[Dict[str, Any]] = None,
        content: Optional[str] = None,
    ) -> None:
        """
        Insere ou atualiza um vetor

        Args:
            id: Identificador unico (chunk_id, etc.)
            vector: Vetor de embedding
            metadata: Metadados associados (candidate_id, section, etc.)
            content: Conteudo textual original (opcional)
        """
        ...

    @abstractmethod
    async def upsert_batch(
        self,
        ids: List[str],
        vectors: List[List[float]],
        metadatas: Optional[List[Dict[str, Any]]] = None,
        contents: Optional[List[str]] = None,
    ) -> None:
        """Insere ou atualiza vetores em lote"""
        ...

    @abstractmethod
    async def search(
        self,
        query_vector: List[float],
        limit: int = 10,
        threshold: float = 0.0,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[VectorSearchResult]:
        """
        Busca vetorial por similaridade

        Args:
            query_vector: Vetor de consulta
            limit: Numero maximo de resultados
            threshold: Similaridade minima (0-1)
            filters: Filtros de metadados (candidate_id, section, etc.)

        Returns:
            Lista de resultados ordenados por similaridade
        """
        ...

    @abstractmethod
    async def delete(self, id: str) -> None:
        """Remove um vetor pelo ID"""
        ...

    @abstractmethod
    async def delete_by_filter(self, filters: Dict[str, Any]) -> int:
        """
        Remove vetores por filtro de metadados

        Args:
            filters: Filtros (ex: {"document_id": 123})

        Returns:
            Numero de vetores removidos
        """
        ...

    @abstractmethod
    async def count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """Conta vetores, opcionalmente filtrados"""
        ...

    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """
        Verifica saude da conexao

        Returns:
            Dict com status, provider, versao, contagem, etc.
        """
        ...

    @abstractmethod
    async def get_info(self) -> Dict[str, Any]:
        """
        Retorna informacoes sobre o store

        Returns:
            Dict com provider, dimensoes, metrica, contagem, etc.
        """
        ...
