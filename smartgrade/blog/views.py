import csv
import io
from urllib import request
from django.views.decorators.http import require_POST
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from .forms import RegisterForm, StudentProfileForm, TeacherProfileForm, BehaviorForm, FeedbackForm, PrivateNoteForm, ContactForm
from .models import StudentProfile, BehaviorRecord, UserProfile, StudentProfile, StudentFeedback, PrivateNote, UrgentContact, TeacherNote, StudentScore
from django.db.models import Avg, Count, Q
from django.contrib import messages
from .utils import auto_feedback, analyze_grade_trend
from django.utils import timezone
from collections import defaultdict
from datetime import datetime

def get_role_for_user(user):
    """
    ดึง UserProfile ถ้าไม่มีให้สร้างใหม่
    และช่วยแก้ Role ให้ถูกต้องตามสถานะ Staff
    """
    # กำหนดค่าเริ่มต้น: ถ้าเป็น Staff ให้เป็น 'teacher' ถ้าไม่ใช่ให้เป็น 'student'
    default_role = 'teacher' if user.is_staff else 'student'
    
    user_profile, created = UserProfile.objects.get_or_create(
        user=user,
        defaults={"role": default_role} 
    )
    
    # ✅ ระบบ Auto-Fix: 
    # ถ้าในระบบ Django เขาเป็น Staff (ครู) แต่ใน Profile ดันบันทึกผิดว่าเป็น 'student'
    # ให้แก้กลับเป็น 'teacher' ทันที
    if user.is_staff and user_profile.role == 'student':
        user_profile.role = 'teacher'
        user_profile.save()
        
    return user_profile

def classroom_mode(request):
    # ดึงห้องเรียนทั้งหมดมาทำ Filter หรือดึงมาทั้งหมด
    students = StudentProfile.objects.all().order_by('class_name', 'user__username')
    return render(request, 'management/classroom_mode.html', {'students': students})

def quick_behavior_log(request, student_id, behavior_type):
    student = get_object_or_404(StudentProfile, id=student_id)
    
    # สร้างหรืออัปเดต Record ของ "วันนี้"
    record, created = BehaviorRecord.objects.get_or_create(
        student=student,
        record_date=timezone.now().date(),
        defaults={
            'attendance_score': 10, 'homework_done': False, 
            'quiz_score': 0, 'activity_score': 10
        }
    )

    # Logic: แปลงปุ่มกด -> เป็นคะแนน
    if behavior_type == 'sleep':
        record.activity_score = 5  # ตัดคะแนนกิจกรรม
        messages.warning(request, f"บันทึก: {student.user.username} หลับในห้อง (-คะแนนกิจกรรม)")
    
    elif behavior_type == 'active':
        record.activity_score = 20 # คะแนนเต็ม
        messages.success(request, f"บันทึก: {student.user.username} มีส่วนร่วมยอดเยี่ยม (+คะแนนกิจกรรม)")
        
    elif behavior_type == 'late':
        record.attendance_score = 5 # มาสาย
        messages.warning(request, f"บันทึก: {student.user.username} มาสาย (-คะแนนเข้าเรียน)")
        
    elif behavior_type == 'phone':
        record.activity_score = 0   # เล่นมือถือ
        messages.error(request, f"บันทึก: {student.user.username} เล่นโทรศัพท์ (คะแนนกิจกรรมเป็น 0)")

    record.save() # บันทึก
    
    return redirect('classroom_mode') # กลับไปหน้าเดิม

@login_required
def profile_detail(request):
    """
    หน้าโปรไฟล์: แสดงข้อมูลอย่างเดียว (ดึงจาก UserProfile ที่เป็นตารางกลาง)
    """
    
    # 1. ใช้ try-except ตามรูปแบบที่คุณต้องการ
    try:
        user_profile = UserProfile.objects.get(user=request.user)
    except UserProfile.DoesNotExist:
        user_profile = None

    # 2. ส่ง object ไปให้ HTML
    context = {
        "user_profile": user_profile,
        # ต้องเช็คก่อนว่า user_profile มีค่าไหม กัน Error กรณีเป็น None
        "role": user_profile.role if user_profile else None, 
    }

    return render(request, "management/profile_detail.html", context)


@login_required
def profile_edit(request):
    user = request.user
    
    # 1. ดึง UserProfile ของผู้ใช้นี้มา
    user_profile, created = UserProfile.objects.get_or_create(user=user)
    role = user_profile.role

    # 2. เลือกฟอร์มตามบทบาท
    if role == 'teacher':
        FormClass = TeacherProfileForm
    else:
        FormClass = StudentProfileForm

    if request.method == 'POST':
        form = FormClass(request.POST, request.FILES)
        
        if form.is_valid():
            # --- ส่วนที่ 1: บันทึกข้อมูลเข้าตาราง User ---
            user.first_name = form.cleaned_data.get('first_name', '')
            user.last_name = form.cleaned_data.get('last_name', '')
            user.save()

            # --- ส่วนที่ 2: บันทึกข้อมูลเข้าตาราง UserProfile ---
            user_profile.nickname = form.cleaned_data.get('nickname', '')
            user_profile.bio = form.cleaned_data.get('bio', '')
            user_profile.phone = form.cleaned_data.get('phone', '')
            
            # รูปภาพ
            if form.cleaned_data.get('profile_image'):
                user_profile.profile_image = form.cleaned_data.get('profile_image')

            # ข้อมูลเฉพาะบทบาท
            if role == 'teacher':
                user_profile.department = form.cleaned_data.get('department', '')
                user_profile.position = form.cleaned_data.get('position', '')
                user_profile.line_id = form.cleaned_data.get('line_id', '')
            elif role == 'student':
                user_profile.class_name = form.cleaned_data.get('class_name', '')
                # ✅ เพิ่มบรรทัดนี้ (บันทึก Line ID ของนักเรียน)
                user_profile.line_id = form.cleaned_data.get('line_id', '')

            # ✅ สั่งบันทึกลงฐานข้อมูล
            user_profile.save()

            messages.success(request, 'บันทึกข้อมูลเรียบร้อยแล้ว')
            return redirect('profile') # หรือชื่อ url ที่คุณตั้งไว้
    else:
        # --- ส่วนที่ 3: เตรียมข้อมูลเดิมมาแสดงในฟอร์ม ---
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
            # ✅ เพิ่มบรรทัดนี้ (ดึง Line ID เก่าของนักเรียนมาแสดง)
            initial_data['line_id'] = user_profile.line_id

        form = FormClass(initial=initial_data)

    return render(request, 'management/profile_edit.html', {
        'form': form,
        'user_profile': user_profile,
        'role': role
    })
    
def register_view(request):
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
    logout(request)
    return redirect('login')

def evaluate_status(behavior: BehaviorRecord | None):
    if behavior is None:
        return "ยังไม่มีข้อมูล", "gray", "ยังไม่มีข้อมูลพฤติกรรม"

    # สมมติ fields ใน BehaviorRecord
    total = (
        (behavior.attendance_score or 0) +
        (behavior.quiz_score or 0) +
        (behavior.activity_score or 0)
    )
    # homework_done: True/False
    if total >= 80 and behavior.homework_done:
        return "ปลอดภัย", "green", "มีแนวโน้มผ่าน"
    elif total >= 60:
        return "เริ่มมีความเสี่ยง", "yellow", "เสี่ยงเล็กน้อย"
    else:
        return "มีความเสี่ยงสูง", "red", "ควรได้รับความช่วยเหลือ"

@login_required
def dashboard(request):
    """
    ใช้ใน redirect หลัง login:
    - ถ้าเป็น staff -> ส่งไป teacher_dashboard
    - ถ้าไม่ใช่ -> ส่งไป student_dashboard
    """
    user = request.user
    user_profile = get_role_for_user(user)
    
    if user_profile.role == "teacher":
        return redirect("teacher_dashboard")
    else:
        return redirect("student_dashboard")

# views.py

@login_required
def teacher_dashboard(request):
    if not request.user.is_staff:
        return redirect('student_dashboard')

    all_students_raw = StudentProfile.objects.filter(teachers=request.user).select_related('user').order_by('class_name')
    
    # ... (ส่วนจัดการ Search/Filter เหมือนเดิม) ...
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
    widget_list = [] # สำหรับกลุ่มเสี่ยง 5 คน
    all_classes = all_students_raw.values_list('class_name', flat=True).distinct().order_by('class_name')
    user_profile = get_role_for_user(request.user)
    
    for s in all_students_raw:
        latest = s.behaviors.filter(teacher=request.user).order_by('-record_date', '-id').first()
        
        stat_att = 0
        stat_score = 0
        risk_status = "none"
        risk_label = "ไม่มีข้อมูล"
        risk_class = "bg-gray-100 text-gray-400"

        if latest:
            stat_att = latest.attendance_score
            # ✅ ปรับเกณฑ์: แดงต่ำกว่า 50, เหลืองต่ำกว่า 70 (หรือตามใจคุณ)
            if stat_att < 50:
                risk_status = "critical"
                risk_label = "เสี่ยงสูง"
                risk_class = "bg-red-100 text-red-700"
            elif stat_att < 70:
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
        
        # ✅ แก้ไขจำนวนคน: ให้ Widget โชว์เฉพาะคนที่เป็น 'critical' (แดง) เท่านั้น
        # ถ้าคุณใส่ 'warning' เข้าไปด้วย เลขมันจะเยอะเกิน 5 คนครับ
        if risk_status == 'critical': 
            widget_list.append(s_data) # ย่อหน้าตรงนี้คือจุดที่เคย Error ครับ

        if s.id in filtered_ids:
            table_list.append(s_data)

    # กรอง ID ซ้ำ (กันเหนียว)
    unique_widget = list({v['info'].id: v for v in widget_list}.values())

    return render(request, 'management/teacher_dashboard.html', {
        "students": table_list,
        "risk_list": unique_widget, # จะเหลือแค่คนเสี่ยงจริงๆ
        "total_students": all_students_raw.count(),
        "risk_count": len(unique_widget),
        "search_query": search_query,
        "class_filter": class_filter,
        "all_classes": all_classes,
        "user_profile": user_profile,
    })

@login_required
def teacher_student_list(request):
    # 1. ดึงนักเรียน
    students = StudentProfile.objects.filter(teachers=request.user).select_related('user').order_by('class_name')
    user_profile = get_role_for_user(request.user)
    
    # 2. Filter (คงเดิม)
    search_query = request.GET.get('q')
    if search_query:
        students = students.filter(
            Q(user__username__icontains=search_query) | 
            Q(user__first_name__icontains=search_query)
        )
    class_filter = request.GET.get('class_name')
    if class_filter:
        students = students.filter(class_name=class_filter)
        
    all_classes = StudentProfile.objects.filter(teachers=request.user).values_list('class_name', flat=True).distinct().order_by('class_name')

    # ==========================================
    # ✅ Logic ใหม่: ดูคะแนน "ครั้งล่าสุด" เท่านั้น
    # ==========================================
    final_list = []
    for s in students:
        # ดึงข้อมูลเรียงจาก วันที่ล่าสุด มาก่อน (.first())
        latest_record = s.behaviors.filter(teacher=request.user).order_by('-record_date').first()
        
        # ตั้งค่า Default
        s.debug_score = 0
        s.custom_status = "unknown"
        s.last_date = "-"

        if latest_record:
            # ใช้คะแนนล่าสุด (ไม่ใช้ Avg แล้ว)
            score = latest_record.attendance_score
            s.debug_score = score
            s.last_date = latest_record.record_date
            
            # ตัดเกรดจากคะแนนล่าสุด
            if score < 50:
                s.custom_status = "critical"  # แดง (ถ้าได้ 34 จะเข้าอันนี้แน่นอน)
            elif score < 60:
                s.custom_status = "warning"   # เหลือง
            else:
                s.custom_status = "normal"    # เขียว
            
        final_list.append(s)

    return render(request, 'management/teacher_student_list.html', {
        'students': final_list, 
        'all_classes': all_classes,
        'search_query': search_query,
        'class_filter': class_filter,
        'user_profile': user_profile,
    })

# --- 2. หน้า Detail + History + Add Behavior ---
@login_required
def teacher_student_detail(request, student_id):
    student = get_object_or_404(StudentProfile, id=student_id)
    
    # ดึงข้อมูลเฉพาะของครูคนนี้ (เพื่อแสดงผลในตาราง)
    behaviors = student.behaviors.filter(teacher=request.user).order_by('-record_date')
    records = BehaviorRecord.objects.filter(student=student, teacher=request.user).order_by('-record_date')
    feedbacks = student.feedbacks.filter(teacher=request.user).order_by('-created_at')
    notes = PrivateNote.objects.filter(student=student, teacher=request.user).order_by('-created_at')
    contacts = student.contact_logs.filter(teacher=request.user).order_by('-created_at')

    # เตรียม Form
    behavior_form = BehaviorForm()
    feedback_form = FeedbackForm()
    note_form = PrivateNoteForm()
    contact_form = ContactForm()
    
    # ✅ 1. สร้างแผนที่แปลง Code -> ชื่อไทย (ต้องตรงกับ models.py)
    dept_map = {
        'math': 'คณิตศาสตร์', 
        'sci': 'วิทยาศาสตร์', 
        'eng': 'ภาษาต่างประเทศ',
        'thai': 'ภาษาไทย', 
        'soc': 'สังคมศึกษา', 
        'art': 'ศิลปะ',
        'pe': 'สุขศึกษาและพลศึกษา', 
        'work': 'การงานอาชีพ',
        'comp': 'คอมพิวเตอร์',
        'guidance': 'แนะแนว',
    }

    user_profile = get_role_for_user(request.user)
    
    if request.method == "POST":
        action = request.POST.get('action')

        if action == 'add_behavior':
            form = BehaviorForm(request.POST)
            if form.is_valid():
                obj = form.save(commit=False)
                obj.student = student
                obj.teacher = request.user 
                
                # ✅✅✅ จุดแก้ไขสำคัญ: ดึงวิชาจาก Profile ครูมาใส่ ✅✅✅
                user_profile = get_role_for_user(request.user) # ดึง Profile ครู
                
                if user_profile and user_profile.department:
                    dept_code = user_profile.department
                    # แปลง code (เช่น 'math') เป็นชื่อไทย ('คณิตศาสตร์')
                    # ถ้าไม่มีใน map ให้ใช้ชื่อเดิมไปเลย
                    obj.subject = dept_map.get(dept_code, dept_code)
                else:
                    # ถ้าครูยังไม่ตั้งค่า Profile ให้เป็นวิชาทั่วไป + ชื่อครู (กันเหนียว)
                    obj.subject = f"วิชาทั่วไป ({request.user.first_name})"

                obj.save()
                messages.success(request, f"บันทึกคะแนนวิชา {obj.subject} เรียบร้อย")
                
        elif action == 'delete_behavior':
            record_id = request.POST.get('record_id')
            try:
                # ลบเฉพาะรายการที่เป็นของนักเรียนคนนี้ และครูคนนี้เป็นคนลบ (เพื่อความปลอดภัย)
                record_to_delete = BehaviorRecord.objects.get(id=record_id, student=student, teacher=request.user)
                record_to_delete.delete()
                messages.success(request, "ลบรายการเรียบร้อยแล้ว")
            except BehaviorRecord.DoesNotExist:
                messages.error(request, "ไม่สามารถลบรายการนี้ได้")
            
            return redirect('teacher_student_detail', student_id=student.id)
        
        elif action == 'add_feedback':
            form = FeedbackForm(request.POST)
            if form.is_valid():
                obj = form.save(commit=False)
                obj.student = student
                obj.teacher = request.user
                
                # ดึงวิชาใส่ Feedback ด้วย
                user_profile = get_role_for_user(request.user)
                if user_profile and user_profile.department:
                    dept_code = user_profile.department
                    obj.subject = dept_map.get(dept_code, "General")
                else:
                    obj.subject = "General"
                
                obj.save()
                messages.success(request, "ส่ง Feedback เรียบร้อยแล้ว")

        elif action == 'add_note':
            form = PrivateNoteForm(request.POST)
            if form.is_valid():
                obj = form.save(commit=False)
                obj.student = student
                obj.teacher = request.user
                obj.save()
                messages.success(request, "บันทึกโน้ตส่วนตัวแล้ว")

        elif action == 'add_contact':
            form = ContactForm(request.POST)
            if form.is_valid():
                obj = form.save(commit=False)
                obj.student = student
                obj.teacher = request.user
                obj.save()
                messages.success(request, "บันทึกการติดต่อด่วนแล้ว")
        
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

@login_required
def teacher_add_student_manual(request):
    user_profile = get_role_for_user(request.user)
    
    if request.method == 'POST':
        student_id = request.POST.get('student_id', '').strip()
        
        if not student_id:
            messages.error(request, "กรุณากรอกรหัสนักเรียน")
            return redirect('teacher_add_student_manual')

        try:
            # 1. ค้นหานักเรียน
            student = StudentProfile.objects.select_related('user').get(user__username=student_id)
            
            # 2. เช็คว่ามีเราอยู่ในรายชื่อครูของเขาหรือยัง?
            # (สังเกต: ใช้ .filter(...).exists() กับ ManyToMany)
            if student.teachers.filter(id=request.user.id).exists():
                messages.warning(request, f"นักเรียน {student.user.get_full_name()} ({student_id}) อยู่ในห้องเรียนของคุณอยู่แล้ว")
            else:
                # ✅✅✅ จุดแก้ไขสำคัญ: ใช้ .add() เพื่อเพิ่มเราเข้าไป (ไม่ลบครูคนเก่า)
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

# --- 3. ลบนักเรียน (Delete) ---
def teacher_student_delete(request, student_id):
    student = get_object_or_404(StudentProfile, id=student_id)
    # ลบ User หลัก -> Profile และ Behavior จะหายไปเอง (Cascade)
    user = student.user
    user.delete()
    messages.success(request, f"ลบนักเรียน {user.username} เรียบร้อยแล้ว")
    return redirect('teacher_student_list')

# --- 4. ลบประวัติพฤติกรรมบางรายการ ---
def behavior_delete(request, behavior_id):
    behavior = get_object_or_404(BehaviorRecord, id=behavior_id)
    student_id = behavior.student.id
    behavior.delete()
    messages.success(request, "ลบรายการพฤติกรรมเรียบร้อย")
    return redirect('teacher_student_detail', student_id=student_id)

@login_required
def student_dashboard(request):
    if request.user.is_staff:
        return redirect('teacher_dashboard')

    user_profile = get_role_for_user(request.user)

    try:
        student = StudentProfile.objects.get(user=request.user)
        # 1. ดึงข้อมูล
        behaviors = BehaviorRecord.objects.filter(student=student).select_related('teacher', 'teacher__profile').order_by('-record_date')[:10]
        all_records_for_graph = BehaviorRecord.objects.filter(student=student).select_related('teacher', 'teacher__profile')
        
        # Config Map (คงเดิม)
        dept_map = {
            'math': 'คณิตศาสตร์', 'sci': 'วิทยาศาสตร์', 'eng': 'ภาษาต่างประเทศ',
            'thai': 'ภาษาไทย', 'soc': 'สังคมศึกษา', 'art': 'ศิลปะ',
            'pe': 'สุขศึกษาและพลศึกษา', 'work': 'การงานอาชีพ'
        }
        manual_teacher_map = {'Teacher01': 'วิทยาศาสตร์', 'Teacher02': 'ภาษาต่างประเทศ'}

        def get_subject_name(record):
            if not record.teacher: return 'ประวัติเก่า (ไม่ระบุครู)'
            if record.teacher.username in manual_teacher_map:
                return manual_teacher_map[record.teacher.username]
            if hasattr(record.teacher, 'profile') and record.teacher.profile.department:
                code = record.teacher.profile.department
                return dept_map.get(code, code)
            db_sub = getattr(record, 'subject', '')
            if db_sub and db_sub not in ['วิชาทั่วไป', 'General', 'general', '', '-']:
                return db_sub
            return 'วิชาทั่วไป'

        # จัดกลุ่มวิชา
        grouped_subjects = {}
        for record in all_records_for_graph:
            subj_name = get_subject_name(record)
            if subj_name not in grouped_subjects:
                grouped_subjects[subj_name] = []
            grouped_subjects[subj_name].append(record)

        subject_data = []
        chart_labels, chart_scores, chart_colors = [], [], []

        # --- ส่วนที่เคยมีปัญหาเรื่องย่อหน้า (Indentation) ---
        for name, records in grouped_subjects.items():
            if name == 'ประวัติเก่า (ไม่ระบุครู)': 
                continue

            count = len(records)
            if count == 0: continue

            # คำนวณคะแนนย่อย
            total_quiz = sum(r.quiz_score for r in records)
            s_quiz = min(100, (total_quiz / (count * 20)) * 100) 
            
            total_att = sum(r.attendance_score for r in records)
            max_val_att = max((r.attendance_score for r in records), default=0)
            base_score_att = 10 if max_val_att > 2 else 2
            s_att = min(100, (total_att / (count * base_score_att)) * 100)
            
            hw_done_count = sum(1 for r in records if r.homework_done)
            s_hw = (hw_done_count / count) * 100

            # คำนวณ Health Score
            raw_health = (s_att * 0.4) + (s_hw * 0.3) + (s_quiz * 0.3)
            health_score = min(100, int(raw_health))

            # ✅ ปรับเกณฑ์สถานะ 70 / 50 ให้ตรงกัน
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

        subject_data.sort(key=lambda x: x['score'])
        manual_feedbacks = StudentFeedback.objects.filter(student=student).order_by('-created_at')
        urgent_messages = UrgentContact.objects.filter(student=student, target='student').select_related('teacher').order_by('-created_at')

        # ภาพรวม Dashboard
        latest = BehaviorRecord.objects.filter(student=student).order_by('-record_date').first()
        status, advice = "ไม่มีข้อมูล", "-"
        if latest:
            avg = (latest.attendance_score + latest.quiz_score + latest.activity_score) / 3
            if avg >= 70: # ปรับให้ตรงกัน
                status, advice = "ดีเยี่ยม", "รักษามาตรฐานนี้ต่อไป"
            elif avg >= 50:
                status, advice = "ปานกลาง", "ควรเพิ่มความสม่ำเสมอ"
            else:
                status, advice = "เสี่ยง", "ควรติดต่อครูผู้สอน"

    except StudentProfile.DoesNotExist:
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

@login_required
def student_report(request, student_id):
    # 1. Fetch Student Data
    student = get_object_or_404(StudentProfile, id=student_id)
    
    # 2. Handle POST requests (คงเดิม)
    if request.method == "POST":
        action = request.POST.get('action')
        if action == 'add_note':
            form = PrivateNoteForm(request.POST)
            if form.is_valid():
                obj = form.save(commit=False)
                obj.student = student
                obj.teacher = request.user
                obj.save()
                messages.success(request, "บันทึกโน้ตเรียบร้อย")
                return redirect('student_report', student_id=student.id)
        elif action == 'add_contact':
            form = ContactForm(request.POST)
            if form.is_valid():
                obj = form.save(commit=False)
                obj.student = student
                obj.teacher = request.user
                obj.save()
                messages.success(request, "บันทึกการติดต่อเรียบร้อย")
                return redirect('student_report', student_id=student.id)

    # 3. Prepare Display Data
    notes = PrivateNote.objects.filter(student=student, teacher=request.user).order_by('-created_at')
    contacts = student.contact_logs.all().order_by('-created_at')
    records = BehaviorRecord.objects.filter(student=student, teacher=request.user).order_by('-record_date', '-id')

    # ========================================================
    # ✅ 4. Logic วิเคราะห์พฤติกรรมอัตโนมัติ (AI Analysis)
    # ========================================================
    latest_rec = BehaviorRecord.objects.filter(student=student, teacher=request.user).order_by('-record_date', '-id').first()  # ดึงรายการล่าสุดตัวแรก
    ai_status = "unknown"
    ai_message = "ไม่พบข้อมูลคะแนนล่าสุดสำหรับการวิเคราะห์"

    if latest_rec:
        score = latest_rec.attendance_score
        # 🚩 ปรับ Logic ความเสี่ยงให้ตรงกับที่ต้องการ (เช่น < 50 คือเสี่ยงสูง)
        if score < 50:
            ai_status = "critical"
            ai_message = f"นักเรียนมีพฤติกรรมเสี่ยงสูง (คะแนนล่าสุด {score}%) พบว่ามีการขาดเรียนหรือขาดส่งงานในระดับวิกฤต ครูควรติดต่อผู้ปกครองทันที"
        elif score < 80:
            ai_status = "warning"
            ai_message = f"นักเรียนอยู่ในกลุ่มเฝ้าระวัง (คะแนนล่าสุด {score}%) เริ่มมีแนวโน้มพฤติกรรมถดถอย ควรสอบถามปัญหาเบื้องต้นหรือตักเตือน"
        else:
            ai_status = "normal"
            ai_message = f"นักเรียนมีพฤติกรรมปกติ (คะแนนล่าสุด {score}%) รักษามาตรฐานการเข้าเรียนและส่งงานได้ดีเยี่ยม"

    # ========================================================
    # 5. Prepare Graph Data (Graph Data) - Sorted Old -> New
    history_records = BehaviorRecord.objects.filter(student=student, teacher=request.user).order_by('record_date')
    
    report_dates = []
    report_attendance = []
    report_quiz = []
    report_activity = []
    daily_data = defaultdict(lambda: {'att': [], 'quiz': [], 'act': []})
    
    for r in history_records:
        date_str = r.record_date.strftime('%d/%m')
        att_score = r.attendance_score if r.attendance_score else 0
        
        # ปรับสูตรคำนวณกราฟให้ตรงกับคะแนนจริง (%)
        daily_data[date_str]['att'].append(att_score)
        daily_data[date_str]['quiz'].append(r.quiz_score)
        daily_data[date_str]['act'].append(r.activity_score)
        
    for date, values in daily_data.items():
        report_dates.append(date)
        report_attendance.append(round(sum(values['att']) / len(values['att']), 1))
        report_quiz.append(round(sum(values['quiz']) / len(values['quiz']), 1))
        report_activity.append(round(sum(values['act']) / len(values['act']), 1))

    csv_scores = StudentScore.objects.filter(student=student).order_by('subject_code')
    
    return render(request, 'management/student_report.html', {
        'student': student,
        'records': records,
        'ai_status': ai_status,     # ✅ ส่งสถานะไปเปลี่ยนสีกล่อง
        'ai_message': ai_message,   # ✅ ส่งข้อความวิเคราะห์ไปโชว์
        'latest_rec': latest_rec,   # ✅ ส่งข้อมูลล่าสุดไปใช้อ้างอิง
        'notes': notes,
        'contacts': contacts,
        'csv_scores': csv_scores,
        'report_dates': report_dates,
        'report_attendance': report_attendance,
        'report_quiz': report_quiz,
        'report_activity': report_activity,
    })

@login_required
def student_subject_detail(request, subject_name):
    if request.user.is_staff:
        return redirect('teacher_dashboard')

    try:
        student = StudentProfile.objects.get(user=request.user)
        
        # 1. ดึงข้อมูล
        all_records = BehaviorRecord.objects.filter(student=student).select_related('teacher', 'teacher__profile').order_by('-record_date')
        
        filtered_records = []
        subject_teacher = None
        
        # Config Map
        dept_map = {
            'math': 'คณิตศาสตร์', 'sci': 'วิทยาศาสตร์', 'eng': 'ภาษาต่างประเทศ',
            'thai': 'ภาษาไทย', 'soc': 'สังคมศึกษา', 'art': 'ศิลปะ',
            'pe': 'สุขศึกษาและพลศึกษา', 'work': 'การงานอาชีพ'
        }
        manual_teacher_map = {
            'Teacher01': 'วิทยาศาสตร์',    
            'Teacher02': 'ภาษาต่างประเทศ',
        }

        # Helper Function
        def get_subj(r):
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

        # 2. คัดกรอง
        for record in all_records:
            if get_subj(record) == subject_name:
                filtered_records.append(record)
                if not subject_teacher and record.teacher:
                    subject_teacher = record.teacher

        # 3. คำนวณสถิติ
        count = len(filtered_records)
        avg_score = 0
        attendance_rate = 0
        
        # ✅ เพิ่มตัวแปรนับจำนวนครั้ง
        present_count = 0
        late_count = 0
        absent_count = 0

        labels = []
        scores = []
        att_scores = []

        if count > 0:
            # Quiz
            total_quiz = sum(r.quiz_score for r in filtered_records)
            avg_score = total_quiz / count

            # Attendance (Original Logic - Percentage)
            total_att = sum(r.attendance_score for r in filtered_records)
            max_val = max((r.attendance_score for r in filtered_records), default=0)
            
            if max_val > 10:
                score_base = max_val 
            elif max_val > 2:
                score_base = 10      
            else:
                score_base = 2       
            
            max_possible = count * score_base
            attendance_rate = (total_att / max_possible) * 100 if max_possible > 0 else 0
            attendance_rate = min(100, attendance_rate)
            
            # ✅✅✅ Loop นับจำนวนครั้ง (เพิ่มใหม่) ✅✅✅
            for r in filtered_records:
                score = r.attendance_score
                # ปรับเกณฑ์ตรงนี้ได้ตามต้องการ (80-100=มาเรียน, 1-79=สาย, 0=ขาด)
                if score >= 80:
                    present_count += 1
                elif score > 0:
                    late_count += 1
                else:
                    absent_count += 1

            # กราฟ
            graph_data = filtered_records[:10][::-1]
            labels = [r.record_date.strftime('%d/%m') if r.record_date else '-' for r in graph_data]
            scores = [r.quiz_score for r in graph_data]
            att_scores = [r.attendance_score for r in graph_data]

    except StudentProfile.DoesNotExist:
        student = None
        filtered_records = []
        subject_teacher = None
        count = 0
        avg_score = 0
        attendance_rate = 0
        present_count = 0
        late_count = 0
        absent_count = 0
        labels, scores, att_scores = [], [], []

    return render(request, 'management/student_subject_detail.html', {
        'subject_name': subject_name,
        'teacher': subject_teacher,
        'records': filtered_records,
        'avg_score': avg_score,
        'attendance_rate': attendance_rate,
        # ✅ ส่งตัวแปรนับจำนวนไปหน้าเว็บ
        'present_count': present_count,
        'late_count': late_count,
        'absent_count': absent_count,
        'labels': labels,
        'scores': scores,
        'att_scores': att_scores,
    })
    
def teacher_student_edit(request, student_id):
    student = get_object_or_404(StudentProfile, id=student_id)
    
    if request.method == "POST":
        # แก้ไข Class Name
        student.class_name = request.POST.get('class_name')
        student.save()
        
        # ถ้าอยากแก้ Username หรือ Password ด้วย ต้องแก้ที่ตัว User
        new_username = request.POST.get('username')
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
    # เปลี่ยนชื่อฟังก์ชันจาก _delete เป็น _remove
    student = get_object_or_404(StudentProfile, id=student_id)
    
    # ✅ ใช้ .remove() เพื่อตัดความสัมพันธ์ โดยข้อมูลนักเรียนยังอยู่
    student.teachers.remove(request.user)
    
    messages.success(request, f"นำนักเรียน {student.user.username} ออกจากรายชื่อแล้ว")
    return redirect('teacher_student_list')

@login_required
def teacher_student_bulk_remove(request):
    if request.method == "POST":
        student_ids = request.POST.getlist('student_ids')
        if student_ids:
            students = StudentProfile.objects.filter(id__in=student_ids)
            for student in students:
                # ✅ วนลูปนำออกทีละคน (Unlink)
                student.teachers.remove(request.user)
                
            messages.success(request, f"นำนักเรียนออก {len(student_ids)} คนเรียบร้อยแล้ว")
        else:
            messages.warning(request, "ไม่ได้เลือกนักเรียน")
            
    return redirect('teacher_student_list')

@login_required
def student_import_csv_view(request):
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
            data = io.TextIOWrapper(csv_file.file, encoding="utf-8-sig")
            reader = csv.DictReader(data)
            
            # ลบช่องว่างหัวตาราง (กันพลาด)
            if reader.fieldnames:
                reader.fieldnames = [name.strip() for name in reader.fieldnames]
                
        except Exception as e:
            messages.error(request, f"อ่านไฟล์ไม่ได้: {e}")
            return redirect("teacher_student_import")

        created_count = 0
        updated_count = 0
        error_rows = []

        # ฟังก์ชันแปลงวันที่
        def parse_date(date_str):
            if not date_str: return timezone.now().date()
            date_str = date_str.strip()
            for fmt in ('%m/%d/%Y', '%d/%m/%Y', '%Y-%m-%d'):
                try: return datetime.strptime(date_str, fmt).date()
                except ValueError: continue
            return timezone.now().date()

        def clean_int(val): return int(val) if val and val.strip().isdigit() else 0
        def clean_float(val):
            try: return float(val) if val else 0.0
            except ValueError: return 0.0

        print("--- START IMPORT ---") # ดูใน Terminal
        
        for index, row in enumerate(reader, start=1):
            # 1. เช็คหัวตารางให้ชัวร์
            username = row.get("username", "").strip()
            
            # Debug: ถ้าหา username ไม่เจอ ให้ปริ้นท์บอก
            if not username:
                print(f"Row {index}: ข้าม (ไม่พบ username ในไฟล์ CSV)")
                # ลองเช็คว่า CSV ใช้ชื่ออื่นไหม?
                if index == 1: print(f"Headers ที่พบ: {reader.fieldnames}") 
                continue

            try:
                # ==================================================
                # ✅ แก้ไข Logic: สร้าง User ก่อน แล้วค่อยสร้าง Profile
                # ==================================================
                user_obj, _ = User.objects.get_or_create(username=username)
                
                # ถ้าอยากตั้งรหัสผ่าน Default ให้ทำตรงนี้ (Optional)
                if not user_obj.password:
                    user_obj.set_password("123456") 
                    user_obj.save()

                # หานักเรียนจาก User ที่ได้มา
                s, created = StudentProfile.objects.get_or_create(
                    user=user_obj, # ใส่เป็น Object
                    defaults={'class_name': row.get("class_name", "ไม่ระบุ").strip()}
                )
                
                # Link ครู
                s.teachers.add(request.user) 

                # 2. บันทึกคะแนน (เหมือนเดิม)
                r_date = parse_date(row.get("record_date"))
                
                obj, created = BehaviorRecord.objects.update_or_create(
                    student=s,
                    record_date=r_date,
                    teacher=request.user,
                    defaults={
                        'attendance_score': clean_int(row.get("attendance_score")),
                        'homework_done': str(row.get("homework_done", "0")).strip() in ['1', 'True', 'true'],
                        'quiz_score': clean_float(row.get("quiz_score")),
                        'activity_score': clean_int(row.get("activity_score")),
                    }
                )
                
                if created: created_count += 1
                else: updated_count += 1

            except Exception as e:
                print(f"Error Row {index}: {e}") # ปริ้นท์ error ลง Terminal
                error_rows.append(f"แถว {index} ({username}): {e}")

        messages.success(request, f"เสร็จสิ้น: เพิ่มใหม่ {created_count}, อัปเดต {updated_count}")
        if error_rows:
            messages.warning(request, f"มีข้อผิดพลาด: {error_rows[:3]}")

        return redirect("teacher_student_import")
    
    return render(request, "management/teacher_student_import.html", {"user_profile": user_profile})

def risk_students():
    risky = []
    records = BehaviorRecord.objects.all().order_by("student", "-created_at")

    for r in records:
        avg = (r.attendance_score + r.homework_score + r.quiz_score + r.participation_score) / 4
        if avg < 60:
            risky.append(r.student)

    return set(risky)