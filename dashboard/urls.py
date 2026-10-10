"""
URL configuration for the dashboard application.
"""

from django.urls import path
from . import views

urlpatterns = [
    path('', views.inbox_view, name='inbox'),
    path('message/<int:message_id>/', views.message_detail_view, name='message_detail'),
    path('message/<int:message_id>/approve/', views.approve_draft_view, name='approve_draft'),
    path('message/<int:message_id>/edit-draft/', views.edit_draft_view, name='edit_draft'),
    path('message/<int:message_id>/regenerate-draft/', views.regenerate_draft_view, name='regenerate_draft'),
    path('message/<int:message_id>/assign/', views.assign_message_view, name='assign_message'),
    path('message/<int:message_id>/update-status/', views.update_status_view, name='update_status'),
    path('message/<int:message_id>/add-note/', views.add_note_view, name='add_note'),
    path('analytics/', views.daily_summary_view, name='daily_summary'),
    path('knowledge-base/', views.knowledge_base_view, name='knowledge_base'),
    path('routing-rules/', views.routing_rules_view, name='routing_rules'),
    path('integrations/', views.integrations_view, name='integrations'),
    path('simulate-ingest/', views.simulate_ingest_view, name='simulate_ingest'),
]
