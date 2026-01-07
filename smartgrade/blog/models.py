from django.db import models
from django.contrib.auth.models import User
from django.db.models import Avg
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
    
    # --- Logic ความเสี่ยง (IF-ELSE) ---
    @property
    def risk_status(self):
        # หาค่าเฉลี่ยการเข้าเรียนจากทุก Record
        avg_attendance = self.behaviors.aggregate(Avg('attendance_score'))['attendance_score__avg']
        
        if avg_attendance is None:
            return "unknown" # ยังไม่มีข้อมูล
            
        # Logic ตามโจทย์
        if avg_attendance < 50:
            return "critical" # สีแดง: เสี่ยงสูง (เข้าเรียนน้อยกว่า 50%)
        elif avg_attendance < 80:
            return "warning"  # สีเหลือง: เฝ้าระวัง (เข้าเรียน 50-79%)
        else:
            return "normal"   # สีเขียว: ปกติ

class BehaviorRecord(models.Model):
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='behaviors')
    attendance_score = models.IntegerField(default=0)   # percent
    quiz_score = models.FloatField(default=0.0)
    homework_done = models.BooleanField(default=False)
    activity_score = models.IntegerField(default=0)
    record_date = models.DateField(default=timezone.now)

    def __str__(self):
        return f"{self.student.user.username} - {self.record_date}"
    
class StudentFeedback(models.Model):
    FEEDBACK_TYPES = [
        ('general', 'ทั่วไป'),
        ('praise', 'ชื่นชม'),
        ('warn', 'ตักเตือน'),
    ]
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='feedbacks')
    teacher = models.ForeignKey(User, on_delete=models.CASCADE) # คนส่ง
    feedback_type = models.CharField(max_length=20, choices=FEEDBACK_TYPES, default='general')
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.feedback_type} - {self.student.user.username}"

class TeacherNote(models.Model):
    # โน้ตส่วนตัวครู (คนอื่นไม่เห็น)
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='private_notes')
    teacher = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=100)
    note_type = models.CharField(max_length=50, default='ทั่วไป') # เช่น สิ่งที่ต้องทำ, ติดตามผล
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

class UrgentContact(models.Model):
    CONTACT_TARGETS = [('student', 'นักเรียน'), ('parent', 'ผู้ปกครอง'), ('guardian', 'ที่อยู่ตามทะเบียน')]
    CONTACT_METHODS = [('system', 'ระบบแจ้งเตือน'), ('email', 'Email'), ('call', 'โทรศัพท์'), ('other', 'อื่นๆ')]
    
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='contact_logs')
    teacher = models.ForeignKey(User, on_delete=models.CASCADE)
    target = models.CharField(max_length=20, choices=CONTACT_TARGETS)
    method = models.CharField(max_length=20, choices=CONTACT_METHODS)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)