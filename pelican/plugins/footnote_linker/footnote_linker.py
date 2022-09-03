"""This plug-in links in-text citations to footnotes and vice-versa."""

import logging
import re

from typing import Union

from pelican import ArticlesGenerator, PagesGenerator, signals  # type: ignore
from pelican.contents import Article, Page  # type: ignore

logger = logging.getLogger(__name__)

RE_REF = re.compile("((?:.|\\n)*?)\\[ref(\\d+)\\]")
REF_SUBNAMES = "abcdefghijklmnopqrstuvwxyz"

RE_FOOTNOTE_HEADING = re.compile("<h[234]>Footnotes")

RE_FOOTNOTE = re.compile("((?:.|\\n)*?)<p>\\[ref(\\d+)\\]((?:.|\\n)*?)</p>")

# pylint: disable=protected-access,too-many-locals,too-many-statements
def link_footnotes(item: Union[Article, Page]) -> None:
    """Process the references on an article or page."""

    # Process references

    ref_matches = list(RE_REF.finditer(item._content))

    footnote_references: dict[str, list[str]] = {}

    if len(ref_matches) == 0:
        # Document has no references
        return

    footnote_heading_match = RE_FOOTNOTE_HEADING.search(item._content)

    if not footnote_heading_match:
        logger.warning(
            'Document "%s" has %i references but no footnotes heading; skipping',
            item.title,
            len(ref_matches),
        )
        return

    footnote_matches = list(RE_FOOTNOTE.finditer(item._content))

    if len(footnote_matches) == 0:
        logger.warning(
            'Document "%s" has %i references but no footnotes; skipping',
            item.title,
            len(ref_matches),
        )
        return

    # Any references found below the footnote heading are footnotes, not in-text
    # references
    footnote_heading_pos = footnote_heading_match.span()[0]

    processed_content = []

    for match in ref_matches:
        content_before = match.group(1)
        note_num = match.group(2)

        ref_pos = match.span(2)[0]

        if len(content_before) >= 1 and content_before[-1] == " ":
            logger.debug(
                "content_before ends with space; replacing with non-breaking space"
            )
            content_before = content_before[:-1] + "&nbsp;"

        processed_content.append(content_before)

        if ref_pos >= footnote_heading_pos:
            # Done finding in-text references
            first_footnote = match

            # Add the consumed footnote back
            processed_content.append(f"[ref{note_num}]")
            break

        if note_num not in footnote_references:
            footnote_references[note_num] = []

        ref_idx = len(footnote_references[note_num])
        ref_name = REF_SUBNAMES[ref_idx : (ref_idx + 1)]

        footnote_references[note_num].append(ref_name)

        processed_content.append(
            f'[<a href="#note-{note_num}" id="ref-{note_num}{ref_name}">{note_num}</a>]'
        )

    content_after = item._content[first_footnote.span()[1] :]
    processed_content.append(content_after)

    content_with_references_processed = "".join(processed_content)

    # Process footnotes

    footnote_matches = list(RE_FOOTNOTE.finditer(content_with_references_processed))

    processed_footnotes = []
    footnotes_without_references = []

    processed_content = []

    for match in footnote_matches:
        content_before = match.group(1)
        note_num = match.group(2)
        content_within = match.group(3)

        processed_content.append(content_before)

        processed_footnotes.append(note_num)

        if note_num not in footnote_references:
            footnotes_without_references.append(note_num)
            reference_links = ""
        elif len(footnote_references[note_num]) == 1:
            reference_links = "".join(
                [
                    f'<a href="#ref-{note_num}{ref_name}">^</a>'
                    for ref_name in footnote_references[note_num]
                ]
            )
            reference_links = f" {reference_links}"
        else:
            reference_links = "".join(
                [
                    f'<a href="#ref-{note_num}{ref_name}">^{ref_name}</a>'
                    for ref_name in footnote_references[note_num]
                ]
            )
            reference_links = f" {reference_links}"

        processed_content.append(
            f'<p id="note-{note_num}">[{note_num}] {content_within}{reference_links}</p>'
        )

    content_after = content_with_references_processed[match.span()[1] :]
    processed_content.append(content_after)

    references_without_footnotes = list(
        filter(
            lambda note_num: note_num not in processed_footnotes,
            footnote_references.keys(),
        )
    )

    if len(references_without_footnotes) > 0:
        logger.warning(
            'Document "%s": Reference(s) %s have no footnotes',
            item.title,
            ", ".join(references_without_footnotes),
        )

    if len(footnotes_without_references) > 0:
        logger.warning(
            'Document "%s": Footnote(s) %s have no references',
            item.title,
            ", ".join(footnotes_without_references),
        )

    item._content = "".join(processed_content)


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
