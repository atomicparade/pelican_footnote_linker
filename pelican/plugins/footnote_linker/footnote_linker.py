"""This plug-in links in-text citations to footnotes and vice-versa."""

import logging
import re

from dataclasses import dataclass
from typing import Pattern, Union

from pelican import ArticlesGenerator, PagesGenerator, Pelican, signals  # type: ignore
from pelican.contents import Article, Page  # type: ignore

logger = logging.getLogger(__name__)

CONTENT_REGEX = r"((?:.|\n)*?)"

REFERENCE_REGEX_DEFAULT = r"\[ref\d+\]"
RE_REFERENCE_DEFAULT: Pattern[str]

REF_SUBNAMES = "abcdefghijklmnopqrstuvwxyz"

RE_FOOTNOTE_HEADING = re.compile(r"<h[234]>Footnotes")

RE_FOOTNOTE_DEFAULT: Pattern[str]


def make_reference_regex(regex: str) -> str:
    return f"{CONTENT_REGEX}({regex})"


def make_footnote_regex(regex: str) -> str:
    return f"{CONTENT_REGEX}<p>({regex}){CONTENT_REGEX}</p>"


# pylint: disable=global-statement
def initalize_plugin(pelican_: Pelican) -> None:
    global RE_REFERENCE_DEFAULT
    global RE_FOOTNOTE_DEFAULT

    pattern = pelican_.settings.get("REFERENCE_REGEX", REFERENCE_REGEX_DEFAULT)
    RE_REFERENCE_DEFAULT = re.compile(make_reference_regex(pattern))
    RE_FOOTNOTE_DEFAULT = re.compile(make_footnote_regex(pattern))


@dataclass
class Footnote:
    num: int
    html_id: str
    ref_count: int

    def __init__(self, num: int):
        self.num = num
        self.html_id = f"note-{self.num}"
        self.ref_count = 0

    def add_ref(self) -> str:
        self.ref_count += 1
        return self.get_ref_html_id(self.ref_count)

    def get_ref_name(self, ref_num: int) -> str:
        return REF_SUBNAMES[ref_num - 1]

    def get_ref_html_id(self, ref_num: int) -> str:
        return f"ref-{self.num}{self.get_ref_name(ref_num)}"


# pylint: disable=protected-access,too-many-locals,too-many-statements
def link_footnotes(item: Union[Article, Page]) -> None:
    """Link the references and footnotes on an article or page to each other."""
    reference_regex = item.metadata.get("referenceregex", None)

    if reference_regex:
        logger.debug("Using custom reference regex: %s", reference_regex)
        re_reference = re.compile(make_reference_regex(reference_regex))
        re_footnote = re.compile(make_footnote_regex(reference_regex))
    else:
        re_reference = RE_REFERENCE_DEFAULT
        re_footnote = RE_FOOTNOTE_DEFAULT

    # Process references
    ref_matches = list(re_reference.finditer(item._content))

    footnotes: dict[str, Footnote] = {}

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

    footnote_matches = list(re_footnote.finditer(item._content))

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
        footnote_name = match.group(2)

        ref_pos = match.span(2)[0]

        # If there's a space immediately before the reference, replace it with
        # a non-breaking space to keep the last word and the reference together
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
            processed_content.append(footnote_name)
            break

        if footnote_name not in footnotes:
            footnotes[footnote_name] = Footnote(len(footnotes) + 1)

        footnote = footnotes[footnote_name]

        ref_id = footnote.add_ref()

        processed_content.append(
            f'[<a href="#{footnote.html_id}" id="{ref_id}">{footnote.num}</a>]'
        )

    content_after = item._content[first_footnote.span()[1] :]
    processed_content.append(content_after)

    content_with_references_processed = "".join(processed_content)

    # Process footnotes
    footnote_matches = list(re_footnote.finditer(content_with_references_processed))

    processed_footnotes = []
    footnotes_without_references = []

    processed_content = []

    for match in footnote_matches:
        content_before = match.group(1)
        footnote_name = match.group(2)
        content_within = match.group(3)

        processed_content.append(content_before)

        processed_footnotes.append(footnote_name)

        if footnote_name not in footnotes:
            footnotes_without_references.append(footnote_name)
            processed_content.append(match.group(0))
            continue

        footnote = footnotes[footnote_name]

        if footnote.ref_count == 1:
            reference_links = f' <a href="#{footnote.get_ref_html_id(1)}">^</a>'
        else:
            reference_links = "".join(
                [
                    f'<a href="#{footnote.get_ref_html_id(i)}">^{footnote.get_ref_name(i)}</a>'
                    for i in range(1, footnote.ref_count + 1)
                ]
            )
            reference_links = f" {reference_links}"

        processed_content.append(
            f'<p id="{footnote.html_id}">[{footnote.num}] {content_within}{reference_links}</p>'
        )

    content_after = content_with_references_processed[match.span()[1] :]
    processed_content.append(content_after)

    references_without_footnotes = list(
        filter(
            lambda footnote_name: footnote_name not in processed_footnotes,
            footnotes.keys(),
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
    signals.initialized.connect(initalize_plugin)
    signals.article_generator_finalized.connect(process_articles)
    signals.page_generator_finalized.connect(process_pages)
