from django.conf import settings
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from rag_ocr.models import DocumentChunk, LegalDocument

CHUNK_SIZE = 700
CHUNK_OVERLAP = 100
EMBEDDING_MODEL = "models/text-embedding-004"


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


def vectorize_document(document: LegalDocument, extraction_result: dict) -> int:
    """
    Divide o texto em chunks por página, gera embeddings e salva os DocumentChunk com metadados.
    """
    pages_data = extraction_result.get("pages_data", [])
    page_count = extraction_result.get("page_count")

    if not pages_data:
        raise ValueError(f"Texto vazio para o documento '{document.file_name}'. Nenhum chunk criado.")

    if page_count is not None:
        LegalDocument.objects.filter(pk=document.pk).update(page_count=page_count)

    # Filtra os metadados removendo chaves vazias
    raw_metadata = {
        "subject": extraction_result.get("subject"),
        "keywords": extraction_result.get("keywords"),
        "creator": extraction_result.get("creator"),
        "producer": extraction_result.get("producer"),
        "creation_date": extraction_result.get("creation_date"),
        "modification_date": extraction_result.get("modification_date"),
    }
    chunk_metadata = {k: v for k, v in raw_metadata.items() if v is not None}

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ".", " ", ""],
    )

    all_trechos = []
    all_page_numbers = []

    # Processa os chunks respeitando os limites das páginas
    for page in pages_data:
        text = page.get("text", "")
        if not text.strip():
            continue
            
        trechos = splitter.split_text(text)
        all_trechos.extend(trechos)
        all_page_numbers.extend([page.get("page_number")] * len(trechos))

    if not all_trechos:
        raise ValueError(f"Nenhum trecho gerado para '{document.file_name}'.")

    embeddings_client = _get_embeddings()
    vetores = embeddings_client.embed_documents(all_trechos)

    DocumentChunk.objects.filter(document=document).delete()

    chunks = [
        DocumentChunk(
            document=document,
            content=trecho,
            chunk_index=i,
            page_number=page_num,
            embedding=vetor,
            embedding_model=EMBEDDING_MODEL,
            metadata=chunk_metadata,
        )
        for i, (trecho, vetor, page_num) in enumerate(zip(all_trechos, vetores, all_page_numbers))
    ]
    
    DocumentChunk.objects.bulk_create(chunks)

    return len(chunks)