from django.db import models


class Blogs(models.Model):
    TYPE_CHOICES = [
        ('article', 'Article'),
        ('blog', 'Blog'),
        ('news', 'News'),
        ('event', 'Event'),
    ]

    title = models.CharField(max_length=255)
    type = models.CharField(max_length=50, choices=TYPE_CHOICES)
    description = models.TextField()
    image = models.ImageField(upload_to='uploads/', blank=True, null=True)
    status = models.IntegerField(default=1)
    created_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)


class Comment(models.Model):
    blog = models.ForeignKey(Blogs, on_delete=models.CASCADE, related_name='comments')
    name = models.CharField(max_length=100)
    email_address = models.EmailField()
    comment = models.TextField()
    status = models.IntegerField(default=1)


