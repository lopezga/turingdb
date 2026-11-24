import unittest
from unittest.mock import patch
import create


class InstallerTests(unittest.TestCase):
    def test_wsl_uses_existing_linux_docker(self):
        with patch.object(create.os, 'name', 'posix'), patch.object(create.shutil, 'which', return_value='/usr/bin/docker'):
            self.assertEqual(create.docker_path(), '/usr/bin/docker')

    def test_missing_linux_docker_does_not_fall_back_to_desktop(self):
        with patch.object(create.os, 'name', 'posix'), patch.object(create.shutil, 'which', return_value=None):
            with self.assertRaisesRegex(ValueError, 'No se encuentra docker en el PATH de Linux/WSL'):
                create.docker_path()

    def test_profile_uses_docker_memory(self):
        self.assertEqual(create.choose_profile(16 * create.GIB, 'auto'), 'full')
        self.assertEqual(create.choose_profile(12 * create.GIB, 'auto'), 'compact')
        with self.assertRaises(ValueError):
            create.choose_profile(8 * create.GIB, 'auto')
        with self.assertRaises(ValueError):
            create.choose_profile(12 * create.GIB, 'full')

    def test_adaptation_keeps_credentials_and_disables_local_llm_in_compact(self):
        original = {'NEO4J_PASSWORD': 'existing-secret', 'NL_PROVIDER': 'ollama', 'DATA_DIR': './data'}
        compact = create.apply_resources(original, 'compact', 2)
        self.assertEqual(compact['NEO4J_PASSWORD'], original['NEO4J_PASSWORD'])
        self.assertEqual(compact['NL_PROVIDER'], 'rules')
        self.assertEqual(compact['ENGINE_MEMORY'], '5g')
        self.assertEqual(compact['ENGINE_CPUS'], '2')
        self.assertEqual(original['NL_PROVIDER'], 'ollama')

    def test_external_provider_survives_resource_adaptation(self):
        result = create.apply_resources({'NL_PROVIDER': 'openai-compatible'}, 'compact', 16)
        self.assertEqual(result['NL_PROVIDER'], 'openai-compatible')
        self.assertEqual(result['ENGINE_CPUS'], '4')
