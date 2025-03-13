from django.urls import path
from . import views

urlpatterns = [
    path('hello/', views.hello, name='hello'),
    path('todos/', views.todo_list, name='todo_list'),
    path('todos/<int:pk>/', views.todo_detail, name='todo_detail'),
]
