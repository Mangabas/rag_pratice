"""
Comando de indexação de documentos jurídicos no banco vetorial.

Uso:
    python manage.py index_docs                          # indexa documentos pendentes
    python manage.py index_docs --force                  # reindexa todos (inclusive já processados)
    python manage.py index_docs --dry-run                # simula sem gravar no banco
    python manage.py index_docs --document-id <uuid>     # indexa um documento específico

Fluxo por tipo de arquivo:
    PDF / DOCX / TXT / MD / CSV:
        1. Extrai texto via pypdf / python-docx / built-in
        2. Divide em chunks (RecursiveCharacterTextSplitter)
        3. Gera embeddings via Gemini (gemini-embedding-001, 768 dims)
        4. Salva em DocumentChunk (substitui os chunks anteriores)

    JPG / PNG / WEBP:
        1. Converte para JPEG padronizado (Pillow)
        2. Envia imagem ao Gemini Vision para OCR
        3. Divide o texto extraído em chunks
        4. Gera embeddings e salva em DocumentChunk

Requisitos:
    - GOOGLE_API_KEY no .env
    - pgvector habilitado no PostgreSQL (migration 0001)
    - LegalDocuments já salvos no banco (via upload pela API ou Admin)
"""

from django.core.management.base import BaseCommand

from rag_ocr.models import LegalDocument
from rag_ocr.pipeline.llm_agent import ingest_document


class Command(BaseCommand):
    help = "Indexa LegalDocuments pendentes (ou todos com --force) na tabela vetorial DocumentChunk"

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Reindexa todos os documentos, inclusive os já processados",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Lista os documentos que seriam indexados sem alterar o banco",
        )
        parser.add_argument(
            "--document-id",
            type=str,
            default=None,
            metavar="UUID",
            help="Indexa apenas o documento com o UUID informado",
        )

    def handle(self, *args, **options):
        forcar = options["force"]
        simulacao = options["dry_run"]
        doc_id = options["document_id"]

        # Monta o queryset base
        qs = LegalDocument.objects.all()

        if doc_id:
            qs = qs.filter(pk=doc_id)
            if not qs.exists():
                self.stderr.write(self.style.ERROR(f"Documento não encontrado: {doc_id}"))
                return
        elif not forcar:
            qs = qs.filter(processing_status__in=["PENDING", "FAILED"])

        documentos = list(qs.order_by("created_at"))

        if not documentos:
            self.stdout.write(self.style.WARNING(
                "Nenhum documento pendente encontrado. "
                "Use --force para reindexar todos ou faça o upload de novos documentos."
            ))
            return

        self.stdout.write(
            f"Encontrado(s): {len(documentos)} documento(s) para indexar."
        )

        if simulacao:
            self.stdout.write(self.style.WARNING("SIMULAÇÃO — nenhuma alteração será salva.\n"))
            for doc in documentos:
                self.stdout.write(
                    f"  [DRY-RUN] {doc.file_name} "
                    f"(tipo: {doc.document_type}, status: {doc.processing_status})"
                )
            return

        total_chunks = 0
        erros = 0

        for doc in documentos:
            self.stdout.write(f"\n  [INDEXANDO] {doc.file_name} ({doc.document_type})")

            try:
                n_chunks = ingest_document(doc)
                total_chunks += n_chunks
                self.stdout.write(self.style.SUCCESS(
                    f"    ✓ {n_chunks} chunk(s) criado(s)"
                ))

            except ValueError as exc:
                erros += 1
                self.stderr.write(self.style.ERROR(f"    ✗ Erro de validação: {exc}"))

            except Exception as exc:
                erros += 1
                self.stderr.write(self.style.ERROR(f"    ✗ Erro inesperado: {exc}"))

        self.stdout.write("\n" + "─" * 50)
        self.stdout.write(self.style.SUCCESS(
            f"Indexação concluída: {total_chunks} chunk(s) salvos, {erros} erro(s)."
        ))

        if erros:
            self.stdout.write(
                "  Os documentos com erro ficaram com status=FAILED. "
                "Corrija o problema e re-execute com --force."
            )
