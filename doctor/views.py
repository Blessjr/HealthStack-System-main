import time
import random
import string
import datetime
import re
from io import BytesIO
from urllib import response
from email import message
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.cache import cache_control
from django.views.decorators.csrf import csrf_exempt
from django.core.mail import BadHeaderError, send_mail
from django.template.loader import render_to_string, get_template
from django.utils.html import strip_tags
from django.http import HttpResponse, HttpResponseForbidden
from xhtml2pdf import pisa
from django.db.models import Q, Count
from django.dispatch import receiver
from django.contrib.auth.signals import user_logged_in, user_logged_out
from doctor.forms import DoctorUserCreationForm
from hospital.models import User, Patient
from hospital_admin.models import Admin_Information, Clinical_Laboratory_Technician, Test_Information
from .models import (
    Doctor_Information, Appointment, Education, Experience, Prescription_medicine, 
    Report, Specimen, Test, Prescription_test, Prescription, Doctor_review, Conversation, ChatMessage
)
from .utils import forward_patient_bot_messages


# ------------------- Utility Functions -------------------

def generate_random_string():
    N = 8
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=N))


def render_to_pdf(template_src, context_dict={}):
    template = get_template(template_src)
    html = template.render(context_dict)
    result = BytesIO()
    pdf = pisa.pisaDocument(BytesIO(html.encode("ISO-8859-1")), result)
    if not pdf.err:
        return HttpResponse(result.getvalue(), content_type="application/pdf")
    return None


# ------------------- Auth / Account Views -------------------

@csrf_exempt
@login_required(login_url="doctor-login")
def doctor_change_password(request, pk):
    doctor = Doctor_Information.objects.get(user_id=pk)
    context = {'doctor': doctor}

    if request.method == "POST":
        new_password = request.POST["new_password"]
        confirm_password = request.POST["confirm_password"]
        if new_password == confirm_password:
            request.user.set_password(new_password)
            request.user.save()
            messages.success(request, "Password Changed Successfully")
            return redirect("doctor-dashboard")
        else:
            messages.error(request, "New Password and Confirm Password is not same")
            return redirect("change-password", pk)

    return render(request, 'doctor-change-password.html', context)


@csrf_exempt
@login_required(login_url="doctor-login")
def schedule_timings(request):
    doctor = Doctor_Information.objects.get(user=request.user)
    return render(request, 'schedule-timings.html', {'doctor': doctor})


@csrf_exempt
@login_required(login_url="doctor-login")
def patient_id(request):
    return render(request, 'patient-id.html')


@csrf_exempt
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def logoutDoctor(request):
    user = User.objects.get(id=request.user.id)
    if getattr(user, "is_doctor", False):
        user.login_status = False
        user.save()
        logout(request)
    messages.success(request, 'User Logged out')
    return redirect('doctor-login')


@csrf_exempt
def doctor_register(request):
    page = 'doctor-register'
    form = DoctorUserCreationForm()

    if request.method == 'POST':
        form = DoctorUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_doctor = True
            user.save()
            messages.success(request, 'Doctor account was created!')
            return redirect('doctor-login')
        else:
            messages.error(request, 'An error has occurred during registration')

    return render(request, 'doctor-register.html', {'page': page, 'form': form})


@csrf_exempt
def doctor_login(request):
    if request.method == 'GET':
        return render(request, 'doctor-login.html')
    elif request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            messages.error(request, 'Username does not exist')
            return render(request, 'doctor-login.html')

        user = authenticate(username=username, password=password)
        if user is not None:
            login(request, user)
            if getattr(user, "is_doctor", False):
                user.login_status = True
                user.save()
                messages.success(request, 'Welcome Doctor!')
                return redirect('doctor-dashboard')
            else:
                messages.error(request, 'Invalid credentials. Not a Doctor')
                return redirect('doctor-logout')
        else:
            messages.error(request, 'Invalid username or password')

    return render(request, 'doctor-login.html')


# ------------------- Dashboard -------------------

@csrf_exempt
@login_required(login_url="doctor-login")
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def doctor_dashboard(request):
    if not getattr(request.user, 'is_doctor', False):
        return redirect('doctor-logout')

    doctor = Doctor_Information.objects.get(user=request.user)

    # Forward all pending patient-bot messages to this doctor
    patient_conversations = Conversation.objects.filter(doctor=request.user)
    for conv in patient_conversations:
        forwarded_messages = forward_patient_bot_messages(conv.id)

    # Get all patients assigned to this doctor
    patient_ids = Appointment.objects.filter(
        doctor=doctor,
        appointment_status='confirmed'
    ).values_list('patient_id', flat=True).distinct()
    patient_users = User.objects.filter(id__in=patient_ids)

    conversations = Conversation.objects.filter(
        patient__in=patient_users,
        doctor=request.user
    )

    chat_messages = ChatMessage.objects.filter(
        conversation__in=conversations
    ).order_by('-timestamp')[:50]

    processed_messages = [
        {
            'timestamp': msg.timestamp.strftime("%Y-%m-%d %H:%M"),
            'sender': msg.sender,
            'message': msg.message,
            'language': msg.language
        } for msg in chat_messages
    ]

    current_date = datetime.date.today()
    today_appointments = Appointment.objects.filter(
        date=str(current_date),
        doctor=doctor,
        appointment_status='confirmed'
    )
    next_date = current_date + datetime.timedelta(days=1)
    next_days_appointment = Appointment.objects.filter(
        date=str(next_date),
        doctor=doctor
    ).filter(Q(appointment_status='pending') | Q(appointment_status='confirmed')).count()
    today_patient_count = today_appointments.count()
    total_appointments_count = Appointment.objects.filter(doctor=doctor).count()

    doctor_session_id = f"doctor_{doctor.pk}_{int(time.time())}"

    context = {
        'doctor': doctor,
        'today_appointments': today_appointments,
        'today_patient_count': today_patient_count,
        'total_appointments_count': total_appointments_count,
        'next_days_appointment': next_days_appointment,
        'current_date': str(current_date),
        'next_date': str(next_date),
        'chat_messages': processed_messages,
        'websocket_session_id': doctor_session_id,
        'websocket_role': 'doctor'
    }

    return render(request, 'doctor-dashboard.html', context)


# ------------------- Appointments -------------------

@csrf_exempt
@login_required(login_url="doctor-login")
def appointments(request):
    doctor = Doctor_Information.objects.get(user=request.user)
    appointments = Appointment.objects.filter(doctor=doctor, appointment_status='pending').order_by('date')
    return render(request, 'appointments.html', {'doctor': doctor, 'appointments': appointments})


@csrf_exempt
@login_required(login_url="doctor-login")
def accept_appointment(request, pk):
    appointment = Appointment.objects.get(id=pk)
    appointment.appointment_status = 'confirmed'
    appointment.save()

    # Send email notification
    patient_email = appointment.patient.email
    patient_name = appointment.patient.name
    patient_username = appointment.patient.username
    patient_serial_number = appointment.patient.serial_number
    doctor_name = appointment.doctor.name
    appointment_serial_number = appointment.serial_number
    appointment_date = appointment.date
    appointment_time = appointment.time
    appointment_status = appointment.appointment_status

    subject = "Appointment Acceptance Email"
    values = {
        "email": patient_email,
        "name": patient_name,
        "username": patient_username,
        "serial_number": patient_serial_number,
        "doctor_name": doctor_name,
        "appointment_serial_num": appointment_serial_number,
        "appointment_date": appointment_date,
        "appointment_time": appointment_time,
        "appointment_status": appointment_status,
    }
    html_message = render_to_string('appointment_accept_mail.html', {'values': values})
    plain_message = strip_tags(html_message)

    try:
        send_mail(subject, plain_message, 'hospital_admin@gmail.com', [patient_email], html_message=html_message, fail_silently=False)
    except BadHeaderError:
        return HttpResponse('Invalid header found')

    messages.success(request, 'Appointment Accepted')
    return redirect('doctor-dashboard')


@csrf_exempt
@login_required(login_url="doctor-login")
def reject_appointment(request, pk):
    appointment = Appointment.objects.get(id=pk)
    appointment.appointment_status = 'cancelled'
    appointment.save()

    patient_email = appointment.patient.email
    patient_name = appointment.patient.name
    doctor_name = appointment.doctor.name

    subject = "Appointment Rejection Email"
    values = {
        "email": patient_email,
        "name": patient_name,
        "doctor_name": doctor_name,
    }
    html_message = render_to_string('appointment_reject_mail.html', {'values': values})
    plain_message = strip_tags(html_message)

    try:
        send_mail(subject, plain_message, 'hospital_admin@gmail.com', [patient_email], html_message=html_message, fail_silently=False)
    except BadHeaderError:
        return HttpResponse('Invalid header found')

    messages.error(request, 'Appointment Rejected')
    return redirect('doctor-dashboard')


# ------------------- Doctor Profile -------------------

@csrf_exempt
@login_required(login_url="doctor-login")
def doctor_profile(request, pk):
    patient = request.user.patient if getattr(request.user, "is_patient", False) else None
    doctor = Doctor_Information.objects.get(doctor_id=pk)
    educations = Education.objects.filter(doctor=doctor).order_by('-year_of_completion')
    experiences = Experience.objects.filter(doctor=doctor).order_by('-from_year', '-to_year')
    doctor_review = Doctor_review.objects.filter(doctor=doctor)
    return render(request, 'doctor-profile.html', {'doctor': doctor, 'patient': patient, 'educations': educations, 'experiences': experiences, 'doctor_review': doctor_review})


@csrf_exempt
@login_required(login_url="doctor-login")
def doctor_profile_settings(request):
    doctor = Doctor_Information.objects.get(user=request.user)

    if request.method == "POST":
        doctor.name = request.POST.get("name", doctor.name)
        doctor.phone_number = request.POST.get("phone_number", doctor.phone_number)
        doctor.specialization = request.POST.get("specialization", doctor.specialization)
        doctor.save()
        messages.success(request, "Profile updated successfully")
        return redirect("doctor-dashboard")

    return render(request, "doctor-profile-settings.html", {"doctor": doctor})


@login_required(login_url="doctor-login")
def doctor_view_report(request, pk):
    """
    View a specific report for a patient by the doctor
    """
    report = get_object_or_404(Report, pk=pk)
    specimens = Specimen.objects.filter(report=report)
    tests = Test.objects.filter(report=report)
    return render(request, "doctor-view-report.html", {
        "report": report,
        "specimens": specimens,
        "tests": tests
    })


@csrf_exempt
@login_required(login_url="doctor-login")
def delete_education(request, pk):
    """
    Delete a specific education record for the logged-in doctor.
    """
    if not getattr(request.user, "is_doctor", False):
        return redirect("doctor-logout")

    doctor = Doctor_Information.objects.get(user=request.user)
    education = get_object_or_404(Education, pk=pk, doctor=doctor)

    if request.method == "POST":
        education.delete()
        messages.success(request, "Education record deleted successfully")
        return redirect("doctor-profile-settings")

    return render(request, "confirm-delete.html", {"object": education, "type": "Education"})


@csrf_exempt
@login_required(login_url="doctor-login")
def delete_experience(request, pk):
    """
    Delete a specific experience record for the logged-in doctor.
    """
    if not getattr(request.user, "is_doctor", False):
        return redirect("doctor-logout")

    doctor = Doctor_Information.objects.get(user=request.user)
    experience = get_object_or_404(Experience, pk=pk, doctor=doctor)

    if request.method == "POST":
        experience.delete()
        messages.success(request, "Experience record deleted successfully")
        return redirect("doctor-profile-settings")

    return render(request, "confirm-delete.html", {"object": experience, "type": "Experience"})


@csrf_exempt
@login_required(login_url="doctor-login")
def doctor_test_list(request):
    doctor = Doctor_Information.objects.get(user=request.user)
    doctor_reports = Report.objects.filter(doctor=doctor)
    tests = Test.objects.filter(report__in=doctor_reports)
    return render(request, "doctor-test-list.html", {"doctor": doctor, "tests": tests})


@login_required(login_url="doctor-login")
def doctor_view_prescription(request, pk):
    prescription = get_object_or_404(Prescription, pk=pk)
    return render(request, "doctor-view-prescription.html", {"prescription": prescription})

# ------------------- Patient Search (NEW) -------------------

@csrf_exempt
@login_required(login_url="doctor-login")
def patient_search(request, pk):
    """
    Search patients for a doctor based on query (by patient_id or name)
    """
    doctor = Doctor_Information.objects.get(user=request.user)
    search_query = request.GET.get('search_query', '')

    # Filter patients assigned to this doctor
    patient_ids = Appointment.objects.filter(
        doctor=doctor,
        appointment_status='confirmed'
    ).values_list('patient_id', flat=True).distinct()

    patients = Patient.objects.filter(
        Q(patient_id__icontains=search_query) | Q(name__icontains=search_query),
        patient_id__in=patient_ids
    )

    return render(request, 'patient-search.html', {'patients': patients, 'search_query': search_query})


# ------------------- Booking / Prescriptions / Reports -------------------

@csrf_exempt
@login_required(login_url="doctor-login")
def booking_success(request):
    return render(request, 'booking-success.html')


@csrf_exempt
@login_required(login_url="doctor-login")
def booking(request, pk):
    patient = request.user.patient
    doctor = Doctor_Information.objects.get(doctor_id=pk)

    if request.method == 'POST':
        appointment = Appointment(patient=patient, doctor=doctor)
        date = request.POST['appoint_date']
        time_val = request.POST['appoint_time']
        appointment_type = request.POST['appointment_type']
        message_val = request.POST['message']

        appointment.date = datetime.datetime.strptime(date, '%m/%d/%Y').strftime('%Y-%m-%d')
        appointment.time = time_val
        appointment.appointment_status = 'pending'
        appointment.serial_number = generate_random_string()
        appointment.appointment_type = appointment_type
        appointment.message = message_val
        appointment.save()

        if message_val:
            subject = "Appointment Request"
            values = {
                "email": patient.email,
                "name": patient.name,
                "username": patient.username,
                "phone_number": patient.phone_number,
                "doctor_name": doctor.name,
                "message": message_val,
            }
            html_message = render_to_string('appointment-request-mail.html', {'values': values})
            plain_message = strip_tags(html_message)
            try:
                send_mail(subject, plain_message, 'hospital_admin@gmail.com', [patient.email], html_message=html_message, fail_silently=False)
            except BadHeaderError:
                return HttpResponse('Invalid header found')

        messages.success(request, 'Appointment Booked')
        return redirect('patient-dashboard')

    return render(request, 'booking.html', {'patient': patient, 'doctor': doctor})


@csrf_exempt
@login_required(login_url="doctor-login")
def my_patients(request):
    if not getattr(request.user, "is_doctor", False):
        return redirect('doctor-logout')

    doctor = Doctor_Information.objects.get(user=request.user)
    appointments = Appointment.objects.filter(doctor=doctor, appointment_status='confirmed')
    return render(request, 'my-patients.html', {'doctor': doctor, 'appointments': appointments})


@csrf_exempt
@login_required(login_url="doctor-login")
def patient_profile(request, pk):
    if not getattr(request.user, "is_doctor", False):
        return redirect('doctor-logout')

    doctor = Doctor_Information.objects.get(user=request.user)
    patient = Patient.objects.get(patient_id=pk)
    appointments = Appointment.objects.filter(doctor=doctor, patient=patient)
    prescription = Prescription.objects.filter(doctor=doctor, patient=patient)
    report = Report.objects.filter(doctor=doctor, patient=patient)
    return render(request, 'patient-profile.html', {'doctor': doctor, 'patient': patient, 'appointments': appointments, 'prescription': prescription, 'report': report})



@csrf_exempt
@login_required(login_url="doctor-login")
def create_prescription(request, pk):
    if not getattr(request.user, "is_doctor", False):
        return redirect('doctor-logout')

    doctor = Doctor_Information.objects.get(user=request.user)
    patient = Patient.objects.get(patient_id=pk)
    create_date = datetime.date.today()

    if request.method == 'POST':
        prescription = Prescription(doctor=doctor, patient=patient, create_date=create_date)
        prescription.extra_information = request.POST.get('extra_information', '')
        prescription.save()

        # Save medicines
        medicine_name = request.POST.getlist('medicine_name')
        medicine_quantity = request.POST.getlist('quantity')
        medecine_frequency = request.POST.getlist('frequency')
        medicine_duration = request.POST.getlist('duration')
        medicine_relation_with_meal = request.POST.getlist('relation_with_meal')
        medicine_instruction = request.POST.getlist('instruction')
        for i in range(len(medicine_name)):
            Prescription_medicine.objects.create(
                prescription=prescription,
                medicine_name=medicine_name[i],
                quantity=medicine_quantity[i],
                frequency=medecine_frequency[i],
                duration=medicine_duration[i],
                relation_with_meal=medicine_relation_with_meal[i],
                instruction=medicine_instruction[i]
            )

        # Save tests
        test_name = request.POST.getlist('test_name')
        test_description = request.POST.getlist('description')
        test_info_id = request.POST.getlist('id')
        for i in range(len(test_name)):
            test_info = Test_Information.objects.get(test_id=test_info_id[i])
            Prescription_test.objects.create(
                prescription=prescription,
                test_name=test_name[i],
                test_description=test_description[i],
                test_info_id=test_info_id[i],
                test_info_price=test_info.test_price
            )

        messages.success(request, 'Prescription Created')
        return redirect('patient-profile', pk=patient.patient_id)

    return render(request, 'create-prescription.html', {'doctor': doctor, 'patient': patient})


# ------------------- Reports -------------------

@csrf_exempt
def report_pdf(request, pk):
    if getattr(request.user, "is_patient", False):
        patient = Patient.objects.get(user=request.user)
        report = Report.objects.get(report_id=pk)
        specimen = Specimen.objects.filter(report=report)
        test = Test.objects.filter(report=report)
        context = {'patient': patient, 'report': report, 'test': test, 'specimen': specimen}
        pdf = render_to_pdf('report_pdf.html', context)
        if pdf:
            response = HttpResponse(pdf, content_type='application/pdf')
            response['Content-Disposition'] = "inline; filename=report.pdf"
            return response
    return HttpResponse("Not Found")


# ------------------- Signals -------------------

@csrf_exempt
@receiver(user_logged_in)
def got_online(sender, user, request, **kwargs):
    user.login_status = True
    user.save()
    if getattr(user, "is_doctor", False):
        doctor_conversations = Conversation.objects.filter(doctor=user)
        for conv in doctor_conversations:
            forward_patient_bot_messages(conv.id)


@csrf_exempt
@receiver(user_logged_out)
def got_offline(sender, request, user, **kwargs):
    if user is not None:
        user.login_status = False
        user.save()


# ------------------- Reviews -------------------

@csrf_exempt
@login_required(login_url="login")
def doctor_review(request, pk):
    doctor = get_object_or_404(Doctor_Information, pk=pk)

    if getattr(request.user, "is_doctor", False):
        if doctor.user != request.user:
            return HttpResponseForbidden("You can view only your own reviews.")
        reviews = Doctor_review.objects.filter(doctor=doctor)
        return render(request, "reviews.html", {"doctor": doctor, "doctor_review": reviews})

    if getattr(request.user, "is_patient", False):
        patient = get_object_or_404(Patient, user=request.user)
        if request.method == 'POST':
            Doctor_review.objects.create(
                doctor=doctor,
                patient=patient,
                title=request.POST.get("title", "").strip(),
                message=request.POST.get("message", "").strip(),
            )
            return redirect("doctor_review", pk=pk)

        reviews = Doctor_review.objects.filter(doctor=doctor).select_related("patient").order_by("-created_at")
        return render(request, "reviews.html", {"doctor": doctor, "patient": patient, "doctor_review": reviews})

    logout(request)
    return redirect("login")
