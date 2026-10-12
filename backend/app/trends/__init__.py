"""
Trends Service - personalized news feed for creators.

"""

from app.trends.schemas import TrendingArticle, TrendsResponse
from app.trends.service import get_trends_for_user

__all__ = [
    "TrendingArticle",
    "TrendsResponse",
    "get_trends_for_user",
]
