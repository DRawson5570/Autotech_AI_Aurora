Autodb Tool
===========

Lightweight integration for Operation CHARM (autodb) - provides:

- get_makes() -> list available makes
- get_manual_list(make) -> list manuals/pages for a make
- get_manual_text(url) -> raw text content extracted from manual page

Usage example:

```python
from addons.autodb_tool import AutodbAPI
api = AutodbAPI()
print(api.get_makes())
```