
class BaseModel(models.Model):
  '''BaseModel class'''
  class Meta:
    abstract = True

  def save(self, *args, **kwargs):
    '''Save method'''
    _sanitize_fields(obj=self)
    super().save(*args, **kwargs)

class AbstractUserBaseModel(AbstractUser):
  '''AbstractUser BaseModel class'''

  class Meta:
    verbose_name = _("user")
    verbose_name_plural = _("users")
    abstract = True

  def save(self, *args, **kwargs):
    '''Save method'''
    _sanitize_fields(obj=self)
    super().save(*args, **kwargs)

def _sanitize_fields(obj=None):
  '''Helper function to strip html tags from char/text fields'''
  for field in obj._meta.fields:
    field_name = field.attname
    if field and field.__class__.__name__ in ['CharField', 'TextField']:
      value = getattr(obj, field_name, None)
      if value:
        setattr(obj, field_name, strip_tags(value))

class BpUser(AbstractUserBaseModel):
  '''Model class'''

  aws_access_key_id = models.CharField(blank=True, max_length=100, null=True)
  aws_secret_access_key = models.CharField(blank=True, max_length=100, null=True)
  basespace = models.JSONField(null=True, blank=True)
  bill_by = models.CharField(default='seq_length', max_length=100)
  code = models.CharField(default='', max_length=100, blank=True)
  info = models.JSONField(null=True, blank=True)
  institution_name = models.CharField(blank=True, max_length=255, null=True)
  is_bp_staff = models.BooleanField(
    default=False,
    help_text='staff, dont use for analytics',
  )
  is_verified = models.BooleanField(default=False, help_text='track user email verification')
  num_samples_in_trial = models.IntegerField(default=6)
  phone = models.CharField(blank=True, max_length=255, null=True)
  plan = models.CharField(default='Trial', max_length=100)
  pre_paid = models.DecimalField(decimal_places=2, max_digits=20, null=True, blank=True)
  rate = models.DecimalField(decimal_places=2, max_digits=20, null=True, blank=True)
  status = models.CharField(max_length=100, null=True, blank=True)
  trial_expiry = models.DateTimeField(db_index=True, null=True, blank=True)

  # date on
  deleted_on = models.DateTimeField(db_index=True, null=True, blank=True)

  # relations
  active_project = models.ForeignKey(
    'Project',
    null=True,
    on_delete=models.DO_NOTHING,
    related_name='+',
  )

  REQUIRED_FIELDS = ['email']

  def __str__(self):
    '''To string method'''
    return f'{self.id}:{self.name}'

  def get_host(self):
    '''Get host from user'''
    def _get_first(user, role='manager'):
      '''Get last host membership'''
      HostsMembers = apps.get_model('bpapp.HostsMembers') # pylint: disable=invalid-name
      try:
        print([(membership.created_on, membership.host) for membership in HostsMembers.objects.filter(
          role=role,
          user=user,
        ).order_by('-created_on')])
        membership = HostsMembers.objects.filter(
          role=role,
          user=user,
        ).order_by('-created_on')[0]
        return membership.host
      except IndexError:
        return None
    return _get_first(self) or _get_first(self, 'member')

  def get_trial_info(self):
    '''Get info related to trial period'''
    trial_period = None
    user_status = self.status
    if user_status in ['in_trial', 'trial_expired']:
      trial_period = {'trial': False}
      if user_status == 'in_trial':
        trial_days_remaining = self.trial_days_remaining
        if trial_days_remaining and trial_days_remaining > 0:
          trial_period = {
            'maxInTrial': self.num_samples_in_trial,
            'numSamples': len([sample.id for sample in self.sample_set.all() if sample.count_in_trial()]),
            'trial': True,
            'trialDaysRemaining': trial_days_remaining,
          }
    return trial_period

  def has_billing_account(self):
    '''Has billing account'''
    BillingAccountMember = apps.get_model('bpapp.BillingAccountMember') # pylint: disable=invalid-name
    return BillingAccountMember.objects.select_related('account').filter(user=self).exists()

  @property
  def name(self):
    '''Full name or username'''
    return f'{self.first_name} {self.last_name}'.strip() \
      if self.first_name or self.last_name \
      else self.username

  @property
  def trial_days_remaining(self):
    '''Number of days remainging in the trial '''
    return self.trial_expiry and (self.trial_expiry - datetime.now(pytz.utc)).days + 1

  @property
  def trial_expired(self):
    '''If current date is higher than trial expiry'''
    return self.trial_expiry and self.trial_expiry < datetime.now(pytz.utc)

# hooks
post_save.connect(create_api_key, sender=BpUser)

class Analysis(BaseModel):
  '''Analysis Model class'''
  tracker = FieldTracker()

  app_data = models.JSONField(null=True, blank=True)
  filesize = models.BigIntegerField(default=0)
  host = models.ForeignKey(Host, blank=True, null=True, on_delete=models.DO_NOTHING)
  info = models.JSONField(null=True, blank=True)
  meta = models.JSONField(null=True, blank=True)
  name = models.CharField(max_length=500)
  params = models.JSONField(null=True, blank=True)
  status = models.CharField(max_length=100, null=True, blank=True)
  swf_run_id = models.CharField(blank=True, max_length=100, null=True)
  swf_workflow_id = models.CharField(blank=True, max_length=100, null=True)
  tags = models.JSONField(null=True, blank=True)
  user_params = models.JSONField(null=True, blank=True)
  workflow_data = models.JSONField(null=True, blank=True)

  # date on
  completed_on = models.DateTimeField(null=True, blank=True)
  date_created = models.DateTimeField(auto_now_add=True) # TODO: rename to created_on pylint: disable=fixme
  deleted_on = models.DateTimeField(db_index=True, null=True, blank=True)
  last_updated = models.DateTimeField(auto_now=True) # TODO: rename to updated_on pylint: disable=fixme
  scheduled_on = models.DateTimeField(null=True, blank=True)
  started_on = models.DateTimeField(null=True, blank=True)

  # relations
  controls = models.ManyToManyField(Sample, blank=True, related_name='control_analyses')
  # each analysis belongs to a single user
  owner = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.DO_NOTHING)
  projects = models.ManyToManyField(Project, related_name='analyses')
  samples = models.ManyToManyField(Sample, blank=True, related_name='analyses')
  # each analysis may shared with multiple users
  users = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='analyses')
  workflow = models.ForeignKey(Workflow, on_delete=models.DO_NOTHING, related_name='analyses')

  class Meta:
    '''Meta class'''
    permissions = (
      ('view', 'Can view analysis'),
      ('edit', 'Can edit analysis'),
      ('admin', 'Can move, share, and delete analysis'),
    )

  def __str__(self):
    '''To string method'''
    return f'{self.id}:{self.name}'

  def add_project(self):
    '''Link analysis to project'''

    # if analysis already has at least 1 project or source is auto, then theres nothing to do
    is_auto = (getattr(self, 'meta', {}) or {}).get('source', '') == 'auto'
    if self.projects.filter(deleted_on__isnull=True).count() > 0 or is_auto:
      return

    if self.owner:
      analysis_owner_projects = self.owner.project_set.filter(deleted_on__isnull=True)
      if self.owner.active_project is None:
        self.owner.active_project = analysis_owner_projects[0] \
          if analysis_owner_projects.count() > 0 \
          else Project.objects.create(name='Project 1', owner=self.owner)
        self.owner.save()
      self.owner.active_project.analyses.add(self)
    else:
      LOG.warning(f'analysis.add_project: analysis {self.id} created without owner')

  def clone(self, owner=None):
    '''Clone analysis'''
    new_analysis = copy(self)
    new_analysis.pk = None # pylint: disable=invalid-name
    if owner:
      new_analysis.owner = owner
    new_analysis.save()

    for file in self.files.all():
      file.pk = None # pylint: disable=invalid-name
      if owner:
        file.owner = owner
      file.analysis = new_analysis
      file.save()

    return new_analysis

  @property
  def timetaken(self):
    '''Time taken for the analysis'''
    try:
      timetaken = round((self.completed_on - self.started_on).total_seconds()) \
        if self.completed_on and self.started_on \
        else 0
    except TypeError:
      timetaken = 0

    return timetaken

  def update_analysis_meta(self):
    '''Set sample meta'''
    if self.meta is None:
      self.meta = {}

    self.meta['num_files'] = self._num_files()
    self.save()

  def _num_files(self):
    '''The number of files for the analysis'''
    return self.files.count()

# hook
def hook_create_analysis_log(sender, instance, **kwargs): # pylint: disable=unused-argument
  '''Hook to call create analysis log when new analysis created'''
  if sender == Analysis:
    AnalysisLog = apps.get_model('bpapp.AnalysisLog') # pylint: disable=invalid-name
    if not AnalysisLog.objects.filter(analysis=instance).exists():
      analysis_log = AnalysisLog.objects.create(analysis=instance)
      analysis_log.reset()

def hook_send_notification(sender, instance, **kwargs): # pylint: disable=unused-argument
  '''Hook to send email notification whenever analysis status updates'''
  notification_should_be_sent = instance.tracker.has_changed('status') \
    and instance.status in ['abort', 'completed', 'error', 'failed'] \
    and sender == Analysis
  if notification_should_be_sent:
    config_key, run_status = ({
      'abort': ('on_fail', 'aborted'),
      'error': ('on_fail', 'failed'),
      'failed': ('on_fail', 'failed'),
    }).get(instance.status, ('on_complete', 'completed'),)
    user_email, cc_emails, event_name = _get_send_info(instance, config_key)
    _send_email(instance, cc_emails, event_name, run_status, user_email)

def _get_send_info(instance, config_key):
  '''get the emails of users for sending emails'''
  host_data = Host.objects.get(id=instance.host_id)
  worker_confg = host_data.config.get('compute', {}).get('worker', {})
  worker_settings = worker_confg.get('settings', {})
  notify_to = worker_settings.get('notification', {}).get(config_key)
  user_email, cc_emails, event_name = None, [], 'analysis_ended'
  if notify_to != 'none':
    user_email = (instance.owner.info or {}).get('send_emails', {}).get('analysis_status') and instance.owner.email
    if notify_to == 'admin':
      cc_emails = HostsMembers.objects.filter(
        host_id=instance.host_id,
        role='manager',
        user__info__send_emails__analysis_status=True,
      ).values_list('user__email', flat=True)
    elif notify_to == 'host_contact':
      user_email = host_data.contact_email
      event_name = 'analysis_ended_without_links'
  return user_email, cc_emails, event_name

def _get_errors(analysis):
  '''Get errors html string'''
  analysis_log = analysis.logs.first()
  bio_log = analysis_log.log.get('bio')

  errors = ''
  for data in bio_log.values():
    pre_validation_logs = data.get('pre')
    post_validation_logs = data.get('post')
    all_logs = [*(pre_validation_logs or []), *(post_validation_logs or [])]
    module_errors = ''
    for log in all_logs:
      if isinstance(log, dict) and log.get('level') in ['error', 'fatal']:
        module_errors = f'{module_errors}<p>{log.get("msg")}<p/>'

    if module_errors:
      module_errors = f'<p>Module <b>{data.get("label")}</b>:<p/>{module_errors}<br/>'
    errors = f'{errors}{module_errors}'
  if errors:
    errors = f'<hr><p>The following errors were detected:</p><br/>{errors}' \
             f'<p>To discuss the above errors with our Bioinformatics team, ' \
             f'<a href={BIOINFORMATICS_CALENDLY}>schedule a meeting here.</a></p>'

  return errors

def _send_email(analysis, cc_emails, event_name, run_status, user_email):
  '''To send an email based on host config value'''
  try:
    samples = ', '.join(analysis.samples.all().values_list('name', flat=True))
    controls = ', '.join(analysis.controls.all().values_list('name', flat=True))
  except TypeError as error:
    LOG.error(f'Could not get samples, controls to include in email - {error}')
    samples = None
    controls = None

  user_email = user_email or next(iter(cc_emails or []), None)
  errors = _get_errors(analysis) # error from analysis logs
  if errors and settings.MODE == 'prod':
    cc_emails += [SALES_EMAIL] # add sales in cc if analysis log error
  try:
    if user_email:
      # get host domain
      host = None
      domain = settings.CONFIG['api']['host']
      if analysis.host:
        host = analysis.host
        domain = host.domain
      data = {
        'analysis_name': analysis.name,
        'analysis_url': f'https://{domain}/analyses/{analysis.id}',
        'cc': cc_emails,
        'controls': controls and f'<p><b>Controls </b>{controls}</p><br />',
        'email': user_email,
        'errors': errors,
        'host': host,
        'run_status': run_status,
        'samples': samples and f'<p><b>Samples </b>{samples}</p><br />',
        'workflow_name': analysis.workflow.name,
      }
      Sender.send_email(
        data=data,
        name=event_name
      )
  except Exception as error: # pylint: disable=broad-except
    LOG.error(
      'message_action_handler._action_send_completion_message: sending email',
      payload={'extra_data': {'detail': f'{error}'}}
    )


post_save.connect(hook_create_analysis_log, sender=Analysis)
pre_save.connect(hook_send_notification, sender=Analysis)


class Instance(BaseModel):
  '''Instance Model class'''

  analysis_id = models.CharField(max_length=20)
  aws_instance_id = models.CharField(max_length=40)
  hostname = models.CharField(max_length=100)
  instance_type = models.CharField(max_length=20)
  lifecycle = models.CharField(max_length=20)
  mode = models.CharField(max_length=20)
  name = models.CharField(max_length=50)
  owner_id = models.CharField(max_length=20)
  rate = models.DecimalField(decimal_places=5, max_digits=20, null=True)
  task_list = models.CharField(max_length=100)

  # date on
  date_created = models.DateTimeField(auto_now_add=True) # TODO: rename to created_on # pylint: disable=fixme
  deleted_on = models.DateTimeField(db_index=True, blank=True, null=True)
  last_updated = models.DateTimeField(auto_now=True) # TODO: rename to updated_on # pylint: disable=fixme
  ready_on = models.DateTimeField(null=True)
  requested_on = models.DateTimeField(null=True)
  terminated_on = models.DateTimeField(null=True)

  def __str__(self):
    return self.name

  @property
  def time_to_boot(self):
    '''Time to boot machine'''
    return (self.ready_on - self.requested_on).total_seconds() \
      if self.ready_on and self.requested_on \
      else 0

  @property
  def time_to_run_analysis(self):
    '''Time to run analysis'''
    return (self.terminated_on - self.ready_on).total_seconds() \
      if self.terminated_on and self.ready_on \
      else 0