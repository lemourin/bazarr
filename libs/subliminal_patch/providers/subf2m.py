# -*- coding: utf-8 -*-

import functools
import logging

from bs4 import BeautifulSoup as bso
from guessit import guessit
from requests import Session
from subliminal_patch.core import Episode
from subliminal_patch.core import Movie
from subliminal_patch.exceptions import APIThrottled
from subliminal_patch.providers import Provider
from subliminal_patch.providers.utils import get_archive_from_bytes
from subliminal_patch.providers.utils import get_subtitle_from_archive
from subliminal_patch.providers.utils import update_matches
from subliminal_patch.subtitle import Subtitle
from subzero.language import Language

logger = logging.getLogger(__name__)


class Subf2mSubtitle(Subtitle):
    provider_name = "subf2m"
    hash_verifiable = False

    def __init__(self, language, page_link, release_info, episode_number=None):
        super().__init__(language, page_link=page_link)

        self.release_info = release_info
        self.episode_number = episode_number

        self._matches = set(
            ("title", "year")
            if episode_number is None
            else ("title", "series", "season", "episode")
        )

    def get_matches(self, video):
        update_matches(self._matches, video, self.release_info)

        return self._matches

    @property
    def id(self):
        return self.page_link


_BASE_URL = "https://subf2m.co"

# TODO: add more seasons and languages

_SEASONS = (
    "First",
    "Second",
    "Third",
    "Fourth",
    "Fifth",
    "Sixth",
    "Seventh",
    "Eighth",
    "Ninth",
    "Tenth",
    "Eleventh",
    "Twelfth",
    "Thirdteenth",
    "Fourthteenth",
    "Fifteenth",
    "Sixteenth",
    "Seventeenth",
    "Eightheenth",
    "Nineteenth",
    "Tweentieth",
)

_LANGUAGE_MAP = {
    "english": "eng",
    "farsi_persian": "per",
    "arabic": "ara",
    "spanish": "spa",
    "portuguese": "por",
    "italian": "ita",
    "dutch": "dut",
    "hebrew": "heb",
    "indonesian": "ind",
}


class Subf2mProvider(Provider):
    provider_name = "subf2m"

    _supported_languages = {}
    _supported_languages["brazillian-portuguese"] = Language("por", "BR")

    for key, val in _LANGUAGE_MAP.items():
        _supported_languages[key] = Language.fromalpha3b(val)

    _supported_languages_reversed = {
        val: key for key, val in _supported_languages.items()
    }

    languages = set(_supported_languages.values())

    video_types = (Episode, Movie)
    subtitle_class = Subf2mSubtitle

    def initialize(self):
        self._session = Session()
        self._session.headers.update({"user-agent": "Bazarr"})

    def terminate(self):
        self._session.close()

    def _gen_results(self, query):
        req = self._session.get(
            f"{_BASE_URL}/subtitles/searchbytitle?query={query.replace(' ', '+')}&l=",
            stream=True,
        )
        text = "\n".join(line for line in req.iter_lines(decode_unicode=True) if line)
        soup = bso(text, "html.parser")

        for title in soup.select("li div[class='title'] a"):
            yield title

    def _search_movie(self, title, year):
        title = title.lower()
        year = f"({year})"

        found_movie = None

        for result in self._gen_results(title):
            text = result.text.lower()
            if title.lower() in text and year in text:
                found_movie = result.get("href")
                logger.debug("Movie found: %s", found_movie)
                break

        return found_movie

    def _search_tv_show_season(self, title, season):
        try:
            season_str = f"{_SEASONS[season - 1]} Season"
        except IndexError:
            logger.debug("Season number not supported: %s", season)
            return None

        expected_result = f"{title} - {season_str}".lower()

        found_tv_show_season = None

        for result in self._gen_results(title):
            if expected_result in result.text.lower():
                found_tv_show_season = result.get("href")
                logger.debug("TV Show season found: %s", found_tv_show_season)
                break

        return found_tv_show_season

    def _find_movie_subtitles(self, path, language):
        soup = self._get_subtitle_page_soup(path, language)
        subtitles = []

        for item in soup.select("li.item"):
            subtitle = _get_subtitle_from_item(item, language)
            if subtitle is None:
                continue

            logger.debug("Found subtitle: %s", subtitle)
            subtitles.append(subtitle)

        return subtitles

    def _find_episode_subtitles(self, path, season, episode, language):
        soup = self._get_subtitle_page_soup(path, language)

        subtitles = []

        for item in soup.select("li.item"):
            valid_item = None
            clean_text = " ".join(item.text.split())

            if not clean_text:
                continue

            # It will return list values
            guess = _memoized_episode_guess(clean_text)

            if "season" not in guess:
                logger.debug("Nothing guessed from release: %s", clean_text)
                continue

            if season in guess["season"] and episode in guess.get("episode", []):
                logger.debug("Episode match found: %s - %s", guess, clean_text)
                valid_item = item

            elif season in guess["season"] and not "episode" in guess:
                logger.debug("Season pack found: %s", clean_text)
                valid_item = item

            if valid_item is None:
                continue

            subtitle = _get_subtitle_from_item(item, language, episode)

            if subtitle is None:
                continue

            logger.debug("Found subtitle: %s", subtitle)
            subtitles.append(subtitle)

        return subtitles

    def _get_subtitle_page_soup(self, path, language):
        language_path = self._supported_languages_reversed[language]

        req = self._session.get(f"{_BASE_URL}{path}/{language_path}", stream=True)
        text = "\n".join(line for line in req.iter_lines(decode_unicode=True) if line)

        return bso(text, "html.parser")

    def list_subtitles(self, video, languages):
        is_episode = isinstance(video, Episode)

        if is_episode:
            result = self._search_tv_show_season(video.series, video.season)
        else:
            result = self._search_movie(video.title, video.year)

        if result is None:
            logger.debug("No results")
            return []

        subtitles = []

        for language in languages:
            if is_episode:
                subtitles.extend(
                    self._find_episode_subtitles(
                        result, video.season, video.episode, language
                    )
                )
            else:
                subtitles.extend(self._find_movie_subtitles(result, language))

        return subtitles

    def download_subtitle(self, subtitle):
        # TODO: add MustGetBlacklisted support

        req = self._session.get(subtitle.page_link, stream=True)
        text = "\n".join(line for line in req.iter_lines(decode_unicode=True) if line)
        soup = bso(text, "html.parser")
        try:
            download_url = _BASE_URL + str(
                soup.select_one("a[id='downloadButton']")["href"]  # type: ignore
            )
        except (AttributeError, KeyError):
            raise APIThrottled(f"Couldn't get download url from {subtitle.page_link}")

        downloaded = self._session.get(download_url, allow_redirects=True)

        archive = get_archive_from_bytes(downloaded.content)

        if archive is None:
            raise APIThrottled(f"Invalid archive: {subtitle.page_link}")

        subtitle.content = get_subtitle_from_archive(
            archive, episode=subtitle.episode_number
        )


@functools.lru_cache(2048)
def _memoized_episode_guess(content):
    # Use include to save time from unnecessary checks
    return guessit(
        content,
        {
            "type": "episode",
            # Add codec keys to avoid matching x264, 5.1, etc as episode info
            "includes": ["season", "episode", "video_codec", "audio_codec"],
            "enforce_list": True,
        },
    )


def _get_subtitle_from_item(item, language, episode_number=None):
    release_info = [
        rel.text.strip() for rel in item.find("ul", {"class": "scrolllist"})
    ]

    try:
        text = item.find("div", {"class": "comment-col"}).find("p").text
        release_info.append(text.replace("\n", " ").strip())
    except AttributeError:
        pass

    release_info = "\n".join([item for item in release_info if item])

    try:
        path = item.find("a", {"class": "download icon-download"})["href"]  # type: ignore
    except (AttributeError, KeyError):
        logger.debug("Couldn't get path: %s", item)
        return None

    return Subf2mSubtitle(language, _BASE_URL + path, release_info, episode_number)
