from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from .models import StudentProfile, BehaviorRecord, StudentFeedback, TeacherNote, UrgentContact

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
            # save profile
            profile = StudentProfile.objects.get(user=user)
            profile.class_name = self.cleaned_data.get('class_name','')
            profile.save()
        return user

class StudentProfileForm(forms.Form):
    first_name = forms.CharField(label="ชื่อ", max_length=150, required=False)
    last_name = forms.CharField(label="นามสกุล", max_length=150, required=False)
    email = forms.EmailField(label="อีเมล", required=True)
    class_name = forms.CharField(label="ห้องเรียน", max_length=100, required=False)
    profile_image = forms.ImageField(label="รูปโปรไฟล์", required=False)


class TeacherProfileForm(forms.Form):
    first_name = forms.CharField(label="ชื่อ", max_length=150, required=False)
    last_name = forms.CharField(label="นามสกุล", max_length=150, required=False)
    email = forms.EmailField(label="อีเมล", required=True)
    profile_image = forms.ImageField(label="รูปโปรไฟล์", required=False)

class BehaviorForm(forms.ModelForm):
    class Meta:
        model = BehaviorRecord
        fields = ['record_date', 'attendance_score', 'homework_done', 'quiz_score', 'activity_score']
        widgets = {
            'record_date': forms.DateInput(attrs={'type': 'date', 'class': 'border rounded px-3 py-2 w-full'}),
            'attendance_score': forms.NumberInput(attrs={'class': 'border rounded px-3 py-2 w-full'}),
            'quiz_score': forms.NumberInput(attrs={'class': 'border rounded px-3 py-2 w-full'}),
            'activity_score': forms.NumberInput(attrs={'class': 'border rounded px-3 py-2 w-full'}),
        }

def get_tailwind_widgets():
    return {
        'message': forms.Textarea(attrs={'rows': 3, 'class': 'w-full border border-gray-300 rounded-xl px-4 py-2 focus:ring-2 focus:ring-indigo-500 outline-none resize-none'}),
        'content': forms.Textarea(attrs={'rows': 3, 'class': 'w-full border border-gray-300 rounded-xl px-4 py-2 focus:ring-2 focus:ring-indigo-500 outline-none resize-none'}),
        'title': forms.TextInput(attrs={'class': 'w-full border border-gray-300 rounded-xl px-4 py-2 focus:ring-2 focus:ring-indigo-500 outline-none'}),
        'feedback_type': forms.Select(attrs={'class': 'w-full border border-gray-300 rounded-xl px-4 py-2 outline-none bg-white'}),
        'note_type': forms.TextInput(attrs={'class': 'w-full border border-gray-300 rounded-xl px-4 py-2 focus:ring-2 focus:ring-indigo-500 outline-none', 'placeholder': 'เช่น ทั่วไป, สิ่งที่ต้องทำ'}),
        'target': forms.Select(attrs={'class': 'w-full border border-gray-300 rounded-xl px-4 py-2 outline-none bg-white'}),
        'method': forms.Select(attrs={'class': 'w-full border border-gray-300 rounded-xl px-4 py-2 outline-none bg-white'}),
    }

class FeedbackForm(forms.ModelForm):
    class Meta:
        model = StudentFeedback
        fields = ['feedback_type', 'message']
        widgets = get_tailwind_widgets()
        labels = {'feedback_type': 'ประเภท', 'message': 'ข้อความ'}

class NoteForm(forms.ModelForm):
    class Meta:
        model = TeacherNote
        fields = ['title', 'note_type', 'content']
        widgets = get_tailwind_widgets()
        labels = {'title': 'หัวข้อ', 'note_type': 'ประเภท', 'content': 'รายละเอียด'}

class ContactForm(forms.ModelForm):
    class Meta:
        model = UrgentContact
        fields = ['target', 'method', 'message']
        widgets = get_tailwind_widgets()
        labels = {'target': 'ส่งถึง', 'method': 'ช่องทาง', 'message': 'รายละเอียดการติดต่อ'}