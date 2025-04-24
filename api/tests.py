from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from core.models import User, Plan, Subscription

class SubscriptionAPITestCase(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            full_name='Usuário Teste',
            email='teste@exemplo.com',
            cpf='12345678901',
            password='senha123',
            is_teacher=False,
            verified_email=True
        )
        self.plan = Plan.objects.create(
            name='Plano Teste',
            price_cents=1000,
            description='Plano de teste'
        )
        self.client.force_authenticate(user=self.user)

    def test_subscription_flow(self):
        # Cria uma assinatura manualmente (simulando integração Appmax)
        subscription = Subscription.objects.create(
            user=self.user,
            plan=self.plan,
            appmax_subscription_id='appmax123',
            status='active'
        )
        url = reverse('subscription-me')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], subscription.id)
        self.assertEqual(response.data['status'], 'active')
        self.assertEqual(response.data['appmax_subscription_id'], 'appmax123')

class AuthAPITestCase(APITestCase):
    def test_register_and_login(self):
        # Cadastro
        register_url = '/api/auth/register/'
        user_data = {
            'full_name': 'Novo Usuário',
            'email': 'novo@exemplo.com',
            'cpf': '98765432100',
            'password': 'senha123',
            'is_teacher': False
        }
        response = self.client.post(register_url, user_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('user', response.data)
        self.assertEqual(response.data['user']['email'], user_data['email'])

        # Forçar verificação de e-mail para permitir login
        from core.models import User
        user = User.objects.get(email=user_data['email'])
        user.verified_email = True
        user.save()

        # Login
        login_url = '/api/auth/login/'
        login_data = {
            'email': user_data['email'],
            'password': user_data['password']
        }
        response = self.client.post(login_url, login_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
        self.assertIn('user', response.data) 