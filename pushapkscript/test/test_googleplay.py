import unittest
from unittest.mock import MagicMock

from pushapkscript.exceptions import TaskVerificationError
from pushapkscript.googleplay import craft_push_apk_config, get_package_name, get_service_account, get_certificate_path, \
    _get_play_config, should_commit_transaction


class GooglePlayTest(unittest.TestCase):
    def setUp(self):
        self.context = MagicMock()
        self.context.config = {
            'google_play_accounts': {
                'aurora': {
                    'service_account': 'aurora_account',
                    'certificate': '/path/to/aurora.p12',
                },
                'beta': {
                    'service_account': 'beta_account',
                    'certificate': '/path/to/beta.p12',
                },
                'release': {
                    'service_account': 'release_account',
                    'certificate': '/path/to/release.p12',
                },
                'dep': {
                    'service_account': 'dummy_dep',
                    'certificate': '/path/to/dummy_non_p12_file',
                },
            },
        }
        self.context.task = {
            'scopes': ['project:releng:googleplay:release'],
            'payload': {
                'google_play_track': 'alpha'
            },
        }
        self.apks = {
            'x86': '/path/to/x86.apk',
            'arm_v15': '/path/to/arm_v15.apk',
        }

    def test_craft_push_config(self):
        data = {
            'aurora': 'org.mozilla.fennec_aurora',
            'beta': 'org.mozilla.firefox_beta',
            'release': 'org.mozilla.firefox'
        }
        for channel, package_name in data.items():
            self.context.task['scopes'] = ['project:releng:googleplay:{}'.format(channel)]
            self.assertEqual(craft_push_apk_config(self.context, self.apks), {
                'service_account': '{}_account'.format(channel),
                'credentials': '/path/to/{}.p12'.format(channel),
                'commit': False,
                'track': 'alpha',
                'package_name': package_name,
                'apk_x86': '/path/to/x86.apk',
                'apk_arm_v15': '/path/to/arm_v15.apk',
                'update_gp_strings_from_l10n_store': True,
            })

    def test_craft_push_config_allows_rollout_percentage(self):
        self.context.task['payload']['google_play_track'] = 'rollout'
        self.context.task['payload']['rollout_percentage'] = 10
        self.assertEqual(craft_push_apk_config(self.context, self.apks), {
            'service_account': 'release_account',
            'credentials': '/path/to/release.p12',
            'commit': False,
            'track': 'rollout',
            'rollout_percentage': 10,
            'package_name': 'org.mozilla.firefox',
            'apk_x86': '/path/to/x86.apk',
            'apk_arm_v15': '/path/to/arm_v15.apk',
            'update_gp_strings_from_l10n_store': True,
        })

    def test_craft_push_config_allows_to_contact_google_play_or_not(self):
        self.context.task['scopes'] = ['project:releng:googleplay:aurora']
        config = craft_push_apk_config(self.context, self.apks)
        self.assertNotIn('do_not_contact_google_play', config)

        self.context.task['scopes'] = ['project:releng:googleplay:dep']
        config = craft_push_apk_config(self.context, self.apks)
        self.assertTrue(config['do_not_contact_google_play'])

    def test_craft_push_config_allows_committing_apks(self):
        self.context.task['scopes'] = ['project:releng:googleplay:aurora']
        self.context.task['payload']['commit'] = True
        config = craft_push_apk_config(self.context, self.apks)
        self.assertTrue(config['commit'])

    def test_craft_push_config_allows_deprecated_dry_run(self):
        self.context.task['scopes'] = ['project:releng:googleplay:aurora']
        self.context.task['payload']['dry_run'] = False
        config = craft_push_apk_config(self.context, self.apks)
        self.assertTrue(config['commit'])

    def test_craft_push_config_raises_error_when_channel_is_not_part_of_config(self):
        self.context.task['scopes'] = ['project:releng:googleplay:non_exiting_channel']
        self.assertRaises(TaskVerificationError, craft_push_apk_config, self.context, self.apks)

    def test_craft_push_config_raises_error_when_google_play_accounts_does_not_exist(self):
        self.context.config = {}
        self.assertRaises(TaskVerificationError, craft_push_apk_config, self.context, self.apks)

    def test_get_google_play_package_name(self):
        self.assertEqual(get_package_name('aurora'), 'org.mozilla.fennec_aurora')
        self.assertEqual(get_package_name('beta'), 'org.mozilla.firefox_beta')
        self.assertEqual(get_package_name('release'), 'org.mozilla.firefox')

    def test_get_service_account(self):
        self.assertEqual(get_service_account(self.context, 'aurora'), 'aurora_account')
        self.assertEqual(get_service_account(self.context, 'beta'), 'beta_account')
        self.assertEqual(get_service_account(self.context, 'release'), 'release_account')

    def test_get_certificate_path(self):
        self.assertEqual(get_certificate_path(self.context, 'aurora'), '/path/to/aurora.p12')
        self.assertEqual(get_certificate_path(self.context, 'beta'), '/path/to/beta.p12')
        self.assertEqual(get_certificate_path(self.context, 'release'), '/path/to/release.p12')

    def test_get_play_config(self):
        self.assertEqual(_get_play_config(self.context, 'aurora'), {
            'service_account': 'aurora_account', 'certificate': '/path/to/aurora.p12'
        })

        self.assertRaises(TaskVerificationError, _get_play_config, self.context, 'non-existing-channel')

        class FakeContext:
            config = {}

        context_without_any_account = FakeContext()
        self.assertRaises(TaskVerificationError, _get_play_config, context_without_any_account, 'whatever-channel')

    def test_should_commit_transaction(self):
        self.context.task['payload']['dry_run'] = True
        self.assertFalse(should_commit_transaction(self.context))

        self.context.task['payload']['dry_run'] = False
        self.assertTrue(should_commit_transaction(self.context))

        del self.context.task['payload']['dry_run']
        self.context.task['payload']['commit'] = True
        self.assertTrue(should_commit_transaction(self.context))

        self.context.task['payload']['commit'] = False
        self.assertFalse(should_commit_transaction(self.context))

        del self.context.task['payload']['commit']
        self.assertFalse(should_commit_transaction(self.context))

        self.context.task['payload']['commit'] = False
        self.context.task['payload']['dry_run'] = False
        self.assertRaises(TaskVerificationError, should_commit_transaction, self.context)
