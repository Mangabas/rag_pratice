from rest_framework import serializers

from .models import (
    Answer,
    AnswerCitation,
    Conversation,
    DocumentChunk,
    LegalDocument,
    Query,
)


class LegalDocumentSerializer(serializers.ModelSerializer):
    chunk_count = serializers.IntegerField(source="chunks.count", read_only=True)

    class Meta:
        model = LegalDocument
        fields = [
            "id", "file", "file_name", "document_type", "file_extension",
            "author", "keywords", "page_count", "chunk_count",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "page_count", "chunk_count", "created_at", "updated_at"]


class LegalDocumentUploadSerializer(serializers.ModelSerializer):
    # Serializer usado na criação (upload) do documento.

    EXTENSOES_PERMITIDAS = {
        "pdf", "docx", "txt", "md", "csv",   # documentos
        "jpg", "jpeg", "png", "webp",          # imagens
    }

    class Meta:
        model = LegalDocument
        fields = ["file", "document_type"]

    def validate_file(self, value):
        extensao = value.name.rsplit(".", 1)[-1].lower()
        if extensao not in self.EXTENSOES_PERMITIDAS:
            permitidas = ", ".join(sorted(self.EXTENSOES_PERMITIDAS))
            raise serializers.ValidationError(
                f"Extensão '.{extensao}' não suportada. Permitidas: {permitidas}"
            )
        return value

    def create(self, validated_data):
        uploaded_file = validated_data["file"]
        name, _, ext = uploaded_file.name.rpartition(".")
        validated_data.setdefault("file_name", name or uploaded_file.name)
        validated_data.setdefault("file_extension", ext.lower())
        return super().create(validated_data)


class DocumentChunkSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentChunk
        fields = [
            "id", "document", "content", "chunk_index",
            "page_number", "token_count", "embedding_model",
            "metadata", "created_at",
        ]
        read_only_fields = fields


class AnswerCitationSerializer(serializers.ModelSerializer):
    document_file_name = serializers.CharField(source="chunk.document.file_name", read_only=True)
    page_number = serializers.IntegerField(source="chunk.page_number", read_only=True)

    class Meta:
        model = AnswerCitation
        fields = [
            "id", "chunk", "document_file_name",
            "page_number", "relevance_score", "excerpt",
        ]
        read_only_fields = fields


class AnswerSerializer(serializers.ModelSerializer):
    citations = AnswerCitationSerializer(source="citations_answer", many=True, read_only=True)

    class Meta:
        model = Answer
        fields = ["id", "content", "model_used", "latency_ms", "citations", "created_at"]
        read_only_fields = fields


class QuerySerializer(serializers.ModelSerializer):
    # exibe uma pergunta já feita, com a resposta aninhada (se existir).
    answer = AnswerSerializer(read_only=True)

    class Meta:
        model = Query
        fields = ["id", "conversation", "user", "question", "answer", "created_at"]
        read_only_fields = ["id", "user", "answer", "created_at"]


class QueryCreateSerializer(serializers.Serializer):
    """
    Input do endpoint de pergunta. A criação da Answer depende do
    pipeline de RAG, por isso não é um ModelSerializer.
    """

    conversation = serializers.PrimaryKeyRelatedField(
        queryset=Conversation.objects.all(), required=False, allow_null=True
    )
    question = serializers.CharField(min_length=3, max_length=4000)


class ConversationSerializer(serializers.ModelSerializer):
    queries = QuerySerializer(many=True, read_only=True)

    class Meta:
        model = Conversation
        fields = ["id", "title", "queries", "created_at", "updated_at"]
        read_only_fields = ["id", "queries", "created_at", "updated_at"]
