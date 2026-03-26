from django.db import models
from django.contrib.auth.models import User
from django.db.models import Avg
from django.utils import timezone

class UserProfile(models.Model):
    ROLE_CHOICES = (
        ('student', 'Student'),
        ('teacher', 'Teacher'),
    )

    DEPARTMENT_CHOICES = [
        ('math', 'คณิตศาสตร์'),
        ('sci', 'วิทยาศาสตร์'),
        ('eng', 'ภาษาต่างประเทศ'),
        ('thai', 'ภาษาไทย'),
        ('soc', 'สังคมศึกษา'),
        ('art', 'ศิลปะ'),
        ('pe', 'สุขศึกษาและพลศึกษา'),
        ('work', 'การงานอาชีพ'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='student')

    profile_image = models.ImageField(
        upload_to='profile_pics/',
        blank=True,
        null=True
    )

    nickname = models.CharField(max_length=50, blank=True, null=True, verbose_name="ชื่อเล่น")
    bio = models.TextField(blank=True, null=True, verbose_name="แนะนำตัว")
    phone = models.CharField(max_length=20, blank=True, null=True, verbose_name="เบอร์โทรศัพท์")

    line_id = models.CharField(max_length=50, blank=True, null=True, verbose_name="Line ID")
    
    department = models.CharField(
        max_length=100, 
        choices=DEPARTMENT_CHOICES, 
        blank=True, 
        null=True, 
        verbose_name="กลุ่มสาระฯ"
    )
    
    position = models.CharField(max_length=100, blank=True, null=True, verbose_name="ตำแหน่ง")

    class_name = models.CharField(max_length=50, blank=True, null=True, verbose_name="ห้องเรียน")

    def __str__(self):
        return f"{self.user.username} ({self.role})"

class Student(models.Model):
    student_id = models.AutoField(primary_key=True)
    username = models.CharField(max_length=50, unique=True) 
    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=128)
    class_name = models.CharField(max_length=50)

    def __str__(self):
        return self.name

class StudentProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    teachers = models.ManyToManyField(User, related_name='my_students', blank=True)
    class_name = models.CharField(max_length=50, blank=True)
    profile_image = models.ImageField(upload_to='profiles/', blank=True, null=True)
    nickname = models.CharField(max_length=50, blank=True, null=True, verbose_name="ชื่อเล่น")
    bio = models.TextField(blank=True, null=True, verbose_name="แนะนำตัว")
    phone = models.CharField(max_length=20, blank=True, null=True, verbose_name="เบอร์โทร")
    
    line_id = models.CharField(max_length=50, blank=True, null=True)
    department = models.CharField(max_length=100, blank=True, null=True, verbose_name="กลุ่มสาระฯ")
    position = models.CharField(max_length=100, blank=True, null=True, verbose_name="ตำแหน่ง")
    
    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username}"
    
    @property
    def risk_status(self):
        latest = self.behaviors.order_by('-record_date', '-id').first()
        if not latest: return "unknown"
        
        score = latest.attendance_score
        if score < 50: return "critical" 
        if score < 60: return "warning"  
        return "normal" 

class TeacherProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    
    profile_image = models.ImageField(upload_to='teacher_images/', blank=True, null=True)
    nickname = models.CharField(max_length=50, blank=True, null=True, verbose_name="ชื่อเล่น")
    bio = models.TextField(blank=True, null=True, verbose_name="แนะนำตัว")
    phone = models.CharField(max_length=20, blank=True, null=True, verbose_name="เบอร์โทร")
    line_id = models.CharField(max_length=50, blank=True, null=True, verbose_name="Line ID")
    
    department = models.CharField(max_length=100, blank=True, null=True, verbose_name="กลุ่มสาระฯ")
    position = models.CharField(max_length=100, blank=True, null=True, verbose_name="ตำแหน่ง")

    def __str__(self):
        return f"Teacher: {self.user.username}"

class BehaviorRecord(models.Model):
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='behaviors')
    
    teacher = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='teacher_behaviors',
        verbose_name="ครูผู้บันทึก"
    )

    attendance_score = models.IntegerField(default=0)
    quiz_score = models.FloatField(default=0.0)
    homework_done = models.BooleanField(default=False)
    activity_score = models.IntegerField(default=0)
    record_date = models.DateField(default=timezone.now)
    subject = models.CharField(max_length=100, default="General", verbose_name="วิชา")
    
    def __str__(self):
        return f"{self.student.user.username} - {self.record_date}"

class StudentScore(models.Model):
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='exam_scores')

    subject_code = models.CharField(max_length=20, verbose_name="รหัสวิชา")
    subject_name = models.CharField(max_length=200, verbose_name="ชื่อวิชา")
    academic_year = models.CharField(max_length=10, verbose_name="ปีการศึกษา", blank=True) # เช่น 2568
    semester = models.CharField(max_length=10, verbose_name="เทอม", blank=True) # เช่น 1, 2
    
    score = models.FloatField(default=0.0, verbose_name="คะแนนที่ได้")
    max_score = models.FloatField(default=100.0, verbose_name="คะแนนเต็ม")
    grade = models.CharField(max_length=5, blank=True, null=True, verbose_name="เกรด") # A, B+, 4.0

    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.subject_code} - {self.student.user.username} ({self.score})"

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
    subject = models.CharField(max_length=100, default="General", verbose_name="วิชา")
    created_at = models.DateTimeField(auto_now_add=True)
    department = models.CharField(
        max_length=100, 
        choices=UserProfile.DEPARTMENT_CHOICES, 
        blank=True, 
        null=True,
        verbose_name="วิชา/กลุ่มสาระ"
    )

    def __str__(self):
        return f"{self.feedback_type} - {self.student.user.username}"

class TeacherNote(models.Model):
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='private_notes')
    teacher = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=100)
    note_type = models.CharField(max_length=50, default='ทั่วไป')
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

class PrivateNote(models.Model):
    teacher = models.ForeignKey(User, on_delete=models.CASCADE)
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='student_private_notes') # นักเรียนที่ถูกเขียนถึง
    title = models.CharField(max_length=200)
    content = models.TextField()
    
    note_type = models.CharField(max_length=50, default='general')
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} ({self.student.user.username})"

class UrgentContact(models.Model):
    CONTACT_TARGETS = [('student', 'นักเรียน'), ('parent', 'ผู้ปกครอง'), ('guardian', 'ที่อยู่ตามทะเบียน')]
    CONTACT_METHODS = [('system', 'ระบบแจ้งเตือน'), ('email', 'Email'), ('call', 'โทรศัพท์'), ('other', 'อื่นๆ')]
    
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='contact_logs')
    teacher = models.ForeignKey(User, on_delete=models.CASCADE)
    target = models.CharField(max_length=20, choices=CONTACT_TARGETS)
    method = models.CharField(max_length=20, choices=CONTACT_METHODS)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
