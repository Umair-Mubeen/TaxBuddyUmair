from django.db import models
from django.contrib.auth.models import User
from django.utils.text import slugify
from django.utils import timezone


# ─────────────────────────────────────────────────────────────
# BLOG
# ─────────────────────────────────────────────────────────────

class Blog(models.Model):
    STATUS_CHOICES = [('draft', 'Draft'), ('published', 'Published')]
    TYPE_CHOICES   = [('income_tax', 'Income Tax'), ('sales_tax', 'Sales Tax'),
                      ('general', 'General'), ('freelancer', 'Freelancer')]

    title             = models.CharField(max_length=300)
    slug              = models.SlugField(max_length=350, unique=True, blank=True)
    category          = models.CharField(max_length=100, blank=True)
    type              = models.CharField(max_length=50, choices=TYPE_CHOICES, default='general')
    content           = models.TextField()
    featured_image    = models.ImageField(upload_to='blog_images/', null=True, blank=True)
    author            = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    status            = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    tag               = models.CharField(max_length=500, blank=True, help_text="Comma-separated tags")
    meta_title        = models.CharField(max_length=200, blank=True)
    meta_description  = models.TextField(max_length=300, blank=True)
    view_count        = models.PositiveIntegerField(default=0)
    is_deleted        = models.BooleanField(default=False)
    deleted_at        = models.DateTimeField(null=True, blank=True)
    created_at        = models.DateTimeField(auto_now_add=True)
    updated_at        = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Blog'
        verbose_name_plural = 'Blogs'

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.title)
            slug = base
            n = 1
            while Blog.objects.filter(slug=slug).exists():
                slug = f"{base}-{n}"
                n += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def get_tags_list(self):
        if self.tag:
            return [t.strip() for t in self.tag.split(',') if t.strip()]
        return []


class Comment(models.Model):
    STATUS_CHOICES = [(0, 'Pending'), (1, 'Approved'), (2, 'Rejected')]

    blog          = models.ForeignKey(Blog, on_delete=models.CASCADE, related_name='comments', null=True, blank=True)
    slug          = models.SlugField(max_length=350, blank=True)
    name          = models.CharField(max_length=100)
    email_address = models.EmailField()
    comment       = models.TextField()
    status        = models.IntegerField(choices=STATUS_CHOICES, default=0)
    created_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} on {self.slug}"


# ─────────────────────────────────────────────────────────────
# CONTACT
# ─────────────────────────────────────────────────────────────

class Contact(models.Model):
    first_name         = models.CharField(max_length=100)
    last_name          = models.CharField(max_length=100, blank=True)
    phone_number       = models.CharField(max_length=20, blank=True)
    email_address      = models.EmailField()
    subject            = models.CharField(max_length=200, blank=True)
    additional_details = models.TextField(blank=True)
    is_read            = models.BooleanField(default=False)
    created_at         = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.first_name} {self.last_name} – {self.email_address}"


# ─────────────────────────────────────────────────────────────
# TAX BRACKETS
# ─────────────────────────────────────────────────────────────

class TaxBracket(models.Model):
    """Salary Individual tax brackets."""
    year        = models.CharField(max_length=20)  # e.g. "2025-2026"
    income_min  = models.DecimalField(max_digits=15, decimal_places=2)
    income_max  = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    rate        = models.DecimalField(max_digits=5, decimal_places=4)  # e.g. 0.05 = 5%
    base_income = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    base_tax    = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    class Meta:
        ordering = ['year', 'income_min']
        verbose_name = 'Salary Tax Bracket'

    def __str__(self):
        return f"{self.year} | {self.income_min} – {self.income_max or '∞'} @ {self.rate*100:.1f}%"


class Business_AOP_Slab(models.Model):
    """Business Individual / AOP tax slabs."""
    year        = models.CharField(max_length=20)
    income_min  = models.DecimalField(max_digits=15, decimal_places=2)
    income_max  = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    rate        = models.DecimalField(max_digits=5, decimal_places=4)
    base_income = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    base_tax    = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    class Meta:
        ordering = ['year', 'income_min']
        verbose_name = 'Business/AOP Slab'

    def __str__(self):
        return f"Biz/AOP {self.year} | {self.income_min} – {self.income_max or '∞'}"


class Property_Business_AOP_Slab(models.Model):
    """Rental / Property income slabs."""
    year        = models.CharField(max_length=20)
    income_min  = models.DecimalField(max_digits=15, decimal_places=2)
    income_max  = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    rate        = models.DecimalField(max_digits=5, decimal_places=4)
    base_income = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    base_tax    = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    class Meta:
        ordering = ['year', 'income_min']
        verbose_name = 'Property/Rental Slab'

    def __str__(self):
        return f"Property {self.year} | {self.income_min}"


class SuperTax4CRate(models.Model):
    tax_year    = models.IntegerField()
    income_from = models.DecimalField(max_digits=15, decimal_places=2)
    income_to   = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    rate        = models.DecimalField(max_digits=5, decimal_places=4)

    class Meta:
        ordering = ['tax_year', 'income_from']
        verbose_name = 'Super Tax 4C Rate'

    def __str__(self):
        return f"Super Tax {self.tax_year} | {self.income_from} @ {self.rate*100:.1f}%"


# ─────────────────────────────────────────────────────────────
# MCQ / QUIZ
# ─────────────────────────────────────────────────────────────

class Category(models.Model):
    name  = models.CharField(max_length=100)
    order = models.PositiveIntegerField(default=0)
    slug  = models.SlugField(max_length=120, unique=True, blank=True)

    class Meta:
        ordering = ['order', 'name']
        verbose_name_plural = 'Categories'

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Tag(models.Model):
    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(unique=True, blank=True)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Question(models.Model):
    DIFFICULTY_CHOICES = [('basic', 'Basic'), ('medium', 'Medium'), ('advanced', 'Advanced')]

    question_text = models.TextField()
    category      = models.CharField(max_length=100, blank=True)
    explanation   = models.TextField(blank=True)
    section_ref   = models.CharField(max_length=200, blank=True, help_text="e.g. ITO 2001, Section 155")
    difficulty    = models.CharField(max_length=20, choices=DIFFICULTY_CHOICES, default='basic')
    is_active     = models.BooleanField(default=True)
    created_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['category', 'id']

    def __str__(self):
        return self.question_text[:80]


class Option(models.Model):
    question   = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='options')
    option_text = models.CharField(max_length=500)
    is_correct  = models.BooleanField(default=False)

    def __str__(self):
        return f"{'✓' if self.is_correct else '✗'} {self.option_text[:60]}"


# ─────────────────────────────────────────────────────────────
# TESTIMONIALS & FAQ  (new — used by homepage)
# ─────────────────────────────────────────────────────────────

class Testimonial(models.Model):
    name       = models.CharField(max_length=100)
    role       = models.CharField(max_length=150, blank=True)
    initials   = models.CharField(max_length=4, blank=True)
    text       = models.TextField()
    rating     = models.PositiveSmallIntegerField(default=5)
    is_active  = models.BooleanField(default=True)
    order      = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', '-created_at']

    def __str__(self):
        return f"{self.name} – {self.role}"

    def stars(self):
        return '★' * self.rating + '☆' * (5 - self.rating)


class FAQ(models.Model):
    question   = models.CharField(max_length=300)
    answer     = models.TextField()
    page       = models.CharField(max_length=50, default='home', help_text="home, calculator, mcq …")
    order      = models.PositiveIntegerField(default=0)
    is_active  = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['page', 'order']

    def __str__(self):
        return self.question[:80]
