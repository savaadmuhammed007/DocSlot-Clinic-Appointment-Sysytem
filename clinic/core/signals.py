from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import PatientProfile


@receiver(post_save, sender=User)
def create_patient_profile(sender, instance, created, **kwargs):
    if created and not hasattr(instance, 'patient_profile') and not hasattr(instance, 'doctor_profile'):
        PatientProfile.objects.create(user=instance)