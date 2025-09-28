from django.contrib import admin
from .models import CustomUser, Metodo, ModeloLaudo, Frase, Variavel

# Register your models here.

@admin.register(CustomUser)
class CustomUserAdmin(admin.ModelAdmin):
    list_display = ['email', 'username', 'nome_completo', 'telefone', 'is_active', 'date_joined']
    list_filter = ['is_active', 'is_staff', 'date_joined']
    search_fields = ['email', 'username', 'nome_completo']
    ordering = ['email']

@admin.register(Metodo)
class MetodoAdmin(admin.ModelAdmin):
    list_display = ['metodo']
    search_fields = ['metodo']
    ordering = ['metodo']

@admin.register(ModeloLaudo)
class ModeloLaudoAdmin(admin.ModelAdmin):
    list_display = ['titulo', 'metodo', 'usuario', 'criado_em']
    list_filter = ['metodo', 'usuario', 'criado_em']
    search_fields = ['titulo', 'metodo__metodo', 'usuario__email']
    ordering = ['-criado_em']

@admin.register(Frase)
class FraseAdmin(admin.ModelAdmin):
    list_display = ['tituloFrase', 'categoriaFrase', 'usuario', 'criado_em']
    list_filter = ['categoriaFrase', 'usuario', 'criado_em']
    search_fields = ['tituloFrase', 'categoriaFrase', 'usuario__email']
    ordering = ['-criado_em']
    filter_horizontal = ['modelos_laudo']

@admin.register(Variavel)
class VariavelAdmin(admin.ModelAdmin):
    list_display = ['tituloVariavel', 'usuario', 'criado_em']
    list_filter = ['usuario', 'criado_em']
    search_fields = ['tituloVariavel', 'usuario__email']
    ordering = ['-criado_em']
