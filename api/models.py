from django.db import models
from django.contrib.auth.models import AbstractUser

class CustomUser(AbstractUser):
    email = models.EmailField(unique=True)
    nome_completo = models.CharField(max_length=255)
    telefone = models.CharField(max_length=20)
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'nome_completo']

    def __str__(self):
        return self.email

class Metodo(models.Model):
    metodo = models.CharField(max_length=100)
    
    def __str__(self):
        return self.metodo

class ModeloLaudo(models.Model):
    titulo = models.CharField(max_length=255)
    texto = models.TextField()
    metodo = models.ForeignKey(Metodo, on_delete=models.CASCADE)
    usuario = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.titulo

class Frase(models.Model):
    categoriaFrase = models.CharField(max_length=100)
    tituloFrase = models.CharField(max_length=100)
    frase = models.JSONField()
    modelos_laudo = models.ManyToManyField(ModeloLaudo, blank=True)
    usuario = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.tituloFrase} - {self.categoriaFrase}"

class Variavel(models.Model):
    tituloVariavel = models.CharField(max_length=255)
    variavel = models.JSONField()
    usuario = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.tituloVariavel
