from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from .models import StudentProfile, BehaviorRecord, StudentFeedback, UrgentContact, PrivateNote

class StudentForm(forms.ModelForm):
    class Meta:
        model = StudentProfile
        fields = ['class_name']


class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(required=False)
    last_name = forms.CharField(required=False)
    class_name = forms.CharField(required=False)

    class Meta:
        model = User
        fields = ("username","email","first_name","last_name","password1","password2","class_name")

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
            # สร้าง Profile และบันทึกห้องเรียน
            profile, created = StudentProfile.objects.get_or_create(user=user)
            profile.class_name = self.cleaned_data.get('class_name','')
            profile.save()
        return user

class StudentProfileForm(forms.Form):
    first_name = forms.CharField(label="ชื่อจริง", max_length=150, required=True, widget=forms.TextInput(attrs={'class': 'w-full px-4 py-2 border border-gray-300 rounded-xl outline-none focus:border-indigo-500'}))
    last_name = forms.CharField(label="นามสกุล", max_length=150, required=True, widget=forms.TextInput(attrs={'class': 'w-full px-4 py-2 border border-gray-300 rounded-xl outline-none focus:border-indigo-500'}))

    email = forms.EmailField(label="อีเมล", required=False, widget=forms.TextInput(attrs={'class': 'w-full px-4 py-2 bg-gray-100 border border-gray-300 rounded-xl outline-none text-gray-500', 'readonly': 'readonly'}))
    
    profile_image = forms.ImageField(label="รูปโปรไฟล์", required=False)
    nickname = forms.CharField(label="ชื่อเล่น", max_length=50, required=False, widget=forms.TextInput(attrs={'class': 'w-full px-4 py-2 border border-gray-300 rounded-xl outline-none focus:border-indigo-500'}))
    bio = forms.CharField(label="คติประจำใจ", required=False, widget=forms.Textarea(attrs={'rows': 3, 'class': 'w-full px-4 py-2 border border-gray-300 rounded-xl outline-none focus:border-indigo-500'}))
    phone = forms.CharField(label="เบอร์โทรศัพท์", max_length=20, required=False, widget=forms.TextInput(attrs={'class': 'w-full px-4 py-2 border border-gray-300 rounded-xl outline-none focus:border-indigo-500'}))
    line_id = forms.CharField(label="Line ID", required=False, widget=forms.TextInput(attrs={'class': 'w-full px-4 py-2 border border-gray-300 rounded-xl outline-none focus:border-indigo-500'}))
    class_name = forms.CharField(label="ห้องเรียน", max_length=100, required=False, widget=forms.TextInput(attrs={'class': 'w-full px-4 py-2 border border-gray-300 rounded-xl outline-none focus:border-indigo-500'}))

class TeacherProfileForm(forms.Form):
    first_name = forms.CharField(label="ชื่อจริง", max_length=150, required=True, widget=forms.TextInput(attrs={'class': 'w-full px-4 py-2 border border-gray-300 rounded-xl outline-none focus:border-indigo-500'}))
    last_name = forms.CharField(label="นามสกุล", max_length=150, required=True, widget=forms.TextInput(attrs={'class': 'w-full px-4 py-2 border border-gray-300 rounded-xl outline-none focus:border-indigo-500'}))
    email = forms.EmailField(label="อีเมล", required=False, widget=forms.TextInput(attrs={'class': 'w-full px-4 py-2 bg-gray-100 border border-gray-300 rounded-xl outline-none text-gray-500', 'readonly': 'readonly'}))
    
    profile_image = forms.ImageField(label="รูปโปรไฟล์", required=False, widget=forms.FileInput(attrs={'class': 'block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-indigo-50 file:text-indigo-700 hover:file:bg-indigo-100'}))
    nickname = forms.CharField(label="ชื่อเล่น", max_length=50, required=False, widget=forms.TextInput(attrs={'class': 'w-full px-4 py-2 border border-gray-300 rounded-xl outline-none focus:border-indigo-500'}))
    bio = forms.CharField(label="แนะนำตัว (Bio)", required=False, widget=forms.Textarea(attrs={'rows': 3, 'class': 'w-full px-4 py-2 border border-gray-300 rounded-xl outline-none focus:border-indigo-500'}))
    phone = forms.CharField(label="เบอร์โทรศัพท์", max_length=20, required=False, widget=forms.TextInput(attrs={'class': 'w-full px-4 py-2 border border-gray-300 rounded-xl outline-none focus:border-indigo-500'}))
    
    DEPARTMENT_CHOICES = [
        ('','-- เลือกกลุ่มสาระ --'),
        ('math','คณิตศาสตร์'),
        ('sci','วิทยาศาสตร์'),
        ('eng','ภาษาต่างประเทศ'),
        ('thai','ภาษาไทย'),
        ('soc','สังคมศึกษา'),
        ('art','ศิลปะ'),
        ('pe','สุขศึกษาและพลศึกษา'),
        ('work','การงานอาชีพ'),
        ('comp', 'คอมพิวเตอร์'),
        ('guidance', 'แนะแนว'),
    ]
    department = forms.ChoiceField(label="กลุ่มสาระฯ", choices=DEPARTMENT_CHOICES, required=False, widget=forms.Select(attrs={'class': 'w-full px-4 py-2 border border-gray-300 rounded-xl outline-none bg-white focus:border-indigo-500'}))
    position = forms.CharField(label="ตำแหน่ง", max_length=100, required=False, widget=forms.TextInput(attrs={'class': 'w-full px-4 py-2 border border-gray-300 rounded-xl outline-none focus:border-indigo-500'}))
    line_id = forms.CharField(label="Line ID", max_length=50, required=False, widget=forms.TextInput(attrs={'class': 'w-full px-4 py-2 border border-gray-300 rounded-xl outline-none focus:border-indigo-500'}))

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        self.profile = kwargs.pop('profile', None)
        super(TeacherProfileForm, self).__init__(*args, **kwargs)

        if self.user:
            self.fields['first_name'].initial = self.user.first_name
            self.fields['last_name'].initial = self.user.last_name
            self.fields['email'].initial = self.user.email
        
        if self.profile:
            self.fields['nickname'].initial = self.profile.nickname
            self.fields['bio'].initial = self.profile.bio
            self.fields['phone'].initial = self.profile.phone
            self.fields['department'].initial = self.profile.department
            self.fields['position'].initial = self.profile.position
            self.fields['line_id'].initial = self.profile.line_id


    def save(self):
        if self.user:
            self.user.first_name = self.cleaned_data['first_name']
            self.user.last_name = self.cleaned_data['last_name']
            self.user.save()

        if self.profile:
            self.profile.nickname = self.cleaned_data['nickname']
            self.profile.bio = self.cleaned_data['bio']
            self.profile.phone = self.cleaned_data['phone']
            self.profile.department = self.cleaned_data['department']
            self.profile.position = self.cleaned_data['position']
            self.profile.line_id = self.cleaned_data['line_id']
            
            if self.cleaned_data.get('profile_image'):
                self.profile.profile_image = self.cleaned_data['profile_image']
            
            self.profile.save()


def get_tailwind_widgets():
    return {
        'message': forms.Textarea(attrs={'rows': 3, 'class': 'w-full border border-gray-300 rounded-xl px-4 py-2 focus:ring-2 focus:ring-indigo-500 outline-none resize-none'}),
        'content': forms.Textarea(attrs={'rows': 3, 'class': 'w-full border border-gray-300 rounded-xl px-4 py-2 focus:ring-2 focus:ring-indigo-500 outline-none resize-none'}),
        'title': forms.TextInput(attrs={'class': 'w-full border border-gray-300 rounded-xl px-4 py-2 focus:ring-2 focus:ring-indigo-500 outline-none'}),
        'feedback_type': forms.Select(attrs={'class': 'w-full border border-gray-300 rounded-xl px-4 py-2 outline-none bg-white'}),
        'target': forms.Select(attrs={'class': 'w-full border border-gray-300 rounded-xl px-4 py-2 outline-none bg-white'}),
        'method': forms.Select(attrs={'class': 'w-full border border-gray-300 rounded-xl px-4 py-2 outline-none bg-white'}),
    }

class BehaviorForm(forms.ModelForm):
    ATTENDANCE_CHOICES = [
        (100, '🟢 มาเรียน (ปกติ)'),
        (50,  '🟡 มาสาย'),
        (0,   '🔴 ขาดเรียน'),
    ]

    attendance_score = forms.TypedChoiceField(
        choices=ATTENDANCE_CHOICES,
        coerce=int, 
        empty_value=0,
        widget=forms.Select(attrs={
            'class': 'w-full rounded-xl border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 py-2.5',
        }),
        label="สถานะการเข้าเรียน"
    )
    
    ACTIVITY_CHOICES = [
        (10, '🌟 ดีมาก (Active)'), 
        (5,  '🙂 ปกติ (Passive)'),
        (0,  '😴 ไม่ร่วมกิจกรรม'),
    ]
    
    activity_score = forms.TypedChoiceField(
        choices=ACTIVITY_CHOICES,
        coerce=int,
        empty_value=0,
        widget=forms.Select(attrs={
            'class': 'w-full rounded-xl border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 py-2.5',
        }),
        label="การมีส่วนร่วม/กิจกรรม"
    )
    
    class Meta:
        model = BehaviorRecord
        fields = ['record_date', 'attendance_score', 'homework_done', 'quiz_score', 'activity_score']
        widgets = {
            'record_date': forms.DateInput(attrs={'type': 'date', 'class': 'border rounded px-3 py-2 w-full'}),
            'quiz_score': forms.NumberInput(attrs={'class': 'border rounded px-3 py-2 w-full'}),
            'activity_score': forms.NumberInput(attrs={'class': 'border rounded px-3 py-2 w-full'}),
        }

class FeedbackForm(forms.ModelForm):
    class Meta:
        model = StudentFeedback
        fields = ['feedback_type', 'message']
        widgets = get_tailwind_widgets()
        labels = {'feedback_type': 'ประเภท', 'message': 'ข้อความ'}

class ContactForm(forms.ModelForm):
    class Meta:
        model = UrgentContact
        fields = ['target', 'method', 'message']
        widgets = get_tailwind_widgets()
        labels = {'target': 'ส่งถึง', 'method': 'ช่องทาง', 'message': 'รายละเอียดการติดต่อ'}

class PrivateNoteForm(forms.ModelForm):
    NOTE_TYPES = [
        ('general', '📝 ทั่วไป'),
        ('behavior', '⚠️ พฤติกรรม'),
        ('academic', '📚 การเรียน'),
        ('family', '👨‍👩‍👧‍👦 ครอบครัว/ทางบ้าน'),
        ('urgent', '🚨 เร่งด่วน'),
    ]

    note_type = forms.ChoiceField(
        choices=NOTE_TYPES, 
        widget=forms.Select(attrs={'class': 'w-full border border-gray-300 rounded-xl px-4 py-2 focus:ring-2 focus:ring-indigo-500 outline-none bg-white'}),
        label="หมวดหมู่"
    )

    class Meta:
        model = PrivateNote
        fields = ['title', 'note_type', 'content']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'w-full border border-gray-300 rounded-xl px-4 py-2 focus:ring-2 focus:ring-indigo-500 outline-none', 'placeholder': 'หัวข้อบันทึก...'}),
            'content': forms.Textarea(attrs={'class': 'w-full border border-gray-300 rounded-xl px-4 py-2 focus:ring-2 focus:ring-indigo-500 outline-none resize-none', 'rows': 4, 'placeholder': 'รายละเอียด...'}),
        }