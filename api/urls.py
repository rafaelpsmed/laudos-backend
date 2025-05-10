from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    MetodoViewSet, ModeloLaudoViewSet,
    FraseViewSet, VariavelViewSet, AuthViewSet
)

router = DefaultRouter()
router.register(r'metodos', MetodoViewSet)
router.register(r'modelo_laudo', ModeloLaudoViewSet)
router.register(r'frases', FraseViewSet, basename='frases')
router.register(r'variaveis', VariavelViewSet)
router.register(r'auth', AuthViewSet, basename='auth')

urlpatterns = [
    path('', include(router.urls)),
] 