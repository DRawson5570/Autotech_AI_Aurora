class Document:
    def __init__(self, metadata=None, page_content=""):
        self.metadata = metadata or {}
        self.page_content = page_content
