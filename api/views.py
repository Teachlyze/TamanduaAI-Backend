# views.py
from django.shortcuts import get_object_or_404
# Importar timezone explicitamente
from django.utils import timezone
from django.db.models import Q
from django.contrib.auth.hashers import check_password
from rest_framework import viewsets, status, permissions, views, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer


# Importar para filtros, busca, ordenação e paginação
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.pagination import PageNumberPagination # Para paginação

# TODO: Importar biblioteca para Throttling
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle

# TODO: Importar SDK ou biblioteca para integração com Appmax
# import appmax_sdk

# TODO: Importar SDK ou biblioteca para integração com Cloudinary
# Certifique-se de ter as credenciais configuradas (settings.py)
# import cloudinary.uploader
# import cloudinary.api
# from cloudinary.utils import api_url

import uuid
import random
import string
from datetime import datetime, timedelta
import json
import logging


# Import dos modelos
from core.models import (
    User, Profile, Plan, Payment, Subscription, ClassModel,
    ClassStudent, Invite, Activity, ActivityClass, Submission, Feedback
)
# Import dos serializers
from .serializers import (
    UserReadSerializer, UserWriteSerializer, ProfileSerializer, UserProfileUpdateSerializer,
    PlanSerializer, PaymentSerializer, SubscriptionSerializer, PaymentInitiateSerializer,
    ClassModelSerializer, InviteSerializer, ClassStudentSerializer,
    ActivitySerializer, ActivityClassSerializer, SubmissionSerializer, FeedbackSerializer
)

# Configurando o logger
logger = logging.getLogger(__name__)

# -----------------------------
# PERMISSÕES PERSONALIZADAS (Manter e refinar)
# -----------------------------
class IsTeacher(permissions.BasePermission): pass
class IsClassTeacher(permissions.BasePermission): pass
class IsActivityTeacher(permissions.BasePermission): pass
class IsOwner(permissions.BasePermission): pass
class IsClassMember(permissions.BasePermission): pass
# TODO: Criar permissão IsTeacherAndPremiumActive
# TODO: Refinar as permissões para Submissions/Feedbacks (Aluno dono vs Professor da atividade)

# --------------------------------
# BASE VIEWSET (Com filtros, busca, ordenação e paginação padrão)
# --------------------------------
class BaseModelViewSet(viewsets.ModelViewSet):
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    pagination_class = PageNumberPagination # Configuração de paginação padrão (ex: 10 items por página)

    # Defina search_fields e ordering_fields nos Viewsets específicos
    # search_fields = []
    # ordering_fields = []


# --------------------------------
# 1. AUTENTICAÇÃO (APIViews customizadas)
# --------------------------------

class AuthRegisterView(views.APIView):
    """Endpoint para registrar um novo usuário."""
    permission_classes = [permissions.AllowAny]
    # TODO: Implementar Throttling (limitação de taxa)
    # throttling_classes = [AnonRateThrottle, UserRateThrottle]

    def post(self, request):
        serializer = UserWriteSerializer(data=request.data)
        if serializer.is_valid():
            # .save() no UserWriteSerializer chama set_password() e cria o Profile
            user = serializer.save()

            # TODO: Gerar código de verificação e enviar e-mail (INTEGRAÇÃO EXTERNA - EMAIL)
            verification_code = ''.join(random.choices(string.digits, k=6))
            user.verification_code = verification_code
            user.verification_sent_at = timezone.now()
            user.save()
            logger.info(f"Código de verificação para {user.email}: {verification_code}")
            # Ex: send_verification_email(user.email, verification_code)

            # Retornar UserReadSerializer para não expor senha, etc.
            return Response({
                'message': 'Usuário registrado com sucesso! Verifique seu e-mail para ativar sua conta.',
                'user': UserReadSerializer(user).data
            }, status=status.HTTP_201_CREATED)
        # TODO: >>> PONTO DE REVISÃO E IMPLEMENTAÇÃO: TRATAMENTO DE ERROS <<<
        # Retornar erros de validação do serializer
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AuthLoginView(views.APIView):
    """Endpoint para login e obtenção de tokens JWT."""
    permission_classes = [permissions.AllowAny]
    # TODO: Implementar Throttling (limitação de taxa)
    # throttling_classes = [AnonRateThrottle, UserRateThrottle]

    def post(self, request):
        serializer = TokenObtainPairSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except Exception as e:
            # TODO: >>> PONTO DE REVISÃO E IMPLEMENTAÇÃO: TRATAMENTO DE ERROS <<<
            # Captura exceções do serializer (ex: usuário não encontrado, senha inválida)
            logger.warning(f"Tentativa de login falhou: {e}")
            return Response({'detail': 'Credenciais inválidas.'}, status=status.HTTP_401_UNAUTHORIZED)

        user = serializer.user

        # TODO: Verificar verified_email aqui antes de retornar tokens
        # Se a conta não for verificada, não permita o login.
        if not user.verified_email:
             return Response({
                 'error': 'Conta não verificada. Por favor, verifique seu e-mail.'
             }, status=status.HTTP_401_UNAUTHORIZED)

        # Retornar tokens e dados do usuário
        return Response({
            'refresh': serializer.validated_data['refresh'],
            'access': serializer.validated_data['access'],
            'user': UserReadSerializer(user).data
        })


class AuthLogoutView(views.APIView):
    """Endpoint para fazer logout (invalidar token de refresh)."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        # Blacklist o token de refresh. Requer 'rest_framework_simplejwt.token_blacklist'.
        try:
            refresh_token = request.data["refresh"]
            token = RefreshToken(refresh_token)
            token.blacklist()
            # TODO: Se estiver usando uma blocklist separada para tokens de acesso, invalidar o atual também.
        except Exception as e:
            logger.error(f"Erro ao fazer logout: {e}", exc_info=True)
            # TODO: >>> PONTO DE REVISÃO E IMPLEMENTAÇÃO: TRATAMENTO DE ERROS <<<
            # Retorna 400/401 se o token já for inválido, ou 500 em caso de erro interno
            return Response({"detail": "Token inválido ou expirado."}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            'message': 'Logout realizado com sucesso'
        }, status=status.HTTP_200_OK)


# TODO: Adicionar APIViews para:
# - RequestVerificationView: Solicitar novo código de verificação.
# - VerifyEmailView: Verificar email com código.
# - ResetPasswordRequestView: Solicitar reset de senha (envia link/código).
# - ResetPasswordConfirmView: Confirmar reset de senha com código e nova senha.
# Note: Lógica similar às implementadas na estrutura Claude.

# --------------------------------
# 2. USER e PROFILE (Viewset com @action para /me)
# --------------------------------

class UserViewSet(BaseModelViewSet): # Herda de BaseModelViewSet para filtros/paginação
    """Viewset para listar (Admin), obter detalhes e gerenciar o usuário logado (/me)."""
    queryset = User.objects.all() # Queryset base para listar/detalhe (Admin)

    # TODO: Definir search_fields e ordering_fields se a lista geral for relevante (Admin)
    search_fields = ['full_name', 'email', 'cpf'] # Cuidado ao buscar por CPF, apenas Admin
    ordering_fields = ['created_at', 'full_name']

    def get_permissions(self):
         """Define permissões baseadas na ação."""
         # TODO: >>> PONTO DE REVISÃO E IMPLEMENTAÇÃO: PERMISSÕES DE USUÁRIO <<<
         # - list: Apenas IsAdminUser pode listar todos.
         # - retrieve: Apenas IsAdminUser PODE ver qualquer um. Usuário comum SÓ PODE ver a si mesmo (gerenciado pela action 'me').
         # - create: Desabilitar (criado via registro).
         # - update/partial_update/destroy: Desabilitar (gerenciado pela action 'me' para o próprio, Admin pode precisar de outro endpoint).
         if self.action == 'list':
             self.permission_classes = [permissions.IsAdminUser]
         elif self.action in ['retrieve']:
             # Permite Admin ver qualquer um, ou usuário comum ver a si mesmo (redundante com /me/)
             self.permission_classes = [permissions.IsAdminUser | (permissions.IsAuthenticated & IsOwner)] # Exemplo combinando
         elif self.action in ['create', 'update', 'partial_update', 'destroy']:
             self.permission_classes = [permissions.IsAdminUser] # Ações desabilitadas para usuários comuns, apenas admin
         elif self.action == 'me':
              self.permission_classes = [permissions.IsAuthenticated] # Apenas autenticado pode acessar /me/
         return super().get_permissions()

    def get_serializer_class(self):
        """Usa serializers diferentes para leitura e escrita."""
        if self.action in ['create', 'update', 'partial_update']:
            return UserWriteSerializer
        if self.action == 'me' and self.request.method in ['PUT', 'PATCH']:
             return UserProfileUpdateSerializer # Serializer especial para /me/ update
        return UserReadSerializer # Para leitura (list, retrieve, me GET)


    @action(detail=False, methods=['get', 'put', 'patch'], permission_classes=[permissions.IsAuthenticated])
    def me(self, request):
        """Endpoint para obter ou atualizar o usuário autenticado e seu perfil."""
        user = request.user

        if request.method == 'GET':
            # UserReadSerializer já inclui o perfil
            serializer = self.get_serializer(user) # Usa UserReadSerializer
            return Response(serializer.data)

        # Para PUT e PATCH, usar o UserProfileUpdateSerializer
        serializer = self.get_serializer(user, data=request.data, partial=request.method == 'PATCH')

        # TODO: >>> PONTO DE REVISÃO E IMPLEMENTAÇÃO: TRATAMENTO DE ERROS <<<
        # Lidar com erros de validação do UserProfileUpdateSerializer
        if serializer.is_valid():
            # A lógica de atualização conjunta de User e Profile está aqui
            user_data = serializer.validated_data.get('user', {})
            profile_data = serializer.validated_data.get('profile', {})

            # Atualizar User data (UserWriteSerializer já tratou a senha no save)
            user_serializer = UserWriteSerializer(user, data=user_data, partial=request.method == 'PATCH')
            if user_serializer.is_valid():
                 user_serializer.save() # Chama UserWriteSerializer.update() que usa set_password()
            else:
                 # TODO: >>> PONTO DE REVISÃO E IMPLEMENTAÇÃO: TRATAMENTO DE ERROS <<<
                 # Retornar erros específicos da sub-validação de User
                 return Response({"user_errors": user_serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

            # Atualizar Profile data (ProfileSerializer já tratou disciplines_list no save/update)
            profile = user.profile
            profile_serializer = ProfileSerializer(profile, data=profile_data, partial=request.method == 'PATCH')
            if profile_serializer.is_valid():
                 profile_serializer.save() # Chama ProfileSerializer.update() que usa set_disciplines()
            else:
                 # TODO: >>> PONTO DE REVISÃO E IMPLEMENTAÇÃO: TRATAMENTO DE ERROS <<<
                 # Retornar erros específicos da sub-validação de Profile
                 return Response({"profile_errors": profile_serializer.errors}, status=status.HTTP_400_BAD_REQUEST)


            # Retornar dados atualizados (usando UserReadSerializer)
            return Response(UserReadSerializer(user).data)

        # Erros de validação do serializer principal
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# --------------------------------
# 3. PLANOS (ReadOnlyModelViewSet)
# --------------------------------

class PlanViewSet(BaseModelViewSet): # Herda de BaseModelViewSet
    """Viewset para listar planos."""
    queryset = Plan.objects.all()
    serializer_class = PlanSerializer
    permission_classes = [permissions.AllowAny] # Planos geralmente são públicos

    # TODO: Definir search_fields e ordering_fields
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'price_cents']

    # TODO: >>> PONTO DE REVISÃO E IMPLEMENTAÇÃO: PERMISSÕES DE PLANO <<<
    # Permitir create/update/destroy apenas para AdminUser.
    # def get_permissions(self): ...


# --------------------------------
# 4. PAGAMENTOS e ASSINATURAS (APIViews para fluxos complexos, ViewSets para Listar/Detalhe e @actions)
# --------------------------------
# ViewSets para aproveitar a infraestrutura de routers e permissions, com actions para /me/... endpoints

class PaymentViewSet(BaseModelViewSet): # Herda de BaseModelViewSet
    """ViewSet para listar (Admin), obter detalhes (Dono/Admin) e listar pagamentos do usuário logado."""
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer

    # TODO: Definir search_fields e ordering_fields
    search_fields = ['method', 'status']
    ordering_fields = ['created_at', 'amount']

    def get_permissions(self):
         """Define permissões baseadas na ação."""
         # TODO: >>> PONTO DE REVISÃO E IMPLEMENTAÇÃO: PERMISSÕES DE PAGAMENTO <<<
         # - list: Apenas IsAdminUser.
         # - retrieve: IsAdminUser ou IsOwner.
         # - my_payments (@action): IsAuthenticated.
         # - create/update/destroy: Desabilitadas (criado via initiate, atualizado via webhook).
         if self.action == 'list':
             self.permission_classes = [permissions.IsAdminUser]
         elif self.action in ['retrieve']:
             self.permission_classes = [permissions.IsAuthenticated, IsOwner | permissions.IsAdminUser]
         elif self.action == 'my_payments':
              self.permission_classes = [permissions.IsAuthenticated]
         # Desabilitar outras ações:
         # elif self.action in ['create', 'update', 'partial_update', 'destroy']: ...
         return super().get_permissions()

    # TODO: Implementar get_queryset para filtrar lista para admins ou seletivamente
    # Ex: se não for admin, retornar Payment.objects.none().

    # --- Actions centralizadas ---
    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def my_payments(self, request):
        """Lista os pagamentos do usuário autenticado (/users/me/payments/)."""
        # Queryset já filtrado pelo usuário logado
        queryset = Payment.objects.filter(user=request.user).order_by('-created_at')
        # Usa paginação e filtros/busca padrão de BaseModelViewSet se configurados
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class SubscriptionViewSet(BaseModelViewSet): # Herda de BaseModelViewSet
    """ViewSet para listar (Admin), obter detalhes (Dono/Admin) e gerenciar assinatura do usuário logado."""
    queryset = Subscription.objects.all()
    serializer_class = SubscriptionSerializer

    # TODO: Definir search_fields e ordering_fields
    search_fields = ['appmax_subscription_id', 'status']
    ordering_fields = ['started_at', 'status']

    def get_permissions(self):
         """Define permissões baseadas na ação."""
         # TODO: >>> PONTO DE REVISÃO E IMPLEMENTAÇÃO: PERMISSÕES DE ASSINATURA <<<
         # - list: Apenas IsAdminUser.
         # - retrieve: IsAdminUser ou IsOwner.
         # - my_subscription (@action): IsAuthenticated.
         # - cancel (@action): IsAuthenticated.
         # - create/update/destroy: Desabilitadas (criado via initiate, atualizado via webhook/cancel endpoint).
         if self.action == 'list':
             self.permission_classes = [permissions.IsAdminUser]
         elif self.action in ['retrieve']:
             self.permission_classes = [permissions.IsAuthenticated, IsOwner | permissions.IsAdminUser]
         elif self.action in ['my_subscription', 'cancel']:
             self.permission_classes = [permissions.IsAuthenticated]
         # Desabilitar outras ações:
         # elif self.action in ['create', 'update', 'partial_update', 'destroy']: ...
         return super().get_permissions()

    # TODO: Implementar get_queryset para filtrar lista para admins ou seletivamente
    # Ex: se não for admin, retornar Subscription.objects.none().

    # --- Actions centralizadas ---
    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAuthenticated], url_path='me')
    def my_subscription(self, request):
        """Obtém detalhes da assinatura ativa do usuário autenticado (/users/me/subscription/)."""
        # Busca a assinatura do usuário logado com status relevante
        # TODO: Definir exatamente quais status representam uma assinatura 'ativa' para fins de acesso premium
        subscription = get_object_or_404(
            Subscription,
            user=request.user,
            status__in=['active', 'pending', 'past_due'] # Inclui status que podem requerer atenção do usuário
        )
        serializer = self.get_serializer(subscription) # Usa SubscriptionSerializer
        return Response(serializer.data)

    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAuthenticated], url_path='cancel')
    def cancel(self, request):
        """Cancela a assinatura ativa do usuário (/users/me/subscription/cancel/)."""
        try:
            # Encontra a assinatura ativa ou pendente/atrasada do usuário logado
            subscription = Subscription.objects.get(
                user=request.user,
                status__in=['active', 'pending', 'past_due'] # Status que permitem cancelamento pelo usuário
            )
        except Subscription.DoesNotExist:
            # TODO: >>> PONTO DE REVISÃO E IMPLEMENTAÇÃO: TRATAMENTO DE ERROS <<<
            # Retornar 404 Not Found se não houver assinatura cancelável.
            return Response({
                'error': 'Assinatura ativa não encontrada ou não cancelável neste momento.'
            }, status=status.HTTP_404_NOT_FOUND)

        # TODO: >>> PONTO DE REVISÃO E IMPLEMENTAÇÃO: CANCELAR NA APPMAX <<<
        # Chamar a API da Appmax para solicitar o cancelamento da assinatura usando subscription.appmax_subscription_id.
        # Ex: appmax_sdk.cancel_subscription(subscription.appmax_subscription_id)

        # TODO: Processar o resultado da Appmax. O ideal é esperar o webhook de 'subscription_update' com status 'cancelled'
        # para atualizar o status localmente, mas você pode marcar localmente como "cancelamento pendente" imediatamente.
        # Por simplicidade neste esboço, atualizamos localmente. O webhook confirmará.
        # if appmax_result.success: # Verificar sucesso da API Appmax
        subscription.status = 'cancelled'
        subscription.cancelled_at = timezone.now()
        subscription.save()
        # TODO: Lógica adicional após cancelamento (ex: remover acesso premium imediatamente, enviar e-mail de confirmação)

        return Response({
            'message': 'Solicitação de cancelamento de assinatura processada. O status final será confirmado em breve.'
        }, status=status.HTTP_200_OK) # Status 200 OK para sucesso


# APIViews para fluxos complexos (fora dos ViewSets padrão)
# PaymentInitiateView e AppmaxWebhookView permanecem como APIViews separadas

class PaymentInitiateView(views.APIView):
    # ... (mantida como no código anterior, com TODOs e validação do serializer)
    """Inicia um novo pagamento ou assinatura via Appmax."""
    permission_classes = [permissions.IsAuthenticated]
    # TODO: Implementar Throttling
    # throttling_classes = [...]

    def post(self, request):
        # Lógica da PaymentInitiateView como no código anterior
        # ... (incluindo serialização, validação, busca de plano, integração Appmax, criação local de Payment/Subscription)
        serializer = PaymentInitiateSerializer(data=request.data)
        if serializer.is_valid():
            plan_id = serializer.validated_data['plan_id']
            method = serializer.validated_data['method']
            is_subscription = serializer.validated_data['is_subscription']
            # ... outros dados ...

            try:
                plan = Plan.objects.get(id=plan_id)
            except Plan.DoesNotExist:
                 return Response({'error': 'Plano não encontrado'}, status=status.HTTP_404_NOT_FOUND)

            if is_subscription and Subscription.objects.filter(user=request.user, plan=plan, status='active').exists():
                 return Response({'error': 'Você já possui uma assinatura ativa para este plano.'}, status=status.HTTP_400_BAD_REQUEST)

            # TODO: >>> PONTO DE REVISÃO E IMPLEMENTAÇÃO: INTEGRAÇÃO APPMAX INICIAR PAGAMENTO/ASSINATURA <<<
            # Chamar a API da Appmax aqui.
            # Exemplo BÁSICO (SUBSTITUIR):
            try:
                appmax_response_data = {
                     'success': True,
                     'appmax_transaction_id': f"appmax_txn_{uuid.uuid4().hex[:10]}",
                     'appmax_subscription_id': f"appmax_sub_{uuid.uuid4().hex[:10]}" if is_subscription else None,
                     'status': 'pending',
                     'checkout_url': 'https://appmax.com.br/checkout/fake_id',
                }
                # appmax_response_data = appmax_sdk.create_transaction(...) # Chamada real

                if not appmax_response_data.get('success'):
                     logger.error(f"Falha na API Appmax ao iniciar pagamento para user {request.user.id}: {appmax_response_data.get('error_details')}")
                     return Response({'error': 'Falha ao iniciar pagamento na Appmax', 'details': appmax_response_data.get('error_details', 'Erro desconhecido')}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            except Exception as e:
                 logger.error(f"Exceção ao chamar API Appmax iniciar pagamento para user {request.user.id}: {e}", exc_info=True)
                 return Response({'error': 'Erro interno ao comunicar com a Appmax.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            # TODO: Criar registro local no BD *após* a Appmax aceitar a requisição inicial
            # Lembre de salvar o appmax_transaction_id no Payment
            payment = Payment.objects.create(
                user=request.user,
                plan=plan,
                amount=plan.price_cents / 100,
                method=method,
                status='pending',
                # appmax_transaction_id=appmax_response_data['appmax_transaction_id'], # Adicionar campo no modelo Payment
            )

            subscription = None
            if is_subscription:
                 # TODO: Criar Subscription local e salvar appmax_subscription_id
                 subscription = Subscription.objects.create(
                     user=request.user,
                     plan=plan,
                     appmax_subscription_id=appmax_response_data['appmax_subscription_id'],
                     status='pending',
                     started_at=timezone.now(),
                 )
                 # Ex: payment.subscription = subscription; payment.save() # Vincular Payment à Subscription


            response_data = {
                'message': 'Processamento de pagamento/assinatura iniciado.',
                'payment_id': payment.id,
                'appmax_data': appmax_response_data # Retornar dados da Appmax
            }
            if subscription:
                response_data['subscription_id'] = subscription.id

            return Response(response_data, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AppmaxWebhookView(views.APIView):
    # ... (mantida como no código anterior, com TODOs e lógica esboçada para eventos)
    """Recebe e processa webhooks da Appmax para atualizar status de pagamentos/assinaturas."""
    permission_classes = [permissions.AllowAny]
    # TODO: Implementar Throttling
    # throttling_classes = [...]

    def post(self, request):
        # TODO: >>> PONTO DE REVISÃO E IMPLEMENTAÇÃO: VERIFICAÇÃO DE AUTENTICIDADE DO WEBHOOK (ESSENCIAL!) <<<
        # Verificar assinatura HMAC.

        try:
            data = json.loads(request.body)
            event_type = data.get('event')
            appmax_transaction_id = data.get('transaction_id')
            appmax_subscription_id = data.get('subscription_id')
            appmax_status = data.get('status')
            # TODO: Extrair outros dados cruciais do payload

            logger.info(f"Webhook Appmax recebido: Evento={event_type}, Transaction ID Appmax={appmax_transaction_id}, Subscription ID Appmax={appmax_subscription_id}, Status Appmax={appmax_status}")

            # TODO: >>> PONTO DE REVISÃO E IMPLEMENTAÇÃO: PROCESSAR DIFERENTES EVENTOS E PAYLOADS <<<
            # Encontrar modelos locais (Payment/Subscription) usando IDs da Appmax.
            # Atualizar status e dados nos modelos locais.
            # Lidar com criação de novos Payments para cobranças recorrentes.
            # Implementar _map_appmax_status e _map_appmax_subscription_status completos.
            # Adicionar lógica para conceder/remover acesso premium.

            # Exemplo BÁSICO de fluxo (substituir pela lógica real para cada event_type):
            if event_type == 'payment_update':
                # Encontrar Payment local usando appmax_transaction_id
                # Atualizar status e confirmed_at
                # Se for o primeiro pagamento de assinatura, ativar Subscription
                 pass # Implemente a lógica real

            elif event_type == 'subscription_update':
                # Encontrar Subscription local usando appmax_subscription_id
                # Atualizar status (cancelled, expired, past_due)
                # Lógica para remover acesso premium se status for cancelado/expirado
                 pass # Implemente a lógica real

            elif event_type in ['charge_success', 'charge_failed']:
                 # Encontrar Subscription local usando appmax_subscription_id
                 # Criar NOVO Payment para esta cobrança recorrente, salvando transaction_id e vinculando à Subscription
                 # Atualizar status da Subscription se necessário (ex: 'active' se sucesso, 'past_due' se falha)
                 pass # Implemente a lógica real

            # TODO: Lidar com outros eventos (refund, etc.)

            return Response({'status': 'success'}) # Appmax espera 200 OK

        except json.JSONDecodeError:
            logger.error("Erro ao decodificar JSON do webhook Appmax.")
            return Response({'status': 'error', 'message': 'Payload inválido'}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Erro inesperado processando webhook Appmax: {e}", exc_info=True)
            return Response({'status': 'error', 'message': 'Erro interno no servidor'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # TODO: Mapear status da Appmax para o seu modelo (COMPLETAR)
    def _map_appmax_status(self, appmax_status):
        # ... (implementação como no código anterior)
        status_map = {'approved': 'confirmed', 'pending': 'pending', 'processing': 'pending', 'rejected': 'failed', 'refunded': 'failed', 'chargeback': 'failed',}
        return status_map.get(appmax_status, 'pending')

    def _map_appmax_subscription_status(self, appmax_status):
        # ... (implementação como no código anterior)
        status_map = {'active': 'active', 'cancelled': 'cancelled', 'past_due': 'past_due', 'expired': 'expired', 'pending_payment': 'pending', 'trialing': 'active',}
        return status_map.get(appmax_status, 'pending')


# UserPaymentsView e UserSubscriptionView foram movidas para @actions nos ViewSets correspondentes.
# ClassStudentsView e RemoveStudentView serão movidas para @actions em ClassModelViewSet.

# --------------------------------
# 5. TURMAS, ALUNOS E CONVITES (ViewSets com actions customizadas)
# --------------------------------

class ClassModelViewSet(BaseModelViewSet): # Herda de BaseModelViewSet
    """ViewSet para operações CRUD em Turmas e gerenciar alunos/turmas do usuário logado."""
    queryset = ClassModel.objects.all()
    serializer_class = ClassModelSerializer

    # TODO: Definir search_fields e ordering_fields
    search_fields = ['name', 'professor__full_name']
    ordering_fields = ['created_at', 'name']

    def get_permissions(self):
         """Define permissões baseadas na ação."""
         # TODO: >>> PONTO DE REVISÃO E IMPLEMENTAÇÃO: PERMISSÕES DE TURMA <<<
         # - create: IsTeacher (e talvez IsTeacherAndPremiumActive).
         # - list: Decidir quem pode listar o quê (filtrado no get_queryset).
         # - retrieve: IsClassMember (Professor ou Aluno da turma) OU Admin.
         # - update/partial_update/destroy: IsClassTeacher.
         # - my_classes (@action): IsAuthenticated.
         # - students (@action aninhada): IsAuthenticated, IsClassMember.
         # - remove_student (@action aninhada): IsAuthenticated, IsClassTeacher.
         if self.action == 'create':
             self.permission_classes = [permissions.IsAuthenticated, IsTeacher] # TODO: Add IsTeacherAndPremiumActive
         elif self.action in ['update', 'partial_update', 'destroy']:
             self.permission_classes = [permissions.IsAuthenticated, IsClassTeacher]
         elif self.action in ['retrieve']:
             self.permission_classes = [permissions.IsAuthenticated, IsClassMember | permissions.IsAdminUser] # Exemplo: admin também pode ver
         elif self.action == 'my_classes':
              self.permission_classes = [permissions.IsAuthenticated]
         # Permissões para actions aninhadas (students, remove_student) definidas diretamente nelas
         # Permissão para list action get_queryset cuidará da filtragem, permissão IsAuthenticated ou AllowAny na classe

         return super().get_permissions()

    def get_queryset(self):
        """Filtra queryset baseado no usuário para a lista geral."""
        user = self.request.user

        if self.action == 'list':
            # TODO: >>> PONTO DE REVISÃO E IMPLEMENTAÇÃO: FILTRAGEM DA LISTA GERAL DE TURMAS <<<
            # O que /api/classes/list deve retornar?
            # - Todas as turmas (para admin, com IsAdminUser permission)
            # - Apenas as turmas do usuário (professor/aluno)?
            # - Apenas turmas "públicas"?
            # - Nenhuma?
            if user.is_authenticated:
                 # Exemplo: Retorna apenas as turmas do usuário logado (similar a UserClassesView anterior)
                 return ClassModel.objects.filter(
                     Q(professor=user) |
                     Q(class_students__student=user, class_students__removed_at__isnull=True)
                 ).distinct()
            else:
                 # Exemplo: Não autenticado não vê a lista geral
                 return ClassModel.objects.none()

        # Para actions de detalhe, update, destroy, e actions customizadas que operam em uma turma específica (e.g. students, remove_student),
        # o get_object usa o queryset base e as permissões baseadas em objeto farão a verificação.
        return super().get_queryset() # Queryset base para retrieve, update, destroy etc.


    def perform_create(self, serializer):
        """Define o professor logado na criação da turma."""
        # A permissão IsTeacher (e IsTeacherAndPremiumActive) já garantiu que é um professor elegível
        # TODO: >>> PONTO DE REVISÃO E IMPLEMENTAÇÃO: ACESSO PREMIUM (CRIAR TURMA) <<<
        # A permissão IsTeacherAndPremiumActive deve ser verificada ANTES de perform_create.
        serializer.save(professor=self.request.user, status='active')

    # --- Actions centralizadas ---
    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAuthenticated], url_path='me')
    def my_classes(self, request):
        """Lista as turmas onde o usuário autenticado é professor ou aluno (/users/me/classes/)."""
        user = request.user
        # Busca turmas onde o usuário é professor OU aluno ativo
        queryset = ClassModel.objects.filter(
            Q(professor=user) |
            Q(class_students__student=user, class_students__removed_at__isnull=True)
        ).distinct().select_related('professor').prefetch_related('class_students') # Otimizações de busca

        # Usa paginação e filtros/busca padrão de BaseModelViewSet
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True) # Serializer da ClassModel
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    # TODO: >>> PONTO DE REVISÃO E IMPLEMENTAÇÃO: CENTRALIZAR LISTA DE ALUNOS <<<
    # Transformar ClassStudentsView em uma @action aninhada
    # @action(detail=True, methods=['get'], serializer_class=ClassStudentSerializer, permission_classes=[permissions.IsAuthenticated, IsClassMember])
    # def students(self, request, pk=None): # pk é o ID da turma
    #     class_obj = self.get_object() # Obtém a turma (pk)
    #     # check_object_permissions para garantir permissão nesta turma (feita pela permission_classes)
    #     queryset = ClassStudent.objects.filter(class_instance=class_obj, removed_at__isnull=True).select_related('student')
    #     # Usa paginação e filtros/busca
    #     page = self.paginate_queryset(queryset)
    #     if page is not None:
    #         serializer = self.get_serializer(page, many=True) # Usa ClassStudentSerializer
    #         return self.get_paginated_response(serializer.data)
    #     serializer = self.get_serializer(queryset, many=True)
    #     return Response(serializer.data)


    # TODO: >>> PONTO DE REVISÃO E IMPLEMENTAÇÃO: CENTRALIZAR REMOVER ALUNO <<<
    # Transformar RemoveStudentView em uma @action aninhada
    # @action(detail=True, methods=['delete'], permission_classes=[permissions.IsAuthenticated, IsClassTeacher])
    # def remove_student(self, request, pk=None): # pk é o ID da turma
    #     class_obj = self.get_object() # Obtém a turma (pk)
    #     student_id = request.data.get('student_id') # Obter o ID do aluno do payload
    #     # check_object_permissions para garantir permissão (feita pela permission_classes)

    #     # Busca a associação ClassStudent ativa
    #     try:
    #         enrollment = ClassStudent.objects.get(
    #             class_instance=class_obj,
    #             student_id=student_id,
    #             removed_at__isnull=True
    #         )
    #     except ClassStudent.DoesNotExist:
    #         return Response({'error': 'Aluno não encontrado nesta turma ou já removido.'}, status=status.HTTP_404_NOT_FOUND)

    #     # Marca como removido
    #     reason = request.data.get('reason', 'Removido pelo professor')
    #     enrollment.removed_at = timezone.now()
    #     enrollment.removal_reason = reason
    #     enrollment.save()

    #     return Response({
    #         'message': f'Aluno {enrollment.student.full_name} removido da turma {class_obj.name}.'
    #     }, status=status.HTTP_200_OK)


class InviteViewSet(BaseModelViewSet): # Herda de BaseModelViewSet
    """ViewSet para gerenciar Convites e a ação de consumo."""
    queryset = Invite.objects.all()
    serializer_class = InviteSerializer
    lookup_field = 'code' # Define que o detalhe e actions detalhadas usam o campo 'code' na URL

    # TODO: Definir search_fields e ordering_fields
    search_fields = ['code', 'alias']
    ordering_fields = ['created_at', 'expires_at']

    def get_permissions(self):
        """Define permissões baseadas na ação."""
        # TODO: >>> PONTO DE REVISÃO E IMPLEMENTAÇÃO: PERMISSÕES DE CONVITE <<<
        # - create/update/destroy/list/retrieve: Apenas Professor (da turma associada).
        # - consume (@action): Apenas Aluno (autenticado), e a lógica interna valida.
        if self.action == 'consume':
             self.permission_classes = [permissions.IsAuthenticated, ~IsTeacher] # Apenas aluno autenticado pode consumir
        elif self.action in ['create', 'update', 'partial_update', 'destroy', 'list', 'retrieve']:
             self.permission_classes = [permissions.IsAuthenticated, IsTeacher] # Apenas professor (filtra no get_queryset)

        return super().get_permissions()

    def get_queryset(self):
        """Filtra queryset para listar/detalhe apenas convites das turmas do professor logado."""
        user = self.request.user
        if user.is_teacher:
            # Professor só vê os convites das SUAS turmas
            return Invite.objects.filter(class_invite__professor=user).select_related('class_invite')
        # Alunos não listam convites gerais ou vêem detalhes por ID/code aqui
        return Invite.objects.none()


    def perform_create(self, serializer):
        """Define a turma e gera o código antes de salvar o convite."""
        # A permissão IsTeacher e o get_queryset já garantiram que é um professor.
        # A turma (class_invite) deve vir do payload (class_invite_id).
        class_invite_id = serializer.validated_data.get('class_invite')

        if not class_invite_id:
             # TODO: >>> PONTO DE REVISÃO E IMPLEMENTAÇÃO: TRATAMENTO DE ERROS <<<
             # Se class_invite_id não foi fornecido no payload
             raise serializers.ValidationError({"class_invite": "ID da turma é obrigatório para criar um convite."})

        class_obj = get_object_or_404(ClassModel, id=class_invite_id)

        # Verificar se o usuário logado é o professor da turma antes de criar o convite para ela
        if class_obj.professor != self.request.user:
             # TODO: >>> PONTO DE REVISÃO E IMPLEMENTAÇÃO: TRATAMENTO DE ERROS <<<
             raise permissions.PermissionDenied("Você não é o professor desta turma.")

        serializer.validated_data['class_invite'] = class_obj # Define o objeto turma no validated_data

        # Gerar código único para o convite antes de salvar
        # TODO: Garantir unicidade do código de forma robusta (ex: loop try/except ou usar um pacote)
        code = uuid.uuid4().hex[:10]
        serializer.save(code=code)


    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated, ~IsTeacher], url_path='consume')
    def consume(self, request, code=None): # Usa 'code' como argumento vindo da URL por causa do lookup_field
        """Endpoint para um aluno usar um código de convite para entrar em uma turma."""
        # get_object() usará o lookup_field 'code' para buscar o convite
        invite = self.get_object()

        user = request.user # Já garantido que é autenticado e não é professor

        # TODO: >>> PONTO DE REVISÃO E IMPLEMENTAÇÃO: CONSUMIR CONVITE LÓGICA <<<
        # Verificar validade do convite: usos, expiração, se aluno já está na turma.
        if invite.max_uses is not None and invite.uses_count >= invite.max_uses:
            return Response({"error": "Este convite atingiu o número máximo de usos."}, status=status.HTTP_400_BAD_REQUEST)

        if invite.expires_at is not None and invite.expires_at < timezone.now():
             return Response({"error": "Este convite expirou."}, status=status.HTTP_400_BAD_REQUEST)

        # Verificar se o aluno já é membro ativo da turma
        if ClassStudent.objects.filter(class_instance=invite.class_invite, student=user, removed_at__isnull=True).exists():
             return Response({"error": "Você já é membro desta turma."}, status=status.HTTP_400_BAD_REQUEST)


        # Criar a associação ClassStudent
        ClassStudent.objects.create(
            class_instance=invite.class_invite,
            student=user
        )

        # Incrementar o contador de usos do convite
        invite.uses_count += 1
        invite.save()

        return Response({
            "message": f"Você entrou na turma '{invite.class_invite.name}' com sucesso!"
        }, status=status.HTTP_200_OK)


# ClassStudentsView e RemoveStudentView serão movidas para actions em ClassModelViewSet (ver TODOs acima)
# class ClassStudentsView(generics.ListAPIView): ...
# class RemoveStudentView(views.APIView): ...


# --------------------------------
# 6. ATIVIDADES (ViewSets com actions customizadas)
# --------------------------------

class ActivityViewSet(BaseModelViewSet): # Herda de BaseModelViewSet
    """ViewSet para operações CRUD em Atividades e listagem por turma/usuário."""
    queryset = Activity.objects.all()
    serializer_class = ActivitySerializer

    # TODO: Definir search_fields e ordering_fields
    search_fields = ['title', 'description', 'professor__full_name']
    ordering_fields = ['created_at', 'due_date', 'title']

    def get_permissions(self):
        """Define permissões baseadas na ação."""
        # TODO: >>> PONTO DE REVISÃO E IMPLEMENTAÇÃO: PERMISSÕES DE ATIVIDADE <<<
        # - create: IsTeacher (e talvez IsTeacherAndPremiumActive).
        # - list: Decidir quem pode listar o quê (filtrado no get_queryset).
        # - retrieve: Professor da atividade, Membro da turma associada (via ActivityClass), Admin.
        # - update/partial_update/destroy: Apenas professor da atividade (IsActivityTeacher).
        # - list_by_class (@action aninhada): IsAuthenticated, IsClassMember na turma.
        if self.action == 'create':
             self.permission_classes = [permissions.IsAuthenticated, IsTeacher] # TODO: Add IsTeacherAndPremiumActive
        elif self.action in ['update', 'partial_update', 'destroy']:
             self.permission_classes = [permissions.IsAuthenticated, IsActivityTeacher] # Verificar se o usuário é professor da activity
        elif self.action in ['retrieve']:
            # Professor da atividade OU Membro da turma associada OU Admin
             self.permission_classes = [permissions.IsAuthenticated, IsActivityTeacher | IsClassMember | permissions.IsAdminUser] # Combine/refine

        # Permissões para action list_by_class definidas diretamente nela.
        # Permissão para list action get_queryset cuidará da filtragem, permissão IsAuthenticated na classe

        return super().get_permissions()

    def get_queryset(self):
        """Filtra queryset baseado no usuário para a lista geral."""
        user = self.request.user

        if self.action == 'list':
            # TODO: >>> PONTO DE REVISÃO E IMPLEMENTAÇÃO: FILTRAGEM DA LISTA GERAL DE ATIVIDADES <<<
            # O que /api/activities/list deve retornar?
            # - Atividades do professor logado (criadas por ele)
            # - Atividades das turmas do aluno logado
            # - Todas as atividades (para admin)
            if user.is_teacher:
                 return Activity.objects.filter(professor=user)
            elif user.is_authenticated: # Aluno
                 # Busca atividades associadas a turmas onde o aluno é membro ativo
                 return Activity.objects.filter(
                     activity_classes__class_instance__class_students__student=user,
                     activity_classes__class_instance__class_students__removed_at__isnull=True
                 ).distinct()
            # Admin vê todas por padrão com IsAdminUser permission na classe/get_permissions
            return super().get_queryset() # Queryset base para Admin

        return super().get_queryset() # Queryset base para retrieve, update, destroy etc.


    def perform_create(self, serializer):
        """Define o professor logado na criação da atividade."""
        # A permissão IsTeacher (e IsTeacherAndPremiumActive) já garantiu que é um professor elegível
        serializer.save(professor=self.request.user)

    # TODO: Adicionar @action para listar atividades de uma turma específica?
    # Exemplo (requer ViewSet aninhado ou rota customizada com ID da turma):
    # @action(detail=False, methods=['get'], serializer_class=ActivitySerializer, permission_classes=[IsAuthenticated, IsClassMember], url_path='by_class/(?P<class_pk>[^/.]+)')
    # def list_by_class(self, request, class_pk=None): # class_pk virá da URL
    #     class_obj = get_object_or_404(ClassModel, pk=class_pk)
    #     self.check_object_permissions(request, class_obj) # Verificar permissão na turma
    #     queryset = self.get_queryset().filter(activity_classes__class_instance=class_obj).distinct()
    #     # Usa paginação e filtros/busca
    #     page = self.paginate_queryset(queryset)
    #     if page is not None:
    #         serializer = self.get_serializer(page, many=True)
    #         return self.get_paginated_response(serializer.data)
    #     serializer = self.get_serializer(queryset, many=True)
    #     return Response(serializer.data)


class ActivityClassViewSet(BaseModelViewSet): # Herda de BaseModelViewSet
    """ViewSet para gerenciar associações Atividade-Turma."""
    queryset = ActivityClass.objects.all()
    serializer_class = ActivityClassSerializer

    # TODO: Definir search_fields e ordering_fields
    search_fields = ['activity__title', 'class_instance__name']
    ordering_fields = ['id']

    def get_permissions(self):
        """Define permissões baseadas na ação."""
        # TODO: >>> PONTO DE REVISÃO E IMPLEMENTAÇÃO: PERMISSÕES DE ASSOCIATION <<<
        # Apenas professores podem criar/deletar associações.
        # O professor deve ser o professor da atividade OU da turma.
        # Listar? Detalhe? Talvez só para admin ou professor que gerencia?
        if self.action in ['create', 'destroy']:
            self.permission_classes = [permissions.IsAuthenticated, IsTeacher] # Lógica adicional em perform_create/destroy
        # self.permission_classes = [...] # Para list/retrieve
        return super().get_permissions()

    def get_queryset(self):
        """Filtra quais associações podem ser listadas/vistas."""
        user = self.request.user
        if user.is_teacher:
            # Professor só gerencia associações das SUAS atividades/turmas
            return ActivityClass.objects.filter(Q(activity__professor=user) | Q(class_instance__professor=user)).select_related('activity', 'class_instance')
        # Admin vê todas por padrão com IsAdminUser permission
        return super().get_queryset().select_related('activity', 'class_instance') # Queryset base para Admin


    def perform_create(self, serializer):
        """Cria uma associação Atividade-Turma, verificando permissões."""
        activity = serializer.validated_data.get('activity')
        class_instance = serializer.validated_data.get('class_instance')

        # TODO: >>> PONTO DE REVISÃO E IMPLEMENTAÇÃO: VALIDAR PERMISSÃO NA CRIAÇÃO DE ASSOCIAÇÃO <<<
        # Verificar se o usuário logado é o professor da 'activity' OU da 'class_instance'.
        if activity.professor != self.request.user and class_instance.professor != self.request.user:
            # TODO: >>> PONTO DE REVISÃO E IMPLEMENTAÇÃO: TRATAMENTO DE ERROS <<<
            raise permissions.PermissionDenied("Você não é o professor da atividade nem da turma associada.")

        serializer.save()

    def perform_destroy(self, instance):
        """Deleta uma associação Atividade-Turma, verificando permissões."""
         # A permissão já foi verificada no get_permissions e get_queryset.
         # Lógica adicional pode ser necessária se a deleção tiver efeitos colaterais.
        instance.delete()


# --------------------------------
# 7. SUBMISSÕES E FEEDBACK (ViewSets com actions customizadas e integração Cloudinary)
# --------------------------------

class SubmissionViewSet(BaseModelViewSet): # Herda de BaseModelViewSet
    """ViewSet para operações CRUD em Submissões, com upload para Cloudinary."""
    queryset = Submission.objects.all()
    serializer_class = SubmissionSerializer

    # TODO: Definir search_fields e ordering_fields
    search_fields = ['status', 'activity__title', 'student__full_name']
    ordering_fields = ['submitted_at', 'status']

    def get_permissions(self):
        """Define permissões baseadas na ação."""
        # TODO: >>> PONTO DE REVISÃO E IMPLEMENTAÇÃO: PERMISSÕES DE SUBMISSÃO <<<
        # - create: Apenas Aluno (autenticado e não professor), e deve ser membro da turma associada.
        # - list: Aluno (suas), Professor (suas atividades/turmas), Admin (todas).
        # - retrieve: Aluno (dono), Professor (atividade/turma), Admin.
        # - update/partial_update: Aluno (dono, se no prazo), Professor (atividade/turma, para status?). Admin.
        # - destroy: Aluno (dono, se permitido/no prazo), Professor (atividade/turma). Admin.
        if self.action == 'create':
             self.permission_classes = [permissions.IsAuthenticated, ~IsTeacher] # Apenas aluno autenticado
             # Lógica adicional na view.create() para verificar associação Atividade-Turma-Aluno
        elif self.action in ['retrieve']:
             self.permission_classes = [permissions.IsAuthenticated, IsOwner | IsClassTeacher | permissions.IsAdminUser] # Combine/refine
        elif self.action in ['update', 'partial_update']:
             self.permission_classes = [permissions.IsAuthenticated, IsOwner | IsClassTeacher | permissions.IsAdminUser] # Combine/refine, lógica de prazo/campos na view
        elif self.action in ['destroy']:
             self.permission_classes = [permissions.IsAuthenticated, IsOwner | IsClassTeacher | permissions.IsAdminUser] # Combine/refine, lógica de prazo na view
        # list action get_queryset cuidará da filtragem, permissão IsAuthenticated na classe

        return super().get_permissions()

    def get_queryset(self):
        """Filtra queryset baseado no usuário para a lista geral."""
        user = self.request.user

        # TODO: >>> PONTO DE REVISÃO E IMPLEMENTAÇÃO: FILTRAGEM DA LISTA GERAL DE SUBMISSÕES <<<
        # Quem vê o quê na lista /api/submissions/list?
        if user.is_teacher:
             # Submissões para atividades criadas por ele OU associadas a turmas que ele ensina
             return Submission.objects.filter(
                 Q(activity__professor=user) |
                 Q(activity__activity_classes__class_instance__professor=user)
             ).distinct().select_related('activity', 'student')
        elif user.is_authenticated: # Aluno
             # Apenas as submissões dele
             return Submission.objects.filter(student=user).select_related('activity', 'student')
        # Admin vê todas por padrão com IsAdminUser permission na classe/get_permissions
        return super().get_queryset().select_related('activity', 'student') # Queryset base para Admin


    def create(self, request, *args, **kwargs):
        """Cria uma nova submissão, lidando com o upload de arquivo para Cloudinary."""
        # User: Já garantido que é autenticado e não professor pela permission_classes (~IsTeacher)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True) # Valida campos como activity, file, etc.

        activity = serializer.validated_data.get('activity') # Objeto Activity validado
        file_obj = serializer.validated_data.get('file') # O arquivo (UploadedFile)

        # TODO: >>> PONTO DE REVISÃO E IMPLEMENTAÇÃO: VALIDAÇÃO ADICIONAL (CREATE SUBMISSION) <<<
        # 1. Verificar se o usuário logado (request.user) é um aluno. (Já feito na permissão ~IsTeacher)
        # 2. Verificar se este aluno é membro ativo de *alguma* turma onde a 'activity' está associada (para submeter).
        # 3. Verificar se a atividade está aberta para submissões (status, due_date).
        # 4. Verificar se um arquivo foi fornecido se a atividade exige um arquivo (regra de negócio).

        # Exemplo de validação de associação Atividade-Turma-Aluno
        is_member = ClassStudent.objects.filter(
            class_instance__activity_classes__activity=activity,
            student=request.user,
            removed_at__isnull=True
        ).exists()
        if not is_member:
             # TODO: >>> PONTO DE REVISÃO E IMPLEMENTAÇÃO: TRATAMENTO DE ERROS <<<
             return Response({"error": "Você não é membro de uma turma onde esta atividade foi atribuída."}, status=status.HTTP_403_FORBIDDEN)

        # TODO: Validar status e due_date da atividade para submissão
        # if activity.status != 'open' or (activity.due_date and timezone.now() > activity.due_date):
        #      return Response({"error": "Esta atividade não está aberta para submissões no momento."}, status=status.HTTP_400_BAD_REQUEST)


        file_path = None # URL do Cloudinary
        mime_type = None
        public_id = None # ID do Cloudinary para deleção futura

        # TODO: >>> PONTO DE REVISÃO E IMPLEMENTAÇÃO: CLOUDINARY UPLOAD (CREATE) <<<
        # Fazer upload do file_obj para o Cloudinary usando o SDK.
        # Obter a URL (`secure_url`), `mime_type` (ou format), e `public_id` do resultado do upload.
        # Lidar com erros de upload.
        if file_obj:
            try:
                # Exemplo de chamada Cloudinary (SUBSTITUIR):
                # upload_result = cloudinary.uploader.upload(
                #     file_obj,
                #     folder=f"submissions/activity_{activity.id}/user_{request.user.id}", # Exemplo de organização de pastas
                #     public_id=f"{activity.id}_{request.user.id}_{uuid.uuid4().hex[:5]}", # Nome único
                #     resource_type='auto' # Detectar tipo automaticamente
                # )
                # file_path = upload_result['secure_url']
                # mime_type = upload_result.get('resource_type') + '/' + upload_result.get('format') # Ou file_obj.content_type
                # public_id = upload_result['public_id'] # SALVAR este ID no modelo Submission!

                # Placeholder:
                file_path = f"http://cloudinary.com/placeholder/submissions/{uuid.uuid4().hex}"
                mime_type = file_obj.content_type
                public_id = f"placeholder_id_{uuid.uuid4().hex[:8]}" # Salvar este ID
                logger.info(f"Placeholder: Arquivo '{file_obj.name}' seria enviado para Cloudinary. URL: {file_path}, Public ID: {public_id}")

            except Exception as e:
                logger.error(f"Erro no upload para Cloudinary para activity {activity.id}, user {request.user.id}: {e}", exc_info=True)
                # TODO: >>> PONTO DE REVISÃO E IMPLEMENTAÇÃO: TRATAMENTO DE ERROS <<<
                return Response({"error": "Falha no upload do arquivo para a nuvem."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


        # TODO: >>> PONTO DE REVISÃO E IMPLEMENTAÇÃO: SALVAR SUBMISSION <<<
        # Criar a instância de Submission no BD:
        # student=request.user
        # activity=activity
        # file_path = URL do Cloudinary
        # mime_type = tipo do arquivo
        # status='pending' (ou 'late' se o prazo passou - verificar due_date aqui)
        # cloudinary_public_id = public_id # Adicionar este campo no modelo Submission e salvar!
        submission = Submission.objects.create(
            activity=activity,
            student=request.user,
            file_path=file_path, # URL salva no DB
            mime_type=mime_type,
            status='pending', # TODO: Verificar due_date para status 'late'
            # cloudinary_public_id=public_id, # Salvar o public_id do Cloudinary
        )

        # Retornar os dados da submissão criada
        headers = self.get_success_headers(self.get_serializer(submission).data)
        return Response(self.get_serializer(submission).data, status=status.HTTP_201_CREATED, headers=headers)


    def update(self, request, *args, **kwargs):
        """Atualiza uma submissão, lidando com upload de arquivo e permissões (Aluno/Professor)."""
        # TODO: >>> PONTO DE REVISÃO E IMPLEMENTAÇÃO: LÓGICA DE UPDATE DE SUBMISSÃO <<<
        # 1. Obter a instância de Submission (self.get_object() já verifica permissões IsOwner | IsClassTeacher).
        # 2. Verificar quem está atualizando (Aluno vs Professor).
        # 3. Se for Aluno (instance.student == request.user):
        #    - Verificar se o prazo (instance.activity.due_date) ainda não passou.
        #    - Validar que o Aluno SÓ PODE atualizar o campo 'file'. Outros campos devem ser ignorados ou barrados.
        #    - Se um novo arquivo foi enviado (validated_data.get('file')): Deletar o arquivo anterior no Cloudinary usando o public_id salvo. Fazer upload do novo. Atualizar file_path, mime_type, public_id.
        # 4. Se for Professor (verifica IsClassTeacher na permissão):
        #    - Professor pode atualizar o campo 'status'. Outros campos devem ser ignorados (ex: file).
        #    - Professor GERALMENTE NÃO ATUALIZA O ARQUIVO ENVIADO PELO ALUNO.
        # 5. Salvar a instância atualizada.
        # 6. Retornar dados atualizados.

        instance = self.get_object() # Já verifica permissões (IsOwner para Aluno, IsClassTeacher para Professor, AdminUser)
        # Use o serializer com partial=True para validar apenas os campos recebidos
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True) # Validação básica dos campos recebidos

        file_obj = serializer.validated_data.get('file')
        new_status = serializer.validated_data.get('status')
        # Obter outros campos permitidos para atualização

        # Lógica de atualização baseada no usuário e permissões
        if instance.student == request.user and not request.user.is_teacher:
             # Atualização por Aluno (apenas arquivo e talvez status pendente?)
             # TODO: Verificar prazo da atividade (instance.activity.due_date)
             # TODO: Validar que o Aluno SÓ PODE atualizar campos permitidos (ex: 'file')
             # Remover outros campos não permitidos da validated_data antes de salvar
             if 'status' in serializer.validated_data and serializer.validated_data['status'] != 'pending':
                 # Aluno talvez só possa resetar para pendente ou não mudar status
                 return Response({"error": "Alunos geralmente não podem alterar o status da submissão."}, status=status.HTTP_403_FORBIDDEN)
             if 'status' in serializer.validated_data:
                  instance.status = new_status # Permitir Aluno mudar status para pending?

             if file_obj:
                 # TODO: Implementar deleção do arquivo anterior no Cloudinary usando o public_id salvo no modelo
                 # TODO: Fazer upload do novo arquivo para Cloudinary
                 # TODO: Atualizar instance.file_path, instance.mime_type, public_id
                 logger.info(f"Placeholder: Aluno atualizando arquivo para submissão {instance.id}. Novo arquivo: {file_obj.name}")
                 instance.file_path = f"http://cloudinary.com/placeholder/submissions/updated_{uuid.uuid4().hex}" # Placeholder
                 instance.mime_type = file_obj.content_type # Placeholder
                 # instance.cloudinary_public_id = new_public_id # Salvar novo public_id

             instance.save() # Salva a instância com as alterações permitidas

        elif instance.activity.professor == request.user or (hasattr(request.user, 'is_teacher') and request.user.is_teacher): # Professor da atividade ou relacionado ou Admin
             # Atualização por Professor (apenas status?)
             # TODO: Validar que o Professor SÓ PODE atualizar campos permitidos (ex: 'status')
             # Remover outros campos não permitidos da validated_data antes de salvar
             if file_obj:
                 # Professor não deveria atualizar arquivo do aluno via este endpoint
                 return Response({"error": "Professores não podem alterar o arquivo submetido pelo aluno."}, status=status.HTTP_403_FORBIDDEN)

             if new_status:
                 instance.status = new_status
                 instance.save()
                 logger.info(f"Professor atualizou status da submissão {instance.id} para {instance.status}.")
             # Professor pode adicionar score/comment via endpoint de Feedback.


        else:
             # Se chegou aqui, o usuário não tem permissão para atualizar este objeto
             # A permissão do ViewSet já deveria ter barrado, mas esta lógica interna é uma salvaguarda.
             return Response({"error": "Você não tem permissão para atualizar esta submissão ou os campos fornecidos."}, status=status.HTTP_403_FORBIDDEN)


        # Retornar dados atualizados
        return Response(self.get_serializer(instance).data)


    def destroy(self, request, *args, **kwargs):
        """Deleta uma submissão, deletando o arquivo correspondente no Cloudinary."""
        # TODO: >>> PONTO DE REVISÃO E IMPLEMENTAÇÃO: LÓGICA DE DELETE DE SUBMISSÃO <<<
        # 1. Obter a instância de Submission (self.get_object() já verifica permissões IsOwner | IsClassTeacher).
        # 2. Verificar quem está deletando (Aluno vs Professor).
        # 3. Se for Aluno: Verificar se permitido (ex: se o prazo não passou).
        # 4. Se for Professor: Permitir sempre?
        # 5. Se a deleção for permitida E existir um arquivo (instance.file_path ou instance.cloudinary_public_id):
        #    - Chamar a API do Cloudinary para deletar o arquivo usando o public_id (SALVO NO MODELO).
        # 6. Deletar a instância de Submission do BD.

        instance = self.get_object() # Já verifica permissões

        # Exemplo: Permitir que o Aluno delete se for o dono E o prazo não passou
        if instance.student == request.user and not request.user.is_teacher:
            # TODO: Verificar prazo da atividade (instance.activity.due_date)
            # if timezone.now() > instance.activity.due_date:
            #     return Response({"error": "Prazo para deletar a submissão expirado."}, status=status.HTTP_403_FORBIDDEN)
            pass # Permite Aluno deletar se for o dono e no prazo

        # Exemplo: Permitir Professor ou Admin delete sempre (verificado pela permissão IsClassTeacher | AdminUser)
        elif instance.activity.professor == request.user or (hasattr(request.user, 'is_teacher') and request.user.is_teacher) or (hasattr(request.user, 'is_staff') and request.user.is_staff):
             pass # Permite Professor/Admin deletar

        else:
             # Se chegou aqui, o usuário não tem permissão
             return Response({"error": "Você não tem permissão para deletar esta submissão."}, status=status.HTTP_403_FORBIDDEN)


        # TODO: >>> PONTO DE REVISÃO E IMPLEMENTAÇÃO: CLOUDINARY DELETE <<<
        # Chamar a API do Cloudinary para deletar o arquivo usando o public_id SALVO no modelo Submission.
        if instance.file_path: # Ou use instance.cloudinary_public_id
            try:
                # Exemplo hipotético de chamada Cloudinary (SUBSTITUIR, precisa do public_id salvo)
                # public_id = instance.cloudinary_public_id # Obter o public_id salvo no modelo
                # if public_id:
                #    cloudinary.uploader.destroy(public_id)
                logger.info(f"Placeholder: Arquivo no Cloudinary para submissão {instance.id} (Public ID: [salvo no modelo]) seria deletado.")
            except Exception as e:
                 logger.error(f"Erro ao deletar arquivo no Cloudinary para submissão {instance.id}: {e}", exc_info=True)
                 # TODO: Decidir se falhar na deleção do Cloudinary impede a deleção local ou apenas loga o erro.
                 # Geralmente, a deleção local no BD deve ocorrer mesmo que a deleção na nuvem falhe.


        # Deleta a instância do banco de dados
        self.perform_destroy(instance)

        return Response(status=status.HTTP_204_NO_CONTENT)


class FeedbackViewSet(BaseModelViewSet): # Herda de BaseModelViewSet
    """ViewSet para operações CRUD em Feedback."""
    queryset = Feedback.objects.all()
    serializer_class = FeedbackSerializer

    # TODO: Definir search_fields e ordering_fields
    search_fields = ['comment', 'professor__full_name', 'submission__student__full_name']
    ordering_fields = ['created_at', 'score']

    def get_permissions(self):
        """Define permissões baseadas na ação."""
        # TODO: >>> PONTO DE REVISÃO E IMPLEMENTAÇÃO: PERMISSÕES DE FEEDBACK <<<
        # - create: Apenas Professor (da atividade associada à submissão).
        # - list: Professor (seus), Aluno (suas submissões), Admin (todas).
        # - retrieve: Professor (criador), Aluno (da submissão), Admin.
        # - update/partial_update/destroy: Apenas Professor que criou o feedback (IsOwner).
        # - list_by_submission (@action aninhada): IsAuthenticated, IsClassMember na turma/atividade.
        if self.action == 'create':
             self.permission_classes = [permissions.IsAuthenticated, IsTeacher] # Lógica adicional em perform_create
        elif self.action in ['retrieve']:
             self.permission_classes = [permissions.IsAuthenticated, IsOwner | IsClassMember | permissions.IsAdminUser] # IsOwner verifica professor criador, IsClassMember verifica aluno/professor da turma/atividade
        elif self.action in ['update', 'partial_update', 'destroy']:
             self.permission_classes = [permissions.IsAuthenticated, IsOwner] # IsOwner verifica professor criador do Feedback
        # list action get_queryset cuidará da filtragem, permissão IsAuthenticated na classe

        return super().get_permissions()

    def get_queryset(self):
        """Filtra queryset baseado no usuário para a lista geral."""
        user = self.request.user

        # TODO: >>> PONTO DE REVISÃO E IMPLEMENTAÇÃO: FILTRAGEM DA LISTA GERAL DE FEEDBACK <<<
        # Quem vê o quê na lista /api/feedbacks/list?
        if user.is_teacher:
             # Feedbacks dados pelo professor logado
             return Feedback.objects.filter(professor=user).select_related('submission__student', 'submission__activity')
        elif user.is_authenticated: # Aluno
             # Feedbacks para as submissões dele
             return Feedback.objects.filter(submission__student=user).select_related('submission__activity', 'professor')
        # Admin vê todas por padrão com IsAdminUser permission na classe/get_permissions
        return super().get_queryset().select_related('submission__student', 'submission__activity', 'professor') # Queryset base para Admin


    def perform_create(self, serializer):
        """Define o professor logado e valida permissão na criação do feedback."""
        # A permissão IsTeacher já garantiu que é um professor.
        # Agora, verificar se ele é o professor da atividade associada à submissão.
        submission = serializer.validated_data.get('submission') # Objeto Submission validado
        activity_professor = submission.activity.professor

        # TODO: >>> PONTO DE REVISÃO E IMPLEMENTAÇÃO: VALIDAR PROFESSOR DA ATIVIDADE <<<
        # Verificar se o usuário logado é o professor da atividade associada à submissão.
        if self.request.user != activity_professor:
             # TODO: >>> PONTO DE REVISÃO E IMPLEMENTAÇÃO: TRATAMENTO DE ERROS <<<
             raise permissions.PermissionDenied("Você não é o professor da atividade para a qual está tentando dar feedback.")

        # Salvar o feedback, definindo o professor como o usuário logado
        serializer.save(professor=self.request.user)

    # TODO: Adicionar @action para listar feedbacks de uma submissão específica?
    # Exemplo (requer ViewSet aninhado ou rota customizada com ID da submissão):
    # @action(detail=False, methods=['get'], serializer_class=FeedbackSerializer, permission_classes=[IsAuthenticated, IsClassMember], url_path='by_submission/(?P<submission_pk>[^/.]+)')
    # def list_by_submission(self, request, submission_pk=None): # submission_pk virá da URL
    #     submission_obj = get_object_or_404(Submission, pk=submission_pk)
    #     # check_object_permissions para garantir permissão na submissão/turma/atividade
    #     self.check_object_permissions(request, submission_obj)
    #     queryset = self.get_queryset().filter(submission=submission_obj)
    #     # Usa paginação e filtros/busca
    #     page = self.paginate_queryset(queryset)
    #     if page is not None:
    #         serializer = self.get_serializer(page, many=True)
    #         return self.get_paginated_response(serializer.data)
    #     serializer = self.get_serializer(queryset, many=True)
    #     return Response(serializer.data)


# TODO: >>> PONTO DE REVISÃO E IMPLEMENTAÇÃO: VALIDAÇÃO E TRATAMENTO DE ERROS GERAL <<<
# - Revisar todos os métodos validate() nos serializers para cobrir as regras de negócio (ranges, datas, consistência entre campos).
# - Implementar tratamento de exceções global no DRF (settings.py) para retornar respostas de erro consistentes (400, 401, 403, 404, 500) com format
# - Garantir que todas as views customizadas e actions capturem exceções inesperadas (try...except Exception) e retornem 500 Internal Server Error.
# - Padronizar o formato das respostas de erro (ex: {'error': 'Mensagem de erro', 'details': {...}}).