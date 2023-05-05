'''Analysis permission'''

# App imports
from bpapp.api3.resources.base_permission import BasePermission
from bpapp.models import Project, Sample

class AnalysisPermission(BasePermission):
  '''Analysis base permission'''

  def has_object_permission(self, request, view, obj):
    '''object level permission check fallback'''
    return BasePermission.is_owner(request.user, obj) \
      or super().has_object_permission(request, view, obj)

  def _post(self, request, user, obj):
    '''create detail access'''
    return self.can_analyze(user, request.data)

  def _patch(self, request, user, obj):
    '''update detail access'''
    return user.has_perm('edit', obj) \
      or user.has_perm('admin', obj) \
      or BasePermission.has_project_perms(['edit', 'admin'], user, obj)

  def _put(self, request, user, obj):
    '''update detail access'''
    AnalysisPermission._patch(self, request, user, obj)

  def _delete(self, request, user, obj):
    '''delete detail access'''
    return user.has_perm('admin', obj) \
      or BasePermission.has_project_perms(['admin'], user, obj)

  @staticmethod
  def can_analyze(user, data):
    '''Check if user can analyze'''

    # If not for either, raise an error
    # The projects the user is trying to add the analysis to.
    # On the UI, this would only be the active project, but if the user
    # is using the API directly, he can request to add the analysis to any
    # projects he wishes. We need to check that he has permission to add to
    # each of these projects, as well as has perm on each sample
    projects_ids = data.get('projects', [])
    projects = Project.objects.filter(pk__in=projects_ids) or [user.active_project]

    # projects the user does not own and has no edit permission for
    no_auth_projects = [
      project for project in projects if not BasePermission.can_edit(user, project)
    ]

    if no_auth_projects:
      # first check that user has auth for each sample
      samples_ids = data.get('samples', [])
      samples = Sample.objects.filter(pk__in=samples_ids)
      for sample in samples:
        if not BasePermission.can_edit(user, sample):
          return False

      # now check that each no_auth_project is the project of at
      # least one of the samples
      sample_projects_ids = Project.objects.filter(
        samples__in=list(samples)
      ).values_list('pk', flat=True).distinct()

      for project in no_auth_projects:
        if project.id not in sample_projects_ids:
          return False

    return True


class SamplePermission(BasePermission):
  '''Sample base permission'''

  def has_object_permission(self, request, view, obj):
    '''object level permission check fallback'''
    return BasePermission.is_owner(request.user, obj) \
      or super().has_object_permission(request, view, obj)

  def _get(self, request, user, obj):
    '''read detail access'''
    return user.has_perm('view', obj) \
      or user.has_perm('edit', obj) \
      or user.has_perm('admin', obj) \
      or BasePermission.has_project_perms(
        ['view', 'edit', 'admin'], user, obj,
        include_public=True
      )

  def _post(self, request, user, obj):
    '''create detail access'''
    return self.can_add_sample(user, request.data)

  def _patch(self, request, user, obj):
    '''update detail access'''
    return user.has_perm('edit', obj) \
      or user.has_perm('admin', obj) \
      or BasePermission.has_project_perms(['edit', 'admin'], user, obj)

  def _put(self, request, user, obj):
    '''update detail access'''
    SamplePermission._patch(self, request, user, obj)

  def _delete(self, request, user, obj):
    '''delete detail access'''
    return user.has_perm('admin', obj) \
      or BasePermission.has_project_perms(['admin'], user, obj)

  @staticmethod
  def can_add_sample(user, data):
    '''Check if user can add a sample'''
    #(i.e. owns projects, has edit perm on projects, or combination of both)
    projects_ids = data.get('projects') or []
    projects = Project.objects.filter(pk__in=projects_ids) or [user.active_project]
    return BasePermission.has_auth_on_all_objs(
      ['edit', 'admin'], user, projects
    )