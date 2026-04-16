from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm


class RegisterForm(UserCreationForm):
    first_name = forms.CharField(max_length=50, required=True)
    last_name  = forms.CharField(max_length=50, required=True)
    email      = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'username', 'email', 'password1', 'password2']

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("Bu email allaqachon ro'yxatdan o'tgan.")
        return email

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("Bu foydalanuvchi nomi band.")
        return username


class LoginForm(AuthenticationForm):
    pass


class PasswordResetRequestForm(forms.Form):
    email = forms.EmailField()

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if not User.objects.filter(email=email).exists():
            raise forms.ValidationError("Bu email bilan ro'yxatdan o'tgan foydalanuvchi topilmadi.")
        return email


class OTPVerifyForm(forms.Form):
    otp = forms.CharField(max_length=6, min_length=6)


class SetNewPasswordForm(forms.Form):
    new_password1 = forms.CharField(min_length=8)
    new_password2 = forms.CharField(min_length=8)

    def clean(self):
        d = super().clean()
        if d.get('new_password1') != d.get('new_password2'):
            raise forms.ValidationError("Parollar mos kelmadi.")
        return d


class ProfileEditForm(forms.Form):
    first_name       = forms.CharField(max_length=50, required=False)
    last_name        = forms.CharField(max_length=50, required=False)
    username         = forms.CharField(max_length=150)
    email            = forms.EmailField()
    bio              = forms.CharField(widget=forms.Textarea, required=False)
    country          = forms.CharField(max_length=100, required=False)
    city             = forms.CharField(max_length=100, required=False)
    favorite_opening = forms.CharField(max_length=100, required=False)
    play_style       = forms.ChoiceField(
        choices=[('','--'),('aggressive','Hujumkor'),('defensive','Mudofaachi'),
                 ('positional','Pozitsion'),('tactical','Taktik')],
        required=False)
    avatar           = forms.ImageField(required=False)

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean_username(self):
        username = self.cleaned_data.get('username')
        qs = User.objects.filter(username=username).exclude(pk=self.user.pk)
        if qs.exists():
            raise forms.ValidationError("Bu foydalanuvchi nomi band.")
        return username

    def clean_email(self):
        email = self.cleaned_data.get('email')
        qs = User.objects.filter(email=email).exclude(pk=self.user.pk)
        if qs.exists():
            raise forms.ValidationError("Bu email allaqachon ishlatilgan.")
        return email


class AdminAddUserForm(UserCreationForm):
    first_name = forms.CharField(max_length=50, required=False)
    last_name  = forms.CharField(max_length=50, required=False)
    email      = forms.EmailField(required=True)
    role       = forms.ChoiceField(choices=[('user','O\'yinchi'),('admin','Admin'),('superuser','Superuser')])
    is_active  = forms.BooleanField(required=False, initial=True)
    initial_rating = forms.IntegerField(min_value=100, max_value=3000, initial=1200)

    class Meta:
        model = User
        fields = ['first_name','last_name','username','email','password1','password2']


class AdminEditUserForm(forms.Form):
    first_name = forms.CharField(max_length=50, required=False)
    last_name  = forms.CharField(max_length=50, required=False)
    username   = forms.CharField(max_length=150)
    email      = forms.EmailField()
    rating     = forms.IntegerField(min_value=100, max_value=3000)
    wins       = forms.IntegerField(min_value=0)
    losses     = forms.IntegerField(min_value=0)
    is_staff   = forms.BooleanField(required=False)
    is_active  = forms.BooleanField(required=False)

    def __init__(self, target_user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.target_user = target_user

    def clean_username(self):
        username = self.cleaned_data.get('username')
        qs = User.objects.filter(username=username).exclude(pk=self.target_user.pk)
        if qs.exists():
            raise forms.ValidationError("Bu foydalanuvchi nomi band.")
        return username


class AdminResetPasswordForm(forms.Form):
    new_password  = forms.CharField(min_length=6)
    new_password2 = forms.CharField(min_length=6)

    def clean(self):
        d = super().clean()
        if d.get('new_password') != d.get('new_password2'):
            raise forms.ValidationError("Parollar mos kelmadi.")
        return d
