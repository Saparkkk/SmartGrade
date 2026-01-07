"""
URL configuration for smartgrade project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.urls import path
from . import views

urlpatterns = [
    path('', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),
    path("profile/", views.profile_detail, name="profile"),
    path("profile/edit/", views.profile_edit, name="profile_edit"),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('teacher/dashboard/', views.teacher_dashboard, name='teacher_dashboard'),
    path('student/dashboard/', views.student_dashboard, name='student_dashboard'),
    
    path('students/', views.teacher_student_list, name='teacher_student_list'),
    path('students/import/', views.student_import_csv_view, name='teacher_student_import'),
    path('students/create/', views.teacher_student_create, name='teacher_student_create'),
    path('student/report/<str:student_id>/', views.student_report, name='student_report'),
    path('students/<int:student_id>/', views.teacher_student_detail, name='teacher_student_detail'),
    path('students/<int:student_id>/delete/', views.teacher_student_delete, name='teacher_student_delete'),
    path('behavior/<int:behavior_id>/delete/', views.behavior_delete, name='behavior_delete'),
    
    path('teacher/dashboard/', views.dashboard, name='teacher_dashboard'),
    path('students/<int:student_id>/edit/', views.teacher_student_edit, name='teacher_student_edit'),
    path('students/bulk-delete/', views.teacher_student_bulk_delete, name='teacher_student_bulk_delete'),
    
    path('classroom/', views.classroom_mode, name='classroom_mode'),
    path('classroom/log/<int:student_id>/<str:behavior_type>/', views.quick_behavior_log, name='quick_log'),
]
