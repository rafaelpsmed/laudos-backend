from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from .models import CustomUser, Metodo, ModeloLaudo, Frase, Variavel
import json

# Register your models here.

@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ['email', 'username', 'nome_completo', 'telefone', 'is_active', 'is_staff', 'date_joined']
    list_filter = ['is_active', 'is_staff', 'is_superuser', 'date_joined']
    search_fields = ['email', 'username', 'nome_completo', 'telefone']
    ordering = ['email']
    
    # Configuração dos campos para criar/editar usuários
    fieldsets = (
        (None, {'fields': ('email', 'username', 'password')}),
        ('Informações Pessoais', {'fields': ('nome_completo', 'telefone')}),
        ('Permissões', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Datas Importantes', {'fields': ('last_login', 'date_joined')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'username', 'password1', 'password2', 'nome_completo', 'telefone'),
        }),
    )

@admin.register(Metodo)
class MetodoAdmin(admin.ModelAdmin):
    list_display = ['metodo']
    search_fields = ['metodo']
    ordering = ['metodo']

@admin.register(ModeloLaudo)
class ModeloLaudoAdmin(admin.ModelAdmin):
    list_display = ['titulo', 'metodo', 'usuario', 'texto_preview', 'criado_em']
    list_filter = ['metodo', 'usuario', 'criado_em']
    search_fields = ['titulo', 'metodo__metodo', 'usuario__email', 'texto']
    ordering = ['-criado_em']
    readonly_fields = ['criado_em', 'atualizado_em']
    
    def texto_preview(self, obj):
        """Mostra preview do texto"""
        if obj.texto:
            preview = obj.texto[:100] + '...' if len(obj.texto) > 100 else obj.texto
            return format_html('<span title="{}">{}</span>', obj.texto, preview)
        return '-'
    texto_preview.short_description = 'Preview do Texto'
    
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('titulo', 'metodo', 'usuario')
        }),
        ('Conteúdo', {
            'fields': ('texto',),
            'description': 'Texto completo do modelo de laudo'
        }),
        ('Datas', {
            'fields': ('criado_em', 'atualizado_em'),
            'classes': ('collapse',)
        }),
    )

@admin.register(Frase)
class FraseAdmin(admin.ModelAdmin):
    list_display = ['tituloFrase', 'categoriaFrase', 'usuario', 'count_modelos', 'criado_em']
    list_filter = ['categoriaFrase', 'usuario', 'criado_em']
    search_fields = ['tituloFrase', 'categoriaFrase', 'usuario__email']
    ordering = ['-criado_em']
    filter_horizontal = ['modelos_laudo']
    readonly_fields = ['criado_em', 'atualizado_em', 'frase_formatada']
    
    def count_modelos(self, obj):
        """Conta quantos modelos estão associados"""
        return obj.modelos_laudo.count()
    count_modelos.short_description = 'Modelos'
    
    def frase_formatada(self, obj):
        """Mostra o JSON formatado de forma legível"""
        if obj.frase:
            return format_html('<pre>{}</pre>', json.dumps(obj.frase, indent=2, ensure_ascii=False))
        return '-'
    frase_formatada.short_description = 'Dados da Frase'
    
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('categoriaFrase', 'tituloFrase', 'usuario')
        }),
        ('Associação com Modelos', {
            'fields': ('modelos_laudo',),
            'description': 'Selecione os modelos de laudo associados a esta frase'
        }),
        ('Dados da Frase', {
            'fields': ('frase_formatada', 'frase'),
            'description': 'Os dados JSON da frase. Edite com cuidado!'
        }),
        ('Datas', {
            'fields': ('criado_em', 'atualizado_em'),
            'classes': ('collapse',)
        }),
    )

@admin.register(Variavel)
class VariavelAdmin(admin.ModelAdmin):
    list_display = ['tituloVariavel', 'usuario', 'tipo_variavel', 'criado_em']
    list_filter = ['usuario', 'criado_em']
    search_fields = ['tituloVariavel', 'usuario__email']
    ordering = ['-criado_em']
    readonly_fields = ['criado_em', 'atualizado_em', 'variavel_formatada']
    
    def tipo_variavel(self, obj):
        """Mostra o tipo da variável baseado no JSON"""
        if obj.variavel and isinstance(obj.variavel, dict):
            return obj.variavel.get('tipo', 'N/A')
        return 'N/A'
    tipo_variavel.short_description = 'Tipo'
    
    def variavel_formatada(self, obj):
        """Mostra o JSON formatado de forma legível"""
        if obj.variavel:
            return format_html('<pre>{}</pre>', json.dumps(obj.variavel, indent=2, ensure_ascii=False))
        return '-'
    variavel_formatada.short_description = 'Dados da Variável'
    
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('tituloVariavel', 'usuario')
        }),
        ('Dados da Variável', {
            'fields': ('variavel_formatada', 'variavel'),
            'description': 'Os dados JSON da variável. Edite com cuidado!'
        }),
        ('Datas', {
            'fields': ('criado_em', 'atualizado_em'),
            'classes': ('collapse',)
        }),
    )
