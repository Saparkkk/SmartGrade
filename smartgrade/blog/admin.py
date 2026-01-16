from django.contrib import admin
from .models import StudentScore # Import Model คะแนนสอบ

@admin.register(StudentScore)
class StudentScoreAdmin(admin.ModelAdmin):
    list_display = ['student', 'subject_code', 'subject_name', 'score', 'grade']
    search_fields = ['student__user__username', 'subject_code']