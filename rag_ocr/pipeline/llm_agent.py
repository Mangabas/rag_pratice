from django.conf import settings
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage

from rag_ocr.models import LegalDocument
from rag_ocr.pipeline.router import process_upload
from rag_ocr.pipeline.vectorizer import vectorize_document


def ingest_document(document: LegalDocument) -> int:
    """
    Orquestra o pipeline completo de ingestão para um LegalDocument já salvo no banco.
    Para imagens: o Gemini Vision faz o OCR e extrai o texto.
    Para documentos: pypdf/python-docx extrai o texto diretamente.
    """
    LegalDocument.objects.filter(pk=document.pk).update(processing_status="PROCESSING")

    try:
        with document.file.open("rb") as file_obj:
            nome_completo = f"{document.file_name}.{document.file_extension}"
            resultado = process_upload(file_obj, nome_completo)

        extracted_text = resultado.get("extracted_text") or ""

        # OCR via Gemini para imagens sem texto extraível nativamente
        if not extracted_text and resultado.get("img_base64"):
            extracted_text = _ocr_via_gemini(
                imagem_base64=resultado["img_base64"],
                filename=document.file_name,
            )
            # Insere a estrutura de páginas para que o vectorizer consiga processar imagens
            resultado["pages_data"] = [{"text": extracted_text, "page_number": 1}]
            resultado["page_count"] = 1
            resultado["extracted_text"] = extracted_text

        total_chunks = vectorize_document(
            document=document,
            extraction_result=resultado,
        )

        LegalDocument.objects.filter(pk=document.pk).update(processing_status="PROCESSED")
        return total_chunks

    except Exception as exc:
        LegalDocument.objects.filter(pk=document.pk).update(processing_status="FAILED")
        raise exc


def _ocr_via_gemini(imagem_base64: str, filename: str) -> str:
    """
    Usa o Gemini Vision (multimodal) para extrair texto de uma imagem.
    """
    api_key = getattr(settings, "GOOGLE_API_KEY", "").strip()
    if not api_key:
        raise ValueError("GOOGLE_API_KEY não configurada para OCR via Gemini.")

    if not imagem_base64.startswith("data:"):
        imagem_base64 = f"data:image/jpeg;base64,{imagem_base64}"

    llm = ChatGoogleGenerativeAI(
        model="gemini-3.6-flash",
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
    conteudo = resposta.content
    if isinstance(conteudo, list):
        texto_final = ""
        for bloco in conteudo:
            if isinstance(bloco, str):
                texto_final += bloco
            elif isinstance(bloco, dict) and "text" in bloco:
                texto_final += bloco["text"]
        return texto_final
    return str(conteudo)