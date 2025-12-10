import csv
import io
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from .forms import RegisterForm, StudentProfileForm, TeacherProfileForm
from .models import Student, StudentProfile, BehaviorRecord, UserProfile, StudentProfile
from django.db.models import Sum
from django.contrib import messages


def get_role_for_user(user):
    # ไม่ต้อง sync กับ is_staff แล้ว ให้ role ใน UserProfile เป็นตัวจริง
    user_profile, _ = UserProfile.objects.get_or_create(
        user=user,
        defaults={"role": "student"}  # ค่าเริ่มต้นเป็นนักเรียน
    )
    return user_profile

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

    context = {
        "students": students,
        "risk_students": risk_students,
    }
    return render(request, 'management/dashboard_teacher.html', context)

@login_required
def student_dashboard(request):
    # กันไม่ให้ครูเข้าหน้านักเรียน (จะโยนกลับไปหน้า teacher)
    if request.user.is_staff:
        return redirect('teacher_dashboard')

    user = request.user
    profile, created = StudentProfile.objects.get_or_create(user=user)
    behaviors = profile.behaviors.order_by('-record_date')[:10]

    latest = behaviors.first() if behaviors else None
    status = "ไม่มีข้อมูล"
    advice = ""

    if latest:
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

    return render(
        request,
        'management/dashboard_student.html',
        {'profile': profile, 'behaviors': behaviors, 'status': status, 'advice': advice}
    )
    
def student_list_view(request):
    students = (
        StudentProfile.objects
        .select_related('user')
        .all()
    )

    student_rows = []
    for s in students:
        latest_behavior = (
            BehaviorRecord.objects
            .filter(student=s)
            .order_by('-record_date')
            .first()
        )
        status, color, summary = evaluate_status(latest_behavior)

        if latest_behavior:
            total_score = (
                (latest_behavior.attendance_score or 0) +
                (latest_behavior.quiz_score or 0) +
                (latest_behavior.activity_score or 0)
            )
        else:
            total_score = 0

        student_rows.append({
            "profile": s,
            "status": status,
            "color": color,          # "green" / "yellow" / "red" / "gray"
            "total_score": total_score,
            "summary": summary,
        })

    context = {
        "student_rows": student_rows,
    }
    return render(request, "management/teacher_student_list.html", context)

def student_detail_view(request, pk):
    profile = get_object_or_404(StudentProfile, pk=pk)
    behaviors = (
        BehaviorRecord.objects
        .filter(student=profile)
        .order_by('-record_date')
    )
    latest = behaviors.first()
    status, color, summary = evaluate_status(latest)

    context = {
        "profile": profile,
        "behaviors": behaviors,
        "status": status,
        "color": color,
        "summary": summary,
    }
    return render(request, "management/teacher_student_detail.html", context)

def student_import_csv_view(request):
    """
    รับ CSV ที่มี header ตัวอย่าง:
    username,class_name,record_date,attendance_score,homework_done,quiz_score,activity_score
    """
    if request.method == "POST":
        csv_file = request.FILES.get("file")
        if not csv_file:
            messages.error(request, "กรุณาเลือกไฟล์ CSV ก่อน")
            return redirect("teacher_student_import")

        if not csv_file.name.endswith(".csv"):
            messages.error(request, "รองรับเฉพาะไฟล์ .csv เท่านั้น")
            return redirect("teacher_student_import")

        # แปลงเป็น text stream
        try:
            data = io.TextIOWrapper(csv_file.file, encoding="utf-8")
            reader = csv.DictReader(data)
        except Exception:
            messages.error(request, "ไม่สามารถอ่านไฟล์ CSV ได้")
            return redirect("teacher_student_import")

        created = 0
        for row in reader:
            username = row.get("username")
            class_name = row.get("class_name")
            if not username:
                continue

            # หา StudentProfile จาก username
            try:
                s = StudentProfile.objects.select_related("user").get(
                    user__username=username
                )
            except StudentProfile.DoesNotExist:
                # ถ้าอยากสร้างใหม่เลย ก็เขียน logic เพิ่มเองได้
                continue

            # อัปเดต class_name ถ้าส่งมาด้วย
            if class_name:
                s.class_name = class_name
                s.save()

            BehaviorRecord.objects.create(
                student=s,
                record_date=row.get("record_date") or None,
                attendance_score=int(row.get("attendance_score") or 0),
                homework_done=row.get("homework_done") == "1",
                quiz_score=int(row.get("quiz_score") or 0),
                activity_score=int(row.get("activity_score") or 0),
            )
            created += 1

        messages.success(request, f"นำเข้า Behavioral Records สำเร็จ {created} แถว")
        return redirect("teacher_student_list")

    return render(request, "management/teacher_student_import.html")

# CREATE
def create_student(request):
    if request.method == "POST":
        username = request.POST['username']
        name = request.POST['name']
        email = request.POST['email']
        password = request.POST['password']
        class_name = request.POST['class_name']
        student_id = request.POST['student_id']
        Student.objects.create(
            username=username,  # demo ยังไม่ hash
            name=name,
            email=email,
            password=password,
            class_name=class_name,
            student_id=student_id
        )
        return redirect('list_students')
    return render(request, 'management/create_student.html')

# RETRIEVE (READ)
def list_students(request):
    students = Student.objects.all()
    return render(request, 'management/list_students.html', {'students': students})

# UPDATE
def update_student(request, student_id):
    student = get_object_or_404(Student, pk=student_id)
    if request.method == "POST":
        student.name = request.POST['name']
        student.email = request.POST['email']
        student.student_id = request.POST['student_id']
        student.class_name = request.POST['class_name']
        student.save()
        return redirect('list_students')
    return render(request, 'management/update_student.html', {'student': student})

# DELETE
def delete_student(request, student_id):
    student = get_object_or_404(Student, pk=student_id)
    student.delete()
    return redirect('list_students')
