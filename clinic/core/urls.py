from django.urls import path
from . import views
from django.contrib import admin
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('', views.home, name='home'),

    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    path('departments/', views.department_list, name='department_list'),
    path('departments/<int:department_id>/doctors/', views.doctors_by_department, name='doctors_by_department'),
    path('doctor/<int:doctor_id>/book/', views.book_appointment, name='book_appointment'),

    path('my/appointments/', views.my_appointments, name='my_appointments'),
    path('my/appointments/<int:appointment_id>/cancel/', views.cancel_appointment, name='cancel_appointment'),
    path('my/appointments/<int:appointment_id>/reschedule/', views.reschedule_appointment, name='reschedule_appointment'),
    path('my/appointments/<int:appointment_id>/consultation/',views.patient_consultation_detail,name='patient_consultation_detail'),
    path('doctor/<int:doctor_id>/available-slots/', views.get_available_slots, name='available_slots'),

    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('manage-appointments/', views.manage_appointments, name='manage_appointments'),

    path('doctor-dashboard/', views.doctor_dashboard, name='doctor_dashboard'),
    path('doctor/appointment/<int:appointment_id>/note/', views.add_consultation_note, name='add_consultation_note'),
    path('doctor/leave/', views.doctor_leave, name='doctor_leave'),


    path('manage-doctors/', views.manage_doctors, name='manage_doctors'),
    path('manage-doctors/add/', views.add_doctor, name='add_doctor'),
    path('manage-doctors/<int:doctor_id>/edit/', views.edit_doctor, name='edit_doctor'),
    path('manage-doctors/<int:doctor_id>/delete/', views.delete_doctor, name='delete_doctor'),



    path(
        'forgot-password/',
        auth_views.PasswordResetView.as_view(
            template_name='core/forgot_password.html',
            email_template_name='core/password_reset_email.html',
            subject_template_name='core/password_reset_subject.txt',
            success_url='/forgot-password/done/'
        ),
        name='password_reset'
    ),

    path(
        'forgot-password/done/',
        auth_views.PasswordResetDoneView.as_view(
            template_name='core/password_reset_done.html'
        ),
        name='password_reset_done'
    ),

    path(
        'reset/<uidb64>/<token>/',
        auth_views.PasswordResetConfirmView.as_view(
            template_name='core/password_reset_confirm.html',
            success_url='/reset-complete/'
        ),
        name='password_reset_confirm'
    ),

    path(
        'reset-complete/',
        auth_views.PasswordResetCompleteView.as_view(
            template_name='core/password_reset_complete.html'
        ),
        name='password_reset_complete'
    ),
]