from django.db import models
from django.utils.text import slugify


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

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)


class Comment(models.Model):
    blog = models.ForeignKey(Blogs, on_delete=models.CASCADE, related_name='comments')
    name = models.CharField(max_length=100)
    email_address = models.EmailField()
    comment = models.TextField()
    status = models.IntegerField(default=1)


