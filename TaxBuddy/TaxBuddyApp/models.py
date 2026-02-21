from django.contrib.auth.models import User
from django.db import models
from django.utils.text import slugify
from django.utils import timezone
from django.urls import reverse

class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children'
    )

    def __str__(self):
        return self.name


class Tag(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True, blank=True)

    def save(self, *args, **kwargs):
        self.name = self.name.strip().lower()

        if not self.slug:
            self.slug = slugify(self.name)

        super().save(*args, **kwargs)

    def __str__(self):
        return self.name



# ==============================
# BLOG MODEL
# ==============================

class Blog(models.Model):

    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('archived', 'Archived'),
    ]

    TYPE_CHOICES = [
        ('article', 'Article'),
        ('blog', 'Blog'),
        ('news', 'News'),
        ('event', 'Event'),
    ]

    # Basic Info
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)

    author = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="blogs"
    )

    tag = models.CharField(max_length=100, default="", blank=True)
    category = models.CharField(max_length=100, default="", blank=True)

    type = models.CharField(max_length=50, choices=TYPE_CHOICES)

    # Content
    content = models.TextField()
    excerpt = models.TextField(blank=True, null=True)

    featured_image = models.ImageField(upload_to="blog/", blank=True, null=True)

    # SEO Fields
    meta_title = models.CharField(max_length=255, blank=True, null=True)
    meta_description = models.TextField(blank=True, null=True)
    focus_keyword = models.CharField(max_length=150, blank=True, null=True)

    # Status & Publishing
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    is_featured = models.BooleanField(default=False)

    published_at = models.DateTimeField(blank=True, null=True)

    # Analytics
    views = models.PositiveIntegerField(default=0)

    # Soft Delete
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(blank=True, null=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-published_at', '-created_at']
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['status']),
            models.Index(fields=['published_at']),
        ]

    def save(self, *args, **kwargs):

        # Auto slug generator
        if not self.slug:
            base_slug = slugify(self.title)
            slug = base_slug
            counter = 1

            while Blog.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1

            self.slug = slug

        # Auto publish date
        if self.status == "published" and not self.published_at:
            self.published_at = timezone.now()

        super().save(*args, **kwargs)

    def soft_delete(self):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save()

    def get_absolute_url(self):
        return reverse("blog_detail", kwargs={"slug": self.slug})

    def __str__(self):
        return self.title


class Comment(models.Model):
    blog = models.ForeignKey(Blog, on_delete=models.CASCADE, related_name='comments')
    name = models.CharField(max_length=100)
    email_address = models.EmailField()
    comment = models.TextField()
    slug = models.SlugField(max_length=255, blank=True)
    status = models.IntegerField(default=1)


class Contact(models.Model):
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    phone_number = models.CharField(max_length=15)
    email_address = models.EmailField()
    subject = models.CharField(max_length=200)
    additional_details = models.TextField(blank=True, null=True)


class TaxBracket(models.Model):
    YEAR_CHOICES = [
        ("2021-2022", "2021-2022"),
        ("2022-2023", "2022-2023"),
        ("2023-2024", "2023-2024"),
        ("2024-2025", "2024-2025"),
        ("2025-2026", "2025-2026"),

    ]
    year = models.CharField(max_length=20, choices=YEAR_CHOICES)
    income_min = models.BigIntegerField()
    income_max = models.BigIntegerField(null=True, blank=True)  # null = infinity
    rate = models.DecimalField(max_digits=5, decimal_places=3)  # store 0.35 for 35%
    base_income = models.BigIntegerField()
    base_tax = models.BigIntegerField()


class Business_AOP_Slab(models.Model):
    YEAR_CHOICES = [
        ("2021-2022", "2021-2022"),
        ("2022-2023", "2022-2023"),
        ("2023-2024", "2023-2024"),
        ("2024-2025", "2024-2025"),
        ("2025-2026", "2025-2026"),

    ]
    year = models.CharField(max_length=20, choices=YEAR_CHOICES)
    income_min = models.BigIntegerField()
    income_max = models.BigIntegerField(null=True, blank=True)  # null = infinity
    rate = models.DecimalField(max_digits=5, decimal_places=3)  # store 0.35 for 35%
    base_income = models.BigIntegerField()
    base_tax = models.BigIntegerField()


class Property_Business_AOP_Slab(models.Model):
    YEAR_CHOICES = [
        ("2021-2022", "2021-2022"),
        ("2022-2023", "2022-2023"),
        ("2023-2024", "2023-2024"),
        ("2024-2025", "2024-2025"),
        ("2025-2026", "2025-2026"),

    ]
    year = models.CharField(max_length=20, choices=YEAR_CHOICES)
    income_min = models.BigIntegerField()
    income_max = models.BigIntegerField(null=True, blank=True)  # null = infinity
    rate = models.DecimalField(max_digits=5, decimal_places=3)  # store 0.35 for 35%
    base_income = models.BigIntegerField()
    base_tax = models.BigIntegerField()



class Question(models.Model):
    question_text = models.CharField(max_length=500)

    category = models.CharField(
        max_length=100,
        help_text="e.g. Basic Income Tax, Withholding Tax"
    )

    explanation = models.TextField(blank=True)
    section_ref = models.CharField(max_length=100, blank=True)

    difficulty = models.CharField(
        max_length=20,
        choices=[
            ("basic", "Basic"),
            ("intermediate", "Intermediate"),
            ("advanced", "Advanced"),
        ],
        default="basic"
    )

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["category", "id"]   # ✅ FIXED

    def __str__(self):
        return self.question_text



class Option(models.Model):
    question = models.ForeignKey(
        Question,
        related_name="options",
        on_delete=models.CASCADE
    )

    option_text = models.CharField(max_length=255)
    is_correct = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.option_text} ({'Correct' if self.is_correct else 'Wrong'})"


class SuperTax4CRate(models.Model):
    tax_year = models.IntegerField()
    income_from = models.BigIntegerField()
    income_to = models.BigIntegerField(null=True, blank=True)
    rate = models.DecimalField(max_digits=5, decimal_places=4)  # e.g. 0.03 = 3%
