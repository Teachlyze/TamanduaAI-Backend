# urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_nested import routers # Para rotas aninhadas
from .views import PaymentInitiateView, AppmaxWebhookView 

from .views import (
    # APIViews de Auth
    AuthRegisterView, AuthLoginView, AuthLogoutView,
    # TODO: RequestVerificationView, VerifyEmailView, ResetPasswordRequestView, ResetPasswordConfirmView,

    # ViewSets (mapeados pelo Router)
    UserViewSet,
    PlanViewSet,
    PaymentViewSet, # Para lista geral (Admin) e detalhe (Dono/Admin)
    SubscriptionViewSet, # Para lista geral (Admin) e detalhe (Dono/Admin)
    ClassModelViewSet,
    InviteViewSet, # Para CRUD geral de invites e action consume
    ActivityViewSet,
    ActivityClassViewSet, # Para criar/deletar associações

    SubmissionViewSet, # Para CRUD de submissões
    FeedbackViewSet # Para CRUD de feedbacks

    # Views/Generics que podem ser movidas para ViewSets como @actions:
    # UserPaymentsView, # -> Mover para PaymentViewSet como action 'my_payments'
    # UserSubscriptionView, # -> Mover para SubscriptionViewSet como action 'my_subscription'
    # UserClassesView, # -> Mover para ClassModelViewSet como action 'my_classes'
    # ClassStudentsView, # -> Mover para ClassModelViewSet como action 'students' (aninhada)
    # RemoveStudentView, # -> Mover para ClassModelViewSet como action 'remove_student' (aninhada)
)

# Router principal usando DefaultRouter para ViewSets
router = DefaultRouter()
# Note: lookup padrão é 'pk'
router.register(r'users', UserViewSet, basename='user')
router.register(r'plans', PlanViewSet, basename='plan')
router.register(r'payments', PaymentViewSet, basename='payment')
router.register(r'subscriptions', SubscriptionViewSet, basename='subscription')
router.register(r'classes', ClassModelViewSet, basename='class')
# Para invites que usam código ao invés de PK na URL de detalhe/action consume:
router.register(r'invites', InviteViewSet, basename='invite') # Usar lookup='code'
router.register(r'activities', ActivityViewSet, basename='activity')
router.register(r'activity-classes', ActivityClassViewSet, basename='activity-class')
router.register(r'submissions', SubmissionViewSet, basename='submission')
router.register(r'feedbacks', FeedbackViewSet, basename='feedback')


# Rotas aninhadas usando rest_framework_nested (Recomendado para organização)
# Exemplo: /classes/{class_pk}/students/ e /classes/{class_pk}/invites/ (se Invite fosse aninhado)
classes_router = routers.NestedDefaultRouter(router, r'classes', lookup='class')
# Exemplo de registro de action aninhada (se ClassStudentsView for movida para action 'students' em ClassModelViewSet)
# classes_router.register(r'students', ClassModelViewSet, basename='class-students', parents_query_lookups=['class_students__student']) # lookup precisa ser definido para filtrar
# A rota RemoveStudentView também pode ser aninhada se movida para @action em ClassModelViewSet

# TODO: Decidir quais ViewSets/Actions aninhados você realmente precisa e configurá-los aqui.


# URL Patterns principais
urlpatterns = [
    # Rotas de Autenticação (APIViews customizadas) - Use prefixo 'auth/'
    path('api/auth/register/', AuthRegisterView.as_view(), name='auth_register'),
    path('api/auth/login/', AuthLoginView.as_view(), name='auth_login'),
    path('api/auth/logout/', AuthLogoutView.as_view(), name='auth_logout'),
    # TODO: Adicionar URLs para RequestVerification, VerifyEmail, ResetPassword...

    # Rotas geradas pelos ViewSets via Router principal
    # Ex: /api/users/, /api/users/{pk}/, /api/users/me/, /api/plans/, /api/payments/, etc.
    path('api/', include(router.urls)),

    # Rotas geradas pelos ViewSets via Router aninhado (se usados)
    # Ex: /api/classes/{class_pk}/students/ (se movido para action/ViewSet aninhado)
    # path('api/', include(classes_router.urls)), # Descomentar e configurar se usar ViewSets aninhados

    # Rotas específicas que não são ViewSets CRUD padrão ou actions de ViewSet principal
    # Mover para @actions nos ViewSets correspondentes é o ideal (ver TODOs nas views)
    # Se não mover, defina as rotas aqui:

    # Rotas de Pagamento/Assinatura Específicas (TODO: Mover para actions em PaymentViewSet/SubscriptionViewSet)
    # 4path('api/payments/initiate/', PaymentInitiateView.as_view(), name='payment_initiate'), # Nome de URL: use hífens e prefixo relevante
    # 4path('api/webhooks/appmax/', AppmaxWebhookView.as_view(), name='appmax_webhook'), # Nome fixo para Appmax
    # path('api/users/me/payments/', UserPaymentsView.as_view(), name='user_payments'), # Mover
    # path('api/payments/<int:pk>/', PaymentDetailView.as_view(), name='payment_detail'), # ViewSet já gera payments/{pk}/
    # path('api/users/me/subscription/', UserSubscriptionView.as_view(), name='user_subscription'), # Mover
    # 4path('api/users/me/subscription/cancel/', CancelSubscriptionView.as_view(), name='subscription_cancel'), # Nome de URL: prefixo + ação

    # Rotas de Turma/Aluno/Convite Específicas (TODO: Mover para actions em ClassModelViewSet/InviteViewSet)
    # path('api/users/me/classes/', UserClassesView.as_view(), name='user_classes'), # Mover
    # path('api/classes/<int:class_id>/students/', ClassStudentsView.as_view(), name='class_students'), # Manter aqui se não for action/ViewSet aninhado
    # path('api/classes/<int:class_id>/students/<int:student_id>/remove/', RemoveStudentView.as_view(), name='remove_student'), # Nome de URL: ação + IDs
    # path('api/invites/<str:code>/consume/', InviteViewSet.as_view({'post': 'consume'}), name='invite_consume'), # Gerado pelo router com lookup='code' e url_path='consume'

    # TODO: Revisar e PADRONIZAR todos os nomes de URLs (usando snake_case, plurais, prefixos de recurso).
    # Exemplo de nomes de URLs mais padronizados:
    # 'auth-register', 'auth-login', 'auth-logout'
    # 'user-me', 'user-list', 'user-detail'
    # 'plan-list', 'plan-detail'
    # 'payments-initiate', 'payments-list', 'payments-detail', 'payments-my' (se action)
    # 'subscriptions-my', 'subscriptions-cancel', 'subscriptions-list', 'subscriptions-detail'
    # 'classes-list', 'classes-detail', 'classes-my' (se action), 'classes-students-list' (se aninhado action/view), 'classes-students-remove' (se aninhado action)
    # 'invites-list', 'invites-detail', 'invites-consume'
    # 'activities-list', 'activities-detail', 'activities-by-class' (se action)
    # 'activity-classes-list', 'activity-classes-detail' (se ViewSet)
    # 'submissions-list', 'submissions-detail', 'submissions-my' (se action)
    # 'feedbacks-list', 'feedbacks-detail', 'feedbacks-by-submission' (se action)

]

# TODO: Verifique se TODOS os endpoints definidos no documento original estão implementados aqui
# Seja como rota gerada por Router, @action, ou path explícito.