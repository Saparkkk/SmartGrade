from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class UserProfile(models.Model):
    ROLE_CHOICES = (
        ('student', 'Student'),
        ('teacher', 'Teacher'),
    )
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='student')

    profile_image = models.ImageField(
        upload_to='profile_pics/',
        blank=True,
        null=True
    )

    def __str__(self):
        return f"{self.user.username} ({self.role})"

class Student(models.Model):
    student_id = models.AutoField(primary_key=True)
    username = models.CharField(max_length=50, unique=True) # ควรเก็บแบบ hash
    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=128)
    class_name = models.CharField(max_length=50)

    def __str__(self):
        return self.name

class StudentProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    class_name = models.CharField(max_length=50, blank=True)
    profile_image = models.ImageField(upload_to='profiles/', blank=True, null=True)

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username}"

class BehaviorRecord(models.Model):
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='behaviors')
    attendance_score = models.IntegerField(default=0)   # percent
    quiz_score = models.FloatField(default=0.0)
    homework_done = models.BooleanField(default=False)
    activity_score = models.IntegerField(default=0)
    record_date = models.DateField(default=timezone.now)

    def __str__(self):
        return f"{self.student.user.username} - {self.record_date}"