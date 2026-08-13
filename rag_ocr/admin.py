from django.contrib import admin

from .models import Answer, AnswerCitation, Conversation, DocumentChunk, LegalDocument, Query


@admin.register(LegalDocument)
class LegalDocumentAdmin(admin.ModelAdmin):
    list_display = ["file_name", "document_type", "author", "page_count", "created_at"]
    list_filter = ["document_type"]
    search_fields = ["file_name", "author"]
    readonly_fields = ["id", "created_at", "updated_at"]


class DocumentChunkInline(admin.TabularInline):
    model = DocumentChunk
    extra = 0
    fields = ["chunk_index", "page_number", "token_count", "embedding_model"]
    readonly_fields = fields
    show_change_link = True
    can_delete = False


@admin.register(DocumentChunk)
class DocumentChunkAdmin(admin.ModelAdmin):
    list_display = ["document", "chunk_index", "page_number", "token_count", "embedding_model"]
    list_filter = ["document", "embedding_model"]
    search_fields = ["content"]


class AnswerCitationInline(admin.TabularInline):
    model = AnswerCitation
    fk_name = "answer"
    extra = 0
    fields = ["chunk", "relevance_score", "excerpt"]


@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):
    list_display = ["query", "model_used", "latency_ms", "created_at"]
    inlines = [AnswerCitationInline]
    readonly_fields = ["id", "created_at"]


@admin.register(Query)
class QueryAdmin(admin.ModelAdmin):
    list_display = ["question_short", "user", "conversation", "created_at"]
    search_fields = ["question"]
    readonly_fields = ["id", "created_at"]

    def question_short(self, obj):
        return obj.question[:80]

    question_short.short_description = "Pergunta"


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ["title", "user", "created_at", "updated_at"]
    search_fields = ["title", "user__username"]
    readonly_fields = ["id", "created_at", "updated_at"]


admin.site.register(AnswerCitation)
