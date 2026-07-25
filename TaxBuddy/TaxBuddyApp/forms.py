from django import forms
from .models import Contact, Comment


class ContactForm(forms.ModelForm):
    """
    Contact / consultation request form.
    Rendered in the contact section of the homepage and the /contact/ page.
    """
    first_name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Muhammad',
        })
    )
    last_name = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Ahmed',
        })
    )
    phone_number = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': '+92 3XX XXXXXXX',
        })
    )
    email_address = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-input',
            'placeholder': 'you@example.com',
        })
    )
    subject = forms.ChoiceField(
        choices=[
            ('', 'Select a service'),
            ('NTN Registration', 'NTN Registration – PKR 1,000'),
            ('Salary Return Filing', 'Salary Return Filing – PKR 2,000'),
            ('Business Return Filing', 'Business Return Filing – PKR 5,000+'),
            ('Sales Tax Registration', 'Sales Tax Registration – PKR 3,000'),
            ('FBR Notice Response', 'FBR Notice Response – PKR 5,000+'),
            ('Tax Consultation', 'Tax Consultation (30 min) – PKR 1,500'),
            ('Other', 'Other'),
        ],
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    additional_details = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-input',
            'placeholder': 'Describe your tax situation or query…',
            'rows': 4,
        })
    )

    class Meta:
        model = Contact
        fields = ['first_name', 'last_name', 'phone_number',
                  'email_address', 'subject', 'additional_details']


class CommentForm(forms.Form):
    """Blog comment form."""
    user = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Your Name',
        })
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-input',
            'placeholder': 'your@email.com',
        })
    )
    comment = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-input',
            'placeholder': 'Leave a comment…',
            'rows': 4,
        })
    )
    slug = forms.CharField(widget=forms.HiddenInput())
