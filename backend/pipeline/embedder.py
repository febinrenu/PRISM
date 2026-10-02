"""
Sentence embeddings using all-MiniLM-L6-v2 + UMAP 2D projection.
Model is loaded once at startup and reused across requests.
"""
import numpy as np

_model = None


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def embed_texts(texts: list[str]) -> np.ndarray:
    """
    Generate sentence embeddings for a list of texts.
    Returns numpy array of shape (N, 384).
    """
    if not texts:
        return np.zeros((0, 384), dtype=np.float32)
    model = _get_model()
    return model.encode(
        texts,
        batch_size=32,
        show_progress_bar=False,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )


def project_umap(embeddings: np.ndarray) -> np.ndarray:
    """
    Project high-dim embeddings to 2D using UMAP.
    Returns numpy array of shape (N, 2).
    Falls back to PCA or random if UMAP fails.
    """
    n = len(embeddings)

    if n < 2:
        return np.zeros((n, 2), dtype=float)

    if n == 2:
        return np.array([[0.0, 0.0], [1.0, 0.0]])

    # Validate embeddings — replace NaN/Inf with zeros
    embeddings = np.nan_to_num(embeddings, nan=0.0, posinf=0.0, neginf=0.0)

    try:
        import umap
        n_neighbors = min(15, n - 1)
        reducer = umap.UMAP(
            n_components=2,
            n_neighbors=n_neighbors,
            min_dist=0.1,
            metric="cosine",
            random_state=42,
            low_memory=True,
        )
        projected = reducer.fit_transform(embeddings)
    except Exception:
        # Fallback: PCA
        try:
            from sklearn.decomposition import PCA
            pca = PCA(n_components=2, random_state=42)
            projected = pca.fit_transform(embeddings)
        except Exception:
            # Last resort: random 2D positions
            rng = np.random.default_rng(42)
            projected = rng.uniform(-5, 5, (n, 2))

    # Normalize to [-10, 10] range
    for dim in range(2):
        col = projected[:, dim]
        col_min, col_max = col.min(), col.max()
        if col_max > col_min:
            projected[:, dim] = (col - col_min) / (col_max - col_min) * 20 - 10

    return projected
