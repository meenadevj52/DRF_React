
class AnalysisFilterSet(FilterSet):
  '''Analysis filterset'''

  class Meta:
    model = Analysis
    fields = {
      'date_created': ['gte', 'lte'],
      'id': ['exact', 'icontains'],
      # 'info': ['iregex'],
      'last_updated': ['gte', 'lte'],
      'name': ['icontains'],
      'owner': ['exact'],
      'owner__id': ['exact'],
      'owner__username': ['icontains'],
      'controls': ['exact'],
      'controls__id': ['exact'],
      'controls__name': ['icontains'],
      'projects': ['exact'],
      'samples': ['exact'],
      'samples__id': ['exact'],
      'samples__name': ['icontains'],
      'status': ['icontains', 'iregex', 'in'],
      'workflow': ['exact'],
      'workflow__id': ['exact'],
      'workflow__name': ['icontains'],
    }


class AnalysisViewSet(BaseViewSet):  # pylint: disable=too-many-ancestors
  '''Analysis viewset'''
  queryset = Analysis.objects.all()
  serializer_class = AnalysisSerializer
  ordering = [
    'completed_on',
    'controls',
    'date_created',
    'filesize',
    'id',
    'last_updated',
    'name',
    'owner',
    'samples',
    'started_on',
    'status',
  ]
  filterset_class = AnalysisFilterSet
  permission_classes = [AnalysisPermission]

  def create(self, request, *args, **kwargs):  # pylint: disable=too-many-locals
    '''Override obj create'''
    user = request.user
    if not user.id:
      user = BpUser.objects.get(pk=1)
    payloads = request.data.copy()

    source = (payloads.get('meta', {}) or {}).get('source')
    pipeline_id = (payloads.get('workflow') or '').split('/').pop()
    if source == 'cli' and int(pipeline_id) in PIPELINE_NOT_ALLOWED_FROM_CLI:
      data = {
        'error': f'Analysis of pipeline id - {pipeline_id} cannot be started from CLI.'
      }
      return Response(data=data, status=status.HTTP_403_FORBIDDEN)

    pipeline_validator = PipelineValidator(payloads)
    validation_result = pipeline_validator.validate_all()
    error = validation_result.get('error')
    warning = validation_result.get('warning')

    if error or warning:
      data = {'error': validation_result}
      return Response(data=data, status=status.HTTP_400_BAD_REQUEST)

    payloads['owner'] = user.pk
    if isinstance(payloads['workflow'], str):
      payloads['workflow'] = payloads['workflow'].replace('workflows', 'pipelines')

    serializer = self.get_serializer(data=payloads)
    serializer.is_valid(raise_exception=True)
    obj = serializer.save()

    obj.status = 'waiting-in-queue'
    obj.meta = {'source': source or 'web', **(getattr(obj, 'meta', {}) or {})}
    try:
      obj.host = Host.objects.get(domain=request.get_host())
    except Host.DoesNotExist:
      member_of = HostsMembers.objects.filter(user=user).order_by('-created_on')[0]
      obj.host = member_of.host
    except IndexError:
      obj.host = None
    obj.save()

    self.set_name(obj)

    api_cfg = settings.CONFIG.get('api', {})
    host = obj.host or Host.get_host_by_domain(api_cfg.get('host', ''))

    queue_cfg = (host.config or {}).get('queue', {})
    queue_settings = queue_cfg.get('settings', {})
    queue_name = queue_settings.get('instance_queue', f'instance-{settings.MODE}')
    queue = SQS({
      'credentials': queue_cfg.get('credentials'),
      'queue': queue_name,
      'region': queue_settings.get('region'),
    })
    res = queue.send_message({
      'action': 'start-analysis',
      'analysis_id': obj.id,
      'host': request.get_host()
    })
    if isinstance(res, dict) and res.get('error'):
      msg = f"Cannot connect to analysis q from api:\n{res.get('detail')}"
      if settings.MODE in ['prod', 'test']:
        raise Exception(msg)
      print(msg)

    # update projects if different project list was given
    projects = serializer.validated_data['projects']
    update_projects(obj, projects)
    serializer = self.get_serializer(obj)
    return Response(data=serializer.data, status=status.HTTP_201_CREATED)

  def update(self, request, *args, **kwargs):  # pylint: disable=too-many-locals
    '''Override obj update'''
    user = request.user
    payloads = request.data.copy()
    params = request.GET.get('params', '{}')
    if params:
      params = json.loads(params)

    if isinstance(payloads['workflow'], str):
      payloads['workflow'] = payloads['workflow'].replace('workflows', 'pipelines')

    obj = self.get_object()
    self.set_name(obj)

    # sharing validations - only owners/admins can share
    cannot_share = not BasePermission.can_share(user, obj)
    if Share.is_sharing(bundle=None, params=params) and cannot_share:
      raise exceptions.NotAuthorized('You are not authorized to share this sample.')

    # moving validations - only owners/admins can move analyses between projects
    project_ids = dict(payloads)['projects']
    is_moving_copy = BasePermission.is_moving_or_copying(request, obj, project_ids, params)
    cannot_move_copy = not BasePermission.can_move_or_copy(request, obj, project_ids, params)
    if not user.is_superuser and is_moving_copy and cannot_move_copy:
      raise exceptions.NotAuthorized('You are not authorized to move/copy this sample.')

    # if analysis is to be shared
    permission_data = params.get('permission_data')
    if permission_data:
      BasePermission.assign_obj_perms(obj, permission_data, request)

      # if user chose to share all of the analysis's samples
      if permission_data.get('share_related'):
        samples = obj.samples.filter(deleted_on__isnull=True)
        for sample in samples:
          BasePermission.assign_obj_perms(sample, permission_data, request)

    # if analysis permissions are to be changed
    elif params.get('update_permissions'):
      BasePermission.update_obj_perms(request, obj, params)

    else:
      serializer = self.get_serializer(obj, data=payloads)
      serializer.is_valid(raise_exception=True)
      obj = serializer.save()

      # if we are moving an analysis from one project to another, remove the original project from the analysis
      if params.get('old_project_id'):
        obj.projects.remove(params['old_project_id'])
      if params.get('new_project_id'):
        obj.projects.add(params['new_project_id'])

    serializer = self.get_serializer(obj)
    return Response(data=serializer.data, status=status.HTTP_204_NO_CONTENT)

  def retrieve(self, request, *args, **kwargs):
    '''Override obj retrieve'''
    user = request.user
    obj = self.get_object()

    # Look for analysis files to check if we need to update the self signed
    if obj:
      api_cfg = settings.CONFIG.get('api', {})
      host = obj.host or Host.get_host_by_domain(api_cfg.get('host', ''))

      # set analysis host if not available
      if not obj.host:
        obj.host = host
        obj.save()

      # we only check for signing url if user is not decider
      if user.username != 'da_decider':
        storage_cfg = (host.config or {}).get('storage', {}).get('user', {})
        storage_settings = storage_cfg.get('settings', {})
        storage = S3({
          'bucket': storage_settings.get('bucket'),
          'credentials': storage_cfg.get('credentials'),
          'region': storage_settings.get('region'),
        })
        session_credential = storage.get_credentials()

        # files_to_update = []
        for file in obj.files.all():
          if file.is_url_expired(session_credential):
            result = storage.get_self_signed(file.path, 28800) # 8hs

            # If error in signing urls return error response
            if isinstance(result, dict) and result.get('error'):
              LOG.error('analysis.obj_get: signing file', payload={'extra_data': result})
              continue

            file.uri = file.uri or f"s3://{storage_settings.get('bucket')}/{file.path}"
            file.url = result
            file.save()
            # replace above line with below two after upgrading to django>=2.2
            #   files_to_update.append(file)
            # File.objects.bulk_update(files_to_update, ['url'])

    serializer = self.get_serializer(obj)
    return Response(data=serializer.data)

  def destroy(self, request, *args, **kwargs):
    '''Override obj destroy'''
    self.soft_destroy(request, *args, **kwargs)
    obj = self.get_object()
    # delete log
    AnalysisLog.objects.filter(analysis_id=obj.id).delete()

    # send termination message
    api_cfg = settings.CONFIG.get('api', {})
    host = obj.host or Host.get_host_by_domain(api_cfg.get('host', ''))

    queue_cfg = (host.config or {}).get('queue', {})
    queue_settings = queue_cfg.get('settings', {})
    queue_name = queue_settings.get('instance_queue', f'instance-{settings.MODE}')

    queue = SQS({
      'credentials': queue_cfg.get('credentials'),
      'queue': queue_name,
      'region': queue_settings.get('region'),
    })
    queue.send_message({
      'action': 'terminate-instance',
      'analysis_id': obj.id,
      'name': f'{settings.MODE}-{obj.id}',
    })
    return Response(status=status.HTTP_204_NO_CONTENT)

  @action(detail=False, methods=['post'])
  def bulk_start(self, request):  # pylint: disable=too-many-locals, no-self-use
    '''Bulk start analyses'''
    user = request.user
    if user and user.is_authenticated:
      data = request.data
      data_analyses = data.get('analyses')
      project_id = data.get('project_id') or user.active_project.id
      response = []

      host = Host.objects.get(domain=request.get_host())
      queue_cfg = (host.config or {}).get('queue', {})
      queue_settings = queue_cfg.get('settings', {})
      queue_name = queue_settings.get('instance_queue', f'instance-{settings.MODE}')
      queue = SQS({
        'credentials': queue_cfg.get('credentials'),
        'queue': queue_name,
        'region': queue_settings.get('region'),
      })
      # creating analyses
      analyses = Analysis.objects.bulk_create([
        Analysis(
          host=host,
          meta={'source': 'cli', **(analysis.get('meta') or {})},
          name=analysis.get('name'),
          owner=user,
          params=analysis.get('params', {}),
          status='waiting-in-queue',
          workflow_id=analysis.get('pipeline_id'),
        ) for analysis in data_analyses
      ])

      # TODO: move to celery pylint: disable=fixme
      # we update the analysis if it was saved
      for index, analysis in enumerate(analyses):
        if analysis.id:
          # set the m2m
          analysis.samples.set(Sample.objects.filter(pk__in=data_analyses[index].get('samples', [])))
          analysis.controls.set(Sample.objects.filter(pk__in=data_analyses[index].get('controls', [])))
          analysis.projects.add(project_id)
          # create analysis logs
          analysis_log = AnalysisLog.objects.create(analysis=analysis)
          analysis_log.reset()
          # queuing message
          queue.send_message({
            'action': 'start-analysis',
            'analysis_id': analysis.id,
            'host': request.get_host()
          })
          response.append({'id': analysis.id, 'name': analysis.name, 'params': analysis.params})
      return Response({'analyses': response, 'success': True})
    return Response({'error': 'UNAUTHORIZED'}, status=status.HTTP_401_UNAUTHORIZED)

  @action(detail=False, methods=['post'], url_path='log')
  def save_log(self, request):  # pylint: disable=no-self-use
    '''Save analysis logs'''
    user = request.user
    if user and user.is_authenticated:
      data = request.data
      try:
        analysis_log = AnalysisLog.objects.filter(analysis_id=data.get('id'))[0]
      except IndexError:
        return Response({'error': 'AnalysisLog object not found.'}, status=status.HTTP_400_BAD_REQUEST)

      analysis_log.log = deep_merge(data.get('log'), (analysis_log.log or {}))
      analysis_log.save()

      return Response({'status': 'SUCCESS'})
    return Response({'error': 'UNAUTHORIZED'}, status=status.HTTP_401_UNAUTHORIZED)

  @action(detail=False, methods=['post'], url_path='reanalyze')
  def re_analyze(self, request):  # pylint: disable=no-self-use, too-many-locals
    '''Re queue analysis to be re analyzed'''
    user = request.user
    if user and user.is_authenticated:
      data = request.data
      source = data.get('source', 'N/A')

      analysis_id = data.get('id')
      genome_id = data.get('genome_id')

      LOG.info(f'analysis.re_analyze: re analyze request received from {source} for analysis id {analysis_id}')

      if analysis_id:
        try:
          analysis = Analysis.objects.get(pk=analysis_id)
        except Analysis.DoesNotExist as error:
          raise exceptions.BadRequest(f'Analysis not found with id: {analysis_id}.') from error
      elif genome_id:
        if not Genome.objects.filter(pk=genome_id).exists():
          raise exceptions.BadRequest(f'Genome not found with id: {genome_id}.')
        try:
          analysis = Analysis.objects.filter(**{
            'params__node__index_genome': {'index_genome_id': genome_id},
            'owner': user
          })[0]
        except IndexError:
          try:
            Workflow.objects.get(pk=INDEX_GENOME_PIPELINE)
          except Workflow.DoesNotExist as error:
            raise exceptions.BadRequest(f'Pipeline not found with id: {INDEX_GENOME_PIPELINE}.') from error
      else:
        raise exceptions.BadRequest('Parameter missing.')

      # when the analysis was soft deleted
      if analysis.deleted_on:
        raise exceptions.BadRequest('This analysis has been deleted.')

      # set analysis status
      analysis.status = 'waiting-in-queue'
      analysis.meta = {
        **analysis.meta,
        'source': source
      }
      analysis.scheduled_on = datetime.now(pytz.utc)
      analysis.save()

      # send request to queue
      api_cfg = settings.CONFIG.get('api', {})
      host = analysis.host if analysis else Host.get_host_by_domain(api_cfg.get('host', ''))

      queue_cfg = (host.config or {}).get('queue', {})
      queue_settings = queue_cfg.get('settings', {})
      queue_name = queue_settings.get('instance_queue', f'instance-{settings.MODE}')

      delay = 0 if source == 'webapp' else 300

      queue = SQS({
        'credentials': queue_cfg.get('credentials'),
        'queue': queue_name,
        'region': queue_settings.get('region'),
      })
      queue.send_message({
        'action': 'restart-analysis',
        'analysis_id': analysis_id,
        'force': True,
        'instance_type': data.get('instance_type'),
        'send_completion_email': not user.is_superuser
      }, delay=delay)

      # reset logs
      analysis_log, _ = AnalysisLog.objects.get_or_create(analysis=analysis)
      analysis_log.reset()

      # delete all existing files
      File.objects.filter(analysis_id=analysis.id).delete()

      return Response({'status': 'SUCCESS'})
    return Response({'error': 'UNAUTHORIZED'}, status=status.HTTP_401_UNAUTHORIZED)

  @action(detail=False, methods=['post'])
  def terminate(self, request):  # pylint: disable=no-self-use
    '''Terminate instance and delete SWF task'''
    user = request.user
    if user and user.is_authenticated:
      data = request.data
      source = data.get('source', 'N/A')
      analysis_id = data.get('id')
      LOG.info(f'analysis.terminate: terminate analysis request received from {source} for analysis id - {analysis_id}')

      if analysis_id:
        try:
          analysis = Analysis.objects.get(pk=analysis_id)
        except Analysis.DoesNotExist:
          return Response({'error': 'Analysis object not found.'}, status=status.HTTP_400_BAD_REQUEST)
      else:
        raise exceptions.BadRequest('Analysis id required.')

      # when the analysis was soft deleted
      if analysis.deleted_on:
        raise exceptions.BadRequest('Analysis has been deleted.')

      if not re.search(r'^(started|running)', analysis.status):
        raise exceptions.BadRequest(f'Analysis termination with status - {analysis.status} is not allowed.')

      if BasePermission.can_edit(user, analysis):
        try:
          self._terminate_workflow(analysis=analysis)
          self._terminate_instance(analysis=analysis)
        except Exception as error:  # pylint: disable=broad-except
          print(f'ERROR: Terminating analysis failed - {str(error)}')
          return Response({'error': f'Terminating analysis failed - {str(error)}'}, status=status.HTTP_400_BAD_REQUEST)

        # set analysis status
        analysis.status = 'abort'
        analysis.save()
        try:
          analysis_log = AnalysisLog.objects.get(analysis_id=analysis_id)
          analysis_log.log = deep_merge({
            'infra': [{
              'display_in_report_view': False,
              'level': 'info',
              'msg': f'Analysis terminated after receiving request from {source}',
            }]
          }, (analysis_log.log or {}))
          analysis_log.save()
        except AnalysisLog.DoesNotExist:
          print(f'ERROR: Analysis log object not found with analysis id - {analysis_id}')
        return Response({'status': 'SUCCESS'})
    return Response({'error': 'UNAUTHORIZED'}, status=status.HTTP_401_UNAUTHORIZED)

  @staticmethod
  def set_name(obj):
    '''Set analysis name if empty'''
    if not obj.name:
      obj.name = f'{obj.workflow.name}'
      samples = obj.samples.filter(deleted_on__isnull=True)
      if samples.count():
        obj.name += f' on {samples[0].name}'
      obj.save()

  @staticmethod
  def _terminate_instance(analysis=None):
    '''Send ec2 instance termination message'''
    api_cfg = settings.CONFIG.get('api', {})
    host = analysis.host or Host.get_host_by_domain(api_cfg.get('host', ''))

    queue_cfg = (host.config or {}).get('queue', {})
    queue_settings = queue_cfg.get('settings', {})

    queue = SQS({
      'credentials': queue_cfg.get('credentials'),
      'queue': queue_settings.get('instance_queue', f'instance-{settings.MODE}'),
      'region': queue_settings.get('region'),
    })
    queue.send_message({
      'action': 'terminate-instance',
      'analysis_id': analysis.id,
      'mode': settings.MODE,
      'name': f'{settings.MODE}-{analysis.id}',
    }, delay=0)

  @staticmethod
  def _terminate_workflow(analysis=None):
    '''Terminate SWF task'''
    api_cfg = settings.CONFIG.get('api', {})
    host = analysis.host or Host.get_host_by_domain(api_cfg.get('host', ''))

    workflow_cfg = (host.config or {}).get('workflow', {})
    workflow_settings = workflow_cfg.get('settings', {})

    workflow_service = SWF({
      'credentials': workflow_cfg.get('credentials'),
      'domain': workflow_settings.get('domain'),
      'region': workflow_settings.get('region'),
    })
    workflow_service.terminate(f"{host.domain.replace('.', '_')}-analysis-{analysis.id}")