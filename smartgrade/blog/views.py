# 1. Standard Libraries
import csv
import io
import json
from datetime import datetime
from collections import defaultdict
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.contrib import messages
from django import forms
from django.db.models import Q
from django.utils import timezone
from .forms import RegisterForm, StudentProfileForm, TeacherProfileForm, BehaviorForm, FeedbackForm, PrivateNoteForm, ContactForm, UserCreationForm
from .models import StudentProfile, BehaviorRecord, UserProfile, StudentFeedback, PrivateNote, UrgentContact, StudentScore
# ==========================================
# ส่วนจัดการสิทธิ์ (Permissions)
# ==========================================

def is_admin(user):
    """ตรวจสอบว่าผู้ใช้มีสิทธิ์เป็น Superuser (Admin) หรือไม่"""
    return user.is_superuser

# ==========================================
# ส่วนผู้ดูแลระบบ (Admin Views)
# ==========================================

@user_passes_test(is_admin)
def admin_dashboard(request):
    """หน้า Dashboard สำหรับ Admin: แสดงสถิติจำนวนอาจารย์และนักเรียน"""
    # ดึงมาแค่ข้อมูลบัญชีตาม Use Case
    teachers = User.objects.filter(is_staff=True, is_superuser=False)
    students = User.objects.filter(is_staff=False)
    total_users = teachers.count() + students.count()
    
    context = {
        'teachers': teachers,
        'students': students,
        'total_users': total_users,
    }
    return render(request, 'admin/admin_dashboard.html', context)

def manage_teachers(request):
    """หน้าจัดการข้อมูลอาจารย์: ดึงเฉพาะผู้ใช้ที่เป็น Staff แต่ไม่ใช่ Superuser"""
    teachers = User.objects.filter(is_staff=True, is_superuser=False)
    return render(request, 'admin/manage_teachers.html', {'teachers': teachers})

def manage_students(request):
    """หน้าจัดการข้อมูลนักเรียน: ดึงเฉพาะผู้ใช้ที่ไม่ใช่ Staff"""
    students = User.objects.filter(is_staff=False)
    return render(request, 'admin/manage_students.html', {'students': students})

def add_user(request):
    """เพิ่มผู้ใช้งานใหม่โดย Admin"""
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, f"สร้างบัญชี {user.username} สำเร็จแล้ว!")
            return redirect('admin_dashboard')
    else:
        form = UserCreationForm()
    
    return render(request, 'admin/add_user.html', {'form': form})

# ==========================================
# ส่วนฟอร์มแก้ไขผู้ใช้งาน (Forms)
# ==========================================

class EditUserForm(forms.ModelForm):
    """ฟอร์มสำหรับการแก้ไขข้อมูลพื้นฐานของ User"""
    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'is_active', 'is_staff']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'w-full px-4 py-2 border rounded-xl focus:ring-2 focus:ring-blue-500 outline-none'}),
            'first_name': forms.TextInput(attrs={'class': 'w-full px-4 py-2 border rounded-xl focus:ring-2 focus:ring-blue-500 outline-none'}),
            'last_name': forms.TextInput(attrs={'class': 'w-full px-4 py-2 border rounded-xl focus:ring-2 focus:ring-blue-500 outline-none'}),
            'email': forms.EmailInput(attrs={'class': 'w-full px-4 py-2 border rounded-xl focus:ring-2 focus:ring-blue-500 outline-none'}),
        }

# ==========================================
# ส่วนแก้ไขและลบผู้ใช้งาน (CRUD Operations)
# ==========================================

def edit_user(request, user_id):
    """แก้ไขข้อมูลผู้ใช้งานโดยระบุ ID"""
    user_to_edit = get_object_or_404(User, id=user_id)
    
    if request.method == 'POST':
        form = EditUserForm(request.POST, instance=user_to_edit)
        if form.is_valid():
            form.save()
            messages.success(request, 'อัปเดตข้อมูลสำเร็จแล้ว!')
            # เปลี่ยนเส้นทางตามสถานะของผู้ใช้ที่ถูกแก้ไข
            if user_to_edit.is_staff:
                return redirect('manage_teachers')
            return redirect('manage_students')
    else:
        form = EditUserForm(instance=user_to_edit)
        
    return render(request, 'admin/edit_user.html', {
        'form': form,
        'user_to_edit': user_to_edit
    })
    
def delete_user(request, user_id):
    """ลบผู้ใช้งานทีละคน"""
    user_to_delete = get_object_or_404(User, id=user_id)
    
    # ป้องกันไม่ให้ Admin ลบตัวเอง
    if request.user.id == user_to_delete.id:
        messages.error(request, "คุณไม่สามารถลบบัญชีของตัวเองได้!")
        return redirect('admin_dashboard')

    is_staff = user_to_delete.is_staff
    user_to_delete.delete()
    messages.success(request, f"ลบบัญชี {user_to_delete.username} เรียบร้อยแล้ว")
    
    if is_staff:
        return redirect('manage_teachers')
    return redirect('manage_students')

@require_POST
@login_required
def bulk_delete_users(request):
    """ลบผู้ใช้งานแบบกลุ่ม (Bulk Delete) รองรับผ่านการเรียก API (AJAX/Fetch)"""
    try:
        # รับข้อมูล ID ที่ส่งมาจาก JavaScript (ส่งมาเป็น JSON)
        data = json.loads(request.body)
        user_ids = data.get('user_ids', [])
        
        if not user_ids:
            return JsonResponse({'status': 'error', 'message': 'ไม่ได้เลือกรายการ'}, status=400)
            
        # กรองไม่ให้ลบตัวเอง
        if request.user.id in user_ids:
            user_ids.remove(request.user.id)
            
        # ลบ User ทั้งหมดที่อยู่ในลิสต์
        deleted_count, _ = User.objects.filter(id__in=user_ids).delete()
        
        return JsonResponse({
            'status': 'success', 
            'message': f'ลบข้อมูลสำเร็จ {deleted_count} รายการ'
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

# ==========================================
# ส่วนจัดการโปรไฟล์ (Profile Management)
# ==========================================

def get_role_for_user(user):
    """ฟังก์ชันช่วยเหลือ (Helper) สำหรับดึงหรือสร้างโปรไฟล์ผู้ใช้ และเช็ค Role"""
    default_role = 'teacher' if user.is_staff else 'student'
    
    user_profile, created = UserProfile.objects.get_or_create(
        user=user,
        defaults={"role": default_role} 
    )
    
    # ปรับปรุง Role ให้ตรงกับ is_staff อัตโนมัติเผื่อมีการเปลี่ยนแปลงสิทธิ์
    if user.is_staff and user_profile.role == 'student':
        user_profile.role = 'teacher'
        user_profile.save()
        
    return user_profile

@login_required
def profile_detail(request):
    """หน้าแสดงรายละเอียดโปรไฟล์ส่วนตัว"""
    try:
        user_profile = UserProfile.objects.get(user=request.user)
    except UserProfile.DoesNotExist:
        user_profile = None

    context = {
        "user_profile": user_profile,
        "role": user_profile.role if user_profile else None, 
    }

    return render(request, "management/profile_detail.html", context)

@login_required
def profile_edit(request):
    """หน้าแก้ไขโปรไฟล์ส่วนตัว (แยกฟอร์มตาม Role: Teacher / Student)"""
    user = request.user
    user_profile, created = UserProfile.objects.get_or_create(user=user)
    role = user_profile.role

    # เลือกใช้งานฟอร์มตามตำแหน่ง (Role)
    if role == 'teacher':
        FormClass = TeacherProfileForm
    else:
        FormClass = StudentProfileForm

    if request.method == 'POST':
        form = FormClass(request.POST, request.FILES)
        
        if form.is_valid():
            # อัปเดตข้อมูลในโมเดล User พื้นฐาน
            user.first_name = form.cleaned_data.get('first_name', '')
            user.last_name = form.cleaned_data.get('last_name', '')
            user.save()

            # อัปเดตข้อมูลในโมเดล UserProfile
            user_profile.nickname = form.cleaned_data.get('nickname', '')
            user_profile.bio = form.cleaned_data.get('bio', '')
            user_profile.phone = form.cleaned_data.get('phone', '')

            if form.cleaned_data.get('profile_image'):
                user_profile.profile_image = form.cleaned_data.get('profile_image')

            # บันทึกข้อมูลเฉพาะของแต่ละ Role
            if role == 'teacher':
                user_profile.department = form.cleaned_data.get('department', '')
                user_profile.position = form.cleaned_data.get('position', '')
                user_profile.line_id = form.cleaned_data.get('line_id', '')
            elif role == 'student':
                user_profile.class_name = form.cleaned_data.get('class_name', '')
                user_profile.line_id = form.cleaned_data.get('line_id', '')

            user_profile.save()

            messages.success(request, 'บันทึกข้อมูลเรียบร้อยแล้ว')
            return redirect('profile') # กลับไปยังหน้า Profile หลังจากบันทึกสำเร็จ
    else:
        # เตรียมข้อมูลเดิมมาแสดงในฟอร์ม
        initial_data = {
            'first_name': user.first_name,
            'last_name': user.last_name,
            'email': user.email,
            'nickname': user_profile.nickname,
            'bio': user_profile.bio,
            'phone': user_profile.phone,
        }
        
        if role == 'teacher':
            initial_data['department'] = user_profile.department
            initial_data['position'] = user_profile.position
            initial_data['line_id'] = user_profile.line_id
        elif role == 'student':
            initial_data['class_name'] = user_profile.class_name
            initial_data['line_id'] = user_profile.line_id

        form = FormClass(initial=initial_data)

    return render(request, 'management/profile_edit.html', {
        'form': form,
        'user_profile': user_profile,
        'role': role
    })

# ==========================================
# ส่วนยืนยันตัวตนและการประเมิน (Authentication & Evaluation)
# ==========================================

def register_view(request):
    """หน้าลงทะเบียนสำหรับผู้ใช้งานใหม่"""
    if request.method == 'POST':
        form = RegisterForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save()
            messages.success(request, "ลงทะเบียนสำเร็จ เข้าใช้งานได้เลย")
            return redirect('login')
    else:
        form = RegisterForm()
    return render(request, 'management/register.html', {'form': form})

def login_view(request):
    """หน้าเข้าสู่ระบบ"""
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            return redirect('dashboard')
        else:
            messages.error(request, "username หรือ password ไม่ถูกต้อง")
    return render(request, 'management/login.html')

def logout_view(request):
    """ระบบออกจากระบบ"""
    logout(request)
    return redirect('login')

def evaluate_status(behavior):
    """
    ฟังก์ชันประเมินสถานะของนักเรียนจากคะแนนพฤติกรรม
    คืนค่าเป็น Tuple (ข้อความสถานะ, สีที่ใช้แสดงผล, คำอธิบายเพิ่มเติม)
    """
    if behavior is None:
        return "ยังไม่มีข้อมูล", "gray", "ยังไม่มีข้อมูลพฤติกรรม"

    total = (
        (behavior.attendance_score or 0) +
        (behavior.quiz_score or 0) +
        (behavior.activity_score or 0)
    )
    
    if total >= 80 and behavior.homework_done:
        return "ปลอดภัย", "green", "มีแนวโน้มผ่าน"
    elif total >= 60:
        return "เริ่มมีความเสี่ยง", "yellow", "เสี่ยงเล็กน้อย"
    else:
        return "มีความเสี่ยงสูง", "red", "ควรได้รับความช่วยเหลือ"

@login_required
def dashboard(request):
    """
    Dashboard หลัก (Router): 
    ใช้กระจายผู้ใช้งานไปยัง Dashboard ที่เหมาะสมตาม Role ของตัวเอง
    """
    user = request.user
    user_profile = get_role_for_user(user)
    
    if user_profile.role == "teacher":
        return redirect("teacher_dashboard")
    else:
        return redirect("student_dashboard")

# ==========================================
# ส่วนหน้าแดชบอร์ดครู (Teacher Dashboard)
# ==========================================

@login_required
def teacher_dashboard(request):
    """
    หน้า Dashboard หลักสำหรับครู: 
    แสดงภาพรวมของนักเรียน คัดกรองนักเรียนที่มีความเสี่ยง และรองรับการค้นหา/กรองตามห้องเรียน
    """
    if not request.user.is_staff:
        return redirect('student_dashboard')

    all_students_raw = StudentProfile.objects.filter(teachers=request.user).select_related('user').order_by('class_name')
    
    search_query = request.GET.get('q', '') 
    class_filter = request.GET.get('class_filter', '')
    query_for_filter = all_students_raw 
    
    if search_query:
        query_for_filter = query_for_filter.filter(
            Q(user__first_name__icontains=search_query) | Q(user__username__icontains=search_query)
        )
    if class_filter:
        query_for_filter = query_for_filter.filter(class_name=class_filter)
        
    filtered_ids = set(query_for_filter.values_list('id', flat=True))

    table_list = []
    widget_list = [] 
    all_classes = all_students_raw.values_list('class_name', flat=True).distinct().order_by('class_name')
    user_profile = get_role_for_user(request.user)
    
    for s in all_students_raw:
        latest = s.behaviors.filter(teacher=request.user).order_by('-record_date', '-id').first()
        
        stat_att = 0 # อาจจะเก็บไว้แสดงผลแยกต่างหากถ้าต้องการ
        stat_score = 0
        risk_status = "none"
        risk_label = "ไม่มีข้อมูล"
        risk_class = "bg-gray-100 text-gray-400"

        if latest:
            quiz = getattr(latest, 'quiz_score', 0)
            att = getattr(latest, 'attendance_score', 0)
            act = getattr(latest, 'activity_score', 0)
            
            # 1. หาค่าเฉลี่ยก่อน (ตอนนี้เต็ม 10)
            avg_score = (quiz + att + act) / 3
            
            # 2. แปลงเป็นฐาน 100 (คูณ 10) แล้วค่อยปัดทศนิยม
            stat_score = round(avg_score * 10, 2) 
            stat_att = att * 10 # ถ้าอยากให้การเข้าเรียนแสดงเป็น % ด้วยก็คูณ 10 ได้เลย
            
            # ประเมินความเสี่ยงจากคะแนนเฉลี่ย
            if stat_score < 50:
                risk_status = "critical"
                risk_label = "เสี่ยงสูง"
                risk_class = "bg-red-100 text-red-700"
            elif stat_score < 70:
                risk_status = "warning"
                risk_label = "เฝ้าระวัง"
                risk_class = "bg-yellow-100 text-yellow-700"
            else:
                risk_status = "normal"
                risk_label = "ปลอดภัย"
                risk_class = "bg-green-100 text-green-700"

        s_data = {
            'info': s,
            'stat_att': stat_att,
            'stat_score': stat_score,
            'risk_status': risk_status,
            'risk_label': risk_label,
            'risk_class': risk_class,
        }
        
        if risk_status == 'critical': 
            widget_list.append(s_data)

        if s.id in filtered_ids:
            table_list.append(s_data)

    unique_widget = list({v['info'].id: v for v in widget_list}.values())

    return render(request, 'management/teacher_dashboard.html', {
        "students": table_list,
        "risk_list": unique_widget,
        "total_students": all_students_raw.count(),
        "risk_count": len(unique_widget),
        "search_query": search_query,
        "class_filter": class_filter,
        "all_classes": all_classes,
        "user_profile": user_profile,
    })

# ==========================================
# ส่วนหน้ารายชื่อนักเรียน (Student List)
# ==========================================

@login_required
def teacher_student_list(request):
    """หน้ารายชื่อนักเรียนทั้งหมดที่อยู่ในความดูแลของครู พร้อมระบบค้นหาและฟิลเตอร์"""
    students = StudentProfile.objects.filter(teachers=request.user).select_related('user').order_by('class_name')
    user_profile = get_role_for_user(request.user)
    
    # ระบบค้นหา (ชื่อผู้ใช้ หรือ ชื่อจริง)
    search_query = request.GET.get('q')
    if search_query:
        students = students.filter(
            Q(user__username__icontains=search_query) | 
            Q(user__first_name__icontains=search_query)
        )
        
    # ระบบกรองตามห้องเรียน
    class_filter = request.GET.get('class_name')
    if class_filter:
        students = students.filter(class_name=class_filter)
        
    all_classes = StudentProfile.objects.filter(teachers=request.user).values_list('class_name', flat=True).distinct().order_by('class_name')

    final_list = []
    # แนบสถานะความเสี่ยงล่าสุดไปกับอ็อบเจกต์นักเรียนแต่ละคน
    for s in students:
        latest_record = s.behaviors.filter(teacher=request.user).order_by('-record_date').first()
        
        s.debug_score = 0
        s.custom_status = "unknown"
        s.last_date = "-"

        if latest_record:
            # ---------------------------------------------------------
            # ดึงคะแนน 3 ส่วนมาหาค่าเฉลี่ย (Quiz, Attendance, Activity)
            # ---------------------------------------------------------
            q = getattr(latest_record, 'quiz_score', 0)
            a = getattr(latest_record, 'attendance_score', 0)
            act = getattr(latest_record, 'activity_score', 0)
            
            avg_score = (q + a + act) / 3
            s.debug_score = round(avg_score * 10, 2) # เก็บเป็นค่าเฉลี่ย (ปัดทศนิยม 2 ตำแหน่ง)
            s.last_date = latest_record.record_date
            
            # ประเมินเกณฑ์ให้ตรงกับหน้า Dashboard (<50 แดง, <70 เหลือง, นอกนั้นเขียว)
            if s.debug_score < 50:
                s.custom_status = "critical" 
            elif s.debug_score < 70:
                s.custom_status = "warning" 
            else:
                s.custom_status = "normal" 
            
        final_list.append(s)

    return render(request, 'management/teacher_student_list.html', {
        'students': final_list, 
        'all_classes': all_classes,
        'search_query': search_query,
        'class_filter': class_filter,
        'user_profile': user_profile,
    })

# ==========================================
# ส่วนหน้ารายละเอียดของนักเรียน (Student Detail)
# ==========================================

@login_required
def teacher_student_detail(request, student_id):
    """
    หน้ารายละเอียดของนักเรียนรายบุคคล (มุมมองครู):
    - คำนวณสถานะความเสี่ยงแบบ Real-time (Average Quiz + Att + Act * 10)
    - แสดงประวัติพฤติกรรม, Feedback, โน้ตส่วนตัว และการติดต่อ
    - รองรับการเพิ่มข้อมูลผ่านฟอร์มต่างๆ
    """
    student = get_object_or_404(StudentProfile, id=student_id)

    # 1. ดึงข้อมูลประวัติต่างๆ ที่เกี่ยวข้อง
    behaviors = student.behaviors.filter(teacher=request.user).order_by('-record_date', '-id')
    latest_record = behaviors.first()
    
    # ---------------------------------------------------------
    # [LOGIC] คำนวณสถานะความเสี่ยงให้สอดคล้องกับ Dashboard (ฐาน 100)
    # ---------------------------------------------------------
    student.risk_level = "none" # ค่าเริ่มต้นกรณีไม่มีข้อมูล
    if latest_record:
        q = getattr(latest_record, 'quiz_score', 0)
        a = getattr(latest_record, 'attendance_score', 0)
        act = getattr(latest_record, 'activity_score', 0)
        
        # หาร 3 คูณ 10 เพื่อให้เป็นฐาน 100
        total_percent = ((q + a + act) / 3) * 10 
        
        if total_percent < 50:
            student.risk_level = "critical"
        elif total_percent < 70:
            student.risk_level = "warning"
        else:
            student.risk_level = "normal"
    # ---------------------------------------------------------

    # ดึงข้อมูลส่วนอื่นๆ
    records = BehaviorRecord.objects.filter(student=student, teacher=request.user).order_by('-record_date')
    feedbacks = student.feedbacks.filter(teacher=request.user).order_by('-created_at')
    notes = PrivateNote.objects.filter(student=student, teacher=request.user).order_by('-created_at')
    contacts = student.contact_logs.filter(teacher=request.user).order_by('-created_at')

    # เตรียมฟอร์มเปล่า
    behavior_form = BehaviorForm()
    feedback_form = FeedbackForm()
    note_form = PrivateNoteForm()
    contact_form = ContactForm()

    # Mapping รายวิชาภาษาไทย
    dept_map = {
        'math': 'คณิตศาสตร์', 'sci': 'วิทยาศาสตร์', 'eng': 'ภาษาต่างประเทศ',
        'thai': 'ภาษาไทย', 'soc': 'สังคมศึกษา', 'art': 'ศิลปะ',
        'pe': 'สุขศึกษาและพลศึกษา', 'work': 'การงานอาชีพ',
        'comp': 'คอมพิวเตอร์', 'guidance': 'แนะแนว',
    }

    user_profile = get_role_for_user(request.user)
    
    # 2. จัดการการส่งฟอร์ม (POST Requests)
    if request.method == "POST":
        action = request.POST.get('action')

        # เพิ่มบันทึกพฤติกรรม/คะแนน
        if action == 'add_behavior':
            form = BehaviorForm(request.POST)
            if form.is_valid():
                obj = form.save(commit=False)
                obj.student = student
                obj.teacher = request.user 
                
                # กำหนดวิชาอัตโนมัติตามกลุ่มสาระของครู
                if user_profile and user_profile.department:
                    dept_code = user_profile.department
                    obj.subject = dept_map.get(dept_code, dept_code)
                else:
                    obj.subject = f"วิชาทั่วไป ({request.user.first_name})"
                
                obj.save()
                messages.success(request, f"บันทึกข้อมูลสำเร็จ")

        # ลบบันทึกพฤติกรรม
        elif action == 'delete_behavior':
            record_id = request.POST.get('record_id')
            record_to_delete = BehaviorRecord.objects.filter(id=record_id, student=student, teacher=request.user).first()
            if record_to_delete:
                record_to_delete.delete()
                messages.success(request, "ลบรายการเรียบร้อยแล้ว")

        # เพิ่ม Feedback
        elif action == 'add_feedback':
            form = FeedbackForm(request.POST)
            if form.is_valid():
                obj = form.save(commit=False)
                obj.student = student
                obj.teacher = request.user
                obj.subject = dept_map.get(user_profile.department, "General") if user_profile else "General"
                obj.save()
                messages.success(request, "ส่งข้อเสนอแนะเรียบร้อย")

        # เพิ่มโน้ตส่วนตัว
        elif action == 'add_note':
            form = PrivateNoteForm(request.POST)
            if form.is_valid():
                obj = form.save(commit=False)
                obj.student = student
                obj.teacher = request.user
                obj.save()
                messages.success(request, "บันทึกโน้ตแล้ว")

        # เพิ่มบันทึกการติดต่อ
        elif action == 'add_contact':
            form = ContactForm(request.POST)
            if form.is_valid():
                obj = form.save(commit=False)
                obj.student = student
                obj.teacher = request.user
                obj.save()
                messages.success(request, "บันทึกการติดต่อแล้ว")

        return redirect('teacher_student_detail', student_id=student.id)

    return render(request, 'management/teacher_student_detail.html', {
        'student': student,
        'records': records,
        'behaviors': behaviors,
        'feedbacks': feedbacks,
        'notes': notes,
        'contacts': contacts,
        'behavior_form': behavior_form,
        'feedback_form': feedback_form,
        'note_form': note_form,
        'contact_form': contact_form,
        'user_profile': user_profile,
    })

# ==========================================
# ส่วนจัดการนักเรียนและการลบข้อมูล (Teacher Management)
# ==========================================

@login_required
def teacher_add_student_manual(request):
    """หน้าสำหรับครูเพื่อเพิ่มนักเรียนเข้าห้องเรียนด้วยตัวเอง (Manual) ผ่านรหัสนักเรียน (Username)"""
    user_profile = get_role_for_user(request.user)
    
    if request.method == 'POST':
        student_id = request.POST.get('student_id', '').strip()
        
        # ตรวจสอบว่ากรอกข้อมูลมาหรือไม่
        if not student_id:
            messages.error(request, "กรุณากรอกรหัสนักเรียน")
            return redirect('teacher_add_student_manual')

        try:
            # ค้นหานักเรียนจาก Username (ซึ่งมักใช้เป็นรหัสนักเรียน)
            student = StudentProfile.objects.select_related('user').get(user__username=student_id)
            
            # ตรวจสอบว่านักเรียนคนนี้อยู่ในห้องเรียนของครูคนนี้อยู่แล้วหรือไม่
            if student.teachers.filter(id=request.user.id).exists():
                messages.warning(request, f"นักเรียน {student.user.get_full_name()} ({student_id}) อยู่ในห้องเรียนของคุณอยู่แล้ว")
            else:
                # เพิ่มครูคนนี้เข้าไปในรายชื่อครูผู้สอนของนักเรียน
                student.teachers.add(request.user)
                messages.success(request, f"เพิ่ม {student.user.get_full_name()} เข้าสู่ห้องเรียนเรียบร้อยแล้ว (เรียนร่วมกับวิชาอื่นได้)")
                return redirect('teacher_student_list')

        except StudentProfile.DoesNotExist:
            messages.error(request, f"ไม่พบนักเรียนรหัส '{student_id}' ในระบบ")
        except Exception as e:
            messages.error(request, f"เกิดข้อผิดพลาด: {e}")

    return render(request, 'management/teacher_add_student_manual.html', {
        'user_profile': user_profile
    })

def teacher_student_delete(request, student_id):
    """
    ลบข้อมูลนักเรียน
    ** ข้อควรระวัง: คำสั่ง user.delete() เป็นการลบบัญชีผู้ใช้งาน (User) ออกจากระบบอย่างถาวร 
    ไม่ได้เป็นเพียงการเตะออกจากห้องเรียน
    """
    student = get_object_or_404(StudentProfile, id=student_id)
    user = student.user
    user.delete()
    messages.success(request, f"ลบนักเรียน {user.username} เรียบร้อยแล้ว")
    return redirect('teacher_student_list')

def behavior_delete(request, behavior_id):
    """ลบรายการบันทึกพฤติกรรมของนักเรียน"""
    behavior = get_object_or_404(BehaviorRecord, id=behavior_id)
    student_id = behavior.student.id
    behavior.delete()
    messages.success(request, "ลบรายการพฤติกรรมเรียบร้อย")
    return redirect('teacher_student_detail', student_id=student_id)

# ==========================================
# ส่วนหน้าแดชบอร์ดนักเรียน (Student Dashboard)
# ==========================================

@login_required
def student_dashboard(request):
    """
    หน้า Dashboard หลักสำหรับนักเรียน:
    แสดงกราฟผลการเรียน การคำนวณ Health Score แยกตามรายวิชา ข้อความแจ้งเตือน และ Feedback จากครู
    """
    # ป้องกันไม่ให้ครู/Admin เข้าใช้งานหน้านี้
    if request.user.is_staff:
        return redirect('teacher_dashboard')

    user_profile = get_role_for_user(request.user)

    try:
        student = StudentProfile.objects.get(user=request.user)
        # ดึงประวัติล่าสุด 10 รายการ และดึงประวัติทั้งหมดเพื่อใช้วาดกราฟ/คำนวณ
        behaviors = BehaviorRecord.objects.filter(student=student).select_related('teacher', 'teacher__profile').order_by('-record_date')[:10]
        all_records_for_graph = BehaviorRecord.objects.filter(student=student).select_related('teacher', 'teacher__profile')
        
        # Mapping รหัสวิชาเป็นชื่อภาษาไทย
        dept_map = {
            'math': 'คณิตศาสตร์', 'sci': 'วิทยาศาสตร์', 'eng': 'ภาษาต่างประเทศ',
            'thai': 'ภาษาไทย', 'soc': 'สังคมศึกษา', 'art': 'ศิลปะ',
            'pe': 'สุขศึกษาและพลศึกษา', 'work': 'การงานอาชีพ'
        }
        # Mapping ครูที่เพิ่มเข้าระบบแบบ Manual (ถ้ามี)
        manual_teacher_map = {'Teacher01': 'วิทยาศาสตร์', 'Teacher02': 'ภาษาต่างประเทศ'}

        def get_subject_name(record):
            """ฟังก์ชันช่วยหาว่ารายการพฤติกรรมนี้มาจากวิชาอะไร"""
            if not record.teacher: return 'ประวัติเก่า (ไม่ระบุครู)'
            if record.teacher.username in manual_teacher_map:
                return manual_teacher_map[record.teacher.username]
            if hasattr(record.teacher, 'profile') and record.teacher.profile.department:
                code = record.teacher.profile.department
                return dept_map.get(code, code)
            
            # กรณีที่มีการระบุวิชาไว้ใน record โดยตรง
            db_sub = getattr(record, 'subject', '')
            if db_sub and db_sub not in ['วิชาทั่วไป', 'General', 'general', '', '-']:
                return db_sub
            return 'วิชาทั่วไป'

        # จัดกลุ่มข้อมูลพฤติกรรมแยกตามรายวิชา
        grouped_subjects = {}
        for record in all_records_for_graph:
            subj_name = get_subject_name(record)
            if subj_name not in grouped_subjects:
                grouped_subjects[subj_name] = []
            grouped_subjects[subj_name].append(record)

        subject_data = []
        chart_labels, chart_scores, chart_colors = [], [], []

        # คำนวณ Health Score ของแต่ละรายวิชา
        for name, records in grouped_subjects.items():
            if name == 'ประวัติเก่า (ไม่ระบุครู)': 
                continue

            count = len(records)
            if count == 0: continue

            # คำนวณเปอร์เซ็นต์คะแนน Quiz
            total_quiz = sum(r.quiz_score for r in records)
            s_quiz = min(100, (total_quiz / (count * 20)) * 100) 
            
            # คำนวณเปอร์เซ็นต์การเข้าเรียน (Attendance) ปรับฐานคะแนนตามค่าสูงสุดที่ครูตั้งไว้
            total_att = sum(r.attendance_score for r in records)
            max_val_att = max((r.attendance_score for r in records), default=0)
            base_score_att = 10 if max_val_att > 2 else 2
            s_att = min(100, (total_att / (count * base_score_att)) * 100)
            
            # คำนวณเปอร์เซ็นต์การส่งการบ้าน
            hw_done_count = sum(1 for r in records if r.homework_done)
            s_hw = (hw_done_count / count) * 100

            # น้ำหนักคะแนนรวม (Health Score): เข้าเรียน 40%, การบ้าน 30%, ควิซ 30%
            raw_health = (s_att * 0.4) + (s_hw * 0.3) + (s_quiz * 0.3)
            health_score = min(100, int(raw_health))

            # กำหนดสถานะและสีที่จะแสดงใน UI
            if health_score >= 70:
                sub_status = "Good"
                color_hex = "#10b981"
                bg_class = "bg-emerald-50 text-emerald-700 border-emerald-200"
            elif health_score >= 50:
                sub_status = "Warning"
                color_hex = "#f59e0b"
                bg_class = "bg-amber-50 text-amber-700 border-amber-200"
            else:
                sub_status = "Critical"
                color_hex = "#ef4444"
                bg_class = "bg-red-50 text-red-700 border-red-200"

            chart_labels.append(name)
            chart_scores.append(health_score)
            chart_colors.append(color_hex)
            
            subject_data.append({
                'name': name,
                'score': health_score,
                'status': sub_status,
                'bg_class': bg_class,
                'stats': {'att': int(s_att), 'hw': int(s_hw), 'quiz': int(s_quiz)}
            })

        # เรียงลำดับวิชาจากคะแนนน้อยไปมาก (เอาวิชาที่มีปัญหาขึ้นก่อน)
        subject_data.sort(key=lambda x: x['score'])
        
        # ดึงข้อความต่างๆ
        manual_feedbacks = StudentFeedback.objects.filter(student=student).order_by('-created_at')
        urgent_messages = UrgentContact.objects.filter(student=student, target='student').select_related('teacher').order_by('-created_at')

        # วิเคราะห์สถานะภาพรวมจากบันทึกล่าสุด
        latest = BehaviorRecord.objects.filter(student=student).order_by('-record_date').first()
        status, advice = "ไม่มีข้อมูล", "-"
        if latest:
            avg = (latest.attendance_score + latest.quiz_score + latest.activity_score) / 3
            if avg >= 70:
                status, advice = "ดีเยี่ยม", "รักษามาตรฐานนี้ต่อไป"
            elif avg >= 50:
                status, advice = "ปานกลาง", "ควรเพิ่มความสม่ำเสมอ"
            else:
                status, advice = "เสี่ยง", "ควรติดต่อครูผู้สอน"

    except StudentProfile.DoesNotExist:
        # กรณีไม่มีข้อมูลโปรไฟล์นักเรียน (Fallback)
        student, behaviors, subject_data = None, [], []
        chart_labels, chart_scores, chart_colors = [], [], []
        manual_feedbacks, urgent_messages = [], []
        status, advice = "-", "-"

    context = {
        'user_profile': user_profile, 'student': student, 'behaviors': behaviors,
        'status': status, 'advice': advice, 'subject_data': subject_data,
        'chart_labels': chart_labels, 'chart_scores': chart_scores, 'chart_colors': chart_colors,
        'manual_feedbacks': manual_feedbacks, 'urgent_messages': urgent_messages,
    }
    return render(request, 'management/student_dashboard.html', context)

# ==========================================
# ส่วนรายงานและสถิติเชิงลึก (Student Report - มุมมองครู)
# ==========================================

@login_required
def student_report(request, student_id):
    """
    หน้ารายงานผลนักเรียนแบบเจาะลึก (มุมมองครู):
    แสดงการวิเคราะห์สถานะด้วย AI, กราฟแนวโน้มรายวัน และแบบฟอร์มการเพิ่มโน้ต/การติดต่อ
    """
    student = get_object_or_404(StudentProfile, id=student_id)
    
    # จัดการ POST Requests สำหรับเพิ่มข้อมูล
    if request.method == "POST":
        action = request.POST.get('action')
        
        # บันทึกโน้ตส่วนตัว (สำหรับครูเท่านั้น)
        if action == 'add_note':
            form = PrivateNoteForm(request.POST)
            if form.is_valid():
                obj = form.save(commit=False)
                obj.student = student
                obj.teacher = request.user
                obj.save()
                messages.success(request, "บันทึกโน้ตเรียบร้อย")
                return redirect('student_report', student_id=student.id)
                
        # บันทึกประวัติการติดต่อผู้ปกครอง/นักเรียน
        elif action == 'add_contact':
            form = ContactForm(request.POST)
            if form.is_valid():
                obj = form.save(commit=False)
                obj.student = student
                obj.teacher = request.user
                obj.save()
                messages.success(request, "บันทึกการติดต่อเรียบร้อย")
                return redirect('student_report', student_id=student.id)

    # ดึงประวัติต่างๆ
    notes = PrivateNote.objects.filter(student=student, teacher=request.user).order_by('-created_at')
    contacts = student.contact_logs.all().order_by('-created_at')
    records = BehaviorRecord.objects.filter(student=student, teacher=request.user).order_by('-record_date', '-id')

    # วิเคราะห์และสร้างข้อความแจ้งเตือน (AI Status Simulation) อิงจากคะแนนการเข้าเรียนล่าสุด
    latest_rec = BehaviorRecord.objects.filter(student=student, teacher=request.user).order_by('-record_date', '-id').first()
    ai_status = "unknown"
    ai_message = "ไม่พบข้อมูลคะแนนล่าสุดสำหรับการวิเคราะห์"

    if latest_rec:
        # เปลี่ยนมาใช้คะแนนเฉลี่ย 3 ส่วนแทน
        q = getattr(latest_rec, 'quiz_score', 0)
        a = getattr(latest_rec, 'attendance_score', 0)
        act = getattr(latest_rec, 'activity_score', 0)
        score = round((q + a + act) / 3, 2)
        
        if score < 50: # เปลี่ยนเกณฑ์ให้ตรงกัน
            ai_status = "critical"
            ai_message = f"นักเรียนมีพฤติกรรมเสี่ยงสูง (คะแนนประเมินเฉลี่ย {score}/10) พบว่ามีการขาดเรียนหรือคะแนนต่ำในระดับวิกฤต ควรติดต่อผู้ปกครอง"
        elif score < 70:
            # ... (แก้ข้อความให้เข้ากับคะแนนเต็ม 10)
            ai_status = "warning"
            ai_message = f"นักเรียนอยู่ในกลุ่มเฝ้าระวัง (คะแนนประเมินเฉลี่ย {score}/10) เริ่มมีแนวโน้มพฤติกรรมถดถอย ควรสอบถามปัญหาเบื้องต้นหรือตักเตือน"
        else:
            ai_status = "normal"
            ai_message = f"นักเรียนมีพฤติกรรมปกติ (คะแนนประเมินเฉลี่ย {score}/10) รักษามาตรฐานการเข้าเรียนและส่งงานได้ดีเยี่ยม"

    # เตรียมข้อมูลสำหรับสร้างกราฟเส้น (Trend Chart) รายวัน
    history_records = BehaviorRecord.objects.filter(student=student, teacher=request.user).order_by('record_date')
    
    report_dates = []
    report_attendance = []
    report_quiz = []
    report_activity = []
    # จัดกลุ่มคะแนนตามวันที่ (หากวันเดียวกันบันทึกหลายครั้ง จะนำมาหาค่าเฉลี่ย)
    daily_data = defaultdict(lambda: {'att': [], 'quiz': [], 'act': []})
    
    for r in history_records:
        date_str = r.record_date.strftime('%d/%m')
        att_score = r.attendance_score if r.attendance_score else 0
        
        daily_data[date_str]['att'].append(att_score)
        daily_data[date_str]['quiz'].append(r.quiz_score)
        daily_data[date_str]['act'].append(r.activity_score)
        
    # หาค่าเฉลี่ยในแต่ละวัน เพื่อส่งไปพล็อตในกราฟ
    for date, values in daily_data.items():
        report_dates.append(date)
        report_attendance.append(round(sum(values['att']) / len(values['att']), 1))
        report_quiz.append(round(sum(values['quiz']) / len(values['quiz']), 1))
        report_activity.append(round(sum(values['act']) / len(values['act']), 1))

    # ดึงคะแนนผลการเรียนที่นำเข้าผ่านไฟล์ CSV (ถ้ามี)
    csv_scores = StudentScore.objects.filter(student=student).order_by('subject_code')
    
    return render(request, 'management/student_report.html', {
        'student': student,
        'records': records,
        'ai_status': ai_status,   
        'ai_message': ai_message,   
        'latest_rec': latest_rec,   
        'notes': notes,
        'contacts': contacts,
        'csv_scores': csv_scores,
        'report_dates': report_dates,
        'report_attendance': report_attendance,
        'report_quiz': report_quiz,
        'report_activity': report_activity,
    })

# ==========================================
# ส่วนรายละเอียดรายวิชาของนักเรียน (Student Subject Detail)
# ==========================================

@login_required
def student_subject_detail(request, subject_name):
    """
    หน้าแสดงรายละเอียดและสถิติของนักเรียนเจาะจงตามรายวิชา:
    ปรับปรุง: รวมคะแนนเฉลี่ย (Quiz, เข้าร่วม, กิจกรรม) และเตรียมข้อมูลกราฟ
    """
    # ป้องกันครูเข้าถึงหน้านี้
    if request.user.is_staff:
        return redirect('teacher_dashboard')

    try:
        # ดึงข้อมูลโปรไฟล์ของนักเรียนที่ล็อกอิน
        student = StudentProfile.objects.get(user=request.user)
        # ดึงประวัติพฤติกรรมทั้งหมดของนักเรียนคนนี้
        all_records = BehaviorRecord.objects.filter(student=student).select_related('teacher', 'teacher__profile').order_by('-record_date')
        
        filtered_records = []
        subject_teacher = None

        # Mapping หมวดหมู่วิชาและครูที่เพิ่มแบบ Manual
        dept_map = {
            'math': 'คณิตศาสตร์', 'sci': 'วิทยาศาสตร์', 'eng': 'ภาษาต่างประเทศ',
            'thai': 'ภาษาไทย', 'soc': 'สังคมศึกษา', 'art': 'ศิลปะ',
            'pe': 'สุขศึกษาและพลศึกษา', 'work': 'การงานอาชีพ'
        }
        manual_teacher_map = {
            'Teacher01': 'วิทยาศาสตร์',    
            'Teacher02': 'ภาษาต่างประเทศ',
        }

        def get_subj(r):
            """ฟังก์ชันช่วยหาชื่อวิชาจากข้อมูลบันทึกพฤติกรรมและข้อมูลครูผู้สอน"""
            if not r.teacher: return 'วิชาทั่วไป'
            if r.teacher.username in manual_teacher_map:
                return manual_teacher_map[r.teacher.username]
            
            full_name = f"{r.teacher.first_name} {r.teacher.last_name}".strip()
            if full_name in manual_teacher_map:
                return manual_teacher_map[full_name]

            if hasattr(r.teacher, 'profile') and r.teacher.profile.department:
                code = r.teacher.profile.department
                return dept_map.get(code, code)
            
            db_sub = getattr(r, 'subject', '')
            if db_sub and db_sub not in ['วิชาทั่วไป', 'General', 'general', '', '-']:
                return db_sub
            return 'วิชาทั่วไป'

        # กรองข้อมูลเอาเฉพาะประวัติที่ตรงกับชื่อวิชา (subject_name) ที่คลิกเข้ามา
        for record in all_records:
            if get_subj(record) == subject_name:
                filtered_records.append(record)
                if not subject_teacher and record.teacher:
                    subject_teacher = record.teacher

        count = len(filtered_records)
        avg_score = 0
        attendance_rate = 0
        present_count = late_count = absent_count = 0
        labels, scores, att_scores, total_avg_scores = [], [], [], []

        if count > 0:
            total_avg_sum = 0
            total_att_earned = 0
            
            # คำนวณคะแนนรวมและสถานะการเข้าเรียน
            for r in filtered_records:
                # ดึงคะแนน 3 ส่วน (ถ้าไม่มีให้เป็น 0)
                q = getattr(r, 'quiz_score', 0)
                a = getattr(r, 'attendance_score', 0)
                act = getattr(r, 'activity_score', 0)
                
                # หาค่าเฉลี่ยของ record นี้
                record_avg = (q + a + act) / 3
                total_avg_sum += record_avg
                total_att_earned += a
                
                # นับสถิติ มาเรียน, มาสาย, ขาดเรียน (อิงจากคะแนน attendance)
                if a >= 80: present_count += 1
                elif a > 0: late_count += 1
                else: absent_count += 1

            # 1. คะแนนเฉลี่ยรวมของวิชานี้ (ทุกครั้งที่บันทึก)
            avg_score = round(total_avg_sum / count, 2)

            # 2. อัตราการเข้าเรียน (เป็น %)
            max_val = max((getattr(r, 'attendance_score', 0) for r in filtered_records), default=0)
            score_base = max_val if max_val > 0 else 100 # ป้องกันการหารด้วย 0
            max_possible = count * score_base
            attendance_rate = round((total_att_earned / max_possible) * 100, 2) if max_possible > 0 else 0
            attendance_rate = min(100, attendance_rate) # กันค่าเกิน 100%

            # 3. เตรียมข้อมูลสำหรับวาดกราฟ (ย้อนหลัง 10 ครั้งล่าสุด นำมากลับลำดับเป็นเก่าไปใหม่)
            graph_data = filtered_records[:10][::-1]
            labels = [r.record_date.strftime('%d/%m') if r.record_date else '-' for r in graph_data]
            scores = [getattr(r, 'quiz_score', 0) for r in graph_data]
            att_scores = [getattr(r, 'attendance_score', 0) for r in graph_data]
            total_avg_scores = [round((getattr(r, 'quiz_score', 0) + getattr(r, 'attendance_score', 0) + getattr(r, 'activity_score', 0))/3, 2) for r in graph_data]

    except StudentProfile.DoesNotExist:
        student = None
        # กำหนดค่าเริ่มต้นกรณีไม่พบข้อมูล
        # (เว้นไว้ตามเดิมในโค้ดของคุณ)

    return render(request, 'management/student_subject_detail.html', {
        'subject_name': subject_name,
        'teacher': subject_teacher,
        'records': filtered_records,
        'avg_score': avg_score,
        'attendance_rate': attendance_rate,
        'present_count': present_count,
        'late_count': late_count,
        'absent_count': absent_count,
        'labels': labels,
        'scores': scores,
        'att_scores': att_scores,
        'total_avg_scores': total_avg_scores, # ส่งข้อมูลกราฟเส้นค่าเฉลี่ยรวมไปด้วย
    })

# ==========================================
# ส่วนการจัดการข้อมูลนักเรียนโดยครู (Teacher - Student Management)
# ==========================================

def teacher_student_edit(request, student_id):
    """หน้าสำหรับครูเพื่อแก้ไขข้อมูลชั้นเรียนและ Username ของนักเรียน"""
    student = get_object_or_404(StudentProfile, id=student_id)
    
    if request.method == "POST":
        student.class_name = request.POST.get('class_name')
        student.save()

        new_username = request.POST.get('username')
        # เช็คว่ามีการเปลี่ยน Username และ Username ใหม่ไม่ซ้ำกับคนอื่นในระบบ
        if new_username and new_username != student.user.username:
            if User.objects.filter(username=new_username).exists():
                messages.error(request, "Username นี้มีคนใช้แล้ว")
            else:
                student.user.username = new_username
                student.user.save()

        messages.success(request, "บันทึกข้อมูลเรียบร้อย")
        return redirect('teacher_student_list')

    return render(request, 'management/teacher_student_edit.html', {'student': student})

@login_required
def teacher_student_remove(request, student_id):
    """นำนักเรียนออกจากความดูแลของครู (ไม่ได้ลบ User ทิ้ง แค่เอาออกจากรายชื่อห้องเรียน)"""
    student = get_object_or_404(StudentProfile, id=student_id)
    
    # ลบ Many-to-Many Relationship ระหว่างครูและนักเรียน
    student.teachers.remove(request.user)
    
    messages.success(request, f"นำนักเรียน {student.user.username} ออกจากรายชื่อแล้ว")
    return redirect('teacher_student_list')

@login_required
def teacher_student_bulk_remove(request):
    """นำนักเรียนหลายคนออกจากความดูแลของครูพร้อมกัน (Bulk Remove)"""
    if request.method == "POST":
        student_ids = request.POST.getlist('student_ids')
        if student_ids:
            students = StudentProfile.objects.filter(id__in=student_ids)
            for student in students:
                student.teachers.remove(request.user)
                
            messages.success(request, f"นำนักเรียนออก {len(student_ids)} คนเรียบร้อยแล้ว")
        else:
            messages.warning(request, "ไม่ได้เลือกนักเรียน")
            
    return redirect('teacher_student_list')

# ==========================================
# ส่วนการนำเข้าข้อมูลนักเรียน (CSV Import)
# ==========================================

@login_required
def student_import_csv_view(request):
    """หน้าสำหรับนำเข้าข้อมูลนักเรียนและคะแนนพฤติกรรมผ่านไฟล์ CSV"""
    user_profile = get_role_for_user(request.user)
    
    if request.method == "POST":
        csv_file = request.FILES.get("file")
        if not csv_file:
            messages.error(request, "กรุณาเลือกไฟล์ CSV ก่อน")
            return redirect("teacher_student_import")

        if not csv_file.name.endswith(".csv"):
            messages.error(request, "รองรับเฉพาะไฟล์ .csv เท่านั้น")
            return redirect("teacher_student_import")

        try:
            # ใช้ utf-8-sig เพื่อรองรับไฟล์ CSV ที่เซฟจาก Excel (ป้องกันปัญหาภาษาไทยและ BOM)
            data = io.TextIOWrapper(csv_file.file, encoding="utf-8-sig")
            reader = csv.DictReader(data)
            
            if reader.fieldnames:
                reader.fieldnames = [name.strip() for name in reader.fieldnames]
                
        except Exception as e:
            messages.error(request, f"อ่านไฟล์ไม่ได้: {e}")
            return redirect("teacher_student_import")

        created_count = 0
        updated_count = 0
        error_rows = []

        # --- Helper Functions สำหรับจัดการ Data Types ---
        def parse_date(date_str):
            if not date_str: return timezone.now().date()
            date_str = date_str.strip()
            # รองรับรูปแบบวันที่หลายแบบ
            for fmt in ('%m/%d/%Y', '%d/%m/%Y', '%Y-%m-%d'):
                try: return datetime.strptime(date_str, fmt).date()
                except ValueError: continue
            return timezone.now().date()

        def clean_int(val): return int(val) if val and str(val).strip().isdigit() else 0
        def clean_float(val):
            try: return float(val) if val else 0.0
            except ValueError: return 0.0

        print("--- START IMPORT ---") 
        
        # วนลูปอ่านข้อมูลทีละแถว
        for index, row in enumerate(reader, start=1):
            username = row.get("username", "").strip()

            if not username:
                continue

            try:
                # --- 1. จัดการข้อมูล User (ชื่อ, นามสกุล, เมล) ---
                user_obj, created_user = User.objects.get_or_create(username=username)
                
                user_obj.first_name = row.get("first_name", "").strip()
                user_obj.last_name = row.get("last_name", "").strip()
                user_obj.email = row.get("email", "").strip()

                # ตั้งรหัสผ่านเริ่มต้นหากเพิ่งสร้าง User ใหม่
                if not user_obj.password or created_user:
                    user_obj.set_password("123456") 
                
                user_obj.save()

                # --- 2. จัดการ StudentProfile (รหัสนักเรียน, ชั้นเรียน) ---
                s, created_profile = StudentProfile.objects.update_or_create(
                    user=user_obj,
                    defaults={
                        'student_id': row.get("student_id", "").strip(),
                        'class_name': row.get("class_name", "ไม่ระบุ").strip()
                    }
                )

                # ผูกนักเรียนเข้ากับครูผู้นำเข้าข้อมูล
                s.teachers.add(request.user) 

                # --- 3. บันทึกพฤติกรรม (BehaviorRecord) ---
                r_date = parse_date(row.get("record_date"))
                
                obj, created = BehaviorRecord.objects.update_or_create(
                    student=s,
                    record_date=r_date,
                    teacher=request.user,
                    defaults={
                        'attendance_score': clean_int(row.get("attendance_score")),
                        'homework_done': str(row.get("homework_done", "0")).strip().lower() in ['1', 'true', 'yes'],
                        'quiz_score': clean_float(row.get("quiz_score")),
                        'activity_score': clean_int(row.get("activity_score")),
                    }
                )
                
                if created: created_count += 1
                else: updated_count += 1

            except Exception as e:
                print(f"Error Row {index}: {e}") 
                error_rows.append(f"แถว {index} ({username}): {e}")

        messages.success(request, f"นำเข้าสำเร็จ: เพิ่มพฤติกรรมใหม่ {created_count}, อัปเดต {updated_count}")
        if error_rows:
            messages.warning(request, f"พบข้อผิดพลาดบางแถว: {error_rows[:3]}")

        return redirect("teacher_student_import")
    
    return render(request, "management/teacher_student_import.html", {"user_profile": user_profile})

# ==========================================
# ส่วนฟังก์ชันประเมินความเสี่ยง (Risk Assessment)
# ==========================================

def risk_students():
    """
    ฟังก์ชันวิเคราะห์กลุ่มนักเรียนที่มีความเสี่ยง:
    ประเมินจากคะแนนเฉลี่ยรวม 4 ด้าน ถ้าน้อยกว่า 60 ถือว่ามีความเสี่ยง
    """
    risky = []
    # หมายเหตุ: โค้ดต้นฉบับดึงมาประมวลผลทั้งหมด ซึ่งถ้าข้อมูลเยอะอาจทำให้ช้า 
    # (แนะนำให้เปลี่ยนเป็นการทำ Aggregation ในระดับ Database แทนในอนาคต)
    records = BehaviorRecord.objects.all().order_by("student", "-created_at")

    for r in records:
        # หมายเหตุ: homework_score และ participation_score ในสมการนี้ 
        # อาจจะต้องเช็คในโมเดลว่ามีฟิลด์นี้หรือไม่ เพราะด้านบนใช้ homework_done เป็น boolean
        avg = (r.attendance_score + r.homework_score + r.quiz_score + r.participation_score) / 4
        if avg < 60:
            risky.append(r.student)

    # แปลงเป็น Set เพื่อลบรายชื่อนักเรียนที่ซ้ำกันออก
    return set(risky)