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
    permission_classes = [IsStaffOrReadOnly]
    filterset_fields = ["document_type"]

    def get_serializer_class(self):
        if self.action == "create":
            return LegalDocumentUploadSerializer
        return LegalDocumentSerializer


class DocumentChunkViewSet(viewsets.ReadOnlyModelViewSet):
    # restrito à leitura dos chunks

    serializer_class = DocumentChunkSerializer
    permission_classes = [permissions.IsAuthenticated]

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
    Endpoint principal de consulta. Por enquanto só cria o registro de
    Query, a chamada ao pipeline de RAG ainda não está implementada
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = QueryCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        conversation = serializer.validated_data.get("conversation")
        if conversation and conversation.user_id != request.user.id:
            return Response(
                {"detail": "Você não tem acesso a essa conversa."},
                status=status.HTTP_403_FORBIDDEN,
            )

        query = Query.objects.create(
            user=request.user,
            conversation=conversation,
            question=serializer.validated_data["question"],
        )

        # chamar o serviço de RAG aqui

        return Response(QuerySerializer(query).data, status=status.HTTP_201_CREATED)
