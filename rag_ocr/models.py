import uuid

from django.conf import settings
from django.db import models

from pgvector.django import VectorField


class LegalDocument(models.Model):
    class DocumentType(models.TextChoices):
        ADI = "ADI", "Ação Direta de Inconstitucionalidade"
        ADC = "ADC", "Ação Declaratória de Constitucionalidade"
        ADPF = "ADPF", "Arguição de Descumprimento de Preceito Fundamental"
        ADO = "ADO", "Ação Direta de Inconstitucionalidade por Omissão"
        OUTRO = "OUTRO", "Outro"

    class ProcessingStatus(models.TextChoices):
        PENDING = "PENDING", "Pendente"
        PROCESSING = "PROCESSING", "Processando"
        PROCESSED = "PROCESSED", "Processado"
        FAILED = "FAILED", "Falhou"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    file = models.FileField(upload_to="legal_documents/%Y/%m/")
    file_name = models.CharField(max_length=255)
    document_type = models.CharField(max_length=10, choices=DocumentType.choices, default=DocumentType.OUTRO)
    file_extension = models.CharField(max_length=10, blank=True)
    author = models.CharField(max_length=50, blank=True)
    keywords = models.JSONField(default=list, blank=True)
    page_count = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.document_type} - {self.file_name}"


class DocumentChunk(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(LegalDocument, on_delete=models.CASCADE, related_name="chunks")
    content = models.TextField()
    chunk_index = models.PositiveIntegerField()
    page_number = models.PositiveIntegerField(null=True, blank=True)
    token_count = models.PositiveIntegerField(null=True, blank=True)
    embedding = VectorField(dimensions=1024, null=True, blank=True)
    embedding_model = models.CharField(max_length=100, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["document", "chunk_index"]
        constraints = [
            models.UniqueConstraint(
                fields=["document", "chunk_index"], name="unique_chunk_per_document"
            )
        ]

    def __str__(self):
        return f"{self.document_id} - chunk {self.chunk_index}"


class Conversation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="conversations")
    title = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return self.title or f"Conversa {self.id}"


class Query(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="queries",
        null=True,
        blank=True,
    )
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="queries")
    question = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return self.question[:80]


class Answer(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    query = models.OneToOneField(Query, on_delete=models.CASCADE, related_name="answer")
    content = models.TextField()
    model_used = models.CharField(max_length=100, blank=True)
    latency_ms = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Resposta para {self.query_id}"


class AnswerCitation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    answer = models.ForeignKey(Answer, on_delete=models.CASCADE, related_name="citations_answer")
    chunk = models.ForeignKey(DocumentChunk, on_delete=models.PROTECT, related_name="citations_chunk")
    relevance_score = models.FloatField(null=True, blank=True)
    excerpt = models.TextField(blank=True)

    class Meta:
        ordering = ["-relevance_score"]

    def __str__(self):
        return f"Citação de {self.chunk_id} em {self.answer_id}"
