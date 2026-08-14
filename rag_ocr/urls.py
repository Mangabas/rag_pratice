from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AskQuestionView,
    DocumentChunkViewSet,
    LegalDocumentViewSet,
)

router = DefaultRouter()
router.register("documents", LegalDocumentViewSet, basename="document")
router.register("chunks", DocumentChunkViewSet, basename="chunk")
# router.register("conversations", ConversationViewSet, basename="conversation")

urlpatterns = [
    path("", include(router.urls)),
    path('api-auth/', include('rest_framework.urls')),
    path("ask/", AskQuestionView.as_view(), name="ask-question"),
]