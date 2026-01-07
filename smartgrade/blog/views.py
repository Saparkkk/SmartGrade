import csv
import io
from django.views.decorators.http import require_POST
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from .forms import RegisterForm, StudentProfileForm, TeacherProfileForm, BehaviorForm, StudentForm, FeedbackForm, NoteForm, ContactForm
from .models import StudentProfile, BehaviorRecord, UserProfile, StudentProfile, StudentFeedback, TeacherNote, UrgentContact
from django.db.models import Sum, Q
from django.contrib import messages
from .utils import auto_feedback, analyze_grade_trend
from django.utils import timezone


def get_role_for_user(user):
    # ไม่ต้อง sync กับ is_staff แล้ว ให้ role ใน UserProfile เป็นตัวจริง
    user_profile, _ = UserProfile.objects.get_or_create(
        user=user,
        defaults={"role": "student"}  # ค่าเริ่มต้นเป็นนักเรียน
    )
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
    หน้าโปรไฟล์: แสดงข้อมูลอย่างเดียว (ไม่แก้ไข)
    """
    user = request.user
    user_profile = get_role_for_user(user)
    role = user_profile.role  # 'student' หรือ 'teacher'

    # เตรียมข้อมูลที่จะแสดง
    data = {
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "email": user.email,
        "role": role,
        "class_name": None,
        "profile_image": user_profile.profile_image,
    }
    
    if role == "student":
        student_profile, _ = StudentProfile.objects.get_or_create(user=user)
        data["class_name"] = student_profile.class_name

    return render(request, "management/profile_detail.html", data)


@login_required
def profile_edit(request):
    user = request.user
    user_profile = get_role_for_user(user)
    role = user_profile.role

    FormClass = StudentProfileForm if role == "student" else TeacherProfileForm

    if request.method == "POST":
        form = FormClass(request.POST, request.FILES)
        if form.is_valid():
            user.first_name = form.cleaned_data.get("first_name", "")
            user.last_name = form.cleaned_data.get("last_name", "")
            user.email = form.cleaned_data.get("email", "")
            user.save()

            # ✅ บันทึกรูปโปรไฟล์
            img = form.cleaned_data.get("profile_image")
            if img:
                user_profile.profile_image = img
                user_profile.save()

            if role == "student":
                student_profile, _ = StudentProfile.objects.get_or_create(user=user)
                student_profile.class_name = form.cleaned_data.get("class_name", "")
                student_profile.save()

            messages.success(request, "บันทึกโปรไฟล์เรียบร้อยแล้ว")
            return redirect("profile")
    else:
        initial = {
            "first_name": user.first_name,
            "last_name": user.last_name,
            "email": user.email,
        }
        if role == "student":
            student_profile, _ = StudentProfile.objects.get_or_create(user=user)
            initial["class_name"] = student_profile.class_name

        form = FormClass(initial=initial)

    return render(request, "management/profile_edit.html", {
        "form": form,
        "role": role,
        "user_profile": user_profile,
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

@login_required
def teacher_dashboard(request):
    # กันไม่ให้นักเรียนเข้าหน้านี้
    if not request.user.is_staff:
        return redirect('student_dashboard')

    students = StudentProfile.objects.select_related('user')

    risk_students = []
    for s in students:
        latest_behavior = (
            BehaviorRecord.objects
            .filter(student=s)
            .order_by('-record_date')
            .first()
        )
        status, color, _ = evaluate_status(latest_behavior)
        if color == "red":
            risk_students.append(s)
        elif color == "yellow":
            risk_students.append(s)

    context = {
        "students": students,
        "risk_students": risk_students,
    }
    return render(request, 'management/dashboard_teacher.html', context)

def teacher_student_list(request):
    students = StudentProfile.objects.select_related('user').all()

    # Search (ค้นหาจาก Username)
    search_query = request.GET.get('q')
    if search_query:
        students = students.filter(user__username__icontains=search_query)

    # Filter (กรองตามห้อง)
    class_filter = request.GET.get('class_name')
    if class_filter:
        students = students.filter(class_name=class_filter)

    # เตรียม list ของห้องเรียนเพื่อใส่ใน Dropdown Filter
    all_classes = StudentProfile.objects.values_list('class_name', flat=True).distinct().order_by('class_name')

    return render(request, 'management/teacher_student_list.html', {
        'students': students,
        'all_classes': all_classes,
        'search_query': search_query,
        'class_filter': class_filter
    })

# --- 2. หน้า Detail + History + Add Behavior ---
def teacher_student_detail(request, student_id):
    student = get_object_or_404(StudentProfile, id=student_id)
    behaviors = student.behaviors.all().order_by('-record_date')
    records = BehaviorRecord.objects.filter(student=student).order_by('-record_date')
    trend_alert = analyze_grade_trend(records)
    
    # เตรียม Form เริ่มต้น
    behavior_form = BehaviorForm()
    feedback_form = FeedbackForm()
    note_form = NoteForm()
    contact_form = ContactForm()

    if request.method == "POST":
        action = request.POST.get('action') # ดูว่ากดปุ่มไหนมา

        if action == 'add_behavior':
            form = BehaviorForm(request.POST)
            if form.is_valid():
                obj = form.save(commit=False)
                obj.student = student
                obj.save()
                messages.success(request, "บันทึกพฤติกรรมเรียบร้อย")
        
        elif action == 'add_feedback':
            form = FeedbackForm(request.POST)
            if form.is_valid():
                obj = form.save(commit=False)
                obj.student = student
                obj.teacher = request.user
                obj.save()
                messages.success(request, f"ส่ง Feedback ({obj.get_feedback_type_display()}) แล้ว")

        elif action == 'add_note':
            form = NoteForm(request.POST)
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

    # ดึงประวัติรายการอื่นๆ เพื่อแสดงผล
    feedbacks = student.feedbacks.all().order_by('-created_at')
    notes = student.private_notes.filter(teacher=request.user).order_by('-created_at')
    contacts = student.contact_logs.all().order_by('-created_at')

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
        'trend_alert': trend_alert,
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
    # กันไม่ให้ครูเข้าหน้านักเรียน
    if request.user.is_staff:
        return redirect('teacher_dashboard')

    user = request.user
    # 1. ใช้ตัวแปรชื่อ profile เหมือนเดิม
    profile, created = StudentProfile.objects.get_or_create(user=user)
    
    behaviors = profile.behaviors.order_by('-record_date')[:10]
    latest = behaviors.first() if behaviors else None
    
    status = "ไม่มีข้อมูล"
    advice = ""
    feedback_auto = ""

    if latest:
        # คำนวณเกรด/สถานะ (Logic เดิมของคุณ)
        avg = (latest.attendance_score + latest.quiz_score + latest.activity_score) / 3
        if avg >= 80 and latest.homework_done:
            status = "ดี"
            advice = "รักษาความสม่ำเสมอ"
        elif avg >= 60:
            status = "ปานกลาง"
            advice = "ควรปรับปรุงบางจุด"
        else:
            status = "เสี่ยง"
            advice = "ควรขอคำปรึกษาจากอาจารย์"
            
        # ดึง Feedback อัตโนมัติ (ถ้ามีฟังก์ชัน auto_feedback)
        # feedback_auto = auto_feedback(latest) 

    # 2. [จุดที่แก้] เปลี่ยนจาก student_profile เป็น profile ให้ตรงกับด้านบน
    manual_feedbacks = StudentFeedback.objects.filter(student=profile).order_by('-created_at')
    
    urgent_messages = UrgentContact.objects.filter(
        student=profile, 
        target='student'  # กรองเฉพาะที่ส่งถึงนักเรียน
    ).order_by('-created_at')

    # 3. [จุดที่แก้] รวมทุกอย่างไว้ใน context เดียว
    context = {
        'profile': profile,
        'user_profile': profile, # เผื่อใน HTML ใช้คำนี้
        'behaviors': behaviors,
        'status': status,
        'advice': advice,
        'feedback': feedback_auto, # สำหรับ {{ feedback }} ใน HTML
        
        # ส่งข้อมูลใหม่ไปหน้าเว็บ
        'manual_feedbacks': manual_feedbacks, 
        'urgent_messages': urgent_messages, 
    }

    # ส่ง context ก้อนเดียวไปที่ render
    return render(request, 'management/dashboard_student.html', context)

def student_report(request, student_id):
    student_profile = get_object_or_404(StudentProfile, user__username=student_id)
    records = BehaviorRecord.objects.filter(student=student_profile)

    feedback = None
    if records.exists():
        feedback = auto_feedback(records.last())

    return render(request, "management/student_report.html", {
        "student": student_profile,
        "records": records,
        "feedback": feedback
    })

def teacher_student_create(request):
    if request.method == "POST":
        # รับค่าจาก Form แบบบ้านๆ หรือจะใช้ Django Form ก็ได้
        username = request.POST.get('username')
        class_name = request.POST.get('class_name')
        password = request.POST.get('password') # ถ้าไม่กรอก อาจจะตั้ง default ได้

        # เช็คว่ามี User นี้หรือยัง
        if User.objects.filter(username=username).exists():
            messages.error(request, f"ชื่อผู้ใช้ {username} มีอยู่ในระบบแล้ว")
            return redirect('teacher_student_create')

        # สร้าง User
        user = User.objects.create_user(username=username, password=password)
        
        # สร้าง Profile
        StudentProfile.objects.create(user=user, class_name=class_name)
        
        messages.success(request, f"เพิ่มนักเรียน {username} สำเร็จ")
        return redirect('teacher_student_list')

    return render(request, 'management/teacher_student_create.html')

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

@require_POST # รับเฉพาะ POST request เท่านั้น
def teacher_student_bulk_delete(request):
    # รับค่า list ของ id ที่ติ๊กมา (ชื่อต้องตรงกับ name="student_ids" ใน HTML)
    student_ids = request.POST.getlist('student_ids')
    
    if student_ids:
        # ลบนักเรียนที่มี id อยู่ใน list
        # เปลี่ยน StudentProfile เป็น Model ของคุณ (เช่น Student)
        StudentProfile.objects.filter(id__in=student_ids).delete()
        messages.success(request, f"ลบนักเรียนจำนวน {len(student_ids)} คนเรียบร้อยแล้ว")
    else:
        messages.warning(request, "ไม่ได้เลือกนักเรียนที่ต้องการลบ")
        
    return redirect('teacher_student_list') # กลับไปหน้ารายชื่อ

def student_import_csv_view(request):
    if request.method == "POST":
        csv_file = request.FILES.get("file")
        if not csv_file:
            messages.error(request, "กรุณาเลือกไฟล์ CSV ก่อน")
            return redirect("teacher_student_import")

        if not csv_file.name.endswith(".csv"):
            messages.error(request, "รองรับเฉพาะไฟล์ .csv เท่านั้น")
            return redirect("teacher_student_import")

        try:
            # 1. แก้ encoding เป็น 'utf-8-sig' เพื่อรองรับไฟล์จาก Excel
            data = io.TextIOWrapper(csv_file.file, encoding="utf-8-sig")
            reader = csv.DictReader(data)
            
            # 2. Clean Header: ลบช่องว่างหัวตาราง (เผื่อพิมพ์เว้นวรรคมา เช่น "username ")
            if reader.fieldnames:
                reader.fieldnames = [name.strip() for name in reader.fieldnames]
                
        except Exception as e:
            messages.error(request, f"ไม่สามารถอ่านไฟล์ CSV ได้: {e}")
            return redirect("teacher_student_import")

        created_count = 0
        new_students_count = 0  # นับจำนวนนักเรียนใหม่ที่เพิ่งสร้าง
        error_rows = []

        for index, row in enumerate(reader, start=1):
            username = row.get("username", "").strip()
            class_name = row.get("class_name", "").strip()
            
            if not username:
                continue

            # --- เริ่มส่วนที่แก้: Logic การค้นหาหรือสร้างใหม่ ---
            s = None
            try:
                # 1. ลองหาก่อน
                s = StudentProfile.objects.select_related("user").get(
                    user__username=username
                )
                
                # ถ้าเจอ ก็แค่อัปเดต class_name (ถ้ามีค่าส่งมา)
                if class_name:
                    s.class_name = class_name
                    s.save()

            except StudentProfile.DoesNotExist:
                # 2. ถ้าหาไม่เจอ -> สร้างใหม่เลย (Auto-Create)
                try:
                    # ตรวจสอบหรือสร้าง User ในตาราง auth_user
                    user, user_created = User.objects.get_or_create(username=username)
                    if user_created:
                        # ตั้งรหัสผ่านเริ่มต้น = username (หรือจะเปลี่ยนเป็น '123456' ก็ได้)
                        user.set_password(username) 
                        user.save()
                    
                    # สร้าง StudentProfile ผูกกับ User นั้น
                    s = StudentProfile.objects.create(
                        user=user,
                        class_name=class_name if class_name else "ไม่ระบุห้อง"
                    )
                    new_students_count += 1
                    
                except Exception as e:
                    error_rows.append(f"แถว {index}: สร้าง User ใหม่ไม่สำเร็จ ({e})")
                    continue
            # --- จบส่วนที่แก้ ---

            # สร้าง BehaviorRecord (เหมือนเดิม)
            try:
                def clean_int(val):
                    return int(val) if val and val.strip().isdigit() else 0
                
                def clean_float(val):
                    try:
                        return float(val) if val else 0.0
                    except ValueError:
                        return 0.0

                BehaviorRecord.objects.create(
                    student=s,
                    record_date=row.get("record_date") or None,
                    attendance_score=clean_int(row.get("attendance_score")),
                    homework_done=row.get("homework_done", "0").strip() == "1",
                    quiz_score=clean_float(row.get("quiz_score")),
                    activity_score=clean_int(row.get("activity_score")),
                )
                created_count += 1

            except Exception as e:
                error_rows.append(f"แถว {index}: บันทึกคะแนนไม่สำเร็จ ({e})")

        # สรุปผล
        msg = f"นำเข้าข้อมูล {created_count} รายการ"
        if new_students_count > 0:
            msg += f" (สร้างนักเรียนใหม่ {new_students_count} คน)"
            
        messages.success(request, msg)
        
        if error_rows:
            err_msg = "<br>".join(error_rows[:5])
            if len(error_rows) > 5:
                err_msg += f"<br>...และอีก {len(error_rows)-5} รายการ"
            messages.warning(request, f"พบปัญหาบางรายการ:<br>{err_msg}")

        return redirect("teacher_student_import")
    return render(request, "management/teacher_student_import.html")

def risk_students():
    risky = []
    records = BehaviorRecord.objects.all().order_by("student", "-created_at")

    for r in records:
        avg = (r.attendance_score + r.homework_score + r.quiz_score + r.participation_score) / 4
        if avg < 60:
            risky.append(r.student)

    return set(risky)