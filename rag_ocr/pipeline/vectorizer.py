"""
Módulo de vetorização: divide texto em chunks e gera embeddings.

Responsabilidades:
    1. Dividir o texto extraído em trechos menores (chunking)
    2. Gerar o vetor de embedding de cada trecho via Gemini
    3. Salvar os DocumentChunk vinculados ao LegalDocument
"""

from django.conf import settings
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from rag_ocr.models import DocumentChunk, LegalDocument

CHUNK_SIZE = 700
CHUNK_OVERLAP = 100
EMBEDDING_MODEL = "gemini-embedding-001"


def _get_embeddings() -> GoogleGenerativeAIEmbeddings:
    api_key = getattr(settings, "GOOGLE_API_KEY", "").strip()
    if not api_key:
        raise ValueError(
            "GOOGLE_API_KEY não encontrada nas configurações. "
            "Adicione a chave no arquivo .env do projeto."
        )
    return GoogleGenerativeAIEmbeddings(
        model=EMBEDDING_MODEL,
        google_api_key=api_key,
    )


def vectorize_document(document: LegalDocument, text: str, page_count: int = None) -> int:
    """
    Divide o texto em chunks, gera embeddings e salva os DocumentChunk no banco.

    Args:
        document: Instância de LegalDocument já salva no banco.
        text: Texto extraído do documento.
        page_count: Número de páginas (opcional, para PDF/DOCX).

    Returns:
        Número de chunks criados.

    Raises:
        ValueError: Se o texto estiver vazio ou a chave de API não estiver configurada.
    """
    if not text or not text.strip():
        raise ValueError(f"Texto vazio para o documento '{document.file_name}'. Nenhum chunk criado.")

    # Atualiza page_count se fornecido
    if page_count is not None:
        LegalDocument.objects.filter(pk=document.pk).update(page_count=page_count)

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ".", " ", ""],
    )
    trechos = splitter.split_text(text)

    if not trechos:
        raise ValueError(f"Nenhum trecho gerado para '{document.file_name}'.")

    embeddings_client = _get_embeddings()
    vetores = embeddings_client.embed_documents(trechos)

    # Substitui os chunks anteriores do mesmo documento
    DocumentChunk.objects.filter(document=document).delete()

    chunks = [
        DocumentChunk(
            document=document,
            content=trecho,
            chunk_index=i,
            embedding=vetor,
            embedding_model=EMBEDDING_MODEL,
        )
        for i, (trecho, vetor) in enumerate(zip(trechos, vetores))
    ]
    DocumentChunk.objects.bulk_create(chunks)

    return len(chunks)