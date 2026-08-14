"""
Agente de orquestração do pipeline de ingestão.

Fluxo para documentos (PDF, DOCX, TXT, etc.):
    upload → router → document_preprocessor → vectorizer → DocumentChunk

Fluxo para imagens (JPG, PNG, etc.):
    upload → router → image_preprocessor → Gemini Vision (OCR) → vectorizer → DocumentChunk
"""

from rag_ocr.models import LegalDocument
from rag_ocr.pipeline.router import process_upload
from rag_ocr.pipeline.vectorizer import vectorize_document


def ingest_document(document: LegalDocument) -> int:
    """
    Orquestra o pipeline completo de ingestão para um LegalDocument já salvo no banco.

    Para imagens: o Gemini Vision faz o OCR e extrai o texto.
    Para documentos: pypdf/python-docx extrai o texto diretamente.

    Args:
        document: Instância de LegalDocument com o arquivo já salvo.

    Returns:
        Número de chunks criados no banco.

    Raises:
        ValueError: Se o arquivo não puder ser processado ou não houver texto extraído.
    """
    LegalDocument.objects.filter(pk=document.pk).update(processing_status="PROCESSING")

    try:
        with document.file.open("rb") as file_obj:
            nome_completo = f"{document.file_name}.{document.file_extension}"
            resultado = process_upload(file_obj, nome_completo)

        extracted_text = resultado.get("extracted_text") or ""

        # Para imagens: o texto ainda não foi extraído (prepare_image não faz OCR)
        # Usamos o Gemini Vision para realizar o OCR agora
        if not extracted_text and resultado.get("img_base64"):
            extracted_text = _ocr_via_gemini(
                imagem_base64=resultado["img_base64"],
                filename=document.file_name,
            )

        total_chunks = vectorize_document(
            document=document,
            text=extracted_text,
            page_count=resultado.get("page_count"),
        )

        LegalDocument.objects.filter(pk=document.pk).update(processing_status="PROCESSED")
        return total_chunks

    except Exception as exc:
        LegalDocument.objects.filter(pk=document.pk).update(processing_status="FAILED")
        raise exc


def _ocr_via_gemini(imagem_base64: str, filename: str) -> str:
    """
    Usa o Gemini Vision (multimodal) para extrair texto de uma imagem.

    Args:
        imagem_base64: Imagem codificada em base64.
        filename: Nome do arquivo (usado apenas para contexto no prompt).

    Returns:
        Texto extraído pelo modelo.
    """
    from django.conf import settings
    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain_core.messages import HumanMessage

    api_key = getattr(settings, "GOOGLE_API_KEY", "").strip()
    if not api_key:
        raise ValueError("GOOGLE_API_KEY não configurada para OCR via Gemini.")

    if not imagem_base64.startswith("data:"):
        imagem_base64 = f"data:image/jpeg;base64,{imagem_base64}"

    llm = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash",
        google_api_key=api_key,
        temperature=0.0,
    )

    mensagem = HumanMessage(
        content=[
            {
                "type": "text",
                "text": (
                    f"Extraia TODO o texto visível da imagem do documento jurídico '{filename}'. "
                    "Preserve a estrutura original: parágrafos, numerações, títulos e formatação. "
                    "Retorne apenas o texto extraído, sem comentários adicionais."
                ),
            },
            {
                "type": "image_url",
                "image_url": {"url": imagem_base64},
            },
        ]
    )

    resposta = llm.invoke([mensagem])
    return resposta.content