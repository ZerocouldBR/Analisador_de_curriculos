"""
Servico de embeddings local usando sentence-transformers

Vetorizacao em codigo (sem API externa), usando modelos
como all-MiniLM-L6-v2 rodando localmente.

Todas as configuracoes vem de app.core.config.settings.
"""
import logging
from typing import List, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

# Cache global do modelo
_model = None


def _get_model():
    """Carrega o modelo sentence-transformers (lazy loading)"""
    global _model
    if _model is not None:
        return _model

    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        raise RuntimeError(
            "sentence-transformers nao instalado. "
            "Instale com: pip install sentence-transformers"
        )

    model_name = settings.embedding_local_model
    device = settings.embedding_local_device

    logger.info(f"Carregando modelo local: {model_name} (device={device})")
    _model = SentenceTransformer(model_name, device=device)
    logger.info(f"Modelo carregado. Dimensoes: {_model.get_sentence_embedding_dimension()}")

    return _model


class LocalEmbeddingService:
    """
    Gera embeddings usando sentence-transformers localmente.

    Nao faz chamadas de API - todo processamento e local.
    Custo zero de API, mas requer mais CPU/GPU.
    """

    @staticmethod
    def generate_embedding(text: str) -> List[float]:
        """Gera embedding para um texto"""
        model = _get_model()
        max_chars = settings.embedding_max_chars
        if len(text) > max_chars:
            text = text[:max_chars]

        embedding = model.encode(text, normalize_embeddings=True)
        return embedding.tolist()

    @staticmethod
    def generate_embeddings_batch(
        texts: List[str],
        batch_size: Optional[int] = None,
    ) -> List[List[float]]:
        """Gera embeddings em lote"""
        model = _get_model()
        _batch_size = batch_size or settings.embedding_batch_size
        max_chars = settings.embedding_max_chars

        processed = [t[:max_chars] for t in texts]

        embeddings = model.encode(
            processed,
            batch_size=_batch_size,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return [e.tolist() for e in embeddings]

    @staticmethod
    def get_dimensions() -> int:
        """Retorna dimensoes do modelo local"""
        model = _get_model()
        return model.get_sentence_embedding_dimension()
