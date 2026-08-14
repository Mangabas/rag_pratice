import time
from django.conf import settings
from rest_framework import permissions, status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from rag_ocr.pipeline.llm_agent import ingest_document
from rag_ocr.services.langchain_services import LangchainServices

from .models import (
    Answer,
    AnswerCitation,
    Conversation,
    DocumentChunk,
    LegalDocument,
    Query,
)
from .serializers import (
    DocumentChunkSerializer,
    LegalDocumentSerializer,
    LegalDocumentUploadSerializer,
)


class IsStaffOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return bool(request.user and request.user.is_authenticated)
        return bool(request.user and request.user.is_staff)


class LegalDocumentViewSet(viewsets.ModelViewSet):
    queryset = LegalDocument.objects.all()
    # Modificado para permitir apenas usuários com perfil
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["document_type"]

    def get_serializer_class(self):
        if self.action == "create":
            return LegalDocumentUploadSerializer
        return LegalDocumentSerializer

    def perform_create(self, serializer):
        document = serializer.save()
        try:
            ingest_document(document)
        except Exception as e:
            print(f"Erro na ingestão do documento {document.id}: {e}")


class DocumentChunkViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = DocumentChunkSerializer
    # Modificado para permitir apenas usuários com perfil
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = DocumentChunk.objects.select_related("document")
        document_id = self.request.query_params.get("document")
        if document_id:
            qs = qs.filter(document_id=document_id)
        return qs


class AskQuestionView(APIView):
    # Modificado para exigir que o usuário esteja logado e identificado
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        question = request.data.get("question")
        # Permite vincular a uma conversa existente se o ID for enviado no JSON
        conversation_id = request.data.get("conversation_id")

        if not question:
            return Response(
                {"detail": "O campo 'question' é obrigatório no JSON."},
                status=status.HTTP_400_BAD_REQUEST
            )

        conversation = None
        if conversation_id:
            try:
                conversation = Conversation.objects.get(
                    id=conversation_id, 
                    user=request.user
                )
            except Conversation.DoesNotExist:
                pass

        # Salva a pergunta vinculada ao usuário que fez a requisição
        query_obj = Query.objects.create(
            user=request.user,
            conversation=conversation,
            question=question
        )

        try:
            rag_service = LangchainServices()
            
            # Mede o tempo de resposta da LLM
            start_time = time.time()
            resultado = rag_service.perguntar(question)
            latency = int((time.time() - start_time) * 1000)
            
            # Salva a resposta da LLM
            answer_obj = Answer.objects.create(
                query=query_obj,
                content=resultado["resposta"],
                model_used=getattr(settings, "CHAT_MODEL", "gemini"),
                latency_ms=latency
            )
            
            # Salva as citações mapeando de qual trecho a IA tirou a resposta
            chunks = resultado.get("chunks", [])
            citations = [
                AnswerCitation(
                    answer=answer_obj,
                    chunk=chunk,
                    excerpt=chunk.content[:250]  # Salva o início do texto como prévia
                )
                for chunk in chunks
            ]
            if citations:
                AnswerCitation.objects.bulk_create(citations)
            
            return Response({
                "query_id": query_obj.id,
                "question": question,
                "answer": resultado["resposta"],
                "sources": resultado.get("fontes", [])
            }, status=status.HTTP_200_OK)
                
        except Exception as e:
            return Response(
                {"detail": f"Erro ao processar a pergunta: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
