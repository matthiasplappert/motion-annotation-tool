from django.contrib import admin

from .models import MotionFile, Annotation, Download, Dataset


admin.site.register(MotionFile)
admin.site.register(Annotation)
admin.site.register(Download)
admin.site.register(Dataset)
