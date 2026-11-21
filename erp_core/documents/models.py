from django.db import models
from pgvector.django import HnswIndex, VectorField

from core.models import TimeStampedModel


class SupplyChainDocument(TimeStampedModel):
    """
    Unstructured supply chain documents (supplier contracts, SLAs, SOPs,
    disruption incident reports, and rate cards) indexed for semantic memory.
    """

    DOC_TYPES = [
        ('CONTRACT', 'Supplier Contract / SLA'),
        ('SOP', 'Standard Operating Procedure'),
        ('INCIDENT', 'Disruption / Quality Incident Report'),
        ('INVOICE', 'Commercial Invoice / Rate Card'),
    ]

    title = models.CharField(max_length=255)
    doc_type = models.CharField(max_length=20, choices=DOC_TYPES)
    supplier = models.ForeignKey(
        'procurement.Supplier',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='documents',
    )
    product = models.ForeignKey(
        'inventory.Product',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='documents',
    )
    source_uri = models.CharField(max_length=512, blank=True)
    file = models.FileField(upload_to='documents/%Y/%m/', null=True, blank=True)
    severity = models.PositiveSmallIntegerField(
        default=0,
        help_text="0=routine, 1=warning, 2=critical",
    )
    valid_from = models.DateField(null=True, blank=True)
    is_indexed = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.doc_type}] {self.title}"


class DocumentChunk(models.Model):
    """
    Chunked passage of a SupplyChainDocument with a 384-dim bge-small-en-v1.5
    embedding indexed via pgvector HNSW cosine distance.
    """

    document = models.ForeignKey(
        SupplyChainDocument,
        on_delete=models.CASCADE,
        related_name='chunks',
    )
    chunk_index = models.PositiveIntegerField()
    chunk_text = models.TextField()
    embedding = VectorField(dimensions=384)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['document', 'chunk_index']
        unique_together = ('document', 'chunk_index')
        indexes = [
            HnswIndex(
                name='doc_chunk_emb_hnsw_idx',
                fields=['embedding'],
                m=16,
                ef_construction=64,
                opclasses=['vector_cosine_ops'],
            )
        ]

    def __str__(self):
        return f"Doc #{self.document_id} Chunk #{self.chunk_index}"
