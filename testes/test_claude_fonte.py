"""Testes do claude-fonte num HOME descartável, com systemctl, switcher e agent-deck falsos."""
import importlib.machinery
import importlib.util
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace

SCRIPT = Path(__file__).resolve().parent.parent / 'claude-fonte'


def carregar(home):
    os.environ['CLAUDE_FONTE_HOME'] = str(home)
    loader = importlib.machinery.SourceFileLoader('claude_fonte', str(SCRIPT))
    spec = importlib.util.spec_from_loader('claude_fonte', loader)
    m = importlib.util.module_from_spec(spec)
    loader.exec_module(m)
    return m


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        (self.home / '.claude').mkdir()
        (self.home / '.config/seazone-ia').mkdir(parents=True)
        (self.home / '.config/seazone-ia/chave').write_text('x')
        self.settings = self.home / '.claude/settings.json'
        self.settings.write_text(json.dumps({'model': 'opus', 'env': {'OUTRA': '1'},
                                             'hooks': {'Stop': [{'hooks': [{'type': 'command', 'command': 'x'}]}]}}))
        self.m = carregar(self.home)
        self.chamadas, self.timer = [], 'inactive'

        def falso(cmd, **kw):
            self.chamadas.append(cmd)
            if cmd[:3] == ['systemctl', '--user', 'is-active']:
                return SimpleNamespace(returncode=0, stdout=self.timer + '\n', stderr='')
            return SimpleNamespace(returncode=0, stdout='[]', stderr='')
        self.m.rodar = falso

    def tearDown(self):
        self.tmp.cleanup()

    def usar(self, fonte):
        with redirect_stdout(io.StringIO()) as out:
            rc = self.m.usar(fonte)
        return rc, out.getvalue()

    def lido(self):
        return json.loads(self.settings.read_text())


class TestUsar(Base):
    def test_portal_poe_helper_e_base_e_preserva_o_resto(self):
        self.assertEqual(self.usar('portal')[0], 0)
        d = self.lido()
        self.assertTrue(d['apiKeyHelper'].endswith('.config/seazone-ia/chave.sh'))
        self.assertEqual(d['env'], {'OUTRA': '1', 'ANTHROPIC_BASE_URL': 'https://ia.seazone.dev'})
        self.assertEqual((d['model'], list(d['hooks'])), ('opus', ['Stop']))
        self.assertEqual(self.m.fonte_do_settings(d), 'portal')

    def test_fonte_antiga_recusada(self):
        self.assertEqual(self.usar('bill')[0], 2)

    def test_login_tira_proxy_e_tokens_soltos(self):
        self.usar('portal')
        d = self.lido(); d['env']['ANTHROPIC_AUTH_TOKEN'] = 'velho'; self.settings.write_text(json.dumps(d))
        self.usar('login')
        d = self.lido()
        self.assertNotIn('apiKeyHelper', d)
        self.assertEqual(d['env'], {'OUTRA': '1'})
        self.assertEqual(self.m.fonte_do_settings(d), 'login')

    def test_sair_do_switcher_desliga_timer_devolve_conta_e_pede_login(self):
        sw = self.home / '.claude-switcher'; sw.mkdir(); (sw / 'active.json').write_text('{}')
        self.timer = 'active'
        rc, out = self.usar('login')
        self.assertEqual(rc, 0)
        self.assertIn(['systemctl', '--user', 'disable', '--now', self.m.TIMER], self.chamadas)
        self.assertIn(['switcher', 'logout'], self.chamadas)
        self.assertTrue((sw / 'nao-me-gerencie').exists())
        self.assertIn('/login', out)

    def test_sessao_do_switcher_sem_conta_nao_faz_logout(self):  # o logout apagaria o login Google
        sw = self.home / '.claude-switcher'; sw.mkdir(); (sw / 'session.json').write_text('{}')
        rc, out = self.usar('portal')
        self.assertEqual(rc, 0)
        self.assertNotIn(['switcher', 'logout'], self.chamadas)
        self.assertNotIn('/login', out)

    def test_switcher_sem_sessao_nao_mexe_em_nada(self):
        antes = self.settings.read_text()
        rc, out = self.usar('switcher')
        self.assertEqual(rc, 1)
        self.assertIn('claude-fonte login-switcher', out)
        self.assertEqual(self.settings.read_text(), antes)
        self.assertNotIn(['switcher', 'switch'], self.chamadas)

    def test_switcher_com_sessao_liga_timer_tira_marcador_e_poe_gancho(self):
        sw = self.home / '.claude-switcher'; sw.mkdir()
        (sw / 'session.json').write_text('{}'); (sw / 'nao-me-gerencie').touch()
        self.usar('portal')
        rc, _ = self.usar('switcher')
        self.assertEqual(rc, 0)
        self.assertFalse((sw / 'nao-me-gerencie').exists())
        self.assertIn(['systemctl', '--user', 'enable', '--now', self.m.TIMER], self.chamadas)
        d = self.lido()
        self.assertNotIn('apiKeyHelper', d)
        self.assertEqual(self.m.fonte_do_settings(d), 'switcher')
        self.usar('switcher')  # de novo: um gancho só
        self.assertEqual(len(self.lido()['hooks']['StopFailure']), 1)

    def test_proxy_sem_chave_recusa(self):
        (self.home / '.config/seazone-ia/chave').unlink()
        antes = self.settings.read_text()
        self.assertEqual(self.usar('portal')[0], 1)
        self.assertEqual(self.settings.read_text(), antes)

    def test_cada_troca_guarda_backup(self):
        self.usar('portal'); self.usar('login')
        self.assertEqual(len(list((self.home / '.local/state/claude-fonte/backup').iterdir())), 2)

    def test_fonte_desconhecida(self):
        self.assertEqual(self.usar('xyz')[0], 2)



class TestLoginSwitcher(Base):
    LINK = ('https://accounts.google.com/o/oauth2/v2/auth?client_id=x&redirect_uri=http%3A%2F%2F127.0.0.1%3A45197'
            '%2Fcallback&response_type=code&state=abc')

    def test_porta_do_link(self):
        self.assertEqual(self.m.porta_do_link(self.LINK), 45197)
        self.assertIsNone(self.m.porta_do_link('https://accounts.google.com/x'))

    def test_retorno_valido(self):
        ok = 'http://127.0.0.1:45197/callback?state=abc&code=4/0AB&scope=email'
        self.assertEqual(self.m.retorno_valido('  ' + ok + '\n', 45197), ok)
        self.assertEqual(self.m.retorno_valido(ok.replace('127.0.0.1', 'localhost'), 45197), ok)
        self.assertIsNone(self.m.retorno_valido(ok, 45198))                       # outra tentativa
        self.assertIsNone(self.m.retorno_valido(ok.replace('code=4/0AB&', ''), 45197))  # sem code
        self.assertIsNone(self.m.retorno_valido('http://evil.com:45197/callback?code=1', 45197))

    def test_status_mostra_falta_de_login(self):
        with redirect_stdout(io.StringIO()) as out:
            self.m.status()
        self.assertIn('claude-fonte login-switcher', out.getvalue())

    def test_usar_switcher_sem_login_aponta_o_comando(self):
        self.assertIn('claude-fonte login-switcher', self.usar('switcher')[1])



class TestReabrir(Base):
    def test_nao_ressuscita_sessao_morta_e_respeita_grupos(self):
        lista = [{'id': 'a', 'title': 'A', 'status': 'waiting', 'group': 'G1', 'command': 'claude'},
                 {'id': 'b', 'title': 'B', 'status': 'error', 'group': 'G1', 'command': 'claude'},
                 {'id': 'c', 'title': 'C', 'status': 'waiting', 'group': 'G2', 'command': 'claude'}]
        feitos = []

        def falso(cmd, **kw):
            feitos.append(cmd)
            return SimpleNamespace(returncode=0, stdout=json.dumps(lista), stderr='')
        self.m.rodar = falso
        with redirect_stdout(io.StringIO()):
            self.m.reabrir(('G1',))
        reiniciadas = [c[-1] for c in feitos if c[:3] == ['agent-deck', 'session', 'restart']]
        self.assertEqual(reiniciadas, ['a'])


if __name__ == '__main__':
    unittest.main()
