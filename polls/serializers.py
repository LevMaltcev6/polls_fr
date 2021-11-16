from typing import Dict, List

from django.db import transaction
from django.db.models import Q
from django.db.utils import IntegrityError
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from polls.models import Poll, ChoiceAnswer, Question, Answer


class PollAdminSerializer(serializers.ModelSerializer):
    """
    Standard Poll serializer
    """
    class Meta:
        model = Poll
        fields = '__all__'


class ChoiceSerializer(serializers.ModelSerializer):
    """
    Serialize choices for questions
    """

    class Meta:
        model = ChoiceAnswer
        exclude = ('question',)


class QuestionSerializer(serializers.ModelSerializer):
    """
    Serialize question
    """
    choices = ChoiceSerializer(many=True, required=False, allow_null=True)

    class Meta:
        model = Question
        fields = ['id', 'text', 'type', 'choices']

    def validate(self, attrs):
        """
        Validate Choices: unique and count
        """
        if choices := attrs.get('choices'):
            choices = [frozenset(choice.items()) for choice in choices]
            choices_set = set(choices)
            if len(choices) != len(choices_set):
                raise ValidationError('Choices values must be unique')
        return super().validate(attrs)

    def create(self, validated_data):
        """
        Create question with choices
        """
        choices = validated_data.pop('choices', [])
        poll = Poll.objects.get(pk=self.context['view'].kwargs['poll_pk'])

        if poll.is_published:
            raise ValidationError('Cant update published poll')

        try:
            question = Question.objects.create(**validated_data, poll=poll)
        except IntegrityError:
            raise ValidationError('This question exists in the poll')

        if question.has_choice:
            if question.type == question.QuestionType.single_choice and len(choices) != 1:
                raise ValidationError('Single choice allow only one choice')

        self._save_choices(question, choices)
        return question

    def update(self, instance, validated_data):
        if instance.poll.is_published:
            raise ValidationError('Cant update published poll')

        for choice in instance.choices.all():
            choice.delete()

        choices = validated_data.pop('choices', [])
        self._save_choices(instance, choices)
        return super().update(instance, validated_data)

    @staticmethod
    def _save_choices(question: Question, choices: List) -> None:
        """
        Save choices for save and update methods

        :param question: created question object
        :param choices: list of choices for question object
        """
        def add_question(choice: Dict, question=question):
            choice['question'] = question
            return choice

        if choices:
            choices = list(map(add_question, choices))
            ChoiceAnswer.objects.bulk_create(
                [ChoiceAnswer(**choice) for choice in choices]
            )


class QuestionForUserSerializer(serializers.ModelSerializer):
    choices = ChoiceSerializer(many=True, required=False)

    class Meta:
        model = Question
        fields = "__all__"


# Answer serializer
class AnswerSerializer(serializers.ModelSerializer):
    """
    Serialize user answer
    """

    def validate(self, attrs):
        """
        Validate user answer by count of choices
        """
        question_type = attrs['question'].type
        if question_type == Question.QuestionType.text:
            if attrs.get("choice") is not None:
                raise ValidationError("This is text question, not choice")

        elif question_type == Question.QuestionType.single_choice:
            if len(attrs.get("choice")) > 1 or attrs.get('text') is not None:
                raise ValidationError("This question only for one choice and choice field not contains text")

        elif question_type == Question.QuestionType.multi_choice:
            if attrs.get('text') is not None:
                raise ValidationError("Choice field not contains text")

        return attrs

    class Meta:
        model = Answer
        exclude = ('anonymous_id', 'user', )


class UserPollSerializer(serializers.ModelSerializer):
    answers = AnswerSerializer(many=True)
    anonymous_id = serializers.IntegerField(allow_null=True)

    def validate(self, attrs):
        """
        Add question validation
        """
        for answer in attrs['answers']:
            if self.context['view'].kwargs['pk'] != str(answer['question'].poll_id):
                raise ValidationError('Invalid question id for this poll')

        poll = self.context['view'].queryset.get(pk=self.context['view'].kwargs['pk'])
        if poll.questions.count() != len(attrs['answers']):
            raise ValidationError('pls answer the all questions')
        questions = [answer['question'] for answer in attrs['answers']]
        if set(questions) != set(poll.questions.all()):
            raise ValidationError('Invalid question ids for this poll')
        return attrs

    def create(self, validated_data):
        answers = validated_data.pop('answers')
        answers_db = []
        for answer in answers:
            with transaction.atomic():
                choice = answer.pop('choice', None)
                try:
                    answer = Answer.objects.create(
                        user=user if ((user := self.context['request'].user) and user.is_authenticated) else None,
                        anonymous_id=validated_data.get('anonymous_id'),
                        **answer
                    )
                    if choice:
                        answer.choice.add(*choice)
                    answers_db.append(answer)
                except ValueError as err:
                    raise ValidationError(str(err))

        result = {'answers': answers_db}
        if anonymous_id := validated_data.get('anonymous_id'):
            result.update({'anonymous_id': anonymous_id})

        return result

    class Meta:
        model = Poll
        fields = ('answers', 'anonymous_id', )


class UserAnswerHistorySerializer(serializers.ModelSerializer):
    choice = ChoiceSerializer(many=True, required=False)

    class Meta:
        model = Answer
        exclude = ['question']


class UserQuestionHistorySerializer(serializers.ModelSerializer):
    answers = serializers.SerializerMethodField('get_answers')

    @extend_schema_field(UserAnswerHistorySerializer)
    def get_answers(self, question):
        anonymous_id = self.context['request'].query_params.get('anonymous_id')
        qs = Answer.objects.filter(
            Q(user=(self.context['request'].user if self.context['request'].user.is_authenticated else None)) &
            Q(anonymous_id=anonymous_id), question=question)
        serializer = UserAnswerHistorySerializer(instance=qs, many=True, required=False)
        return serializer.data

    class Meta:
        model = Question
        exclude = ['poll']


class UserPollShowSerializer(serializers.ModelSerializer):
    questions = UserQuestionHistorySerializer(many=True)

    class Meta:
        model = Poll
        fields = '__all__'
