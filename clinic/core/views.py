from datetime import datetime, timedelta, time as dtime

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import IntegrityError
from django.db.models import Count
from django.http import JsonResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import RegisterForm, AppointmentForm, RescheduleForm, ConsultationNoteForm, LeaveForm, DoctorCreateUpdateForm
from .models import (
    Department,
    DoctorProfile,
    PatientProfile,
    Availability,
    Leave,
    Appointment,
    ConsultationNote,
)

SLOT_MINUTES = 15


def home(request):
    return render(request, 'core/home.html')


def register_view(request):
    if request.user.is_authenticated:
        return redirect('home')

    form = RegisterForm(request.POST or None)
    if request.method == 'POST':
        if form.is_valid():
            user = User.objects.create_user(
                username=form.cleaned_data['username'],
                email=form.cleaned_data['email'],
                password=form.cleaned_data['password'],
                first_name=form.cleaned_data['first_name'],
                last_name=form.cleaned_data['last_name'],
            )

            patient = user.patient_profile
            patient.age = form.cleaned_data.get('age')
            patient.gender = form.cleaned_data.get('gender')
            patient.phone = form.cleaned_data.get('phone')
            patient.save()

            messages.success(request, "Registration successful. Please login.")
            return redirect('login')

    return render(request, 'core/register.html', {'form': form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)

            if hasattr(user, 'doctor_profile'):
                return redirect('doctor_dashboard')
            elif user.is_staff:
                return redirect('admin_dashboard')
            else:
                return redirect('department_list')

        messages.error(request, "Invalid username or password")

    return render(request, 'core/login.html')


def logout_view(request):
    logout(request)
    return redirect('login')


def _round_time_to_slot(t: dtime, slot_minutes: int = SLOT_MINUTES) -> dtime:
    dt = datetime.combine(datetime.today().date(), t)
    minutes = (dt.minute // slot_minutes) * slot_minutes
    rounded = dt.replace(minute=minutes, second=0, microsecond=0)
    if rounded.time() < t:
        rounded += timedelta(minutes=slot_minutes)
    return rounded.time()


def _generate_slots(start_time, end_time, slot_minutes):
    slots = []
    current = datetime.combine(datetime.today(), start_time)
    end_dt = datetime.combine(datetime.today(), end_time)

    while current + timedelta(minutes=slot_minutes) <= end_dt:
        slots.append(current.time())
        current += timedelta(minutes=slot_minutes)

    return slots


def _doctor_is_on_leave(doctor, date):
    return Leave.objects.filter(doctor=doctor, date=date).exists()


def _slot_capacity_ok(doctor, date, time_value):
    weekday = date.weekday()
    availability = Availability.objects.filter(
        doctor=doctor,
        day_of_week=weekday,
        start_time__lte=time_value,
        end_time__gt=time_value,
        active=True
    ).first()

    if not availability:
        return False

    count = Appointment.objects.filter(
        doctor=doctor,
        appointment_date=date,
        appointment_time=time_value,
        status__in=['PENDING', 'APPROVED', 'COMPLETED']
    ).count()

    return count < availability.max_patients_per_slot


def _doctor_available_on(doctor, date, time_value):
    return _slot_capacity_ok(doctor, date, time_value)


@login_required
def get_available_slots(request, doctor_id):
    doctor = get_object_or_404(DoctorProfile, id=doctor_id)
    date_str = request.GET.get('date')

    if not date_str:
        return JsonResponse({'slots': []})

    try:
        appointment_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return JsonResponse({'slots': []})

    if appointment_date < timezone.localdate():
        return JsonResponse({'slots': []})

    if _doctor_is_on_leave(doctor, appointment_date):
        return JsonResponse({'slots': []})

    availabilities = Availability.objects.filter(
        doctor=doctor,
        day_of_week=appointment_date.weekday(),
        active=True
    ).order_by('start_time')

    if not availabilities.exists():
        return JsonResponse({'slots': []})

    free_slots = []
    now = timezone.localtime()

    for availability in availabilities:
        all_slots = _generate_slots(
            availability.start_time,
            availability.end_time,
            SLOT_MINUTES
        )

        for slot in all_slots:
            if appointment_date == timezone.localdate() and slot <= now.time():
                continue

            if _slot_capacity_ok(doctor, appointment_date, slot):
                free_slots.append(slot.strftime("%H:%M"))

    free_slots = sorted(list(set(free_slots)))

    return JsonResponse({'slots': free_slots})


@login_required
def department_list(request):
    departments = Department.objects.all()
    return render(request, 'core/department_list.html', {'departments': departments})


@login_required
def doctors_by_department(request, department_id):
    department = get_object_or_404(Department, id=department_id)
    doctors = department.doctors.filter(is_available=True)
    return render(request, 'core/doctors_by_department.html', {
        'department': department,
        'doctors': doctors
    })


@login_required
def book_appointment(request, doctor_id):
    if hasattr(request.user, 'doctor_profile'):
        messages.error(request, "Doctors cannot book appointments as patients.")
        return redirect('doctor_dashboard')

    doctor = get_object_or_404(DoctorProfile, id=doctor_id)
    patient = get_object_or_404(PatientProfile, user=request.user)

    if request.method == 'POST':
        appointment_date = request.POST.get('appointment_date')
        appointment_time = request.POST.get('appointment_time')
        reason = request.POST.get('reason')

        if not appointment_date or not appointment_time:
            messages.error(request, "Please select date and time.")
            return render(request, 'core/book_appointment.html', {'doctor': doctor})

        try:
            appointment_date = datetime.strptime(appointment_date, "%Y-%m-%d").date()
            appointment_time = datetime.strptime(appointment_time, "%H:%M").time()
        except ValueError:
            messages.error(request, "Invalid date or time format.")
            return render(request, 'core/book_appointment.html', {'doctor': doctor})

        if appointment_date < timezone.localdate():
            messages.error(request, "You cannot book an appointment for a past date.")
            return render(request, 'core/book_appointment.html', {'doctor': doctor})

        if _doctor_is_on_leave(doctor, appointment_date):
            messages.error(request, "Doctor is on leave on this date.")
            return render(request, 'core/book_appointment.html', {'doctor': doctor})

        if not _slot_capacity_ok(doctor, appointment_date, appointment_time):
            messages.error(request, "Selected slot is full or unavailable.")
            return render(request, 'core/book_appointment.html', {'doctor': doctor})

        try:
            Appointment.objects.create(
                patient=patient,
                doctor=doctor,
                appointment_date=appointment_date,
                appointment_time=appointment_time,
                reason=reason,
                status='PENDING'
            )
            messages.success(request, "Appointment booked successfully.")
            return redirect('my_appointments')
        except IntegrityError:
            messages.error(request, "This slot is already booked for the doctor.")

    return render(request, 'core/book_appointment.html', {
        'doctor': doctor
    })


@login_required
def my_appointments(request):
    patient = get_object_or_404(PatientProfile, user=request.user)
    appointments = patient.appointments.select_related(
        'doctor__user',
        'consultation_note'
    ).all()

    return render(request, 'core/my_appointments.html', {
        'appointments': appointments
    })

@login_required
def patient_consultation_detail(request, appointment_id):
    patient = get_object_or_404(PatientProfile, user=request.user)

    appointment = get_object_or_404(
        Appointment.objects.select_related(
            'doctor__user',
            'patient__user'
        ),
        id=appointment_id,
        patient=patient
    )

    if not hasattr(appointment, 'consultation_note'):
        messages.error(request, "Consultation note is not available yet.")
        return redirect('my_appointments')

    return render(request, 'core/patient_consultation_detail.html', {
        'appointment': appointment,
        'note': appointment.consultation_note
    })


@login_required
def cancel_appointment(request, appointment_id):
    patient = get_object_or_404(PatientProfile, user=request.user)
    appointment = get_object_or_404(Appointment, id=appointment_id, patient=patient)

    if appointment.status not in ['PENDING', 'APPROVED']:
        messages.error(request, "Only pending or approved appointments can be cancelled.")
        return redirect('my_appointments')

    if not appointment.can_cancel():
        messages.error(request, "Cancellation is allowed only before 2 hours.")
        return redirect('my_appointments')

    appointment.status = 'CANCELLED'
    appointment.save()
    messages.success(request, "Appointment cancelled.")
    return redirect('my_appointments')


@login_required
def reschedule_appointment(request, appointment_id):
    patient = get_object_or_404(PatientProfile, user=request.user)
    appointment = get_object_or_404(Appointment, id=appointment_id, patient=patient)

    if appointment.status not in ['PENDING', 'APPROVED']:
        messages.error(request, "Only pending or approved appointments can be rescheduled.")
        return redirect('my_appointments')

    form = RescheduleForm(request.POST or None, instance=appointment)

    if request.method == 'POST':
        if form.is_valid():
            new_date = form.cleaned_data['appointment_date']
            new_time = _round_time_to_slot(form.cleaned_data['appointment_time'])

            if _doctor_is_on_leave(appointment.doctor, new_date):
                messages.error(request, "Doctor is on leave on this date.")
                return render(request, 'core/reschedule.html', {'form': form, 'appointment': appointment})

            if not _doctor_available_on(appointment.doctor, new_date, new_time):
                messages.error(request, "Doctor is not available at this new time.")
                return render(request, 'core/reschedule.html', {'form': form, 'appointment': appointment})

            existing = Appointment.objects.filter(
                doctor=appointment.doctor,
                appointment_date=new_date,
                appointment_time=new_time
            ).exclude(id=appointment.id).exists()

            if existing:
                messages.error(request, "This slot is already booked.")
                return render(request, 'core/reschedule.html', {'form': form, 'appointment': appointment})

            appointment.appointment_date = new_date
            appointment.appointment_time = new_time
            appointment.status = 'PENDING'
            appointment.save()

            messages.success(request, "Appointment rescheduled successfully.")
            return redirect('my_appointments')

    return render(request, 'core/reschedule.html', {
        'form': form,
        'appointment': appointment
    })


@login_required
def admin_dashboard(request):
    if not request.user.is_staff:
        raise Http404()

    today = timezone.localdate()
    today_appointments = Appointment.objects.filter(appointment_date=today).select_related('doctor__user', 'patient__user')
    pending_count = Appointment.objects.filter(status='PENDING').count()
    completed_count = Appointment.objects.filter(status='COMPLETED').count()

    return render(request, 'core/admin_dashboard.html', {
        'today_appointments': today_appointments,
        'pending_count': pending_count,
        'completed_count': completed_count,
    })


@login_required
def manage_appointments(request):
    if not request.user.is_staff:
        raise Http404()

    appointments = Appointment.objects.select_related('doctor__user', 'patient__user').all()

    if request.method == 'POST':
        appointment_id = request.POST.get('appointment_id')
        action = request.POST.get('action')

        appointment = get_object_or_404(Appointment, id=appointment_id)

        if action == 'approve':
            appointment.status = 'APPROVED'
        elif action == 'reject':
            appointment.status = 'REJECTED'
        elif action == 'complete':
            appointment.status = 'COMPLETED'

        appointment.save()
        messages.success(request, "Appointment updated.")
        return redirect('manage_appointments')

    return render(request, 'core/manage_appointments.html', {'appointments': appointments})


@login_required
def doctor_dashboard(request):
    if not hasattr(request.user, 'doctor_profile'):
        raise Http404()

    doctor = request.user.doctor_profile
    today = timezone.localdate()
    appointments = Appointment.objects.filter(
        doctor=doctor,
        appointment_date=today
    ).select_related('patient__user')

    return render(request, 'core/doctor_dashboard.html', {
        'appointments': appointments,
        'doctor': doctor
    })


@login_required
def add_consultation_note(request, appointment_id):
    if not hasattr(request.user, 'doctor_profile'):
        raise Http404()

    doctor = request.user.doctor_profile
    appointment = get_object_or_404(Appointment, id=appointment_id, doctor=doctor)

    note, created = ConsultationNote.objects.get_or_create(appointment=appointment)
    form = ConsultationNoteForm(request.POST or None, instance=note)

    if request.method == 'POST':
        if form.is_valid():
            form.save()
            appointment.status = 'COMPLETED'
            appointment.save()
            messages.success(request, "Consultation note saved.")
            return redirect('doctor_dashboard')

    return render(request, 'core/consultation_note_form.html', {
        'form': form,
        'appointment': appointment
    })


@login_required
def doctor_leave(request):
    if not hasattr(request.user, 'doctor_profile'):
        raise Http404()

    doctor = request.user.doctor_profile
    form = LeaveForm(request.POST or None)

    if request.method == 'POST':
        if form.is_valid():
            leave = form.save(commit=False)
            leave.doctor = doctor
            leave.save()
            messages.success(request, "Leave added successfully.")
            return redirect('doctor_leave')

    leaves = doctor.leaves.all().order_by('-date')
    return render(request, 'core/doctor_leave.html', {
        'form': form,
        'leaves': leaves
    })


@login_required
def manage_doctors(request):
    if not request.user.is_staff:
        raise Http404()

    doctors = DoctorProfile.objects.select_related('user', 'department').all().order_by('user__first_name')
    return render(request, 'core/manage_doctors.html', {'doctors': doctors})


@login_required
def add_doctor(request):
    if not request.user.is_staff:
        raise Http404()

    form = DoctorCreateUpdateForm(request.POST or None)

    if request.method == 'POST':
        if form.is_valid():
            user = User.objects.create_user(
                username=form.cleaned_data['username'],
                email=form.cleaned_data['email'],
                password='asdf@123',  # default password
                first_name=form.cleaned_data['first_name'],
                last_name=form.cleaned_data['last_name'],
            )

            DoctorProfile.objects.create(
                user=user,
                department=form.cleaned_data['department'],
                phone=form.cleaned_data['phone'],
                specialization=form.cleaned_data['specialization'],
                consultation_fee=form.cleaned_data['consultation_fee'],
                is_available=form.cleaned_data['is_available'],
            )

            messages.success(request, "Doctor added successfully. Default password: doctor12345")
            return redirect('manage_doctors')

    return render(request, 'core/doctor_form.html', {
        'form': form,
        'title': 'Add Doctor'
    })


@login_required
def edit_doctor(request, doctor_id):
    if not request.user.is_staff:
        raise Http404()

    doctor = get_object_or_404(DoctorProfile, id=doctor_id)
    user = doctor.user

    form = DoctorCreateUpdateForm(
        request.POST or None,
        instance=doctor,
        user_instance=user
    )

    if request.method == 'POST':
        if form.is_valid():
            user.first_name = form.cleaned_data['first_name']
            user.last_name = form.cleaned_data['last_name']
            user.email = form.cleaned_data['email']
            user.username = form.cleaned_data['username']
            user.save()

            form.save()
            messages.success(request, "Doctor updated successfully.")
            return redirect('manage_doctors')

    return render(request, 'core/doctor_form.html', {
        'form': form,
        'title': 'Edit Doctor'
    })


@login_required
def delete_doctor(request, doctor_id):
    if not request.user.is_staff:
        raise Http404()

    doctor = get_object_or_404(DoctorProfile, id=doctor_id)

    if request.method == 'POST':
        doctor.user.delete()
        messages.success(request, "Doctor deleted successfully.")
        return redirect('manage_doctors')

    return render(request, 'core/delete_doctor.html', {'doctor': doctor})