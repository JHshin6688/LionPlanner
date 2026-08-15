from src.config import get_embedding_model


def embed_syllabus_summary(syllabus_summary: str) -> list[float]:
    """Embed the (short, already-condensed) syllabus_summary as a single vector -
    no chunking, since syllabus_summary is a few sentences, not a full document."""
    if not syllabus_summary:
        return []

    embedding_model = get_embedding_model()
    return embedding_model.embed_query(syllabus_summary)
