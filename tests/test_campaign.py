"""Offline operator tests: no Google credentials, network or GPU jobs."""
import argparse
import csv
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('campaign', ROOT / '.agents/skills/bindcraft-colab/scripts/campaign.py')
campaign = importlib.util.module_from_spec(spec)
spec.loader.exec_module(campaign)


def arguments(**changes):
    defaults = dict(name='test', accepted=50, target_file=None, target_name=None,
                    chains=None, settings=None, exclude=None, gpus='T4,T4,T4,L4,L4',
                    seed_base=1000, max_trajectories=None, unbounded=False)
    return argparse.Namespace(**{**defaults, **changes})


class CampaignTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name) / 'project'

    def prepare(self, **changes):
        with patch.object(campaign, 'cli', side_effect=AssertionError('Preparation must not allocate compute')):
            campaign.prepare(arguments(**changes), self.project)
        return campaign.read(self.project / 'campaign_manifest.json')

    def test_five_quotas_unique_seeds_and_bounded_default(self):
        manifest = self.prepare()
        configs = [campaign.read(p) for p in sorted((self.project / 'campaigns').glob('*.json'))]
        self.assertEqual(len(configs), 5)
        self.assertEqual(sum(c['number_of_final_designs'] for c in configs), 50)
        self.assertEqual(len({c['campaign_seed'] for c in configs}), 5)
        self.assertTrue(all(c['max_trajectories'] == 100 and c['desperation'] is False for c in configs))
        self.assertEqual(len(manifest['workers']), 5)
        self.assertTrue(all(c['targets'][0]['target_path'] == '/content/target_input.fasta' for c in configs))

    def test_refuses_overwrite(self):
        self.prepare()
        before = (self.project / 'campaign_manifest.json').read_bytes()
        with self.assertRaises(ValueError):
            campaign.prepare(arguments(), self.project)
        self.assertEqual((self.project / 'campaign_manifest.json').read_bytes(), before)

    def test_invalid_quota_does_not_create_project(self):
        with self.assertRaises(ValueError):
            campaign.prepare(arguments(accepted=13), self.project)
        self.assertFalse(self.project.exists())

    def test_structured_input_retains_type_and_chain(self):
        target = Path(self.temp.name) / 'target.cif'
        target.write_text('data_target\n#\n')
        self.prepare(target_file=str(target), chains='A', unbounded=True)
        config = campaign.read(self.project / 'campaigns/w1.json')
        self.assertTrue(config['targets'][0]['target_path'].endswith('.cif'))
        self.assertEqual(config['targets'][0]['chains'], 'A')
        self.assertNotIn('crop_fasta_sequence', config)
        self.assertNotIn('max_trajectories', config)

    def test_fetch_deduplication_exclusion_and_structure_packaging(self):
        manifest = self.prepare()
        state = self.project / 'results/tdp43-test'
        campaign.write(state / 'exclude_sequences.json', ['AAAA'])
        table = io.StringIO()
        writer = csv.DictWriter(table, fieldnames=['design', 'Binder_Sequence', 'i_pDAE'])
        writer.writeheader()
        writer.writerows([{'design': 'one', 'Binder_Sequence': 'AAAA', 'i_pDAE': '.4'},
                          {'design': 'two', 'Binder_Sequence': 'CCCC', 'i_pDAE': '.3'}])
        for index in (1, 2):
            folder = state / f'w{index}'
            folder.mkdir()
            with zipfile.ZipFile(folder / 'snapshot.zip', 'w') as archive:
                archive.writestr('3_Ranked/!_Ranked.csv', table.getvalue())
                archive.writestr('3_Ranked/one.cif', 'data_one\n#\n')
                archive.writestr('3_Ranked/two.cif', 'data_two\n#\n')
        campaign.fetch(self.project, manifest)
        audit = campaign.read(state / 'accepted/audit.json')
        self.assertEqual(audit['unique_passing_count'], 1)
        self.assertFalse(audit['independent_refolding_performed'])
        self.assertEqual(len(list((state / 'accepted').glob('*.cif'))), 1)
        with zipfile.ZipFile(self.project / 'test-results.zip') as archive:
            self.assertIsNone(archive.testzip())
            self.assertIn('accepted/passing_designs.fasta', archive.namelist())


if __name__ == '__main__':
    unittest.main()
