# coding=utf-8

import operator

from functools import reduce
from flask_restx import Resource, Namespace, fields

from app.database import get_exclusion_clause, TableEpisodes, TableShows, TableMovies
from app.get_providers import get_throttled_providers
from utilities.health import get_health_issues

from ..utils import authenticate

api_ns_badges = Namespace('Badges', description='Get badges count to update the UI (episodes and movies wanted '
                                                'subtitles, providers with issues and health issues.')


@api_ns_badges.route('badges')
class Badges(Resource):
    get_model = api_ns_badges.model('BadgesGet', {
        'episodes': fields.Integer(),
        'movies': fields.Integer(),
        'providers': fields.Integer(),
        'status': fields.Integer(),
    })

    @authenticate
    @api_ns_badges.marshal_with(get_model, code=200)
    @api_ns_badges.response(401, 'Not Authenticated')
    @api_ns_badges.doc(parser=None)
    def get(self):
        """Get badges count to update the UI"""
        episodes_conditions = [(TableEpisodes.missing_subtitles.is_null(False)),
                               (TableEpisodes.missing_subtitles != '[]')]
        episodes_conditions += get_exclusion_clause('series')
        missing_episodes = TableEpisodes.select(TableShows.tags,
                                                TableShows.seriesType,
                                                TableEpisodes.monitored)\
            .join(TableShows, on=(TableEpisodes.sonarrSeriesId == TableShows.sonarrSeriesId))\
            .where(reduce(operator.and_, episodes_conditions))\
            .count()

        movies_conditions = [(TableMovies.missing_subtitles.is_null(False)),
                             (TableMovies.missing_subtitles != '[]')]
        movies_conditions += get_exclusion_clause('movie')
        missing_movies = TableMovies.select(TableMovies.tags,
                                            TableMovies.monitored)\
            .where(reduce(operator.and_, movies_conditions))\
            .count()

        throttled_providers = len(get_throttled_providers())

        health_issues = len(get_health_issues())

        result = {
            "episodes": missing_episodes,
            "movies": missing_movies,
            "providers": throttled_providers,
            "status": health_issues
        }
        return result
