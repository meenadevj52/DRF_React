
class BaseSerializer(serializers.ModelSerializer):
  '''Base serializer'''
  resource_uri = serializers.SerializerMethodField()

  def get_resource_uri(self, obj):
    '''reverse viewset detail to get resource_uri'''
    url_kwargs = {
      'pk': obj.pk
    }
    viewset_basename = self.context['view'].basename
    resource_uri = reverse(f'{DrfApiConfig.name}:{viewset_basename}-detail', kwargs=url_kwargs)
    return resource_uri

  class Meta:
    abstract = True

class HostSerializer(BaseSerializer):
  '''Host serializer class'''
  contact_email = serializers.CharField(
    required=False,
    validators=[EmailValidator()],
  )
  domain = serializers.CharField(
    error_messages={'blank': 'CANNOT_BE_EMPTY'},
    validators=[
      DomainValidator(),
      IsRequiredValidator(),
    ],
  )
  name = serializers.CharField(
    error_messages={'blank': 'CANNOT_BE_EMPTY'},
    validators=[IsRequiredValidator()],
  )

  class Meta:
    model = Host
    fields = '__all__'


class AnalysisSerializer(BaseSerializer):
  '''Analysis serializer class'''
  owner__username = serializers.ReadOnlyField(source='owner.username', default='')
  permission = serializers.SerializerMethodField()
  log = serializers.SerializerMethodField()

  def get_permission(self, obj):
    '''Populate `permission` field'''
    request = self.context['request']
    user = request.user
    return BasePermission.get(user, obj)

  def get_log(self, obj):
    '''Populate `log` field'''
    analysis_log = AnalysisLog.get_by_analysis_id(analysis_id=obj.id) or {}
    for key, value in analysis_log.get('bio', {}).items():
      for field in ['pre', 'post']:
        validation_logs = value.get(field)
        if validation_logs and isinstance(validation_logs, dict):
          analysis_log['bio'][key][field] = self._get_restructured_logs(logs=validation_logs)
    return analysis_log

  def _get_restructured_logs(self, logs=None):
    '''Restructure logs for retro compatibility'''
    restructured_logs = []
    display_in_report_view = {'error': True}
    for level in ['error', 'info', 'warning']:
      for log in logs.get(level):
        restructured_logs.append({
          **log,
          'display_in_report_view': display_in_report_view.get(level, False),
          'level': level,
          'timestamp': log.get('datetime')
        })
    return restructured_logs

  class Meta:
    model = Analysis
    fields = '__all__'

class SampleSerializer(BaseSerializer):
  '''Sample serializer class'''
  owner__username = serializers.ReadOnlyField(source='owner.username', default='')
  owner_fullname = serializers.ReadOnlyField(source='owner.name', default='')
  genome_name = serializers.ReadOnlyField(source='genome.name', default='')
  spike_in_name = serializers.ReadOnlyField(source='spike_in.name', default='')
  meta = serializers.SerializerMethodField()
  permission = serializers.SerializerMethodField()

  def get_meta(self, obj):
    '''Populate `meta` field'''
    _meta = None
    meta = obj.meta or {}
    if not all(attribute in meta for attribute in ['filetype', 'upload_percentage']):
      obj.update_sample_meta()
      _meta = obj.meta
    return _meta

  def get_permission(self, obj):
    '''Populate `permission` field'''
    request = self.context['request']
    return BasePermission.get(request.user, obj)

  class Meta:
    model = SampleModel
    fields = '__all__'

class FileSerializer(BaseSerializer):
  '''File serializer class'''
  analysis_id = serializers.SerializerMethodField()
  analysis_name = serializers.SerializerMethodField()

  def get_analysis_id(self, obj):
    '''Populate `analysis_id` field'''
    request = self.context['request']
    has_project_filter = request.GET.get('analysis__projects__exact')
    analysis_id = None
    analysis = obj.analysis
    if has_project_filter:
      analysis_id = getattr(analysis, 'id', '')

    if request.GET.get('check_self_signed'):
      api_cfg = settings.CONFIG.get('api', {})
      host = analysis.host or Host.get_host_by_domain(api_cfg.get('host', ''))
      storage_cfg = (host.config or {}).get('storage', {}).get('user', {})
      storage_settings = storage_cfg.get('settings', {})
      storage = S3({
        'bucket': storage_settings.get('bucket'),
        'credentials': storage_cfg.get('credentials'),
        'region': storage_settings.get('region'),
      })
      session_credential = storage.get_credentials()
      if obj.path and obj.is_url_expired(session_credential):
        result = storage.get_self_signed(obj.path, 28800)  # 8hs
        # If error in signing urls return error response
        if isinstance(result, dict) and result.get('error'):
          LOG.error('file.dehydrate: signing file fail', payload={'extra_data': result})
        else:
          obj.uri = obj.uri or f"s3://{storage_settings.get('bucket')}/{obj.path}"
          obj.url = result
          obj.save()
    return analysis_id

  def get_analysis_name(self, obj):
    '''Populate `analysis_name` field'''
    request = self.context['request']
    has_project_filter = request.GET.get('analysis__projects__exact')
    analysis_name = None
    analysis = obj.analysis
    if has_project_filter:
      analysis_name = getattr(analysis, 'name', '')
    return analysis_name

  class Meta:
    model = File
    fields = '__all__'