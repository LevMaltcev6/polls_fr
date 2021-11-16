from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()


class UniqueTogetherValidator:

    def _validate_unique_together_for_null_fields(self, query):
        if self.__class__.objects.filter(**query).exists():
            raise ValueError('Value not unique')


class Poll(models.Model):
    """
    Poll model
    """
    name = models.CharField(max_length=256)
    start_date = models.DateTimeField(editable=False, auto_now_add=True)
    end_date = models.DateTimeField()
    description = models.TextField()
    is_published = models.BooleanField(default=False)

    class Meta:
        verbose_name_plural = "Опросы"
        verbose_name = "Опрос"

    def __str__(self):
        return self.name


class Question(models.Model):
    """
    Question model
    """
    class QuestionType(models.TextChoices):
        text = "text", "Text answer"
        single_choice = "single_choice", "single option"
        multi_choice = 'multi_choice', "many options"

    poll = models.ForeignKey('polls.Poll', on_delete=models.CASCADE, related_name='questions')
    text = models.TextField()
    type = models.CharField(max_length=256, choices=QuestionType.choices, default=QuestionType.text)

    @property
    def has_choice(self):
        return self.type in [self.QuestionType.multi_choice, self.QuestionType.single_choice]

    class Meta:
        unique_together = (('poll', 'text'),)

    def __str__(self):
        return self.text


class ChoiceAnswer(models.Model):
    """
    Choices of answer models
    """
    question = models.ForeignKey('polls.Question', on_delete=models.CASCADE, related_name='choices')
    text = models.TextField()

    class Meta:
        unique_together = (('text', 'question'), )

    def __str__(self):
        return self.text


class Answer(models.Model, UniqueTogetherValidator):
    """
    Answer model
    """
    question = models.ForeignKey('polls.Question', on_delete=models.CASCADE, related_name='answers')
    text = models.TextField(null=True, blank=True)
    choice = models.ManyToManyField(ChoiceAnswer, blank=True)

    user = models.ForeignKey(User, on_delete=models.RESTRICT, null=True)
    anonymous_id = models.IntegerField(null=True)

    def save(self, force_insert=False, force_update=False, using=None,
             update_fields=None):
        """
        Save with db level validation of correct user
        """
        if self.user and self.anonymous_id:
            raise ValueError('Cant use user auth and anonymous token both')

        self._validate_unique_together_for_null_fields({
            'user': self.user,
            'anonymous_id': self.anonymous_id,
            'question': self.question
        })
        return super().save(force_insert, force_update, using, update_fields)

    class Meta:
        unique_together = (('user', 'anonymous_id', 'question'), )

    def __str__(self):
        return f'answer of {self.user or self.anonymous_id} for {self.question}'
