from polls import views
from django.urls import path, include
from rest_framework_nested import routers


polls = routers.DefaultRouter()
polls.register(r'admin', views.PollAdminViewSet, basename="poll_admin")

admin_questions = routers.NestedSimpleRouter(polls, r'admin', lookup='poll')
admin_questions.register(r'questions', views.QuestionAdminViewSet, basename='poll-question')

polls.register('user', views.UserPolls, basename='poll_user')

urlpatterns = [
    path("", include(polls.urls)),
    path("", include(admin_questions.urls)),
    path('user/<pk>', views.UserPolls.as_view({'post': 'vote_in_poll'})),
    path('user/show_answers', views.UserPolls.as_view({'get': 'show_answers'})),
]
