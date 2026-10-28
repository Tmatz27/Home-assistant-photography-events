"""Pure release gating: no subprocess, tag, release or network operation."""
import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('ha_release_policy',Path(__file__).parents[1]/'tools/ha_release_policy.py')
policy=importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)


class ReleasePolicyTests(unittest.TestCase):
    def test_development_candidate_is_prerelease_and_cannot_replace_latest(self):
        args=policy.release_arguments('0.17.0-dev.4','a'*40)
        self.assertIn('--prerelease',args)
        self.assertIn('--latest=false',args)
        self.assertNotIn('--latest',args)
        self.assertEqual(args[args.index('--target')+1],'a'*40)

    def test_stable_policy_remains_explicit(self):
        args=policy.release_arguments('0.17.0','a'*40)
        self.assertIn('--latest',args)
        self.assertNotIn('--prerelease',args)

    def test_bad_version_or_unpinned_commit_cannot_publish(self):
        for version,commit in [('0.17.0-dev.0','a'*40),('0.17.0\nlatest','a'*40),('0.17.0-dev.4','main')]:
            with self.subTest(version=version,commit=commit):
                with self.assertRaises(ValueError):policy.release_arguments(version,commit)
