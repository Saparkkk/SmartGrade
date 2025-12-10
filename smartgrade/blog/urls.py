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
    
    path('students/', views.list_students, name='list_students'),
    path('students/create/', views.create_student, name='create_student'),
    path('students/update/<int:student_id>/', views.update_student, name='update_student'),
    path('students/delete/<int:student_id>/', views.delete_student, name='delete_student'),
    
    path('teacher/dashboard/', views.dashboard, name='teacher_dashboard'),
    path('teacher/students/', views.student_list_view, name='teacher_student_list'),
    path('teacher/students/<int:pk>/', views.student_detail_view, name='teacher_student_detail'),
    path('teacher/students/import/', views.student_import_csv_view, name='teacher_student_import'),
]
