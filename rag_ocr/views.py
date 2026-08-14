from rest_framework import permissions, status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Conversation, DocumentChunk, LegalDocument, Query
from .serializers import (
    ConversationSerializer,
    DocumentChunkSerializer,
    LegalDocumentSerializer,
    LegalDocumentUploadSerializer,
    QueryCreateSerializer,
    QuerySerializer,
)


class IsStaffOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return bool(request.user and request.user.is_authenticated)
        return bool(request.user and request.user.is_staff)


class LegalDocumentViewSet(viewsets.ModelViewSet):
    queryset = LegalDocument.objects.all()
    permission_classes = [permissions.AllowAny]
    filterset_fields = ["document_type"]

    def get_serializer_class(self):
        if self.action == "create":
            return LegalDocumentUploadSerializer
        return LegalDocumentSerializer

    def perform_create(self, serializer):
        document = serializer.save()
        # Chama a ingestão de forma síncrona
        from rag_ocr.pipeline.llm_agent import ingest_document
        try:
            ingest_document(document)
        except Exception as e:
            # Em um app em produção, seria ideal logar esse erro adequadamente
            print(f"Erro na ingestão do documento {document.id}: {e}")


class DocumentChunkViewSet(viewsets.ReadOnlyModelViewSet):
    # restrito à leitura dos chunks

    serializer_class = DocumentChunkSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        qs = DocumentChunk.objects.select_related("document")
        document_id = self.request.query_params.get("document")
        if document_id:
            qs = qs.filter(document_id=document_id)
        return qs


class ConversationViewSet(viewsets.ModelViewSet):
    serializer_class = ConversationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Conversation.objects.filter(user=self.request.user).prefetch_related(
            "queries__answer__citations_answer__chunk__document"
        )

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class AskQuestionView(APIView):
    """
    Endpoint principal de consulta simplificado para focar apenas no RAG.
    Ignora conversas e autenticação por enquanto.
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        question = request.data.get("question")
        if not question:
            return Response(
                {"detail": "O campo 'question' é obrigatório no JSON."},
                status=status.HTTP_400_BAD_REQUEST
            )

        from rag_ocr.services.langchain_services import LangchainServices

        try:
            rag_service = LangchainServices()
            resultado = rag_service.perguntar(question)
            
            return Response({
                "question": question,
                "answer": resultado["resposta"],
                "sources": resultado.get("fontes", [])
            }, status=status.HTTP_200_OK)
                
        except Exception as e:
            # Em caso de erro na LLM ou busca
            return Response(
                {"detail": f"Erro ao processar a pergunta: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
