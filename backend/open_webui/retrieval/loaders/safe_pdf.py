"""
Safe PDF Loader that handles corrupted images gracefully.

Some PDFs have images with corrupted dimension metadata that don't match
the actual pixel data, causing numpy reshape errors. This wrapper catches
those errors and skips corrupted images instead of failing the entire load.
"""

import logging
from typing import Iterator

from langchain_community.document_loaders import PyPDFLoader
from langchain_community.document_loaders.parsers.pdf import PyPDFParser
from langchain_core.documents import Document

log = logging.getLogger(__name__)


class SafePyPDFParser(PyPDFParser):
    """PyPDFParser that catches image extraction errors."""

    def extract_images_from_page(self, page) -> str:
        """Override to catch KeyError and other errors from problematic images."""
        try:
            return super().extract_images_from_page(page)
        except KeyError as e:
            # Some PDFs have XObjects without /Filter key
            log.warning(
                f"Skipping image extraction on page (missing key {e})"
            )
            return ""
        except ValueError as e:
            if "reshape" in str(e):
                log.warning(
                    f"Skipping corrupted image on page: {e}"
                )
                return ""
            raise
        except Exception as e:
            log.warning(
                f"Error extracting images from page: {e}"
            )
            return ""


class SafePyPDFLoader(PyPDFLoader):
    """
    PyPDFLoader that handles corrupted images gracefully.
    
    Use this instead of PyPDFLoader when extract_images=True to avoid
    crashes on PDFs with malformed image data.
    """

    def __init__(self, file_path: str, *, extract_images: bool = False, **kwargs):
        # Initialize parent but we'll override the parser
        super().__init__(file_path, extract_images=extract_images, **kwargs)
        
        # Replace the parser with our safe version
        if extract_images:
            self.parser = SafePyPDFParser(
                extract_images=True,
                images_parser=self.parser.images_parser if hasattr(self.parser, 'images_parser') else None,
            )

    def lazy_load(self) -> Iterator[Document]:
        """Load pages, catching any remaining errors."""
        try:
            yield from super().lazy_load()
        except ValueError as e:
            if "reshape" in str(e):
                log.error(
                    f"Failed to load PDF due to image error, retrying without images: {e}"
                )
                # Retry without image extraction
                self.parser = SafePyPDFParser(extract_images=False)
                yield from super().lazy_load()
            else:
                raise
        except Exception as e:
            # Catch any other unexpected errors during PDF loading
            log.error(f"Unexpected error loading PDF, retrying without images: {e}")
            try:
                self.parser = SafePyPDFParser(extract_images=False)
                yield from super().lazy_load()
            except Exception as e2:
                log.error(f"PDF load failed even without images: {e2}")
                raise
