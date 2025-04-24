# serializers.py
from rest_framework import serializers
from django.contrib.auth.hashers import make_password
# Importar timezone para validações de data
from django.utils import timezone

from core.models import (
    User, Profile, Plan, Payment, Subscription, ClassModel,
    ClassStudent, Invite, Activity, ActivityClass, Submission, Feedback
)

# -----------------------------
# 1. SERIALIZERS DE USUÁRIO E PERFIL
# -----------------------------

class UserReadSerializer(serializers.ModelSerializer):
    """Serializer para representar dados do usuário na leitura."""
    profile = serializers.SerializerMethodField() # Incluir perfil na leitura

    class Meta:
        model = User
        fields = [
            'id', 'full_name', 'email', 'cpf', # Cuidado ao expor CPF, pode ser apenas para Admin
            'is_teacher', 'created_at', 'verified_email',
            'profile' # Adicionado profile aqui
        ]
        read_only_fields = ['id', 'created_at', 'verified_email']

    def get_profile(self, obj):
        # Inclui o perfil se existir
        profile = getattr(obj, 'profile', None)
        if profile:
            return ProfileSerializer(profile).data
        return None


class UserWriteSerializer(serializers.ModelSerializer):
    """Serializer para criar e atualizar dados básicos do usuário, incluindo senha."""
    password = serializers.CharField(write_only=True, required=False) # required=False permite atualizar sem mudar senha

    class Meta:
        model = User
        # CPF geralmente não é atualizável via API do usuário, remova se for o caso
        # is_teacher pode não ser atualizável pelo usuário comum, remova se for o caso
        fields = ['full_name', 'email', 'cpf', 'password', 'is_teacher']

    # Método create e update com set_password implementados aqui
    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password) # Usar set_password() do modelo Django
        user.save()
        Profile.objects.create(user=user) # Garantir que o perfil é criado junto
        return user

    def update(self, instance, validated_data):
        if 'password' in validated_data:
            instance.set_password(validated_data.pop('password')) # Usar set_password()
        # Atualizar outros campos
        return super().update(instance, validated_data)


class ProfileSerializer(serializers.ModelSerializer):
    """Serializer para o modelo Profile."""
    # Usa disciplines_list para entrada/saída de lista, o modelo converte para/de string
    disciplines_list = serializers.ListField(child=serializers.CharField(), required=False, allow_empty=True)

    class Meta:
        model = Profile
        # 'user' é o OneToOneField, geralmente definido pela View/ViewSet no contexto do usuário logado
        fields = ['age', 'school', 'teaching_area', 'disciplines_list', 'experience_years', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']

    # Sobrescrever update/create no serializer para chamar set_disciplines
    def create(self, validated_data):
        disciplines_list = validated_data.pop('disciplines_list', None)
        profile = Profile.objects.create(**validated_data)
        if disciplines_list is not None:
            profile.set_disciplines(disciplines_list)
            profile.save()
        return profile

    def update(self, instance, validated_data):
        disciplines_list = validated_data.pop('disciplines_list', None)
        # Chama o update padrão para os outros campos
        profile = super().update(instance, validated_data)
        # Lida com disciplines_list separadamente
        if disciplines_list is not None:
            profile.set_disciplines(disciplines_list)
            profile.save()
        return profile


class UserProfileUpdateSerializer(serializers.Serializer):
    """Serializer para validar a atualização conjunta de User e Profile no endpoint /me."""
    user = UserWriteSerializer(required=False)
    profile = ProfileSerializer(required=False)

    # A lógica de update será implementada na View/Action que usa este serializer


# --------------------------------
# 2. PLANOS E FINANCEIRO
# --------------------------------

class PlanSerializer(serializers.ModelSerializer):
    """Serializer para o modelo Plan."""
    class Meta:
        model = Plan
        fields = ['id', 'name', 'price_cents', 'description']
        read_only_fields = ['id']


class PaymentSerializer(serializers.ModelSerializer):
    """Serializer para o modelo Payment."""
    formatted_amount = serializers.ReadOnlyField() # Para exibir o valor formatado
    plan_name = serializers.ReadOnlyField(source='plan.name') # Nome do plano para leitura

    class Meta:
        model = Payment
        fields = ['id', 'user', 'plan', 'plan_name', 'amount', 'formatted_amount', 'method', 'status', 'created_at', 'confirmed_at', 'expires_at']
        # Campos gerenciados pelo backend/webhook, não pela requisição direta do usuário
        read_only_fields = ['id', 'user', 'plan', 'plan_name', 'amount', 'formatted_amount', 'status', 'created_at', 'confirmed_at', 'expires_at']


class SubscriptionSerializer(serializers.ModelSerializer):
    """Serializer para o modelo Subscription."""
    plan_name = serializers.ReadOnlyField(source='plan.name') # Nome do plano para leitura

    class Meta:
        model = Subscription
        fields = ['id', 'appmax_subscription_id', 'user', 'plan', 'plan_name', 'status', 'started_at', 'updated_at', 'cancelled_at', 'expires_at']
        # Campos gerenciados pelo backend/webhook/integração Appmax
        read_only_fields = ['id', 'appmax_subscription_id', 'user', 'plan', 'plan_name', 'status', 'started_at', 'updated_at', 'cancelled_at', 'expires_at']


class PaymentInitiateSerializer(serializers.Serializer):
    """Serializer para validar dados de entrada para iniciar pagamento/assinatura."""
    plan_id = serializers.IntegerField()
    method = serializers.ChoiceField(choices=Payment.METHOD_CHOICES)
    is_subscription = serializers.BooleanField(default=False)

    # Campos adicionais para pagamento com cartão (write_only por segurança)
    card_number = serializers.CharField(required=False, write_only=True)
    card_holder_name = serializers.CharField(required=False, write_only=True)
    card_expiry = serializers.CharField(required=False, write_only=True) # Formato MM/AA
    card_cvv = serializers.CharField(required=False, write_only=True)

    # Campos para endereço (opcional dependendo do método Appmax)
    address = serializers.CharField(required=False)
    city = serializers.CharField(required=False)
    state = serializers.CharField(required=False)
    postal_code = serializers.CharField(required=False)

    # TODO: Implementar método validate() para validações customizadas
    def validate(self, data):
        method = data.get('method')
        if method == 'card':
            required_card_fields = ['card_number', 'card_holder_name', 'card_expiry', 'card_cvv']
            for field in required_card_fields:
                if not data.get(field):
                    raise serializers.ValidationError({field: f"Campo '{field}' é obrigatório para pagamento com cartão."})
        # TODO: Validar formato de card_expiry (Regex).
        # TODO: Validar se plan_id existe (pode ser feito na view também, mas aqui centraliza).

        return data


# --------------------------------
# 3. TURMAS E ASSOCIADOS
# --------------------------------

class ClassModelSerializer(serializers.ModelSerializer):
    """Serializer para o modelo ClassModel."""
    professor_name = serializers.ReadOnlyField(source='professor.full_name') # Nome do professor para leitura
    students_count = serializers.SerializerMethodField() # Contagem de alunos ativos para leitura

    class Meta:
        model = ClassModel
        fields = ['id', 'professor', 'professor_name', 'name', 'status', 'created_at', 'students_count']
        # professor é definido no backend na criação
        read_only_fields = ['id', 'professor', 'professor_name', 'created_at', 'students_count']

    def get_students_count(self, obj):
        """Calcula o número de alunos ativos na turma."""
        return obj.class_students.filter(removed_at__isnull=True).count()


class InviteSerializer(serializers.ModelSerializer):
    """Serializer para o modelo Invite."""
    class_name = serializers.ReadOnlyField(source='class_invite.name') # Nome da turma para leitura

    class Meta:
        model = Invite
        fields = ['id', 'class_invite', 'class_name', 'code', 'alias', 'max_uses', 'uses_count', 'expires_at', 'created_at']
        # code e uses_count são gerados/gerenciados pelo backend
        read_only_fields = ['id', 'code', 'uses_count', 'created_at']
        # class_invite pode ser write_only na criação/update, se a view for aninhada

    # Implementar método validate() para validações customizadas
    def validate(self, data):
        max_uses = data.get('max_uses')
        expires_at = data.get('expires_at')

        if max_uses is not None and max_uses < 0:
             raise serializers.ValidationError({"max_uses": "Número máximo de usos não pode ser negativo."})

        # Validar expires_at no futuro
        if expires_at is not None and expires_at < timezone.now():
             raise serializers.ValidationError({"expires_at": "Data de expiração não pode ser no passado."})

        # TODO: Adicionar validação se class_invite existe e se o usuário é professor dela na criação/update
        return data


class ClassStudentSerializer(serializers.ModelSerializer):
    """Serializer para o modelo ClassStudent (associação Aluno-Turma)."""
    student_name = serializers.ReadOnlyField(source='student.full_name') # Nome do aluno para leitura
    student_email = serializers.ReadOnlyField(source='student.email') # Email do aluno para leitura
    class_name = serializers.ReadOnlyField(source='class_instance.name') # Nome da turma para leitura

    class Meta:
        model = ClassStudent
        fields = ['id', 'class_instance', 'class_name', 'student', 'student_name', 'student_email', 'enrolled_at', 'removed_at', 'removal_reason']
        # Estes campos são definidos na View/lógica de "entrar na turma" ou "remover aluno"
        read_only_fields = ['id', 'class_instance', 'class_name', 'student', 'student_name', 'student_email', 'enrolled_at', 'removed_at', 'removal_reason']


# --------------------------------
# 4. ATIVIDADES
# --------------------------------

class ActivitySerializer(serializers.ModelSerializer):
    """Serializer para o modelo Activity."""
    professor_name = serializers.ReadOnlyField(source='professor.full_name') # Nome do professor para leitura

    class Meta:
        model = Activity
        fields = ['id', 'professor', 'professor_name', 'title', 'description', 'max_score', 'due_date', 'notify_before_days', 'status', 'created_at']
        # professor é definido no backend na criação
        read_only_fields = ['id', 'professor', 'professor_name', 'created_at']

    # Implementar método validate() para validações customizadas
    def validate(self, data):
        max_score = data.get('max_score')
        due_date = data.get('due_date')
        status = data.get('status') # Status pode ser atualizado
        notify_before_days = data.get('notify_before_days')

        if max_score is not None and max_score < 0:
            raise serializers.ValidationError({"max_score": "Pontuação máxima não pode ser negativa."})

        # TODO: Implementar validação condicional para due_date
        # Ex: Se status está sendo DEFINIDO ou JÁ É 'open' E due_date é fornecido
        # (verificar se 'status' está em data ou self.instance existe e self.instance.status é 'open')
        is_opening = (status == 'open' and (self.instance is None or self.instance.status != 'open'))
        is_already_open = (self.instance is not None and self.instance.status == 'open' and status != 'closed') # Não está fechando

        if (is_opening or is_already_open) and due_date is not None and due_date < timezone.now():
             # Permitir data passada se estiver fechando ou já fechada
             if status != 'closed' and (self.instance is None or self.instance.status != 'closed'):
                 raise serializers.ValidationError({"due_date": "Data de entrega para atividade aberta não pode ser no passado."})
             # TODO: Adicionar flag extra no modelo/serializer se precisar de controle mais fino sobre datas passadas.


        if notify_before_days is not None and notify_before_days < 0:
             raise serializers.ValidationError({"notify_before_days": "Número de dias para notificar não pode ser negativo."})


        return data


class ActivityClassSerializer(serializers.ModelSerializer):
    """Serializer para o modelo ActivityClass (associação Atividade-Turma)."""
    activity_title = serializers.ReadOnlyField(source='activity.title') # Título da atividade para leitura
    class_name = serializers.ReadOnlyField(source='class_instance.name') # Nome da turma para leitura

    class Meta:
        model = ActivityClass
        fields = ['id', 'activity', 'activity_title', 'class_instance', 'class_name']
        # Estes campos são definidos na View/lógica de associação
        read_only_fields = ['id', 'activity_title', 'class_name']


# --------------------------------
# 5. SUBMISSÕES E FEEDBACK
# --------------------------------

class SubmissionSerializer(serializers.ModelSerializer):
    """Serializer para o modelo Submission."""
    student_name = serializers.ReadOnlyField(source='student.full_name') # Nome do aluno para leitura
    activity_title = serializers.ReadOnlyField(source='activity.title') # Título da atividade para leitura

    # Campo para receber o arquivo na criação/update. write_only=True.
    file = serializers.FileField(write_only=True, required=False)

    # Campo para retornar a URL pública do arquivo Cloudinary na leitura
    file_url = serializers.SerializerMethodField() # Adicionado campo de URL

    class Meta:
        model = Submission
        # Adicionado 'file_url' para leitura
        fields = ['id', 'activity', 'activity_title', 'student', 'student_name', 'file_path', 'mime_type', 'submitted_at', 'status', 'file', 'file_url']
        # Campos definidos na View/lógica de submissão
        read_only_fields = ['id', 'activity', 'activity_title', 'student', 'student_name', 'file_path', 'mime_type', 'submitted_at', 'file_url'] # file_url é calculado

    # Método para obter a URL do arquivo (se file_path contiver a URL completa)
    # Se file_path for apenas o public_id, construa a URL aqui usando a base do Cloudinary
    def get_file_url(self, obj):
        """Retorna a URL pública do arquivo submetido."""
        if obj.file_path:
            # TODO: >>> PONTO DE REVISÃO E IMPLEMENTAÇÃO: URL CLOUDINARY <<<
            # Se file_path já é a URL completa salva, retorne-o diretamente.
            # Se você salvou apenas o public_id, construa a URL usando sua base do Cloudinary.
            # Ex: return f"https://res.cloudinary.com/seu-cloud-name/image/upload/{obj.file_path}" # Se file_path é public_id
            # Ex: return cloudinary.utils.api_url(obj.file_path) # Usando SDK util (se file_path é public_id)
            return obj.file_path # Assumindo que file_path já é a URL completa

        return None

    # Implementar método validate() para validações customizadas
    def validate(self, data):
         # Exemplo: Validar status se ele for enviado na requisição (geralmente só pelo professor)
         if 'status' in data:
             valid_statuses = [choice[0] for choice in Submission.STATUS_CHOICES]
             if data['status'] not in valid_statuses:
                 raise serializers.ValidationError({"status": f"Status inválido. Escolhas válidas: {', '.join(valid_statuses)}"})

         # TODO: Adicionar validações na criação para garantir activity e student são setados na view.
         # TODO: Na criação, validar se um arquivo foi fornecido se a submissão exige um arquivo.

         return data


class FeedbackSerializer(serializers.ModelSerializer):
    """Serializer para o modelo Feedback."""
    professor_name = serializers.ReadOnlyField(source='professor.full_name') # Nome do professor para leitura

    class Meta:
        model = Feedback
        fields = ['id', 'submission', 'professor', 'professor_name', 'score', 'comment', 'automatic', 'created_at']
        # Campos definidos na View/lógica de feedback
        read_only_fields = ['id', 'submission', 'professor', 'professor_name', 'created_at']

    # Implementar método validate_score para validações customizadas no score
    # Usar self.initial_data para acessar dados não validados como submission_id na criação
    def validate_score(self, value):
        if value is not None: # Validações apenas se score for fornecido
            if value < 0:
                raise serializers.ValidationError("Pontuação não pode ser negativa.")

            # Obter submission_id do contexto ou dos dados iniciais (antes de validação completa)
            # Na criação, 'submission' estará em self.initial_data
            # Na atualização, 'submission' pode não estar em self.initial_data, mas self.instance tem a submission
            submission = self.instance.submission if self.instance else None
            if not submission:
                 # Se é criação, tentar obter a submission do initial_data
                 submission_id = self.initial_data.get('submission')
                 if submission_id:
                     try:
                         # Buscar a submission (e a atividade relacionada para otimizar)
                         submission = Submission.objects.select_related('activity').get(id=submission_id)
                     except Submission.DoesNotExist:
                         # A validação do campo 'submission' tratará este erro, apenas passamos
                         pass
                 else:
                     # Se nem na instância nem no initial_data, não podemos validar contra max_score
                     pass # Ou levantar um erro se submission é obrigatório

            # Validar contra max_score se submission foi encontrado e tem max_score
            if submission and submission.activity.max_score is not None:
                if value > submission.activity.max_score:
                     # TODO: >>> PONTO DE REVISÃO E IMPLEMENTAÇÃO: TRATAMENTO DE ERROS <<<
                    raise serializers.ValidationError(
                        f"Pontuação ({value}) não pode ser maior que a pontuação máxima da atividade ({submission.activity.max_score})."
                    )

        return value # Retorna o valor validado

    # TODO: Implementar método validate() para validações customizadas na criação
    # Ex: Validar que 'submission' existe e que o usuário logado é o professor da atividade associada.
    # Essa validação também é feita na View, mas pode ser redundante aqui.