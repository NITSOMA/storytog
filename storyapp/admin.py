from django.contrib import admin

from .models import Story, RequestChapter, Notification


admin.site.register(Story)
admin.site.register(RequestChapter)
admin.site.register(Notification)
