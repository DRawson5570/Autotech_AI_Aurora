from addons.autodb_tool.parsers import parse_makes, parse_manual_list, parse_manual_content

SAMPLE_MAKES_HTML = '''
<html><body>
<ul>
<li><a href="/autodb/Acura/">Acura</a></li>
<li><a href="/autodb/Audi/">Audi</a></li>
<li><a href="/autodb/BMW/">BMW</a></li>
</ul>
</body></html>
'''

SAMPLE_MANUAL_LIST_HTML = '''
<html><body>
<div>
<a href="/autodb/Chrysler/">Chrysler</a>
<table class="manuals">
<tr><td><a href="/autodb/Chrysler/manual1.html">Manual 1</a></td></tr>
<tr><td><a href="/autodb/Chrysler/manual2.html">Manual 2</a></td></tr>
</table>
</div>
</body></html>
'''

SAMPLE_MANUAL_HTML = '''
<html><body>
<h1>Title of Manual</h1>
<p>This bulletin involves discussing FCA US LLC position with regard to collision repair industry awareness regarding scan tool equipment and economic shop solutions with wiTECH support.</p>
<h2>Discussion</h2>
<p>FCA vehicles, systems, and components are engineered...</p>
</body></html>
'''


def test_parse_makes():
    makes = parse_makes(SAMPLE_MAKES_HTML, "http://example.com/autodb")
    assert any(m['name'] == 'Acura' for m in makes)
    assert any(m['name'] == 'Audi' for m in makes)


def test_parse_manual_list():
    manuals = parse_manual_list(SAMPLE_MANUAL_LIST_HTML, "http://example.com/autodb")
    titles = [m['title'] for m in manuals]
    assert 'Manual 1' in titles and 'Manual 2' in titles


def test_parse_manual_content():
    text = parse_manual_content(SAMPLE_MANUAL_HTML)
    assert 'Title of Manual' in text
    assert 'Discussion' in text
    assert 'scan tool' in text.lower()
