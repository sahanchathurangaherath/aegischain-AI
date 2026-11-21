from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import DocumentChunk, SupplyChainDocument


@admin.register(SupplyChainDocument)
class SupplyChainDocumentAdmin(ModelAdmin):
    list_display = ['title', 'doc_type', 'supplier', 'product', 'severity', 'is_indexed', 'created_at']
    list_filter = ['doc_type', 'severity', 'is_indexed']
    search_fields = ['title', 'source_uri']


@admin.register(DocumentChunk)
class DocumentChunkAdmin(ModelAdmin):
    list_display = ['document', 'chunk_index', 'created_at']
    list_filter = ['document__doc_type']
    search_fields = ['chunk_text']
