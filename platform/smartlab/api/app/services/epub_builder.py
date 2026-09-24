"""
EPUB3 Builder — Assembles AI-enriched chapters into an accessible EPUB3 file.
"""
import os
import io
import uuid
import logging
from datetime import datetime
from typing import Optional
from ebooklib import epub

logger = logging.getLogger("smartlab.epub")


def build_epub3(book_data: dict) -> bytes:
    """
    Build an EPUB3 file from book_data.

    book_data structure:
    {
      "id": "uuid",
      "title": "Book Title",
      "author": "Author Name",
      "description": "...",
      "language": "en",
      "publisher": "i3 Technologies",
      "cover_image_bytes": b"...",   # optional
      "chapters": [
        {
          "title": "Chapter 1",
          "content_html": "<p>...</p>",
          "narration_url": "https://...",    # optional
          "image_url": "https://...",        # optional
        }
      ]
    }

    Returns EPUB3 bytes.
    """
    book = epub.EpubBook()
    book_id = book.get("id", str(uuid.uuid4()))

    # Metadata
    book.set_identifier(f"i3-{book_id}")
    book.set_title(book["title"])
    book.set_language(book.get("language", "en"))
    book.add_author(book.get("author", "i3 SmartLab Author"))
    book.add_metadata("DC", "publisher", book.get("publisher", "i3 Technologies"))
    book.add_metadata("DC", "description", book.get("description", ""))
    book.add_metadata("DC", "date", datetime.utcnow().strftime("%Y-%m-%d"))

    # EPUB3 accessibility metadata
    book.add_metadata(None, "meta", "", {
        "property": "schema:accessibilityFeature",
        "content": "alternativeText",
    })
    book.add_metadata(None, "meta", "", {
        "property": "schema:accessMode",
        "content": "textual",
    })

    # CSS
    style_css = epub.EpubItem(
        uid="style-main",
        file_name="styles/main.css",
        media_type="text/css",
        content=_get_epub_css(),
    )
    book.add_item(style_css)

    # Cover image
    cover_image_bytes = book.get("cover_image_bytes")
    if cover_image_bytes:
        cover_img = epub.EpubItem(
            uid="cover-image",
            file_name="images/cover.jpg",
            media_type="image/jpeg",
            content=cover_image_bytes,
        )
        book.add_item(cover_img)
        book.set_cover("images/cover.jpg", cover_image_bytes)

    # Table of Contents + spine
    chapters_epub = []
    toc_items = []

    # Title page
    title_page = epub.EpubHtml(
        title=book["title"],
        file_name="title-page.xhtml",
        lang=book.get("language", "en"),
    )
    title_page.content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="{book.get('language', 'en')}">
<head>
  <title>{book["title"]}</title>
  <link rel="stylesheet" type="text/css" href="styles/main.css"/>
</head>
<body>
  <section epub:type="titlepage" class="title-page">
    <h1>{book["title"]}</h1>
    <p class="author">{book.get("author", "")}</p>
    <p class="publisher">{book.get("publisher", "i3 Technologies")}</p>
    <p class="description">{book.get("description", "")}</p>
  </section>
</body>
</html>"""
    book.add_item(title_page)
    chapters_epub.append(title_page)

    # Chapters
    for ch_i, chapter in enumerate(book.get("chapters", [])):
        ch_filename = f"chapter-{ch_i+1:02d}.xhtml"
        ch_title    = chapter["title"]
        ch_html     = chapter.get("content_html", "")
        narr_url    = chapter.get("narration_url", "")

        # Add audio element if narration exists
        audio_html = ""
        if narr_url:
            audio_html = f"""
  <aside epub:type="aside" class="audio-aside">
    <audio controls="controls" epub:type="voice">
      <source src="{narr_url}" type="audio/mpeg"/>
      Listen to this chapter
    </audio>
  </aside>"""

        ch_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="{book.get('language', 'en')}">
<head>
  <title>{ch_title}</title>
  <link rel="stylesheet" type="text/css" href="styles/main.css"/>
</head>
<body>
  <section epub:type="chapter" class="chapter">
    <h2 class="chapter-title">{ch_title}</h2>
    {audio_html}
    <div class="chapter-content">
      {ch_html}
    </div>
  </section>
</body>
</html>"""

        ch_epub = epub.EpubHtml(
            title=ch_title,
            file_name=ch_filename,
            lang=book.get("language", "en"),
        )
        ch_epub.content = ch_content
        ch_epub.add_item(style_css)
        book.add_item(ch_epub)
        chapters_epub.append(ch_epub)
        toc_items.append(epub.Link(ch_filename, ch_title, f"chapter-{ch_i+1}"))

    # NCX navigation
    book.toc = tuple(toc_items)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    # Spine
    book.spine = ["nav"] + chapters_epub

    # Write to bytes
    buf = io.BytesIO()
    epub.write_epub(buf, book, {})
    return buf.getvalue()


def _get_epub_css() -> str:
    return """
/* i3 SmartLab EPUB3 Stylesheet */
body {
  font-family: "Georgia", "Times New Roman", serif;
  font-size: 1em;
  line-height: 1.7;
  color: #1f2328;
  margin: 1em 1.5em;
}
.title-page {
  text-align: center;
  margin-top: 3em;
}
h1 {
  font-size: 2em;
  color: #1e2761;
  margin-bottom: 0.5em;
}
h2.chapter-title {
  font-size: 1.5em;
  color: #1e2761;
  border-bottom: 2px solid #1e2761;
  padding-bottom: 0.25em;
  margin: 1em 0 0.75em;
}
h3 {
  font-size: 1.2em;
  color: #374151;
  margin: 1em 0 0.5em;
}
p {
  margin-bottom: 0.75em;
  text-align: justify;
  hyphens: auto;
}
ul, ol {
  margin: 0.5em 0 0.75em 1.5em;
}
li {
  margin-bottom: 0.4em;
}
.author {
  font-size: 1.1em;
  color: #57606a;
  margin-top: 0.5em;
}
.publisher {
  font-size: 0.9em;
  color: #57606a;
}
.description {
  font-style: italic;
  color: #374151;
  margin-top: 1em;
}
.audio-aside {
  background: #eff6ff;
  border-left: 3px solid #3b82d4;
  padding: 0.75em 1em;
  margin: 1em 0;
  border-radius: 0 5px 5px 0;
}
.chapter-content img {
  max-width: 100%;
  height: auto;
  display: block;
  margin: 1em auto;
}
blockquote {
  border-left: 4px solid #e5e7eb;
  padding-left: 1em;
  color: #57606a;
  font-style: italic;
  margin: 1em 0;
}
code {
  font-family: "Courier New", monospace;
  background: #f3f4f6;
  padding: 0.1em 0.4em;
  border-radius: 3px;
  font-size: 0.9em;
}
"""
