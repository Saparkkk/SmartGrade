from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from .models import StudentProfile

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
        model = StudentProfile  # or BehaviorRecord if creating records
        fields = ['class_name','profile_image']
