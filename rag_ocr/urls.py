from django.urls import include, path
from rest_framework.routers import APIRootView, DefaultRouter
from rest_framework.reverse import reverse

from .views import (
    AskQuestionView,
    DocumentChunkViewSet,
    LegalDocumentViewSet,
)

class CustomAPIRootView(APIRootView):
    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        response.data["ask-question"] = reverse("ask-question", request=request)
        return response

class CustomRouter(DefaultRouter):
    APIRootView = CustomAPIRootView

router = CustomRouter()
router.register("documents", LegalDocumentViewSet, basename="document")
router.register("chunks", DocumentChunkViewSet, basename="chunk")

urlpatterns = [
    path("", include(router.urls)),
    path("api-auth/", include("rest_framework.urls")),
    path("ask/", AskQuestionView.as_view(), name="ask-question"),
]