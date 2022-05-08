"""This plug-in links in-text citations to footnotes and vice-versa."""

import logging
import re

from typing import Union

from pelican import ArticlesGenerator, PagesGenerator, signals  # type: ignore
from pelican.contents import Article, Page  # type: ignore

logger = logging.getLogger(__name__)

RE_CITATION = re.compile("\\[ref(\\d+)\\]")  # In-text citation
CITATION_SUBNAMES = "abcdefghijklmnopqrstuvwxyz"

RE_NOTE = re.compile("<p>\\[note(\\d+)\\]((.|\\s)*?)</p>")  # Footnote

# pylint: disable=protected-access
def link_footnotes(item: Union[Article, Page]) -> None:
    """Process the references on an article or page."""

    note_citations: dict[str, list[str]] = {}  # Map each note to its in-text citations
    note_nums: list[str] = []
    notes_without_citations: list[str] = []

    match = RE_CITATION.search(item._content)

    # Process in-text citations
    while match is not None:
        note_num = match.group(1)

        if note_num not in note_citations:
            note_citations[note_num] = []

        note_citation_num = len(note_citations[note_num])

        citation_subname = CITATION_SUBNAMES[
            note_citation_num : (note_citation_num + 1)
        ]

        citation_name = f"{citation_subname}"

        note_citations[note_num].append(citation_name)

        item._content = RE_CITATION.sub(
            f'[<a href="#note-\\1" id="citation-{note_num}{citation_name}">\\1</a>]',
            item._content,
            1,
        )

        match = RE_CITATION.search(item._content)

    # Process footnotes
    match = RE_NOTE.search(item._content)

    while match is not None:
        note_num = match.group(1)

        if not note_num in note_citations:
            notes_without_citations.append(note_num)

            item._content = RE_NOTE.sub(
                '<a id="note-\\1">[\\1]</a>\\2</p>',
                item._content,
                1,
            )
        else:
            if len(note_citations[note_num]) == 1:
                citation_link_list = [
                    f'<a href="#citation-{note_num}{citation_name}">^</a>'
                    for citation_name in note_citations[note_num]
                ]
            else:
                citation_link_list = [
                    f'<a href="#citation-{note_num}{citation_name}">^{citation_name}</a>'
                    for citation_name in note_citations[note_num]
                ]

            citation_links = "".join(citation_link_list)

            item._content = RE_NOTE.sub(
                f'<p id="note-\\1">[\\1]\\2 {citation_links}</p>',
                item._content,
                1,
            )

        match = RE_NOTE.search(item._content)

        note_nums.append(note_num)

    citations_without_notes = list(
        filter(lambda note_num: note_num not in note_nums, note_citations.keys())
    )

    if len(citations_without_notes) > 0:
        logger.warning(
            'Document "%s": Citation(s) %s have no notes',
            item.title,
            ", ".join(citations_without_notes),
        )

    if len(notes_without_citations) > 0:
        logger.warning(
            'Document "%s": Footnote(s) %s have no citations',
            item.title,
            ", ".join(notes_without_citations),
        )


def process_articles(generator: ArticlesGenerator) -> None:
    """Process all articles."""

    list_names = [
        "articles",
        "translations",
        "hidden_articles",
        "hidden_translations",
        "drafts",
        "drafts_translations",
    ]

    for list_name in list_names:
        item_list = getattr(generator, list_name)

        for item in item_list:
            link_footnotes(item)


def process_pages(generator: PagesGenerator) -> None:
    """Process all pages."""

    list_names = [
        "pages",
        "translations",
        "hidden_pages",
        "hidden_translations",
        "draft_pages",
        "draft_translations",
    ]

    for list_name in list_names:
        item_list = getattr(generator, list_name)

        for item in item_list:
            link_footnotes(item)


def register() -> None:
    """Register the plug-in with Pelican."""
    signals.article_generator_finalized.connect(process_articles)
    signals.page_generator_finalized.connect(process_pages)
