"""Defines the App class."""

from typing import Type

from absl import flags

from perfkitbenchmarker.scripts.messaging_service_scripts.common import client
from perfkitbenchmarker.scripts.messaging_service_scripts.common import log_utils
from perfkitbenchmarker.scripts.messaging_service_scripts.common import runners
from perfkitbenchmarker.scripts.messaging_service_scripts.common.e2e import latency_runner

PUBLISH_LATENCY = 'publish_latency'
PULL_LATENCY = 'pull_latency'
END_TO_END_LATENCY = 'end_to_end_latency'
STREAMING_PULL_END_TO_END_LATENCY = 'streaming_pull_end_to_end_latency'
BENCHMARK_SCENARIO_CHOICES = [PUBLISH_LATENCY, PULL_LATENCY, END_TO_END_LATENCY]

_BENCHMARK_SCENARIO = flags.DEFINE_enum(
    'benchmark_scenario',
    'publish_latency',
    BENCHMARK_SCENARIO_CHOICES,
    help='Which part of the benchmark to run.',)
_NUMBER_OF_MESSAGES = flags.DEFINE_integer(
    'number_of_messages', 100, help='Number of messages to send on benchmark.')
_MESSAGE_SIZE = flags.DEFINE_integer(
    'message_size',
    10,
    help='Number of characters to have in a message. '
    "Ex: 1: 'A', 2: 'AA', ...")
_STREAMING_PULL = flags.DEFINE_boolean(
    'streaming_pull', False,
    help=('Use StreamingPull to fetch messages. Supported only in GCP Pubsub '
          'end-to-end benchmarking.')
)


@flags.multi_flags_validator(
    ['streaming_pull', 'benchmark_scenario'],
    message=(
        'streaming_pull is only supported for end-to-end latency benchmarking '
        'with GCP PubSub.'))
def validate_streaming_pull(flags_dict):
  client_class_name = App.get_instance().get_client_class().__name__
  return (not flags_dict['streaming_pull'] or
          client_class_name == 'GCPPubSubClient' and
          flags_dict['benchmark_scenario'] == END_TO_END_LATENCY)


@flags.multi_flags_validator(
    ['warmup_messages', 'number_of_messages'],
    message='warmup_message must be less than number_of_messages.')
def validate_warmup_messages(flags_dict):
  return flags_dict['warmup_messages'] < flags_dict['number_of_messages']


log_utils.silence_log_messages_by_default()


class App:
  """Benchmarking Application.

  This is a singleton that allows to create a runner instance honoring the flags
  and the client class provided.
  """

  instance = None

  @classmethod
  def get_instance(cls) -> 'App':
    """Gets the App instance.

    On the first call, it creates the instance. For subsequent calls, it just
    returns that instance.

    Returns:
      The App instance.
    """
    if cls.instance is None:
      cls.instance = cls()
    return cls.instance

  @classmethod
  def for_client(cls,
                 client_cls: Type[client.BaseMessagingServiceClient]) -> 'App':
    """Gets the app instance and configures it to use the passed client class.

    Args:
      client_cls: A BaseMessagingServiceClient class.

    Returns:
      The App instance.
    """
    instance = cls.get_instance()
    instance.register_client(client_cls)
    return instance

  def __init__(self):
    """Private constructor. Outside this class, use get_instance instead."""
    self.client_cls = None
    self.runner_registry = {}

  def __call__(self, _):
    """Runs the benchmark for the flags passed to the script.

    Implementing this magic method allows you to pass this instance directly to
    absl.app.run.

    Args:
      _: Unused. Just for compatibility with absl.app.run.
    """
    self._register_runners()
    runner = self.get_runner()
    try:
      runner.run_phase(_NUMBER_OF_MESSAGES.value, _MESSAGE_SIZE.value)
    finally:
      runner.close()

  def get_runner(self) -> runners.BaseRunner:
    """Creates a client instance, using the client class registered.

    Returns:
      A BaseMessagingServiceClient instance.

    Raises:
      Exception: No client class has been registered.
    """
    client_class = self.get_client_class()
    runner_class = self.get_runner_class()
    runner_class.run_class_startup()
    return runner_class(client_class.from_flags())

  def get_client_class(self) -> Type[client.BaseMessagingServiceClient]:
    """Gets the client class registered.

    Returns:
      A BaseMessagingServiceClient class.

    Raises:
      Exception: No client class has been registered.
    """
    if self.client_cls is None:
      raise Exception('No client class has been registered.')
    return self.client_cls

  def get_runner_class(self) -> Type[runners.BaseRunner]:
    """Gets the BaseRunner class registered.

    Returns:
      A BaseRunner class.
    """
    try:
      if (_STREAMING_PULL.value and
          _BENCHMARK_SCENARIO.value == END_TO_END_LATENCY):
        return self.runner_registry[STREAMING_PULL_END_TO_END_LATENCY]
      return self.runner_registry[_BENCHMARK_SCENARIO.value]
    except KeyError:
      raise Exception('Unknown benchmark_scenario flag value.') from None

  def register_client(self,
                      client_cls: Type[client.BaseMessagingServiceClient]):
    """Registers a client class to create instances with.

    Args:
      client_cls: The client class to register.
    """
    self.client_cls = client_cls

  def _register_runners(self):
    """Registers all runner classes to create instances depending on flags."""
    self._register_runner(PUBLISH_LATENCY, runners.PublishLatencyRunner)
    self._register_runner(PULL_LATENCY, runners.PullLatencyRunner)
    self._register_runner(
        END_TO_END_LATENCY, latency_runner.EndToEndLatencyRunner)
    self._register_runner(
        STREAMING_PULL_END_TO_END_LATENCY,
        latency_runner.StreamingPullEndToEndLatencyRunner)

  def _register_runner(self, benchmark_scenario: str,
                       runner_cls: Type[runners.BaseRunner]):
    self.runner_registry[benchmark_scenario] = runner_cls

  def promote_to_singleton_instance(self):
    """Set this instance as the App.instance singleton."""
    App.instance = self
