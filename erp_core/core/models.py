from django.db import models
from django.utils import timezone
import uuid


class TimeStampedModel(models.Model):
    """
    Abstract base model that adds created and updated timestamps
    to all models that inherit from it
    """
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        abstract = True


class UUIDModel(models.Model):
    """
    Abstract base model that uses UUID as primary key
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    class Meta:
        abstract = True


class ActiveModel(models.Model):
    """
    Abstract base model that adds is_active flag for soft deletes
    """
    is_active = models.BooleanField(default=True)
    
    class Meta:
        abstract = True