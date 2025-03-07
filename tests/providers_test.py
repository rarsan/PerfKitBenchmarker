# Copyright 2018 PerfKitBenchmarker Authors. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests for perfkitbenchmarker.providers."""

import typing
import unittest

from absl import flags
import mock
from perfkitbenchmarker import providers
from perfkitbenchmarker import requirements
from perfkitbenchmarker.configs import benchmark_config_spec
from perfkitbenchmarker.providers.gcp import util as gcp_util
from tests import pkb_common_test_case

FLAGS = flags.FLAGS


class LoadProvidersTestCase(pkb_common_test_case.PkbCommonTestCase):

  def setUp(self):
    super(LoadProvidersTestCase, self).setUp()
    FLAGS.ignore_package_requirements = True
    p = mock.patch.object(providers, '_imported_providers', new=set())
    p.start()
    self.addCleanup(p.stop)

  # TODO(user): See if this can be fixed.
  @unittest.skip('This fails because modules are being imported multiple '
                 'times in the instance of this process. Not sure how this '
                 'ever worked.')
  def testImportAllProviders(self):
    # Test that all modules can be imported successfully, but mock out the
    # import of CloudStack's csapi.
    with mock.patch.dict('sys.modules', csapi=mock.Mock()):
      for cloud in providers.VALID_CLOUDS:
        providers.LoadProvider(cloud)

  def testLoadInvalidProvider(self):
    with self.assertRaises(ImportError):
      providers.LoadProvider('InvalidCloud')

  def testLoadProviderChecksRequirements(self):
    with mock.patch(requirements.__name__ + '.CheckProviderRequirements'):
      providers.LoadProvider('GCP', ignore_package_requirements=False)
      typing.cast(
          mock.MagicMock,
          requirements.CheckProviderRequirements).assert_called_once_with('gcp')

  def testLoadProviderIgnoresRequirements(self):
    with mock.patch(requirements.__name__ + '.CheckProviderRequirements'):
      providers.LoadProvider('GCP')
      typing.cast(mock.MagicMock,
                  requirements.CheckProviderRequirements).assert_not_called()

  def testBenchmarkConfigSpecLoadsProvider(self):
    p = mock.patch(providers.__name__ + '.LoadProvider')
    p.start()
    self.addCleanup(p.stop)
    config = {
        'vm_groups': {
            'group1': {
                'cloud': 'AWS',
                'os_type': 'ubuntu1804',
                'vm_count': 0,
                'vm_spec': {'AWS': {}}
            }
        }
    }
    benchmark_config_spec.BenchmarkConfigSpec(
        'name', flag_values=FLAGS, **config)
    typing.cast(mock.MagicMock,
                providers.LoadProvider).assert_called_with('AWS', True)

  def testLoadProviderUtils(self):
    test_cloud = providers.GCP

    actual_utils_module = providers.LoadProviderUtils(test_cloud)

    expected_utils_module = gcp_util
    self.assertEqual(expected_utils_module, actual_utils_module)

if __name__ == '__main__':
  unittest.main()
