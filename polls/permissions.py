from rest_framework.permissions import BasePermission


class UserPollsPermission(BasePermission):

    def has_permission(self, request, view):
        if view.action in ['vote_in_poll', 'show_answers']:
            is_anonymous_id = bool(request.query_params.get('anonymous_id')) or bool(request.data.get('anonymous_id'))
            if request.user.is_authenticated == is_anonymous_id:
                return False
        return True
