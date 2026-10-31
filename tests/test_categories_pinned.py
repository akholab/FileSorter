"""Pins the built-in categories, so a change to them is deliberate.

AGENTS.md says to ask the owner before changing the category rules. This test
makes that visible: changing `DEFAULT_CATEGORIES` fails here until this copy is
updated too, and that edit shows up in the pull request.
"""
from categorizer import DEFAULT_CATEGORIES

EXPECTED = {'documents': {'extensions': ['.pdf', '.doc', '.docx', '.txt', '.rtf', '.odt'],
               'keywords': ['document', 'report', 'contract', 'proposal', 'manual'],
               'folders': ['Documents', 'Reports', 'Contracts']},
 'images': {'extensions': ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.svg'],
            'keywords': ['photo', 'image', 'picture', 'screenshot'],
            'folders': ['Images', 'Photos', 'Screenshots']},
 'videos': {'extensions': ['.mp4', '.avi', '.mov', '.wmv', '.flv', '.mkv'],
            'keywords': ['video', 'movie', 'clip', 'recording'],
            'folders': ['Videos', 'Movies', 'Recordings']},
 'audio': {'extensions': ['.mp3', '.wav', '.flac', '.aac', '.ogg'],
           'keywords': ['audio', 'music', 'song', 'podcast'],
           'folders': ['Audio', 'Music', 'Podcasts']},
 'archives': {'extensions': ['.zip', '.rar', '.7z', '.tar', '.gz'],
              'keywords': ['archive', 'backup', 'compressed'],
              'folders': ['Archives', 'Backups']},
 'code': {'extensions': ['.py', '.js', '.html', '.css', '.java', '.cpp', '.c', '.php'],
          'keywords': ['code', 'script', 'program', 'source'],
          'folders': ['Code', 'Scripts', 'Projects']}}


def test_default_categories_are_unchanged():
    assert DEFAULT_CATEGORIES == EXPECTED, (
        "The category rules changed. Ask the owner first (see AGENTS.md), "
        "then update EXPECTED in this file."
    )
    assert list(DEFAULT_CATEGORIES) == list(EXPECTED)  # order matters: first match wins
