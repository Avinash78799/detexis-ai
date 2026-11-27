from urllib.parse import urlencode

import pytest

from app.rules import evaluate


def command_hit(path='/', value=''):
    return 'command_injection' in {finding.rule_id for finding in evaluate(path, urlencode({'q':value}))}


@pytest.mark.parametrize('path,value', [
    ('/catalog;cat=books;ord=7',''),
    ('/products;id=12;cat=home',''),
    ('/','nested=x&&id=12'),
    ('/',';cat=/tmp/file'),
    ('/', ';cat="images here"'),
    ('/', ';id=17;cat=home'),
])
def test_assignment_words_do_not_masquerade_as_commands(path, value):
    assert not command_hit(path, value)


@pytest.mark.parametrize('value', [
    ';cat=books id',
    '&&id=17 whoami',
    ";cat='two words' /bin/sh -c true",
    ';cat=x;id',
    ';cat=$(id)',
    ';cat=`whoami`',
    ';id >/dev/null',
    '$(cat /etc/passwd)',
    '`id`',
    ';a=1 b=2 c=3 d=4 id',
    ';cat= /usr/bin/id',
    ';cat=books\nid',
])
def test_executable_commands_survive_assignment_and_substitution_evasions(value):
    assert command_hit(value=value)


def test_boundary_fix_does_not_concatenate_request_fields_into_a_command():
    assert not command_hit('/catalog;cat=', 'id')
