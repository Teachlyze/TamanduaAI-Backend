from django.contrib import admin
from .models import (
    User, Profile, Plan, Payment, ClassModel,
    Invite, ClassStudent, Activity, ActivityClass,
    Submission, Feedback
)

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'email', 'cpf', 'is_teacher', 'verified_email')
    search_fields = ('full_name', 'email', 'cpf')
    list_filter = ('is_teacher', 'verified_email')

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'age', 'school', 'teaching_area')
    search_fields = ('user__full_name', 'school', 'teaching_area')

@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'price_cents', 'description')
    search_fields = ('name',)

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('user', 'plan', 'amount', 'method', 'status', 'created_at')
    list_filter = ('method', 'status')
    search_fields = ('user__full_name', 'plan__name')
    date_hierarchy = 'created_at'

@admin.register(ClassModel)
class ClassModelAdmin(admin.ModelAdmin):
    list_display = ('name', 'professor', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('name', 'professor__full_name')

@admin.register(Invite)
class InviteAdmin(admin.ModelAdmin):
    list_display = ('code', 'class_invite', 'max_uses', 'uses_count', 'expires_at')
    search_fields = ('code', 'class_invite__name')

@admin.register(ClassStudent)
class ClassStudentAdmin(admin.ModelAdmin):
    list_display = ('class_instance', 'student', 'enrolled_at', 'removed_at')
    search_fields = ('class_instance__name', 'student__full_name')

@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = ('title', 'professor', 'max_score', 'due_date', 'status')
    list_filter = ('status',)
    search_fields = ('title', 'professor__full_name')

@admin.register(ActivityClass)
class ActivityClassAdmin(admin.ModelAdmin):
    list_display = ('activity', 'class_instance')
    search_fields = ('activity__title', 'class_instance__name')

@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ('activity', 'student', 'status', 'submitted_at')
    list_filter = ('status',)
    search_fields = ('activity__title', 'student__full_name')

@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ('submission', 'professor', 'score', 'automatic', 'created_at')
    list_filter = ('automatic',)
    search_fields = ('submission__activity__title', 'professor__full_name')
