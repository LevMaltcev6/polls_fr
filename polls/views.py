from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils.timezone import now
from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework import status
from rest_framework import viewsets, mixins
from rest_framework.response import Response

from rest_framework.exceptions import ValidationError

from polls import serializers
from polls.models import Poll, Question
from polls.permissions import UserPollsPermission
from polls.serializers import PollAdminSerializer, QuestionSerializer, UserPollSerializer, \
    UserPollShowSerializer
from rest_framework import permissions


class PollAdminViewSet(viewsets.ModelViewSet):
    """
    CRUD for polls. admin api
    """
    model = Poll
    queryset = Poll.objects.all()
    serializer_class = PollAdminSerializer
    permission_classes = [permissions.IsAdminUser]

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, *kwargs)


class QuestionAdminViewSet(viewsets.ModelViewSet):
    """
    CRUD for questions with choices. admin api
    """
    model = Question
    queryset = Question.objects.all().select_related('poll').prefetch_related('choices')
    permission_classes = [permissions.IsAdminUser]
    serializer_class = serializers.QuestionSerializer
    http_method_names = ['get', 'post', 'head', 'options', 'delete', 'put']

    def __init__(self, *args, **kwargs):
        self.poll = None
        super().__init__(*args, **kwargs)

    def initial(self, request, *args, **kwargs):
        """
        Add poll existing validation on initial
        """
        self.poll = get_object_or_404(Poll.objects.all(), pk=kwargs['poll_pk'])
        return super().initial(request, *args, **kwargs)

    def get_queryset(self):
        self.queryset = self.queryset.filter(poll=self.poll)
        return super().get_queryset()

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        if self.poll.is_published:
            raise ValidationError('Poll already published and cannot be changed')
        return super().destroy(request, *args, **kwargs)


class UserPolls(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = Poll.objects.all().prefetch_related('questions', 'questions__choices', 'questions__answers')
    permission_classes = (UserPollsPermission, )

    def get_queryset(self):
        return self.queryset.filter(start_date__lt=now(), end_date__gt=now(), is_published=True)

    def get_serializer_class(self):
        if self.action == 'list':
            return PollAdminSerializer
        elif self.action == 'retrieve':
            return QuestionSerializer
        elif self.action == 'show_answers':
            return UserPollShowSerializer
        return UserPollSerializer

    @transaction.atomic
    def vote_in_poll(self, request, *args, **kwargs):
        """
        Send answers
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def list(self, request, *args, **kwargs):
        """Get list of polls"""
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        """Get list of poll's questions"""
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        parameters=[
            OpenApiParameter(name='anonymous_id', required=False,
                             type=int, description='anonymous_id for anonymous user')
        ]
    )
    def show_answers(self, request, *args, **kwargs):
        """Get history of user's polls"""
        return super().list(request, *args, **kwargs)
