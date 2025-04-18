from django.db import models
from django.contrib.postgres.fields import ArrayField

# 1 - Usuários

class User(models.Model):
    full_name = models.CharField(max_length=150)
    email = models.EmailField(max_length=150, unique=True)
    cpf = models.CharField(max_length=11, unique=True)
    password_hash = models.CharField(max_length=255)
    is_teacher = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    verified_email = models.BooleanField(default=False)
    verification_code = models.CharField(max_length=6, blank=True, null=True)
    verification_sent_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        roles = ['Professor' if self.is_teacher else '', 'Aluno']
        return f'{self.full_name} - {" / ".join(filter(None, roles))}'


# 2 - Perfis adicionais
class Profile(models.Model):
    user = models.OneToOneField(User, primary_key=True, on_delete=models.CASCADE, related_name='profile')
    age = models.IntegerField(null=True, blank=True)
    school = models.CharField(max_length=150, null=True, blank=True)
    teaching_area = models.CharField(max_length=100, null=True, blank=True)
    disciplines = ArrayField(models.CharField(max_length=255), blank=True, null=True)
    experience_years = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'Perfil de {self.user.full_name}'


# 3 - Planos de acesso (mudar para integracao com a API do Stripe)
class Plan(models.Model):
    name = models.CharField(max_length=50)
    price_cents = models.IntegerField()
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name


# 4 - Pagamentos (mudar para integracao com a API do Stripe)
class Payment(models.Model):
    METHOD_CHOICES = (
        ('PIX', 'PIX'),
        ('card', 'Cartão'),
        ('boleto', 'Boleto'),
    )

    STATUS_CHOICES = (
        ('pending', 'Pendente'),
        ('confirmed', 'Confirmado'),
        ('failed', 'Falhou'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payments')
    plan = models.ForeignKey(Plan, on_delete=models.RESTRICT, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    method = models.CharField(max_length=20, choices=METHOD_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    reminder_count = models.IntegerField(default=0)

    class Meta:
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['plan']),
            models.Index(fields=['status']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f'Pagamento de {self.user.full_name} - {self.status}'

    @classmethod
    def get_payments_with_related(cls, user_id=None, status=None):
        """
        busca pagamentos com dados relacionados otimizados
        """
        queryset = cls.objects.select_related('user', 'plan')
        
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        if status:
            queryset = queryset.filter(status=status)
            
        return queryset

    @classmethod
    def get_user_payments_with_details(cls, user_id):
        """
        busca pagamentos de um usuário com todos os detalhes relacionados
        """
        return cls.objects.select_related(
            'user',
            'plan',
            'user__profile'  # pra acessanr o perfil do usuário
        ).filter(user_id=user_id)

    def save(self, *args, **kwargs):

        if not self.amount:
            self.amount = self.plan.price_cents / 100  
        super().save(*args, **kwargs)

    @property
    def amount_in_cents(self):
        """
        Propriedade para obter o valor em centavos
        """
        return int(self.amount * 100)

    @property
    def formatted_amount(self):
        """
        Propriedade para obter o valor formatado em reais
        """
        return f'R$ {self.amount:,.2f}'


# 5 - Turmas
class ClassModel(models.Model):
    STATUS_CHOICES = (
        ('active', 'Ativa'),
        ('inactive', 'Inativa'),
    )

    # Para criar uma turma, o usuário que a cria deve ser professor.
    professor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='classes')
    name = models.CharField(max_length=100)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


# 6 - Convites para turmas
class Invite(models.Model):
    class_invite = models.ForeignKey(ClassModel, on_delete=models.CASCADE, related_name='invites')
    code = models.CharField(max_length=32, unique=True)
    alias = models.CharField(max_length=100, blank=True, null=True)
    max_uses = models.IntegerField(null=True, blank=True)
    uses_count = models.IntegerField(default=0)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.code


# 7 - Associação turma pra aluno
class ClassStudent(models.Model):
    class_instance = models.ForeignKey(ClassModel, on_delete=models.CASCADE, related_name='class_students')
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='student_classes')
    enrolled_at = models.DateTimeField(auto_now_add=True)
    removed_at = models.DateTimeField(null=True, blank=True)
    removal_reason = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        unique_together = (('class_instance', 'student'),)
        indexes = [
            models.Index(fields=['class_instance']),
            models.Index(fields=['student']),
        ]

    def __str__(self):
        return f'{self.student.full_name} na turma {self.class_instance.name}'


# 8 - Atividades
class Activity(models.Model):
    STATUS_CHOICES = (
        ('draft', 'Rascunho'),
        ('open', 'Aberta'),
        ('closed', 'Fechada'),
    )

    professor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='activities')
    title = models.CharField(max_length=150)
    description = models.TextField(blank=True, null=True)
    max_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    due_date = models.DateTimeField(null=True, blank=True)
    notify_before_days = models.IntegerField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


# 9 - Associação atividade pra turma
class ActivityClass(models.Model):
    activity = models.ForeignKey(Activity, on_delete=models.CASCADE, related_name='activity_classes')
    class_instance = models.ForeignKey(ClassModel, on_delete=models.CASCADE, related_name='activity_classes')

    class Meta:
        unique_together = (('activity', 'class_instance'),)
        indexes = [
            models.Index(fields=['activity']),
            models.Index(fields=['class_instance']),
        ]

    def __str__(self):
        return f'Atividade {self.activity.title} na turma {self.class_instance.name}'


# 10 - Submissões de atividades
class Submission(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pendente'),
        ('late', 'Atrasada'),
        ('invalid_format', 'Formato Inválido'),
    )

    activity = models.ForeignKey(Activity, on_delete=models.CASCADE, related_name='submissions')
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='submissions')
    file_path = models.CharField(max_length=255, blank=True, null=True)
    mime_type = models.CharField(max_length=50, blank=True, null=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES)

    class Meta:
        indexes = [
            models.Index(fields=['activity']),
            models.Index(fields=['student']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f'Submissão de {self.student.full_name} para {self.activity.title}'


# 11 - Feedbacks
class Feedback(models.Model):
    submission = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name='feedbacks')
    professor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='feedbacks')
    score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    comment = models.TextField(blank=True, null=True)
    automatic = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['submission']),
            models.Index(fields=['professor']),
        ]

    def __str__(self):
        return f'Feedback para submissão {self.submission.id} por {self.professor.full_name}'