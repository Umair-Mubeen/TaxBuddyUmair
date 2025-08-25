from django.db import models
from django.utils.text import slugify
from django.utils import timezone


class Blogs(models.Model):
    TYPE_CHOICES = [
        ('article', 'Article'),
        ('blog', 'Blog'),
        ('news', 'News'),
        ('event', 'Event'),
    ]

    title = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, blank=True, max_length=255, null=True)  # SEO
    type = models.CharField(max_length=50, choices=TYPE_CHOICES)
    description = models.TextField()
    image = models.ImageField(upload_to='uploads/', blank=True, null=True)
    status = models.IntegerField(default=1)
    created_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)  # soft delete field
    deleted_at = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    def delete(self, using=None, keep_parents=False):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save()


class Comment(models.Model):
    blog = models.ForeignKey(Blogs, on_delete=models.CASCADE, related_name='comments')
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


class PropertyTaxBracket(models.Model):
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


