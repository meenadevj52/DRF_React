'''Base permission'''

# Lib imports
from guardian.shortcuts import assign_perm, remove_perm, get_objects_for_user
from rest_framework.exceptions import APIException
from rest_framework.permissions import (BasePermission as DRFBasePermission,
                                  IsAuthenticated)

# App imports
from bpapp.api3 import exceptions
from bpapp.models import BpUser, Project, Analysis, Sample, Host
from bpapp.share import Share

class BasePermission(DRFBasePermission):
  '''Base permission'''

  def has_permission(self, request, view):
    '''request view permission check fallback'''
    return IsAuthenticated.has_permission(self, request, view) or request.user.is_superuser

  def has_object_permission(self, request, view, obj):
    '''object level permission check fallback'''
    user = request.user
    return user.is_superuser or getattr(self, f'_{request.method.lower()}')(request, user, obj)

  def _get(self, request, user, obj):
    '''read detail access'''
    return self.has_access(user, obj)

  def _post(self, request, user, obj):  # pylint: disable=unused-argument, no-self-use
    '''create detail access'''
    return user.is_active

  def _patch(self, request, user, obj):
    '''update detail access'''
    return self.can_edit(user, obj)

  def _put(self, request, user, obj):
    '''update detail access'''
    BasePermission._patch(self, request, user, obj)

  def _delete(self, request, user, obj):
    '''delete detail access'''
    return self.can_delete(user, obj)

  def _options(self, request, user, obj):  # pylint: disable=unused-argument
    '''option detail access'''
    return BasePermission._post(self, request, user, obj)

  @staticmethod
  def check_updating_su_fields(request, obj, forbidden_fields):  # pylint: disable=arguments-differ
    '''Check if a non superuser is attempting to update a field that shouldn't'''
    user = request.user
    data = request.data.copy()
    if not user.is_superuser:
      for field_name, field_type in forbidden_fields:
        field_value = data.get(field_name, None)
        field_value = field_type(field_value)
        value = obj.serializable_value(field_name)
        if field_value and value:
          is_float = field_type == float
          if (is_float and float(value) != float(field_value)) \
                  or (not is_float and value != field_value):
            raise exceptions.NotAuthorized('You are not authorized to make this update.')

  @staticmethod
  def is_moving_or_copying(request, obj, project_ids, params):  # pylint: disable=arguments-differ
    '''Check if the user is moving or copying obj'''
    old_projects_ids = obj.projects.filter(
      deleted_on__isnull=True
    ).values_list('pk', flat=True)

    new_projects = Project.objects.filter(
      pk__in=project_ids, deleted_on__isnull=True
    ).exclude(pk__in=old_projects_ids)

    return params.get('old_project_id') \
      or params.get('new_project_id') \
      or new_projects

  @staticmethod
  def can_move_or_copy(request, obj, project_ids, params):  # pylint: disable=arguments-differ
    '''Check if user can move or copy object'''

    # get new project
    old_projects_ids = obj.projects.filter(
      deleted_on__isnull=True
    ).values_list('pk', flat=True)

    new_projects = Project.objects.filter(
      pk__in=project_ids,
      deleted_on__isnull=True
    ).exclude(pk__in=old_projects_ids)

    user = request.user
    # if adding project via 'new_project_id', add it to new_projects
    if params.get('new_project_id'):
      new_projects = new_projects.union(
        Project.objects.filter(id=params['new_project_id'])
      )

    return BasePermission.has_auth_on_all_objs(['admin'], user, new_projects) \
      and (
        BasePermission.is_owner_or_admin(user, obj) \
        or BasePermission.has_project_perms(['admin'], user, obj)
      )

  @staticmethod
  def update_obj_perms(request, obj, data):  # pylint: disable=arguments-differ
    '''Update guardian perms (and shared_with)'''
    new_shared_with = data.get('info').get('shared_with', {})

    old_info = obj.info or {}
    old_shared_with = old_info.get('shared_with', {})

    for user_key, perm in new_shared_with.items(): # pylint: disable=too-many-nested-blocks
      new_perm = perm.get('permission')
      old_perm = old_shared_with.get(user_key, {}).get('permission', None)

      # if the perm has been changed
      if new_perm != old_perm:
        if user_key.isnumeric():
          try:
            user = BpUser.objects.get(id=user_key)
          except BpUser.DoesNotExist:
            user = None
        else:
          user = BpUser(email=user_key)

        # if is not the owner
        if obj.owner != user:
          # if new perm is None then remove permission
          if new_perm == 'None':
            for perm_item in ['view', 'edit', 'admin']:
              if user and user.id:
                remove_perm(perm_item, user, obj)
            Share.remove_shared_with_for_user(user_key, obj)
          else:
            if user.id:
              remove_perm(old_perm, user, obj)
              assign_perm(new_perm, user, obj)
            Share.assign_shared_with(new_perm, user, obj)
        obj.save()

  @staticmethod
  def has_project_perms(perms, user, obj, include_public=False):
    '''Check if user has auth on obj'''
    if hasattr(obj, 'projects'):
      owner_projects = obj.projects.filter(
        deleted_on__isnull=True,
        owner=user
      ).values_list('pk', flat=True)

      public_projects = Project.objects.none()  # Empty queryset to avoid union error on line:316
      if include_public:
        public_projects = obj.projects.filter(
          deleted_on__isnull=True,
          visibility='public'
        ).values_list('pk', flat=True)

      shared_projects = get_objects_for_user(
        user, perms, Project,
        any_perm=True
      ).values_list('pk', flat=True)

      combined_projects = owner_projects.union(public_projects, shared_projects)

      return obj.projects.filter(
        pk__in=combined_projects,
        deleted_on__isnull=True
      ).exists()
    return False

  @staticmethod
  def assign_obj_perms(obj, permission_data, request):
    '''Assigning guardian perms (and shared_with)'''
    # on Analysis, Project and Sample

    # maybe check if perm is a valid permission here
    # by getting all of the different object permissions
    perm = permission_data.get('perm')
    user_emails = [
      email for email in permission_data.get('emails', []) if email # skip empty email
    ]

    # check user emails exist
    if user_emails is None:
      raise APIException('Please enter at least one email to share with.')

    for email in user_emails:
      # if the user tries to share with himself
      if email == request.user.email:
        raise APIException('You can\'t share with yourself.')

      try:
        user = BpUser.objects.get(email=email, deleted_on__isnull=True)
      except BpUser.DoesNotExist:
        user = BpUser(email=email) # emails is not an user yet

      # edge case if the sharee is owner of obj, no need to assign perms
      if obj.owner != user:
        # assign_guardian_permissions(perm, user, obj) # assign the guardian permission to the user
        if user.id:
          assign_perm(perm, user, obj) # assign the guardian permission to the user

        Share.assign_shared_with(perm, user, obj) # assign the shared_with property of the obj

  @staticmethod
  def has_sample_analysis_perms(perms, user, project):
    '''Check if user (who is not an owner) has permission for any of a projects samples or analyses'''

    # therefore the user can still access the shared samples/analyses even though he does not have permission for the project itself
    owner_samples = project.samples.filter(
      deleted_on__isnull=True,
      owner=user
    ).values_list('pk', flat=True)

    owner_analyses = project.analyses.filter(
      deleted_on__isnull=True,
      owner=user
    ).values_list('pk', flat=True)

    shared_analyses = get_objects_for_user(
      user, perms, Analysis,
      any_perm=True
    ).values_list('pk', flat=True)

    shared_samples = get_objects_for_user(
      user, perms, Sample,
      any_perm=True
    ).values_list('pk', flat=True)

    combined_samples = owner_samples.union(shared_samples)
    combined_analyses = owner_analyses.union(shared_analyses)

    return project.visibility == 'public' \
      or project.samples.filter(
        pk__in=combined_samples,
        deleted_on__isnull=True
      ).exists() \
      or project.analyses.filter(
        pk__in=combined_analyses,
        deleted_on__isnull=True
      ).exists()

  @staticmethod
  def is_owner(user, obj):
    '''Check if user is owner of the obj'''
    return hasattr(obj, 'owner') and obj.owner == user

  @staticmethod
  def is_owner_or_admin(user, obj):
    '''Check if user is owner or admin of the obj'''
    return BasePermission.is_owner(user, obj) or user.has_perm('admin', obj)

  @staticmethod
  def is_manager(domain, user):
    '''Check if user is manager of the domain'''
    return Host.objects.filter(
      domain=domain,
      hostsmembers__role='manager',
      hostsmembers__user=user
    ).exists()

  @staticmethod
  def can_delete(user, obj):
    '''Check if user can delete object'''
    return BasePermission.is_owner_or_admin(user, obj)

  @staticmethod
  def can_edit(user, obj):
    '''Check if user can edit object'''
    return BasePermission.is_owner(user, obj) \
      or user.has_perm('edit', obj) \
      or user.has_perm('admin', obj)

  @staticmethod
  def can_share(user, obj):
    '''Check if user can share object'''
    return BasePermission.can_delete(user, obj) \
        or BasePermission.has_project_perms(['admin'], user, obj) \

  @staticmethod
  def can_view_user(request, user):
    '''Check if user can view other user'''

    # function for viewing other users that shared data with you
    # req_user: the user making the request to view user
    # user: the user being requested to be viewed

    req_user = request.user
    domain = request.get_host()

    return (
      # if user has shared data with req_user
      Project.objects.filter(
        info__shared_with__has_key=str(req_user.id),
        owner=user,
        deleted_on__isnull=True
      ).exists()
      or Sample.objects.filter(
        info__shared_with__has_key=str(req_user.id),
        owner=user,
        deleted_on__isnull=True
      ).exists()
      or Analysis.objects.filter(
        info__shared_with__has_key=str(req_user.id),
        owner=user,
        deleted_on__isnull=True
      ).exists()

      # if req_user has shared data with user
      or Project.objects.filter(
        info__shared_with__has_key=str(user.id),
        owner=req_user,
        deleted_on__isnull=True
      ).exists()
      or Sample.objects.filter(
        info__shared_with__has_key=str(user.id),
        owner=req_user,
        deleted_on__isnull=True
      ).exists()
      or Analysis.objects.filter(
        info__shared_with__has_key=str(user.id),
        owner=req_user,
        deleted_on__isnull=True
      ).exists()

      # if a different user has shared data with both user and req_user
      or Project.objects.filter(
        info__shared_with__has_key=str(req_user.id),
        deleted_on__isnull=True
      ).filter(
        info__shared_with__has_key=str(user.id)
      ).exists()
      or Sample.objects.filter(
        info__shared_with__has_key=str(req_user.id),
        deleted_on__isnull=True
      ).filter(
        info__shared_with__has_key=str(user.id)
      ).exists()
      or Analysis.objects.filter(
        info__shared_with__has_key=str(req_user.id),
        deleted_on__isnull=True
      ).filter(
        info__shared_with__has_key=str(user.id)
      ).exists()

      or (BasePermission.is_manager(domain, req_user) and Host.objects.filter(
        domain=domain,
        hostsmembers__user=user
      ).exists())
    )

  @staticmethod
  def has_access(user, obj, is_project=False):
    '''Check if user has access to obj'''
    return user.has_perm('view', obj) \
      or BasePermission.can_edit(user, obj) \
      or (is_project and BasePermission.has_sample_analysis_perms(
        ['view', 'edit', 'admin'], user, obj
      ))

  @staticmethod
  def has_auth_on_all_objs(perms, user, objs):
    '''Check if user has auth on all objs'''
    for obj in objs:
      has_auth_for_obj = False
      for perm in perms:
        if BasePermission.is_owner(user, obj) or user.has_perm(perm, obj):
          has_auth_for_obj = True
          break

      if not has_auth_for_obj:
        return False
    return True

  @staticmethod
  def get(user, obj):
    '''Get user permission for object'''
    if BasePermission.can_delete(user, obj) or BasePermission.has_project_perms(['admin'], user, obj):
      permission = 'admin'
    elif BasePermission.can_edit(user, obj) or BasePermission.has_project_perms(['edit'], user, obj):
      permission = 'edit'
    else:
      permission = Share.get_perm_by_user_id(user.id, obj)

    return permission

  @staticmethod
  def get_host_by_domain(domain):
    '''Get host from request'''
    try:
      host = Host.objects.get(domain=domain)
    except Host.DoesNotExist:
      host = Host.get_default_host()
    return host
