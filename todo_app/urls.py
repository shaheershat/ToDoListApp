from django.urls import path
from tasks import views

urlpatterns = [
    path('', views.index, name='home'),
    path('save-email/', views.save_email, name='save_email'),
    path('save-tasks/', views.save_tasks, name='save_tasks'),
    path('get-tasks-by-date/', views.get_tasks_by_date, name='get_tasks_by_date'),
]
