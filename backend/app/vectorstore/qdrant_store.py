"""
Implementacao do VectorStore para Qdrant

Qdrant e um banco de dados vetorial dedicado com:
- Alta performance para buscas vetoriais
- Filtros avancados de metadados
- Suporte a colecoes e sharding
- API REST e gRPC

Requer:
- pip install qdrant-client
- Servidor Qdrant rodando (Docker: docker run -p 6333:6333 qdrant/qdrant)
- Ou Qdrant Cloud (qdrant_url + qdrant_api_key)
"""
import logging
from typing import List, Optional, Dict, Any
from uuid import uuid4

from app.vectorstore.base import VectorStore, VectorSearchResult
from app.core.config import settings

logger = logging.getLogger(__name__)

try:
    from qdrant_client import QdrantClient, AsyncQdrantClient
    from qdrant_client.models import (
        Distance, VectorParams, PointStruct,
        Filter, FieldCondition, MatchValue,
        CollectionInfo, OptimizersConfigDiff,
    )
    QDRANT_AVAILABLE = True
except ImportError:
    QDRANT_AVAILABLE = False


class QdrantVectorStore(VectorStore):
    """
    VectorStore usando Qdrant

    Requer:
    - pip install qdrant-client
    - Variaveis: QDRANT_URL (e QDRANT_API_KEY para cloud)
    """

    def __init__(self):
        self._client: Optional[Any] = None

    def _get_client(self) -> Any:
        if not QDRANT_AVAILABLE:
            raise RuntimeError(
                "qdrant-client nao disponivel. Execute: pip install qdrant-client"
            )

        if self._client is None:
            if not settings.qdrant_url:
                raise ValueError("QDRANT_URL deve estar configurado")

            kwargs = {
                "url": settings.qdrant_url,
                "prefer_grpc": settings.qdrant_prefer_grpc,
            }
            if settings.qdrant_api_key:
                kwargs["api_key"] = settings.qdrant_api_key
            if settings.qdrant_grpc_port:
                kwargs["grpc_port"] = settings.qdrant_grpc_port

            self._client = QdrantClient(**kwargs)

        return self._client

    def _get_distance(self) -> Any:
        """Mapeia metrica de distancia para enum do Qdrant"""
        if not QDRANT_AVAILABLE:
            raise RuntimeError("qdrant-client nao disponivel")

        metric_map = {
            "cosine": Distance.COSINE,
            "l2": Distance.EUCLID,
            "inner_product": Distance.DOT,
        }
        return metric_map.get(settings.pgvector_distance_metric, Distance.COSINE)

    async def initialize(self) -> None:
        """Cria colecao no Qdrant se nao existir"""
        client = self._get_client()
        collection = settings.qdrant_collection_name

        try:
            collections = client.get_collections().collections
            collection_names = [c.name for c in collections]

            if collection not in collection_names:
                client.create_collection(
                    collection_name=collection,
                    vectors_config=VectorParams(
                        size=settings.embedding_dimensions,
                        distance=self._get_distance(),
                    ),
                    optimizers_config=OptimizersConfigDiff(
                        indexing_threshold=20000,
                    ),
                )
                logger.info(f"Qdrant collection '{collection}' created")

                # Criar indices para campos de filtro
                client.create_payload_index(
                    collection_name=collection,
                    field_name="candidate_id",
                    field_schema="integer",
                )
                client.create_payload_index(
                    collection_name=collection,
                    field_name="document_id",
                    field_schema="integer",
                )
                client.create_payload_index(
                    collection_name=collection,
                    field_name="section",
                    field_schema="keyword",
                )
                logger.info("Qdrant payload indices created")
            else:
                logger.info(f"Qdrant collection '{collection}' already exists")

        except Exception as e:
            logger.error(f"Error initializing Qdrant: {e}")
            raise

    async def upsert(
        self,
        id: str,
        vector: List[float],
        metadata: Optional[Dict[str, Any]] = None,
        content: Optional[str] = None,
    ) -> None:
        """Insere ou atualiza ponto no Qdrant"""
        client = self._get_client()

        payload = metadata.copy() if metadata else {}
        if content:
            payload["content"] = content
        payload["chunk_id"] = id

        # Qdrant usa IDs numericos ou UUID
        try:
            point_id = int(id)
        except (ValueError, TypeError):
            point_id = str(uuid4())

        client.upsert(
            collection_name=settings.qdrant_collection_name,
            points=[
                PointStruct(
                    id=point_id,
                    vector=vector,
                    payload=payload,
                )
            ],
        )

    async def upsert_batch(
        self,
        ids: List[str],
        vectors: List[List[float]],
        metadatas: Optional[List[Dict[str, Any]]] = None,
        contents: Optional[List[str]] = None,
    ) -> None:
        """Insere pontos em lote no Qdrant"""
        client = self._get_client()

        points = []
        for i, (id_val, vector) in enumerate(zip(ids, vectors)):
            payload = metadatas[i].copy() if metadatas else {}
            if contents and i < len(contents):
                payload["content"] = contents[i]
            payload["chunk_id"] = id_val

            try:
                point_id = int(id_val)
            except (ValueError, TypeError):
                point_id = str(uuid4())

            points.append(PointStruct(
                id=point_id,
                vector=vector,
                payload=payload,
            ))

        # Qdrant suporta batch de ate 100 pontos por chamada
        batch_size = 100
        for i in range(0, len(points), batch_size):
            batch = points[i:i + batch_size]
            client.upsert(
                collection_name=settings.qdrant_collection_name,
                points=batch,
            )

    async def search(
        self,
        query_vector: List[float],
        limit: int = 10,
        threshold: float = 0.0,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[VectorSearchResult]:
        """Busca vetorial no Qdrant"""
        client = self._get_client()

        # Construir filtros Qdrant
        qdrant_filter = None
        if filters:
            conditions = []
            for key, value in filters.items():
                if value is not None:
                    conditions.append(
                        FieldCondition(
                            key=key,
                            match=MatchValue(value=value),
                        )
                    )
            if conditions:
                qdrant_filter = Filter(must=conditions)

        results = client.search(
            collection_name=settings.qdrant_collection_name,
            query_vector=query_vector,
            query_filter=qdrant_filter,
            limit=limit,
            score_threshold=threshold if threshold > 0 else None,
        )

        return [
            VectorSearchResult(
                id=str(hit.payload.get("chunk_id", hit.id)),
                score=float(hit.score),
                metadata={
                    k: v for k, v in hit.payload.items()
                    if k not in ("content", "chunk_id")
                },
                content=hit.payload.get("content"),
            )
            for hit in results
        ]

    async def delete(self, id: str) -> None:
        """Remove ponto do Qdrant"""
        client = self._get_client()

        try:
            point_id = int(id)
        except (ValueError, TypeError):
            # Buscar pelo chunk_id no payload
            results = client.scroll(
                collection_name=settings.qdrant_collection_name,
                scroll_filter=Filter(
                    must=[FieldCondition(key="chunk_id", match=MatchValue(value=id))]
                ),
                limit=1,
            )
            if results[0]:
                point_id = results[0][0].id
            else:
                return

        client.delete(
            collection_name=settings.qdrant_collection_name,
            points_selector=[point_id],
        )

    async def delete_by_filter(self, filters: Dict[str, Any]) -> int:
        """Remove pontos por filtro"""
        client = self._get_client()

        conditions = []
        for key, value in filters.items():
            if value is not None:
                conditions.append(
                    FieldCondition(key=key, match=MatchValue(value=value))
                )

        if not conditions:
            return 0

        qdrant_filter = Filter(must=conditions)

        # Contar antes de deletar
        count_before = await self.count(filters)

        client.delete(
            collection_name=settings.qdrant_collection_name,
            points_selector=qdrant_filter,
        )

        return count_before

    async def count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """Conta pontos no Qdrant"""
        client = self._get_client()

        if filters:
            conditions = []
            for key, value in filters.items():
                if value is not None:
                    conditions.append(
                        FieldCondition(key=key, match=MatchValue(value=value))
                    )
            if conditions:
                result = client.count(
                    collection_name=settings.qdrant_collection_name,
                    count_filter=Filter(must=conditions),
                )
                return result.count

        result = client.count(
            collection_name=settings.qdrant_collection_name,
        )
        return result.count

    async def health_check(self) -> Dict[str, Any]:
        """Verifica saude do Qdrant"""
        try:
            client = self._get_client()
            collection_info = client.get_collection(settings.qdrant_collection_name)

            return {
                "status": "healthy",
                "provider": "qdrant",
                "url": settings.qdrant_url,
                "collection": settings.qdrant_collection_name,
                "embeddings_count": collection_info.points_count,
                "dimensions": settings.embedding_dimensions,
                "distance": settings.pgvector_distance_metric,
                "indexed": collection_info.status.value if hasattr(collection_info.status, 'value') else str(collection_info.status),
            }
        except Exception as e:
            return {"status": "unhealthy", "provider": "qdrant", "error": str(e)}

    async def get_info(self) -> Dict[str, Any]:
        """Retorna info do Qdrant"""
        health = await self.health_check()
        return {
            **health,
            "grpc_port": settings.qdrant_grpc_port,
            "prefer_grpc": settings.qdrant_prefer_grpc,
            "sdk_available": QDRANT_AVAILABLE,
        }
