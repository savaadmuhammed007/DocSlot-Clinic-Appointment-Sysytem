from django.contrib import admin
from .models import (
    Department,
    PatientProfile,
    DoctorProfile,
    Availability,
    Leave,
    Appointment,
    ConsultationNote
)


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ['id', 'name']
    search_fields = ['name']


@admin.register(PatientProfile)
class PatientProfileAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'age', 'gender', 'phone']
    search_fields = ['user__username', 'user__first_name', 'user__last_name', 'phone']


class AvailabilityInline(admin.TabularInline):
    model = Availability
    extra = 1


class LeaveInline(admin.TabularInline):
    model = Leave
    extra = 1


@admin.register(DoctorProfile)
class DoctorProfileAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'doctor_name',
        'department',
        'phone',
        'specialization',
        'consultation_fee',
        'is_available'
    ]
    list_filter = ['department', 'is_available']
    search_fields = [
        'user__username',
        'user__first_name',
        'user__last_name',
        'specialization',
        'phone'
    ]
    list_editable = ['department', 'phone', 'specialization', 'consultation_fee', 'is_available']
    inlines = [AvailabilityInline, LeaveInline]

    def doctor_name(self, obj):
        return obj.user.get_full_name() or obj.user.username

    doctor_name.short_description = "Doctor Name"


@admin.register(Availability)
class AvailabilityAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'doctor',
        'day_of_week',
        'start_time',
        'end_time',
        'slot_minutes',
        'max_patients_per_slot',
        'active'
    ]
    list_filter = ['day_of_week', 'active']
    search_fields = ['doctor__user__first_name', 'doctor__user__last_name']


@admin.register(Leave)
class LeaveAdmin(admin.ModelAdmin):
    list_display = ['id', 'doctor', 'date', 'reason']
    list_filter = ['date']
    search_fields = ['doctor__user__first_name', 'doctor__user__last_name', 'reason']


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ['id', 'patient', 'doctor', 'appointment_date', 'appointment_time', 'status', 'created_at']
    list_filter = ['status', 'appointment_date', 'doctor']
    search_fields = [
        'patient__user__username',
        'patient__user__first_name',
        'doctor__user__first_name',
        'doctor__user__last_name'
    ]


@admin.register(ConsultationNote)
class ConsultationNoteAdmin(admin.ModelAdmin):
    list_display = ['id', 'appointment', 'created_at', 'updated_at']