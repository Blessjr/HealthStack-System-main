from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Doctor_Information
from hospital.models import User  # Use your actual User model path if different


# ========== TRACK DOCTOR LOGIN STATUS ==========
@receiver(user_logged_in)
def doctor_login(sender, request, user, **kwargs):
    if hasattr(user, 'doctor'):
        user.doctor.is_online = True
        user.doctor.save()


@receiver(user_logged_out)
def doctor_logout(sender, request, user, **kwargs):
    if hasattr(user, 'doctor'):
        user.doctor.is_online = False
        user.doctor.save()


# ========== UPDATE USER INFO FROM DOCTOR_Information ==========
@receiver(post_save, sender=Doctor_Information)
def update_user_from_doctor_info(sender, instance, created, **kwargs):
    doctor = instance
    user = doctor.user

    if not created:
        user.first_name = doctor.name
        user.username = doctor.username
        user.email = doctor.email
        user.save()
